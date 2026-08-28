# 记忆与多 Agent

目标：Claude Code 和 Codex（以及以后别的 Agent）共用**一份指令、一份仓库内记忆**。换工具不丢上下文。

## 为什么要管

| | Claude Code | Codex |
|---|---|---|
| 读项目指令 | 只读 `CLAUDE.md`（**不读 `AGENTS.md`**） | 只读 `AGENTS.md` |
| 记忆目录可改 | 能：`autoMemoryDirectory` | **不能**，固定 `$CODEX_HOME/memories` |
| 项目级配置 | `.claude/settings.local.json` | `.codex/config.toml`（**需项目被信任**） |

不管的话：指令两份会漂，记忆写到家目录，换人或换机器就没了。

## 本仓库已经做好的

1. `AGENTS.md` 是唯一正本；`CLAUDE.md` 由 `bootstrap.sh` 链过去。
2. Claude 的记忆被指到 `.memory/`（本机绝对路径写在不入库的 `settings.local.json`）。
3. Codex 自带记忆三项全关，改由 `AGENTS.md` 约束它往 `.memory/` 写。
4. 以上配置全部由 `bootstrap.sh` 自动完成并保持幂等；本文件记录机制与陷阱，供排查时查阅。

换新机器只需要再跑 `./scripts/bootstrap.sh`，再（若用 Codex）把本目录标为 trusted。

## 记忆写什么

只记「换个会话仍然有用、且代码和 Git 历史里读不出来」的事：

- 用户偏好（先找成熟方案、末尾要总结）
- 纠正过的做法（呈现层也要固化、文风管交付物）
- 外部资源指针
- 非显然的约束

不记：代码结构、已修复的 bug、本次会话的临时结论、领域对象（那是 wiki）。

格式：

- `.memory/MEMORY.md` 是索引，每条一行
- 每条记忆一个 `.md`，含 `name` / `description` / `metadata.type`
- `type` 取 `user` | `feedback` | `project` | `reference`
- 写入前先查有没有已覆盖该事实的文件，有就改，不新建重复条目

## 陷阱

| 陷阱 | 后果 | 应对 |
|---|---|---|
| 没有 `CLAUDE.md` | Claude 完全不读项目规则，无任何提示 | bootstrap 会建软链 |
| Codex 项目未被信任 | 项目级 `.codex/` 整体不加载，静默失效 | `~/.codex/config.toml` 加 trusted |
| 用 `codex doctor` 验证项目配置 | doctor 只报全局值，会得出反向结论 | 按下方「验证」节直接问 Codex 或查生效配置 |
| 只关 `generate_memories` | `add_ad_hoc_note` 仍往仓库外写 | 三项一起关 |
| 去清 `~/.codex/memories` | 后台管线会按会话更新时间重建 | 接受副本；本项目读不回来 |

后台记忆管线读的是**全局** `~/.codex/config.toml`。项目级 `generate_memories = false` 挡不住它。要彻底停只能改全局，代价是所有项目的自动记忆一起停。本脚手架选择不改全局。

## 验证

```bash
# Claude 是否读到指令
# 在本目录开 Claude Code，问：不用工具，复述项目指令里关于 wiki 写入门的那条

# Codex 项目配置是否生效：确认本目录 trusted 后，在本目录开 Codex，
# 问：不用工具，复述项目指令里关于记忆写入位置的那条
```
