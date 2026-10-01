#!/usr/bin/env bash
# ingest 收口自动上传：守卫 → 拿仓库级锁 → 按路径暂存 → 生成索引 → 按同一组路径提交 → pull --rebase → push。
# rebase 冲突立即停止交人工，不 force；无远端仍本地提交。
# 用法：
#   sync.sh "<主题>" <路径…>        只提交本轮自己写的路径（文件或目录），外加脚本生成的索引
#   sync.sh --all "<主题>" [路径…]  提交默认范围（wiki、inputs/manual、inputs/common、state、.memory）再加列出的路径
#   sync.sh "<主题>"                有未提交的内容改动时拒绝并列出；没有改动时报「无变更」
# 路径须落在内容白名单内；本轮删除或改名的旧路径只要是已跟踪文件，同样可以传。主题缺省为「自动同步」。
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

# --all 只认第一个参数：明确要求按目录提交默认范围（单会话使用，或确认工作区里全是本会话的改动）
ALL=0
if [ "${1:-}" = "--all" ]; then
    ALL=1
    shift
fi
MSG="ingest: ${1:-自动同步}"
if [ $# -gt 0 ]; then shift; fi
# 主题之后的参数：本轮要提交的路径（须落在 CONTENT_DIRS 之内）
EXTRA_PATHS=("$@")
BRANCH=$(git branch --show-current)

# 内容白名单目录（与 AGENTS.md「提交与分支约定」同一清单）：暂存、判空、提交都只看这些路径。
# 白名单外的骨架改动——哪怕已经暂存——不随 ingest 提交，必须走 worktree。
CONTENT_DIRS=(wiki inputs outputs state .memory)
# --all 的默认范围：本会话通常自己写的路径。inputs/raw（各采集器的快照）与 outputs（成稿）不在其中——
# 并行会话常在这两处留有在途改动，整目录暂存会把别人的半成品卷进本次提交；本轮产出请作为参数显式传入。
DEFAULT_PATHS=(wiki inputs/manual inputs/common state .memory)
# 实例登记要排除的子路径，pathspec 写法，如 ':(exclude)inputs/raw/source-a'。
# 典型用途：定时采集任务自行提交的快照目录，避免把半写快照带进无关的 ingest 提交。
CONTENT_EXCLUDES=()

# 守卫放在任何 add 之前：合并 / 拣选 / 回退 / 变基进行中，或索引被占用时不动仓库。
GITDIR=$(git rev-parse --absolute-git-dir)
if git rev-parse --verify -q MERGE_HEAD >/dev/null 2>&1 \
    || git rev-parse --verify -q CHERRY_PICK_HEAD >/dev/null 2>&1 \
    || git rev-parse --verify -q REVERT_HEAD >/dev/null 2>&1 \
    || [ -d "${GITDIR}/rebase-merge" ] || [ -d "${GITDIR}/rebase-apply" ]; then
    echo "✗ 有进行中的合并 / 拣选 / 回退 / 变基，不自动提交。处理完再重跑 sync.sh。"
    exit 1
fi
if [ -e "${GITDIR}/index.lock" ]; then
    echo "✗ ${GITDIR}/index.lock 被占用（另一个 git 进程在跑），稍后重跑 sync.sh。"
    exit 1
fi
if [ -z "$BRANCH" ]; then
    echo "✗ 处于分离 HEAD，不自动提交。请先切回分支。"
    exit 1
fi
if [ "$BRANCH" != "main" ]; then
    echo "✗ 当前在 ${BRANCH}，sync.sh 只在 main 上提交内容；任务分支的产出请手工 git commit。"
    exit 1
fi

# 路径是否落在内容白名单目录内（等于目录本身或其下）
in_content_dirs() {
    local p="${1%/}" d
    for d in "${CONTENT_DIRS[@]}"; do
        [ "$p" = "$d" ] && return 0
        case "$p" in "$d"/*) return 0 ;; esac
    done
    return 1
}

# 收集内容白名单内的在途改动，结果放进 CHANGES 数组（一项一个路径）。
# $1 为 unstaged 时只收未暂存与未跟踪的（暂存之后用，看还剩什么没带走）；为 all 时收全部未提交改动。
# 实例登记的排除目录不收。用 -z 取路径：不带 -z 时中文与含空格的路径会被转义加引号，没法原样传回给 sync.sh。
CHANGES=()
collect_changes() {
    local mode="$1" entry status path ex skip d
    local -a dirs=()
    CHANGES=()
    for d in "${CONTENT_DIRS[@]}"; do [ -e "$d" ] && dirs+=("$d"); done
    [ ${#dirs[@]} -gt 0 ] || return 0
    while IFS= read -r -d '' entry; do
        status="${entry:0:2}"
        path="${entry:3}"
        # 已暂存的改名 / 复制后面还跟着一项旧路径，读掉不算
        case "${status:0:1}" in R|C) IFS= read -r -d '' _ || true ;; esac
        if [ "$mode" = "unstaged" ]; then
            # 索引列为空或 ? 的才是未暂存 / 未跟踪
            case "${status:0:1}" in " "|"?") ;; *) continue ;; esac
        fi
        skip=0
        for ex in ${CONTENT_EXCLUDES[@]+"${CONTENT_EXCLUDES[@]}"}; do
            ex="${ex#:(exclude)}"
            case "$path" in "$ex"|"$ex"/*) skip=1 ;; esac
        done
        [ "$skip" -eq 1 ] || CHANGES+=("$path")
    done < <(git status --porcelain -z --untracked-files=normal -- "${dirs[@]}" 2>/dev/null)
}

# 组装路径数组：--all 时先放默认范围里存在且未被整目录 gitignore 的路径（目录内的忽略项由 git add 自行排除），
# 再放显式传入的路径（逐个校验在白名单内，且存在于磁盘或是已跟踪文件），最后接上实例登记的排除项。
# 暂存、判空、提交用同一个数组。
PATHSPEC=()
if [ "$ALL" -eq 1 ]; then
    for d in "${DEFAULT_PATHS[@]}"; do
        if [ -e "$d" ] && ! git check-ignore -q "$d"; then
            PATHSPEC+=("$d")
        fi
    done
fi
for p in ${EXTRA_PATHS[@]+"${EXTRA_PATHS[@]}"}; do
    p="${p%/}"
    if ! in_content_dirs "$p"; then
        echo "✗ 路径不在内容白名单内：${p}（白名单：${CONTENT_DIRS[*]}）"
        exit 1
    fi
    if [ ! -e "$p" ] && ! git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
        echo "✗ 路径不存在，也不是已跟踪文件：${p}"
        exit 1
    fi
    PATHSPEC+=("$p")
done
if [ ${#PATHSPEC[@]} -eq 0 ]; then
    if [ "$ALL" -eq 1 ]; then
        echo "· 无内容目录可提交"
        exit 0
    fi
    # 没传路径：不猜哪些是本会话的改动。工作区干净就报无变更，否则列出来让调用方挑。
    collect_changes all
    if [ ${#CHANGES[@]} -eq 0 ]; then
        echo "· 无变更可提交"
        exit 0
    fi
    echo "✗ 没有传入路径。sync.sh 只提交本轮自己写的文件，免得把别的会话没写完的内容带进提交。"
    echo "  当前未提交的内容改动："
    printf '    %s\n' "${CHANGES[@]}"
    echo "  用法：sync.sh \"<主题>\" <路径…>；确认上面全是本会话的改动时，可用 sync.sh --all \"<主题>\"。"
    exit 1
fi
# bash 3.2 在 set -u 下展开空数组会报 unbound variable，故用 ${arr[@]+"${arr[@]}"} 写法
PATHSPEC+=(${CONTENT_EXCLUDES[@]+"${CONTENT_EXCLUDES[@]}"})

# 仓库级锁：同一仓库的多个会话同时收口时排队，暂存到推送这一段不交错。
# 锁是 git 公共目录下的一个目录（mkdir 原子创建，所有工作区共用）；拿不到就每秒重试，超时退出，不自动破锁。
LOCK_DIR="$(cd "$(git rev-parse --git-common-dir)" && pwd)/llm-wiki-sync.lock"
LOCK_TIMEOUT="${LLM_WIKI_SYNC_LOCK_TIMEOUT:-60}"
acquire_lock() {
    local waited=0
    while ! mkdir "$LOCK_DIR" 2>/dev/null; do
        if [ "$waited" -ge "$LOCK_TIMEOUT" ]; then
            echo "✗ 等了 ${LOCK_TIMEOUT} 秒仍拿不到收口锁：${LOCK_DIR}"
            echo "  持有者：$(cat "${LOCK_DIR}/owner" 2>/dev/null || echo 未知)"
            echo "  确认没有别的 sync.sh 在跑之后，手工删除该目录再重试：rm -rf \"${LOCK_DIR}\""
            exit 1
        fi
        if [ "$waited" -eq 0 ]; then
            echo "· 另一个会话正在收口，等待锁（最多 ${LOCK_TIMEOUT} 秒）……"
        fi
        sleep 1
        waited=$((waited + 1))
    done
    printf 'pid %s，%s\n' "$$" "$(date '+%Y-%m-%d %H:%M:%S')" > "${LOCK_DIR}/owner"
    # 只清自己拿到的锁：trap 在拿到之后才登记，超时退出的一方不会删掉别人的锁
    trap 'rm -rf "$LOCK_DIR"' EXIT
}

# 列出白名单内、但没进本次暂存范围的在途改动，只提醒不带走。
report_left_out() {
    collect_changes unstaged
    if [ ${#CHANGES[@]} -gt 0 ]; then
        echo "· 未随本次提交的内容改动（多半是其他会话在途；属于本轮的请补传路径再跑一次：sync.sh \"<主题>\" <路径…>）："
        printf '    %s\n' "${CHANGES[@]}"
    fi
}

# 返回 0 表示提交了，1 表示无变更。
commit_content() {
    local py out generated left
    py=$(command -v python3 || command -v python || true)
    git add -- "${PATHSPEC[@]}"
    if git diff --cached --quiet -- "${PATHSPEC[@]}"; then
        report_left_out
        echo "· 无变更可提交"
        return 1
    fi
    # 公共层分区索引由脚本生成：按已跟踪与本次暂存的页面重写，生成的文件随本次提交。
    # --from-git 不看未跟踪文件，别的会话还没提交的新页不会被写进这次提交的索引。
    if [ -n "$py" ] && [ -f "$ROOT/scripts/build-index.py" ]; then
        if out=$("$py" "$ROOT/scripts/build-index.py" --from-git); then
            while IFS= read -r generated; do
                [ -n "$generated" ] || continue
                git add -- "$generated"
                PATHSPEC+=("$generated")
            done <<< "$out"
        else
            echo "· build-index.py 运行失败，索引未更新（不阻断提交）"
        fi
    fi
    # 提交前跑一次 wiki 机械 lint 并打印，只提示不阻断：内容提交不该被 lint 卡住，但红灯必须被看见。
    if [ -n "$py" ] && [ -f "$ROOT/scripts/lint-wiki.py" ]; then
        echo "· 提交前 lint（只提示，不阻断）："
        "$py" "$ROOT/scripts/lint-wiki.py" | sed 's/^/    /' || true
    fi
    report_left_out
    git commit -q -m "$MSG" -- "${PATHSPEC[@]}"
    left=$(git diff --cached --name-only)
    if [ -n "$left" ]; then
        echo "· 白名单外的已暂存改动未随本次提交（骨架改动请走 worktree）："
        printf '    %s\n' $left
    fi
    return 0
}

acquire_lock

# 模板维护者合一仓（存在本地 template 分支）：origin 是模板发布远端，
# 不接收实例分支——防止把个人内容推上模板仓（尤其公开仓）。
if git show-ref --verify --quiet refs/heads/template; then
    if commit_content; then
        echo "· 模板维护者仓：origin 为模板发布远端，已跳过推送；个人上传请另配 personal 远端"
    fi
elif git remote get-url origin >/dev/null 2>&1; then
    # 先收本地未暂存改动再 rebase，避免脏工作区阻塞
    commit_content || true
    if ! git pull --rebase origin "$BRANCH"; then
        echo "✗ rebase 冲突，已停止。人工解决后重跑 sync.sh；禁止 force。"
        exit 1
    fi
    git push origin "$BRANCH"
    echo "· 已提交并推送到 origin/${BRANCH}"
else
    if commit_content; then
        echo "· 无 origin 远端，仅本地提交（配置远端后自动上传）"
    fi
fi
