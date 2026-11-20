"""Independently inspect the generated handoff in Chromium, including a broken layout."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = [(320,568),(390,844),(768,1024),(839,600),(840,600),(1280,720),(844,390)]
MEASURE = """() => {
  const rect = selector => {
    const r = document.querySelector(selector).getBoundingClientRect();
    return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};
  };
  return {headline:rect('header'), stage:rect('figure'), action:rect('aside'), target:rect('button'),
          width:document.documentElement.scrollWidth, height:document.documentElement.scrollHeight,
          loaded: document.querySelector('img').naturalWidth > 0,
          ids: [...document.querySelectorAll('[data-component]')].map(e=>e.dataset.component)};
}"""


def violations(metrics, width, height, expected):
    h, s, a, t = [metrics[k] for k in ("headline","stage","action","target")]
    issues = []
    if metrics["ids"] != expected or not metrics["loaded"]:
        issues.append("content")
    if metrics["width"] > width or metrics["height"] > height + 1:
        issues.append("overflow")
    if t["height"] < 44 or t["width"] < 44:
        issues.append("target")
    if h["bottom"] > s["y"] + 1 or s["height"] < 140:
        issues.append("stage")
    if width < 840 and a["y"] < s["bottom"] - 1:
        issues.append("stack")
    if width >= 840 and (a["x"] < s["right"] - 1 or abs(a["y"]-s["y"]) > 1):
        issues.append("rail")
    return issues


def measure(root, out):
    design = json.loads((root/"studio/hud-brief.json").read_text())
    expected = [design["acceptance"][key] for key in ("headline","stage","action")]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        rows = []
        for w,h in VIEWPORTS:
            page.set_viewport_size({"width":w, "height":h})
            page.goto((out/"screen.html").resolve().as_uri())
            metrics = page.evaluate(MEASURE)
            issues = violations(metrics,w,h,expected)
            if issues:
                raise ValueError(f"{w}x{h}: {issues}")
            if w == 840:
                page.screenshot(path=str(out/"screen.jpg"),type="jpeg",quality=85)
            rows.append({"viewport":[w,h],"action_size":[metrics["target"]["width"],metrics["target"]["height"]],
                         "layout":"stack" if w<840 else "rail","violations":issues})
        page.add_style_tag(content="button{min-height:0;height:18px;padding:0}")
        broken = violations(page.evaluate(MEASURE),w,h,expected)
        if "target" not in broken:
            raise ValueError("Missed undersized action in negative control")
        browser.close()
    (out/"geometry.json").write_text(json.dumps({"viewports":rows,"injected_fault":broken},indent=2)+"\n")


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("root",type=Path)
    cli.add_argument("out",type=Path)
    args=cli.parse_args()
    measure(args.root,args.out)
