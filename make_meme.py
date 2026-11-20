# -*- coding: utf-8 -*-
"""Meme video (anglický text nad klipem) -> česká verze v šabloně stránky.

- najde klip a anglický text nad ním (automaticky, z jednoho snímku),
- text překryje černou a napíše český (slova v *hvězdičkách* = žlutě),
- nahoře vodoznak, dole zápatí SLEDUJ + FB/IG (jako make_reel.py),
- výstup 1080x1920, původní zvuk.

Použití:
    python make_meme.py vstup.mp4 vystup.mp4 "Já každé ráno *před prací*"
    (víc řádků textu: oddělit znakem |)
"""
import os
import sys
import shutil
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(HERE, "ffmpeg.exe")
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FONT = os.path.join(HERE, "fonts_v2", "Inter.ttf")

W, H = 1080, 1920
YELLOW = (255, 210, 80, 255)
WHITE = (255, 255, 255, 255)
GREY = (150, 150, 165, 255)
IG_HANDLE = "@ironicky_neutralni"
FB_HANDLE = "@ironickyneutralni"


def font(size, weight="Medium"):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


# --- rozpoznání rozložení -----------------------------------------------------------
def grab(video, t):
    p = subprocess.run([FFMPEG, "-loglevel", "error", "-ss", str(t), "-i", video,
                        "-frames:v", "1", "-vf", f"scale={W}:{H}", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(p, np.uint8).reshape(H, W, 3)


def detect_layout(video):
    """Vrátí (clip_top, clip_bottom, text_top, text_bottom) v pixelech 1080x1920."""
    frames = [grab(video, t) for t in (0.6, 1.5, 3.0)]
    f = np.mean([fr.astype(np.float32) for fr in frames], axis=0)
    gray = f.mean(axis=2)
    filled = (gray > 18).mean(axis=1)          # podíl ne-černých pixelů v řádku
    rows = np.where(filled > 0.6)[0]           # řádky, kde je obraz klipu
    # největší souvislý blok = klip
    blocks, start = [], rows[0]
    for a, b in zip(rows, rows[1:]):
        if b != a + 1:
            blocks.append((start, a)); start = b
    blocks.append((start, rows[-1]))
    clip_top, clip_bot = max(blocks, key=lambda x: x[1] - x[0])
    # text = světlé pixely nad klipem
    bright = (gray[:clip_top] > 140).sum(axis=1) > 3
    trows = np.where(bright)[0]
    trows = trows[trows > 120]                 # ignoruj případný vodoznak úplně nahoře
    if len(trows):
        text_top, text_bot = int(trows[0]), int(trows[-1])
    else:
        text_top = text_bot = clip_top - 40
    return int(clip_top), int(clip_bot), text_top, text_bot


# --- text s *zvýrazněním* -------------------------------------------------------------
def tokens(line):
    """Slova se zvýrazněním; jednopísmenné předložky (v, z, k, s, a, i, o, u)
    se přilepí k dalšímu slovu, aby nezůstaly na konci řádku."""
    out, hl = [], False
    for part in line.split("*"):
        for w in part.split():
            out.append((w, hl))
        hl = not hl
    merged = []
    for w, h in out:
        if merged and merged[-1][0].lower() in ("v", "z", "k", "s", "a", "i", "o", "u") \
                and merged[-1][1] == h:
            merged[-1] = (merged[-1][0] + "\u00a0" + w, h)
        else:
            merged.append((w, h))
    return merged


def wrap(draw, toks, f, maxw):
    lines, cur = [], []
    for t in toks:
        trial = " ".join(w for w, _ in cur + [t])
        if cur and draw.textlength(trial, font=f) > maxw:
            lines.append(cur); cur = [t]
        else:
            cur.append(t)
    if cur:
        lines.append(cur)
    return lines


def text_overlay(text, clip_top, text_top):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    margin = 58
    paragraphs = [p.strip() for p in text.split("|")]
    size = 52
    while True:
        f = font(size)
        lh = int(size * 1.32)
        blocks = [wrap(d, tokens(p), f, W - 2 * margin) for p in paragraphs]
        total = sum(len(b) for b in blocks) * lh + (len(blocks) - 1) * int(lh * 0.6)
        if clip_top - 34 - total > 210 or size <= 34:
            break
        size -= 2
    # černá plocha přes původní text (od textu až ke klipu)
    cover_top = min(text_top - 30, clip_top - 34 - total - 20)
    d.rectangle([0, max(160, cover_top), W, clip_top - 2], fill=(0, 0, 0, 255))
    y = clip_top - 34 - total
    for bi, b in enumerate(blocks):
        for line in b:
            lw = d.textlength(" ".join(w for w, _ in line), font=f)
            x = (W - lw) / 2                     # zarovnání na střed
            for w, hl in line:
                d.text((x, y), w, font=f, fill=YELLOW if hl else WHITE)
                x += d.textlength(w + " ", font=f)
            y += lh
        y += int(lh * 0.6)
    return ov


# --- vodoznak + zápatí (stejné jako make_reel.py) ------------------------------------
def fb_icon(size=40):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=(24, 119, 242, 255))
    d.text((size / 2, size / 2 + 1), "f", font=font(int(size * 0.82), "Bold"), fill=WHITE, anchor="mm")
    return img


def ig_icon(size=40):
    grad = Image.new("RGB", (size, size))
    px = grad.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = (int(250 - 80 * t), int(180 - 120 * t), int(60 + 130 * t))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=9, fill=255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 10, size - 8, size - 8], radius=5, outline=WHITE, width=2)
    d.ellipse([size // 2 - 7, size // 2 - 7, size // 2 + 7, size // 2 + 7], outline=WHITE, width=2)
    d.ellipse([size - 14, 8, size - 10, 12], fill=WHITE)
    return img


def brand_overlay(ov, clip_bot):
    d = ImageDraw.Draw(ov)
    wm = font(30, "Bold")
    tw = d.textlength("ironicky_neutralni", font=wm)
    d.text(((W - tw) // 2, 78), "ironicky_neutralni", font=wm, fill=(255, 255, 255, 150))
    y0 = max(clip_bot + 60, 1600)
    d.rectangle([0, clip_bot + 2, W, H], fill=(0, 0, 0, 255))   # zakryje cizí zápatí
    d.rectangle([(W - 220) // 2, y0, (W + 220) // 2, y0 + 4], fill=YELLOW)
    f2 = font(26, "Bold")
    w = d.textlength("SLEDUJ", font=f2)
    d.text(((W - w) // 2, y0 + 18), "SLEDUJ", font=f2, fill=YELLOW)

    def line(y, icon, handle):
        fh = font(34, "Bold")
        hw = int(d.textlength(handle, font=fh))
        x = int((W - (icon.width + 14 + hw)) / 2)
        ov.alpha_composite(icon, (x, int(y) - 3))
        d.text((x + icon.width + 14, int(y)), handle, font=fh, fill=WHITE)

    line(y0 + 58, fb_icon(40), FB_HANDLE)
    line(y0 + 112, ig_icon(40), IG_HANDLE)
    f4 = font(22, "Regular")
    w = d.textlength("denní dávka ironie", font=f4)
    d.text(((W - w) // 2, y0 + 172), "denní dávka ironie", font=f4, fill=GREY)
    return ov


SQUEEZE = 0.85   # zúžení klipu (zdroje bývají roztažené do šířky); 1.0 = beze změny


def _vf(ct, cb, sq):
    """Klip (řádky ct..cb) zúží na sq šířky a vycentruje na černém pozadí."""
    ch = cb - ct + 1
    nw = int(W * sq) // 2 * 2
    return (f"[0:v]scale={W}:{H},setsar=1,split[a][b];"
            f"[a]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill[bg];"
            f"[b]crop={W}:{ch}:0:{ct},scale={nw}:{ch}[c];"
            f"[bg][c]overlay=({W}-{nw})/2:{ct}[m];"
            f"[m][1:v]overlay=0:0[v]")


def make(video, out, text, overlay_png=None, squeeze=None):
    squeeze = SQUEEZE if squeeze is None else squeeze
    clip_top, clip_bot, text_top, text_bot = detect_layout(video)
    ov = text_overlay(text, clip_top, text_top)
    ov = brand_overlay(ov, clip_bot)
    ovp = overlay_png or os.path.splitext(out)[0] + "_overlay.png"
    ov.save(ovp)
    subprocess.run([
        FFMPEG, "-y", "-loglevel", "error", "-i", video, "-i", ovp,
        "-filter_complex", _vf(clip_top, clip_bot, squeeze),
        "-map", "[v]", "-map", "0:a?", "-r", "30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        "-map_metadata", "-1", out,
    ], check=True)
    if overlay_png is None:
        os.remove(ovp)
    print(f"OK: {os.path.basename(out)} (klip {clip_top}-{clip_bot}, text {text_top}-{text_bot})")


if __name__ == "__main__":
    make(sys.argv[1], sys.argv[2], sys.argv[3])
