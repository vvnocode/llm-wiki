#!/usr/bin/env bash
# 一键初始化个人实例（双形态）。用法：bootstrap.sh [--mode global|project]
#   global  全局工作台：~/.llm-wiki 发现软链 + 全局 Skill 软链（Claude / Codex）+ 仓内配置
#   project 专项工作台：仅仓内配置（多工具入口与仓内记忆、项目级 Skill 软链、
#           worktree 共享钩子、脚本权限、远端指引），不改动任何全局配置
# 缺省 --mode 时按发现链探测；全新实例交互询问，非交互环境必须显式传参。
# 多工具入口（CLAUDE.md 引用行）与仓内记忆（.memory/、Claude 记忆路径、Codex 记忆开关）不由本脚本自己写，
# 委托合并进规则仓的公开 skill agent-memory-setup 的 setup.sh（步骤 3）；未安装时先装到全局 Skill 发现根，装 skill 本身幂等。
# 不读取、不写入用户主目录里的凭据文件。
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

# 只在根工作区运行：附属 worktree 里的本机设置由 agent-memory-setup 按主工作区规则处理，不能在此改写。
if [ "$(cd "$(git rev-parse --git-dir)" && pwd -P)" != "$(cd "$(git rev-parse --git-common-dir)" && pwd -P)" ]; then
    echo "✗ 当前是附属 worktree（$ROOT），请在根工作区运行 bootstrap：$(git worktree list --porcelain | head -1 | sed 's/^worktree //')" >&2
    exit 1
fi

echo "═══ llm-wiki bootstrap ═══"
echo "实例：$ROOT"
echo

# ── 模式确定 ──
# 显式 --mode 优先；无参数按发现链探测：已指向本仓→global（幂等重跑），
# 指向别处→project；全新实例交互询问，非 TTY 必须显式传参（防误建全局链）。
MODE=""
LINK="$HOME/.llm-wiki"
while [ $# -gt 0 ]; do
    case "$1" in
        --mode)   MODE="${2:?--mode 需要值：global 或 project}"; shift 2 ;;
        --mode=*) MODE="${1#--mode=}"; shift ;;
        *) echo "✗ 未知参数：$1（用法：bootstrap.sh [--mode global|project]）" >&2; exit 1 ;;
    esac
done
case "$MODE" in
    global|project) ;;
    "")
        if [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$ROOT" ]; then
            MODE=global
        elif [ -e "$LINK" ] || [ -L "$LINK" ]; then
            MODE=project
            echo "· 本机全局位已被 $(readlink "$LINK" 2>/dev/null || echo "$LINK") 占用，按专项模式初始化"
        elif [ -t 0 ]; then
            echo "选择实例形态："
            echo "  global  —— 全局工作台：任意项目的会话都路由到本仓（建 ~/.llm-wiki 发现链与全局 Skill 挂载）"
            echo "  project —— 专项工作台：cd 进本目录使用，不改动任何全局配置"
            printf "输入 global 或 project："
            read -r MODE
            case "$MODE" in
                global|project) ;;
                *) echo "✗ 无效输入，请重跑并输入 global 或 project" >&2; exit 1 ;;
            esac
        else
            echo "✗ 全新实例在非交互环境须显式指定形态：bootstrap.sh --mode global|project" >&2
            exit 1
        fi
        ;;
    *) echo "✗ --mode 只接受 global 或 project" >&2; exit 1 ;;
esac
echo "模式：$MODE"
echo

ensure_link() {
    # ensure_link <链接路径> <目标>：已是软链或已存在则不动，只补缺
    local link=$1 target=$2
    if [ -L "$link" ]; then
        local cur
        cur=$(readlink "$link")
        if [ "$cur" = "$target" ]; then
            echo "· $link 已就位"
        else
            echo "⚠ $link 已是软链但指向 $cur（期望 $target），保持不动，请人工确认"
        fi
        return
    fi
    if [ -e "$link" ]; then
        echo "⚠ $link 已存在且不是软链，保持不动，请人工确认"
        return
    fi
    ln -s "$target" "$link"
    echo "· 已建立 $link → $target"
}

