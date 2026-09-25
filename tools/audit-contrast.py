#!/usr/bin/env python3
"""Audit text/background contrast on every built page, in the real browser.

    python tools/audit-contrast.py
    python tools/audit-contrast.py --theme dark

Why the browser and not the stylesheet: the effective background of a piece of
text is whatever the nearest painted ancestor happens to be, after alpha
compositing. That cannot be read off the CSS reliably — a token that looks fine
in isolation fails once it lands on a band whose colour comes from three levels
up. So this injects an auditor into each page, lets Chrome resolve the cascade,
then reports what actually failed.

WCAG 2.1 AA thresholds are applied per element: 3.0:1 for large text
(>=24px, or >=18.66px at weight >=700), otherwise 4.5:1.

Text sitting on a gradient or an image cannot be reduced to one background
colour, so those are reported separately as "needs a pixel check" rather than
guessed at.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

AUDITOR = r"""
<script>
(function () {
  function parse(c) {
    var m = c && c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(",").map(function (x) { return parseFloat(x.trim()); });
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }

  function over(fg, bg) {          /* alpha-composite fg onto bg */
    var a = fg.a;
    return {
      r: fg.r * a + bg.r * (1 - a),
      g: fg.g * a + bg.g * (1 - a),
      b: fg.b * a + bg.b * (1 - a),
      a: 1
    };
  }

  function lum(c) {
    function f(v) { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }

  function ratio(a, b) {
    var la = lum(a), lb = lum(b);
    var hi = Math.max(la, lb), lo = Math.min(la, lb);
    return (hi + 0.05) / (lo + 0.05);
  }

  function hex(c) {
    function h(v) { return ("0" + Math.round(v).toString(16)).slice(-2); }
    return "#" + h(c.r) + h(c.g) + h(c.b);
  }

  /* Effective background: climb ancestors, compositing translucent layers,
     until an opaque colour is reached. Stop and flag if an image or gradient
     is encountered, since that has no single colour. */
  function background(el) {
    var stack = [], node = el;
    while (node && node.nodeType === 1) {
      var cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== "none") {
        return { image: cs.backgroundImage.slice(0, 60) };
      }
      var bc = parse(cs.backgroundColor);
      if (bc && bc.a > 0) {
        stack.push(bc);
        if (bc.a >= 0.999) break;
      }
      node = node.parentElement;
    }
    if (!stack.length) return { color: { r: 255, g: 255, b: 255, a: 1 } };
    var acc = stack[stack.length - 1];
    if (acc.a < 0.999) acc = over(acc, { r: 255, g: 255, b: 255, a: 1 });
    for (var i = stack.length - 2; i >= 0; i--) acc = over(stack[i], acc);
    return { color: acc };
  }

  function label(el) {
    var s = el.tagName.toLowerCase();
    if (el.id) s += "#" + el.id;
    var cls = (el.getAttribute("class") || "").trim();
    if (cls) s += "." + cls.split(/\s+/).slice(0, 3).join(".");
    return s;
  }

  function ownText(el) {
    var t = "";
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) t += n.nodeValue;
    }
    return t.replace(/\s+/g, " ").trim();
  }

  var fails = [], images = [], checked = 0;

  document.querySelectorAll("body *").forEach(function (el) {
    if (/^(script|style|svg|path|br|hr|img|iframe|input|source)$/i.test(el.tagName)) return;
    var text = ownText(el);
    if (!text || text.length < 2) return;

    var cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none") return;
    if (parseFloat(cs.opacity) === 0) return;
    var rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return;
    /* skip visually-hidden helpers */
    if (el.closest(".sr-only, .skip-link, .hp")) return;

    var fg = parse(cs.color);
    if (!fg) return;

    var size = parseFloat(cs.fontSize);
    var weight = parseInt(cs.fontWeight, 10) || 400;
    var large = size >= 24 || (size >= 18.66 && weight >= 700);
    var need = large ? 3.0 : 4.5;

    var bg = background(el);
    checked++;

    if (bg.image) {
      images.push({ sel: label(el), text: text.slice(0, 48), fg: hex(fg), bg: bg.image, size: size, need: need });
      return;
    }

    var solid = fg.a < 0.999 ? over(fg, bg.color) : fg;
    var r = ratio(solid, bg.color);
    if (r < need - 0.005) {
      fails.push({
        sel: label(el), text: text.slice(0, 48),
        fg: hex(solid), bg: hex(bg.color),
        ratio: Math.round(r * 100) / 100, need: need,
        size: Math.round(size * 10) / 10, weight: weight
      });
    }
  });

  var pre = document.createElement("pre");
  pre.id = "audit";
  pre.textContent = JSON.stringify({ checked: checked, fails: fails, images: images });
  document.body.insertBefore(pre, document.body.firstChild);
})();
</script>
"""


def find_chrome() -> Path:
    for c in CHROME_CANDIDATES:
        if c.is_file():
            return c
    print("No Chrome/Edge found.", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="built site directory")
    ap.add_argument("--theme", choices=["auto", "light", "dark"], default="light")
    args = ap.parse_args()

    root = PROJECT / args.root
    chrome = find_chrome()
    tmp = root / "_audit_tmp"
    tmp.mkdir(exist_ok=True)

    pages = sorted(p for p in root.glob("*.html") if not p.name.startswith("_"))
    if not pages:
        print(f"No pages in {root}", file=sys.stderr)
        return 1

    total_fail = 0
    total_checked = 0
    all_images: list[dict] = []

    print(f"Auditing {len(pages)} page(s) in {root}  (theme: {args.theme})\n")

    for page in pages:
        html = page.read_text(encoding="utf-8")
        if args.theme != "auto":
            html = html.replace('<html lang="fr"', f'<html lang="fr" data-theme="{args.theme}"', 1)
        html = html.replace("</body>", AUDITOR + "</body>")
        # Keep it beside the real assets so relative paths resolve.
        target = root / f"_audit-{page.name}"
        target.write_text(html, encoding="utf-8")

        try:
            out = subprocess.run(
                [str(chrome), "--headless", "--disable-gpu", "--hide-scrollbars",
                 "--window-size=1440,1200", "--virtual-time-budget=8000",
                 "--dump-dom", target.resolve().as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
            ).stdout or ""
        finally:
            target.unlink(missing_ok=True)

        m = re.search(r'<pre id="audit">(.*?)</pre>', out, re.DOTALL)
        if not m:
            print(f"  !! {page.name}: auditor did not run")
            continue

        data = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                          .replace("&lt;", "<").replace("&gt;", ">"))
        total_checked += data["checked"]
        for im in data["images"]:
            im["page"] = page.name
        all_images.extend(data["images"])

        if data["fails"]:
            total_fail += len(data["fails"])
            print(f"  {page.name} — {len(data['fails'])} échec(s) sur {data['checked']} éléments")
            for f in data["fails"]:
                print(f"      {f['ratio']:>5.2f}:1  (besoin {f['need']})  {f['fg']} sur {f['bg']}"
                      f"  {f['size']:g}px/{f['weight']}  {f['sel'][:44]}")
                print(f"             « {f['text']} »")
        else:
            print(f"  {page.name} — OK ({data['checked']} éléments)")

    shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'=' * 68}")
    print(f"{total_checked} éléments testés — {total_fail} échec(s) de contraste")

    if all_images:
        seen = set()
        uniq = []
        for im in all_images:
            key = (im["sel"], im["bg"])
            if key not in seen:
                seen.add(key)
                uniq.append(im)
        print(f"\n{len(all_images)} élément(s) sur dégradé ou image — à vérifier au pixel "
              f"({len(uniq)} combinaison(s) distincte(s)) :")
        for im in uniq[:24]:
            print(f"    {im['sel'][:40]:42s} {im['fg']}  sur  {im['bg'][:38]}")

    return 1 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
