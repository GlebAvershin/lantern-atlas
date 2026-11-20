"""Read solid color pairs from the generated DOM, then evaluate them with a C++20 oracle."""
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright

out = Path(sys.argv[1])
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.goto((out/"screen.html").resolve().as_uri())
    colors = page.evaluate("""() => {
      const pairs = {heading:['h1','header'], accent:['small','header'], instruction:['aside p','aside'],
                     action:['button','button']};
      return Object.fromEntries(Object.entries(pairs).map(([id,[fg,bg]]) => [id,[
        getComputedStyle(document.querySelector(fg)).color, getComputedStyle(document.querySelector(bg)).backgroundColor]]));
    }""")
    browser.close()
lines=[]
for label,pair in colors.items():
    row=[label]
    for color in pair:
        rgb=re.fullmatch(r"rgb\((\d+), (\d+), (\d+)\)",color)
        if not rgb:
            raise ValueError(f"Opaque sRGB pair required for {label}")
        row.extend(rgb.groups())
    lines.append(" ".join(row))
with TemporaryDirectory() as build:
    oracle=Path(build)/"contrast"
    subprocess.run(["c++","-std=c++20","-O2",str(Path(__file__).with_name("contrast.cpp")),"-o",str(oracle)],check=True)
    result=subprocess.run([oracle],input="\n".join(lines),capture_output=True,text=True,check=True)
    control=subprocess.run([oracle],input="muted 120 120 120 121 121 121",capture_output=True,text=True)
    if control.returncode!=1:
        raise ValueError("Oracle missed the near-identical pair")
ratios = {label:float(ratio) for label,ratio in (line.split() for line in result.stdout.splitlines())}
(out/"contrast.json").write_text(json.dumps({"threshold":4.5,"computed_css":colors,"ratios":ratios,
    "negative_control_ratio":float(control.stdout.split()[1]),"negative_control_rejected":True},indent=2)+"\n")