# 1) 发现约定（仅全局模式）：全局指令与全部 Skill 只认这个入口
if [ "$MODE" = global ]; then
    ensure_link "$LINK" "$ROOT"
fi

# 2) 目录骨架
mkdir -p .claude/skills .codex/skills .agents/skills repos
: > repos/.gitkeep 2>/dev/null || true

# 3) 多工具入口与仓内记忆：委托规则仓中的 agent-memory-setup（正本 GitHub vvnocode/AGENTS.md）。
#    它做四件事，全部幂等、只补缺：CLAUDE.md 只含一行 @AGENTS.md 引用（v0.3.0 起取代入库软链——软链在 Windows
#    默认 core.symlinks=false 下检出后是只写着 "AGENTS.md" 的文本文件，旧软链由它自动迁移）；.memory/MEMORY.md；
#    Claude 的 autoMemoryDirectory 指向仓内 .memory（写在不入库的 settings.local.json）；Codex 自带记忆三项全关。
#    机制对照、逐工具验证方法与陷阱见该 skill 的 SKILL.md，本仓不再复述。
#    不传 --with-rule：记忆读写规则由跨工具全局规则承担（本仓 AGENTS.md 已提及 .memory/，传了也会被跳过）。
#    查找顺序：AGENT_MEMORY_SETUP 显式路径 → ~/.agents/skills → ~/.claude/skills → ~/.codex/skills；
#    都没有就用 skills 仓的一行安装命令把 skill 装到三处发现根（已装的只会「已就位」）再找一次，
#    可用 AGENT_MEMORY_SETUP_INSTALLER 换成 fork 或离线安装命令。装不上（离线）只告警，其余步骤照做。
find_memory_setup() {
    local p
    for p in "${AGENT_MEMORY_SETUP:-}" \
             "$HOME/.agents/skills/agent-memory-setup/setup.sh" \
             "$HOME/.claude/skills/agent-memory-setup/setup.sh" \
             "$HOME/.codex/skills/agent-memory-setup/setup.sh"; do
        if [ -n "$p" ] && [ -f "$p" ]; then
            echo "$p"
            return 0
        fi
    done
    return 1
}
SETUP_RAW="https://raw.githubusercontent.com/vvnocode/AGENTS.md/main/skills/agent-memory-setup/setup.sh"
INSTALLER=${AGENT_MEMORY_SETUP_INSTALLER:-"curl -fsSL https://raw.githubusercontent.com/vvnocode/AGENTS.md/main/install.sh | bash"}
MEMORY_SETUP=""
if ! MEMORY_SETUP=$(find_memory_setup); then
    echo "· 未找到 agent-memory-setup，先安装到全局 Skill 发现根（需联网）：$INSTALLER"
    if bash -c "$INSTALLER"; then
        MEMORY_SETUP=$(find_memory_setup) || MEMORY_SETUP=""
    fi
fi
if [ -n "$MEMORY_SETUP" ]; then
    echo "· 多工具入口与仓内记忆 → $MEMORY_SETUP"
    bash "$MEMORY_SETUP" "$ROOT"
else
    echo "⚠ agent-memory-setup 未安装且无法自动安装（离线？）：CLAUDE.md 入口、Claude 记忆路径与 Codex 记忆开关本次未配置。"
    echo "  联网后重跑本脚本；或手工执行：curl -fsSL $SETUP_RAW | bash -s -- \"$ROOT\""
fi

# 5) 项目级 Skill 兼容软链（正本在 .agents/skills）
link_skill_local() {
    local name=$1
    local src=".agents/skills/$name"
    [ -e "$src" ] || return 0
    for dest_root in .claude/skills .codex/skills; do
        if [ -e "$dest_root/$name" ] || [ -L "$dest_root/$name" ]; then
            continue
        fi
        ln -s "../../$src" "$dest_root/$name"
        echo "· 已链 $dest_root/$name"
    done
}

for skill in llm-wiki-ingest llm-wiki-query llm-wiki-lint llm-wiki-learn; do
    link_skill_local "$skill"
done

