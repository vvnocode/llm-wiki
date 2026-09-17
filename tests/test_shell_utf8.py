#!/usr/bin/env python3
"""shell 脚本在 UTF-8 语言环境下的回归测试（v0.3.6）。

背景：macOS 自带 bash 3.2.57 在 UTF-8 语言环境下解析 "$NAME（" 这类写法时，会把紧跟的多字节字符的首字节并入变量名：
开了 set -u 的脚本报「NAME�: unbound variable」退出，没开的展开为空并残留乱码。v0.3.5 发布时 release-check.sh
第 39 行在 Terminal.app 中因此失败。Agent 派生的子进程常不设 LANG，C 语言环境下不触发，所以本文件的用例一律显式设
LC_ALL=en_US.UTF-8 运行真实脚本；另有静态契约逐行扫描全部 bash 脚本，堵住没有用例覆盖的分支。
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
SCRIPTS = ROOT / "scripts"
# 运行脚本的环境：UTF-8 语言环境才会走到 bash 3.2 的多字节解析路径
UTF8_ENV = {**os.environ, "LC_ALL": "en_US.UTF-8"}
# $NAME（不是 ${NAME}）后紧跟一个非 ASCII 字符
BARE_VAR_BEFORE_MULTIBYTE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)(?=[^\x00-\x7f])")
# heredoc 起始：分组 1～3 为带引号或反斜杠的结束标记（正文不展开变量），分组 4 为不带引号的结束标记
HEREDOC_START = re.compile(r"<<-?\s*(?:'(\w+)'|\"(\w+)\"|\\(\w+)|(\w+))")


def shell_scripts() -> list[Path]:
    """仓内全部 bash 脚本：scripts 下的 .sh，以及 scripts/hooks 下的钩子。"""
    files = sorted(SCRIPTS.rglob("*.sh"))
    hooks = SCRIPTS / "hooks"
    if hooks.is_dir():
        files += sorted(p for p in hooks.iterdir() if p.is_file())
    return files


def bare_vars_before_multibyte(text: str) -> list[tuple[int, str]]:
    """返回 (行号, 变量名)：会被展开的行里，$NAME 后紧跟非 ASCII 字符的位置。

    跳过注释行与带引号 heredoc 的正文（不展开变量）；不带引号的 heredoc 正文会展开，照常检查。
    """
    hits: list[tuple[int, str]] = []
    quoted_end: str | None = None          # 正处于带引号 heredoc 正文时，记录其结束标记
    for no, line in enumerate(text.splitlines(), 1):
        if quoted_end is not None:
            if line.strip() == quoted_end:
                quoted_end = None
            continue
        if line.lstrip().startswith("#"):
            continue
        hits += [(no, m.group(1)) for m in BARE_VAR_BEFORE_MULTIBYTE.finditer(line)]
        start = HEREDOC_START.search(line)
        if start and not start.group(4):
            quoted_end = start.group(1) or start.group(2) or start.group(3)
    return hits


class ShellMultibyteContractTest(unittest.TestCase):
    """静态契约：bash 脚本里 $NAME 后不得紧跟非 ASCII 字符，一律写成 ${NAME}。"""

    def test_scanner_recognizes_the_pattern(self) -> None:
        """扫描器自检：命中裸变量接全角标点，放过花括号写法、注释行与带引号 heredoc 的正文。"""
        sample = "\n".join([
            'echo "未找到 $LIST（词表）"',      # 第 1 行：命中
            'echo "未找到 ${LIST}（词表）"',    # 第 2 行：花括号写法，放过
            "# 注释里的 $LIST（不执行）",        # 第 3 行：注释，放过
            "cat <<'EOF'",                      # 第 4 行：带引号 heredoc 开始
            "路由段里的 $WIKI（字面量）",         # 第 5 行：正文不展开，放过
            "EOF",                              # 第 6 行：heredoc 结束
            'echo "跳过 $r（未配置）"',          # 第 7 行：命中
        ])
        self.assertEqual(bare_vars_before_multibyte(sample), [(1, "LIST"), (7, "r")])

    def test_scripts_have_no_bare_var_before_multibyte(self) -> None:
        """逐个扫描全部 bash 脚本，命中即失败并列出位置。"""
        scripts = shell_scripts()
        # 防止扫描范围为空而空跑通过
        self.assertTrue({"bootstrap.sh", "release-check.sh", "release.sh", "pre-push"} <= {p.name for p in scripts})
        found = [
            f"{p.relative_to(ROOT)}:{no}: ${name}"
            for p in scripts
            for no, name in bare_vars_before_multibyte(p.read_text(encoding="utf-8"))
        ]
        self.assertEqual(
            found, [],
            "bash 3.2 在 UTF-8 下会把 $NAME 后紧跟的多字节字符首字节并入变量名，请改写为 ${NAME}：\n" + "\n".join(found),
        )


class ReleaseScriptsUtf8Test(unittest.TestCase):
    """发布工具在 UTF-8 语言环境下的真实行为：release-check.sh、release.sh 与维护者 pre-push 钩子。"""

    def setUp(self) -> None:
        """临时维护者仓：复制三份脚本，template 分支上有一次提交（含供词表命中的词 PLUGH）。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name).resolve() / "repo"
        (self.repo / "scripts" / "hooks").mkdir(parents=True)
        for rel in ("scripts/release-check.sh", "scripts/release.sh", "scripts/hooks/pre-push"):
            shutil.copy(ROOT / rel, self.repo / rel)       # copy 连同执行位一起复制
        (self.repo / "README.md").write_text("# 临时模板\n\n含词 PLUGH\n", encoding="utf-8")
        self.git("init", "-q", "-b", "template")
        self.commit("template: init")

    def tearDown(self) -> None:
        """释放临时目录。"""
        self.temp_dir.cleanup()

    def git(self, *args: str) -> str:
        """在临时仓里执行 git，失败即抛出，返回标准输出。"""
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True).stdout

    def commit(self, message: str) -> None:
        """暂存全部改动并提交。"""
        self.git("add", "-A")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", message)

    def run_script(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        """在 UTF-8 语言环境下用 bash 运行脚本；输出按 UTF-8 解码，残缺字节替换而不抛异常。"""
        return subprocess.run(
            ["bash", *args], cwd=self.repo, input=stdin, capture_output=True,
            encoding="utf-8", errors="replace", env=UTF8_ENV, check=False,
        )

    def test_release_check_without_word_list(self) -> None:
        """未建本地词表：提示行完整给出词表路径，扫描通过、退出码 0（v0.3.5 在此报 unbound variable 退出）。"""
        proc = self.run_script("scripts/release-check.sh", "template")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(".release-check-local（本地敏感词表", proc.stdout)

    def test_release_check_word_list_hit_names_the_word(self) -> None:
        """本地词表命中：告警行点名命中的词，退出码 1。"""
        (self.repo / ".release-check-local").write_text("PLUGH\n", encoding="utf-8")
        proc = self.run_script("scripts/release-check.sh", "template")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("本地词表命中「PLUGH」", proc.stdout)

    def test_release_skips_unconfigured_remote(self) -> None:
        """显式传入未配置的发布远端：先过 release-check，再提示「跳过 远端名（未配置）」，不推送，退出码 0。"""
        proc = self.run_script("scripts/release.sh", "nosuchremote")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("跳过 nosuchremote（未配置）", proc.stdout)

    def test_pre_push_block_message_names_the_remote(self) -> None:
        """推往发布远端的提交不在 template 历史内：阻断，并在提示里点名远端（v0.3.5 在 UTF-8 下丢远端名、残留乱码）。"""
        self.git("checkout", "-q", "-b", "main")
        (self.repo / "note.md").write_text("实例内容\n", encoding="utf-8")
        self.commit("ingest: 实例内容")
        sha = self.git("rev-parse", "main").strip()
        # 发布远端未配置时默认 origin；远端 sha 全零即推成新分支
        proc = self.run_script(
            "scripts/hooks/pre-push", "origin", "https://example.invalid/template.git",
            stdin=f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n",
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("发布远端「origin」只接受模板内容", proc.stdout)


class BootstrapMessagesUtf8Test(unittest.TestCase):
    """bootstrap.sh 里带全角标点的提示在 UTF-8 语言环境下完整输出、不中断。"""

    def setUp(self) -> None:
        """临时实例仓（复制 bootstrap.sh 并提交）与伪 HOME（agent-memory-setup 放空桩，避免联网安装）。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name).resolve()
        self.home = base / "home"
        stub = self.home / ".agents" / "skills" / "agent-memory-setup" / "setup.sh"
        stub.parent.mkdir(parents=True)
        stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)
        self.repo = base / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPTS / "bootstrap.sh", self.repo / "scripts" / "bootstrap.sh")
        (self.repo / "AGENTS.md").write_text("# 临时实例\n", encoding="utf-8")
        for args in (["init", "-q", "-b", "main"], ["add", "-A"],
                     ["-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "init"]):
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)

    def tearDown(self) -> None:
        """释放临时目录。"""
        self.temp_dir.cleanup()

    def run_bootstrap(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        """在伪 HOME、UTF-8 语言环境下运行 cwd 里的 scripts/bootstrap.sh。"""
        return subprocess.run(
            ["bash", "scripts/bootstrap.sh", *args], cwd=cwd, capture_output=True,
            encoding="utf-8", errors="replace", env={**UTF8_ENV, "HOME": str(self.home)}, check=False,
        )

    def test_worktree_refusal_names_the_worktree(self) -> None:
        """在附属 worktree 里运行：拒绝，并在提示里给出 worktree 路径（v0.3.5 在此报 ROOT unbound variable）。"""
        worktree = self.repo.parent / "wt"
        subprocess.run(["git", "worktree", "add", "-q", str(worktree)], cwd=self.repo, capture_output=True, check=True)
        proc = self.run_bootstrap(worktree, "--mode", "project")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(f"附属 worktree（{worktree}）", proc.stderr)

    def test_link_mismatch_warning_is_complete(self) -> None:
        """~/.llm-wiki 已指向别处时显式 --mode global：告警给出现指向与期望指向，其余步骤照做（v0.3.5 在此报 cur unbound variable）。"""
        other = self.home / "other-instance"
        other.mkdir()
        (self.home / ".llm-wiki").symlink_to(other)
        proc = self.run_bootstrap(self.repo, "--mode", "global")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(f"已是软链但指向 {other}（期望 {self.repo}）", proc.stdout)


if __name__ == "__main__":
    unittest.main()
