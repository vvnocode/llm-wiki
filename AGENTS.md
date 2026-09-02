# AGENTS.md

## 项目定位

这是一个**个人 LLM Wiki 工作台**，双形态：既可经固定软链 `~/.llm-wiki` 被全局指令发现、作为**全局工作台**（任何 vibe coding agent、在任何项目里形成的可复用知识都汇入这一份），也可作为**专项工作台**直接进入本目录、服务单一业务域。两种形态共用同一套结构与纪律。跨项目路由（仅全局形态）由全局指令（如 claude.md 规则仓的「全局知识工作台」节）承担；本文件约束「进入本目录工作」的会话，对两种形态同时成立。

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

任务形成跨会话价值时默认 ingest（用户当轮说「不用」才跳过）；ingest 完成后运行 `scripts/sync.sh "<主题>"` 完成提交与上传。rebase 冲突时脚本会停下交人工，禁止 force。

## 数据与凭证

- 凭证只使用用户本机已有登录缓存或钥匙串。禁止读取或提交密码、token、私钥、kubeconfig、完整连接串和主目录凭据文件——任何分区（含 private）都不例外。
- 写远程状态、发消息、改配置或重启服务前确认对象、字段和操作者，执行后回查。

## Skill 路由

- 导入、整理、更新知识：`.agents/skills/llm-wiki-ingest/SKILL.md`
- 分析、设计、排障、跨项目提问：`.agents/skills/llm-wiki-query/SKILL.md`
- 检查 Wiki：`.agents/skills/llm-wiki-lint/SKILL.md`
- 系统学习、教材化整理、验收：`.agents/skills/llm-wiki-learn/SKILL.md`

## 域扩展与路径登记

内核不含任何业务采集器。接入采集类数据源（聊天工具、项目管理系统、邮箱等）按 `docs/workflows/新业务域落地.md` 建立独立域扩展，并在 `config/registry.md` 登记路径与敏感级别。个人项目仓库同样只在 `config/registry.md` 登记。

## 模板与实例

本仓从模板（上游 `template` 历史）实例化而来：骨架文件（`docs/schemas/`、`.agents/skills/`、`scripts/`、`tests/`、根说明文件）由模板演进，升级用 `git merge`（upstream 或本仓 `template` 分支）；`wiki/`、`inputs/` 内容目录归个人，模板永不触碰。

## 提交与分支约定

分支只有两类：**`main` 唯一长期分支**（知识、数据与实例配置的最终落点；没有远端也必须本地提交）；**短期任务分支**一律放 `.worktrees/{任务名}/`，验证后**经用户确认**再 `--no-ff` 合回其目标分支并删除（目标分支见下「一个 worktree 一个合入目标」，实例仓即 `main`）。模板升级直接在 `main` 上 merge（**禁止 rebase**——rebase 会重写 main 历史，破坏既有产出对提交的追溯，也会与远端历史分裂；merge 节点本身就是升级留痕）；预计冲突较大时先在 `.worktrees/upgrade-{版本}/` 演练，绿后再正式 merge。建 worktree 用 `scripts/worktree.sh add <任务名> [基线]`（裸 `git worktree add` 亦可，bootstrap 安装的 post-checkout 钩子同样生效）：`repos/` 克隆、采集游标、私有区、`.claude/settings.local.json`（记忆目录指向）等被 gitignore 的本机资产按 `config/worktree-share.conf` 软链进 worktree，不复制、不入库；收尾用 `scripts/worktree.sh remove <任务名>` 先把 worktree 内新产生的被忽略文件回收到根工作区再删除。共享目录的 `.gitignore` 规则不带尾斜杠（尾斜杠不匹配软链）。

**何时必须建短期分支**：内容目录——`wiki/`、`inputs/`、`outputs/`、`state/`、`.memory/`——的写入直接在 `main` 提交，`sync.sh` 即此路径；**白名单之外的任何文件改动，不论大小，一律先建 worktree**（模板升级 merge 按上一段执行，不属此列）。按改动落点而非任务类型判定：枚举「哪些任务要建」是开放清单，会随功能新增而漏；新增功能必然改动白名单外的文件，天然落入 worktree。一次改动同时涉及内容与骨架的，整体走 worktree。实例可在实例段**收紧**白名单（如要求某类产出也走 worktree），两段不一致时按收紧者执行。

**一个 worktree 一个合入目标**：worktree 从这次改动要合回的分支拉出，验证后 `--no-ff` 合回同一分支，不并行合入多条长期分支。维护者合一仓的骨架改动以 `template` 为基线且只合回 `template`，进入 `main` 走版本发布后的升级 merge（合一仓的 `main` 等同第一个实例，与其他实例同一同步方式）；仅实例侧配置才以 `main` 为基线。发布一律用 `scripts/release.sh`（先跑 release-check 敏感扫描再推全部发布远端，配套 pre-push hook 见 README「模板维护者」节），不得手工 `git push` 发布远端。合并操作在任务 worktree 内执行：在 worktree 里 checkout 目标分支后 merge 任务分支；**根工作区始终留在 `main`**，不得为合并切换根工作区——会打断其他会话的内容写入。

提交前缀：

| 前缀 | 用途 |
|---|---|
| `ingest:` | wiki 知识写入（sync.sh 默认使用） |
| `merge:` | 短期任务分支合入 main |
| `upgrade:` | 模板升级合并的 merge commit |
| `instance:` | 骨架适配与实例配置（AGENTS 实例段、.gitignore、registry 等） |
| `docs:` / `ops:` / `fix:` / `chore:` | 常规含义 |

业务域可自行补充前缀（如采集、报告类），在实例段登记。实例**不产生** `template:` 前缀提交：通用骨架改进一律到模板仓的 `template` 分支开发（维护者合一仓即本仓 `template` 分支，前缀 `template:`），发布后经 `upgrade:` 合并回流各实例。

## 多工具入口

`AGENTS.md` 是唯一指令正本；`CLAUDE.md` 兼容入口与 `.claude/skills/`、`.codex/skills/` 兼容链接以相对软链入库（v0.2.4 起，保证 worktree 内可见），bootstrap 只在缺失或 Windows 无 symlink 权限时按平台补建（junction/副本）。项目级 Skill 的 canonical 位于 `.agents/skills/`；全局挂载由 bootstrap 链到 `~/.claude/skills/` 与 `~/.codex/skills/`。双工具共用指令与记忆的机制说明见 `docs/workflows/记忆与多Agent.md`（配置已由 bootstrap 自动完成）。

## 语言与文风

默认使用简体中文；日期时间使用运行环境本地时区。正式产出先结论后依据，缺证据标为「待补证据」，不得把阶段状态写成已交付。
