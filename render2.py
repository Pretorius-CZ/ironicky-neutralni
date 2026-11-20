#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lepík v2: stejný základ (lepík s ručním písmem), ale víc variability
a výraznější značka stránky.

Všechny náhodné volby se odvozují z `seed` (= pořadové číslo citátu),
takže stejný citát dá při přegenerování vždy stejný obrázek.

Použití (stejné jako render.py, navíc --from):
    python render2.py                       # náhled 1. citátu -> preview.png
    python render2.py both --from 35        # přegeneruje ig_/fb_ PNG od pozice 35 dál
    python render2.py both --from 35 --to 40
    python render2.py missing               # jen chybějící PNG (nové citáty)
    python render2.py sample                # 8 náhledů do preview/ (nic nepřepisuje)
"""
import os
import re
import sys
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts_v2")   # záměrně jiná složka než fonts/ (tu používá starý render.py)

CANVAS_W, CANVAS_H = 1080, 1920
HANDLE_IG = "@ironicky_neutralni"
HANDLE_FB = "@ironickyneutralni"

# --- fonty (všechny umí češtinu) -------------------------------------------
QUOTE_FONTS = [
    "Kalam-Regular.ttf",
    "Caveat.ttf",
    "PatrickHand-Regular.ttf",
    "ShantellSans.ttf",
]
# Caveat (psací) je hlavní písmo, ostatní jen občas pro zpestření
FONT_WEIGHTS = [0.15, 0.55, 0.15, 0.15]
BRAND_FONT = "CaveatBrush-Regular.ttf"
# velikost písma se u Caveat musí zvětšit (je drobnější)
FONT_SCALE = {"Caveat.ttf": 1.25, "ShantellSans.ttf": 0.92}

# --- barvy -------------------------------------------------------------------
POSTIT_COLORS = [
    (255, 243, 166),   # žlutá (původní)
    (255, 214, 214),   # růžová (původní)
    (206, 235, 213),   # zelená (původní)
    (207, 222, 245),   # modrá (původní)
    (255, 206, 158),   # oranžová
    (226, 212, 247),   # levandulová
    (255, 236, 208),   # broskvová
    (196, 238, 236),   # tyrkysová
]
INKS = [
    (34, 40, 58),      # tmavá propiska (původní)
    (28, 28, 30),      # černá fixa
    (30, 58, 140),     # modrá propiska
]
HIGHLIGHT = [
    (255, 235, 59),    # žlutý zvýrazňovač
    (255, 128, 171),   # růžový
    (118, 255, 122),   # zelený
    (130, 210, 255),   # modrý
]
BRAND_BG = (26, 26, 34)        # tmavá jako intro/CTA karty stránky
BRAND_ACCENT = (255, 210, 80)  # žlutá jako pruh na intro/CTA


def font_path(name):
    p = os.path.join(FONTS, name)
    if os.path.exists(p):
        return p
    # nouzově Windows fonty (stejně jako původní render.py)
    for alt in (r"C:\Windows\Fonts\segoepr.ttf", r"C:\Windows\Fonts\Inkfree.ttf"):
        if os.path.exists(alt):
            return alt
    raise FileNotFoundError(f"Chybí font {name} ve složce fonts/")


# --- pozadí ------------------------------------------------------------------
def _noise(rng, h, w, sigma):
    return rng.normal(0, sigma, (h, w, 1)).astype(np.float32)


def _blob(rng, h, w, gh, gw, sigma):
    c = rng.normal(0, sigma, (gh, gw)).astype(np.float32)
    ci = Image.fromarray(np.uint8(np.clip(c + 128, 0, 255)))
    up = np.asarray(ci.resize((w, h), Image.Resampling.BICUBIC), dtype=np.float32) - 128
    return up[..., None]


def bg_desk(rng):
    """Původní světlá pracovní plocha."""
    h, w = CANVAS_H, CANVAS_W
    bg = np.zeros((h, w, 3), np.float32)
    bg[:, :] = (230, 226, 216)
    yy = np.linspace(-1, 1, h)[:, None]
    xx = np.linspace(-1, 1, w)[None, :]
    r = np.sqrt(xx ** 2 + yy ** 2)
    bg = bg * (1 - 0.05 * yy)[..., None] * (1 - 0.12 * np.clip(r - 0.7, 0, 1))[..., None]
    return np.clip(bg + _noise(rng, h, w, 3), 0, 255)


def bg_cork(rng):
    """Korková nástěnka."""
    h, w = CANVAS_H, CANVAS_W
    bg = np.zeros((h, w, 3), np.float32)
    bg[:, :] = (190, 145, 98)
    speck = rng.random((h, w))
    bg[speck > 0.93] *= 0.72
    bg[speck < 0.04] *= 1.12
    bg = bg + _blob(rng, h, w, 120, 70, 14) + _noise(rng, h, w, 6)
    small = Image.fromarray(np.uint8(np.clip(bg, 0, 255))).filter(ImageFilter.GaussianBlur(1.1))
    return np.asarray(small, np.float32)


def bg_wood(rng):
    """Dřevěný stůl."""
    h, w = CANVAS_H, CANVAS_W
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    warp = _blob(rng, h, w, 12, 8, 40)[..., 0]
    grain = np.sin((xx + warp * 1.5) / 7.0 + np.sin(yy / 160.0) * 2.0)
    base = np.array((150, 104, 70), np.float32)
    bg = base[None, None, :] * (1 + 0.08 * grain[..., None])
    # prkna
    plank = (xx // 270).astype(int)
    shade = np.array([1.0, 0.93, 1.05, 0.96, 1.02])[plank % 5]
    bg *= shade[..., None]
    bg[(xx % 270) < 3] *= 0.6
    return np.clip(bg + _noise(rng, h, w, 4), 0, 255)


def bg_grid(rng):
    """Čtverečkovaný papír z bloku."""
    h, w = CANVAS_H, CANVAS_W
    bg = np.zeros((h, w, 3), np.float32)
    bg[:, :] = (246, 245, 240)
    yy, xx = np.mgrid[0:h, 0:w]
    line = ((yy % 54) < 2) | ((xx % 54) < 2)
    bg[line] = (196, 214, 232)
    return np.clip(bg + _noise(rng, h, w, 2.5), 0, 255)


def bg_concrete(rng):
    """Tmavý beton (kontrast pro světlé lepíky)."""
    h, w = CANVAS_H, CANVAS_W
    bg = np.zeros((h, w, 3), np.float32)
    bg[:, :] = (78, 80, 86)
    bg = bg + _blob(rng, h, w, 40, 24, 10) + _blob(rng, h, w, 200, 120, 6) + _noise(rng, h, w, 5)
    return np.clip(bg, 0, 255)


BACKGROUNDS = [bg_desk, bg_cork, bg_wood, bg_grid, bg_concrete]


# --- lepík -------------------------------------------------------------------
def make_postit(w, h, color, rng, corner):
    arr = np.zeros((h, w, 3), np.float32)
    arr[:, :] = color
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    wrinkle = (np.sin(xx / 80.0 + yy / 200.0) + np.sin(xx / 160.0 - yy / 120.0)) * 5.0
    # horní lepicí proužek je o chlup tmavší (jako u skutečného post-itu)
    glue = np.where(yy < 70, -6.0, 0.0)
    arr = arr + _noise(rng, h, w, 3) + _blob(rng, h, w, 32, 24, 6) + (wrinkle + glue)[..., None]
    img = Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB").convert("RGBA")

    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=255)
    fold = 90
    if corner == "fold":
        md.polygon([(w - 1 - fold, h - 1), (w - 1, h - 1 - fold), (w - 1, h - 1)], fill=0)
    img.putalpha(mask)

    over = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    if corner == "fold":
        back = tuple(int(c * 0.82) for c in color)
        od.polygon([(w - 1 - fold, h - 1), (w - 1, h - 1 - fold), (w - 1, h - 1)], fill=back + (255,))
        od.line([(w - 1 - fold, h - 1), (w - 1, h - 1 - fold)], fill=(0, 0, 0, 70), width=4)
    elif corner == "curl":
        # spodní okraj se lehce zvedá -> světlo/stín gradient
        for i in range(140):
            a = int(60 * (i / 140) ** 2)
            od.line([(0, h - 140 + i), (w, h - 140 + i)], fill=(0, 0, 0, a // 3))
    return Image.alpha_composite(img, over)


# --- sazba textu s pointou ----------------------------------------------------
def split_punchline(quote):
    """Vrátí index slova, od kterého začíná pointa (poslední věta), nebo None."""
    parts = re.split(r"(?<=[.!?…])\s+|\s+[–—-]\s+|,\s+(?=ale |akorát |jen |škoda)", quote.strip())
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return None
    last = parts[-1]
    words = quote.split()
    n_last = len(last.split())
    if n_last < 2 or n_last > len(words) * 0.75:
        return None
    return len(words) - n_last


def layout(draw, words, font, max_w):
    lines, cur = [], []
    for i, w in enumerate(words):
        trial = " ".join(words[j] for j in cur + [i])
        if cur and draw.textlength(trial, font=font) > max_w:
            lines.append(cur)
            cur = [i]
        else:
            cur.append(i)
    if cur:
        lines.append(cur)
    return lines


def fit(draw, words, fname, scale, box_w, box_h):
    lo, hi, best = 40, 150, None
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(font_path(fname), int(mid * scale))
        lines = layout(draw, words, font, box_w)
        asc, desc = font.getmetrics()
        lh = int((asc + desc) * 1.12)
        if lh * len(lines) <= box_h:
            best = (font, lines, lh)
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        font = ImageFont.truetype(font_path(fname), int(40 * scale))
        lines = layout(draw, words, font, box_w)
        asc, desc = font.getmetrics()
        best = (font, lines, int((asc + desc) * 1.12))
    return best


def layout_quote(size, quote, rng, ink, fname, accent):
    """Připraví vrstvy textu na lepík (bez kreslení na papír).

    Vrací dict: text (RGBA vrstva s písmem), hl (RGBA vrstva se zvýrazněním nebo None),
    words [(x0, x1, y0, y1, je_pointa)], hl_rows [(x0, x1, y0, y1)].
    """
    w, h = size
    tmp = ImageDraw.Draw(Image.new("RGBA", size))
    words = quote.split()
    pad_x, pad_top, pad_bot = 80, 110, 90
    font, lines, lh = fit(tmp, words, fname, FONT_SCALE.get(fname, 1.0),
                          w - 2 * pad_x, h - pad_top - pad_bot)
    punch = split_punchline(quote)
    total = lh * len(lines)
    y0 = pad_top + (h - pad_top - pad_bot - total) // 2
    asc, desc = font.getmetrics()

    positions = []  # (x, y, text, is_punch)
    for li, line in enumerate(lines):
        text = " ".join(words[i] for i in line)
        lw = tmp.textlength(text, font=font)
        x = (w - lw) / 2
        y = y0 + li * lh
        for i in line:
            ww = words[i]
            positions.append((x, y, ww, punch is not None and i >= punch))
            x += tmp.textlength(ww + " ", font=font)

    hl_layer, hl_rows = None, []
    if punch is not None and accent != "none":
        hl_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        hd = ImageDraw.Draw(hl_layer)
        rows = {}
        for x, y, ww, is_p in positions:
            if is_p:
                x1 = x + tmp.textlength(ww, font=font)
                r = rows.setdefault(y, [x, x1])
                r[0], r[1] = min(r[0], x), max(r[1], x1)
        hcol = HIGHLIGHT[int(rng.integers(len(HIGHLIGHT)))]
        for y, (x0, x1) in rows.items():
            if accent == "marker":
                top = y + asc * 0.30 + rng.uniform(-4, 4)
                bot = y + asc + desc * 0.25 + rng.uniform(-4, 4)
                hd.polygon([(x0 - 14, top + rng.uniform(-5, 5)), (x1 + 14, top + rng.uniform(-5, 5)),
                            (x1 + 10, bot), (x0 - 10, bot)], fill=hcol + (150,))
            else:  # underline
                yb = y + asc + desc * 0.15
                pts = [(xx, yb + 5 * np.sin(xx / 22.0 + rng.uniform(0, 6)))
                       for xx in np.linspace(x0 - 6, x1 + 6, 40)]
                hd.line(pts, fill=accent_color(ink) + (230,), width=6, joint="curve")
            hl_rows.append((x0 - 20, x1 + 20, y - 10, y + lh + 10))
        hl_layer = hl_layer.filter(ImageFilter.GaussianBlur(1.2))

    text_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    wboxes = []
    for x, y, ww, is_p in positions:
        td.text((x, y), ww, font=font, fill=ink + (255,))
        x1 = x + tmp.textlength(ww, font=font)
        wboxes.append((x - 6, x1 + 10, y - 8, y + lh + 4, is_p, len(ww)))
    return {"text": text_layer, "hl": hl_layer, "words": wboxes, "hl_rows": hl_rows}


def draw_quote(note, quote, rng, ink, fname, accent):
    """Nakreslí hotový text na lepík (statický obrázek)."""
    L = layout_quote(note.size, quote, rng, ink, fname, accent)
    if L["hl"] is not None:
        note.alpha_composite(L["hl"])
    note.alpha_composite(L["text"])


def accent_color(ink):
    return (200, 40, 40) if ink != (200, 40, 40) else (30, 58, 140)


# --- doplňky: páska / špendlík ---------------------------------------------------
def tape(rng, w=300, h=86):
    col = [(245, 240, 225), (240, 200, 210), (200, 225, 240), (230, 230, 200)][int(rng.integers(4))]
    t = Image.new("RGBA", (w, h), col + (190,))
    td = ImageDraw.Draw(t)
    # zubaté konce
    for y in range(0, h, 8):
        td.polygon([(0, y), (int(rng.integers(4, 12)), y + 4), (0, y + 8)], fill=(0, 0, 0, 0))
        td.polygon([(w, y), (w - int(rng.integers(4, 12)), y + 4), (w, y + 8)], fill=(0, 0, 0, 0))
    for _ in range(6):
        y = int(rng.integers(0, h))
        td.line([(0, y), (w, y)], fill=(255, 255, 255, 25), width=2)
    return t


def pin(rng):
    col = [(220, 50, 50), (40, 120, 220), (40, 170, 90), (240, 190, 40)][int(rng.integers(4))]
    p = Image.new("RGBA", (90, 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    d.ellipse([18, 22, 78, 82], fill=(0, 0, 0, 70))
    d.ellipse([12, 12, 72, 72], fill=col + (255,))
    d.ellipse([24, 20, 44, 36], fill=(255, 255, 255, 120))
    return p.filter(ImageFilter.GaussianBlur(0.6))


# --- značka stránky --------------------------------------------------------------
def brand_label(handle, style, rng):
    """Výrazný štítek s handle (dřív malý šedý text na lepíku)."""
    f = ImageFont.truetype(font_path(BRAND_FONT), 76)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tw = int(tmp.textlength(handle, font=f))
    pad_x, hgt = 50, 116
    w = tw + 2 * pad_x
    lab = Image.new("RGBA", (w, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(lab)
    if style == "dark":
        d.rounded_rectangle([0, 0, w - 1, hgt - 1], radius=18, fill=BRAND_BG + (240,))
        d.rectangle([0, 0, w - 1, 9], fill=BRAND_ACCENT + (255,))
        d.text((w // 2, hgt // 2 + 6), handle, font=f, fill=(255, 255, 255, 255), anchor="mm")
    else:  # žlutá páska s černým písmem
        d.rectangle([0, 0, w - 1, hgt - 1], fill=BRAND_ACCENT + (235,))
        for y in range(0, hgt, 8):
            d.polygon([(0, y), (int(rng.integers(4, 12)), y + 4), (0, y + 8)], fill=(0, 0, 0, 0))
            d.polygon([(w, y), (w - int(rng.integers(4, 12)), y + 4), (w, y + 8)], fill=(0, 0, 0, 0))
        d.text((w // 2, hgt // 2 + 6), handle, font=f, fill=(26, 26, 34, 255), anchor="mm")
    return lab


def drop_shadow(size, radius, blur, alpha, lift):
    w, h = size
    s = Image.new("RGBA", (w + 160, h + 160), (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle([80, 80 + lift, w + 80, h + 80 + lift],
                                        radius=radius, fill=(30, 20, 10, alpha))
    return s.filter(ImageFilter.GaussianBlur(blur))


# --- hlavní render -----------------------------------------------------------------
def build_scene(quote, seed=1, handle=HANDLE_IG, color=None, angle=None):
    """Rozloží lepík na vrstvy, aby šel animovat. Pořadí náhodných voleb je
    stejné jako dřív, takže hotový obrázek vypadá vždy stejně."""
    rng = np.random.default_rng(seed * 7919 + 17)

    bg_fn = BACKGROUNDS[int(rng.integers(len(BACKGROUNDS)))]
    canvas = Image.fromarray(np.uint8(bg_fn(rng)), "RGB").convert("RGBA")

    if color is None:
        color = POSTIT_COLORS[int(rng.integers(len(POSTIT_COLORS)))]
    if angle is None:
        angle = float(rng.uniform(-5, 5))
    ink = INKS[int(rng.integers(len(INKS)))]
    fname = QUOTE_FONTS[int(rng.choice(len(QUOTE_FONTS), p=FONT_WEIGHTS))]
    corner = ["fold", "curl", "plain"][int(rng.integers(3))]
    attach = ["tape", "pin", "tape2", "none"][int(rng.integers(4))]
    accent = ["marker", "underline", "none"][int(rng.choice(3, p=[0.45, 0.30, 0.25]))]

    note_w, note_h = (880, 960) if rng.random() < 0.5 else (880, 1060)
    paper = make_postit(note_w, note_h, color, rng, corner)
    L = layout_quote(paper.size, quote, rng, ink, fname, accent)

    cx, cy = CANVAS_W // 2 + int(rng.integers(-25, 26)), 880
    lift = 26 if attach == "none" else 16
    sh = drop_shadow((note_w, note_h), 10, 26, 120, lift).rotate(angle, expand=True)
    canvas.alpha_composite(sh, (cx - sh.width // 2, cy - sh.height // 2 + 14))

    over = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))   # věci NAD lepíkem
    top_y = cy - note_h // 2
    if attach == "tape":
        t = tape(rng).rotate(angle + rng.uniform(-6, 6), expand=True, resample=Image.Resampling.BICUBIC)
        over.alpha_composite(t, (cx - t.width // 2, top_y - t.height // 2 + 6))
    elif attach == "tape2":
        for sx, a in ((-1, -38), (1, 38)):
            t = tape(rng, 230, 74).rotate(a + rng.uniform(-5, 5), expand=True, resample=Image.Resampling.BICUBIC)
            over.alpha_composite(t, (cx + sx * (note_w // 2 - 40) - t.width // 2, top_y - t.height // 2 + 30))
    elif attach == "pin":
        over.alpha_composite(pin(rng), (cx - 45, top_y - 10))

    lab = brand_label(handle, "dark" if rng.random() < 0.5 else "tape", rng)
    lab = lab.rotate(float(rng.uniform(-3, 3)), expand=True, resample=Image.Resampling.BICUBIC)
    over.alpha_composite(lab, ((CANVAS_W - lab.width) // 2, cy + note_h // 2 + 70))

    return {"bg": canvas, "paper": paper, "L": L, "over": over, "angle": angle,
            "center": (cx, cy),
            "info": f"[{bg_fn.__name__[3:]}, {fname.split('-')[0].split('.')[0]}, {corner}, {attach}, {accent}]"}


def note_layer(scene, text_mask=None, hl_mask=None):
    """Lepík s textem (a zvýrazněním), už natočený. Masky = L obrázky (None = celé)."""
    L = scene["L"]
    note = scene["paper"].copy()
    if L["hl"] is not None:
        hl = L["hl"]
        if hl_mask is not None:
            hl = hl.copy()
            hl.putalpha(ImageChops.multiply(hl.getchannel("A"), hl_mask))
        note.alpha_composite(hl)
    txt = L["text"]
    if text_mask is not None:
        txt = txt.copy()
        txt.putalpha(ImageChops.multiply(txt.getchannel("A"), text_mask))
    note.alpha_composite(txt)
    return note.rotate(scene["angle"], expand=True, resample=Image.Resampling.BICUBIC)


def finish(scene, rot):
    cx, cy = scene["center"]
    canvas = scene["bg"].copy()
    canvas.alpha_composite(rot, (cx - rot.width // 2, cy - rot.height // 2))
    canvas.alpha_composite(scene["over"])
    return canvas.convert("RGB")


def compose(scene, text_mask=None, hl_mask=None):
    """Složí celý snímek."""
    return finish(scene, note_layer(scene, text_mask, hl_mask))


def render(quote, out_path, color=None, angle=None, seed=1, handle=HANDLE_IG):
    """Hotový (statický) lepík – stejná signatura jako původní render.py."""
    scene = build_scene(quote, seed, handle, color, angle)
    img = compose(scene)
    if out_path is None:
        return img
    img.save(out_path, quality=95)
    print("uloženo:", os.path.basename(out_path), scene["info"])


# --- animace „psaní perem“ ------------------------------------------------------------
CPS = 15.0            # rychlost psaní: znaků za sekundu (zrychlené psaní)
MAX_WRITE = 4.2       # s – delší citáty se píšou rychleji, aby psaní netrvalo déle
WORD_GAP = 0.06       # s – pauza mezi slovy (pero se zvedne)
LINE_GAP = 0.15       # s – přechod na další řádek
PUNCH_GAP = 0.55      # s – dramatická pauza před pointou
HL_DUR = 0.45         # s – tažení zvýrazňovače
START = 0.35          # s – prázdný lepík na začátku
READ_HOLD = 3.5       # s – čas na dočtení po dopsání
MIN_LEN = 8.0         # s – minimální délka videa
EDGE = 14             # px – měkký okraj „inkoustu“


def write_schedule(L):
    """Časový plán psaní jednotlivých slov: [(t0, t1, box)]."""
    words = L["words"]
    nchar = sum(wb[5] for wb in words) or 1
    cps = max(CPS, nchar / MAX_WRITE)
    t = START
    plan = []
    prev = None
    for wb in words:
        if prev is not None:
            if wb[4] and not prev[4]:
                t += PUNCH_GAP
            elif wb[2] != prev[2]:
                t += LINE_GAP
            else:
                t += WORD_GAP
        dur = max(wb[5], 1) / cps
        plan.append((t, t + dur, wb))
        t += dur
        prev = wb
    return plan, t


def _wipe_mask(size, boxes_progress):
    """L maska: pro každý box (x0,x1,y0,y1) a podíl p odkryje zleva p*šířky s měkkým okrajem."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for (x0, x1, y0, y1), p in boxes_progress:
        if p <= 0:
            continue
        xe = x0 + (x1 - x0) * min(p, 1.0)
        if p >= 1:
            d.rectangle([x0, y0, x1, y1], fill=255)
            continue
        d.rectangle([x0, y0, max(x0, xe - EDGE), y1], fill=255)
        for k in range(EDGE):
            xx = xe - EDGE + k
            if xx >= x0:
                d.line([(xx, y0), (xx, y1)], fill=int(255 * (1 - k / EDGE)))
    return m


