# scripts

| 脚本 | 作用 |
|---|---|
| `bootstrap.sh` | 实例初始化：`~/.llm-wiki` 发现软链、全局与项目级 Skill 软链、多工具入口、记忆配置、worktree 共享钩子、远端指引 |
| `sync.sh` | ingest 收口自动上传：pull --rebase → commit → push；rebase 冲突停下交人工，无远端仅本地提交 |
| `lint-wiki.py` | wiki 机械体检：断链、索引覆盖、来源/核验节、log 格式、孤儿页等；按脚本位置定位仓根，任意 cwd 可跑（`--root` 供测试夹具） |
| `new-domain.sh` | 生成域扩展口径骨架（`docs/domains/<域>.md`），不预建数据目录 |
| `worktree.sh` | 任务 worktree：`add` 建 `.worktrees/<任务名>` 并挂载共享资产；`link` 幂等挂载（钩子也调它，位置无关）；`remove` 回收 worktree 内新产生的被忽略文件后删除。清单 `config/worktree-share.conf` |
| `hooks/post-checkout` | `git worktree add` 后自动执行 `worktree.sh link`；bootstrap 软链到 `.git/hooks/`（Windows 复制副本） |
| `hooks/pre-push` | 模板维护者发布保护，见 README「模板升级与维护」 |
