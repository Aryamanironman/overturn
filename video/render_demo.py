#!/usr/bin/env python3
"""Render the OVERTURN workflow demo.

    python video/render_demo.py --stills
    python video/render_demo.py --frames
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

VIDEO = Path(__file__).resolve().parent
URL = (VIDEO / "demo.html").as_uri()
STORY = json.loads((VIDEO / "demo.json").read_text(encoding="utf-8"))
FPS = 30
DURATION = float(STORY["total"])


def contact(paths: list[Path], out: Path, cols: int = 3) -> None:
    thumb_w, thumb_h = 640, 360
    rows = math.ceil(len(paths) / cols)
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + 24)), "#10202b")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
        x = (index % cols) * thumb_w
        y = (index // cols) * (thumb_h + 24)
        sheet.paste(image, (x, y + 24))
        draw.text((x + 8, y + 6), path.stem, fill="#eef1f4")
    sheet.save(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stills", action="store_true")
    parser.add_argument("--frames", action="store_true")
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=DURATION)
    args = parser.parse_args()

    stills_dir = VIDEO / "demo-stills"
    frames_dir = VIDEO / "frames-demo"
    stills_dir.mkdir(exist_ok=True)
    frames_dir.mkdir(exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.goto(URL, wait_until="load")
        page.wait_for_function("window.__storyReady === true", timeout=30000)
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        page.evaluate("(t) => window.seek(t)", 0)
        page.wait_for_timeout(500)

        if args.stills:
            paths = []
            for scene in STORY["scenes"]:
                moment = scene["voice_start"] + min(scene["duration"] * 0.62, 4.2)
                if scene["layout"] in {"reason", "honesty"}:
                    moment = scene["voice_start"] + scene.get("stampAt", 3.0) + 0.6
                if scene["layout"] == "terminal":
                    moment = scene["start"] + scene["duration"] - 0.4
                page.evaluate(
                    "(t) => { window.seek(t); return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }",
                    moment,
                )
                path = stills_dir / f"{scene['index']:02d}-{scene['id']}.png"
                page.screenshot(path=str(path), type="png")
                paths.append(path)
            contact(paths[:7], stills_dir / "sheet-1.png")
            contact(paths[7:], stills_dir / "sheet-2.png")
            print(f"wrote {len(paths)} stills")

        if args.frames:
            first = int(round(max(0.0, args.start) * args.fps))
            last = int(round(min(DURATION, args.end) * args.fps))
            for index in range(first, last):
                t = index / args.fps
                page.evaluate(
                    "(t) => { window.seek(t); return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }",
                    t,
                )
                page.screenshot(path=str(frames_dir / f"f{index:05d}.png"), type="png")
                if index % 150 == 0:
                    print(f"frame {index}/{last}", flush=True)
            print(f"wrote frames {first}..{last - 1}")

        browser.close()


if __name__ == "__main__":
    main()
