"""Compile a verified component map to a portable, single-file design proof."""
import base64
from html import escape
from io import BytesIO
from string import Template

from PIL import Image, ImageOps


PAGE = Template("""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>$project · $screen</title>
<style>
*{box-sizing:border-box}body{margin:0;color:#faf6ea;background:#10191d;font:16px/1.35 system-ui,sans-serif}
main{min-height:100svh;max-width:1200px;margin:auto;padding:clamp(12px,3vw,36px);display:grid;gap:12px;
grid-template-areas:"headline" "stage" "action";grid-template-rows:auto minmax(140px,1fr) auto}
header,aside,figure{border-radius:12px;overflow:hidden}header,aside{background:#$base;padding:18px 22px}
header{grid-area:headline}small{letter-spacing:.08em;color:#$accent}h1{font:clamp(24px,4vw,40px)/1.08 Georgia,serif;margin:8px 0}
p{margin:6px 0}figure{grid-area:stage;position:relative;margin:0;background:#19282c}
img{position:absolute;width:100%;height:100%;object-fit:cover}
figcaption{position:absolute;bottom:0;width:100%;padding:32px 18px 12px;background:linear-gradient(transparent,#10191dfa)}
aside{grid-area:action;align-self:stretch;display:grid;align-content:center;gap:8px}
button{min-height:48px;min-width:48px;border:0;border-radius:8px;background:#$accent;color:#172326;font:600 16px system-ui}
@media(min-width:840px){main{grid-template-columns:minmax(0,2.3fr) minmax(230px,1fr);
grid-template-rows:auto minmax(160px,1fr);grid-template-areas:"headline headline" "stage action"}}
@media(max-height:500px){main{padding:8px;gap:6px}header,aside{padding:8px 14px}h1{margin:3px 0}}
</style><main aria-label="$screen design proof">
<header data-component="$headline_id"><small>$project · $screen</small><h1>$headline</h1><p>$headline_desc</p></header>
<figure data-component="$stage_id"><img src="data:image/jpeg;base64,$photo" alt=""><figcaption>$stage</figcaption></figure>
<aside data-component="$action_id"><p>$action_desc</p><button type="button" disabled>$action</button></aside>
</main></html>""")


def compile_page(root, design, binding):
    with Image.open(root / design["art"]) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((960, 720))
        jpeg = BytesIO()
        image.save(jpeg, format="JPEG", quality=80, optimize=True)
    args = {"photo": base64.b64encode(jpeg.getvalue()).decode(), "base": design["colors"][0],
            "accent": design["colors"][1], "project": escape(design["project"]), "screen": escape(design["screen"])}
    items = {item["id"]: item for item in design["components"]}
    for region, key in binding.items():
        item = items[key]
        args.update({region: escape(item["title"]), region + "_id": key, region + "_desc": escape(item["description"])})
    return PAGE.substitute(args)
