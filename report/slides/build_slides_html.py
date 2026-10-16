"""Ghep cac slide (dinh dang artifact) thanh 1 file HTML xem offline."""
import json
import re
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
deck = json.loads((src / "deck.json").read_text(encoding="utf-8"))
ICON = {"Users": "&#128101;", "Wrench": "&#128295;", "Settings": "&#9881;"}
parts = []
for sid in deck["order"]:
    html = (src / "slides" / f"{sid}.html").read_text(encoding="utf-8")
    html = re.sub(r"<aside>(.*?)</aside>", r'<div class="notes">Ghi chú: \1</div>', html, flags=re.S)
    html = re.sub(r'<x-icon name="(\w+)" style="([^"]*)"></x-icon>',
                  lambda m: f'<div style="{m.group(2)};font-size:48px;line-height:1">{ICON.get(m.group(1), "")}</div>',
                  html)
    html = re.sub(r'<x-shape kind="arrow-right" style="[^"]*"></x-shape>',
                  '<div style="font-size:48px;color:#2F6FDB">&#8594;</div>', html)
    parts.append(f'<div class="frame"><div class="scaler">{html}</div></div>')

page = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{deck['title']}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700;800&display=swap">
<style>
body{{margin:0;background:#2b2f36;font-family:'Be Vietnam Pro',Arial,sans-serif}}
.frame{{width:min(96vw,1280px);aspect-ratio:16/9;margin:24px auto 8px;position:relative;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,.4)}}
.scaler{{width:1920px;height:1080px;transform-origin:0 0;position:absolute;left:0;top:0}}
section{{width:1920px;height:1080px;box-sizing:border-box;position:relative}}
section *{{margin:0}}
table{{border-collapse:collapse}} th,td{{border-bottom:1px solid #c9ced6;padding:.35em .6em;text-align:left}}
.notes{{display:none}}
.frame + .n{{width:min(96vw,1280px);margin:0 auto 24px;color:#cfd6df;font-size:15px}}
</style></head><body>
{''.join(p + '<div class="n"></div>' for p in parts)}
<script>
function fit(){{document.querySelectorAll('.frame').forEach(f=>{{f.firstChild.style.transform='scale('+f.clientWidth/1920+')';}});}}
document.querySelectorAll('.frame').forEach(f=>{{const n=f.querySelector('.notes');if(n)f.nextElementSibling.textContent=n.textContent;}});
addEventListener('resize',fit);fit();
</script></body></html>
"""
out.write_text(page, encoding="utf-8")
print("wrote", out, len(parts), "slides")
