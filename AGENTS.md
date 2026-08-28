# AGENTS.md

## 项目定位

这是一个**通用的个人全局 LLM Wiki 工作台**：任何 vibe coding agent、在任何项目里形成的可复用知识，都沉淀到这一份 wiki。实例通过固定软链 `~/.llm-wiki` 被全局指令发现；跨项目路由由全局指令（如 claude.md 规则仓的「全局知识工作台」节）承担，本文件约束「进入本目录工作」的会话。

原料进入 `inputs/`，编译进 `wiki/`，可再生成的交付物进 `outputs/`。开始领域任务时，先读 `wiki/index.md` 和命中页；接口、部署与安全事实必须回查所在项目源码或登记数据源，不能只信 Wiki。

## 四层分离

- `inputs/manual/` 记录对话中提供、丢失后无法复得的事实（`<日期>-<主题>.md`）；`inputs/raw/`、`inputs/common/` 由域扩展按需建立，原始快照只采集不改写。
- `repos/` 只用于 clone/fetch 和分析，不安装依赖、不构建、不回写外部仓库。
- `wiki/` 只维护经过来源约束的编译知识；事实页必须包含「来源」和「最后核验」。
- `docs/`、`config/`、本文件和 `.agents/skills/` 是规则与 schema；`outputs/` 是可再生成的交付物，不是 Wiki。

## 三级写入门与分区

写入前先判「记到哪一层」，完整判据见 `docs/schemas/分区与共享.md`：

| 层 | 判据 |
|---|---|
| 项目内（该项目自己的文档） | 只对该项目成立、离开项目无意义 |
| `wiki/projects/<项目>/` | 与单项目绑定、但跨会话仍需要 |
| `wiki/` 公共层 | 跨项目可复用的概念、方法、决策、实体 |

同一事实不两写。**私有区** `wiki/private/` 已被 gitignore、物理不出本机：对他人的评价、绩效、薪酬、未公开事项必须写在这里。

## Ingest 收口与自动上传

任务形成跨会话价值时默认 ingest（用户当轮说「不用」才跳过）；ingest 完成后运行 `~/.llm-wiki/scripts/sync.sh "<主题>"` 完成提交与上传。rebase 冲突时脚本会停下交人工，禁止 force。

## 数据与凭证

- 凭证只使用用户本机已有登录缓存或钥匙串。禁止读取或提交密码、token、私钥、kubeconfig、完整连接串和主目录凭据文件——任何分区（含 private）都不例外。
- 写远程状态、发消息、改配置或重启服务前确认对象、字段和操作者，执行后回查。

## Skill 路由

- 导入、整理、更新知识：`~/.llm-wiki/.agents/skills/llm-wiki-ingest/SKILL.md`
- 分析、设计、排障、跨项目提问：`~/.llm-wiki/.agents/skills/llm-wiki-query/SKILL.md`
- 检查 Wiki：`~/.llm-wiki/.agents/skills/llm-wiki-lint/SKILL.md`
- 系统学习、教材化整理、验收：`~/.llm-wiki/.agents/skills/llm-wiki-learn/SKILL.md`

## 域扩展与路径登记

内核不含任何业务采集器。接入采集类数据源（聊天工具、项目管理系统、邮箱等）按 `docs/workflows/新业务域落地.md` 建立独立域扩展，并在 `config/registry.md` 登记路径与敏感级别。个人项目仓库同样只在 `config/registry.md` 登记。

## 模板与实例

本仓从模板（上游 `template` 历史）实例化而来：骨架文件（`docs/schemas/`、`.agents/skills/`、`scripts/`、`tests/`、根说明文件）由模板演进，升级用 `git merge`（upstream 或本仓 `template` 分支）；`wiki/`、`inputs/` 内容目录归个人，模板永不触碰。

## 多工具入口

`AGENTS.md` 是唯一指令正本；`CLAUDE.md` 兼容入口与 `.claude/skills/`、`.codex/skills/` 兼容链接不入库，由 bootstrap 按平台生成（macOS/Linux 软链，Windows junction/副本）。项目级 Skill 的 canonical 位于 `.agents/skills/`；全局挂载由 bootstrap 链到 `~/.claude/skills/` 与 `~/.codex/skills/`。双工具共用指令与记忆的机制说明见 `docs/workflows/记忆与多Agent.md`（配置已由 bootstrap 自动完成）。

## 语言与文风

默认使用简体中文；日期时间使用运行环境本地时区。正式产出先结论后依据，缺证据标为「待补证据」，不得把阶段状态写成已交付。
