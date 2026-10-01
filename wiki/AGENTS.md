# Wiki 目录内规则

本文件给在 `wiki/` 下工作的 Agent 看。完整 schema 是仓库根的 `docs/schemas/wiki.md`，不要在这里复制长文。

- 本目录由 LLM 维护。不要改 `inputs/raw/` 或 `repos/`。
- 含事实结论的页面必须有 `来源` 和 `最后核验`；冲突标 `待核验`，写入 `wiki/risks/` 下对应主题的页。
- 公共层分区（concepts / entities / operations / decisions / risks）的 `index.md` 由 `scripts/build-index.py` 生成，不要手改；项目分区增删页面时更新该分区自己的 `index.md`。根 `index.md` 只列分区入口，不随每次写入更新。
- 演进日志写入 `logs/YYYY-MM.md`；根 `log.md` 只做月份索引。
- 格式：`## [YYYY-MM-DD] ingest|query|lint|correct|ops | 标题`
