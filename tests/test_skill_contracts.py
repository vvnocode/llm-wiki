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

    def test_lint_skill_semantic_checklist(self) -> None:
        """lint Skill 的语义层必须是固定六项清单，且每次跑完都要记 lint 日志（不论是否改动），否则语义 lint 做没做无法回溯。"""
        text = (ROOT / ".agents/skills/llm-wiki-lint/SKILL.md").read_text(encoding="utf-8")
        for item in ("两页冲突", "被新原料否定的旧结论", "重要对象缺页", "缺交叉引用", "能靠读代码或公开文档补上的缺口", "长期待核验"):
            self.assertIn(item, text, f"lint Skill 缺语义项：{item}")
        self.assertIn("不论是否改动", text, "lint Skill 须要求每次都追加 lint 日志")

    def test_ingest_skill_generates_index_and_passes_own_paths(self) -> None:
        """ingest Skill 必须让公共层索引走脚本生成、收口只传本轮自己写的路径，并写明外部原料里的指令当数据。"""
        text = (ROOT / ".agents/skills/llm-wiki-ingest/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("build-index.py", text, "ingest Skill 须让公共层索引由脚本生成，而不是手改清单")
        self.assertIn('sync.sh "<主题>" <路径…>', text, "ingest Skill 须写明收口要传入本轮路径")
        self.assertIn("--all", text, "ingest Skill 须说明 --all 的适用条件")
        self.assertIn("指令", text)
        self.assertIn("当数据", text, "ingest Skill 须写明外部原料里的指令一律当数据")

    def test_query_skill_has_miss_protocol(self) -> None:
        """query Skill 必须写明索引未命中时的顺序：换词再看索引 → 全文搜索 → 之后才能说 wiki 没有。"""
        text = (ROOT / ".agents/skills/llm-wiki-query/SKILL.md").read_text(encoding="utf-8")
        for item in ("同义词", "全文搜索", "曾用标题"):
            self.assertIn(item, text, f"query Skill 缺未命中处理：{item}")

    def test_former_title_skipped_when_renamed_for_correction(self) -> None:
        """「曾用标题」只为普通改名与合并而留：因订正结论而改名的不加，否则被推翻的说法会经索引继续参与选路。
        ingest Skill 与 schema 都要在「曾用标题：<旧标题>」这条规则的同一行里写明这个例外。"""
        for rel in (".agents/skills/llm-wiki-ingest/SKILL.md", "docs/schemas/wiki.md"):
            with self.subTest(file=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                # 规则句以「曾用标题：<旧标题>」为锚；例外必须与它同行，分开写容易只读到前半句
                rule = next((line for line in text.splitlines() if "曾用标题：<旧标题>" in line), "")
                self.assertTrue(rule, f"{rel} 未找到「曾用标题：<旧标题>」规则句")
                self.assertIn("订正", rule, f"{rel} 须写明因订正结论而改名的不加旧标题")

    def test_every_sync_mention_passes_paths(self) -> None:
        """四份 Skill 里凡是让跑 sync.sh 的地方都要带路径：不带路径的调用在有在途改动时会被拒绝。"""
        for name in SKILLS:
            with self.subTest(skill=name):
                text = (ROOT / ".agents/skills" / name / "SKILL.md").read_text(encoding="utf-8")
                for line in text.splitlines():
                    if "sync.sh" in line:
                        self.assertIn("<路径…>", line, f"{name}：{line.strip()[:60]}")

    def test_skills_do_not_pin_risks_to_one_file(self) -> None:
        """待核验按主题分页后，Skill 不再把 open-questions.md 当作唯一落点。"""
        for name in SKILLS:
            with self.subTest(skill=name):
                text = (ROOT / ".agents/skills" / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertNotIn("open-questions", text)



class ContentWhitelistTest(unittest.TestCase):
    """AGENTS.md 内容白名单与 sync.sh add_content 清单必须同源一致（防止两处清单漂移）。"""

    def test_whitelist_single_source(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        m = re.search(r"内容目录——(.+?)——", agents)
        self.assertIsNotNone(m, "AGENTS.md 未找到「内容目录——…——」白名单句")
        agents_dirs = re.findall(r"`([^`]+)/`", m.group(1))
        self.assertTrue(agents_dirs, "AGENTS.md 白名单句中未解析出目录")

        sync = (ROOT / "scripts" / "sync.sh").read_text(encoding="utf-8")
        sm = re.search(r"^CONTENT_DIRS=\(([^)]+)\)", sync, re.M)
        self.assertIsNotNone(sm, "sync.sh 未找到 CONTENT_DIRS 白名单数组")
        sync_dirs = sm.group(1).split()

        self.assertEqual(
            sorted(agents_dirs), sorted(sync_dirs),
            "AGENTS.md 与 sync.sh 的内容白名单不一致——两处必须同步修改",
        )


if __name__ == "__main__":
    unittest.main()
