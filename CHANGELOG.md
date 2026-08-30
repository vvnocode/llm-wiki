# CHANGELOG

模板版本记录。破坏性变更（目录改名、skill 接口变化、schema 不兼容调整）必须在此标注迁移方法。

## v0.2.0 (2026-08-30)

双形态支持：实例化时可选**专项工作台**（clone 后直接进入目录使用）或**全局工作台**（现行 `~/.llm-wiki` 发现约定）。设计见 `docs/specs/2026-08-30-双形态支持-design.md`。

- Skill 契约变更：四份 SKILL.md 改为统一「工作台根（$WIKI）」解析——cwd 所在实例优先，否则 `~/.llm-wiki`；全局+专项并存时在专项实例内不再误写全局库。契约测试 `test_global_skill_paths_absolute` 替换为 `test_skill_root_resolution`。
- bootstrap 变更：新增 `--mode global|project`（ps1 为 `-Mode`）。无参数时按发现链探测：已指向本仓→global（既有实例重跑不受影响）；全新实例交互询问，**非交互环境必须显式传参**（原静默建全局链的行为取消）。project 模式不改动任何全局配置。
- 迁移：既有全局实例 merge 后重跑 bootstrap 即可，无目录或数据变更；自动化脚本中对全新实例的 bootstrap 调用需补 `--mode` 参数。
- Windows：bootstrap.ps1 已同构改造，真机验收待补（v0.1.0 既有功能不受影响）。
- 路由段：bootstrap 打印的「全局知识工作台」段增补实例内就近优先条款（cwd 在某实例内时以该实例为工作台、本段路由不适用），与 skill 的 $WIKI 规则及规则仓同文对齐。
- 杂项：`.gitignore` 增 `.worktrees/`；README / SETUP-FOR-AI / AGENTS.md / 分区与共享 改双形态叙事。

## v0.1.0 (2026-08-28)

首个发布版本。

- 全局工作台内核：`~/.llm-wiki` 发现约定（macOS/Linux 软链，Windows junction）；模板与实例分离，升级走 `git merge` 且只动骨架。
- Wiki 结构：多项目分区（`wiki/projects/<项目>/` 两级索引）、公共层（concepts/entities/operations/decisions/risks）、learning 学习模块、private 私有区（gitignore，物理不出本机）。
- 四个 Skill（ingest / query / lint / learn），路径全绝对化，附契约测试（单一真源、禁裸相对路径）。
- 三级写入门 schema（`docs/schemas/分区与共享.md`）与域扩展机制（`config/registry.md` 登记）。
- 脚本：`bootstrap.sh` / `bootstrap.ps1`（双平台实测）、`sync.sh`（自动上传，rebase 冲突停下不 force）、`lint-wiki.py`、`release.sh` 与 `release-check.sh`（发布安全扫描）、维护者 hook 样本 `scripts/hooks/pre-push`（发布远端只接受 template 内容）。
- `SETUP-FOR-AI.md`：可把仓库直接交给 AI 助手完成自动部署。