def animate(quote, seed, handles=(HANDLE_IG,), fps=30):
    """Animace psaní. Pro víc handle (IG, FB) se lepík počítá jen jednou.

    Vrací (generátor, počet_snímků); generátor dává n-tice snímků, jeden pro každý handle.
    """
    if isinstance(handles, str):
        handles = (handles,)
    scenes = [build_scene(quote, seed, h) for h in handles]
    sc0 = scenes[0]
    L = sc0["L"]
    size = sc0["paper"].size
    plan, t_end = write_schedule(L)
    hl_rows = L["hl_rows"]
    t_hl = t_end + 0.15
    t_done = t_hl + (HL_DUR if hl_rows else 0)
    total = max(MIN_LEN, t_done + READ_HOLD)
    n = int(round(total * fps))
    hl_total = sum(r[1] - r[0] for r in hl_rows) or 1

    def gen():
        last_key, last = None, None
        for f in range(n):
            t = f / fps
            key = "done" if t >= t_done else round(t, 3)
            if key != last_key:
                if key == "done":
                    rot = note_layer(sc0)
                else:
                    prog = [((b[0], b[1], b[2], b[3]), (t - t0) / max(t1 - t0, 1e-6))
                            for t0, t1, b in plan]
                    hm = None
                    if hl_rows:
                        budget = max(0.0, (t - t_hl) / HL_DUR) * hl_total
                        hp = []
                        for r in hl_rows:
                            wdt = r[1] - r[0]
                            hp.append((r, max(0.0, min(1.0, budget / wdt))))
                            budget -= wdt
                        hm = _wipe_mask(size, hp)
                    rot = note_layer(sc0, _wipe_mask(size, prog), hm)
                last = tuple(finish(sc, rot) for sc in scenes)
                last_key = key
            yield last
    return gen(), n


