# scripts

| 脚本 | 作用 |
|---|---|
| `bootstrap.sh` | 实例初始化：`~/.llm-wiki` 发现软链、全局与项目级 Skill 软链、实例特有 `.worktree-share` 清单、去掉 `main` 的上游跟踪与远端指引；多工具入口、仓内记忆和通用 worktree 钩子委托规则仓 skill `agent-memory-setup` |
| `sync.sh` | ingest 收口自动上传：守卫（合并 / 变基进行中、`index.lock` 被占用、分离 HEAD、不在 `main` 一律拒绝）→ 按内容白名单路径暂存与提交（白名单外已暂存的改动不带走，提交后列出提醒）→ pull --rebase → push；rebase 冲突停下交人工，无远端仅本地提交。实例的排除项登记在 `CONTENT_EXCLUDES` 数组 |
| `lint-wiki.py` | wiki 机械体检：断链、两级索引覆盖与子索引规则、来源/核验节、来源路径存在性（外部仓前缀写法不查）、log 格式、孤儿页（私有区豁免）等；按脚本位置定位仓根，任意 cwd 可跑（`--root` 供测试夹具，`tests/test_lint_wiki.py` 每类检查一红一绿） |
| `new-domain.sh` | 生成域扩展口径骨架（`docs/domains/<域>.md`），不预建数据目录 |
| `hooks/pre-push` | 模板维护者发布保护，见 README「模板升级与维护」 |

编写约定：bash 脚本里变量后面紧跟中文等非 ASCII 字符时，一律写成 `${NAME}`。macOS 自带的 bash 3.2 在 UTF-8 语言环境下会把 `$NAME（` 里全角括号的首字节并入变量名，开了 `set -u` 的脚本直接报 unbound variable 退出。`tests/test_shell_utf8.py` 逐行扫描把关，并在 UTF-8 语言环境下实跑脚本。