# 6) 通用 worktree 共享钩子由 agent-memory-setup/setup.sh 安装；本仓只提供特有共享清单。
# 7) 全局 Skill 挂载（仅全局模式）：任意项目的会话都能路由到这四个 skill。
#    canonical 仍是本仓 .agents/skills。三个发现根缺一不可：~/.agents/skills 是跨工具的
#    约定俗成位（dsh、Cline、Dexto、Kimi、Loaf、Warp、Zed 等直接读它），而 Claude 与 Codex
#    各自只认自己的 skills 目录，不扫 ~/.agents/skills，故三处都要挂。
if [ "$MODE" = global ]; then
    for tool_root in "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.codex/skills"; do
        mkdir -p "$tool_root"
        for skill in llm-wiki-ingest llm-wiki-query llm-wiki-lint llm-wiki-learn; do
            ensure_link "$tool_root/$skill" "$HOME/.llm-wiki/.agents/skills/$skill"
        done
    done
fi

# 脚本执行位：只给首行是 #! 的文件加（含 scripts/hooks/）。无 shebang 的纯模块与被 source 的片段保持入库模式，
# 否则以 644 入库的文件每跑一次 bootstrap 就被翻成 755，根工作区平白多出模式变更。
EXEC_ADDED=0
for f in scripts/*.sh scripts/*.py scripts/hooks/*; do
    [ -f "$f" ] || continue
    [ "$(head -c 2 "$f" 2>/dev/null)" = '#!' ] || continue
    [ -x "$f" ] && continue
    chmod +x "$f" && EXEC_ADDED=$((EXEC_ADDED + 1))
done
echo "· 脚本执行位：新加 ${EXEC_ADDED} 个（只处理带 shebang 的文件）"

# 8) 远端指引（不代做）
echo
if ! git remote get-url upstream >/dev/null 2>&1; then
    echo "── 模板升级通道（可选）──"
    echo "git remote add upstream <模板仓URL>   # 之后升级：git fetch upstream && git merge upstream/main"
fi
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "── 自动上传（可选）──"
    echo "git remote add origin <个人wiki仓URL> # sync.sh 将自动 push；未配置则仅本地提交"
fi

echo
# 尾部指引按模式分叉：全局给路由段，专项确认零全局改动（heredoc 正文保持零缩进）
if [ "$MODE" = global ]; then
echo "── 全局指令接入（二选一）──"
echo "A. 跨工具规则仓已含「全局知识工作台」路由段：无需操作。"
echo "B. 手工粘贴：把下面这段加进 ~/.claude/CLAUDE.md、~/.codex/AGENTS.md 等全局文件："
cat <<'ROUTE'
────────────────────────────────────────
## 全局知识工作台（llm-wiki）

本节仅当本机存在 `~/.llm-wiki` 时生效；不存在则整节忽略。

- cwd 位于某个 llm-wiki 实例内时（专项或全局），工作台即该实例、以其仓内指令为准，本节的 `~/.llm-wiki` 路由不适用；实例判定同各 skill 的「工作台根（$WIKI）」规则。
- 排障、分析、设计、学习或跨项目提问，先读 `~/.llm-wiki/wiki/index.md` 再下钻命中页；纯局部代码修改不触发本节。
- 接口、部署、当前状态等易变事实，必须回查所在项目源码与登记数据源，不得只信 wiki。
- 任务形成跨会话复用价值时，按 `~/.llm-wiki/docs/schemas/分区与共享.md` 的分层判据默认写回；用户当轮说「不用」才跳过。收口后运行工作台 sync 完成上传。
- 判据、skill 与 schema 一律以 `~/.llm-wiki` 仓内文件为准；本节只负责路由。
────────────────────────────────────────
ROUTE
else
echo "── 专项实例就绪 ──"
echo "cd 进本目录即可使用：AGENTS.md 生效，Skill 走项目级链接路由；未改动任何全局配置。"
echo "如需转为全局工作台：./scripts/bootstrap.sh --mode global"
fi
echo
echo "自检：python3 -m unittest discover -s tests -v && python3 scripts/lint-wiki.py"
