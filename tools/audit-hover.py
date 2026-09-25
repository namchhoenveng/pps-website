#!/usr/bin/env python3
"""Audit non-text contrast of interactive surfaces (WCAG 2.1 SC 1.4.11).

    python tools/audit-hover.py
    python tools/audit-hover.py --theme dark

audit-contrast.py checks TEXT against its background. It cannot see this class
of defect: a filled control whose surface has too little contrast against the
surface *behind* it, so its boundary disappears. That is how a red hover state
on a red-to-indigo gradient scored 1.00:1 and went unnoticed — the white label
inside it still passed comfortably.

A purely static pass over the stylesheet does not work either: it has no way to
know which ground a control actually sits on, so it compares every fill against
every painted surface in the file and drowns in false positives.

So this runs in the browser. For each interactive element it resolves the real
effective background of the PARENT, then measures:

  - the resting fill against that ground,
  - the fill declared by any matching :hover rule (read out of
    document.styleSheets, since :hover cannot be triggered in a headless
    --dump-dom run),
  - the border colour, for controls that rely on an outline instead of a fill.

Gradient grounds are expanded to their individual colour stops and the worst
one is reported, which is precisely where the CTA failure was hiding.

SC 1.4.11 asks for 3:1 between a UI component and adjacent colours.
"""

from __future__ import annotations

