#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes rel-lite-specks.webp (lossless): white specks in foliage on one frame of a recorded game clip (Black Myth: Wukong Benchmark Tool, the
# bamboo bridge; 4K output from the game's own 2228x1256 frames), run through AMD's FSR 4.1.1 file, AMD's FSR 4.1.2 Lite and this release's
# 4.1.2l-lossy. A 240x135 area at 4x (nearest neighbor, so single pixels stay single pixels), twice: as it is, and with every speck circled
# (at 2x over 480x270 the specks were not visible: user 2026-10-29). A speck: a pixel more than 20 of 255 brighter than
# all 8 of its neighbors on screen; the count under each picture is for this area and frame. The area is the one where 4.1.2l-lossy has the most
# fewer specks than Lite over the clip's last 16 frames (picked from the data); over the whole clip 473 per frame against Lite's 1,004 (AMD 1,189).
# Display mapping x / (1 + x), gamma 1/2.2: this project's, not the game's tone mapping (no game effects or UI).
# Usage: make_release_lite_specks.py <folder with amd/ lite/ new/ display PNGs of the clip's last 16 frames> [frame index] [x,y]
# (the PNGs come from this project's local game-clip runs; the recorded clip itself is not published).
import sys, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC = sys.argv[1]
K = int(sys.argv[2]) if len(sys.argv) > 2 else 0
X, Y = (int(v) for v in (sys.argv[3] if len(sys.argv) > 3 else '1283,104').split(','))
W, H, Z, GAP, TOP, ROWGAP = 240, 135, 4, 12, 46, 40
LABELS = [('amd', 'AMD FSR 4.1.1'), ('lite', 'AMD FSR 4.1.2 Lite'), ('new', '4.1.2l-lossy (this release)')]
FONT = '/usr/share/fonts/TTF/DejaVuSans.ttf'


def specks(a):
    v = a.max(2).astype(np.int32); p = np.pad(v, 1, mode='edge'); h, w = v.shape
    nb = np.max(np.stack([p[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]), 0)
    return (v > nb + 20)[1:-1, 1:-1]


out = Image.new('RGB', (3 * W * Z + 2 * GAP, 2 * H * Z + TOP + ROWGAP + 30), (24, 24, 24))
d = ImageDraw.Draw(out)
f = ImageFont.truetype(FONT, 26); fs = ImageFont.truetype(FONT, 20)
for i, (k, lab) in enumerate(LABELS):
    im = Image.open(sorted(glob.glob(f'{SRC}/{k}/*.png'))[-16:][K]).convert('RGB')
    m = specks(np.asarray(im.crop((X - 1, Y - 1, X + W + 1, Y + H + 1)))); n = int(m.sum())
    x = i * (W * Z + GAP); pic = im.crop((X, Y, X + W, Y + H)).resize((W * Z, H * Z), Image.NEAREST)
    out.paste(pic, (x, TOP)); ring = pic.copy(); dr = ImageDraw.Draw(ring)
    for yy, xx in zip(*np.nonzero(m)):
        cx, cy = xx * Z + Z / 2, yy * Z + Z / 2; dr.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), outline=(255, 60, 200), width=2)
    out.paste(ring, (x, TOP + H * Z + ROWGAP))
    d.text((x + 4, 8), f'{lab}: {n} specks', font=f, fill=(236, 236, 236))
    print(lab, n)
d.text((4, TOP + H * Z + 8), 'The same, every speck circled:', font=fs, fill=(236, 236, 236))
d.text((4, TOP + 2 * H * Z + ROWGAP + 4), 'Black Myth: Wukong Benchmark Tool, recorded frames, 4K Balanced, 4x zoom; this project\'s display mapping, not the game\'s.', font=fs, fill=(170, 170, 170))
out.save('rel-lite-specks.webp', lossless=True)
