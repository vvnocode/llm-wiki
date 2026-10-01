#!/usr/bin/env python3
"""生成公共层分区的页面索引。

对 wiki/ 下存在的每个公共层分区（concepts、entities、operations、decisions、risks），把该目录里的页面
按文件名排序，写成 wiki/<分区>/index.md：一行一页，文字取页面的一级标题，页面里有「曾用标题：」行时附在后面。
生成页是纯导航子索引，不要手改；项目分区与学习中心的 index.md 是手写的，不归本脚本管。

根索引 wiki/index.md 里指向 <分区>/README.md 的入口链接，会被改指 <分区>/index.md（只改链接目标，重复运行不再变化）。

标准输出逐行打印文件路径（相对仓根），小结与提示走标准错误：

- 不带参数：按磁盘上的文件生成，打印本次被改写的文件；没有变化就什么都不打印。写完页面、跑 lint 之前用。
- --from-git：页面清单只取 git 已跟踪或已暂存的文件，不看工作区里未跟踪的文件；打印要随提交带上的生成文件——
  与 HEAD 有差异的分区索引，以及根索引（仅当它的待提交改动恰好只是入口归一，不混着别的手工改动）。
  sync.sh 用它，使提交进去的索引与提交进去的页面一致，不把别的会话尚未提交的新页或改动带进本次提交。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 由脚本生成索引的分区；projects/ 与 learning/ 的子索引带正文或进度，仍然手写
SECTIONS = ("concepts", "entities", "operations", "decisions", "risks")
# 分区目录里不算页面的文件
NOT_PAGES = ("README.md", "index.md")
ROOT_INDEX = "wiki/index.md"

H1_RE = re.compile(r"^# +(.+?)\s*$", re.M)
FORMER_TITLES_RE = re.compile(r"^曾用标题[：:]\s*(.+?)\s*$", re.M)


def git(root: str, *args: str) -> subprocess.CompletedProcess:
    """在仓库根执行 git。输出一律按 UTF-8 解码：Agent 派生的子进程常不带 UTF-8 语言环境，中文路径不能交给本地编码。"""
    return subprocess.run(["git", "-C", root, *args], capture_output=True, encoding="utf-8")


def is_page(name: str) -> bool:
    """分区目录下的直接子文件里，哪些算页面。"""
    return name.endswith(".md") and name not in NOT_PAGES


def pages_on_disk(root: str, section: str) -> list[str]:
    """分区目录里的页面文件名（不递归）。"""
    section_dir = os.path.join(root, "wiki", section)
    return [n for n in os.listdir(section_dir) if is_page(n) and os.path.isfile(os.path.join(section_dir, n))]


def pages_in_git(root: str, section: str) -> list[str]:
    """分区目录里已跟踪或已暂存的页面文件名（不递归）。"""
    prefix = f"wiki/{section}/"
    out = git(root, "ls-files", "-z", "--", prefix).stdout
    names = [path[len(prefix):] for path in out.split("\0") if path.startswith(prefix)]
    return [n for n in names if "/" not in n and is_page(n)]


def page_text(root: str, section: str, name: str, from_git: bool) -> str:
    """读页面正文。--from-git 下文件已不在磁盘上（别的会话删了但没提交）时，取 git 索引里的版本。"""
    path = os.path.join(root, "wiki", section, name)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    if from_git:
        return git(root, "show", f":wiki/{section}/{name}").stdout
    return ""


def entry(name: str, text: str) -> str:
    """一张页面在索引里的一行。"""
    h1 = H1_RE.search(text)
    title = h1.group(1) if h1 else name[: -len(".md")]
    line = f"- [{title}]({name})"
    former = FORMER_TITLES_RE.search(text)
    if former:
        line += f"（曾用标题：{former.group(1)}）"
    return line


def render(root: str, section: str, from_git: bool) -> str:
    """生成一个分区的索引全文。"""
    names = pages_in_git(root, section) if from_git else pages_on_disk(root, section)
    lead = "本页由 `scripts/build-index.py` 按各页标题生成，不要手改"
    if os.path.isfile(os.path.join(root, "wiki", section, "README.md")):
        lead += "；本分区收什么见 [README](README.md)"
    parts = [f"# {section}/ 索引", lead + "。"]
    if names:
        parts.append("\n".join(entry(n, page_text(root, section, n, from_git)) for n in sorted(names)))
    return "\n\n".join(parts) + "\n"


def normalize_root_links(text: str, sections: list[str]) -> str:
    """根索引的分区入口归一：指向 <分区>/README.md 的链接改指生成索引。"""
    for s in sections:
        text = text.replace(f"]({s}/README.md)", f"]({s}/index.md)")
    return text


def write_if_changed(root: str, rel: str, content: str) -> bool:
    """内容有变化才写，返回是否改写。"""
    path = os.path.join(root, rel)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == content:
                return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def files_to_stage(root: str, sections: list[str]) -> list[str]:
    """要随提交带上的生成文件：相对 HEAD 有差异的分区索引；根索引只在待提交改动恰好是入口归一时才算。"""
    stage = [rel for rel in (f"wiki/{s}/index.md" for s in sections) if git(root, "status", "--porcelain", "--", rel).stdout.strip()]
    head = git(root, "show", f"HEAD:{ROOT_INDEX}")
    path = os.path.join(root, ROOT_INDEX)
    if head.returncode == 0 and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            on_disk = f.read()
        if on_disk != head.stdout and on_disk == normalize_root_links(head.stdout, sections):
            stage.append(ROOT_INDEX)
    return stage


def main() -> int:
    # 提示里有中文：标准流统一用 UTF-8，不随本地编码报错
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="生成公共层分区的页面索引")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="仓库根（测试可指向临时夹具）")
    parser.add_argument("--from-git", action="store_true", help="页面清单只取 git 已跟踪或已暂存的文件；打印要随提交带上的生成文件")
    args = parser.parse_args()
    root = os.path.abspath(args.root)

    if args.from_git and git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        print("build-index：--from-git 需要在 git 仓库里运行", file=sys.stderr)
        return 2

    sections = [s for s in SECTIONS if os.path.isdir(os.path.join(root, "wiki", s))]
    rewritten = [
        f"wiki/{s}/index.md" for s in sections if write_if_changed(root, f"wiki/{s}/index.md", render(root, s, args.from_git))
    ]

    # 根索引的分区入口归一；找不到入口的分区提示手工补
    root_index = os.path.join(root, ROOT_INDEX)
    if os.path.isfile(root_index):
        with open(root_index, encoding="utf-8") as f:
            text = normalize_root_links(f.read(), sections)
        if write_if_changed(root, ROOT_INDEX, text):
            rewritten.append(ROOT_INDEX)
        for s in sections:
            if f"]({s}/index.md)" not in text:
                print(f"build-index：根索引里没有 {s} 分区的入口，请手工加上 [{s}/]({s}/index.md)", file=sys.stderr)

    for rel in files_to_stage(root, sections) if args.from_git else rewritten:
        print(rel)
    print(f"build-index：更新 {len(rewritten)} 个文件" if rewritten else "build-index：索引已是最新", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
