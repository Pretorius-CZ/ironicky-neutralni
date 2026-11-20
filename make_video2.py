# -*- coding: utf-8 -*-
"""Video z lepíku v2: víc hudby, chytřejší výběr úseku, srovnaná hlasitost.

Hudba:
  - MP3 dej do složky music/ (případně do podsložek podle kategorie:
    music/lide, music/prace, music/zivot, music/drze — pokud podsložka
    existuje a není prázdná, citáty z té kategorie berou hudbu odtud).
  - Když music/ neexistuje, použijí se MP3 z kořene projektu (jako dřív).
  - Skladba se vybírá podle pořadového čísla citátu (stabilně: stejný citát
    = stejná skladba), ale už ne dokola 1-2-3-1-2-3.
  - Z písně se nebere začátek, ale nejživější 8s úsek (refrén / drop),
    zarovnaný na úder.
  - Hlasitost se srovná (loudnorm), takže všechny skladby hrají stejně nahlas.

Použití:
    python make_video2.py                    # jen CHYBĚJÍCÍ videa (jako dřív)
    python make_video2.py --from 30 --to 90  # PŘEGENERUJE videa v rozsahu
    (od pozice 30 se videa dělají s animací psaní; --static = bez animace)
    python make_video2.py --test             # 6 zkušebních videí do preview/
"""
import os
import sys
import glob
import json
import wave
import hashlib
import shutil
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(HERE, "ffmpeg.exe")
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
MUSIC_DIR = os.path.join(HERE, "music")
CACHE = os.path.join(HERE, "music_cache.json")   # spočítané začátky úseků

DURATION = 8.0
FPS = 30
CATEGORY_NAMES = ["lide", "prace", "zivot", "drze"]


# --- výběr hudby -------------------------------------------------------------
def _dedupe(files):
    """Vyhodí duplicity (např. 'Skladba (1).mp3' se stejnou velikostí)."""
    seen, out = set(), []
    for f in sorted(files, key=lambda p: (len(os.path.basename(p)), p)):
        key = os.path.getsize(f)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return sorted(out)


def music_pool(cat_index=None):
    return _dedupe(_music_pool(cat_index))


def _music_pool(cat_index=None):
    if cat_index is not None and os.path.isdir(MUSIC_DIR):
        sub = os.path.join(MUSIC_DIR, CATEGORY_NAMES[cat_index % len(CATEGORY_NAMES)])
        files = sorted(glob.glob(os.path.join(sub, "*.mp3")))
        if files:
            return files
    if os.path.isdir(MUSIC_DIR):
        files = sorted(glob.glob(os.path.join(MUSIC_DIR, "*.mp3")))
        if files:
            return files
    return sorted(glob.glob(os.path.join(HERE, "*.mp3")))


def pick_track(pool, index):
    """Stabilní výběr: skladby se střídají v zamíchaných kolech, takže se
    všechny použijí stejně často a dva citáty po sobě nemají stejnou."""
    n = len(pool)
    if n == 1:
        return pool[0]

    def perm(cycle):
        return list(np.random.default_rng(1000 + cycle).permutation(n))

    cycle, pos = divmod(index - 1, n)
    p = perm(cycle)
    if cycle > 0 and p[0] == perm(cycle - 1)[-1]:
        p[0], p[1] = p[1], p[0]
    if cycle > 0:
        prev = perm(cycle - 1)
        if cycle > 1 and prev[0] == perm(cycle - 2)[-1]:
            prev[0], prev[1] = prev[1], prev[0]
        if p[0] == prev[-1]:
            p[0], p[1] = p[1], p[0]
    return pool[p[pos]]


