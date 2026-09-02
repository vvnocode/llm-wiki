#!/usr/bin/env python3
"""worktree 共享机制的离线回归测试：`scripts/worktree.sh` 与 `scripts/hooks/post-checkout`。

在临时仓库里模拟「根工作区有被 gitignore 排除的本机资产」，验证：
- `add` / `link` 把 `config/worktree-share.conf` 列出的资产软链进 worktree，且不弄脏 git 状态；
- 重复执行幂等，worktree 里已有的真实文件不被覆盖；
- 尾斜杠目录规则会让软链变成未跟踪文件，脚本必须撤销并告警；
- post-checkout 钩子随裸 `git worktree add` 自动挂载；
- `remove` 先把 worktree 内新产生的被忽略文件回收到根工作区（不覆盖），再删除 worktree。
不访问网络，不触碰真实仓库。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "worktree.sh"
HOOK = ROOT / "scripts" / "hooks" / "post-checkout"

# 目录规则一律不带尾斜杠（带尾斜杠的规则不匹配 worktree 里的软链，见 test_link_reverts_*）
GITIGNORE = """data/*
!data/.gitkeep
state/collectors
wiki/private/*
!wiki/private/README.md
.claude/settings.local.json
raw/**/bodies
.worktrees/
"""

SHARE_CONF = """# 测试用共享清单：一行一个相对仓根的路径前缀
data/
state/collectors/
wiki/private/
.claude/settings.local.json
raw/
"""


class WorktreeShareTest(unittest.TestCase):
    """覆盖 add / link / remove 三个子命令与 post-checkout 钩子。"""

    def setUp(self) -> None:
        """建立带本机资产的临时仓库：入库文件 + 被忽略的本机资产 + 脚本副本。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        # macOS 的临时目录经由 /var → /private/var 软链，先 resolve 便于与 git 输出的真实路径比较
        self.repo = Path(self.temp_dir.name).resolve() / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test User")
        self.git("config", "user.email", "test@example.com")
        self.write(self.repo, ".gitignore", GITIGNORE)
        self.write(self.repo, "config/worktree-share.conf", SHARE_CONF)
        # 入库文件：让 data/、wiki/private/、state/、raw/p1/ 在 worktree 里以真实目录存在
        for rel in ("data/.gitkeep", "wiki/private/README.md", "state/README.md", "raw/p1/index.json"):
            self.write(self.repo, rel, "tracked\n")
        # 脚本与钩子随仓库入库：钩子按「根工作区/scripts/worktree.sh」调用
        (self.repo / "scripts" / "hooks").mkdir(parents=True)
        shutil.copy(SCRIPT, self.repo / "scripts" / "worktree.sh")
        shutil.copy(HOOK, self.repo / "scripts" / "hooks" / "post-checkout")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")
        # 根工作区的本机资产（全部被 gitignore）
        self.write(self.repo, "data/clone/f.txt", "clone\n")
        self.write(self.repo, "data/.DS_Store", "junk\n")
        self.write(self.repo, "state/collectors/c.json", "{}\n")
        self.write(self.repo, "wiki/private/评价.md", "private\n")
        self.write(self.repo, ".claude/settings.local.json", '{"autoMemoryDirectory": "x"}\n')
        self.write(self.repo, "raw/p1/bodies/b.json", "body\n")
        # p2 没有任何入库文件：traditional 模式会把整个 p2 折叠成一个被忽略条目，脚本用 matching 模式只取命中规则的 bodies
        self.write(self.repo, "raw/p2/bodies/b.json", "body2\n")

    def tearDown(self) -> None:
        """释放临时目录。"""
        self.temp_dir.cleanup()

    # ── 工具方法 ──

    @staticmethod
    def write(base: Path, rel: str, text: str) -> None:
        """在 base 下写文本文件，缺失的父目录一并建立。"""
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def git(self, *args: str, cwd: Path | None = None) -> str:
        """运行 git 并返回去掉尾部空白的 stdout；失败时把完整输出带入测试错误。"""
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"git {' '.join(args)} 失败：\n{proc.stdout}\n{proc.stderr}")
        return proc.stdout.strip()

    def run_script(self, *args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
        """运行模板正本 scripts/worktree.sh（位置无关：仓根从目标 worktree 反推）。"""
        proc = subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if check:
            self.assertEqual(proc.returncode, 0, f"worktree.sh {' '.join(args)} 失败：\n{proc.stdout}\n{proc.stderr}")
        return proc

    def status(self, wt: Path) -> str:
        """worktree 的完整 git 状态（含逐个未跟踪文件），期望为空串。"""
        return self.git("status", "--porcelain", "--untracked-files=all", cwd=wt)

    # ── 用例 ──

    def test_add_links_shared_assets_and_keeps_status_clean(self) -> None:
        """add 建 worktree 后，共享清单内的被忽略资产都以软链出现，且 git 状态干净。"""
        proc = self.run_script("add", "t1")
        wt = self.repo / ".worktrees" / "t1"
        self.assertTrue(wt.is_dir(), proc.stdout)
        self.assertEqual(self.git("branch", "--show-current", cwd=wt), "t1")

        expected_links = (
            "data/clone",                  # 前缀下的被忽略目录
            "state/collectors",            # 整个前缀被忽略：单条软链
            "wiki/private/评价.md",         # 非 ASCII 文件名
            ".claude/settings.local.json",  # 文件级前缀
            "raw/p1/bodies",               # 入库目录下的被忽略子目录
            "raw/p2/bodies",               # 父目录 p2 无入库文件、自身不命中规则：只链命中规则的 bodies，worktree 里需先建父目录
        )
        for rel in expected_links:
            with self.subTest(path=rel):
                link = wt / rel
                self.assertTrue(link.is_symlink(), f"{rel} 应为软链\n{proc.stdout}")
                self.assertEqual(link.resolve(), (self.repo / rel).resolve())
        # 内容经软链可读；入库文件仍是真实文件；系统垃圾文件不链
        self.assertEqual((wt / "raw" / "p2" / "bodies" / "b.json").read_text(encoding="utf-8"), "body2\n")
        self.assertFalse((wt / "raw" / "p2").is_symlink())
        self.assertFalse((wt / "data" / ".gitkeep").is_symlink())
        self.assertFalse((wt / "wiki" / "private" / "README.md").is_symlink())
        self.assertFalse((wt / "data" / ".DS_Store").exists())
        self.assertEqual(self.status(wt), "")

    def test_link_is_idempotent_and_never_overwrites(self) -> None:
        """重复 link 不报错、不改状态；worktree 里已有的真实文件保持原样并提示未覆盖。"""
        self.run_script("add", "t1")
        wt = self.repo / ".worktrees" / "t1"
        # 模拟会话在 worktree 里自己写了一份同名真实文件
        (wt / "wiki" / "private" / "评价.md").unlink()
        self.write(wt, "wiki/private/评价.md", "local\n")

        proc = self.run_script("link", str(wt))
        self.assertFalse((wt / "wiki" / "private" / "评价.md").is_symlink())
        self.assertEqual((wt / "wiki" / "private" / "评价.md").read_text(encoding="utf-8"), "local\n")
        self.assertIn("未覆盖", proc.stdout)

        again = self.run_script("link", str(wt))
        self.assertEqual(again.returncode, 0)
        self.assertTrue((wt / "state" / "collectors").is_symlink())
        self.assertEqual(self.status(wt), "")

    def test_link_reverts_symlink_not_covered_by_gitignore(self) -> None:
        """目录规则带尾斜杠时软链不被忽略：脚本必须撤销该软链并指出原因，不留未跟踪文件。"""
        self.write(self.repo, ".gitignore", GITIGNORE.replace("state/collectors\n", "state/collectors/\n"))
        self.git("commit", "-q", "-am", "trailing slash")

        proc = self.run_script("add", "t1")
        wt = self.repo / ".worktrees" / "t1"
        self.assertFalse((wt / "state" / "collectors").is_symlink())
        self.assertFalse((wt / "state" / "collectors").exists())
        self.assertIn("尾斜杠", proc.stdout + proc.stderr)
        # 其余资产照常挂载，状态仍干净
        self.assertTrue((wt / "data" / "clone").is_symlink())
        self.assertEqual(self.status(wt), "")

    def test_post_checkout_hook_links_on_plain_git_worktree_add(self) -> None:
        """安装钩子后，裸 git worktree add（含 Claude Code 的 .claude/worktrees/）也自动挂载。"""
        hooks = self.repo / ".git" / "hooks"
        hooks.mkdir(exist_ok=True)
        os.symlink("../../scripts/hooks/post-checkout", hooks / "post-checkout")
        (self.repo / "scripts" / "hooks" / "post-checkout").chmod(0o755)

        wt = self.repo / ".claude" / "worktrees" / "x"
        self.git("worktree", "add", str(wt), "-b", "x")
        self.assertTrue((wt / "state" / "collectors").is_symlink())
        # worktree 里原本没有 .claude/ 目录，链接前需建父目录
        self.assertTrue((wt / ".claude" / "settings.local.json").is_symlink())
        self.assertTrue((wt / "raw" / "p2" / "bodies").is_symlink())
        self.assertEqual(self.status(wt), "")
        # 根工作区的文件检出（flag=0）不触发挂载逻辑，也不报错
        self.git("checkout", "--", ".gitignore")

    def test_remove_sweeps_new_ignored_files_back_to_root(self) -> None:
        """remove 把 worktree 内新产生的被忽略文件回收到根工作区，已存在的不覆盖，然后删除 worktree、保留分支。"""
        self.run_script("add", "t1")
        wt = self.repo / ".worktrees" / "t1"
        self.write(wt, "raw/p3/bodies/new.json", "new\n")       # 新周期正文：根工作区没有
        self.write(wt, "wiki/private/新页.md", "new page\n")     # 新私有页：根工作区没有
        self.write(self.repo, "wiki/private/冲突.md", "root\n")  # 双方都有：根工作区为准
        self.write(wt, "wiki/private/冲突.md", "worktree\n")

        proc = self.run_script("remove", "t1")
        self.assertFalse(wt.exists(), proc.stdout)
        self.assertNotIn(str(wt), self.git("worktree", "list"))
        self.assertEqual((self.repo / "raw" / "p3" / "bodies" / "new.json").read_text(encoding="utf-8"), "new\n")
        self.assertEqual((self.repo / "wiki" / "private" / "新页.md").read_text(encoding="utf-8"), "new page\n")
        self.assertEqual((self.repo / "wiki" / "private" / "冲突.md").read_text(encoding="utf-8"), "root\n")
        self.assertIn("冲突.md", proc.stdout)
        # 经软链共享的资产原样保留；分支留给合并后人工删除
        self.assertEqual((self.repo / "data" / "clone" / "f.txt").read_text(encoding="utf-8"), "clone\n")
        self.assertEqual((self.repo / "state" / "collectors" / "c.json").read_text(encoding="utf-8"), "{}\n")
        self.assertIn("t1", self.git("branch", "--list", "t1"))

    def test_link_on_root_is_noop_and_missing_conf_fails(self) -> None:
        """对根工作区 link 只提示不动作；清单取根工作区与 worktree 的并集，两份都缺才失败，add 在建 worktree 前就失败。"""
        proc = self.run_script("link", str(self.repo))
        self.assertIn("根工作区", proc.stdout)
        self.assertFalse((self.repo / "data" / "clone").is_symlink())

        (self.repo / "config" / "worktree-share.conf").unlink()
        proc = self.run_script("add", "t2", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("worktree-share.conf", proc.stdout + proc.stderr)
        self.assertFalse((self.repo / ".worktrees" / "t2").exists())

        # 根工作区没有清单、但 worktree 的分支里有（机制引入、或分支新增前缀尚未合入）：link 按并集挂载
        wt = self.repo / ".worktrees" / "t2"
        self.git("worktree", "add", str(wt), "-b", "t2")
        proc = self.run_script("link", str(wt))
        self.assertTrue((wt / "state" / "collectors").is_symlink(), proc.stdout + proc.stderr)
        # 两份都没有才失败
        (wt / "config" / "worktree-share.conf").unlink()
        proc = self.run_script("link", str(wt), check=False)
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
