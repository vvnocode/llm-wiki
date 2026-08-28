#!/usr/bin/env python3
"""项目级 Skill 单一真源、入口链接与全局路径约定的结构测试。"""
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

# 全局挂载的 skill（bootstrap 会软链到 ~/.claude/skills、~/.codex/skills）：
# 其 SKILL.md 会在任意 cwd 下被读取，仓内路径必须写成 ~/.llm-wiki/... 绝对形式
GLOBAL_SKILLS = (
    "llm-wiki-ingest",
    "llm-wiki-query",
    "llm-wiki-lint",
    "llm-wiki-learn",
)

# 裸相对仓内路径：wiki/... docs/... 等前面既不是 ~/.llm-wiki/ 也不是路径成分
BARE_PATH_RE = re.compile(
    r"(?<![\w/~.\-])(?:wiki|inputs|docs|config|scripts|outputs|state)/"
)


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

    def test_global_skill_paths_absolute(self) -> None:
        """全局 skill 的 SKILL.md 禁止裸相对仓内路径，且必须经 ~/.llm-wiki 引用。"""
        for name in GLOBAL_SKILLS:
            with self.subTest(skill=name):
                skill_file = ROOT / ".agents/skills" / name / "SKILL.md"
                self.assertTrue(skill_file.is_file(), skill_file)
                text = skill_file.read_text(encoding="utf-8")
                bare = [
                    f"{m.group(0)!r} @ {text[:m.start()].count(chr(10)) + 1}"
                    for m in BARE_PATH_RE.finditer(text)
                ]
                self.assertEqual(bare, [], f"{skill_file} 含裸相对路径：{bare}")
                self.assertIn("~/.llm-wiki/", text, skill_file)


if __name__ == "__main__":
    unittest.main()
