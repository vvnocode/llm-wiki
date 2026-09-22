# 记忆与多 Agent

目标：Claude Code、Codex、dsh、opencode 等在本仓共用**一份指令（`AGENTS.md`）、一份仓内记忆（`.memory/`）**，换工具不丢上下文。

## 分工：接线交给 agent-memory-setup

多工具接线是任何仓库都会遇到的通用问题，不是工作台特有的，本仓不自己维护一份。bootstrap 调用规则仓中的公开 skill [agent-memory-setup](https://github.com/vvnocode/AGENTS.md/tree/main/skills/agent-memory-setup)（`setup.sh` / `setup.ps1`）完成四件事：

1. `AGENTS.md` 唯一正本，`CLAUDE.md` 只含一行 `@AGENTS.md` 引用并入库。Claude Code 只读 `CLAUDE.md`；引用行取代软链，因为入库软链在 Windows 默认 `core.symlinks=false` 下检出后是只写着 `AGENTS.md` 的文本文件，且不报错。
2. `.memory/MEMORY.md`。
3. Claude 的 `autoMemoryDirectory` 指向仓内 `.memory/`（绝对路径，写在不入库的 `.claude/settings.local.json`）。
4. Codex 自带记忆照常开启（其记忆目录不可改），属于本仓的部分由该 skill 的 `memory-sync` 按 cwd 转写为 `.memory/codex-*.md`（与 Claude 自动记忆同形，`metadata.source: codex`），由规则仓 `install.sh` 写入的全局 `SessionStart` 钩子在会话开始触发；Codex 自己新写的跨会话记忆则由指令约束进 `.memory/`。v0.3.3 前是三项全关，旧关闭块由 setup 脚本按结构识别迁移。

bootstrap 按 `AGENT_MEMORY_SETUP` → `~/.agents/skills` → `~/.claude/skills` → `~/.codex/skills` 找它；没装就先用规则仓的一行安装命令装到三处发现根（已装的只会「已就位」）再调用；装不上只告警，联网后重跑即可。

记忆读写规则本仓不写仓内段（bootstrap 不传 `--with-rule`）：由跨工具全局规则（如 规则仓 vvnocode/AGENTS.md「项目记忆」节）承担。给没有全局规则的协作者用时，在实例里手工跑一次 `setup.sh --with-rule`。

## 本仓特有的部分

**worktree 里的记忆。** `settings.local.json` 被 gitignore，`git worktree add` 检出不到，worktree 会话的记忆目录会退回工具默认位置，仓内记忆整份不可见。规则仓 skill 安装的 post-checkout 钩子按通用清单和本仓根目录 `.worktree-share` 把根工作区本机资产共享进新 worktree；目录用软链，文件用副本，`.claude/settings.local.json` 由 Claude 原生回读而不共享。已存在的 worktree 手动执行该 skill 的 `worktree-share.sh link <路径>`。bootstrap 因此只能在根工作区运行：在附属 worktree 里改写会把根工作区的记忆路径指到 worktree。

**删 worktree 前先回收。** link 只按根工作区当时已有的条目共享一次，之后在 worktree 里新建的被忽略条目和对副本的改动只留在 worktree，而 `git worktree remove` 不检查被忽略文件、不加 `--force` 也会一并删除。机制、列出命令与回收命令见 skill `agent-memory-setup` 的 SKILL.md「worktree 里效果不变」中「删 worktree 前先回收」一条（本机 `~/.agents/skills/agent-memory-setup/SKILL.md`），本仓不再复制一份。本仓要特别当心的条目：新 clone 进 `repos/` 的仓库、实例追加的采集目录下的新周期数据、新私有页。采集类任务优先在根工作区跑：在 worktree 里跑时，整目录软链的采集游标（`state/collectors`）写回根工作区，新周期正文却随 worktree 删除。

**记忆记什么、和 wiki 怎么分。** 见 `docs/schemas/分区与共享.md`「与 `.memory/` 的分工」：记忆记做事方式（偏好、纠正、约束、指针），wiki 记事实结论（对象、机制、决策、案例）。

## 验证

在本目录开各工具会话，问「不用工具，复述项目指令里关于 wiki 写入门的那条」，答得出即指令到达。记忆路径与 Codex 项目配置的验证按 skill `SKILL.md`「验证」节，不要用 `codex doctor`（只报全局值）。
