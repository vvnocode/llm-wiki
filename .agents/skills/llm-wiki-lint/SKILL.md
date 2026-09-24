---
name: llm-wiki-lint
description: 检查 LLM Wiki 工作台的断链、缺证据、来源路径、日志格式、孤儿页和禁止来源。过期核验由模型步骤做。
---

# LLM Wiki Lint

**工作台根（$WIKI）**：从当前工作目录向上逐级查找，第一个同时含 `wiki/index.md` 与 `.agents/skills/llm-wiki-ingest/` 的目录即 $WIKI——此时正位于某个 llm-wiki 实例内，专项实例与全局实例同理。未找到时 $WIKI 为 `~/.llm-wiki`（全局发现链，Windows 为 `%USERPROFILE%\.llm-wiki`）；它也不存在则本机未部署工作台，停止并告知用户。下文全部仓内路径以 `$WIKI/` 为前缀。

1. 跑 `python3 $WIKI/scripts/lint-wiki.py`。
2. 机械问题（断链、未入索引、子索引未入根 index、缺 `来源`/`最后核验`、来源路径不存在、log 格式、根 log 混入条目、孤儿页）可以修。私有区页面不进根索引、不算孤儿，脚本已豁免；外部仓来源改成 `<登记名>[@<ref>]:<仓内路径>` 写法即不再按本仓路径检查。
3. 证据缺口和矛盾记入 `$WIKI/wiki/risks/`，标 `待核验`，不要臆造修复。
4. 语义层固定六项，逐项给结论：两页冲突；被新原料否定的旧结论还留着；重要对象缺页（只有口误、没有自己的页）；缺交叉引用；能靠读代码或公开文档补上的缺口；长期待核验未处理。项目分区的子 index 与根 index 是否一致也在此查。脚本末尾的「提示」项（最后核验只到月份）随下次回写换成 YYYY-MM-DD，不为消提示空改日期。
5. 每次跑完都在 `$WIKI/wiki/logs/YYYY-MM.md` 追加一条 `lint` 条目，不论是否改动：第一行写机械项数（脚本输出），再按六项各写一行「无」或指向 `$WIKI/wiki/risks/open-questions.md` 的条目；改过页面的列出页名。没有日志的语义 lint 等于没做。然后 sync。
