# CHANGELOG

模板版本记录。破坏性变更（目录改名、skill 接口变化、schema 不兼容调整）必须在此标注迁移方法。

## v0.2.8 (2026-09-03)

- 补入 `repos/.gitkeep`。`.gitignore` 早已写有 `repos/*` 与 `!repos/.gitkeep`，意图是让空目录 `repos/` 随模板入库，但模板从未提交这个占位文件，新实例化出的仓库没有 `repos/` 目录；全局实例 2026-08-28 自行补过一次，模板与实例因此多出一处骨架差异。
- 迁移：无动作。实例若已自行补过同名空文件，升级 merge 内容一致不冲突；未补过的升级后自动得到该目录。

## v0.2.7 (2026-09-03)

- `AGENTS.md`「提交与分支约定」新增「合并确认门与一任务一合」：合入前是否等用户确认只看改动落点——内容目录的 worktree 验证后由 agent 自行 `--no-ff` 合一次，无需确认；白名单之外的骨架改动做完停下报告、等用户确认后再合。总则「短期任务分支……经用户确认再合回」相应改为按落点判定。补「一个任务只合一次」：返工提交在同一分支、跨会话沿用原 worktree。实例段收紧白名单时只能改「是否建 worktree」，不得把内容产出改成需确认（v0.2.3 允许收紧后，SM 实例把业务产出收紧成 worktree 且被当成免确认授权，一份月报在 `main` 留下五个 merge 节点）。
- 迁移：实例段若有与之冲突的分流规则（把内容产出写成需确认、或按任务类型枚举），升级后删除或改为只引用模板段。

## v0.2.6 (2026-09-02)

- `bootstrap.sh` 执行位规则收窄：只给首行为 `#!` 的文件加执行位（`scripts/*.sh`、`scripts/*.py`、`scripts/hooks/*`），无 shebang 的纯模块与被 source 的片段保持入库模式。此前对 `scripts/*.sh scripts/*.py` 一律 `chmod +x`，实例里以 644 入库的文件每跑一次 bootstrap 就被翻成 755，根工作区平白多出模式变更。回归测试 `tests/test_bootstrap_chmod.py`。
- 迁移：带 shebang 却以 644 入库的实例脚本请把执行位提交一次（`chmod +x` 后 `git add`），否则规则照样会翻动；无 shebang 的文件此后不再被改动。

## v0.2.5 (2026-09-02)

- 新增 worktree 共享机制。`git worktree add` 只检出入库文件，`repos/` 克隆、`state/collectors/` 采集游标、`wiki/private/` 私有区、`.claude/settings.local.json`（Claude 记忆目录指向）等被 gitignore 的本机资产在新 worktree 里缺失，worktree 会话因此丢记忆、丢数据（v0.2.4 只解决了 `CLAUDE.md` 与技能链接）。现由 `config/worktree-share.conf` 列出共享前缀，`scripts/worktree.sh link` 把根工作区对应的被忽略条目软链进 worktree（不复制、不入库、写入落回根工作区），`scripts/hooks/post-checkout` 让裸 `git worktree add`（含 Claude Code 的 `.claude/worktrees/`）自动挂载；`worktree.sh add` / `remove` 为显式建立与回收入口，`remove` 先把 worktree 内新产生的被忽略文件回收到根工作区（不覆盖）再删除。`bootstrap.sh` 新增步骤 6 安装钩子（软链到 `.git/hooks/post-checkout`；`bootstrap.ps1` 以副本安装，待 Windows 真机验收）。回归测试 `tests/test_worktree_share.py`。
- `.gitignore`：`state/collectors/` 改为 `state/collectors`。**尾斜杠目录规则只匹配真实目录、不匹配 worktree 里的软链**，软链会变成未跟踪文件并被 `sync.sh` 暂存；`worktree.sh` 对每条新建软链做 check-ignore 复核，未被忽略即撤销并告警。
- 迁移：① 升级后重跑 `./scripts/bootstrap.sh`（Windows `bootstrap.ps1`）安装钩子；`core.hooksPath` 已被占用的仓库 bootstrap 只提示，需自行接入。② 实例段里要共享进 worktree 的被忽略目录（如采集正文、运行目录），其 `.gitignore` 规则去掉尾斜杠，并把前缀追加到 `config/worktree-share.conf` 文末。③ 已存在的 worktree 手动执行一次 `scripts/worktree.sh link <worktree路径>`。
- 文档修正：`AGENTS.md`「多工具入口」、README 目录树与 FAQ 仍写着 `CLAUDE.md` 与技能链接「不入库、由 bootstrap 生成」，与 v0.2.4 不符，一并改正。

## v0.2.4 (2026-09-01)

- 兼容入口 `CLAUDE.md` 与项目级技能链接 `.claude/skills/`、`.codex/skills/` 改为入库（相对软链，git mode 120000），`.gitignore` 移除对应三条。此前它们只由 `bootstrap` 在仓库根生成且不入库，`git worktree add` 不会带出，worktree 内的会话因此读不到本仓 `AGENTS.md`（Claude 侧经 `CLAUDE.md` 发现），项目级技能也不注册。`bootstrap.sh` 的 `ensure_link` 遇已就位软链直接跳过，`bootstrap.ps1` 把占位文本判为过期副本后刷新，两者均无需改动。
- 迁移：无动作。升级前实例侧这三者处于 `.gitignore` 忽略状态（非 untracked），merge 直接覆盖为入库软链，不触发 untracked 保护。已实测本地软链指向与入库一致、及故意指向他处两种情况，均 merge 成功且结果正确、工作区干净。
- 已知副作用（Windows 未启用 `core.symlinks`）：检出得到内容为目标路径的占位文本，原有副本会被 merge 覆盖；重跑 `bootstrap.ps1` 即把占位文本判为过期副本并刷新，功能恢复。但此后 `CLAUDE.md` 在 git 中表现为已修改，需 `git update-index --skip-worktree CLAUDE.md` 或启用开发者模式，避免副本被误提交回 `template`。此项未在 Windows 实机核验。

