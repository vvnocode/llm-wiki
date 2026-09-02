#!/usr/bin/env bash
# 任务 worktree 的建立、本机资产共享与回收。
#
#   worktree.sh add <任务名> [基线]           在 <仓根>/.worktrees/<任务名> 建 worktree（新建同名分支；基线缺省为根工作区当前 HEAD），随即 link
#   worktree.sh link [worktree路径]           幂等：按 config/worktree-share.conf 把根工作区里被 gitignore 排除的本机资产软链进 worktree
#                                             （缺省为当前目录所在 worktree；对根工作区只提示不动作）
#   worktree.sh remove <任务名|worktree路径>  先把 worktree 内新产生的被忽略文件回收到根工作区（已存在的不覆盖），再 git worktree remove；
#                                             被拒绝时列出原因交人工，不 --force；分支保留，合入后人工删除
#
# 背景：git worktree add 只检出入库文件。repos/ 克隆、采集游标、私有区、.claude/settings.local.json（记忆目录指向）
# 等被 gitignore 的本机资产在新 worktree 里全部缺失，会话因此丢约束、丢数据。软链（不复制、不入库）让所有
# worktree 共用根工作区这一份，写入也落回根工作区。
#
# 约束：共享目录对应的 .gitignore 规则不得带尾斜杠——尾斜杠规则只匹配真实目录，不匹配 worktree 里的软链，
# 软链会变成未跟踪文件并被 sync.sh 暂存。脚本对每条新建软链做 check-ignore 复核，未被忽略即撤销并告警。
#
# 仓根 = 目标 worktree 所属仓库的主 worktree（git worktree list 首行），与脚本所在位置无关。
# scripts/hooks/post-checkout 在 git worktree add 后调用本脚本 link，裸 git 命令与 Claude Code 的
# .claude/worktrees/ 同样覆盖；本脚本的 add 只是「建 worktree + link」的显式入口。
set -euo pipefail

CONF_REL="config/worktree-share.conf"
# link 的计数（新建 / 已就位 / 告警），在 do_link 里归零
N_NEW=0
N_OK=0
N_WARN=0

