---
name: llm-wiki-lint
description: 检查全局 LLM Wiki 的断链、缺证据、来源路径、日志格式、孤儿页和禁止来源。过期核验由模型步骤做。
---

# LLM Wiki Lint

工作台在 `~/.llm-wiki`（全局软链，任意 cwd 可跑）。

1. 跑 `python3 ~/.llm-wiki/scripts/lint-wiki.py`。
2. 机械问题（断链、未入索引、缺 `来源`/`最后核验`、来源路径不存在、log 格式、根 log 混入条目、孤儿页）可以修。
3. 证据缺口和矛盾记入 `~/.llm-wiki/wiki/risks/`，标 `待核验`，不要臆造修复。
4. 模型还要扫：两页冲突、被新原料否定的旧结论、重要对象缺页、缺交叉引用、长期未核验；项目分区的子 index 与根 index 是否一致。
5. 本次检查改过 wiki 才在 `~/.llm-wiki/wiki/logs/YYYY-MM.md` 追加 `lint` 条目，并 sync。
