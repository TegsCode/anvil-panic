"""Generate labelled placeholder cards for the screenshot slots.

    python tools/slots.py            # only fills in files that are missing
    python tools/slots.py --force    # overwrite (don't: this deletes the real ones)

The page and the README point at fixed filenames. Until the real screenshots
exist, a card saying which file is missing beats a broken image, and it tells you
at a glance what is still outstanding.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "screenshots"

INK = (21, 16, 32)
INK2 = (36, 26, 51)
CREAM = (247, 237, 220)
CREAM2 = (221, 203, 178)
TEAL = (94, 224, 192)
CORAL = (255, 107, 107)

SLOTS = [
    ("classic-01-gameplay.png", "CLASSIC · 01", "Early game, blob mid-screen"),
    ("classic-02-shield.png", "CLASSIC · 02", "Donut shield up, junk closing in"),
    ("classic-03-death.png", "CLASSIC · 03", "Flattened blob + culprit + score"),
    ("classic-04-late.png", "CLASSIC · 04", "Late game, heavy junk, high score"),
    ("tease-01-honoured.png", "TEASE · 01", "THE HONOURED ONE — Hollow Purple"),
    ("tease-02-ninja.png", "TEASE · 02", "THE NINJA — Shadow Clones"),
    ("tease-03-titan.png", "TEASE · 03", "THE TITAN — Heat Vision"),
    ("tease-04-volt.png", "TEASE · 04", "VOLT — Thunder"),
    ("tease-05-merc.png", "TEASE · 05", "THE MERC — Fourth Wall"),
    ("tease-06-bat.png", "TEASE · 06", "THE BAT — Batarangs"),
]

W, H = 1280, 720


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = ("consolab.ttf", "arialbd.ttf") if bold else ("consola.ttf", "arial.ttf")
    for n in names:
        for base in (pathlib.Path("C:/Windows/Fonts"), pathlib.Path("/usr/share/fonts")):
            p = base / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def card(name: str, label: str, what: str) -> Image.Image:
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)

    # dashed frame
    step, dash = 26, 14
    for x in range(0, W, step):
        d.line([(x, 0), (min(x + dash, W), 0)], fill=INK2, width=4)
        d.line([(x, H - 1), (min(x + dash, W), H - 1)], fill=INK2, width=4)
    for y in range(0, H, step):
        d.line([(0, y), (0, min(y + dash, H))], fill=INK2, width=4)
        d.line([(W - 1, y), (W - 1, min(y + dash, H))], fill=INK2, width=4)

    # a blob sitting under the gravity of the missing shot
    d.rounded_rectangle([W // 2 - 90, H // 2 - 40, W // 2 + 90, H // 2 + 52], radius=46,
                        fill=INK2, outline=INK2, width=3)
    for ex in (-34, 34):
        d.ellipse([W // 2 + ex - 7, H // 2 - 6, W // 2 + ex + 7, H // 2 + 8], fill=CREAM)

    d.text((60, 54), label, font=font(34), fill=CORAL)
    d.text((60, H - 148), name, font=font(44), fill=CREAM)
    d.text((60, H - 92), what, font=font(26, bold=False), fill=CREAM2)
    d.text((W - 340, H - 56), "PLACEHOLDER — REPLACE", font=font(20), fill=TEAL)
    return im


def main() -> int:
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    for name, label, what in SLOTS:
        path = OUT / name
        if path.exists() and not force:
            continue
        card(name, label, what).save(path, optimize=True)
        made += 1
    print(f"{made} placeholder(s) written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
