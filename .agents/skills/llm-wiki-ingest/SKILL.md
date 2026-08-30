---
name: llm-wiki-ingest
description: 把新原料编译进个人 LLM Wiki 工作台。用于导入、整理、刷新知识，包括任意项目里排障/分析/学习收口后的默认写入。
---

# LLM Wiki Ingest

**工作台根（$WIKI）**：从当前工作目录向上逐级查找，第一个同时含 `wiki/index.md` 与 `.agents/skills/llm-wiki-ingest/` 的目录即 $WIKI——此时正位于某个 llm-wiki 实例内，专项实例与全局实例同理。未找到时 $WIKI 为 `~/.llm-wiki`（全局发现链，Windows 为 `%USERPROFILE%\.llm-wiki`）；它也不存在则本机未部署工作台，停止并告知用户。下文全部仓内路径以 `$WIKI/` 为前缀。

完整 schema 见 `$WIKI/docs/schemas/wiki.md`。

0. **先判层**：按 `$WIKI/docs/schemas/分区与共享.md` 决定去向——只对当前项目成立的事实留在该项目自己的文档里（不进本工作台）；与单项目绑定但跨会话需要的进 `$WIKI/wiki/projects/<项目>/`；跨项目可复用的进公共层；涉他评价、绩效、未公开事项必须进 `$WIKI/wiki/private/`。同一事实不两写。
1. 确认原料已落盘：对话口述、截图等不可复得的先写 `$WIKI/inputs/manual/<日期>-<主题>.md`；域扩展的数据引用其登记仓库，不复制进本仓。
2. 创建或更新主题页（projects 分区或公共层 concepts / entities / operations / decisions）。每条结论写 `来源` 与 `最后核验`；矛盾保留并标 `待核验`，悬置项进 `$WIKI/wiki/risks/`。
3. 一条经验要回写被改到的实体页和概念页，不要只丢一个案例页。
4. 更新索引：项目分区改自己的 `index.md`；新分区或公共层新页更新根 `$WIKI/wiki/index.md`（两级索引，根只列入口）。
5. 在 `$WIKI/wiki/logs/YYYY-MM.md` 顶部追加 `## [YYYY-MM-DD] ingest | <标题>`；当月文件不存在则创建并更新 `$WIKI/wiki/log.md` 索引。
6. 跑 lint skill（`python3 $WIKI/scripts/lint-wiki.py`），修机械问题。
7. 收口：运行 `$WIKI/scripts/sync.sh "<主题>"` 完成提交与上传（rebase 冲突时脚本会停下交人工）。回复里列出改了哪些页。

凭证红线：密码、token、私钥、kubeconfig、完整连接串不进任何分区（含 private）。
