# scripts

| 脚本 | 作用 |
|---|---|
| `bootstrap.sh` | 实例初始化：`~/.llm-wiki` 发现软链、全局与项目级 Skill 软链、多工具入口、记忆配置、远端指引 |
| `sync.sh` | ingest 收口自动上传：pull --rebase → commit → push；rebase 冲突停下交人工，无远端仅本地提交 |
| `lint-wiki.py` | wiki 机械体检：断链、索引覆盖、来源/核验节、log 格式、孤儿页等；按脚本位置定位仓根，任意 cwd 可跑（`--root` 供测试夹具） |
| `new-domain.sh` | 生成域扩展口径骨架（`docs/domains/<域>.md`），不预建数据目录 |
