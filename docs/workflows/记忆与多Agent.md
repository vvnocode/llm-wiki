# 记忆与多 Agent

目标：Claude Code、Codex、dsh、opencode 等在本仓共用**一份指令（`AGENTS.md`）、一份仓内记忆（`.memory/`）**，换工具不丢上下文。

## 分工：接线交给 agent-memory-setup

多工具接线是任何仓库都会遇到的通用问题，不是工作台特有的，本仓不自己维护一份。v0.3.0 起 `bootstrap.sh` / `bootstrap.ps1` 的步骤 3 调用公开 skill [agent-memory-setup](https://github.com/vvnocode/skills)（`setup.sh` / `setup.ps1`）完成四件事：

1. `AGENTS.md` 唯一正本，`CLAUDE.md` 只含一行 `@AGENTS.md` 引用并入库。Claude Code 只读 `CLAUDE.md`；引用行取代软链，因为入库软链在 Windows 默认 `core.symlinks=false` 下检出后是只写着 `AGENTS.md` 的文本文件，且不报错。
2. `.memory/MEMORY.md`。
3. Claude 的 `autoMemoryDirectory` 指向仓内 `.memory/`（绝对路径，写在不入库的 `.claude/settings.local.json`）。
4. Codex 自带记忆三项全关（其记忆目录不可改），改由指令约束它写 `.memory/`。

bootstrap 按 `AGENT_MEMORY_SETUP` → `~/.agents/skills` → `~/.claude/skills` → `~/.codex/skills` 找它；没装就先用 skills 仓的一行安装命令装到三处发现根（已装的只会「已就位」）再调用；装不上只告警，联网后重跑即可。四工具的机制对照、逐工具验证方法、Codex 信任门与后台记忆管线等陷阱，一律见该 skill 的 `SKILL.md`，本文不复述。

记忆读写规则本仓不写仓内段（bootstrap 不传 `--with-rule`）：由跨工具全局规则（如 claude.md 规则仓「项目记忆」节）承担。给没有全局规则的协作者用时，在实例里手工跑一次 `setup.sh --with-rule`。

## 本仓特有的部分

**worktree 里的记忆。** `settings.local.json` 被 gitignore，`git worktree add` 检出不到，worktree 会话的记忆目录会退回工具默认位置，仓内记忆整份不可见。bootstrap 安装的 post-checkout 钩子按 `config/worktree-share.conf` 把根工作区那份软链进新 worktree，所有 worktree 读写同一份记忆；老 worktree 手动 `scripts/worktree.sh link <路径>`。bootstrap 因此只能在根工作区运行：在附属 worktree 里改写会把根工作区的记忆路径指到 worktree。

**记忆记什么、和 wiki 怎么分。** 见 `docs/schemas/分区与共享.md`「与 `.memory/` 的分工」：记忆记做事方式（偏好、纠正、约束、指针），wiki 记事实结论（对象、机制、决策、案例）。

## 验证

在本目录开各工具会话，问「不用工具，复述项目指令里关于 wiki 写入门的那条」，答得出即指令到达。记忆路径与 Codex 项目配置的验证按 skill `SKILL.md`「验证」节，不要用 `codex doctor`（只报全局值）。
