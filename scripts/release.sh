#!/usr/bin/env bash
# 模板一键发布：release-check → 把 template 分支与 tags 推到全部发布远端。
# 发布远端来自本地配置（不入库）：git config --add llmwiki.release-remote <远端名>（可多条）；
# 未配置时默认 origin。也可显式传参：./scripts/release.sh <远端名...>
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
./scripts/release-check.sh template
REMOTES=("$@")
if [ ${#REMOTES[@]} -eq 0 ]; then
    while IFS= read -r r; do REMOTES+=("$r"); done < <(git config --get-all llmwiki.release-remote || true)
fi
[ ${#REMOTES[@]} -eq 0 ] && REMOTES=(origin)
for r in "${REMOTES[@]}"; do
    if git remote get-url "$r" >/dev/null 2>&1; then
        git push "$r" template:main --tags
        echo "✓ 已发布到 $r"
    else
        echo "· 跳过 $r（未配置）"
    fi
done