# --- CLI ---------------------------------------------------------------------------
def _arg(name, default=None):
    if name in sys.argv:
        return int(sys.argv[sys.argv.index(name) + 1])
    return default


def main():
    sys.path.insert(0, HERE)
    from quotes_loader import build_order

    mode = sys.argv[1] if len(sys.argv) > 1 else "first"
    order = build_order()
    if not order:
        print("V quotes.txt nejsou žádné citáty.")
        return

    if mode == "missing":
        # pro nové citáty: dorenderuje jen chybějící PNG (od pozice 30 = styl v2)
        start = _arg("--from", 30)
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        n = 0
        for i, (qid, q, cat) in enumerate(order, 1):
            if i < start:
                continue
            for tag, h in (("ig", HANDLE_IG), ("fb", HANDLE_FB)):
                p = os.path.join(HERE, "out", f"{tag}_{i:03d}.png")
                if not os.path.exists(p):
                    render(q, p, seed=i, handle=h)
                    n += 1
        print("Hotovo, nových obrázků:", n)
    elif mode == "both":
        start = _arg("--from")
        if start is None:
            print("Zadej --from N (od které pozice přegenerovat). Starší se nepřepíšou.")
            return
        end = _arg("--to", len(order))
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        for i, (qid, q, cat) in enumerate(order, 1):
            if i < start or i > end:
                continue
            render(q, os.path.join(HERE, "out", f"ig_{i:03d}.png"), seed=i, handle=HANDLE_IG)
            render(q, os.path.join(HERE, "out", f"fb_{i:03d}.png"), seed=i, handle=HANDLE_FB)
        print(f"Hotovo: pozice {start}–{end}")
    elif mode == "sample":
        os.makedirs(os.path.join(HERE, "preview"), exist_ok=True)
        start = _arg("--from", 1)
        for i in range(start, min(start + 8, len(order) + 1)):
            render(order[i - 1][1], os.path.join(HERE, "preview", f"v2_{i:03d}.png"), seed=i)
    else:
        render(order[0][1], os.path.join(HERE, "preview.png"), seed=1)


if __name__ == "__main__":
    main()
