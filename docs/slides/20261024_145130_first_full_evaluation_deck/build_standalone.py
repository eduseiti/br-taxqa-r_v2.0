"""Assemble project/slides/*.html (in deck.json order) into one offline-viewable deck.html.

The slide files are fragments for the claude.ai Slides artifact type: 1920x1080 <section>s with
inline styles and speaker notes in <aside>. This page stacks them, scaled to the window width,
with each slide's notes below it. Print to PDF from the browser for a handout.
"""
import json
import re
from pathlib import Path

here = Path(__file__).parent
deck = json.loads((here / "project/deck.json").read_text(encoding="utf-8"))
fonts = "".join(f'<link rel="stylesheet" href="{f["href"]}">\n' for f in deck["faces"].values())

slides = []
for n, sid in enumerate(deck["order"], 1):
    html = (here / f"project/slides/{sid}.html").read_text(encoding="utf-8")
    m = re.search(r"<aside>(.*?)</aside>", html, re.S)
    notes = m.group(1).strip() if m else ""
    html = re.sub(r"<aside>.*?</aside>", "", html, flags=re.S)
    slides.append(
        f'<div class="frame"><div class="slide">{html}</div></div>\n'
        f'<p class="notes"><b>{n} · {sid}</b> — {notes}</p>'
    )

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{deck["title"]}</title>
{fonts}<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #D9D5CC; font-family: 'IBM Plex Sans', Arial, sans-serif; padding: 24px 16px; }}
.frame {{ width: min(100%, 1280px); aspect-ratio: 16 / 9; margin: 0 auto; overflow: hidden;
          position: relative; container-type: inline-size; box-shadow: 0 2px 8px #0003; }}
.slide {{ width: 1920px; height: 1080px; transform-origin: 0 0; transform: scale(calc(100cqw / 1920px));
          position: absolute; top: 0; left: 0; }}
.slide > section {{ width: 1920px; height: 1080px; position: relative; overflow: hidden; }}
table {{ border-collapse: collapse; }} th, td {{ text-align: left; padding: 10px 16px; }}
th {{ font-weight: 600; }} tr {{ border-bottom: 1px solid #C9C3B6; }}
.notes {{ width: min(100%, 1280px); margin: 12px auto 40px; font-size: 15px; line-height: 1.5; color: #333; }}
@media print {{ body {{ background: #fff; padding: 0; }} .frame {{ box-shadow: none; break-inside: avoid; }}
               .notes {{ break-after: page; }} }}
</style></head><body>
{chr(10).join(slides)}
<script>
// cqw in transform is not supported everywhere: scale with JS as a fallback.
function fit() {{ document.querySelectorAll('.frame').forEach(f => {{
  f.querySelector('.slide').style.transform = 'scale(' + f.clientWidth / 1920 + ')'; }}); }}
addEventListener('resize', fit); fit();
</script>
</body></html>
"""
(here / "deck.html").write_text(page, encoding="utf-8")
print(f"wrote deck.html with {len(slides)} slides")
