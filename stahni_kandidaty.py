# -*- coding: utf-8 -*-
"""Stáhne náhledy a videa kandidátů z kandidati.json do složky kandidati/.

Použití:
    python stahni_kandidaty.py            # náhledy + videa všech kandidátů
    python stahni_kandidaty.py --jen-nahledy
Složka kandidati/ je v .gitignore (na GitHub se nenahrává).
"""
import os
import sys
import json
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kandidati")


def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return "už je"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(path + ".part", "wb") as f:
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            f.write(b)
    os.replace(path + ".part", path)
    return f"{os.path.getsize(path) // 1024} kB"


def main():
    with open(os.path.join(HERE, "kandidati.json"), encoding="utf-8") as f:
        cands = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    only_thumbs = "--jen-nahledy" in sys.argv
    for i, c in enumerate(cands):
        base = os.path.join(OUT, f"{i:02d}_{c['id']}")
        try:
            if c.get("nahled"):
                print(f"{i:02d} náhled:", fetch(c["nahled"], base + ".jpg"))
            if c.get("video_url") and not only_thumbs:
                print(f"{i:02d} video: ", fetch(c["video_url"], base + ".mp4"))
        except Exception as e:
            print(f"{i:02d} CHYBA: {e}")
    print("Hotovo ->", OUT)


if __name__ == "__main__":
    main()
