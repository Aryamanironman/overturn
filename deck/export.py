"""Export the deck to PDF. Run from the repo root:

    python deck/export.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

DECK = Path(__file__).resolve().parent
HTML = DECK / "index.html"
PDF = DECK / "OVERTURN-deck.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(HTML.as_uri(), wait_until="load")
    page.wait_for_function("document.fonts.ready.then(() => true)")
    page.emulate_media(media="print")
    page.pdf(
        path=str(PDF),
        width="1920px",
        height="1080px",
        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        print_background=True,
        prefer_css_page_size=True,
    )
    browser.close()

reader = PdfReader(str(PDF))
print(f"{PDF}  {len(reader.pages)} pages  {PDF.stat().st_size / 1024 / 1024:.1f} MB")
