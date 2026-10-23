# -*- coding: utf-8 -*-
"""Vygeneruje popisky (captions) pro IG a FB podle append-only pořadí."""
import os
import json
from quotes_loader import build_order, CATEGORIES_META, HANDLE_IG, HANDLE_FB

HERE = os.path.dirname(os.path.abspath(__file__))


def make_caption(quote, cat_index, handle):
    meta = CATEGORIES_META[cat_index % len(CATEGORIES_META)]
    tags = " ".join("#" + h for h in meta["hashtags"])
    return f"{meta['emoji']} {quote}\n\n{tags}\n\nSleduj {handle} pro víc. 😎"


def main():
    order = build_order()
    rows = []
    txt = []
    for i, (qid, quote, cat_index) in enumerate(order, 1):
        ig = make_caption(quote, cat_index, HANDLE_IG)
        fb = make_caption(quote, cat_index, HANDLE_FB)
        rows.append({
            "index": i,
            "id": qid,
            "quote": quote,
            "video_ig": f"ig_{i:03d}.mp4",
            "video_fb": f"fb_{i:03d}.mp4",
            "caption_ig": ig,
            "caption_fb": fb,
        })
        txt.append(f"===== {i:03d} =====")
        txt.append(f"[IG] video/ig_{i:03d}.mp4")
        txt.append(ig)
        txt.append("")
        txt.append(f"[FB] video/fb_{i:03d}.mp4")
        txt.append(fb)
        txt.append("")
        txt.append("")

    with open(os.path.join(HERE, "captions.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "captions.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(txt))
    print(f"Hotovo: {len(rows)} popisků -> captions.txt + captions.json")


if __name__ == "__main__":
    main()
