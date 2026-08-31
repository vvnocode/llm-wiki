# CHANGELOG

模板版本记录。破坏性变更（目录改名、skill 接口变化、schema 不兼容调整）必须在此标注迁移方法。

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