# --- nejživější úsek ----------------------------------------------------------
def _load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def best_starts(mp3, duration=DURATION, scan=120.0, k=3):
    """Najde až `k` nejživějších (nepřekrývajících se) úseků v prvních `scan` s,
    každý zarovnaný na úder. Vrací seznam začátků v sekundách."""
    key = f"{os.path.basename(mp3)}|{os.path.getsize(mp3)}|v2"
    cache = _load_cache()
    if key in cache:
        return cache[key]

    wav = os.path.join(HERE, "_seg_tmp.wav")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", mp3,
                    "-ac", "1", "-ar", "11025", "-t", str(scan), wav], check=True)
    with wave.open(wav, "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    os.remove(wav)

    hop = 512
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-9)
    fps = sr / hop
    win = int(duration * fps)
    if n <= win:
        starts = [0.0]
    else:
        # energie úseku + bonus za "živost" (změny hlasitosti = rytmus)
        flux = np.abs(np.diff(np.log(rms), prepend=np.log(rms[0])))
        score = np.convolve(rms, np.ones(win), "valid") + 0.15 * np.convolve(flux, np.ones(win), "valid")
        score[: int(2 * fps)] *= 0.8          # mírně penalizuj úplný začátek
        onset = np.maximum(0, np.diff(np.log(rms), prepend=0))
        starts = []
        sc = score.copy()
        for _ in range(k):
            best = int(np.argmax(sc))
            if sc[best] < score.max() * 0.75:  # slabší úseky už nebrat
                break
            lo = max(0, best - int(0.5 * fps))
            b = lo + int(np.argmax(onset[lo: best + 1]))   # zarovnání na úder
            starts.append(round(b / fps, 2))
            sc[max(0, best - win): best + win] = -1        # žádný překryv
        starts = starts or [0.0]
    start = starts
    cache[key] = start
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    return start


