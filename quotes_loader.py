# -*- coding: utf-8 -*-
"""Načítání citátů: odrážky, kategorie, míchání a append-only pořadí."""
import os
import re
import json
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
QUOTES_FILE = os.path.join(HERE, "quotes.txt")
ORDER_FILE = os.path.join(HERE, "order.json")

HANDLE_IG = "@ironicky_neutralni"
HANDLE_FB = "@ironickyneutralni"

# Kategorie v pořadí, v jakém jsou v quotes.txt (oddělené prázdným řádkem).
CATEGORIES_META = [
    {"name": "lide", "emoji": "😏",
     "hashtags": ["ironie", "sarkasmus", "lide", "pravda", "humor", "ceskyhumor"]},
    {"name": "prace", "emoji": "💼",
     "hashtags": ["prace", "kancelar", "korporat", "pondeli", "humor", "ceskyhumor"]},
    {"name": "zivot", "emoji": "🤷",
     "hashtags": ["zivot", "dospelost", "realita", "humor", "ceskyhumor"]},
    {"name": "drze", "emoji": "😈",
     "hashtags": ["drze", "drzost", "sarkasmus", "ironie", "humor", "ceskyhumor"]},
]


def strip_bullet(s):
    """Odstraní odrážky (•, -, *, číslování 1.) ze začátku řádku."""
    s = s.strip()
    if not s:
        return s
    m = re.match(r"^[\u2022\u00b7\u2219\-\u2013\u2014\*\u25aa\u25e6]\s*", s)
    if m:
        s = s[m.end():]
    m = re.match(r"^\d{1,2}[.)]\s*", s)
    if m:
        s = s[m.end():]
    return s.strip()


def load_categories():
    """Vrátí seznam kategorií; každá kategorie je seznam citátů."""
    if not os.path.exists(QUOTES_FILE):
        return [["Sem napiš citát."]]
    categories = []
    current = []
    with open(QUOTES_FILE, encoding="utf-8") as f:
        for raw in f:
            s = strip_bullet(raw)
            if not s or s.startswith("#"):
                if current:
                    categories.append(current)
                    current = []
                continue
            current.append(s)
    if current:
        categories.append(current)
    return categories


def interleave(categories):
    """Promíchá kategorie po jednom (round-robin). Vrací [(quote, cat_index), ...]."""
    if not categories:
        return []
    result = []
    maxlen = max(len(c) for c in categories)
    for i in range(maxlen):
        for ci, cat in enumerate(categories):
            if i < len(cat):
                result.append((cat[i], ci))
    return result


def quote_id(text):
    """Stabilní ID citátu (hash textu)."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def build_order():
    """Append-only pořadí publikování.

    Vrací [(id, quote, cat_index), ...]. Nové citáty se přidají na KONEC
    pořadí, existující pořadí zůstává (uloženo v order.json). Díky tomu se
    staré citáty negenerují znovu — generují se jen chybějící soubory.

    Pozn.: citáty neodstraňuj — mazání by rozhodilo pozice souborů.
    """
    current_ids = []
    id_map = {}
    for q, c in interleave(load_categories()):
        qid = quote_id(q)
        id_map[qid] = (q, c)
        current_ids.append(qid)

    ordered = []
    if os.path.exists(ORDER_FILE):
        try:
            with open(ORDER_FILE, encoding="utf-8") as f:
                ordered = json.load(f)
        except Exception:
            ordered = []

    known = set(ordered)
    for qid in current_ids:
        if qid not in known:
            ordered.append(qid)
            known.add(qid)

    with open(ORDER_FILE, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)

    return [(qid, id_map[qid][0], id_map[qid][1]) for qid in ordered if qid in id_map]
