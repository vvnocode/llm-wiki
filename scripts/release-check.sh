#!/usr/bin/env bash
# 模板发布前安全检查：扫描 template 分支的全部已跟踪文件内容。
# 检查三类：内网 IP、凭证模式、本地敏感词表（.release-check-local，gitignore，维护者自建）。
# 供 pre-push hook 调用（推送含 template 的 ref 前阻断），也可手动执行。
# 退出码：0 干净；1 有命中（逐条列出，不自动修改）。
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
REF=${1:-template}
FAIL=0

check() {
    # check <说明> <grep -E 模式>
    local label=$1 pattern=$2 hits
    hits=$(git grep -nIE "$pattern" "$REF" -- . 2>/dev/null | grep -v "scripts/release-check.sh" || true)
    if [ -n "$hits" ]; then
        echo "✗ ${label}："
        echo "$hits" | head -20
        FAIL=1
    fi
}

# 1) 内网 IP（10.x / 172.16-31.x / 192.168.x）
check "内网 IP 地址" '\b(10|192\.168)\.[0-9]{1,3}\.[0-9]{1,3}\b|\b172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}\b'

# 2) 凭证模式（私钥块、常见 token 前缀、赋值形态的密码/令牌）
check "疑似凭证" 'BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{15,}|sk-[A-Za-z0-9]{20,}|(password|passwd|token|secret)[[:space:]]*[:=][[:space:]]*[^[:space:]<{$#]'

# 3) 本地敏感词表（一行一词；公司名、人名、内部域名等，文件不入库）
LOCAL_LIST="$ROOT/.release-check-local"
if [ -f "$LOCAL_LIST" ]; then
    while IFS= read -r word; do
        [ -z "$word" ] && continue
        case "$word" in \#*) continue ;; esac
        check "本地词表命中「$word」" "$word"
    done < "$LOCAL_LIST"
else
    echo "· 提示：未找到 $LOCAL_LIST（本地敏感词表，建议维护者创建，已被 gitignore）"
fi

if [ "$FAIL" -eq 0 ]; then
    echo "✓ release-check 通过（$REF 分支已跟踪内容未命中敏感模式）"
fi
exit $FAIL
