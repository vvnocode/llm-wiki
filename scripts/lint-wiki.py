#!/usr/bin/env python3
"""wiki 机械体检。

检查：index 覆盖（两级索引：根 index 只列入口，子索引下的页面算已入索引）、子索引未入根 index、
来源/核验节、相对断链、log 格式、根 log 混入条目、没有任何入链的孤儿页、疑似禁止来源路径、
来源节用 outputs 自证、来源节里仓内相对路径是否存在。默认只出清单，退出码 1 表示有问题。

子索引规则：纯导航（标题、紧跟一级标题的一段导语、带链接的列表项、表格、HTML 注释）免检来源与核验两节；
承载正文的按事实页检查。私有区 private/ 只豁免「未入 index」与「孤儿页」，私有页发出的链接不给公共页
算入链；来源、核验、断链、禁止来源照查。外部仓来源写 `<登记名>[@<ref>]:<仓内路径>`，不按本仓路径检查；
裸写的仓内相对路径仍检查是否存在。

提示项（不计入退出码）：「最后核验」首条只写到月份的页。过期核验、两页冲突、缺交叉引用是语义项，由 lint skill
的模型步骤做，本脚本不判。
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
# 外部仓来源：<登记名>[@<ref>]:<仓内路径>，登记名取 config/ 里的名字。这种写法不是本仓路径，不查存在性。
EXTERNAL_REF_RE = re.compile(r"^[A-Za-z0-9._-]+(?:@[^\s:]+)?:")

# 子索引的导航行：标题、表格行、带 Markdown 链接的列表项、HTML 注释
HEADING_RE = re.compile(r"^#{1,6}\s")
TABLE_ROW_RE = re.compile(r"^\|")
LIST_WITH_LINK_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+.*\[[^\]]*\]\([^)]+\)")
HTML_COMMENT_RE = re.compile(r"^<!--.*-->$")
VERIFY_MONTH_ONLY_RE = re.compile(r"^\d{4}-\d{2}$")


def pages(wiki: str) -> list[str]:
    """列出 wiki 下全部 markdown 相对路径。"""
    out = []
    for dirpath, _dirs, files in os.walk(wiki):
        for fn in files:
            if fn.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, fn), wiki).replace(os.sep, "/"))
    return sorted(out)


def page_texts(wiki: str) -> dict[str, str]:
    """一次读入全部页面正文，键为相对 wiki 根的路径。"""
    return {p: open(os.path.join(wiki, p), encoding="utf-8").read() for p in pages(wiki)}


def is_sub_index(rel: str) -> bool:
    """子索引：wiki 根以下任何名为 index.md 的页面，是两级索引的第二级。"""
    return rel != "index.md" and rel.endswith("/index.md")


def is_private(rel: str) -> bool:
    """私有区页面：物理不出本机，按设计不进根索引。"""
    return rel.startswith("private/")


def sub_index_has_body(text: str) -> bool:
    """子索引是否承载正文。

    纯导航只允许：各级标题、紧跟一级标题的一段导语（连续非空行）、带链接的列表项、表格行、HTML 注释。
    出现其它非空行（第二段及以后的段落、没有链接的列表项）即视为承载正文，按事实页检查来源与核验。
    """
    headings = 0
    lead_open = False  # 正在读导语段
    lead_used = False  # 导语段已经结束，之后不再允许散文
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if lead_open:
                lead_open, lead_used = False, True
            continue
        if HEADING_RE.match(line):
            headings += 1
            if lead_open:
                lead_open, lead_used = False, True
            continue
        if TABLE_ROW_RE.match(line) or LIST_WITH_LINK_RE.match(line) or HTML_COMMENT_RE.match(line):
            if lead_open:
                lead_open, lead_used = False, True
            continue
        # 其它非空行：只有紧跟一级标题、且在任何二级标题之前的第一段算导语
        if headings <= 1 and not lead_used:
            lead_open = True
            continue
        return True
    return False


def is_content_page(rel: str, text: str) -> bool:
    """事实页：需要进 index（私有区除外），且需要来源/核验节。子索引只在承载正文时算事实页。"""
    if rel in SKIP_CONTENT_CONTRACT:
        return False
    if rel.startswith("logs/"):
        return False
    if rel.endswith("/README.md") or rel == "README.md":
        return False
    if is_sub_index(rel):
        return sub_index_has_body(text)
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


def index_targets(wiki: str, idx_text: str, from_rel: str = "index.md") -> set[str]:
    """某个索引页里指向的 wiki 页（相对 wiki 根）；from_rel 是该索引页自身的相对路径。"""
    found: set[str] = set()
    for href in MD_LINK_RE.findall(idx_text):
        target = resolve_href(wiki, from_rel, href)
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


def first_verify_token(text: str) -> str | None:
    """「最后核验」节第一条的日期字样（括注与空白之前的部分）；没有该节或没有条目返回 None。"""
    m = re.search(r"^## 最后核验[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return None
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            return re.split(r"[（(\s]", line[2:].strip(), 1)[0]
    return None


def hints(root: str) -> list[str]:
    """提示项：不算机械问题、不改退出码，只在输出末尾列出。目前一项：最后核验只写到月份。"""
    wiki = os.path.join(root, "wiki")
    if not os.path.isdir(wiki):
        return []
    out: list[str] = []
    texts = page_texts(wiki)
    for p in sorted(texts):
        if not is_content_page(p, texts[p]):
            continue
        stamp = first_verify_token(texts[p])
        if stamp and VERIFY_MONTH_ONLY_RE.match(stamp):
            out.append(f"最后核验只到月份（需 YYYY-MM-DD）：{p}")
    return out


def lint(root: str) -> list[str]:
    """对 root 下的 wiki/ 做机械体检，返回问题清单。"""
    wiki = os.path.join(root, "wiki")
    index_path = os.path.join(wiki, "index.md")
    log_path = os.path.join(wiki, "log.md")
    logs_dir = os.path.join(wiki, "logs")
    issues: list[str] = []

    if not os.path.isdir(wiki):
        return ["没有 wiki/ 目录"]

    texts = page_texts(wiki)
    all_pages = sorted(texts)
    if not os.path.exists(index_path):
        issues.append("缺少 index.md")
        indexed: set[str] = set()
    else:
        indexed = index_targets(wiki, texts["index.md"])

    # 两级索引：子索引必须由根 index 直接链接（私有区的子索引除外）；子索引链接的页面同样视为已入索引。
    # 只支持两级，子索引之间不传递。未入根 index 的子索引只报这一条根因，其下页面不再逐个报「未入 index」。
    for sub in all_pages:
        if not is_sub_index(sub):
            continue
        if not is_private(sub) and sub not in indexed:
            issues.append(f"子索引未入根 index：{sub}")
        indexed |= index_targets(wiki, texts[sub], sub)

    content_pages = [p for p in all_pages if is_content_page(p, texts[p])]
    inbound: dict[str, int] = defaultdict(int)
    for p in indexed:
        inbound[p] += 1

    for p in all_pages:
        text = texts[p]
        if is_content_page(p, text):
            if p not in indexed and not is_private(p) and not is_sub_index(p):
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
                if EXTERNAL_REF_RE.match(rel):
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
            # 私有页发出的链接不给公共页算入链：私有区不出本机，公共页不能靠它免于孤儿
            if not rel.startswith("..") and not is_private(p):
                inbound[rel] += 1

    for p in content_pages:
        if is_private(p):
            continue
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
    content_n = 0
    if os.path.isdir(wiki):
        texts = page_texts(wiki)
        content_n = len([p for p in texts if is_content_page(p, texts[p])])
    tips = hints(root)
    if not issues:
        print(f"wiki lint：{content_n} 页，未发现机械问题")
    else:
        print(f"wiki lint：{len(issues)} 项")
        for x in issues:
            print(f"  - {x}")
    for x in tips:
        print(f"  - 提示：{x}")
    if issues:
        print("\n只出清单。改之前仍走 docs/schemas/wiki.md 的写入门。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
