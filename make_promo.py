# -*- coding: utf-8 -*-
"""Promo slideshow (Story/Reel): úvod -> náhodné lepíky padají do rytmu -> CTA.

Vygeneruje 5 variant pro IG i FB (každá s náhodnými lepíky a jinou CTA).
Výstup:   video/promo_story_{ig|fb}_{1..5}.mp4
"""
import os
import glob
import random
import shutil
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(HERE, "ffmpeg.exe")
W, H = 1080, 1920
FPS = 30

PAGE_NAME = "ironicky neutralni"
PLATFORMS = {
    "ig": "@ironicky_neutralni",
    "fb": "@ironickyneutralni",
}

FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"

MUSIC = "DIMMYSAD - Rocking Forward.mp3"

N = 6
FALL = 0.30
INTRO_END = 1.5
XFADE_IN = 0.30
HOLD = 0.35
XFADE = 0.40
CTA_HOLD = 2.4

TILTS = [-7, 6, -5, 8, -6, 7]
OFFS = [(0, 0), (110, 70), (-120, -60), (95, 85), (-105, -55), (120, 60)]
CARD_SCALE = 0.75
CROP_W, CROP_H = 960, 1220

VARIANTS = 5                                     # 5 různých CTA
INTROS = [f"out/intro_{i}.png" for i in range(1, 9)]   # střídavé úvody


def music_path():
    for name in ("promo_music.mp3", MUSIC):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            return p
    mp3s = sorted(glob.glob(os.path.join(HERE, "*.mp3")))
    return mp3s[0] if mp3s else None


def get_onsets(mp3_path, limit=24):
    wav = os.path.join(HERE, "_beat_tmp.wav")
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", mp3_path,
         "-ac", "1", "-ar", "22050", "-t", "25", wav],
        check=True,
    )
    with wave.open(wav, "rb") as w:
        sr = w.getframerate()
        data = w.readframes(w.getnframes())
    os.remove(wav)

    x = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    frame, hop = 1024, 256
    nf = 1 + (len(x) - frame) // hop
    energy = np.array([
        np.sqrt(np.mean(x[i * hop:i * hop + frame] ** 2)) for i in range(nf)
    ])
    energy = np.log1p(energy)
    onset = np.maximum(0, np.diff(energy))
    onset = onset - onset.mean()
    fps = sr / hop

    ac = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
    min_lag = int(fps * 60 / 170)
    max_lag = int(fps * 60 / 70)
    lag = min_lag + int(np.argmax(ac[min_lag:max_lag]))
    beat = lag / fps

    min_dist = int(fps * beat * 0.6)
    thr = onset.max() * 0.35
    peaks = []
    for i in range(1, len(onset) - 1):
        if onset[i] > onset[i - 1] and onset[i] >= onset[i + 1] and onset[i] > thr:
            if not peaks or i - peaks[-1] >= min_dist:
                peaks.append(i)

    times = [p / fps for p in peaks]
    times = [t for t in times if t >= 0.30]
    return times[:limit], beat


def make_bg():
    bg = np.zeros((H, W, 3), dtype=np.float32)
    bg[:, :] = (24, 24, 32)
    yy = np.linspace(-1, 1, H)[:, None]
    xx = np.linspace(-1, 1, W)[None, :]
    r = np.sqrt(xx ** 2 + yy ** 2)
    vig = 1 - 0.18 * np.clip(r - 0.5, 0, 1)
    bg = bg * vig[..., None]
    bg = np.clip(bg + np.random.default_rng(1).normal(0, 2, (H, W, 1)), 0, 255)
    return Image.fromarray(bg.astype(np.uint8), "RGB").convert("RGBA")