## v0.2.3 (2026-08-31)

- `AGENTS.md`「提交与分支约定」补齐 v0.2.2 审计缺口：短期分支合入前须经用户确认；总则「合入 main」改为「合回其目标分支」，消除与合一仓骨架合回 `template` 的表述冲突；发布指定走 `scripts/release.sh`（禁止手工 push 发布远端）；实例段可收紧内容白名单，收紧者优先；合并在任务 worktree 内执行、根工作区始终留在 `main`。
- `tests/test_skill_contracts.py` 新增白名单一致性契约：`AGENTS.md` 内容目录清单与 `scripts/sync.sh` `add_content` 清单必须同源一致。

## v0.2.2 (2026-08-31)

- `AGENTS.md`「提交与分支约定」增补两条：内容目录白名单（`wiki/` `inputs/` `outputs/` `state/` `.memory/`）直接在 `main` 提交，白名单外任何文件改动一律先建 worktree（按改动落点判定，不枚举任务类型）；一个 worktree 一个合入目标，维护者合一仓骨架改动以 `template` 为基线、经版本发布 merge 进 `main`。
- `scripts/sync.sh`：`git add -A` 收紧为只暂存内容白名单目录。行为变化：白名单外的在途改动（含并行会话的骨架工作）不再被 ingest 顺手提交，需走 worktree；升级后无迁移动作。

## v0.2.1 (2026-08-31)

- `AGENTS.md` 增补「提交与分支约定」节：main 唯一长期分支 + `.worktrees/` 短期分支；升级用 merge、禁止 rebase（冲突大先 worktree 演练）；统一提交前缀表（`ingest:` / `merge:` / `upgrade:` / `instance:` 等），实例不产生 `template:` 前缀。非破坏性变更，merge 即得，无迁移动作。

## v0.2.0 (2026-08-30)

双形态支持：实例化时可选**专项工作台**（clone 后直接进入目录使用）或**全局工作台**（现行 `~/.llm-wiki` 发现约定）。设计见 `docs/specs/2026-08-30-双形态支持-design.md`。

- Skill 契约变更：四份 SKILL.md 改为统一「工作台根（$WIKI）」解析——cwd 所在实例优先，否则 `~/.llm-wiki`；全局+专项并存时在专项实例内不再误写全局库。契约测试 `test_global_skill_paths_absolute` 替换为 `test_skill_root_resolution`。
- bootstrap 变更：新增 `--mode global|project`（ps1 为 `-Mode`）。无参数时按发现链探测：已指向本仓→global（既有实例重跑不受影响）；全新实例交互询问，**非交互环境必须显式传参**（原静默建全局链的行为取消）。project 模式不改动任何全局配置。
- 迁移：既有全局实例 merge 后重跑 bootstrap 即可，无目录或数据变更；自动化脚本中对全新实例的 bootstrap 调用需补 `--mode` 参数。
- Windows：bootstrap.ps1 已同构改造，真机验收待补（v0.1.0 既有功能不受影响）。
- 路由段：bootstrap 打印的「全局知识工作台」段增补实例内就近优先条款（cwd 在某实例内时以该实例为工作台、本段路由不适用），与 skill 的 $WIKI 规则及规则仓同文对齐。
- 杂项：`.gitignore` 增 `.worktrees/`；README / SETUP-FOR-AI / AGENTS.md / 分区与共享 改双形态叙事，并补全局形态外部前置说明（路由段接入，可由配套规则仓 [claude.md](https://github.com/vvnocode/claude.md) 承载；专项形态零外部前置，先后顺序无关）。

## v0.1.0 (2026-08-28)

首个发布版本。

- 全局工作台内核：`~/.llm-wiki` 发现约定（macOS/Linux 软链，Windows junction）；模板与实例分离，升级走 `git merge` 且只动骨架。
- Wiki 结构：多项目分区（`wiki/projects/<项目>/` 两级索引）、公共层（concepts/entities/operations/decisions/risks）、learning 学习模块、private 私有区（gitignore，物理不出本机）。
- 四个 Skill（ingest / query / lint / learn），路径全绝对化，附契约测试（单一真源、禁裸相对路径）。
- 三级写入门 schema（`docs/schemas/分区与共享.md`）与域扩展机制（`config/registry.md` 登记）。
- 脚本：`bootstrap.sh` / `bootstrap.ps1`（双平台实测）、`sync.sh`（自动上传，rebase 冲突停下不 force）、`lint-wiki.py`、`release.sh` 与 `release-check.sh`（发布安全扫描）、维护者 hook 样本 `scripts/hooks/pre-push`（发布远端只接受 template 内容）。
- `SETUP-FOR-AI.md`：可把仓库直接交给 AI 助手完成自动部署。
