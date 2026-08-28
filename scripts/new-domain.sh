#!/usr/bin/env bash
# 新业务域三件套草稿。不预建空的 outputs 或 raw。
# 用法：./scripts/new-domain.sh <英文短名>
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
NAME=${1:-}
if [ -z "$NAME" ]; then
    echo "用法：$0 <英文短名>   例如 oncall"
    exit 1
fi
if [[ ! "$NAME" =~ ^[a-z][a-z0-9-]*$ ]]; then
    echo "短名用小写字母、数字、连字符。"
    exit 1
fi

DOC="$ROOT/docs/domains/${NAME}.md"
if [ -e "$DOC" ]; then
    echo "已存在 $DOC"
    exit 1
fi

mkdir -p "$ROOT/docs/domains"
cat > "$DOC" <<EOF
# ${NAME}口径

## 何时用

用户说哪些话时走本文件。

## 数据从哪来

来源、脚本、落盘位置、新鲜度阈值。登记在 \`config/registry.md\` 的「域扩展」表。

## 时间怎么切

快照还是切片；分析时按哪个字段筛。

## 范围

谁 / 哪个系统算本域。和 \`inputs/common/\` 基准文件的关系。

## 分析前先看

完整性字段。不完整就先补采。

## 陷阱

踩过的坑，每条一两句。

## 产出

成稿路径、要不要 HTML、有没有模板。
EOF

echo "已写 $DOC"
echo "下一步："
echo "  1. 在 AGENTS.md 业务域路由加一行"
echo "  2. 有采集脚本时再 mkdir inputs/raw/${NAME}，并在 config/registry.md 域扩展表登一行"
echo "  3. 稳定结论出现后再建 wiki/projects/${NAME}/，不要预建空 wiki"
echo "  4. 需要固定风格再在域扩展仓内建 templates/${NAME}模板.md"
