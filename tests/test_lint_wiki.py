#!/usr/bin/env python3
"""lint-wiki.py 的夹具单测：现有每类机械检查各一红一绿，加两级索引、子索引规则、私有区豁免与外部来源前缀。

夹具在临时目录里搭最小 wiki，用 `lint-wiki.py --root` 实跑脚本；不拿「当前仓库碰巧是绿的」当唯一证明。
最后一个用例另外保证模板自带的种子 wiki 通过 lint。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint-wiki.py"

# 一份合法事实页的正文尾部：来源指向夹具里真实存在的原料
PAGE_TAIL = "\n## 来源\n\n- `inputs/manual/fact.md`：本页结论。\n\n## 最后核验\n\n- 2026-08-20（回读原料）\n"


def run_lint(root: Path) -> subprocess.CompletedProcess[str]:
    """在指定仓库根实跑机械 lint，返回完整进程结果（退出码 1 表示有问题）。"""
    return subprocess.run(
        [sys.executable, str(LINT), "--root", str(root)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def write(root: Path, rel: str, content: str) -> None:
    """写夹具文件，自动建父目录。"""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def minimal_wiki(root: Path) -> None:
    """刚好能通过机械 lint 的最小 wiki：根索引、根 log、一个月日志、一张事实页与它的原料。"""
    write(root, "wiki/index.md", "# Wiki\n\n- [主题](concepts/topic.md)\n- [日志](log.md)\n")
    write(root, "wiki/log.md", "# 日志\n\n- [2026-08](logs/2026-08.md)\n")
    write(root, "wiki/logs/2026-08.md", "# 2026-08\n\n## [2026-08-20] ingest | 建立主题\n")
    write(root, "wiki/concepts/topic.md", "# 主题\n\n事实。\n" + PAGE_TAIL)
    write(root, "inputs/manual/fact.md", "原料\n")


def add_sub_index(root: Path, listed_in_root: bool = True, body: str = "") -> None:
    """在夹具里加一个项目分区：子索引 projects/foo/index.md 与只挂在它下面的 page.md。

    listed_in_root 为 False 时根索引不登记该子索引；body 会追加到子索引的导航内容之后。
    """
    if listed_in_root:
        write(root, "wiki/index.md", "# Wiki\n\n- [主题](concepts/topic.md)\n- [foo 分区](projects/foo/index.md)\n- [日志](log.md)\n")
    write(
        root,
        "wiki/projects/foo/index.md",
        "# foo 分区索引\n\nfoo 项目的分区索引，一句导语。\n\n## 页面\n\n- [foo 页](page.md)：一句话。\n\n| 入口 | 说明 |\n|---|---|\n| [foo 页](page.md) | 表格里的导航 |\n" + body,
    )
    write(root, "wiki/projects/foo/page.md", "# foo 页\n\n事实。\n" + PAGE_TAIL)


class Fixture(unittest.TestCase):
    """每个用例一个临时仓库根。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        minimal_wiki(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def assert_green(self) -> None:
        proc = run_lint(self.root)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def assert_red(self, *fragments: str) -> str:
        """断言 lint 失败且输出包含每个片段，返回输出供进一步断言。"""
        proc = run_lint(self.root)
        self.assertNotEqual(proc.returncode, 0, msg="lint 本应报错却是绿的：\n" + proc.stdout)
        for fragment in fragments:
            self.assertIn(fragment, proc.stdout)
        return proc.stdout


class ExistingChecks(Fixture):
    """既有九类机械检查：绿的基线加每类一个红用例。"""

    def test_fixture_passes(self) -> None:
        self.assert_green()

    def test_page_not_in_index(self) -> None:
        # 被主题页链接（不是孤儿），但根索引没登记
        write(self.root, "wiki/concepts/other.md", "# 其它\n\n事实。\n" + PAGE_TAIL)
        write(self.root, "wiki/concepts/topic.md", "# 主题\n\n见 [其它](other.md)。\n" + PAGE_TAIL)
        out = self.assert_red("未入 index：concepts/other.md")
        self.assertNotIn("孤儿页", out)

    def test_missing_source_section(self) -> None:
        write(self.root, "wiki/concepts/topic.md", "# 主题\n\n## 最后核验\n\n- 2026-08-20\n")
        self.assert_red("缺「来源」节：concepts/topic.md")

    def test_missing_verify_section(self) -> None:
        write(self.root, "wiki/concepts/topic.md", "# 主题\n\n## 来源\n\n- `inputs/manual/fact.md`。\n")
        self.assert_red("缺「最后核验」节：concepts/topic.md")

    def test_broken_link(self) -> None:
        write(self.root, "wiki/concepts/topic.md", "# 主题\n\n见 [无](../missing.md)。\n" + PAGE_TAIL)
        self.assert_red("断链 concepts/topic.md → ../missing.md")

    def test_outputs_as_evidence(self) -> None:
        write(
            self.root,
            "wiki/concepts/topic.md",
            "# 主题\n\n## 来源\n\n- `outputs/2026-08-报告/a.md`：当证据。\n\n## 最后核验\n\n- 2026-08-20\n",
        )
        self.assert_red("来源节疑似用 outputs 自证：concepts/topic.md")

    def test_missing_source_path(self) -> None:
        write(
            self.root,
            "wiki/concepts/topic.md",
            "# 主题\n\n## 来源\n\n- `inputs/manual/no-such.md`：不存在。\n\n## 最后核验\n\n- 2026-08-20\n",
        )
        self.assert_red("来源路径不存在 concepts/topic.md → `inputs/manual/no-such.md`")

    def test_forbidden_source(self) -> None:
        write(self.root, "wiki/concepts/topic.md", "# 主题\n\n读了 `repos/app/node_modules/x/index.js`。\n" + PAGE_TAIL)
        self.assert_red("疑似禁止来源：concepts/topic.md")

    def test_orphan_page(self) -> None:
        write(self.root, "wiki/concepts/lonely.md", "# 孤儿\n\n事实。\n" + PAGE_TAIL)
        self.assert_red("孤儿页（index 与其它页都未链到）：concepts/lonely.md")

    def test_root_log_with_dated_entry(self) -> None:
        write(self.root, "wiki/log.md", "# 日志\n\n## [2026-08-20] ingest | 不该出现在根日志\n")
        self.assert_red("根日志不应含日期条目")

    def test_month_log_entry_format(self) -> None:
        write(self.root, "wiki/logs/2026-08.md", "# 2026-08\n\n## [2026-08-20] 更新了主题\n")
        self.assert_red("logs/2026-08.md:3 格式不是 ## [日期] 动作 | 标题")

    def test_month_log_month_mismatch(self) -> None:
        write(self.root, "wiki/logs/2026-08.md", "# 2026-08\n\n## [2026-09-01] ingest | 月份不对\n")
        self.assert_red("logs/2026-08.md:3 日期与文件名月份不一致")

    def test_month_log_bad_filename(self) -> None:
        write(self.root, "wiki/logs/aug.md", "# aug\n")
        self.assert_red("非法月日志文件名：logs/aug.md")

    def test_missing_month_logs_with_content(self) -> None:
        (self.root / "wiki/logs/2026-08.md").unlink()
        self.assert_red("logs/ 下没有 YYYY-MM.md")

    def test_missing_root_log(self) -> None:
        (self.root / "wiki/log.md").unlink()
        write(self.root, "wiki/index.md", "# Wiki\n\n- [主题](concepts/topic.md)\n")
        self.assert_red("缺少 log.md")

    def test_missing_root_index(self) -> None:
        (self.root / "wiki/index.md").unlink()
        self.assert_red("缺少 index.md")


class TwoLevelIndex(Fixture):
    """两级索引：根 index 只列分区入口，分区页挂在子索引下即算已入索引。"""

    def test_page_listed_only_in_sub_index_passes(self) -> None:
        add_sub_index(self.root)
        self.assert_green()

    def test_sub_index_missing_from_root_reported_once(self) -> None:
        add_sub_index(self.root, listed_in_root=False)
        out = self.assert_red("子索引未入根 index：projects/foo/index.md")
        # 只报根因，不再把子索引下的页面逐个报成「未入 index」
        self.assertNotIn("未入 index：projects/foo/page.md", out)

    def test_learning_index_is_also_sub_index(self) -> None:
        write(self.root, "wiki/index.md", "# Wiki\n\n- [主题](concepts/topic.md)\n- [学习](learning/index.md)\n- [日志](log.md)\n")
        write(self.root, "wiki/learning/index.md", "# 学习中心\n\n- [路线](paths/x.md)\n")
        write(self.root, "wiki/learning/paths/x.md", "# 路线\n\n目标。\n" + PAGE_TAIL)
        self.assert_green()


class SubIndexRule(Fixture):
    """子索引规则：纯导航的免检两节；承载正文的按事实页检查来源与核验。"""

    def test_navigation_only_exempt(self) -> None:
        add_sub_index(self.root)
        self.assert_green()

    def test_extra_paragraph_counts_as_body(self) -> None:
        add_sub_index(self.root, body="\n第二段正文：2026-09-01 上线七期，负责人某某。\n")
        self.assert_red("缺「来源」节：projects/foo/index.md", "缺「最后核验」节：projects/foo/index.md")

    def test_list_item_without_link_counts_as_body(self) -> None:
        add_sub_index(self.root, body="\n- 线上入口 `https://example.test`，09-10 探测正常\n")
        self.assert_red("缺「来源」节：projects/foo/index.md")

    def test_body_with_sections_passes(self) -> None:
        add_sub_index(self.root, body="\n第二段正文。\n" + PAGE_TAIL)
        self.assert_green()


class PrivateZone(Fixture):
    """私有区只豁免「未入 index」与「孤儿页」；私有页发出的链接不给公共页算入链。"""

    def test_private_page_not_indexed_passes(self) -> None:
        write(self.root, "wiki/private/note.md", "# 私有\n\n评价。\n" + PAGE_TAIL)
        self.assert_green()

    def test_private_page_still_needs_sections(self) -> None:
        write(self.root, "wiki/private/note.md", "# 私有\n\n评价。\n")
        self.assert_red("缺「来源」节：private/note.md", "缺「最后核验」节：private/note.md")

    def test_private_link_does_not_rescue_public_orphan(self) -> None:
        write(self.root, "wiki/concepts/hidden.md", "# 隐藏\n\n事实。\n" + PAGE_TAIL)
        write(self.root, "wiki/private/note.md", "# 私有\n\n见 [隐藏](../concepts/hidden.md)。\n" + PAGE_TAIL)
        self.assert_red("孤儿页（index 与其它页都未链到）：concepts/hidden.md")

    def test_private_sub_index_exempt(self) -> None:
        write(self.root, "wiki/private/index.md", "# 私有索引\n\n- [私有](note.md)\n")
        write(self.root, "wiki/private/note.md", "# 私有\n\n评价。\n" + PAGE_TAIL)
        self.assert_green()


class ExternalSourceRef(Fixture):
    """外部仓来源写 `<登记名>[@<ref>]:<仓内路径>`，不按本仓路径检查；裸路径照旧检查。"""

    def test_prefixed_refs_skipped(self) -> None:
        write(
            self.root,
            "wiki/concepts/topic.md",
            "# 主题\n\n## 来源\n\n- `openclaw@v2026.7.1-2:docs/concepts/queue.md`：队列说明。\n- `assistant-repo:docs/acceptance/cases.md`：验收集。\n\n## 最后核验\n\n- 2026-08-20\n",
        )
        self.assert_green()

    def test_bare_path_still_reported(self) -> None:
        write(
            self.root,
            "wiki/concepts/topic.md",
            "# 主题\n\n## 来源\n\n- 外部仓 `docs/concepts/queue.md`：裸写。\n\n## 最后核验\n\n- 2026-08-20\n",
        )
        self.assert_red("来源路径不存在 concepts/topic.md → `docs/concepts/queue.md`")


class TemplateSeed(unittest.TestCase):
    def test_template_seed_wiki_clean(self) -> None:
        """模板自带的种子 wiki 必须通过机械 lint。"""
        proc = run_lint(ROOT)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
