---
name: llm-wiki-lint
description: 检查 LLM Wiki 工作台的断链、缺证据、来源路径、日志格式、孤儿页和禁止来源。过期核验由模型步骤做。
---

# LLM Wiki Lint

**工作台根（$WIKI）**：从当前工作目录向上逐级查找，第一个同时含 `wiki/index.md` 与 `.agents/skills/llm-wiki-ingest/` 的目录即 $WIKI——此时正位于某个 llm-wiki 实例内，专项实例与全局实例同理。未找到时 $WIKI 为 `~/.llm-wiki`（全局发现链，Windows 为 `%USERPROFILE%\.llm-wiki`）；它也不存在则本机未部署工作台，停止并告知用户。下文全部仓内路径以 `$WIKI/` 为前缀。

1. 跑 `python3 $WIKI/scripts/lint-wiki.py`。
2. 机械问题（断链、未入索引、缺 `来源`/`最后核验`、来源路径不存在、log 格式、根 log 混入条目、孤儿页）可以修。
3. 证据缺口和矛盾记入 `$WIKI/wiki/risks/`，标 `待核验`，不要臆造修复。
4. 模型还要扫：两页冲突、被新原料否定的旧结论、重要对象缺页、缺交叉引用、长期未核验；项目分区的子 index 与根 index 是否一致。
5. 本次检查改过 wiki 才在 `$WIKI/wiki/logs/YYYY-MM.md` 追加 `lint` 条目，并 sync。
