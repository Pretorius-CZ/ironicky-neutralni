# -*- coding: utf-8 -*-
"""Vygeneruje náhledy 5 CTA variant."""
import os
from make_promo import make_cta, PLATFORMS

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
for v in range(5):
    make_cta(PLATFORMS["ig"], v).convert("RGB").save(
        os.path.join(HERE, "out", f"cta_{v + 1}.png")
    )
print("OK - 5 CTA nahledu v out/")
