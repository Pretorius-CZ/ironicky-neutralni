#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publikuje denní citát na Instagram (Reels) a Facebook (stránka).

Běží v GitHub Actions. Konfigurace přes proměnné prostředí (repo Secrets):
  META_ACCESS_TOKEN  – dlouhodobý user token (60 dní)
  FB_PAGE_ID         – ID FB stránky
  IG_USER_ID         – Instagram Business Account ID
  GRAPH_VERSION      – výchozí "v21.0"
  SCHEDULE_START     – ISO datum prvního dne, např. 2026-10-23
  TARGET_HOUR        – hodina publikování v Europe/Prague (výchozí 18)
  FORCE              – "1" = ignorovat kontrolu hodiny (pro ruční test)
  VIDEO_BASE_URL     – volitelně vlastní veřejná URL pro videa
"""
import os
import json
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import requests

VER = os.environ.get("GRAPH_VERSION", "v21.0")
TZ = ZoneInfo(os.environ.get("TZ", "Europe/Prague"))
HERE = os.path.dirname(os.path.abspath(__file__))

TOKEN = os.environ["META_ACCESS_TOKEN"]
FB_PAGE_ID = os.environ["FB_PAGE_ID"]
IG_USER_ID = os.environ["IG_USER_ID"]


def _check(resp, what):
    """Ověří odpověď, ale NIKDY neloguje URL (ta může obsahovat token)."""
    if resp.status_code >= 400:
        raise RuntimeError(f"{what}: HTTP {resp.status_code}: {resp.text[:400]}")
    return resp


def today_index():
    """Kolik dní od SCHEDULE_START dnes je (denní publikování)."""
    start = date.fromisoformat(os.environ.get("SCHEDULE_START", "2026-10-26"))
    today = datetime.now(TZ).date()
    if today < start:
        return 0
    return (today - start).days


def load_row(index):
    with open(os.path.join(HERE, "captions.json"), encoding="utf-8") as f:
        rows = json.load(f)
    return rows[index % len(rows)]


def get_page_token():
    """Z user tokenu vytáhne page token pro FB stránku."""
    resp = _check(
        requests.get(
            f"https://graph.facebook.com/{VER}/me/accounts",
            params={"access_token": TOKEN},
            timeout=30,
        ),
        "me/accounts",
    )
    for page in resp.json().get("data", []):
        if page.get("id") == FB_PAGE_ID:
            return page["access_token"]
    raise RuntimeError(f"Stránka {FB_PAGE_ID} nenalezena v /me/accounts")


def publish_fb(page_token, video_path, caption):
    """Nahraje video přímo na FB stránku (multipart, bez veřejné URL).

    Token jde v těle multipartu (ne v URL), aby se nikdy neobjevil v logu.
    """
    url = f"https://graph.facebook.com/{VER}/{FB_PAGE_ID}/videos"
    with open(video_path, "rb") as f:
        resp = _check(
            requests.post(
                url,
                data={"access_token": page_token, "description": caption},
                files={"source": (os.path.basename(video_path), f, "video/mp4")},
                timeout=180,
            ),
            "FB video",
        )
    data = resp.json()
    if "id" not in data:
        raise RuntimeError(f"FB chyba: {data}")
    return data["id"]


def publish_ig(video_url, caption):
    """Reels: vytvoří container, počká na FINISHED, publikuje."""
    init = _check(
        requests.post(
            f"https://graph.facebook.com/{VER}/{IG_USER_ID}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true",
                "access_token": TOKEN,
            },
            timeout=60,
        ),
        "IG media",
    )
    container = init.json()["id"]

    for _ in range(30):
        time.sleep(10)
        s = _check(
            requests.get(
                f"https://graph.facebook.com/{VER}/{container}",
                params={"fields": "status_code", "access_token": TOKEN},
                timeout=30,
            ),
            "IG status",
        ).json()
        sc = s.get("status_code")
        if sc == "FINISHED":
            break
        if sc == "ERROR":
            raise RuntimeError(f"IG zpracování selhalo: {s}")

    pub = _check(
        requests.post(
            f"https://graph.facebook.com/{VER}/{IG_USER_ID}/media_publish",
            data={"creation_id": container, "access_token": TOKEN},
            timeout=60,
        ),
        "IG publish",
    )
    return pub.json().get("id")


def main():
    if os.environ.get("FORCE") != "1":
        target = int(os.environ.get("TARGET_HOUR", "18"))
        if datetime.now(TZ).hour != target:
            print(f"Není {target}:00 v {TZ} — přeskočeno.")
            return

    idx = today_index()
    row = load_row(idx)
    print(f"Publikuji #{row['index']}: {row['quote']}")

    base = os.environ.get(
        "VIDEO_BASE_URL",
        "https://raw.githubusercontent.com/"
        f"{os.environ.get('GITHUB_REPOSITORY', 'owner/repo')}/"
        f"{os.environ.get('GITHUB_REF_NAME', 'main')}/",
    )

    try:
        page_token = get_page_token()
        fb_id = publish_fb(
            page_token,
            os.path.join(HERE, "video", row["video_fb"]),
            row["caption_fb"],
        )
        print("FB OK:", fb_id)
    except Exception as e:
        print("FB CHYBA (chybí pages_manage_posts?):", e)

    ig_id = publish_ig(base + "video/" + row["video_ig"], row["caption_ig"])
    print("IG OK:", ig_id)


if __name__ == "__main__":
    main()
