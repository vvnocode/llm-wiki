---
name: llm-wiki-learn
description: 系统学习与教材化整理：学习路线、教材式章节、实践练习、测验与掌握验收。学习类内容的编译与进度管理。
---

# LLM Wiki Learn

工作台在 `~/.llm-wiki`（全局软链）。学习区结构见 `~/.llm-wiki/wiki/learning/README.md`。

1. **定路线**：明确学习目标后，在 `~/.llm-wiki/wiki/learning/paths/<主题>.md` 写学习路线（目标 → 章节序列 → 验收方式），并更新 `~/.llm-wiki/wiki/learning/index.md`（在学什么、进度、下一步）。
2. **写章节**：教材式讲解落 `~/.llm-wiki/wiki/learning/chapters/`，系统化、带来源（官方文档、源码、实测），不确定的标「待核验」。
3. **配练习**：需要动手的主题在 `~/.llm-wiki/wiki/learning/labs/` 写实践练习（目标、步骤、预期结果）。
4. **验收**：`~/.llm-wiki/wiki/learning/assessments/` 出题并记录作答结果。**未通过验收不得在任何页面把该主题标记为「已掌握」**；未过的差距写回对应章节的复习点。
5. 面向输出的讲义、导出教材放 `~/.llm-wiki/outputs/learning/`（可再生成，不是 wiki）。
6. 学习中沉淀出的跨项目通用结论按 ingest skill 的分层判据写入公共层；涉他内容进 `~/.llm-wiki/wiki/private/`。
7. 收口：追加 `~/.llm-wiki/wiki/logs/YYYY-MM.md` 条目（动作用 ingest），跑 lint，运行 `~/.llm-wiki/scripts/sync.sh "<主题>"`。
