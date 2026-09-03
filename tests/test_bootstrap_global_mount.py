#!/usr/bin/env python3
"""bootstrap.sh 全局挂载的离线回归测试：四个 skill 必须同时出现在三处发现根。

背景：早期全局模式只链 `~/.claude/skills` 与 `~/.codex/skills`，而本机多数编码 Agent
（dsh、Cline、Dexto、Kimi、Loaf、Warp、Zed 等）只读约定俗成的 canonical 根
`~/.agents/skills`，Claude/Codex 之外的工具因此发现不到本工作台的 skill。
测试在临时仓库里以 --mode global 跑真实脚本，HOME 指向临时目录，不触碰用户主目录。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.sh"
SKILLS = ("llm-wiki-ingest", "llm-wiki-query", "llm-wiki-lint", "llm-wiki-learn")
# 全局模式下必须挂载的三个发现根（相对 HOME）
MOUNT_ROOTS = (".agents/skills", ".claude/skills", ".codex/skills")


class BootstrapGlobalMountTest(unittest.TestCase):
    """全局形态：发现链就位，且三处发现根各自软链到仓内 canonical。"""

    def setUp(self) -> None:
        """临时 git 仓库：复制 bootstrap.sh，并造出四个 skill 的 canonical 目录。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name).resolve()
        self.home = base / "home"
        self.home.mkdir()
        self.repo = base / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        shutil.copy(BOOTSTRAP, self.repo / "scripts" / "bootstrap.sh")
        (self.repo / "AGENTS.md").write_text("# 临时实例\n", encoding="utf-8")
        for name in SKILLS:
            skill_dir = self.repo / ".agents" / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

    def tearDown(self) -> None:
        """释放临时目录。"""
        self.temp_dir.cleanup()

    def run_bootstrap(self) -> subprocess.CompletedProcess:
        """在伪 HOME 下跑一次 bootstrap --mode global。"""
        env = {**os.environ, "HOME": str(self.home)}
        proc = subprocess.run(
            ["bash", "scripts/bootstrap.sh", "--mode", "global"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def test_global_mounts_cover_three_discovery_roots(self) -> None:
        """~/.agents、~/.claude、~/.codex 三处 skills 根下各有四条链，且解析到仓内 canonical。"""
        proc = self.run_bootstrap()
        self.assertTrue((self.home / ".llm-wiki").is_symlink(), proc.stdout)
        for mount in MOUNT_ROOTS:
            for name in SKILLS:
                link = self.home / mount / name
                with self.subTest(mount=mount, skill=name):
                    self.assertTrue(link.is_symlink(), f"{link} 应是软链\n{proc.stdout}")
                    # 经 ~/.llm-wiki 发现链解析，最终必须落到仓内 canonical
                    self.assertEqual(
                        link.resolve(),
                        (self.repo / ".agents" / "skills" / name).resolve(),
                        f"{link} 应指向仓内 canonical\n{proc.stdout}",
                    )

    def test_rerun_is_idempotent(self) -> None:
        """重跑不报错、不改写已就位的链（幂等）。"""
        self.run_bootstrap()
        before = {
            (mount, name): os.readlink(self.home / mount / name)
            for mount in MOUNT_ROOTS
            for name in SKILLS
        }
        self.run_bootstrap()
        after = {
            (mount, name): os.readlink(self.home / mount / name)
            for mount in MOUNT_ROOTS
            for name in SKILLS
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
