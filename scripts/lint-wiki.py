#!/usr/bin/env python3
"""wiki 机械体检。

检查：index 覆盖、来源/核验节、相对断链、log 格式、根 log 混入条目、
没有任何入链的孤儿页、疑似禁止来源路径、来源节用 outputs 自证、
来源节里仓内相对路径是否存在。默认只出清单，退出码 1 表示有问题。

过期核验、两页冲突、缺交叉引用是语义项，由 lint skill 的模型步骤做，本脚本不判。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 导航或生成物：不要求出现在 index 的内容表里，也不强制「来源」节。
SKIP_CONTENT_CONTRACT = {
    "index.md",
    "log.md",
    "AGENTS.md",
    "logs/README.md",
}

ENTRY_RE = re.compile(
    r"^## \[(\d{4})-(\d{2})-(\d{2})\] (ingest|query|lint|correct|ops) \| .+"
)
# 禁止把依赖目录、密钥文件当来源引用。只匹配 repos/inputs 下的真实路径，
# 避免把「禁止来源」说明页里的 `.env` 字样误报。
FORBIDDEN = re.compile(
    r"(repos|inputs)/[^\s`)]*(node_modules|(?:^|/)\.env(?:/|$)|/\.venv/|/dist/|/target/)"
)
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"`([^`]+)`")
REPO_REL_RE = re.compile(r"^(inputs|docs|config|wiki|scripts|templates|tests)/")


def pages(wiki: str) -> list[str]:
    """列出 wiki 下全部 markdown 相对路径。"""
    out = []
    for dirpath, _dirs, files in os.walk(wiki):
        for fn in files:
            if fn.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, fn), wiki).replace(os.sep, "/"))
    return sorted(out)


def is_content_page(rel: str) -> bool:
    """事实页：需要进 index，且需要来源/核验节。"""
    if rel in SKIP_CONTENT_CONTRACT:
        return False
    if rel.startswith("logs/"):
        return False
    if rel.endswith("/README.md") or rel == "README.md":
        return False
    return True


def resolve_href(wiki: str, from_rel: str, href: str) -> str | None:
    """把页面内相对链接解析成绝对路径。外链返回 None。"""
    raw = href.strip()
    if raw.startswith(("http://", "https://", "mailto:", "#")):
        return None
    href_path = raw.split("#", 1)[0].split("?", 1)[0]
    if not href_path:
        return None
    return os.path.normpath(os.path.join(wiki, os.path.dirname(from_rel), href_path))


def index_targets(wiki: str, idx_text: str) -> set[str]:
    """index.md 里指向的 wiki 页（相对 wiki 根）。"""
    found: set[str] = set()
    for href in MD_LINK_RE.findall(idx_text):
        target = resolve_href(wiki, "index.md", href)
        if target is None:
            continue
        candidates = [target]
        if not os.path.splitext(target)[1]:
            candidates.append(target + ".md")
        for c in candidates:
            if os.path.isfile(c):
                found.add(os.path.relpath(c, wiki).replace(os.sep, "/"))
    return found


def source_section(text: str) -> str:
    """取出最后一个「## 来源」到下一节或文末。"""
    idx = text.rfind("## 来源")
    if idx < 0:
        return ""
    rest = text[idx:]
    nxt = re.search(r"\n## (?!来源)", rest[1:])
    if nxt:
        return rest[: nxt.start() + 1]
    return rest


