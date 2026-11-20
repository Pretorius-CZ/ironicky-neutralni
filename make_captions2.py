# -*- coding: utf-8 -*-
"""Popisky v2 = původní popisky + povinné uvedení autora hudby.

Od pozice NEW_FROM (videa s novou hudbou ze složky music/) přidá na konec
popisku řádek s autorem skladby, jak to vyžaduje licence CC BY 4.0.
Starší pozice zůstanou přesně jako dřív.

Použití:
    python make_captions2.py --from 30
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from quotes_loader import build_order, HANDLE_IG, HANDLE_FB  # noqa: E402
from make_captions import make_caption  # noqa: E402
from make_video2 import track_for, credit_line  # noqa: E402


def main():
    if "--from" not in sys.argv:
        print("Zadej --from N (od které pozice je nová hudba).")
        return
    new_from = int(sys.argv[sys.argv.index("--from") + 1])

    order = build_order()
    rows, txt = [], []
    credits = {}
    for i, (qid, quote, cat) in enumerate(order, 1):
        ig = make_caption(quote, cat, HANDLE_IG)
        fb = make_caption(quote, cat, HANDLE_FB)
        if i >= new_from:
            mp3 = track_for(i, cat)
            if mp3 not in credits:
                credits[mp3] = credit_line(mp3)
            ig += "\n\n" + credits[mp3]
            fb += "\n\n" + credits[mp3]
        rows.append({
            "index": i, "id": qid, "quote": quote,
            "video_ig": f"ig_{i:03d}.mp4", "video_fb": f"fb_{i:03d}.mp4",
            "caption_ig": ig, "caption_fb": fb,
        })
        txt += [f"===== {i:03d} =====", f"[IG] video/ig_{i:03d}.mp4", ig, "",
                f"[FB] video/fb_{i:03d}.mp4", fb, "", ""]

    with open(os.path.join(HERE, "captions.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "captions.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(txt))
    print(f"Hotovo: {len(rows)} popisků, autor hudby uveden od pozice {new_from}.")


if __name__ == "__main__":
    main()
