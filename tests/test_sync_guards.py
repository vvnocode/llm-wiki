#!/usr/bin/env python3
"""sync.sh 的提交口径与守卫：只提交传入的路径、`--all` 的默认范围、合并进行中拒绝、不在 main 拒绝、
排除项对提交同样生效、仓库级锁、生成索引随提交。

在临时仓库里复制并实跑真实的 scripts/sync.sh（无 origin、无 template 分支，走「仅本地提交」分支）。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "sync.sh"
BUILD_INDEX = ROOT / "scripts" / "build-index.py"
# 与 test_shell_utf8 一致：在 UTF-8 语言环境下实跑，覆盖 bash 3.2 的多字节解析路径
UTF8_ENV = {**os.environ, "LC_ALL": "en_US.UTF-8"}


def git(repo: Path, *args: str) -> str:
    """在 repo 里执行 git，失败即抛出，返回去掉首尾空白的标准输出。"""
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def write(path: Path, text: str) -> None:
    """写文件，自动建父目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def porcelain(repo: Path) -> dict[str, str]:
    """把 git status --porcelain 解析成 {路径: 两字符状态码}，不受首列空格被 strip 掉影响；中文路径原样输出。"""
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    return {line[3:]: line[:2] for line in out.splitlines() if line}


def committed_files(repo: Path) -> list[str]:
    """HEAD 提交涉及的文件清单；关掉改名检测，删除的旧路径与新增的新路径各算一项。"""
    out = git(repo, "show", "--name-only", "--no-renames", "--format=", "HEAD")
    return sorted(line for line in out.splitlines() if line)


