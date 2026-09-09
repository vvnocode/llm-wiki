#!/usr/bin/env python3
"""bootstrap.sh 委托 agent-memory-setup 接线的离线回归测试。

背景：bootstrap 调用规则仓 `vvnocode/AGENTS.md` 中的 `agent-memory-setup`，完成多工具入口、仓内记忆和 worktree 钩子。
bootstrap 只负责找到它并以仓根为参数调用：环境变量 `AGENT_MEMORY_SETUP` 显式指定 →
`~/.agents/skills` → `~/.claude/skills` → `~/.codex/skills`；都没有时用
`AGENT_MEMORY_SETUP_INSTALLER`（缺省为 skills 仓的一行 curl 安装命令）装好再找一次；
仍找不到只告警、其余步骤照做。

测试在临时仓库里跑真实 bootstrap.sh，HOME 指向临时目录，不触碰用户主目录、不联网：
setup.sh 用桩脚本替代，只记录被调用时的参数。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.sh"
SKILL_REL = Path("agent-memory-setup") / "setup.sh"
# 本机真实安装的 setup.sh（有则跑一条真实契约测试，没有则跳过）
REAL_SETUP = Path.home() / ".agents" / "skills" / SKILL_REL


class BootstrapMemorySetupTest(unittest.TestCase):
    """bootstrap 找到 setup.sh 并以仓根调用；自己不再写入口与记忆配置。"""

    def setUp(self) -> None:
        """临时 git 仓库：复制 bootstrap.sh，放一个 AGENTS.md；伪 HOME 初始为空。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name).resolve()
        self.home = base / "home"
        self.home.mkdir()
        self.repo = base / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        shutil.copy(BOOTSTRAP, self.repo / "scripts" / "bootstrap.sh")
        (self.repo / "AGENTS.md").write_text("# 临时实例\n", encoding="utf-8")
        # 桩脚本把收到的参数逐行写到这里
        self.call_log = base / "setup-calls.txt"

    def tearDown(self) -> None:
        """释放临时目录。"""
        self.temp_dir.cleanup()

    def write_stub(self, path: Path) -> Path:
        """在 path 写一个 setup.sh 桩：记录参数，不改仓库。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$@\" >> '{self.call_log}'\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def run_bootstrap(self, **env_extra: str) -> subprocess.CompletedProcess:
        """以伪 HOME 跑 bootstrap --mode project，必须成功退出。"""
        env = {**os.environ, "HOME": str(self.home)}
        env.pop("AGENT_MEMORY_SETUP", None)
        env.pop("AGENT_MEMORY_SETUP_INSTALLER", None)
        env.update(env_extra)
        proc = subprocess.run(
            ["bash", "scripts/bootstrap.sh", "--mode", "project"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def calls(self) -> list[str]:
        """桩脚本记录到的参数行。"""
        if not self.call_log.exists():
            return []
        return self.call_log.read_text(encoding="utf-8").splitlines()

    def assert_bootstrap_left_wiring_to_skill(self) -> None:
        """bootstrap 自己不再写这三样：CLAUDE.md、settings.local.json、.codex/config.toml。"""
        self.assertFalse((self.repo / "CLAUDE.md").exists(), "bootstrap 不应再自己建 CLAUDE.md")
        self.assertFalse((self.repo / ".claude" / "settings.local.json").exists(), "记忆路径应由 setup.sh 写")
        self.assertFalse((self.repo / ".codex" / "config.toml").exists(), "Codex 记忆开关应由 setup.sh 写")

    def test_uses_skill_under_agents_root(self) -> None:
        """~/.agents/skills 下装好的 setup.sh 被以仓根为参数调用。"""
        self.write_stub(self.home / ".agents" / "skills" / SKILL_REL)
        self.run_bootstrap()
        self.assertEqual(self.calls(), [str(self.repo)])
        self.assert_bootstrap_left_wiring_to_skill()

    def test_env_override_wins(self) -> None:
        """AGENT_MEMORY_SETUP 指定的脚本优先于发现根。"""
        self.write_stub(self.home / ".agents" / "skills" / SKILL_REL)
        other_log = self.call_log.with_name("other-calls.txt")
        other = self.home / "elsewhere" / "setup.sh"
        other.parent.mkdir(parents=True)
        other.write_text(
            "#!/usr/bin/env bash\n" f"printf '%s\\n' \"$@\" >> '{other_log}'\n",
            encoding="utf-8",
        )
        other.chmod(0o755)
        self.run_bootstrap(AGENT_MEMORY_SETUP=str(other))
        self.assertEqual(other_log.read_text(encoding="utf-8").splitlines(), [str(self.repo)])
        self.assertEqual(self.calls(), [], "发现根下的脚本不应再被调用")

    def test_falls_back_to_claude_root(self) -> None:
        """~/.agents/skills 没有时退到 ~/.claude/skills。"""
        self.write_stub(self.home / ".claude" / "skills" / SKILL_REL)
        self.run_bootstrap()
        self.assertEqual(self.calls(), [str(self.repo)])

    def test_installs_skill_when_missing(self) -> None:
        """三处发现根都没有：先跑安装命令，再找一次并调用。"""
        installer_log = self.call_log.with_name("installer-calls.txt")
        stub_target = self.home / ".agents" / "skills" / SKILL_REL
        # 安装命令写成脚本文件：记一笔，然后把桩脚本放到 canonical 发现根（避免命令串里多层引号）
        installer_script = self.call_log.with_name("installer.sh")
        installer_script.write_text(
            "#!/usr/bin/env bash\n"
            f"echo ran >> '{installer_log}'\n"
            f"mkdir -p '{stub_target.parent}'\n"
            f"cat > '{stub_target}' <<'STUB'\n"
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$@\" >> '{self.call_log}'\n"
            "STUB\n"
            f"chmod +x '{stub_target}'\n",
            encoding="utf-8",
        )
        installer = f"bash '{installer_script}'"
        proc = self.run_bootstrap(AGENT_MEMORY_SETUP_INSTALLER=installer)
        self.assertEqual(installer_log.read_text(encoding="utf-8").splitlines(), ["ran"], proc.stdout)
        self.assertEqual(self.calls(), [str(self.repo)], proc.stdout)

    def test_warns_and_continues_when_unavailable(self) -> None:
        """装不上（离线）：退出码仍为 0，打印告警与手工命令，其余步骤照做（钩子仍安装）。"""
        proc = self.run_bootstrap(AGENT_MEMORY_SETUP_INSTALLER="false")
        self.assertIn("⚠", proc.stdout)
        self.assertIn("agent-memory-setup", proc.stdout)
        self.assertIn("setup.sh", proc.stdout)
        self.assertEqual(self.calls(), [])

    def test_rerun_is_idempotent(self) -> None:
        """重跑仍只调一次 setup.sh（每次 bootstrap 一次），且不报错。"""
        self.write_stub(self.home / ".agents" / "skills" / SKILL_REL)
        self.run_bootstrap()
        self.run_bootstrap()
        self.assertEqual(self.calls(), [str(self.repo), str(self.repo)])

    @unittest.skipUnless(REAL_SETUP.is_file(), "本机未安装 agent-memory-setup，跳过真实契约测试")
    def test_real_setup_script_contract(self) -> None:
        """用本机真实 setup.sh 跑一遍：入口、记忆路径、Codex 开关、记忆索引四样到位。"""
        proc = self.run_bootstrap(AGENT_MEMORY_SETUP=str(REAL_SETUP))
        self.assertEqual((self.repo / "CLAUDE.md").read_text(encoding="utf-8"), "@AGENTS.md\n", proc.stdout)
        settings = json.loads((self.repo / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["autoMemoryDirectory"], f"{self.repo}/.memory")
        toml = (self.repo / ".codex" / "config.toml").read_text(encoding="utf-8")
        for key in ("generate_memories", "use_memories", "dedicated_tools"):
            self.assertRegex(toml, rf"(?m)^{key} *= *false")
        self.assertTrue((self.repo / ".memory" / "MEMORY.md").is_file())
        self.assertIn(".claude/settings.local.json", (self.repo / ".gitignore").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