def lint(root: str) -> list[str]:
    """对 root 下的 wiki/ 做机械体检，返回问题清单。"""
    wiki = os.path.join(root, "wiki")
    index_path = os.path.join(wiki, "index.md")
    log_path = os.path.join(wiki, "log.md")
    logs_dir = os.path.join(wiki, "logs")
    issues: list[str] = []

    if not os.path.isdir(wiki):
        return ["没有 wiki/ 目录"]

    all_pages = pages(wiki)
    if not os.path.exists(index_path):
        issues.append("缺少 index.md")
        idx_text = ""
        indexed: set[str] = set()
    else:
        idx_text = open(index_path, encoding="utf-8").read()
        indexed = index_targets(wiki, idx_text)

    content_pages = [p for p in all_pages if is_content_page(p)]
    inbound: dict[str, int] = defaultdict(int)
    for p in indexed:
        inbound[p] += 1

    for p in all_pages:
        path = os.path.join(wiki, p)
        text = open(path, encoding="utf-8").read()
        if is_content_page(p):
            if p not in indexed:
                issues.append(f"未入 index：{p}")
            if "## 来源" not in text:
                issues.append(f"缺「来源」节：{p}")
            if "## 最后核验" not in text:
                issues.append(f"缺「最后核验」节：{p}")
            src = source_section(text)
            for line in src.splitlines():
                stripped = line.strip()
                if stripped.startswith("-") and "outputs/" in stripped:
                    if any(w in stripped for w in ("不得", "禁止", "不是", "不给", "不作")):
                        continue
                    issues.append(f"来源节疑似用 outputs 自证：{p}")
            for tick in BACKTICK_RE.findall(src):
                rel = tick.strip()
                if "<" in rel or rel.startswith(("http://", "https://", "~/", "/")):
                    continue
                if not REPO_REL_RE.match(rel):
                    continue
                # 链接里的 wiki 相对路径不算仓根相对路径
                target = os.path.join(root, rel)
                if not os.path.exists(target):
                    issues.append(f"来源路径不存在 {p} → `{rel}`")
        if FORBIDDEN.search(text):
            issues.append(f"疑似禁止来源：{p}")
        for href in MD_LINK_RE.findall(text):
            target = resolve_href(wiki, p, href)
            if target is None:
                continue
            candidates = [target]
            if not os.path.splitext(target)[1]:
                candidates.append(target + ".md")
            exists = [c for c in candidates if os.path.exists(c)]
            if not exists:
                issues.append(f"断链 {p} → {href}")
                continue
            hit = exists[0]
            try:
                rel = os.path.relpath(hit, wiki).replace(os.sep, "/")
            except ValueError:
                continue
            if not rel.startswith(".."):
                inbound[rel] += 1

    for p in content_pages:
        if inbound.get(p, 0) == 0:
            issues.append(f"孤儿页（index 与其它页都未链到）：{p}")

    if not os.path.exists(log_path):
        issues.append("缺少 log.md")
    else:
        for i, line in enumerate(open(log_path, encoding="utf-8"), 1):
            if re.match(r"^## \[\d{4}-\d{2}-\d{2}\] ", line):
                issues.append(f"log.md:{i} 根日志不应含日期条目，应在 logs/YYYY-MM.md")

    if not os.path.isdir(logs_dir):
        issues.append("缺少 logs/ 目录")
    else:
        month_files = [
            fn for fn in os.listdir(logs_dir) if fn.endswith(".md") and fn != "README.md"
        ]
        # 尚无任何 ingest 的空 wiki 允许没有月日志；有主题页才要求
        if not month_files and content_pages:
            issues.append("logs/ 下没有 YYYY-MM.md")
        for fn in month_files:
            m = re.fullmatch(r"(\d{4})-(\d{2})\.md", fn)
            if not m:
                issues.append(f"非法月日志文件名：logs/{fn}")
                continue
            expected = f"{m.group(1)}-{m.group(2)}"
            for i, line in enumerate(open(os.path.join(logs_dir, fn), encoding="utf-8"), 1):
                if not line.startswith("## ["):
                    continue
                mm = ENTRY_RE.match(line.rstrip())
                if not mm:
                    issues.append(f"logs/{fn}:{i} 格式不是 ## [日期] 动作 | 标题")
                    continue
                if f"{mm.group(1)}-{mm.group(2)}" != expected:
                    issues.append(f"logs/{fn}:{i} 日期与文件名月份不一致")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM Wiki 机械体检")
    parser.add_argument(
        "--root",
        default=DEFAULT_ROOT,
        help="仓库根（测试可指向临时夹具）",
    )
    args = parser.parse_args()
    root = os.path.abspath(args.root)
    wiki = os.path.join(root, "wiki")
    issues = lint(root)
    content_n = len([p for p in pages(wiki) if is_content_page(p)]) if os.path.isdir(wiki) else 0
    if not issues:
        print(f"wiki lint：{content_n} 页，未发现机械问题")
        return 0
    print(f"wiki lint：{len(issues)} 项")
    for x in issues:
        print(f"  - {x}")
    print("\n只出清单。改之前仍走 docs/schemas/wiki.md 的写入门。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