usage() {
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

# 目录的真实路径（去软链；macOS 的 /tmp、/var 都是软链，比较路径前必须归一）
realpath_of() {
    (cd "$1" && pwd -P)
}

# 主 worktree（仓根）的真实路径：git worktree list 首行固定是主 worktree
main_worktree_of() {
    local first
    first=$(git -C "$1" worktree list --porcelain | head -1 | sed 's/^worktree //')
    realpath_of "$first"
}

# 读共享清单：根工作区与目标 worktree 两份取并集——分支里新增的前缀合入前就生效，机制引入本身
# 也靠此在 worktree 里先跑通。去注释行、去空行、去尾斜杠与前导 ./；两份都缺才报错。
read_share_list() {
    local root=$1 wt=${2:-} f files=()
    for f in "$root/$CONF_REL" "${wt:+$wt/$CONF_REL}"; do
        [ -n "$f" ] && [ -f "$f" ] && files+=("$f")
    done
    if [ ${#files[@]} -eq 0 ]; then
        echo "✗ 缺少 ${CONF_REL}（模板 v0.2.5 起随骨架提供；升级后缺失请从 upstream/template 取回）" >&2
        return 1
    fi
    cat "${files[@]}" | grep -v '^[[:space:]]*#' | sed -e 's/[[:space:]]*$//' -e 's#^\./##' -e 's#/*$##' | grep -v '^$' | sort -u || true
}

# 在 worktree 里为一条相对路径建软链，指向根工作区同路径。
# 已就位则计数；worktree 里已有真实文件/目录或指向别处的软链则不动只告警；
# 新建后用 check-ignore 复核，没被忽略（典型原因：.gitignore 规则带尾斜杠）就撤销并告警。
link_one() {
    local root=$1 wt=$2 rel=$3 src dst
    src="$root/$rel"
    dst="$wt/$rel"
    case "$(basename "$rel")" in
        .DS_Store|__pycache__) return 0 ;;   # 系统与解释器垃圾，不值得链
    esac
    if [ -L "$dst" ]; then
        if [ "$(readlink "$dst")" = "$src" ]; then
            N_OK=$((N_OK + 1))
        else
            echo "⚠ ${rel} 已是软链但指向 $(readlink "$dst")，未覆盖"
            N_WARN=$((N_WARN + 1))
        fi
        return 0
    fi
    if [ -e "$dst" ]; then
        echo "⚠ $rel 在 worktree 里已是真实文件/目录，未覆盖（remove 时会回收到根工作区）"
        N_WARN=$((N_WARN + 1))
        return 0
    fi
    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
    if ! git -C "$wt" check-ignore -q -- "$rel"; then
        rm "$dst"
        echo "⚠ $rel 的软链未被 .gitignore 忽略，已撤销——目录规则带尾斜杠只匹配真实目录，请改为不带尾斜杠的写法"
        N_WARN=$((N_WARN + 1))
        return 0
    fi
    echo "· 已链 $rel"
    N_NEW=$((N_NEW + 1))
}

# 把根工作区的本机资产软链进目标 worktree。
# 前缀整个被忽略（state/collectors、settings.local.json）：一条软链；
# 前缀本身入库（repos/ 有 .gitkeep、wiki/private/ 有 README）：逐条链接其下被忽略的条目，
# 粒度取 git status --ignored=matching 的结果（命中忽略规则的条目本身；只含被忽略内容、自身不命中规则的
# 目录不整目录折叠，否则其软链在 worktree 里不会被忽略）。
# 只链 `!!`（被忽略）条目；根工作区里尚未提交的 `??` 文件属于待提交内容，不链。
do_link() {
    local wt root list prefix entry
    wt=$(realpath_of "$1")
    root=$(main_worktree_of "$wt")
    if [ "$wt" = "$root" ]; then
        echo "· $wt 是根工作区，本机资产本就在此，无需链接"
        return 0
    fi
    list=$(read_share_list "$root" "$wt") || return 1
    N_NEW=0; N_OK=0; N_WARN=0
    echo "═══ worktree 共享：$root → $wt ═══"
    while IFS= read -r prefix; do
        [ -n "$prefix" ] || continue
        if [ ! -e "$root/$prefix" ] && [ ! -L "$root/$prefix" ]; then
            continue   # 根工作区尚无此资产（如新实例还没 clone 过 repos/）
        fi
        if git -C "$root" check-ignore -q -- "$prefix"; then
            link_one "$root" "$wt" "$prefix"
            continue
        fi
        while IFS= read -r -d '' entry; do
            case "$entry" in
                '!! '*) entry=${entry#\!\! } ;;
                *) continue ;;
            esac
            entry=${entry%/}
            link_one "$root" "$wt" "$entry"
        done < <(git -C "$root" status --ignored=matching --porcelain -z --untracked-files=normal -- "$prefix")
    done <<< "$list"
    echo "✓ 新建 ${N_NEW}，已就位 ${N_OK}，告警 ${N_WARN}"
}

# 建 worktree 并挂载共享资产。清单缺失时在建 worktree 前就失败，避免留下半成品。
do_add() {
    local name=$1 base=$2 root wt
    root=$(main_worktree_of "$PWD")
    read_share_list "$root" >/dev/null || return 1
    wt="$root/.worktrees/$name"
    if [ -e "$wt" ]; then
        echo "✗ $wt 已存在" >&2
        return 1
    fi
    git -C "$root" worktree add "$wt" -b "$name" "$base"
    do_link "$wt"
    echo "✓ worktree：${wt}（分支 ${name}，基线 ${base}）"
}

# 回收 worktree 内新产生的被忽略文件，再删除 worktree。
# 只回收共享前缀下、非软链的真实文件（--untracked-files=all 已展开到文件，软链目录不会被深入）；
# 根工作区已有同路径的一律不覆盖并逐条列出。
do_remove() {
    local arg=$1 root wt p registered=0 list prefix entry copied=0 skipped=0
    root=$(main_worktree_of "$PWD")
    if [ -d "$arg" ]; then
        wt=$(realpath_of "$arg")
    else
        wt="$root/.worktrees/$arg"
    fi
    if [ ! -d "$wt" ]; then
        echo "✗ 找不到 worktree：$wt" >&2
        return 1
    fi
    if [ "$wt" = "$root" ]; then
        echo "✗ 不能删除根工作区" >&2
        return 1
    fi
    while IFS= read -r p; do
        [ -d "$p" ] && [ "$(realpath_of "$p")" = "$wt" ] && registered=1
    done < <(git -C "$root" worktree list --porcelain | sed -n 's/^worktree //p')
    if [ "$registered" != 1 ]; then
        echo "✗ $wt 不是本仓登记的 worktree" >&2
        return 1
    fi
    list=$(read_share_list "$root" "$wt") || return 1
    echo "═══ 回收 worktree 内的本机资产：$wt → $root ═══"
    while IFS= read -r prefix; do
        [ -n "$prefix" ] || continue
        [ -e "$wt/$prefix" ] || continue
        [ -L "$wt/$prefix" ] && continue   # 整个前缀是软链，内容本就在根工作区
        while IFS= read -r -d '' entry; do
            case "$entry" in
                '!! '*) entry=${entry#\!\! } ;;
                *) continue ;;
            esac
            [ -L "$wt/$entry" ] && continue   # 共享软链本身
            [ -f "$wt/$entry" ] || continue
            if [ -e "$root/$entry" ] || [ -L "$root/$entry" ]; then
                echo "· 跳过 ${entry}（根工作区已有，未覆盖）"
                skipped=$((skipped + 1))
                continue
            fi
            mkdir -p "$(dirname "$root/$entry")"
            cp -p "$wt/$entry" "$root/$entry"
            echo "· 回收 $entry"
            copied=$((copied + 1))
        done < <(git -C "$wt" status --ignored --porcelain -z --untracked-files=all -- "$prefix")
    done <<< "$list"
    echo "✓ 回收 ${copied} 个文件到根工作区（跳过 ${skipped} 个已存在的）"
    if ! git -C "$root" worktree remove "$wt"; then
        echo "✗ git worktree remove 被拒绝：worktree 内仍有未提交的改动或未跟踪文件——" >&2
        git -C "$wt" status --short | head -20 >&2
        echo "  请先提交或清理后重试，不要 --force。" >&2
        return 1
    fi
    echo "✓ 已删除 worktree ${wt}；分支未删除，合入后请执行 git branch -d <分支>"
}

case "${1:-}" in
    add)
        [ $# -ge 2 ] && [ $# -le 3 ] || usage
        do_add "$2" "${3:-HEAD}"
        ;;
    link)
        [ $# -le 2 ] || usage
        do_link "${2:-$PWD}"
        ;;
    remove)
        [ $# -eq 2 ] || usage
        do_remove "$2"
        ;;
    *)
        usage
        ;;
esac
