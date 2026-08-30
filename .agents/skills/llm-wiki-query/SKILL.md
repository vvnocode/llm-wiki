---
name: llm-wiki-query
description: 分析、设计、排障、学习或回答跨项目问题。先用已编译的工作台 wiki，再回查项目源码与原料，有复用结论就写回。
---

# LLM Wiki Query

**工作台根（$WIKI）**：从当前工作目录向上逐级查找，第一个同时含 `wiki/index.md` 与 `.agents/skills/llm-wiki-ingest/` 的目录即 $WIKI——此时正位于某个 llm-wiki 实例内，专项实例与全局实例同理。未找到时 $WIKI 为 `~/.llm-wiki`（全局发现链，Windows 为 `%USERPROFILE%\.llm-wiki`）；它也不存在则本机未部署工作台，停止并告知用户。下文全部仓内路径以 `$WIKI/` 为前缀。

wiki 与所在项目的源码/文档两头都要查。

1. 读 `$WIKI/wiki/index.md`；命中项目分区则进 `$WIKI/wiki/projects/<项目>/index.md` 下钻，再读命中的 concepts / entities / operations / risks 页。
2. 回答里分开三块：Wiki 结论 / 回查过的事实 / 待核验。
3. 接口、部署、安全、当前运行状态等易变事实，必须回查当前项目源码、`$WIKI/config/registry.md` 登记的仓库或数据源后再信；不要只根据 wiki 下操作指令。
4. 任务产生可复用的架构、方法、决策或根因时，按 ingest skill 写回对应分区、索引与当月 log；用户当轮说「不用」才跳过。
5. 排障不写口令、不改本机凭据文件；写远程状态前确认对象与字段，执行后回查。
6. 写过 wiki 就跑 lint skill 并 sync。
