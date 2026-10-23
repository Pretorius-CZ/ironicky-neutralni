#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Z PNG udělá krátké vertikální video (jemný zoom + fade) s hudbou.

Použití:
    python make_video.py vstup.png hudba.mp3 [vystup.mp4]
    python make_video.py              # dávkově: out/ig_*.png a out/fb_*.png -> video/
                                      # hudba se střídá mezi *.mp3 v projektu
"""
import os
import sys
import glob
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(HERE, "ffmpeg.exe")

DURATION = 8.0
FPS = 30


def make_video(png, mp3, out_mp4, duration=DURATION, fps=FPS):
    frames = int(duration * fps)
    fade_out = duration - 0.8
    vf = (
        "scale=4320:7680,"
        f"zoompan=z='min(zoom+0.00035,1.10)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
        "format=yuv420p,"
        f"fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out:.2f}:d=0.8"
    )
    cmd = [
        FFMPEG, "-y", "-loglevel", "error", "-nostats",
        "-i", png,
        "-i", mp3,
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "1:a",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-b:a", "128k",
        "-af", f"afade=t=in:st=0:d=0.3,afade=t=out:st={fade_out:.2f}:d=0.8",
        "-movflags", "+faststart",
        out_mp4,
    ]
    subprocess.run(cmd, check=True)
    print("OK:", out_mp4)


def main():
    if len(sys.argv) >= 3:
        png = sys.argv[1]
        mp3 = sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(png)[0] + ".mp4"
        make_video(png, mp3, out)
        return

    mp3s = sorted(glob.glob(os.path.join(HERE, "*.mp3")))
    if not mp3s:
        print("V projektu nejsou žádné MP3.")
        return
    pngs = sorted(
        glob.glob(os.path.join(HERE, "out", "ig_*.png"))
        + glob.glob(os.path.join(HERE, "out", "fb_*.png"))
    )
    if not pngs:
        print("V out/ nejsou žádné obrázky (spusť nejdřív render.py both).")
        return
    os.makedirs(os.path.join(HERE, "video"), exist_ok=True)
    for i, png in enumerate(pngs):
        mp3 = mp3s[i % len(mp3s)]
        name = os.path.splitext(os.path.basename(png))[0]
        out = os.path.join(HERE, "video", name + ".mp4")
        make_video(png, mp3, out)


if __name__ == "__main__":
    main()
