#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Renderuje ironický citát na "lepík" (post-it) s ručně psaným tiskacím písmem.

Použití:
    python render.py              # první citát -> preview.png (IG handle)
    python render.py all          # všechny citáty -> out/001.png, ...
    python render.py both         # všechny citáty pro obě platformy
                                  #   -> out/ig_001.png, out/fb_001.png, ...
    python render.py first @jmeno # první citát s vlastním handle
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from quotes_loader import load_categories, interleave, build_order

HERE = os.path.dirname(os.path.abspath(__file__))

# Kandidáti na ručně psané písmo (použije se první existující).
# Kalam (pokud se později stáhne) > Segoe Print > Ink Free (obojí ve Windows).
FONT_CANDIDATES = {
    "regular": [
        os.path.join(HERE, "fonts", "Kalam-Regular.ttf"),
        r"C:\Windows\Fonts\segoepr.ttf",   # Segoe Print
        r"C:\Windows\Fonts\Inkfree.ttf",   # Ink Free
    ],
    "bold": [
        os.path.join(HERE, "fonts", "Kalam-Bold.ttf"),
        r"C:\Windows\Fonts\segoeprb.ttf",  # Segoe Print Bold
        r"C:\Windows\Fonts\segoepr.ttf",
    ],
}

CANVAS_W, CANVAS_H = 1080, 1920
HANDLE_IG = "@ironicky_neutralni"
HANDLE_FB = "@ironickyneutralni"
DEFAULT_HANDLE = HANDLE_IG

# Barvy lepíků (žlutá / růžová / zelená / modrá)
POSTIT_COLORS = [
    (255, 243, 166),
    (255, 214, 214),
    (206, 235, 213),
    (207, 222, 245),
]
INK = (34, 40, 58)            # barva "propisky"
FOOTER_COLOR = (125, 116, 100)


def _resolve_font(bold=False):
    for p in FONT_CANDIDATES["bold" if bold else "regular"]:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("Žádný ručně psaný font nebyl nalezen.")


def load_font(size, bold=False):
    return ImageFont.truetype(_resolve_font(bold), size)


def load_quotes():
    mixed = interleave(load_categories())
    return [q for q, _ in mixed]


