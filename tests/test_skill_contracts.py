#!/usr/bin/env python3
"""项目级 Skill 单一真源、入口链接与双形态根解析契约的结构测试。"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 全部 skill：canonical 在 .agents/skills，.claude/.codex 放兼容软链
SKILLS = (
    "llm-wiki-ingest",
    "llm-wiki-query",
    "llm-wiki-lint",
    "llm-wiki-learn",
)

# 裸相对仓内路径：wiki/... docs/... 等前面既不是 $WIKI/ 也不是路径成分
BARE_PATH_RE = re.compile(
    r"(?<![\w/~.\-])(?:wiki|inputs|docs|config|scripts|outputs|state)/"
)

# 双形态根解析锚句：四份 SKILL.md 必须逐字包含（写成单一物理行）。
# 该行豁免裸路径与硬编码检查——句中的 wiki/index.md 是实例判定标记，不是仓内路径引用。
ROOT_ANCHOR = "**工作台根（$WIKI）**："


class SkillContractTest(unittest.TestCase):
    """确保多工具入口都指向 `.agents/skills` 的同一份实现。"""

    def test_skill_frontmatter_and_links(self) -> None:
        for name in SKILLS:
            with self.subTest(skill=name):
                canonical = ROOT / ".agents/skills" / name
                skill_file = canonical / "SKILL.md"
                self.assertTrue(skill_file.is_file(), skill_file)
                text = skill_file.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"), skill_file)
                header = text.split("\n---\n", 1)[0]
                self.assertRegex(header, rf"(?m)^name:\s*{re.escape(name)}\s*$")
                self.assertRegex(header, r"(?m)^description:\s*.+$")

                # 兼容链接由 bootstrap 按平台生成（不入库）：存在则必须指向 canonical；
                # 新 clone 未 bootstrap 时不存在，不视为失败
                for compatibility_root in (".claude/skills", ".codex/skills"):
                    link = ROOT / compatibility_root / name
                    if link.exists() or link.is_symlink():
                        self.assertEqual(link.resolve(), canonical.resolve(), link)

    def test_skill_root_resolution(self) -> None:
        """SKILL.md 须带根解析段、仓内路径经 $WIKI 前缀，锚句外禁止硬编码 ~/.llm-wiki。"""
        for name in SKILLS:
            with self.subTest(skill=name):
                skill_file = ROOT / ".agents/skills" / name / "SKILL.md"
                self.assertTrue(skill_file.is_file(), skill_file)
                text = skill_file.read_text(encoding="utf-8")
                self.assertIn(ROOT_ANCHOR, text, f"{skill_file} 缺根解析段")
                self.assertIn("$WIKI/", text, f"{skill_file} 未经 $WIKI 引用仓内路径")
                # 锚句行豁免后逐行检查：既禁裸相对路径，也禁回归硬编码全局链
                body = "\n".join(
                    line for line in text.splitlines() if ROOT_ANCHOR not in line
                )
                bare = [
                    f"{m.group(0)!r} @ body 第 {body[:m.start()].count(chr(10)) + 1} 行"
                    for m in BARE_PATH_RE.finditer(body)
                ]
                self.assertEqual(bare, [], f"{skill_file} 含裸相对路径：{bare}")
                self.assertNotIn("~/.llm-wiki", body, f"{skill_file} 锚句外硬编码全局链")



class ContentWhitelistTest(unittest.TestCase):
    """AGENTS.md 内容白名单与 sync.sh add_content 清单必须同源一致（防止两处清单漂移）。"""

    def test_whitelist_single_source(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        m = re.search(r"内容目录——(.+?)——", agents)
        self.assertIsNotNone(m, "AGENTS.md 未找到「内容目录——…——」白名单句")
        agents_dirs = re.findall(r"`([^`]+)/`", m.group(1))
        self.assertTrue(agents_dirs, "AGENTS.md 白名单句中未解析出目录")

        sync = (ROOT / "scripts" / "sync.sh").read_text(encoding="utf-8")
        sm = re.search(r"for d in ([^;]+); do", sync)
        self.assertIsNotNone(sm, "sync.sh 未找到 add_content 白名单循环")
        sync_dirs = sm.group(1).split()

        self.assertEqual(
            sorted(agents_dirs), sorted(sync_dirs),
            "AGENTS.md 与 sync.sh 的内容白名单不一致——两处必须同步修改",
        )


if __name__ == "__main__":
    unittest.main()
