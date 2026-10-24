# -*- coding: utf-8 -*-
"""Odhadne BPM z MP3 (jednoduchá onset + autokorelace)."""
import os
import sys
import wave
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(HERE, "ffmpeg.exe")
mp3 = sys.argv[1] if len(sys.argv) > 1 else "DIMMYSAD - Rocking Forward.mp3"
wav = os.path.join(HERE, "_bpm_tmp.wav")

subprocess.run(
    [FFMPEG, "-y", "-loglevel", "error", "-i", os.path.join(HERE, mp3),
     "-ac", "1", "-ar", "22050", "-t", "25", wav],
    check=True,
)

with wave.open(wav, "rb") as w:
    n = w.getnframes()
    sr = w.getframerate()
    data = w.readframes(n)
os.remove(wav)

x = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

frame = 1024
hop = 256
frames = 1 + (len(x) - frame) // hop
energy = np.array([
    np.sqrt(np.mean(x[i * hop:i * hop + frame] ** 2)) for i in range(frames)
])
energy = np.log1p(energy)
onset = np.maximum(0, np.diff(energy))
onset = onset - onset.mean()

ac = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
fps = sr / hop
min_lag = int(fps * 60 / 200)   # 200 BPM
max_lag = int(fps * 60 / 50)    # 50 BPM

# top 5 kandidátů
cand = sorted(range(min_lag, max_lag), key=lambda l: ac[l], reverse=True)[:8]
seen = []
for lag in cand:
    bpm = 60 * fps / lag
    if all(abs(bpm - s) > 3 for s in seen):
        seen.append(bpm)
    if len(seen) >= 5:
        break
print("BPM kandidati:", [round(b, 1) for b in seen])
print("perioda (s) pro prvniho:", round(60.0 / seen[0], 3) if seen else "?")
