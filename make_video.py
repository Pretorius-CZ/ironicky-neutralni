# -*- coding: utf-8 -*-
"""Z PNG udělá krátké vertikální video (jemný zoom + fade) s hudbou.

Generuje jen CHYBĚJÍCÍ videa (append-only), takže stará se nedělají znovu.

Použití:
    python make_video.py vstup.png hudba.mp3 [vystup.mp4]
    python make_video.py              # dávkově: chybějící videa do video/
"""
import os
import sys
import glob
import subprocess

from quotes_loader import build_order

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
    print("OK:", os.path.basename(out_mp4))


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
    order = build_order()
    if not order:
        print("Žádné citáty.")
        return
    os.makedirs(os.path.join(HERE, "video"), exist_ok=True)
    for i, (qid, q, cat) in enumerate(order, 1):
        mp3 = mp3s[(i - 1) % len(mp3s)]
        for tag in ("ig", "fb"):
            png = os.path.join(HERE, "out", f"{tag}_{i:03d}.png")
            mp4 = os.path.join(HERE, "video", f"{tag}_{i:03d}.mp4")
            if os.path.exists(mp4) or not os.path.exists(png):
                continue
            make_video(png, mp3, mp4)


if __name__ == "__main__":
    main()
