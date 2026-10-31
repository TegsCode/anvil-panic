"""Regenerate the Android launcher icons from desktop/anvil.ico.

    python tools/make-icons.py

One source image, five densities, three flavours:

  ic_launcher.png            legacy square icon (rounded, full bleed)
  ic_launcher_round.png      legacy round icon
  ic_launcher_foreground.png adaptive foreground, art inside the 66dp safe zone
  ic_launcher_monochrome.png Android 13 themed-icon silhouette
  mipmap-anydpi-v26/*.xml    ties the foreground to the ink background colour

Everything is derived, so the .ico stays the only icon that is edited by hand.
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "desktop" / "anvil.ico"
RES = ROOT / "android" / "app" / "src" / "main" / "res"

DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}

LEGACY_DP = 48      # launcher icon size
FOREGROUND_DP = 108  # adaptive icon canvas
SAFE_DP = 72        # the part of the canvas a launcher is guaranteed to show


def source() -> Image.Image:
    """Largest frame of the .ico, as RGBA."""
    im = Image.open(SRC)
    big = max(im.ico.sizes())
    im.size = big
    im.load()
    return im.convert("RGBA")


def trimmed(im: Image.Image) -> Image.Image:
    """Crop the transparent margin so the art can be centred exactly."""
    box = im.getchannel("A").getbbox()
    return im.crop(box) if box else im


def square(im: Image.Image, size: int) -> Image.Image:
    """Fit the art into a transparent square without distorting it."""
    im = trimmed(im)
    scale = min(size / im.width, size / im.height)
    w, h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    art = im.resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(art, ((size - w) // 2, (size - h) // 2))
    return out


def rounded(im: Image.Image, radius_ratio: float = 0.22) -> Image.Image:
    """Mask an icon to a rounded square, keeping the art's own corners out."""
    mask = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(mask)
    r = int(min(im.size) * radius_ratio)
    d.rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=r, fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out


def circular(im: Image.Image) -> Image.Image:
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, im.width - 1, im.height - 1], fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out


def monochrome(im: Image.Image, size: int) -> Image.Image:
    """Solid white silhouette of the cream blob, for themed icons."""
    art = square(im, size)
    px = art.load()
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dst = out.load()
    for y in range(size):
        for x in range(size):
            r, g, b, a = px[x, y]
            if a > 90 and (r + g + b) / 3 > 90:
                dst[x, y] = (255, 255, 255, a)
    return out


ADAPTIVE_XML = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
"""


def main() -> int:
    src = source()
    written = 0

    for name, mult in DENSITIES.items():
        legacy = RES / f"mipmap-{name}"
        legacy.mkdir(parents=True, exist_ok=True)

        icon = square(src, round(LEGACY_DP * mult))
        rounded(icon).save(legacy / "ic_launcher.png", optimize=True)
        circular(icon).save(legacy / "ic_launcher_round.png", optimize=True)

        fg = RES / f"drawable-{name}"
        fg.mkdir(parents=True, exist_ok=True)
        canvas = round(FOREGROUND_DP * mult)
        safe = round(SAFE_DP * mult)
        fore = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        art = rounded(square(src, safe))
        fore.alpha_composite(art, ((canvas - safe) // 2, (canvas - safe) // 2))
        fore.save(fg / "ic_launcher_foreground.png", optimize=True)

        mono = monochrome(src, safe)
        mc = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        mc.alpha_composite(mono, ((canvas - safe) // 2, (canvas - safe) // 2))
        mc.save(fg / "ic_launcher_monochrome.png", optimize=True)

        written += 4

    anydpi = RES / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    (anydpi / "ic_launcher.xml").write_text(ADAPTIVE_XML, encoding="utf-8")
    (anydpi / "ic_launcher_round.xml").write_text(ADAPTIVE_XML, encoding="utf-8")
    written += 2

    print(f"{written} icon files written under {RES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