class RepoFixture(unittest.TestCase):
    """临时仓库：复制 sync.sh，由子类的 seed() 放初始文件后做第一次提交。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve() / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy(SYNC, self.repo / "scripts" / "sync.sh")
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "test")
        git(self.repo, "config", "user.email", "test@example.com")
        self.seed()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "init")
        self.init_sha = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def seed(self) -> None:
        """初始提交含内容目录文件、采集快照与一个骨架脚本。"""
        write(self.repo / "wiki/index.md", "# index\n")
        write(self.repo / "inputs/manual/m.md", "# m\n")
        write(self.repo / "inputs/raw/source-a/s.json", '{"v": 1}')
        write(self.repo / "scripts/x.sh", "echo 1\n")

    def run_sync(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """实跑 sync.sh；args 原样传入（含 --all、主题与路径）。"""
        return subprocess.run(
            ["bash", "scripts/sync.sh", *args], cwd=self.repo, capture_output=True, text=True, env=env or UTF8_ENV
        )


class SyncGuardsTest(RepoFixture):
    def set_excludes(self, entries: str) -> None:
        """把临时仓库里 sync.sh 的 CONTENT_EXCLUDES 整行换成给定内容；实例已登记排除项时同样适用。"""
        script = self.repo / "scripts/sync.sh"
        text = script.read_text(encoding="utf-8")
        new_text, n = re.subn(r"^CONTENT_EXCLUDES=\(.*\)\s*$", f"CONTENT_EXCLUDES=({entries})", text, flags=re.M)
        self.assertEqual(n, 1, "sync.sh 应有且只有一行 CONTENT_EXCLUDES=(…) 供实例登记排除项")
        script.write_text(new_text, encoding="utf-8")

    def test_prestaged_skeleton_change_not_swept_into_commit(self) -> None:
        """白名单外的已暂存改动不随 ingest 提交，提交后仍留在暂存区。"""
        write(self.repo / "scripts/x.sh", "echo 2\n")
        git(self.repo, "add", "scripts/x.sh")
        write(self.repo / "wiki/index.md", "# index v2\n")
        write(self.repo / "wiki/new.md", "# new\n")
        proc = self.run_sync("--all", "测试主题")
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["wiki/index.md", "wiki/new.md"])
        self.assertEqual(porcelain(self.repo).get("scripts/x.sh"), "M ", "骨架改动应仍留在暂存区")
        self.assertIn("scripts/x.sh", proc.stdout, msg="应提示白名单外的已暂存改动未随本次提交")

    def test_refuses_when_merge_in_progress(self) -> None:
        """有进行中的合并 / 变基时拒绝，不提交。"""
        write(self.repo / "wiki/index.md", "# index v2\n")
        gitdir = self.repo / ".git"
        cases = {
            "MERGE_HEAD": lambda: (gitdir / "MERGE_HEAD").write_text(self.init_sha + "\n"),
            "rebase-merge": lambda: (gitdir / "rebase-merge").mkdir(),
        }
        for name, arm in cases.items():
            with self.subTest(state=name):
                arm()
                try:
                    proc = self.run_sync("测试主题", "wiki/index.md")
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn("进行中", proc.stdout + proc.stderr)
                    self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)
                finally:
                    target = gitdir / name
                    if target.is_dir():
                        target.rmdir()
                    else:
                        target.unlink()

    def test_refuses_off_main(self) -> None:
        """不在 main 上不自动提交内容。"""
        git(self.repo, "checkout", "-q", "-b", "task")
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("main", proc.stdout + proc.stderr)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)

    def test_exclude_entries_apply_to_commit_too(self) -> None:
        """实例在 CONTENT_EXCLUDES 里登记的排除项，对暂存、判空和提交同时生效。"""
        self.set_excludes("':(exclude)inputs/raw/source-a'")
        write(self.repo / "inputs/raw/source-a/s.json", '{"v": 2}')
        write(self.repo / "inputs/manual/m.md", "# m v2\n")
        proc = self.run_sync("--all", "测试主题", "inputs/raw")
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["inputs/manual/m.md"])
        self.assertEqual(porcelain(self.repo).get("inputs/raw/source-a/s.json"), " M", "被排除的快照应保持未暂存")

    def test_set_excludes_replaces_whole_line_even_with_registered_entries(self) -> None:
        """实例已登记含括号的排除项时，整行替换仍得到合法脚本。

        v0.3.8 的正则用 `[^)]*` 匹配数组内容，遇到 `:(exclude)` 的右括号就截断，替换后脚本损坏。
        """
        script = self.repo / "scripts/sync.sh"
        text = script.read_text(encoding="utf-8")
        script.write_text(
            text.replace("CONTENT_EXCLUDES=()", "CONTENT_EXCLUDES=(':(exclude)inputs/raw/source-b')"),
            encoding="utf-8",
        )
        self.set_excludes("':(exclude)inputs/raw/source-a'")
        lines = [ln for ln in script.read_text(encoding="utf-8").splitlines() if ln.startswith("CONTENT_EXCLUDES=")]
        self.assertEqual(lines, ["CONTENT_EXCLUDES=(':(exclude)inputs/raw/source-a')"])
        syntax = subprocess.run(["bash", "-n", "scripts/sync.sh"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_only_excluded_change_means_nothing_to_commit(self) -> None:
        """只有被排除的路径有改动时，判空要说无变更，而不是提交一个空提交或把排除项带进去。"""
        self.set_excludes("':(exclude)inputs/raw/source-a'")
        write(self.repo / "inputs/raw/source-a/s.json", '{"v": 2}')
        for args in (("--all", "测试主题", "inputs/raw"), ("测试主题",)):
            with self.subTest(args=args):
                proc = self.run_sync(*args)
                self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
                self.assertIn("无变更", proc.stdout)
                self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)

    def test_lint_runs_before_commit_without_blocking(self) -> None:
        """仓里有 scripts/lint-wiki.py 时，提交前跑一次并打印结果；lint 红不阻断内容提交。"""
        write(self.repo / "scripts/lint-wiki.py", "print('wiki lint：STUB 2 项')\nraise SystemExit(1)\n")
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("wiki lint：STUB 2 项", proc.stdout)
        self.assertEqual(committed_files(self.repo), ["wiki/index.md"])

    def test_no_lint_script_is_fine(self) -> None:
        """没有 lint 脚本（夹具默认）照常提交，不报错。"""
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("lint", proc.stdout.lower().replace("lint-wiki", ""))


class SyncOwnPathsTest(RepoFixture):
    """默认只提交传入的路径：别的会话在同一目录里的在途改动不带走，只列出提醒。"""

    def seed(self) -> None:
        super().seed()
        write(self.repo / "wiki/projects/foo/a.md", "# a\n")

    def test_only_listed_paths_are_committed(self) -> None:
        write(self.repo / "wiki/index.md", "# index v2\n")                 # 本会话
        write(self.repo / "wiki/别的会话的页.md", "# 别的会话没写完的页\n")   # 他人在途（未跟踪，中文文件名）
        write(self.repo / "inputs/manual/m.md", "# m 被别的会话改了一半\n")  # 他人在途（已跟踪）
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["wiki/index.md"])
        self.assertEqual(porcelain(self.repo), {"wiki/别的会话的页.md": "??", "inputs/manual/m.md": " M"})
        self.assertIn("wiki/别的会话的页.md", proc.stdout, "没带走的在途改动应按原样路径列出，才能补传给 sync.sh")
        self.assertIn("inputs/manual/m.md", proc.stdout)

    def test_no_paths_with_pending_changes_is_refused_and_lists_them(self) -> None:
        write(self.repo / "wiki/index.md", "# index v2\n")
        write(self.repo / "wiki/new.md", "# new\n")
        proc = self.run_sync("测试主题")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("wiki/index.md", proc.stdout)
        self.assertIn("wiki/new.md", proc.stdout)
        self.assertIn("--all", proc.stdout, "应提示两种用法：传路径，或 --all")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)
        self.assertEqual(porcelain(self.repo), {"wiki/index.md": " M", "wiki/new.md": "??"}, "拒绝时不得暂存任何东西")

    def test_no_paths_and_clean_tree_says_nothing_to_commit(self) -> None:
        proc = self.run_sync("测试主题")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("无变更", proc.stdout)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)

    def test_directory_path_commits_everything_under_it(self) -> None:
        write(self.repo / "wiki/projects/foo/a.md", "# a v2\n")
        write(self.repo / "wiki/projects/foo/b.md", "# b\n")
        write(self.repo / "wiki/index.md", "# index 他人在途\n")
        proc = self.run_sync("测试主题", "wiki/projects/foo/")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["wiki/projects/foo/a.md", "wiki/projects/foo/b.md"])
        self.assertEqual(porcelain(self.repo), {"wiki/index.md": " M"})

    def test_deleted_tracked_path_can_be_committed(self) -> None:
        """本轮删除（或改名）的旧路径已不在磁盘上，但它是已跟踪文件，照样可以传入。"""
        (self.repo / "wiki/projects/foo/a.md").unlink()
        write(self.repo / "wiki/projects/foo/renamed.md", "# a\n")
        proc = self.run_sync("测试主题", "wiki/projects/foo/a.md", "wiki/projects/foo/renamed.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["wiki/projects/foo/a.md", "wiki/projects/foo/renamed.md"])
        self.assertNotIn("wiki/projects/foo/a.md", git(self.repo, "ls-files"))
        self.assertEqual(porcelain(self.repo), {})

    def test_missing_untracked_path_is_refused(self) -> None:
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "wiki/index.md", "wiki/nope.md")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("wiki/nope.md", proc.stdout + proc.stderr)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)

    def test_path_outside_whitelist_is_refused(self) -> None:
        write(self.repo / "scripts/x.sh", "echo 2\n")
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "scripts/x.sh")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("scripts/x.sh", proc.stdout + proc.stderr)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)


class SyncAllScopeTest(RepoFixture):
    """--all：提交默认范围（本会话通常自己写的目录）再加传入的路径；inputs/raw 与 outputs 仍须显式传入。"""

    def seed(self) -> None:
        write(self.repo / "wiki/index.md", "# index\n")
        write(self.repo / "inputs/manual/m.md", "# m\n")
        write(self.repo / "inputs/raw/chats/2026-09/index.json", '{"v": 1}')
        write(self.repo / "state/reporting/w.json", '{"v": 1}')
        write(self.repo / "outputs/README.md", "成稿目录\n")   # outputs 本身已跟踪，未跟踪的是其下的新成稿目录（与真实实例一致）

    def dirty_everything(self) -> None:
        """模拟本会话写了 wiki / manual / state，另一个会话在途采集与成稿。"""
        write(self.repo / "wiki/index.md", "# index v2\n")
        write(self.repo / "inputs/manual/m.md", "# m v2\n")
        write(self.repo / "state/reporting/w.json", '{"v": 2}')
        write(self.repo / "inputs/raw/chats/2026-09/index.json", '{"v": 2}')          # 他人在途采集（已跟踪）
        write(self.repo / "outputs/2026-09-24-x/a.md", "草稿\n")                       # 他人在途成稿（未跟踪）

    def test_default_scope_leaves_raw_and_outputs_and_reports_them(self) -> None:
        self.dirty_everything()
        proc = self.run_sync("--all", "测试主题")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["inputs/manual/m.md", "state/reporting/w.json", "wiki/index.md"])
        self.assertIn("inputs/raw/chats/2026-09/index.json", proc.stdout)
        self.assertIn("outputs/2026-09-24-x/", proc.stdout)
        self.assertIn("传路径", proc.stdout)
        st = porcelain(self.repo)
        self.assertEqual(st.get("inputs/raw/chats/2026-09/index.json"), " M")
        self.assertEqual(st.get("outputs/2026-09-24-x/"), "??")

    def test_explicit_paths_are_added_to_default_scope(self) -> None:
        self.dirty_everything()
        proc = self.run_sync("--all", "测试主题", "outputs/2026-09-24-x", "inputs/raw/chats/2026-09")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), [
            "inputs/manual/m.md", "inputs/raw/chats/2026-09/index.json", "outputs/2026-09-24-x/a.md",
            "state/reporting/w.json", "wiki/index.md",
        ])
        self.assertEqual(porcelain(self.repo), {})

    def test_no_default_change_but_raw_dirty_says_nothing_to_commit(self) -> None:
        write(self.repo / "inputs/raw/chats/2026-09/index.json", '{"v": 2}')
        proc = self.run_sync("--all", "测试主题")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("无变更", proc.stdout)
        self.assertIn("inputs/raw/chats/2026-09/index.json", proc.stdout)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)


class SyncLockTest(RepoFixture):
    """仓库级锁：同一仓库的收口排队执行；拿不到锁超时退出、不动仓库、不破别人的锁；自己的锁退出时清掉。"""

    def lock_dir(self) -> Path:
        return self.repo / ".git" / "llm-wiki-sync.lock"

    def env(self, timeout: int) -> dict[str, str]:
        return {**UTF8_ENV, "LLM_WIKI_SYNC_LOCK_TIMEOUT": str(timeout)}

    def test_times_out_when_lock_is_held_and_leaves_it_alone(self) -> None:
        self.lock_dir().mkdir()
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "wiki/index.md", env=self.env(1))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("llm-wiki-sync.lock", proc.stdout + proc.stderr)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)
        self.assertEqual(porcelain(self.repo), {"wiki/index.md": " M"}, "拿不到锁时不得暂存任何东西")
        self.assertTrue(self.lock_dir().is_dir(), "别人的锁不能被超时的一方删掉")

    def test_waits_then_proceeds_once_lock_is_released(self) -> None:
        self.lock_dir().mkdir()
        write(self.repo / "wiki/index.md", "# index v2\n")
        timer = threading.Timer(1.5, self.lock_dir().rmdir)
        timer.start()
        try:
            proc = self.run_sync("测试主题", "wiki/index.md", env=self.env(20))
        finally:
            timer.cancel()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("等待", proc.stdout)
        self.assertEqual(committed_files(self.repo), ["wiki/index.md"])

    def test_lock_is_removed_after_success(self) -> None:
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(self.lock_dir().exists())

    def test_lock_is_removed_after_failure(self) -> None:
        """拿到锁之后出错退出（这里让 pull 失败），锁同样要清掉，否则下一个会话会被卡住。"""
        git(self.repo, "remote", "add", "origin", str(self.repo.parent / "no-such-remote"))
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.lock_dir().exists())


class SyncBuildIndexTest(RepoFixture):
    """仓里有 build-index.py 时，收口按已提交与本次提交的页面重新生成索引，生成的文件随本次提交。"""

    def seed(self) -> None:
        shutil.copy(BUILD_INDEX, self.repo / "scripts" / "build-index.py")
        write(self.repo / "wiki/index.md", "# Wiki\n\n| [concepts/](concepts/README.md) | 概念 |\n")
        write(self.repo / "wiki/concepts/README.md", "# concepts/\n\n分区说明。\n")
        write(self.repo / "wiki/concepts/old.md", "# 已有的页\n")

    def test_generated_index_is_committed_without_others_untracked_pages(self) -> None:
        write(self.repo / "wiki/concepts/mine.md", "# 本会话的新页\n")
        write(self.repo / "wiki/concepts/others.md", "# 别的会话没写完的页\n")
        proc = self.run_sync("测试主题", "wiki/concepts/mine.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(
            committed_files(self.repo), ["wiki/concepts/index.md", "wiki/concepts/mine.md", "wiki/index.md"]
        )
        index = git(self.repo, "show", "HEAD:wiki/concepts/index.md")
        self.assertIn("- [已有的页](old.md)", index)
        self.assertIn("- [本会话的新页](mine.md)", index)
        self.assertNotIn("others.md", index)
        self.assertIn("(concepts/index.md)", git(self.repo, "show", "HEAD:wiki/index.md"))
        self.assertEqual(porcelain(self.repo), {"wiki/concepts/others.md": "??"})

    def test_all_scope_also_regenerates_index(self) -> None:
        write(self.repo / "wiki/concepts/mine.md", "# 本会话的新页\n")
        proc = self.run_sync("--all", "测试主题")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("- [本会话的新页](mine.md)", git(self.repo, "show", "HEAD:wiki/concepts/index.md"))
        self.assertEqual(porcelain(self.repo), {})

    def test_index_generated_before_sync_is_still_committed(self) -> None:
        """Agent 按流程先跑 build-index.py（让 lint 通过）再收口：磁盘上的索引此时已是最新，仍要随本次提交带上，
        根索引的入口归一也一样。"""
        write(self.repo / "wiki/concepts/mine.md", "# 本会话的新页\n")
        subprocess.run([sys.executable, "scripts/build-index.py"], cwd=self.repo, check=True, capture_output=True)
        proc = self.run_sync("测试主题", "wiki/concepts/mine.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(
            committed_files(self.repo), ["wiki/concepts/index.md", "wiki/concepts/mine.md", "wiki/index.md"]
        )
        self.assertEqual(porcelain(self.repo), {})

    def test_root_index_with_other_edits_is_not_swept(self) -> None:
        """根索引里除了入口归一还有别的手工改动（可能是别的会话的）时，不替人提交，只列在在途清单里。"""
        write(self.repo / "wiki/concepts/mine.md", "# 本会话的新页\n")
        root_index = self.repo / "wiki/index.md"
        root_index.write_text(root_index.read_text(encoding="utf-8") + "\n别的会话加的一行\n", encoding="utf-8")
        proc = self.run_sync("测试主题", "wiki/concepts/mine.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["wiki/concepts/index.md", "wiki/concepts/mine.md"])
        self.assertEqual(porcelain(self.repo), {"wiki/index.md": " M"})
        self.assertIn("wiki/index.md", proc.stdout)

    def test_index_only_change_is_not_committed_alone(self) -> None:
        """没有自己的改动时不为生成索引单独造一个提交。"""
        proc = self.run_sync("测试主题")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("无变更", proc.stdout)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)


class SyncRemoteTest(RepoFixture):
    """有 origin 时：远端没有新提交就直接推送，工作区里别的会话的在途改动不挡路；远端有新提交才 rebase，
    rebase 被在途改动挡住时停下，本地提交与在途改动都不丢。"""

    def setUp(self) -> None:
        super().setUp()
        self.origin = self.repo.parent / "origin.git"
        git(self.repo.parent, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(self.repo, "remote", "add", "origin", str(self.origin))
        git(self.repo, "push", "-q", "origin", "main")

    def remote_head(self) -> str:
        return git(self.origin, "rev-parse", "main")

    def push_from_another_machine(self) -> str:
        """模拟另一台机器向远端推了一个提交，返回它的 sha。"""
        other = self.repo.parent / "other"
        git(self.repo.parent, "clone", "-q", str(self.origin), str(other))
        git(other, "config", "user.name", "other")
        git(other, "config", "user.email", "other@example.com")
        write(other / "wiki/from-other-machine.md", "# 另一台机器写的页\n")
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "ingest: 另一台机器")
        git(other, "push", "-q", "origin", "main")
        return git(other, "rev-parse", "HEAD")

    def test_pushes_even_when_others_changes_are_left_unstaged(self) -> None:
        write(self.repo / "wiki/index.md", "# index v2\n")                  # 本会话
        write(self.repo / "inputs/manual/m.md", "# m 被别的会话改了一半\n")   # 他人在途
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["wiki/index.md"])
        self.assertEqual(self.remote_head(), git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(porcelain(self.repo), {"inputs/manual/m.md": " M"})

    def test_rebases_onto_new_remote_commits_when_tree_is_clean(self) -> None:
        remote_sha = self.push_from_another_machine()
        write(self.repo / "wiki/index.md", "# index v2\n")
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD~1"), remote_sha, "本地提交应接在远端的新提交之后")
        self.assertEqual(self.remote_head(), git(self.repo, "rev-parse", "HEAD"))

    def test_remote_ahead_and_dirty_tree_stops_without_losing_anything(self) -> None:
        remote_sha = self.push_from_another_machine()
        write(self.repo / "wiki/index.md", "# index v2\n")
        write(self.repo / "inputs/manual/m.md", "# m 被别的会话改了一半\n")
        proc = self.run_sync("测试主题", "wiki/index.md")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("在途改动", proc.stdout + proc.stderr)
        self.assertEqual(committed_files(self.repo), ["wiki/index.md"], "本地提交应已完成并保留")
        self.assertEqual((self.repo / "inputs/manual/m.md").read_text(encoding="utf-8"), "# m 被别的会话改了一半\n")
        self.assertEqual(porcelain(self.repo), {"inputs/manual/m.md": " M"})
        self.assertEqual(self.remote_head(), remote_sha, "没推上去，远端不变")


if __name__ == "__main__":
    unittest.main()
