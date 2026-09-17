#!/usr/bin/env python3
"""bootstrap.sh 去掉实例 main 上游跟踪的离线回归测试。

背景：`git clone <模板仓URL>` 让 main 跟踪 origin/main，部署时 `git remote rename origin upstream` 又把跟踪带到
upstream/main。git status 与 IDE 因此显示「领先 N、可推送」，IDE 的同步 / 发布按钮或裸 `git push` 会把个人内容
快进推上模板仓。推个人仓由 sync.sh 显式指定 origin、发布模板走 release.sh，都不依赖跟踪，所以实例 main 一律不跟踪远端。
测试在临时仓库里以 --mode project 跑真实脚本，HOME 指向临时目录，远端是临时裸仓，不触碰用户主目录与网络。
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


class BootstrapMainNoUpstreamTest(unittest.TestCase):
    """实例 main 不跟踪远端：安装后与每次升级后重跑 bootstrap 都会去掉跟踪，远端本身保留。"""

    def setUp(self) -> None:
        """临时实例仓库（复制 bootstrap.sh、提交一次）与一个充当远端的临时裸仓。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name).resolve()
        self.home = base / "home"
        self.home.mkdir()
        # bootstrap 会调用 agent-memory-setup 的 setup.sh：伪 HOME 下放一个空桩，避免联网安装
        stub = self.home / ".agents" / "skills" / "agent-memory-setup" / "setup.sh"
        stub.parent.mkdir(parents=True)
        stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)
        self.remote = base / "template.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.repo = base / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        shutil.copy(BOOTSTRAP, self.repo / "scripts" / "bootstrap.sh")
        (self.repo / "AGENTS.md").write_text("# 临时实例\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "init")

    def tearDown(self) -> None:
        """释放临时目录。"""
        self.temp_dir.cleanup()

    def git(self, *args: str) -> str:
        """在临时实例仓库里执行 git，失败即抛出，返回标准输出。"""
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=True,
        ).stdout

    def track(self, remote_name: str) -> None:
        """添加远端并 push -u，使 main 跟踪 <远端>/main——与 clone 或 remote rename 之后的状态一致。"""
        self.git("remote", "add", remote_name, str(self.remote))
        self.git("push", "-q", "-u", remote_name, "main")

    def main_upstream(self) -> str:
        """main 当前跟踪的远端分支；未跟踪返回空串。"""
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "main@{upstream}"],
            cwd=self.repo, capture_output=True, text=True, check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    def run_bootstrap(self) -> subprocess.CompletedProcess:
        """在伪 HOME 下跑一次 bootstrap --mode project，要求退出码为 0。"""
        env = {**os.environ, "HOME": str(self.home)}
        proc = subprocess.run(
            ["bash", "scripts/bootstrap.sh", "--mode", "project"],
            cwd=self.repo, capture_output=True, text=True, env=env, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def test_tracking_of_template_remote_is_removed(self) -> None:
        """部署时把 origin 改名为 upstream 的实例：main 跟踪 upstream/main，跑完 bootstrap 不再跟踪，upstream 远端保留。"""
        self.track("upstream")
        self.assertEqual(self.main_upstream(), "upstream/main")   # 前置条件：确实在跟踪
        proc = self.run_bootstrap()
        self.assertEqual(self.main_upstream(), "", proc.stdout)
        self.assertIn("upstream", self.git("remote").split(), "只去掉跟踪，不删远端")
        self.assertIn("upstream/main", proc.stdout, "输出要点名去掉了哪个跟踪")

    def test_tracking_of_clone_origin_is_removed(self) -> None:
        """按旧命令 clone 的实例：main 跟踪 origin/main，同样去掉——不猜 origin 是模板仓还是个人仓。"""
        self.track("origin")
        self.assertEqual(self.main_upstream(), "origin/main")
        self.run_bootstrap()
        self.assertEqual(self.main_upstream(), "")
        self.assertIn("origin", self.git("remote").split())

    def test_rerun_without_tracking_is_noop(self) -> None:
        """已不跟踪时重跑：退出码 0，仍不跟踪，git 配置不变（幂等）。"""
        self.track("upstream")
        self.run_bootstrap()
        before = self.git("config", "--local", "--list")
        self.run_bootstrap()
        self.assertEqual(self.main_upstream(), "")
        self.assertEqual(before, self.git("config", "--local", "--list"))


if __name__ == "__main__":
    unittest.main()
