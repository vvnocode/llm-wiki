#!/usr/bin/env bash
# ingest 收口自动上传：守卫 → 按路径暂存 → 按同一路径提交 → pull --rebase → push。
# rebase 冲突立即停止交人工，不 force；无远端仍本地提交。
# 用法：sync.sh "<主题>" [路径…]（主题缺省为「自动同步」；路径为本轮要一并提交的成稿与采集快照，须在内容白名单内）
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

MSG="ingest: ${1:-自动同步}"
if [ $# -gt 0 ]; then shift; fi
# 主题之后的参数：本轮要一并提交的成稿与采集快照路径（须落在 CONTENT_DIRS 之内）
EXTRA_PATHS=("$@")
BRANCH=$(git branch --show-current)

# 内容白名单目录（与 AGENTS.md「提交与分支约定」同一清单）：暂存、判空、提交都只看这些路径。
# 白名单外的骨架改动——哪怕已经暂存——不随 ingest 提交，必须走 worktree；并行会话的在途改动也不会被扫进来。
CONTENT_DIRS=(wiki inputs outputs state .memory)
# 默认暂存范围：本会话必然自己写的路径。inputs/raw（各采集器的快照）与 outputs（成稿）不在默认范围——
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

# 组装路径数组：默认范围里存在且未被整目录 gitignore 的路径（目录内的忽略项由 git add 自行排除），
# 加上显式传入的路径（逐个校验在白名单内且存在），再接上实例登记的排除项。暂存、判空、提交用同一个数组。
PATHSPEC=()
for d in "${DEFAULT_PATHS[@]}"; do
    if [ -e "$d" ] && ! git check-ignore -q "$d"; then
        PATHSPEC+=("$d")
    fi
done
for p in ${EXTRA_PATHS[@]+"${EXTRA_PATHS[@]}"}; do
    p="${p%/}"
    if ! in_content_dirs "$p"; then
        echo "✗ 路径不在内容白名单内：${p}（白名单：${CONTENT_DIRS[*]}）"
        exit 1
    fi
    if [ ! -e "$p" ]; then
        echo "✗ 路径不存在：${p}"
        exit 1
    fi
    PATHSPEC+=("$p")
done
if [ ${#PATHSPEC[@]} -eq 0 ]; then
    echo "· 无内容目录可提交"
    exit 0
fi
# bash 3.2 在 set -u 下展开空数组会报 unbound variable，故用 ${arr[@]+"${arr[@]}"} 写法
PATHSPEC+=(${CONTENT_EXCLUDES[@]+"${CONTENT_EXCLUDES[@]}"})

# 列出白名单内、但没进本次暂存范围的在途改动（多半是其他会话的采集快照或成稿），只提醒不带走。
# 实例登记的排除目录（定时任务自己提交）不列。索引列为空或 ? 的才是未暂存 / 未跟踪。
report_left_out() {
    local line path ex skip d
    local -a lines=() dirs=()
    for d in "${CONTENT_DIRS[@]}"; do [ -e "$d" ] && dirs+=("$d"); done
    [ ${#dirs[@]} -gt 0 ] || return 0
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        case "${line:0:1}" in " "|"?") ;; *) continue ;; esac
        path="${line:3}"
        skip=0
        for ex in ${CONTENT_EXCLUDES[@]+"${CONTENT_EXCLUDES[@]}"}; do
            ex="${ex#:(exclude)}"
            case "$path" in "$ex"|"$ex"/*) skip=1 ;; esac
        done
        [ "$skip" -eq 1 ] || lines+=("$path")
    done < <(git status --porcelain --untracked-files=normal -- "${dirs[@]}" 2>/dev/null)
    if [ ${#lines[@]} -gt 0 ]; then
        echo "· 未随本次提交的内容改动（多半是其他会话在途；本轮产出请显式传路径：sync.sh \"<主题>\" <路径…>）："
        printf '    %s\n' "${lines[@]}"
    fi
}

# 返回 0 表示提交了，1 表示无变更。
commit_content() {
    # 提交前跑一次 wiki 机械 lint 并打印，只提示不阻断：内容提交不该被 lint 卡住，但红灯必须被看见。
    if [ -f "$ROOT/scripts/lint-wiki.py" ]; then
        local py
        py=$(command -v python3 || command -v python || true)
        if [ -n "$py" ]; then
            echo "· 提交前 lint（只提示，不阻断）："
            "$py" "$ROOT/scripts/lint-wiki.py" | sed 's/^/    /' || true
        fi
    fi
    git add -- "${PATHSPEC[@]}"
    report_left_out
    if git diff --cached --quiet -- "${PATHSPEC[@]}"; then
        echo "· 无变更可提交"
        return 1
    fi
    git commit -q -m "$MSG" -- "${PATHSPEC[@]}"
    local left
    left=$(git diff --cached --name-only)
    if [ -n "$left" ]; then
        echo "· 白名单外的已暂存改动未随本次提交（骨架改动请走 worktree）："
        printf '    %s\n' $left
    fi
    return 0
}

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
