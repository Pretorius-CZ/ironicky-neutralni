# -*- coding: utf-8 -*-
"""Načítání citátů: odstraňuje odrážky, čte kategorie a míchá je."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
QUOTES_FILE = os.path.join(HERE, "quotes.txt")

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
