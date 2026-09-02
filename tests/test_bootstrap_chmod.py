#!/usr/bin/env python3
"""bootstrap.sh 执行位规则的离线回归测试：只给带 shebang 的脚本加执行位。

背景：早期 bootstrap 对 scripts/*.sh scripts/*.py 一律 chmod +x，实例里以 644 入库的
纯模块文件每跑一次就被翻成 755，根工作区随之出现模式变更。规则收窄为「首行是 #! 的
文件才加执行位」，模块文件保持原样。测试在临时仓库里以 --mode project 跑真实脚本，
HOME 指向临时目录，不触碰用户主目录。
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.sh"


class BootstrapChmodTest(unittest.TestCase):
    """带 shebang 的脚本获得执行位，纯模块文件不动，hooks/ 下的钩子同样处理。"""

    def setUp(self) -> None:
        """临时 git 仓库：复制 bootstrap.sh，放入带 / 不带 shebang 的样例文件（全部 644）。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name).resolve()
        self.home = base / "home"
        self.home.mkdir()
        self.repo = base / "repo"
        (self.repo / "scripts" / "hooks").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        shutil.copy(BOOTSTRAP, self.repo / "scripts" / "bootstrap.sh")
        self.samples = {
            "scripts/cli.py": "#!/usr/bin/env python3\nprint('cli')\n",
            "scripts/run.sh": "#!/usr/bin/env bash\necho run\n",
            "scripts/hooks/post-checkout": "#!/usr/bin/env bash\nexit 0\n",
            "scripts/lib.py": '"""纯模块，没有 shebang。"""\nX = 1\n',
            "scripts/data.sh": "# 只被 source 的片段，没有 shebang\nFOO=1\n",
        }
        for rel, text in self.samples.items():
            path = self.repo / rel
            path.write_text(text, encoding="utf-8")
            path.chmod(0o644)

    def tearDown(self) -> None:
        """释放临时目录。"""
        self.temp_dir.cleanup()

    @staticmethod
    def executable(path: Path) -> bool:
        """文件是否带任一执行位。"""
        return bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))

    def test_only_shebang_files_get_exec_bit(self) -> None:
        """跑一次 bootstrap --mode project：带 shebang 的三个文件变为可执行，两个无 shebang 文件保持 644。"""
        env = {**os.environ, "HOME": str(self.home)}
        proc = subprocess.run(
            ["bash", "scripts/bootstrap.sh", "--mode", "project"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for rel in ("scripts/cli.py", "scripts/run.sh", "scripts/hooks/post-checkout"):
            with self.subTest(path=rel):
                self.assertTrue(self.executable(self.repo / rel), f"{rel} 带 shebang，应获得执行位\n{proc.stdout}")
        for rel in ("scripts/lib.py", "scripts/data.sh"):
            with self.subTest(path=rel):
                self.assertFalse(self.executable(self.repo / rel), f"{rel} 无 shebang，不应被加执行位\n{proc.stdout}")
        # 专项模式不建全局发现链（macOS 的 python 会在 HOME 下建 Library/ 缓存，故不断言目录全空）
        self.assertFalse((self.home / ".llm-wiki").exists())


if __name__ == "__main__":
    unittest.main()
