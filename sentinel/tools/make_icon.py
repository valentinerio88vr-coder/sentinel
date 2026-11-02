#!/usr/bin/env python3
"""Generates the Sentinel desktop icon.

Draws at 1024px with 4x supersampling, then writes:
  assets/sentinel.ico   multi-resolution Windows icon (16/24/32/48/64/128/256)
  assets/sentinel.png   512px PNG for shortcuts and docs

Run:  python3 tools/make_icon.py
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "assets")
SUPER = 4
BASE = 1024
S = BASE * SUPER


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def gradient(size: int, c1: tuple[int, int, int], c2: tuple[int, int, int]) -> Image.Image:
    """Diagonal two-stop gradient."""
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x / size * 0.55 + y / size * 0.45)
            px[x, y] = (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))
    return img


def _bezier(p0, p1, p2, p3, steps: int):
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0]
        y = u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]
        out.append((x, y))
    return out


def draw_shield(d: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float,
                fill: tuple[int, int, int, int]) -> None:
    """A symmetric shield: flat shoulders, curved sides meeting at a bottom point."""
    left, right = cx - w / 2, cx + w / 2
    top, bottom = cy - h / 2, cy + h / 2
    notch = top + h * 0.075          # centre dips slightly below the top corners
    shoulder = top + h * 0.46

    pts = [(left, top + h * 0.06), (cx, notch), (right, top + h * 0.06), (right, shoulder)]
    # right side curves down to the point
    pts += _bezier((right, shoulder), (right - w * 0.02, top + h * 0.76),
                   (cx + w * 0.17, bottom - h * 0.10), (cx, bottom), 40)
    # mirrored left side back up
    pts += _bezier((cx, bottom), (cx - w * 0.17, bottom - h * 0.10),
                   (left + w * 0.02, top + h * 0.76), (left, shoulder), 40)
    d.polygon(pts, fill=fill)


def draw_pin(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
             fill: tuple[int, int, int, int]) -> None:
    """Map-pin: circle head with a tapered tail."""
    head_cy = cy - r * 0.35
    d.ellipse([cx - r, head_cy - r, cx + r, head_cy + r], fill=fill)
    tail = [
        (cx - r * 0.62, head_cy + r * 0.52),
        (cx + r * 0.62, head_cy + r * 0.52),
        (cx, cy + r * 1.35),
    ]
    d.polygon(tail, fill=fill)


def build() -> Image.Image:
    # --- background tile with gradient + soft inner glow
    grad = gradient(S, (14, 116, 214), (34, 211, 238))
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    tile.paste(grad, (0, 0), rounded_mask(S, radius=int(S * 0.22)))

    # subtle top-left highlight
    glow = Image.new("L", (S, S), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-S * 0.35, -S * 0.55, S * 0.75, S * 0.55], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.06))
    white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    tile = Image.composite(white, tile, Image.composite(glow, Image.new("L", (S, S), 0), rounded_mask(S, int(S * 0.22))))

    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # --- drop shadow under the shield
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    draw_shield(sd, S / 2, S / 2 + S * 0.012, S * 0.50, S * 0.60, (2, 20, 40, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.022))
    layer = Image.alpha_composite(layer, shadow)
    d = ImageDraw.Draw(layer)

    # --- shield body (white) then an inset blue face for depth
    draw_shield(d, S / 2, S / 2, S * 0.50, S * 0.60, (255, 255, 255, 255))
    draw_shield(d, S / 2, S / 2 + S * 0.004, S * 0.40, S * 0.50, (13, 42, 74, 255))

    # --- location pin inside the shield
    draw_pin(d, S / 2, S / 2 + S * 0.005, S * 0.105, (34, 211, 238, 255))
    d.ellipse([S / 2 - S * 0.038, S / 2 - S * 0.036 - S * 0.038, S / 2 + S * 0.038, S / 2 - S * 0.036 + S * 0.038],
              fill=(13, 42, 74, 255))

    out = Image.alpha_composite(tile, layer)
    return out.resize((BASE, BASE), Image.LANCZOS)


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    icon = build()
    png = os.path.join(ASSETS, "sentinel.png")
    icon.resize((512, 512), Image.LANCZOS).save(png, "PNG")

    ico = os.path.join(ASSETS, "sentinel.ico")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    icon.save(ico, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"wrote {png}")
    print(f"wrote {ico}  ({', '.join(str(s) for s in sizes)})")


if __name__ == "__main__":
    main()
