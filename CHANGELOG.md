# CHANGELOG

模板版本记录。破坏性变更（目录改名、skill 接口变化、schema 不兼容调整）必须在此标注迁移方法。

## v0.1.0 (2026-08-28)

首个发布版本。

- 全局工作台内核：`~/.llm-wiki` 发现约定（macOS/Linux 软链，Windows junction）；模板与实例分离，升级走 `git merge` 且只动骨架。
- Wiki 结构：多项目分区（`wiki/projects/<项目>/` 两级索引）、公共层（concepts/entities/operations/decisions/risks）、learning 学习模块、private 私有区（gitignore，物理不出本机）。
- 四个 Skill（ingest / query / lint / learn），路径全绝对化，附契约测试（单一真源、禁裸相对路径）。
- 三级写入门 schema（`docs/schemas/分区与共享.md`）与域扩展机制（`config/registry.md` 登记）。
- 脚本：`bootstrap.sh` / `bootstrap.ps1`（双平台实测）、`sync.sh`（自动上传，rebase 冲突停下不 force）、`lint-wiki.py`、`release.sh` 与 `release-check.sh`（发布安全扫描）、维护者 hook 样本 `scripts/hooks/pre-push`（发布远端只接受 template 内容）。
- `SETUP-FOR-AI.md`：可把仓库直接交给 AI 助手完成自动部署。
