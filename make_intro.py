# -*- coding: utf-8 -*-
"""Vygeneruje 3 varianty úvodní karty pro promo (Story 1080x1920)."""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"


def make(path, lines, small, big=175):
    img = Image.new("RGB", (W, H), (24, 24, 32))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 16], fill=(255, 210, 80))
    fb = ImageFont.truetype(FONT_BOLD, big)
    fs = ImageFont.truetype(FONT_REG, 62)
    lh = int(big * 1.12)
    total = lh * len(lines)
    y = (H - total) // 2 - 60
    for line in lines:
        w = d.textlength(line, font=fb)
        d.text(((W - w) // 2, y), line, font=fb, fill=(255, 255, 255))
        y += lh
    w = d.textlength(small, font=fs)
    d.text(((W - w) // 2, H - 620), small, font=fs, fill=(150, 150, 165))
    img.save(path)
    print("OK:", path)


def main():
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    make(os.path.join(HERE, "out", "intro_1.png"),
         ["Pravda", "bolí."], "ironicky neutralni")
    make(os.path.join(HERE, "out", "intro_2.png"),
         ["Poznáváš", "se?"], "ironicky neutralni")
    make(os.path.join(HERE, "out", "intro_3.png"),
         ["ironicky", "neutralni"], "denní dávka ironie")


if __name__ == "__main__":
    main()