def make_cta(handle, variant):
    """5 různých podob závěrečné CTA karty."""
    img = Image.new("RGB", (W, H), (26, 26, 34))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 16], fill=(255, 210, 80))
    yellow = (255, 210, 80)
    white = (255, 255, 255)
    grey = (150, 150, 165)

    def line(text, size, y, color):
        f = ImageFont.truetype(FONT_BOLD, size)
        w = d.textlength(text, font=f)
        while w > W - 80 and size > 24:
            size -= 4
            f = ImageFont.truetype(FONT_BOLD, size)
            w = d.textlength(text, font=f)
        d.text(((W - w) // 2, y), text, font=f, fill=color)

    v = variant % 5
    if v == 0:
        line("SLEDUJ", 230, 600, yellow)
        line(handle, 100, 930, white)
        line(PAGE_NAME, 60, 1080, grey)
        d.polygon([(540, 1250), (605, 1185), (475, 1185)], fill=yellow)
    elif v == 1:
        line("SLEDUJ", 230, 560, yellow)
        line("PRO VÍC", 140, 880, white)
        line(handle, 80, 1120, grey)
    elif v == 2:
        line("PŘIDEJ SE", 170, 640, yellow)
        line(handle, 85, 920, white)
        d.polygon([(540, 1200), (605, 1135), (475, 1135)], fill=yellow)
    elif v == 3:
        line("DENNÍ DÁVKA", 130, 560, white)
        line("IRONIE", 230, 760, yellow)
        line(handle, 90, 1180, grey)
    else:
        line("TOHLE JE JEN", 120, 540, white)
        line("ZAČÁTEK", 210, 700, yellow)
        line(handle, 85, 1080, white)
        d.polygon([(540, 1260), (605, 1195), (475, 1195)], fill=yellow)

    return img.convert("RGBA")


def load_cards():
    """Náhodně vybere 6 lepíků z out/ig_*.png."""
    imgs = sorted(glob.glob(os.path.join(HERE, "out", "ig_*.png")))
    if len(imgs) < N:
        return []
    pick = random.sample(imgs, N)

    cards = []
    for p, tilt in zip(pick, TILTS):
        img = Image.open(p).convert("RGB")
        left = (img.width - CROP_W) // 2
        top = (img.height - CROP_H) // 2
        crop = img.crop((left, top, left + CROP_W, top + CROP_H))
        crop = crop.resize(
            (int(CROP_W * CARD_SCALE), int(CROP_H * CARD_SCALE)), Image.LANCZOS
        )
        crop = crop.convert("RGBA")
        rot = crop.rotate(
            tilt, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0)
        )
        cards.append(rot)
    return cards


def build_one(platform, handle, cards, intro, bg, land_times, music, total, variant):
    cta = make_cta(handle, variant)
    nframes = int(total * FPS)
    frame_dir = os.path.join(HERE, "out", f"pf_{platform}_{variant}")
    if os.path.exists(frame_dir):
        shutil.rmtree(frame_dir)
    os.makedirs(frame_dir)

    last_land = land_times[-1]
    cta_start = last_land + HOLD
    cta_end = cta_start + XFADE
    xfade_end = INTRO_END + XFADE_IN

    for f in range(nframes):
        t = f / FPS

        if intro is not None and t < INTRO_END:
            canvas = intro.copy()
        elif intro is not None and t < xfade_end:
            p = (t - INTRO_END) / XFADE_IN
            canvas = Image.blend(intro, bg, p)
        else:
            canvas = bg.copy()

        if intro is None or t >= xfade_end:
            for i, card in enumerate(cards):
                lt = land_times[i]
                st = lt - FALL
                if t < st:
                    continue
                if t >= lt:
                    ease = 1.0
                else:
                    p = (t - st) / FALL
                    ease = 1 - (1 - p) ** 3

                cx = W // 2 + OFFS[i][0]
                cy = H // 2 + OFFS[i][1]
                tl_x = cx - card.width // 2
                tl_y_final = cy - card.height // 2
                tl_y = (-card.height) + (tl_y_final + card.height) * ease
                canvas.alpha_composite(card, (tl_x, int(tl_y)))

        if t >= cta_start:
            a = 1.0 if t >= cta_end else (t - cta_start) / XFADE
            if a >= 1.0:
                canvas = cta.copy()
            else:
                canvas = Image.blend(canvas, cta, a)

        canvas.convert("RGB").save(os.path.join(frame_dir, f"f_{f:04d}.png"))

    out = os.path.join(HERE, "video", f"promo_story_{platform}_{variant + 1}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [
        FFMPEG, "-y", "-loglevel", "error", "-nostats",
        "-framerate", str(FPS), "-start_number", "0",
        "-i", os.path.join(frame_dir, "f_%04d.png"),
        "-i", music,
        "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-af", f"afade=t=in:st=0:d=0.2,afade=t=out:st={total - 0.7:.2f}:d=0.7",
        "-shortest", "-movflags", "+faststart",
        out,
    ]
    subprocess.run(cmd, check=True)
    shutil.rmtree(frame_dir, ignore_errors=True)
    print("OK:", out)


def main():
    music = music_path()
    if not music:
        print("Chybi MP3.")
        return
    bg = make_bg()

    all_times, beat = get_onsets(music, 24)
    xfade_end = INTRO_END + XFADE_IN
    land_times = [t for t in all_times if t - FALL >= xfade_end][:N]
    if len(land_times) < N:
        land_times = [xfade_end + FALL + i * beat for i in range(N)]
    total = land_times[-1] + HOLD + XFADE + CTA_HOLD

    print("BPM ~", round(60.0 / beat, 1), "| celkem", round(total, 1), "s")
    for v in range(VARIANTS):
        cards = load_cards()
        if not cards:
            print("Malo obrazku v out/ (spust regen.bat).")
            return
        intro_path = os.path.join(HERE, random.choice(INTROS))
        intro = (
            Image.open(intro_path).convert("RGBA")
            if os.path.exists(intro_path) else None
        )
        for platform, handle in PLATFORMS.items():
            build_one(platform, handle, cards, intro, bg, land_times, music, total, v)


if __name__ == "__main__":
    main()