def make_postit(w, h, color, rng):
    """Papír lepíku: zrno + zmačkání + přeložený roh."""
    arr = np.zeros((h, w, 3), dtype=np.float32)
    arr[:, :, 0] = color[0]
    arr[:, :, 1] = color[1]
    arr[:, :, 2] = color[2]

    grain = rng.normal(0, 3.0, (h, w, 1)).astype(np.float32)
    coarse = rng.normal(0, 16, (32, 24)).astype(np.float32)
    ci = Image.fromarray(np.uint8(np.clip(coarse + 128, 0, 255)))
    coarse_up = (np.asarray(ci.resize((w, h), Image.Resampling.BICUBIC), dtype=np.float32) - 128)[..., None]

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    wrinkle = (np.sin(xx / 80.0 + yy / 200.0) + np.sin(xx / 160.0 - yy / 120.0)) * 6.0

    arr = arr + grain + coarse_up + wrinkle[..., None]
    arr = np.clip(arr, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")

    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w - 1, h - 1], radius=36, fill=255)
    fold = 96
    md.polygon([(w - 1 - fold, h - 1), (w - 1, h - 1 - fold), (w - 1, h - 1)], fill=0)
    img.putalpha(mask)

    flap = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(flap)
    back = tuple(max(0, int(c * 0.82)) for c in color)
    fd.polygon([(w - 1 - fold, h - 1), (w - 1, h - 1 - fold), (w - 1, h - 1)], fill=back + (255,))
    fd.line([(w - 1 - fold, h - 1), (w - 1, h - 1 - fold)], fill=(0, 0, 0, 70), width=4)
    img = Image.alpha_composite(img, flap)
    return img


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_font(text, note_w, note_h, pad=80):
    """Největší písmo, při kterém se citát vejde do lepíku."""
    lo, hi, best = 40, 150, 40
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    while lo <= hi:
        mid = (lo + hi) // 2
        font = load_font(mid)
        lines = wrap_text(tmp, text, font, note_w - 2 * pad)
        asc, desc = font.getmetrics()
        lh = int((asc + desc) * 1.22)
        total = lh * len(lines)
        if total <= note_h - 2 * pad:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def render(quote, out_path, color, angle, seed, handle=DEFAULT_HANDLE):
    rng = np.random.default_rng(seed)

    # pozadí (pracovní plocha) s jemným gradientem, vinětací a šumem
    bg = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.float32)
    bg[:, :] = (230, 226, 216)
    yy = np.linspace(-1, 1, CANVAS_H)[:, None]
    xx = np.linspace(-1, 1, CANVAS_W)[None, :]
    r = np.sqrt(xx ** 2 + yy ** 2)
    vig = 1 - 0.12 * np.clip(r - 0.7, 0, 1)
    grad = 1 - 0.05 * yy
    bg = bg * grad[..., None] * vig[..., None]
    bg = np.clip(bg + rng.normal(0, 3, (CANVAS_H, CANVAS_W, 1)).astype(np.float32), 0, 255)
    canvas = Image.fromarray(bg.astype(np.uint8), "RGB").convert("RGBA")

    note_w, note_h = 900, 1120
    note = make_postit(note_w, note_h, color, rng)

    fs = fit_font(quote, note_w, note_h)
    font = load_font(fs)
    draw = ImageDraw.Draw(note)
    lines = wrap_text(draw, quote, font, note_w - 160)
    asc, desc = font.getmetrics()
    spacing = int((asc + desc) * 0.22)
    draw.multiline_text(
        (note_w // 2, note_h // 2),
        "\n".join(lines),
        font=font,
        fill=INK + (255,),
        anchor="mm",
        align="center",
        spacing=spacing,
    )

    note = note.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    shadow = Image.new("RGBA", (note_w + 120, note_h + 120), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([60, 60, note_w + 60, note_h + 60], radius=36, fill=(55, 40, 25, 130))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))

    canvas.alpha_composite(shadow, ((CANVAS_W - shadow.size[0]) // 2, (CANVAS_H - shadow.size[1]) // 2 + 36))
    nw, nh = note.size
    canvas.alpha_composite(note, ((CANVAS_W - nw) // 2, (CANVAS_H - nh) // 2))

    fd2 = ImageDraw.Draw(canvas)
    ffont = load_font(66)
    fw = fd2.textlength(handle, font=ffont)
    fd2.text(((CANVAS_W - fw) // 2, CANVAS_H - 160), handle, font=ffont, fill=FOOTER_COLOR + (255,))

    canvas.convert("RGB").save(out_path, quality=95)
    print("uloženo:", out_path, "(písmo", fs, "px)")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "first"
    handle = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HANDLE

    if mode in ("all", "both"):
        order = build_order()
        if not order:
            print("V quotes.txt nejsou žádné citáty.")
            return
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        for i, (qid, q, cat) in enumerate(order, 1):
            color = POSTIT_COLORS[cat % len(POSTIT_COLORS)]
            angle = ((i * 53) % 9) - 4          # -4..4, deterministicky
            if mode == "both":
                ig_path = os.path.join(HERE, "out", f"ig_{i:03d}.png")
                fb_path = os.path.join(HERE, "out", f"fb_{i:03d}.png")
                if not os.path.exists(ig_path):
                    render(q, ig_path, color, angle, i, HANDLE_IG)
                if not os.path.exists(fb_path):
                    render(q, fb_path, color, angle, i, HANDLE_FB)
            else:
                path = os.path.join(HERE, "out", f"{i:03d}.png")
                if not os.path.exists(path):
                    render(q, path, color, angle, i, handle)
        print("Hotovo, pozic:", len(order))
    else:
        quotes = load_quotes()
        if not quotes:
            print("V quotes.txt nejsou žádné citáty.")
            return
        render(quotes[0], os.path.join(HERE, "preview.png"), POSTIT_COLORS[0], 2.5, 42, handle)


if __name__ == "__main__":
    main()
