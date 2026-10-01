#!/usr/bin/env python3
"""build-index.py 的夹具单测：公共层分区索引的生成内容、根索引入口归一、--from-git 口径，以及生成结果能通过 lint。

夹具在临时目录里搭最小 wiki，用 `build-index.py --root` 实跑脚本。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build-index.py"
LINT = ROOT / "scripts" / "lint-wiki.py"

# 一份合法事实页的尾部：来源指向夹具里真实存在的原料
PAGE_TAIL = "\n## 来源\n\n- `inputs/manual/fact.md`：本页结论。\n\n## 最后核验\n\n- 2026-10-01（回读原料）\n"
# 生成索引的导语（分区有 README 时）
LEAD = "本页由 `scripts/build-index.py` 按各页标题生成，不要手改；本分区收什么见 [README](README.md)。"
# 种子根索引的公共层入口写法：链接指向各分区 README
SEED_ROOT = (
    "# Wiki 目录\n\n- [演进日志](log.md)：按月索引。\n\n## 公共层\n\n"
    "| 分区 | 收什么 |\n|---|---|\n"
    "| [concepts/](concepts/README.md) | 概念 |\n"
    "| [entities/](entities/README.md) | 实体 |\n"
    "| [risks/](risks/README.md) | 待核验 |\n\n"
    "## 学习\n\n[learning/](learning/README.md)：学习中心。\n"
)


def write(root: Path, rel: str, content: str) -> None:
    """写夹具文件，自动建父目录。"""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def run_build(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """在指定仓库根实跑 build-index.py。"""
    return subprocess.run(
        [sys.executable, str(BUILD), "--root", str(root), *args], cwd=ROOT, capture_output=True, text=True
    )


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def seed_wiki(root: Path) -> None:
    """最小种子 wiki：根索引、日志、三个公共层分区（各带 README）与一个不归脚本管的学习区。"""
    write(root, "wiki/index.md", SEED_ROOT)
    write(root, "wiki/log.md", "# 日志\n\n- [2026-10](logs/2026-10.md)\n")
    write(root, "wiki/logs/2026-10.md", "# 2026-10\n\n## [2026-10-01] ingest | 建立主题\n")
    for section in ("concepts", "entities", "risks", "learning"):
        write(root, f"wiki/{section}/README.md", f"# {section}/\n\n分区说明。\n")
    write(root, "inputs/manual/fact.md", "原料\n")


class Fixture(unittest.TestCase):
    """每个用例一个临时仓库根。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        seed_wiki(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self, *args: str) -> subprocess.CompletedProcess[str]:
        proc = run_build(self.root, *args)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        return proc


