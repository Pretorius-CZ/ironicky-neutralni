#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publikuje denní citát na Instagram (Reels) a Facebook (stránka).

Běží v GitHub Actions. Konfigurace přes proměnné prostředí (repo Secrets):
  META_ACCESS_TOKEN  – dlouhodobý user token (60 dní)
  FB_PAGE_ID         – ID FB stránky
  IG_USER_ID         – Instagram Business Account ID
  GRAPH_VERSION      – výchozí "v21.0"
  SCHEDULE_START     – ISO datum prvního dne, např. 2026-10-23
  TARGET_HOUR        – hodina publikování v Europe/Prague (nepoužívá se; čas určuje Apps Script – 14:00)
  FORCE              – "1" = ignorovat kontrolu hodiny (pro ruční test)
  VIDEO_BASE_URL     – volitelně vlastní veřejná URL pro videa
"""
import os
import json
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import requests

from quotes_loader import HANDLE_IG, HANDLE_FB

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


def promo_caption(handle):
    brand = "#" + handle.lstrip("@")
    return (
        "Denní dávka ironie. 🎬\n\n"
        f"#ironie #humor #ceskyhumor {brand}\n\n"
        f"Sleduj {handle} pro víc. 😎\n\n"
        + PROMO_CREDIT
    )


# Hudba v nedělním promu (promo_music.mp3) – licence CC BY 4.0 vyžaduje uvést autora.
PROMO_CREDIT = (
    '🎵 "Monkeys Spinning Monkeys" Kevin MacLeod (incompetech.com)\n'
    "Licensed under Creative Commons: By Attribution 4.0 License\n"
    "http://creativecommons.org/licenses/by/4.0/"
)


def promo_variant(today):
    """Varianta promu 1..5 podle ISO týdne (rotace)."""
    return (today.isocalendar()[1] % 5) + 1


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


# --- Telegram (stejný bot jako meme-bot; secrets TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID) -------
def tg(method, data=None, files=None):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not tok or not chat:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/{method}",
                      data={"chat_id": chat, **(data or {})}, files=files, timeout=120)
    except Exception as e:                       # hlášení nesmí shodit publikaci
        print("Telegram:", type(e).__name__)


def ig_permalink(media_id):
    try:
        r = requests.get(f"https://graph.facebook.com/{VER}/{media_id}",
                         params={"fields": "permalink", "access_token": TOKEN}, timeout=30)
        return r.json().get("permalink")
    except Exception:
        return None


def main():
    info = {}
    try:
        _main(info)
    except Exception as e:
        tg("sendMessage", {"text": f"❌ Lepík {info.get('nazev', '')} se nezveřejnil.\n\n{str(e)[:600]}"})
        raise


def _main(info):
    today = datetime.now(TZ).date()

    if today.weekday() == 6:            # nedele -> promo (rotace)
        variant = promo_variant(today)
        video_ig = f"promo_story_ig_{variant}.mp4"
        video_fb = f"promo_story_fb_{variant}.mp4"
        caption_ig = promo_caption(HANDLE_IG)
        caption_fb = promo_caption(HANDLE_FB)
        print(f"Promo den (nedele) - varianta {variant}")
        info["nazev"] = f"(nedělní promo {variant})"
        info["text"] = "Nedělní promo video"
    else:
        row = load_row(today_index())
        video_ig = row["video_ig"]
        video_fb = row["video_fb"]
        caption_ig = row["caption_ig"]
        caption_fb = row["caption_fb"]
        print(f"Publikuji #{row['index']}: {row['quote']}")
        info["nazev"] = f"#{row['index']}"
        info["text"] = row["quote"]

    base = os.environ.get(
        "VIDEO_BASE_URL",
        "https://raw.githubusercontent.com/"
        f"{os.environ.get('GITHUB_REPOSITORY', 'owner/repo')}/"
        f"{os.environ.get('GITHUB_REF_NAME', 'main')}/",
    )

    fb_chyba = None
    try:
        page_token = get_page_token()
        fb_id = publish_fb(
            page_token,
            os.path.join(HERE, "video", video_fb),
            caption_fb,
        )
        print("FB OK:", fb_id)
    except Exception as e:
        fb_chyba = str(e)[:300]
        print("FB CHYBA (chybí pages_manage_posts?):", e)

    ig_id = publish_ig(base + "video/" + video_ig, caption_ig)
    print("IG OK:", ig_id)

    odkaz = ig_permalink(ig_id)
    zprava = (f"🟨 Lepík {info['nazev']} zveřejněn na IG" + (" + FB" if not fb_chyba else "") +
              f"\n\n„{info['text']}“" + (f"\n\n{odkaz}" if odkaz else "") +
              (f"\n\n⚠️ Facebook selhal: {fb_chyba}" if fb_chyba else ""))
    try:
        with open(os.path.join(HERE, "video", video_ig), "rb") as f:
            tg("sendVideo", {"caption": zprava[:1000], "supports_streaming": "true"},
               files={"video": (video_ig, f, "video/mp4")})
    except OSError:
        tg("sendMessage", {"text": zprava})


if __name__ == "__main__":
    main()