import argparse
import json
import re
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
  var NEED = 3.0;

  function parse(c) {
    var m = c && c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(",").map(function (x) { return parseFloat(x.trim()); });
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  function over(fg, bg) {
    var a = fg.a;
    return { r: fg.r*a + bg.r*(1-a), g: fg.g*a + bg.g*(1-a), b: fg.b*a + bg.b*(1-a), a: 1 };
  }
  function lum(c) {
    function f(v) { v/=255; return v<=0.04045 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }
    return 0.2126*f(c.r) + 0.7152*f(c.g) + 0.0722*f(c.b);
  }
  function ratio(a, b) {
    var la = lum(a), lb = lum(b), hi = Math.max(la,lb), lo = Math.min(la,lb);
    return (hi + 0.05) / (lo + 0.05);
  }
  function hex(c) {
    function h(v){ return ("0"+Math.round(v).toString(16)).slice(-2); }
    return "#"+h(c.r)+h(c.g)+h(c.b);
  }
  function label(el) {
    var s = el.tagName.toLowerCase();
    var cls = (el.getAttribute("class")||"").trim();
    if (cls) s += "." + cls.split(/\s+/).slice(0,3).join(".");
    return s;
  }

  /* Grounds behind an element: every opaque colour it could sit on. A gradient
     is expanded into its stops, because the worst stop is what matters. */
  function groundsOf(start) {
    var node = start, out = [];
    while (node && node.nodeType === 1) {
      var cs = getComputedStyle(node);
      var img = cs.backgroundImage;
      if (img && img !== "none" && img.indexOf("gradient") !== -1) {
        var stops = img.match(/rgba?\([^)]+\)/g) || [];
        stops.forEach(function (s) {
          var c = parse(s);
          if (c && c.a > 0.5) out.push({ c: c, from: label(node) + " (stop)" });
        });
        if (out.length) return out;
      }
      if (img && img !== "none" && img.indexOf("url(") !== -1) {
        return [];               /* photographic ground: not decidable here */
      }
      var bc = parse(cs.backgroundColor);
      if (bc && bc.a >= 0.999) { out.push({ c: bc, from: label(node) }); return out; }
      if (bc && bc.a > 0) out.push({ c: bc, from: label(node) + " (alpha)" });
      node = node.parentElement;
    }
    out.push({ c: {r:255,g:255,b:255,a:1}, from: "canvas" });
    return out;
  }

  /* Every :hover rule that declares a background, paired with its selector
     stripped of the pseudo-class so elements can be matched against it. */
  var hoverRules = [];
  for (var i = 0; i < document.styleSheets.length; i++) {
    var rules;
    try { rules = document.styleSheets[i].cssRules; } catch (e) { continue; }
    if (!rules) continue;
    for (var j = 0; j < rules.length; j++) {
      var r = rules[j];
      if (!r.selectorText || r.selectorText.indexOf(":hover") === -1) continue;
      var bg = r.style && (r.style.backgroundColor || r.style.background);
      if (!bg) continue;
      r.selectorText.split(",").forEach(function (sel) {
        sel = sel.trim();
        if (sel.indexOf(":hover") === -1) return;
        hoverRules.push({ base: sel.replace(/:hover/g, ""), bg: bg, sel: sel });
      });
    }
  }

  /* .chip and .tag are decorated text, not controls, so their boundary is not
     required to identify anything — excluded to keep the signal clean. */
  var SEL = 'a, button, .btn, .icon-btn, .pillnav a, .filter__btn, .pill-link';
  var fails = [], checked = 0;

  document.querySelectorAll(SEL).forEach(function (el) {
    if (el.closest(".sr-only, .skip-link, .hp")) return;
    var rect = el.getBoundingClientRect();
    if (rect.width < 8 || rect.height < 8) return;

    var grounds = groundsOf(el.parentElement);
    if (!grounds.length) return;             /* image ground: skip */

    var cs = getComputedStyle(el);

    /* A fill may be a flat colour OR a stack of gradient layers. Reading only
       backgroundColor reported a tile whose colour is the band's but whose
       visible fill is a gradient on top of it as 1.00:1 — a false positive.
       Expand any gradient into its stops, composited over the element's own
       background-colour, and keep the BEST of them: a gradient fill is a
       boundary as soon as some part of it separates from the ground. */
    function fillsOf(value, baseColour) {
      if (!value) return [];
      if (value.indexOf("url(") !== -1) return null;   /* image: not decidable */
      var base = parse(baseColour) || { r:255, g:255, b:255, a:0 };
      var out = [];
      if (value.indexOf("gradient") !== -1) {
        (value.match(/rgba?\([^)]+\)/g) || []).forEach(function (t) {
          var c = parse(t);
          if (c) out.push(c.a >= 0.999 ? c : over(c, base.a > 0.05 ? base : grounds[0].c));
        });
      } else {
        var c = parse(value);
        if (c) out.push(c);
      }
      return out;
    }

    /* sources: [{v: css value, kind: label, base: colour behind a translucent v}] */
    function test(state, sources) {
      var best = -1, bestFill = null, where = "", bestKind = "";
      var any = false;
      sources.forEach(function (src) {
        var cands = fillsOf(src.v, src.base);
        if (cands === null) return;                     /* image: not decidable */
        cands.forEach(function (c) {
          if (c.a < 0.05) return;                       /* transparent draws nothing */
          any = true;
          var solid = c.a < 0.999 ? over(c, grounds[0].c) : c;
          var worst = 99, w = "";
          grounds.forEach(function (g) {
            var rr = ratio(solid, g.c);
            if (rr < worst) { worst = rr; w = hex(g.c) + " " + g.from; }
          });
          if (worst > best) { best = worst; bestFill = solid; where = w; bestKind = src.kind; }
        });
      });
      if (!any) return;
      checked++;
      if (best < NEED - 0.005) {
        fails.push({ sel: label(el), state: state, kind: bestKind,
                     fill: hex(bestFill), ground: where,
                     ratio: Math.round(best*100)/100,
                     text: (el.textContent||"").replace(/\s+/g," ").trim().slice(0,34) });
      }
    }

    /* A child that covers the element paints the surface the eye actually sees
       — .tile--plate puts a full-bleed <img> over its own background, so the
       background is a fallback, not the boundary. Photographic surfaces are
       not decidable here, the same reason an image ANCESTOR is skipped. */
    function imageBacked(node) {
      var r = node.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return false;
      var kids = node.querySelectorAll("img, svg, video, picture");
      for (var k = 0; k < kids.length; k++) {
        var kr = kids[k].getBoundingClientRect();
        if (kr.width * kr.height >= r.width * r.height * 0.9) return true;
      }
      return false;
    }

    /* Fill and border are ALTERNATIVE boundaries, not a fallback chain. The
       border used to be tested only when there was no fill, which reported a
       white-filled button on a white ground as 1.00:1 even though a 1px rule
       drew its edge perfectly well. SC 1.4.11 asks that the component be
       distinguishable — one of the two reaching 3:1 is enough, so they are
       measured together and only the better one is judged. */
    if (!imageBacked(el)) {
      var paint = cs.backgroundImage && cs.backgroundImage !== "none"
                ? cs.backgroundImage : cs.backgroundColor;
      var cands = [{ v: paint, kind: "fond", base: cs.backgroundColor }];
      if (parseFloat(cs.borderTopWidth) >= 1) {
        cands.push({ v: cs.borderTopColor, kind: "bordure", base: "rgba(0,0,0,0)" });
      }
      test("repos", cands);
    }

    hoverRules.forEach(function (hr) {
      var ok = false;
      try { ok = el.matches(hr.base); } catch (e) { ok = false; }
      if (ok) test("SURVOL", [{ v: hr.bg, kind: "fond", base: cs.backgroundColor }]);
    });
  });

  var pre = document.createElement("pre");
  pre.id = "hoveraudit";
  pre.textContent = JSON.stringify({ checked: checked, fails: fails });
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
    ap.add_argument("--root", default=".")
    ap.add_argument("--theme", choices=["auto", "light", "dark"], default="light")
    args = ap.parse_args()

    root = PROJECT / args.root
    chrome = find_chrome()
    pages = sorted(p for p in root.glob("*.html") if not p.name.startswith("_"))
    if not pages:
        print(f"No pages in {root}", file=sys.stderr)
        return 1

    seen: dict[tuple, dict] = {}
    total_checked = 0

    print(f"Audit non-textuel (SC 1.4.11, seuil 3:1) — {args.root}, thème {args.theme}\n")

    for page in pages:
        html = page.read_text(encoding="utf-8")
        if args.theme != "auto":
            html = html.replace('<html lang="fr"', f'<html lang="fr" data-theme="{args.theme}"', 1)
        html = html.replace("</body>", AUDITOR + "</body>")
        target = root / f"_hover-{page.name}"
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

        m = re.search(r'<pre id="hoveraudit">(.*?)</pre>', out, re.DOTALL)
        if not m:
            print(f"  !! {page.name}: auditeur non exécuté")
            continue
        data = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                          .replace("&lt;", "<").replace("&gt;", ">"))
        total_checked += data["checked"]
        for f in data["fails"]:
            key = (f["sel"], f["state"], f["kind"], f["fill"], f["ground"])
            if key not in seen:
                f["pages"] = [page.name]
                seen[key] = f
            else:
                seen[key]["pages"].append(page.name)

    print(f"{total_checked} surface(s) mesurée(s) sur {len(pages)} page(s)\n")

    if not seen:
        print("  aucun échec")
        return 0

    for f in sorted(seen.values(), key=lambda x: x["ratio"]):
        print(f"  {f['ratio']:5.2f}:1  {f['state']:7s} {f['kind']:8s} {f['fill']}  sur  {f['ground']}")
        print(f"           {f['sel'][:60]}   « {f['text']} »")
        print(f"           {len(f['pages'])} page(s) : {', '.join(sorted(set(f['pages']))[:4])}")
    print(f"\n{len(seen)} échec(s) distinct(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