# --- uvedení autora (Kevin MacLeod, CC BY 4.0) ------------------------------------
def track_title(mp3):
    """Název skladby z ID3 štítku (přes ffmpeg), jinak z názvu souboru."""
    import re
    try:
        err = subprocess.run([FFMPEG, "-hide_banner", "-i", mp3],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stderr
        m = re.search(r"^\s+title\s*:\s*(.+)$", err, re.M)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    name = os.path.splitext(os.path.basename(mp3))[0]
    return re.sub(r"\s*\(\d+\)$", "", name)


def credit_line(mp3):
    """Text, který licence CC BY 4.0 vyžaduje uvést u videa."""
    return (f'🎵 "{track_title(mp3)}" Kevin MacLeod (incompetech.com)\n'
            "Licensed under Creative Commons: By Attribution 4.0 License\n"
            "http://creativecommons.org/licenses/by/4.0/")


def track_for(index, cat_index):
    return pick_track(music_pool(cat_index), index)


# --- render videa -----------------------------------------------------------------
def make_video(png, mp3, out_mp4, index=1, duration=DURATION, fps=FPS):
    frames = int(duration * fps)
    fade_out = duration - 0.8
    starts = best_starts(mp3, duration)
    start = starts[(index // 7) % len(starts)]   # úsek se mění, ale ne pokaždé
    vf = (
        "scale=4320:7680,"
        f"zoompan=z='min(zoom+0.00035,1.10)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
        "format=yuv420p,"
        f"fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out:.2f}:d=0.8"
    )
    af = (
        "loudnorm=I=-14:TP=-1.5:LRA=11,"
        f"afade=t=in:st=0:d=0.3,afade=t=out:st={fade_out:.2f}:d=0.8"
    )
    cmd = [
        FFMPEG, "-y", "-loglevel", "error", "-nostats",
        "-i", png,
        "-ss", f"{start:.2f}", "-i", mp3,
        "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]",
        "-map", "[v]", "-map", "[a]",
        "-map_metadata", "-1",          # žádné štítky z MP3 (licence, autor…) do videa

        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
        out_mp4,
    ]
    subprocess.run(cmd, check=True)
    print(f"OK: {os.path.basename(out_mp4)}  <- {os.path.basename(mp3)} od {start:.1f}s")


def _arg(name, default=None):
    if name in sys.argv:
        return int(sys.argv[sys.argv.index(name) + 1])
    return default


def main():
    sys.path.insert(0, HERE)
    from quotes_loader import build_order

    if not music_pool():
        print("Žádné MP3 (ani v music/, ani v kořeni).")
        return
    order = build_order()

    if "--test" in sys.argv:
        os.makedirs(os.path.join(HERE, "preview"), exist_ok=True)
        pngs = sorted(glob.glob(os.path.join(HERE, "preview", "v2_*.png")))[:6]
        for k, png in enumerate(pngs):
            i = int(os.path.basename(png)[3:6])
            cat = order[i - 1][2] if i <= len(order) else None
            mp3 = pick_track(music_pool(cat), i)
            make_video(png, mp3, os.path.splitext(png)[0] + ".mp4", i)
        return

    start = _arg("--from")
    end = _arg("--to", len(order))
    force = start is not None
    static = "--static" in sys.argv          # bez animace (původní styl)
    anim_from = _arg("--anim-from", 30)      # od které pozice se dělá animace psaní
    os.makedirs(os.path.join(HERE, "video"), exist_ok=True)
    for i, (qid, q, cat) in enumerate(order, 1):
        if force and not (start <= i <= end):
            continue
        mp3 = track_for(i, cat)
        outs = [os.path.join(HERE, "video", f"{tag}_{i:03d}.mp4") for tag in ("ig", "fb")]
        if not force and all(os.path.exists(o) for o in outs):
            continue
        if not static and i >= anim_from:
            import render2
            g, n = render2.animate(q, i, (render2.HANDLE_IG, render2.HANDLE_FB))
            make_video_anim(g, n, mp3, outs, i)
            continue
        for tag, mp4 in zip(("ig", "fb"), outs):
            png = os.path.join(HERE, "out", f"{tag}_{i:03d}.png")
            if os.path.exists(png) and (force or not os.path.exists(mp4)):
                make_video(png, mp3, mp4, i)




# --- video s animací psaní (snímky se posílají rovnou do ffmpeg) -----------------------
def _ffmpeg_anim_cmd(total, mp3, start, out_mp4, fps):
    fade_out = total - 0.8
    vf = (
        "scale=2160:3840,"
        f"zoompan=z='min(1+0.0004*on,1.10)':d=1:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
        "format=yuv420p,"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out:.2f}:d=0.8"
    )
    af = ("loudnorm=I=-14:TP=-1.5:LRA=11,"
          f"afade=t=in:st=0:d=0.3,afade=t=out:st={fade_out:.2f}:d=0.8")
    return [
        FFMPEG, "-y", "-loglevel", "error", "-nostats",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x1920", "-r", str(fps), "-i", "-",
        "-ss", f"{start:.2f}", "-i", mp3,
        "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]",
        "-map", "[v]", "-map", "[a]", "-map_metadata", "-1",
        "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
        out_mp4,
    ]


def make_video_anim(frames, n, mp3, outs, index=1, fps=FPS):
    """frames = generátor n-tic snímků (z render2.animate), outs = cesty k MP4 ve stejném pořadí."""
    total = n / fps
    starts = best_starts(mp3, total)
    start = starts[(index // 7) % len(starts)]
    procs = [subprocess.Popen(_ffmpeg_anim_cmd(total, mp3, start, o, fps), stdin=subprocess.PIPE)
             for o in outs]
    last_id, last_bytes = None, None
    try:
        for tup in frames:
            if id(tup) != last_id:          # stejný snímek se nepřevádí znovu
                last_id, last_bytes = id(tup), [im.tobytes() for im in tup]
            for p, b in zip(procs, last_bytes):
                p.stdin.write(b)
    finally:
        for p in procs:
            p.stdin.close()
        bad = [o for p, o in zip(procs, outs) if p.wait() != 0]
        if bad:
            raise RuntimeError(f"ffmpeg selhal: {bad}")
    print(f"OK: {', '.join(os.path.basename(o) for o in outs)}  <- "
          f"{os.path.basename(mp3)} ({total:.1f} s, psaní)")


if __name__ == "__main__":
    main()
