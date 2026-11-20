# -*- coding: utf-8 -*-
"""Hledač memů – krok 1: projde IG účty z meme_ucty.txt a najde virální reels.

Používá Instagram Business Discovery (stejný token jako publish.py).
Vybírá jen reels, u kterých autor POVOLIL stahování (API jinak nevrátí media_url).

Výstup:
    kandidati.json   – seznam kandidátů (pro další kroky: OCR, překlad, schválení)
    kandidati.html   – přehled s náhledy, otevře se v prohlížeči

Konfigurace (soubor .env vedle skriptu, NEPATŘÍ do gitu):
    META_ACCESS_TOKEN=...
    IG_USER_ID=...

Použití:
    python hledac_memu.py              # posledních 45 dní, top 40
    python hledac_memu.py --dni 14 --top 20
"""
import os
import re
import sys
import json
import html
import statistics
import webbrowser
from datetime import datetime, timezone

import urllib.parse
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
VER = os.environ.get("GRAPH_VERSION", "v21.0")
UCTY_FILE = os.path.join(HERE, "meme_ucty.txt")
POUZITE_FILE = os.path.join(HERE, "meme_pouzite.json")   # už použité / zamítnuté
OUT_JSON = os.path.join(HERE, "kandidati.json")
OUT_HTML = os.path.join(HERE, "kandidati.html")

MEDIA_FIELDS = ("id,caption,media_type,media_product_type,permalink,thumbnail_url,"
                "media_url,timestamp,like_count,comments_count,view_count")


# --- konfigurace -----------------------------------------------------------------
def load_env():
    p = os.path.join(HERE, ".env")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    missing = [k for k in ("META_ACCESS_TOKEN", "IG_USER_ID") if not os.environ.get(k)]
    if missing:
        sys.exit("Chybí v .env: " + ", ".join(missing))


