#!/usr/bin/env python3
"""sync.sh 的提交守卫：按路径提交、合并进行中拒绝、不在 main 拒绝、排除项对提交同样生效。

在临时仓库里复制并实跑真实的 scripts/sync.sh（无 origin、无 template 分支，走「仅本地提交」分支）。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "sync.sh"
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
    """把 git status --porcelain 解析成 {路径: 两字符状态码}，不受首列空格被 strip 掉影响。"""
    out = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout
    return {line[3:]: line[:2] for line in out.splitlines() if line}


def committed_files(repo: Path) -> list[str]:
    """HEAD 提交涉及的文件清单。"""
    out = git(repo, "show", "--name-only", "--format=", "HEAD")
    return sorted(line for line in out.splitlines() if line)


class SyncGuardsTest(unittest.TestCase):
    def setUp(self) -> None:
        """临时仓库：复制 sync.sh；初始提交含内容目录文件、采集快照与一个骨架脚本。"""
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve() / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy(SYNC, self.repo / "scripts" / "sync.sh")
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "test")
        git(self.repo, "config", "user.email", "test@example.com")
        write(self.repo / "wiki/index.md", "# index\n")
        write(self.repo / "inputs/manual/m.md", "# m\n")
        write(self.repo / "inputs/raw/source-a/s.json", '{"v": 1}')
        write(self.repo / "scripts/x.sh", "echo 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "init")
        self.init_sha = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def set_excludes(self, entries: str) -> None:
        """把临时仓库里 sync.sh 的 CONTENT_EXCLUDES 整行换成给定内容；实例已登记排除项时同样适用。"""
        script = self.repo / "scripts/sync.sh"
        text = script.read_text(encoding="utf-8")
        new_text, n = re.subn(r"^CONTENT_EXCLUDES=\(.*\)\s*$", f"CONTENT_EXCLUDES=({entries})", text, flags=re.M)
        self.assertEqual(n, 1, "sync.sh 应有且只有一行 CONTENT_EXCLUDES=(…) 供实例登记排除项")
        script.write_text(new_text, encoding="utf-8")

    def run_sync(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "scripts/sync.sh", "测试主题"], cwd=self.repo, capture_output=True, text=True, env=UTF8_ENV
        )

    def test_prestaged_skeleton_change_not_swept_into_commit(self) -> None:
        """白名单外的已暂存改动不随 ingest 提交，提交后仍留在暂存区。"""
        write(self.repo / "scripts/x.sh", "echo 2\n")
        git(self.repo, "add", "scripts/x.sh")
        write(self.repo / "wiki/index.md", "# index v2\n")
        write(self.repo / "wiki/new.md", "# new\n")
        proc = self.run_sync()
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
                    proc = self.run_sync()
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
        proc = self.run_sync()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("main", proc.stdout + proc.stderr)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)

    def test_exclude_entries_apply_to_commit_too(self) -> None:
        """实例在 CONTENT_EXCLUDES 里登记的排除项，对暂存、判空和提交同时生效。"""
        self.set_excludes("':(exclude)inputs/raw/source-a'")
        write(self.repo / "inputs/raw/source-a/s.json", '{"v": 2}')
        write(self.repo / "inputs/manual/m.md", "# m v2\n")
        proc = self.run_sync()
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
        proc = self.run_sync()
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("无变更", proc.stdout)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.init_sha)


if __name__ == "__main__":
    unittest.main()
