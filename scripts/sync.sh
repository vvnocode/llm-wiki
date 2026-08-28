#!/usr/bin/env bash
# ingest 收口自动上传：pull --rebase → commit → push。
# rebase 冲突立即停止交人工，不 force；无远端仍本地提交。
# 用法：sync.sh "<主题>"（缺省为「自动同步」）
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

MSG="ingest: ${1:-自动同步}"
BRANCH=$(git branch --show-current)

if [ -z "$BRANCH" ]; then
    echo "✗ 处于分离 HEAD，不自动提交。请先切回分支。"
    exit 1
fi

# 模板维护者合一仓（存在本地 template 分支）：origin 是模板发布远端，
# 不接收实例分支——防止把个人内容推上模板仓（尤其公开仓）。
if git show-ref --verify --quiet refs/heads/template; then
    git add -A
    if git diff --cached --quiet; then
        echo "· 无变更可提交"
    else
        git commit -m "$MSG"
        echo "· 模板维护者仓：origin 为模板发布远端，已跳过推送；个人上传请另配 personal 远端"
    fi
elif git remote get-url origin >/dev/null 2>&1; then
    # 先收本地未暂存改动再 rebase，避免脏工作区阻塞
    git add -A
    if ! git diff --cached --quiet; then
        git commit -m "$MSG"
    fi
    if ! git pull --rebase origin "$BRANCH"; then
        echo "✗ rebase 冲突，已停止。人工解决后重跑 sync.sh；禁止 force。"
        exit 1
    fi
    git push origin "$BRANCH"
    echo "· 已提交并推送到 origin/$BRANCH"
else
    git add -A
    if git diff --cached --quiet; then
        echo "· 无变更可提交"
    else
        git commit -m "$MSG"
        echo "· 无 origin 远端，仅本地提交（配置远端后自动上传）"
    fi
fi