def load_accounts():
    """Účty z meme_ucty.txt – bere jména i celé odkazy (instagram.com/jmeno/...)."""
    names = []
    with open(UCTY_FILE, encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", line)
            name = m.group(1) if m else line.lstrip("@").split()[0]
            if name.lower() in ("reel", "reels", "p", "stories", "explore"):
                continue
            if name not in names:
                names.append(name)
    return names


def load_used():
    try:
        with open(POUZITE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


# --- Instagram API ------------------------------------------------------------------
def fetch_account(username, limit=50):
    """Business Discovery dotaz (jen standardní knihovna, bez 'requests')."""
    fields = (f"business_discovery.username({username})"
              f"{{username,followers_count,media.limit({limit}){{{MEDIA_FIELDS}}}}}")
    q = urllib.parse.urlencode({"fields": fields,
                                "access_token": os.environ["META_ACCESS_TOKEN"]})
    url = f"https://graph.facebook.com/{VER}/{os.environ['IG_USER_ID']}?{q}"
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        raise RuntimeError(msg) from None          # URL s tokenem se nikdy nevypíše
    except urllib.error.URLError as e:
        raise RuntimeError(f"síťová chyba: {e.reason}") from None
    bd = data.get("business_discovery", {})
    return bd.get("followers_count", 0), bd.get("media", {}).get("data", [])


# --- výběr --------------------------------------------------------------------------
def age_days(ts):
    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400


def score_account(username, followers, media, max_days, used):
    """Virálnost = zhlédnutí / medián zhlédnutí reels toho účtu."""
    reels = [m for m in media
             if m.get("media_type") == "VIDEO" and m.get("media_product_type") in ("REELS", None)]
    views = [m.get("view_count") or 0 for m in reels if m.get("view_count")]
    median = statistics.median(views) if views else 0
    out, skipped = [], {"stahovani_zakazano": 0, "stare": 0, "pouzite": 0}
    for m in reels:
        if m["id"] in used:
            skipped["pouzite"] += 1
            continue
        if age_days(m["timestamp"]) > max_days:
            skipped["stare"] += 1
            continue
        if not m.get("media_url"):
            skipped["stahovani_zakazano"] += 1
            continue
        v = m.get("view_count") or 0
        likes = m.get("like_count") or 0
        viral = (v / median) if median else 0
        out.append({
            "id": m["id"],
            "ucet": username,
            "sledujici": followers,
            "odkaz": m.get("permalink"),
            "nahled": m.get("thumbnail_url"),
            "video_url": m.get("media_url"),
            "popis": (m.get("caption") or "")[:300],
            "datum": m["timestamp"][:10],
            "zhlednuti": v,
            "lajky": likes,
            "komentare": m.get("comments_count") or 0,
            "viralita": round(viral, 2),
        })
    return out, skipped, median


# --- přehled v HTML --------------------------------------------------------------------
def write_html(cands, report):
    rows = []
    for k, c in enumerate(cands, 1):
        rows.append(f"""
<div class="c">
  <a href="{html.escape(c['odkaz'] or '#')}" target="_blank">
    <img src="{html.escape(c['nahled'] or '')}" loading="lazy" alt=""></a>
  <div class="m">
    <b>#{k} @{html.escape(c['ucet'])}</b>
    <span class="v">{c['viralita']}× průměr účtu</span><br>
    👁 {c['zhlednuti']:,} · ❤ {c['lajky']:,} · 💬 {c['komentare']:,} · {c['datum']}
    <p>{html.escape(c['popis'][:160])}</p>
    <a href="{html.escape(c['odkaz'] or '#')}" target="_blank">otevřít na IG ↗</a>
  </div>
</div>""")
    rep = "".join(f"<li>{html.escape(r)}</li>" for r in report)
    doc = f"""<!DOCTYPE html><html lang="cs"><head><meta charset="utf-8">
<title>Kandidáti – memy</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;background:#1a1a22;color:#eee;margin:0;padding:24px}}
h1{{color:#ffd250;margin:0 0 4px}} .s{{color:#999;margin-bottom:20px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}}
.c{{background:#24242e;border-radius:12px;overflow:hidden}}
.c img{{width:100%;aspect-ratio:9/12;object-fit:cover;display:block;background:#333}}
.m{{padding:10px 12px;font-size:14px;line-height:1.45}} .m p{{color:#aaa;margin:6px 0}}
.v{{float:right;background:#ffd250;color:#1a1a22;border-radius:6px;padding:0 6px;font-weight:700}}
a{{color:#8cc8ff}} details{{margin-bottom:20px;color:#aaa}}
</style></head><body>
<h1>Kandidáti na polední video</h1>
<div class="s">{datetime.now():%d.%m.%Y %H:%M} · {len(cands)} kandidátů · seřazeno podle virality</div>
<details><summary>Přehled účtů</summary><ul>{rep}</ul></details>
<div class="g">{''.join(rows)}</div></body></html>"""
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(doc)


def _arg(name, default):
    if name in sys.argv:
        return int(sys.argv[sys.argv.index(name) + 1])
    return default


def main():
    load_env()
    max_days = _arg("--dni", 45)
    top = _arg("--top", 40)
    accounts = load_accounts()
    if not accounts:
        sys.exit("V meme_ucty.txt nejsou žádné účty.")
    used = load_used()

    cands, report = [], []
    for u in accounts:
        try:
            followers, media = fetch_account(u)
        except Exception as e:
            report.append(f"@{u}: CHYBA – {e}")
            print(f"@{u}: CHYBA – {e}")
            continue
        found, sk, med = score_account(u, followers, media, max_days, used)
        line = (f"@{u}: {followers:,} sledujících, medián {int(med):,} zhlédnutí, "
                f"kandidátů {len(found)} (zakázané stahování {sk['stahovani_zakazano']}, "
                f"starší {sk['stare']}, použité {sk['pouzite']})")
        report.append(line)
        print(line)
        cands += found

    cands.sort(key=lambda c: (c["viralita"], c["zhlednuti"]), reverse=True)
    cands = cands[:top]
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(cands, f, ensure_ascii=False, indent=2)
    write_html(cands, report)
    print(f"\nHotovo: {len(cands)} kandidátů -> kandidati.html")
    if "--neotvirat" not in sys.argv:
        webbrowser.open("file://" + OUT_HTML)


if __name__ == "__main__":
    main()
