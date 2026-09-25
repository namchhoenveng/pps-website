#!/usr/bin/env python3
"""Assemble a static site from a source tree into plain HTML.

The published output is ordinary static HTML — no runtime, no bundler, nothing
to install on the server. This script exists only so the header, footer and nav
live in ONE place instead of being copy-pasted into every page.

    python tools/build.py                               # the site
    python tools/build.py --out _preview --noindex      # a preview build

Each page in <src>/pages/ starts with a metadata comment:

    <!--meta
    title: Page title
    description: Meta description used for SEO and Open Graph.
    nav: offres
    path: offres.html
    -->

An optional raw <head> block may follow, for per-page JSON-LD:

    <!--head-->
    <script type="application/ld+json">...</script>
    <!--/head-->
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SITE = "https://parispartners.com/"

# label, filename, nav key. Shared by both versions: the information
# architecture is the same, only the design language differs.
NAV_ITEMS = [
    ("Accueil", "index.html", "accueil"),
    ("Offres", "offres.html", "offres"),
    ("Cas clients", "cas-clients.html", "cas-clients"),
    ("À propos", "a-propos.html", "a-propos"),
    ("Blog", "blog.html", "blog"),
    ("Contact", "contact.html", "contact"),
]

META_RE = re.compile(r"\A\s*<!--meta\s*(.*?)-->", re.DOTALL)
HEAD_RE = re.compile(r"<!--head-->(.*?)<!--/head-->", re.DOTALL)


def build_nav(active: str) -> str:
    """Render the <li> list, marking the active page with aria-current."""
    rows = []
    for label, href, key in NAV_ITEMS:
        current = ' aria-current="page"' if key == active else ""
        rows.append(f'        <li><a class="nav__link" href="{href}"{current}>{label}</a></li>')
    return "\n".join(rows)


def parse_page(text: str) -> tuple[dict[str, str], str, str]:
    """Split a source page into (metadata, raw head extra, body)."""
    match = META_RE.match(text)
    if not match:
        raise ValueError("missing <!--meta ... --> block")

    meta: dict[str, str] = {}
    for line in match.group(1).strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()

    body = text[match.end():]

    head_extra = ""
    head_match = HEAD_RE.search(body)
    if head_match:
        head_extra = head_match.group(1).strip()
        body = body[: head_match.start()] + body[head_match.end():]

    return meta, head_extra, body.strip("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="_src-v3", help="source tree (default: _src-v3)")
    ap.add_argument("--out", default=".", help="output directory (default: project root)")
    ap.add_argument("--site", default=DEFAULT_SITE, help="canonical site origin")
    ap.add_argument("--noindex", action="store_true",
                    help="emit <meta name=robots content=noindex> — for preview builds")
    args = ap.parse_args()

    src = ROOT / args.src
    out = ROOT / args.out
    pages_dir = src / "pages"

    layout_path = src / "layout.html"
    if not layout_path.is_file():
        print(f"No layout at {layout_path}", file=sys.stderr)
        return 1

    layout = layout_path.read_text(encoding="utf-8")
    sources = sorted(pages_dir.glob("*.html"))

    if not sources:
        print(f"No pages found in {pages_dir}", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)

    known_keys = {key for _, _, key in NAV_ITEMS}
    robots = ('\n<meta name="robots" content="noindex, nofollow">'
              if args.noindex else "")
    written = 0

    for source in sources:
        try:
            meta, head_extra, body = parse_page(source.read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"  !! {source.name}: {exc}", file=sys.stderr)
            return 1

        for required in ("title", "description", "path"):
            if required not in meta:
                print(f"  !! {source.name}: missing '{required}' in meta", file=sys.stderr)
                return 1

        nav_key = meta.get("nav", "")
        if nav_key and nav_key not in known_keys:
            print(f"  !! {source.name}: unknown nav key '{nav_key}'", file=sys.stderr)
            return 1

        # index.html is served at the bare domain, so its canonical drops the file name.
        path = "" if meta["path"] == "index.html" else meta["path"]

        page = layout
        for token, value in (
            ("{{TITLE}}", meta["title"]),
            ("{{DESCRIPTION}}", meta["description"]),
            ("{{OGTYPE}}", meta.get("ogtype", "website")),
            ("{{SITE}}", args.site),
            ("{{PATH}}", path),
            ("{{NAV}}", build_nav(nav_key)),
            ("{{ROBOTS}}", robots),
            ("{{HEAD_EXTRA}}", head_extra),
            ("{{BODY}}", body),
        ):
            page = page.replace(token, value)

        leftover = re.findall(r"\{\{[A-Z_]+\}\}", page)
        if leftover:
            print(f"  !! {source.name}: unreplaced tokens {sorted(set(leftover))}", file=sys.stderr)
            return 1

        (out / meta["path"]).write_text(page, encoding="utf-8")
        print(f"  ok  {meta['path']}")
        written += 1

    print(f"\n{written} page(s) written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
