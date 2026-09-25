#!/usr/bin/env python3
"""Sanity-check the generated site: broken links, missing assets, dead anchors.

    python tools/check.py

Exits non-zero if anything is wrong, so it can be wired into CI later.
"""

from __future__ import annotations

import argparse
import html.parser
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

PROJECT = Path(__file__).resolve().parent.parent
ROOT = PROJECT  # rebound from --root in main()


class PageParser(html.parser.HTMLParser):
    """Collect ids, links, asset references and a few a11y-relevant facts."""

    VOID = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }
    # Elements the parser should not try to balance (SVG is self-consistent but
    # noisy, and <script>/<style> contents are CDATA-ish).
    IGNORE_NESTING = {"svg", "path", "circle", "rect", "ellipse", "defs",
                      "lineargradient", "stop", "g", "polygon", "polyline",
                      "use", "symbol", "text", "tspan"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.classes: set[str] = set()
        self.links: list[str] = []
        self.assets: list[str] = []
        self.stack: list[str] = []
        self.imbalance: list[str] = []
        self.images_without_alt = 0
        self.labels: set[str] = set()
        self.form_ids: set[str] = set()
        self.h1_count = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs_list: list) -> None:
        attrs = dict(attrs_list)

        if "class" in attrs:
            self.classes.update(attrs["class"].split())

        if "id" in attrs:
            self.ids.add(attrs["id"])

        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])

        if tag in ("img", "script", "iframe") and "src" in attrs:
            self.assets.append(attrs["src"])

        if tag == "link" and "href" in attrs and attrs.get("rel") != "canonical":
            self.assets.append(attrs["href"])

        if tag == "img" and "alt" not in attrs:
            self.images_without_alt += 1

        if tag == "label" and "for" in attrs:
            self.labels.add(attrs["for"])

        if tag in ("input", "select", "textarea") and "id" in attrs:
            self.form_ids.add(attrs["id"])

        if tag == "h1":
            self.h1_count += 1

        if tag == "title":
            self._in_title = True

        if tag not in self.VOID and tag not in self.IGNORE_NESTING:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in self.VOID or tag in self.IGNORE_NESTING:
            return
        if not self.stack:
            self.imbalance.append(f"</{tag}> with nothing open")
            return
        if self.stack[-1] != tag:
            self.imbalance.append(f"</{tag}> closed while <{self.stack[-1]}> was open")
            # Recover so one slip doesn't cascade.
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def main() -> int:
    global ROOT
    ap = argparse.ArgumentParser(description="Sanity-check a built site.")
    ap.add_argument("--root", default=".",
                    help="directory holding the built HTML (default: project root)")
    args = ap.parse_args()
    ROOT = PROJECT / args.root
    is_default_root = ROOT.resolve() == PROJECT.resolve()

    pages = sorted(p for p in ROOT.glob("*.html"))
    if not pages:
        print("No built pages found — run tools/build.py first.", file=sys.stderr)
        return 1

    parsed: dict[str, PageParser] = {}
    problems: list[str] = []
    notes: list[str] = []

    for page in pages:
        text = page.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(text)
        parsed[page.name] = parser

        if parser.stack:
            problems.append(f"{page.name}: tags left open: {parser.stack}")
        for issue in parser.imbalance:
            problems.append(f"{page.name}: {issue}")
        if parser.images_without_alt:
            problems.append(f"{page.name}: {parser.images_without_alt} <img> without alt")
        if parser.h1_count != 1:
            problems.append(f"{page.name}: expected exactly one <h1>, found {parser.h1_count}")
        if not parser.title.strip():
            problems.append(f"{page.name}: empty <title>")
        elif len(parser.title.strip()) > 70:
            notes.append(f"{page.name}: <title> is {len(parser.title.strip())} chars (>70 may be truncated in search results)")

        for target in parser.labels:
            if target not in parser.form_ids:
                problems.append(f"{page.name}: <label for=\"{target}\"> has no matching field")

        # Unreplaced build tokens.
        for token in set(re.findall(r"\{\{[A-Z_]+\}\}", text)):
            problems.append(f"{page.name}: unreplaced token {token}")

        # Leftover placeholder brackets outside the legal page, where they are
        # intentional and flagged in a comment.
        if page.name != "mentions-legales.html":
            for match in re.findall(r"\[(?:à compléter|TODO|à confirmer)[^\]]*\]", text, re.I):
                problems.append(f"{page.name}: placeholder left in copy: {match}")

    # --------------------------------------------------------------- links
    for name, parser in parsed.items():
        for href in parser.links:
            split = urlsplit(href)

            if split.scheme in ("http", "https", "mailto", "tel"):
                if split.scheme == "http":
                    problems.append(f"{name}: insecure http:// link → {href}")
                continue
            if not href or href == "#":
                problems.append(f"{name}: empty href")
                continue

            path = unquote(split.path)
            fragment = split.fragment

            if path:
                target_file = ROOT / path
                if not target_file.exists():
                    problems.append(f"{name}: link to missing file → {href}")
                    continue
                target_ids = parsed.get(path, PageParser()).ids
            else:
                target_ids = parser.ids

            if fragment and fragment not in target_ids:
                problems.append(f"{name}: anchor not found → {href}")

    # -------------------------------------------------------------- assets
    for name, parser in parsed.items():
        for src in parser.assets:
            split = urlsplit(src)
            if split.scheme in ("http", "https", "data"):
                if split.scheme == "http":
                    problems.append(f"{name}: insecure http:// asset → {src}")
                continue
            asset = ROOT / unquote(split.path)
            if not asset.exists():
                problems.append(f"{name}: missing asset → {src}")

    # ----------------------------------------------------- orphan CSS classes
    # A class in the markup with no rule in the stylesheet is almost always a
    # typo or a scale gap (e.g. using .mt-4 when only .mt-5 exists) and fails
    # silently in the browser. Applied by JS, so not expected in the CSS as a
    # standalone selector: listed below.
    js_applied = {
        "is-visible", "is-open", "is-stuck", "nav-open", "js",
        "icon-sun", "icon-moon",
    }

    css_path = ROOT / "assets" / "css" / "style.css"
    if css_path.exists():
        css = re.sub(r"/\*.*?\*/", "", css_path.read_text(encoding="utf-8"), flags=re.DOTALL)
        defined = set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", css))

        used: set[str] = set()
        for parser in parsed.values():
            used |= parser.classes

        orphans = sorted(used - defined - js_applied)
        for orphan in orphans:
            where = sorted(n for n, p in parsed.items() if orphan in p.classes)
            problems.append(
                f"class '{orphan}' is used in {', '.join(where)} but has no rule in style.css"
            )
    else:
        problems.append("assets/css/style.css is missing")

    # ------------------------------------------------------------- sitemap
    sitemap = ROOT / "sitemap.xml"
    if sitemap.exists():
        listed = set(re.findall(r"<loc>https://parispartners\.com/(.*?)</loc>", sitemap.read_text(encoding="utf-8")))
        listed = {name or "index.html" for name in listed}
        actual = {p.name for p in pages}
        for missing in sorted(actual - listed):
            problems.append(f"sitemap.xml: {missing} is not listed")
        for extra in sorted(listed - actual):
            problems.append(f"sitemap.xml: lists {extra}, which does not exist")
    elif is_default_root:
        problems.append("sitemap.xml is missing")
    else:
        notes.append("no sitemap.xml in this build (fine for a noindex preview)")

    # -------------------------------------------------------------- report
    print(f"Checked {len(pages)} pages.\n")

    if notes:
        print("Notes:")
        for note in notes:
            print(f"  ~  {note}")
        print()

    if problems:
        print(f"{len(problems)} problem(s):")
        for problem in problems:
            print(f"  !! {problem}")
        return 1

    print("No problems found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
