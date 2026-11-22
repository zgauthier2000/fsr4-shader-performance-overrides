#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes rel-2026-11-22-specks.webp (lossless): dark specks on one frame of a recorded game clip (Cyberpunk 2077, the court clip, frame 114;
# 4K Balanced output from the game's own 2259x1271 frames), run through AMD's FSR 4.1.1 file, dll-2026-11-05's `lossy` and this release's
# `lossy` (RX 7000 files). A 240x340 area (a concrete post under a ledge) at 2x (nearest neighbor, so single pixels stay single pixels), twice:
# as it is, and with every dark speck circled. A dark speck: a pixel at least 0.15 darker than AMD 4.1.1's output (display units, 0..1) and at
# least 0.08 darker than the mean of its own 5x5 neighborhood (the release screen's rule); the count under each picture is for this area.
# The area was picked by eye from the frame where the two builds differ most (lossy 418 -> 134 dark specks in the 1280x720 crop around it).
# Display mapping x / (1 + x), gamma 1/2.2: this project's, not the game's tone mapping (no game effects or UI).
# Usage: make_release_2026_11_22.py <folder with amd_NN.png rl_NN.png nl_NN.png display PNGs of the 1280x720 crop at 792,1440> [NN] [x,y]
# (the PNGs come from this project's local game-clip runs; the recorded clip itself is not published).
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC = sys.argv[1]
K = sys.argv[2] if len(sys.argv) > 2 else '03'
X, Y = (int(v) for v in (sys.argv[3] if len(sys.argv) > 3 else '120,380').split(','))
W, H, Z, GAP, TOP, ROWGAP = 240, 340, 2, 12, 46, 40
LABELS = [('amd', 'AMD FSR 4.1.1'), ('rl', 'lossy, dll-2026-11-05'), ('nl', 'lossy, this release')]
FONT = '/usr/share/fonts/TTF/DejaVuSans.ttf'


def lum(im):
    return np.asarray(im.convert('RGB')).astype(np.float32).mean(-1) / 255


def box5(x):
    p = np.pad(x, 2, mode='edge'); c = np.pad(p.cumsum(0).cumsum(1), ((1, 0), (1, 0))); h, w = x.shape
    return (c[5:5 + h, 5:5 + w] - c[0:h, 5:5 + w] - c[5:5 + h, 0:w] + c[0:h, 0:w]) / 25


ims = {k: Image.open(f'{SRC}/{k}_{K}.png').convert('RGB') for k, _ in LABELS}
ref = lum(ims['amd'])
out = Image.new('RGB', (3 * W * Z + 2 * GAP, 2 * H * Z + TOP + ROWGAP + 30), (24, 24, 24))
d = ImageDraw.Draw(out)
f = ImageFont.truetype(FONT, 22); fs = ImageFont.truetype(FONT, 20)
for i, (k, lab) in enumerate(LABELS):
    x = lum(ims[k]); m = ((ref - x) >= 0.15) & ((box5(x) - x) >= 0.08)
    m = m[Y:Y + H, X:X + W]; n = int(m.sum())
    ox = i * (W * Z + GAP); pic = ims[k].crop((X, Y, X + W, Y + H)).resize((W * Z, H * Z), Image.NEAREST)
    out.paste(pic, (ox, TOP)); ring = pic.copy(); dr = ImageDraw.Draw(ring)
    for yy, xx in zip(*np.nonzero(m)):
        cx, cy = xx * Z + Z / 2, yy * Z + Z / 2; dr.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), outline=(255, 60, 200), width=2)
    out.paste(ring, (ox, TOP + H * Z + ROWGAP))
    d.text((ox + 6, 10), lab, font=f, fill=(235, 235, 235))
    d.text((ox + 6, TOP + 2 * H * Z + ROWGAP + 4), f'{n} dark specks', font=fs, fill=(200, 200, 200))
d.text((6, TOP + H * Z + 8), 'dark specks circled', font=fs, fill=(200, 200, 200))
out.save('rel-2026-11-22-specks.webp', lossless=True)
print('wrote rel-2026-11-22-specks.webp', out.size)
