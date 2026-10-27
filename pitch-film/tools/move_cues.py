import re
from pathlib import Path

base = Path(__file__).resolve().parents[1]
html = (base / "index.html").read_text(encoding="utf-8")
block = re.search(
    r'<script type="application/json" id="om-cues">.*?</script>\s*<audio id="om-voice"[^>]*></audio>',
    html,
    re.S,
).group(0)
html = html.replace(block, "", 1)
html = html.replace("<script>\nconst V = OM.vars();", block + "\n<script>\nconst V = OM.vars();", 1)
(base / "index.html").write_text(html, encoding="utf-8")
print("moved", len(block), "bytes")
