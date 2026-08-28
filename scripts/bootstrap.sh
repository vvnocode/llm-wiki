#!/usr/bin/env bash
# 一键初始化个人实例：
#   ~/.llm-wiki 发现软链、全局 Skill 软链（Claude / Codex）、
#   CLAUDE.md 兼容软链、本机记忆路径、项目级 Skill 软链、脚本权限、远端指引。
# 不读取、不写入用户主目录里的凭据文件。
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "═══ llm-wiki bootstrap ═══"
echo "实例：$ROOT"
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

# 1) 发现约定：全局指令与全部 Skill 只认这个入口
ensure_link "$HOME/.llm-wiki" "$ROOT"

# 2) 兼容入口与目录
ensure_link CLAUDE.md AGENTS.md
mkdir -p .claude/skills .codex/skills .agents/skills repos
: > repos/.gitkeep 2>/dev/null || true

# 3) Claude 本机记忆路径（含绝对路径，文件被 gitignore）
SETTINGS=".claude/settings.local.json"
python3 - "$ROOT" "$SETTINGS" <<'PY'
import json, os, sys
root, path = sys.argv[1], sys.argv[2]
want = f"{root}/.memory"
cur = {}
if os.path.exists(path):
    try:
        cur = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError:
        cur = {}
if cur.get("autoMemoryDirectory") == want:
    print(f"· {path} 路径已是本机")
else:
    cur["autoMemoryDirectory"] = want
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"· 已写 {path} （autoMemoryDirectory → {want}）")
PY

# 4) Codex 项目级记忆配置
if [ ! -f .codex/config.toml ]; then
    cat > .codex/config.toml <<'TOML'
# 记忆统一存放在仓库内 .memory/，写入规则见 AGENTS.md。
# 生效前提：本目录须在 ~/.codex/config.toml 里被标记为 trusted。
[memories]
generate_memories = false
use_memories = false
dedicated_tools = false
TOML
    echo "· 已写 .codex/config.toml"
else
    echo "· .codex/config.toml 已存在"
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

# 6) 全局 Skill 挂载：任意项目的会话都能路由到这四个 skill。
#    canonical 仍是本仓 .agents/skills。
for tool_root in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
    mkdir -p "$tool_root"
    for skill in llm-wiki-ingest llm-wiki-query llm-wiki-lint llm-wiki-learn; do
        ensure_link "$tool_root/$skill" "$HOME/.llm-wiki/.agents/skills/$skill"
    done
done

chmod +x scripts/*.sh scripts/*.py 2>/dev/null || true
echo "· 脚本已加执行权限"

# 7) 远端指引（不代做）
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
echo "── 全局指令接入（二选一）──"
echo "A. 跨工具规则仓已含「全局知识工作台」路由段：无需操作。"
echo "B. 手工粘贴：把下面这段加进 ~/.claude/CLAUDE.md、~/.codex/AGENTS.md 等全局文件："
cat <<'ROUTE'
────────────────────────────────────────
## 全局知识工作台（llm-wiki）

本节仅当本机存在 `~/.llm-wiki` 时生效；不存在则整节忽略。

- 排障、分析、设计、学习或跨项目提问，先读 `~/.llm-wiki/wiki/index.md` 再下钻命中页；纯局部代码修改不触发本节。
- 接口、部署、当前状态等易变事实，必须回查所在项目源码与登记数据源，不得只信 wiki。
- 任务形成跨会话复用价值时，按 `~/.llm-wiki/docs/schemas/分区与共享.md` 的分层判据默认写回；用户当轮说「不用」才跳过。收口后运行工作台 sync 完成上传。
- 判据、skill 与 schema 一律以 `~/.llm-wiki` 仓内文件为准；本节只负责路由。
────────────────────────────────────────
ROUTE
echo
echo "── Codex 信任（用 Codex 才需要）──"
echo "把下面这段追加到 ~/.codex/config.toml："
echo
echo "[projects.\"$ROOT\"]"
echo "trust_level = \"trusted\""
echo
echo "自检：python3 -m unittest discover -s tests -v && python3 scripts/lint-wiki.py"