class SectionIndexContent(Fixture):
    """生成索引的内容：标题、排序、回退、曾用标题、空分区、不收的文件。"""

    def test_lists_pages_by_title_sorted_by_filename(self) -> None:
        write(self.root, "wiki/concepts/b.md", "# 乙概念\n\n事实。\n" + PAGE_TAIL)
        write(self.root, "wiki/concepts/a.md", "# 甲概念\n\n事实。\n" + PAGE_TAIL)
        self.build()
        self.assertEqual(
            read(self.root, "wiki/concepts/index.md"),
            f"# concepts/ 索引\n\n{LEAD}\n\n- [甲概念](a.md)\n- [乙概念](b.md)\n",
        )

    def test_title_falls_back_to_file_stem(self) -> None:
        write(self.root, "wiki/concepts/无标题页.md", "没有一级标题。\n" + PAGE_TAIL)
        self.build()
        self.assertIn("- [无标题页](无标题页.md)\n", read(self.root, "wiki/concepts/index.md"))

    def test_former_titles_are_appended(self) -> None:
        write(self.root, "wiki/concepts/x.md", "# 新标题\n\n导语。\n\n曾用标题：旧名一、旧名二\n" + PAGE_TAIL)
        self.build()
        self.assertIn("- [新标题](x.md)（曾用标题：旧名一、旧名二）\n", read(self.root, "wiki/concepts/index.md"))

    def test_square_brackets_in_title_do_not_break_the_link(self) -> None:
        """标题里的方括号会截断 Markdown 链接文字（lint 就认不出这条链接），生成时换成全角。"""
        write(self.root, "wiki/concepts/x.md", "# [已废弃] 旧方案\n\n事实。\n" + PAGE_TAIL)
        self.build()
        self.assertIn("- [［已废弃］ 旧方案](x.md)\n", read(self.root, "wiki/concepts/index.md"))
        proc = subprocess.run(
            [sys.executable, str(LINT), "--root", str(self.root)], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_empty_section_has_header_and_lead_only(self) -> None:
        self.build()
        self.assertEqual(read(self.root, "wiki/entities/index.md"), f"# entities/ 索引\n\n{LEAD}\n")

    def test_readme_index_and_nested_files_are_not_listed(self) -> None:
        write(self.root, "wiki/concepts/a.md", "# 甲\n" + PAGE_TAIL)
        write(self.root, "wiki/concepts/sub/deep.md", "# 深层\n" + PAGE_TAIL)
        self.build()
        self.assertEqual(
            read(self.root, "wiki/concepts/index.md"), f"# concepts/ 索引\n\n{LEAD}\n\n- [甲](a.md)\n"
        )

    def test_section_without_readme_omits_readme_link(self) -> None:
        (self.root / "wiki/entities/README.md").unlink()
        self.build()
        self.assertEqual(
            read(self.root, "wiki/entities/index.md"),
            "# entities/ 索引\n\n本页由 `scripts/build-index.py` 按各页标题生成，不要手改。\n",
        )

    def test_only_existing_public_sections_are_generated(self) -> None:
        """夹具里没有 operations、decisions 目录；学习区不归脚本管。"""
        self.build()
        self.assertFalse((self.root / "wiki/operations").exists())
        self.assertFalse((self.root / "wiki/decisions").exists())
        self.assertFalse((self.root / "wiki/learning/index.md").exists())
        self.assertTrue((self.root / "wiki/risks/index.md").is_file())


class ChangedPathsAndIdempotence(Fixture):
    """标准输出只打印被改写的文件路径；重复运行不再改写。"""

    def test_prints_changed_paths_then_nothing(self) -> None:
        write(self.root, "wiki/concepts/a.md", "# 甲\n" + PAGE_TAIL)
        first = self.build()
        self.assertEqual(
            sorted(first.stdout.split()),
            ["wiki/concepts/index.md", "wiki/entities/index.md", "wiki/index.md", "wiki/risks/index.md"],
        )
        before = {p: read(self.root, p) for p in first.stdout.split()}
        second = self.build()
        self.assertEqual(second.stdout, "")
        self.assertEqual({p: read(self.root, p) for p in before}, before)

    def test_new_page_only_rewrites_its_section(self) -> None:
        self.build()
        write(self.root, "wiki/risks/某主题.md", "# 某主题\n" + PAGE_TAIL)
        proc = self.build()
        self.assertEqual(proc.stdout.split(), ["wiki/risks/index.md"])


class RootEntryLinks(Fixture):
    """根索引的分区入口归一到生成索引；只动公共层分区的链接目标。"""

    def test_root_links_point_to_generated_index(self) -> None:
        self.build()
        root_index = read(self.root, "wiki/index.md")
        self.assertIn("| [concepts/](concepts/index.md) | 概念 |", root_index)
        self.assertIn("| [risks/](risks/index.md) | 待核验 |", root_index)
        self.assertNotIn("concepts/README.md", root_index)
        self.assertIn("[learning/](learning/README.md)", root_index, "学习区不归脚本管，链接不动")

    def test_warns_when_root_has_no_entry_for_a_section(self) -> None:
        write(self.root, "wiki/index.md", SEED_ROOT.replace("| [risks/](risks/README.md) | 待核验 |\n", ""))
        proc = self.build()
        self.assertIn("risks", proc.stderr)
        self.assertIn("入口", proc.stderr)
        self.assertNotIn("concepts", proc.stderr.replace("build-index", ""))


class FromGit(Fixture):
    """--from-git：清单只取已跟踪或已暂存的页，使提交进去的索引与提交进去的页面一致。"""

    def setUp(self) -> None:
        super().setUp()
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.name", "test")
        git(self.root, "config", "user.email", "test@example.com")
        write(self.root, "wiki/concepts/tracked.md", "# 已提交的页\n" + PAGE_TAIL)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")

    def test_untracked_page_is_excluded_but_staged_page_is_included(self) -> None:
        write(self.root, "wiki/concepts/staged.md", "# 本轮暂存的页\n" + PAGE_TAIL)
        git(self.root, "add", "wiki/concepts/staged.md")
        write(self.root, "wiki/concepts/others.md", "# 别的会话没写完的页\n" + PAGE_TAIL)
        self.build("--from-git")
        index = read(self.root, "wiki/concepts/index.md")
        self.assertIn("- [已提交的页](tracked.md)\n", index)
        self.assertIn("- [本轮暂存的页](staged.md)\n", index)
        self.assertNotIn("others.md", index)

    def test_without_flag_lists_files_on_disk(self) -> None:
        write(self.root, "wiki/concepts/others.md", "# 别的会话没写完的页\n" + PAGE_TAIL)
        self.build()
        self.assertIn("- [别的会话没写完的页](others.md)\n", read(self.root, "wiki/concepts/index.md"))

    def test_tracked_page_missing_on_disk_keeps_its_title(self) -> None:
        """别的会话在工作区删了一张已跟踪的页但还没提交：提交进去的树里它仍在，索引照列，标题取自 git 索引。"""
        (self.root / "wiki/concepts/tracked.md").unlink()
        self.build("--from-git")
        self.assertIn("- [已提交的页](tracked.md)\n", read(self.root, "wiki/concepts/index.md"))

    def test_prints_generated_files_that_differ_from_head(self) -> None:
        """--from-git 的标准输出是「要随提交带上的生成文件」：即使本次没有改写（之前手工跑过一次），
        只要与 HEAD 有差异就列出；都已提交后不再列。"""
        self.build()                                   # 先按磁盘生成一次：索引与根索引入口都已是最新，但还没提交
        proc = self.build("--from-git")
        self.assertEqual(
            sorted(proc.stdout.split()),
            ["wiki/concepts/index.md", "wiki/entities/index.md", "wiki/index.md", "wiki/risks/index.md"],
        )
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "index")
        self.assertEqual(self.build("--from-git").stdout, "")

    def test_root_index_is_not_listed_when_it_has_other_pending_edits(self) -> None:
        """根索引的待提交改动不只是入口归一时（还混着手工改动），不列出，由改它的会话自己提交。"""
        root_index = self.root / "wiki/index.md"
        root_index.write_text(root_index.read_text(encoding="utf-8") + "\n别的会话加的一行\n", encoding="utf-8")
        proc = self.build("--from-git")
        self.assertNotIn("wiki/index.md", proc.stdout.split())
        self.assertIn("wiki/concepts/index.md", proc.stdout.split())
        self.assertIn("(concepts/index.md)", read(self.root, "wiki/index.md"), "磁盘上的入口归一照做")

    def test_chinese_paths_survive_a_non_utf8_locale(self) -> None:
        """Agent 派生的子进程常不带 UTF-8 语言环境：git 输出仍按 UTF-8 解码，中文文件名与标题不能乱。"""
        write(self.root, "wiki/concepts/中文页.md", "# 中文标题\n" + PAGE_TAIL)
        git(self.root, "add", "-A")
        env = {**os.environ, "LC_ALL": "en_US.ISO8859-1", "PYTHONUTF8": "0"}
        proc = subprocess.run(
            [sys.executable, str(BUILD), "--root", str(self.root), "--from-git"], cwd=ROOT, capture_output=True, env=env
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr.decode("utf-8", "replace"))
        self.assertIn("- [中文标题](中文页.md)\n", read(self.root, "wiki/concepts/index.md"))

    def test_from_git_outside_a_repository_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bare = Path(tmp).resolve()
            seed_wiki(bare)
            proc = run_build(bare, "--from-git")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("git", proc.stderr)


class GeneratedWikiPassesLint(Fixture):
    """页面只挂在生成索引下、根索引入口已归一时，机械 lint 通过；生成页按纯导航子索引免检两节。"""

    def test_lint_is_green_after_build(self) -> None:
        write(self.root, "wiki/concepts/a.md", "# 甲\n\n事实。\n" + PAGE_TAIL)
        write(self.root, "wiki/risks/某主题.md", "# 某主题\n\n| 问题 | 现状 | 闭环方式 |\n|---|---|---|\n| 甲 | 乙 | 丙 |\n" + PAGE_TAIL)
        self.build()
        proc = subprocess.run(
            [sys.executable, str(LINT), "--root", str(self.root)], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_lint_reports_unindexed_page_before_build(self) -> None:
        """对照：不跑生成时，新页没有入索引，lint 报出来。"""
        write(self.root, "wiki/concepts/a.md", "# 甲\n\n事实。\n" + PAGE_TAIL)
        proc = subprocess.run(
            [sys.executable, str(LINT), "--root", str(self.root)], cwd=ROOT, capture_output=True, text=True
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("未入 index：concepts/a.md", proc.stdout)


if __name__ == "__main__":
    unittest.main()
