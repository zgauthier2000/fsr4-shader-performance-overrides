#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes rel-2026-11-22-sparks.webp (lossless): sparks flying past EVE in a recorded Stellar Blade (demo) clip (the escape-pod scene, frame 81, a frame the
# lossy builds skip), 4K Balanced (2561x1441 -> 3840x2160), a 320x180 area at 2x (nearest neighbor). Top row: AMD's FSR 4.1.2 (its RX 7000 model; this
# project's rig runs AMD's 4.1.1 file, the same picture byte for byte), dll-2026-11-05's lossy, this release's lossy. Bottom row: AMD's FSR 4.1.2 Lite (this
# release's 4.1.2l-exact, the same picture as AMD's own Lite DLL), dll-2026-11-05's 4.1.2l-lossy, this release's 4.1.2l-lossy (RX 7000 files; under Linux
# its Linux form). Under each: pixels in this area more than 16 levels (of 255) away from the row's AMD picture in any channel.
# The area: where the two releases' lossy builds differ most from each other in this frame. Display mapping x / (1 + x), gamma 1/2.2: this project's.
# Usage: make_release_2026_11_22_sparks.py <folder with amd lite lossy_old lossy_new llossy_old llossy_new _f081.png full 4K display PNGs> [x,y]
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
SRC = sys.argv[1]
X, Y = (int(v) for v in (sys.argv[2] if len(sys.argv) > 2 else '1350,130').split(','))
W, H, Z, GAP, TOP, ROWH = 320, 180, 2, 12, 40, 34
ROWS = [[('amd', 'AMD FSR 4.1.2'), ('lossy_old', 'lossy, dll-2026-11-05'), ('lossy_new', 'lossy, this release')],
        [('lite', 'AMD FSR 4.1.2 Lite'), ('llossy_old', '4.1.2l-lossy, dll-2026-11-05'), ('llossy_new', '4.1.2l-lossy, this release')]]
FONT = '/usr/share/fonts/TTF/DejaVuSans.ttf'
im = {k: np.asarray(Image.open(f'{SRC}/{k}_f081.png').convert('RGB'))[Y:Y + H, X:X + W] for r in ROWS for k, _ in r}
PW, PH = W * Z, H * Z
out = Image.new('RGB', (3 * PW + 2 * GAP, 2 * (PH + TOP + ROWH)), (24, 24, 24)); d = ImageDraw.Draw(out)
f = ImageFont.truetype(FONT, 22); fs = ImageFont.truetype(FONT, 20)
for j, row in enumerate(ROWS):
    ref = im[row[0][0]].astype(int); oy = j * (PH + TOP + ROWH)
    for i, (k, lab) in enumerate(row):
        ox = i * (PW + GAP)
        out.paste(Image.fromarray(im[k]).resize((PW, PH), Image.NEAREST), (ox, oy + TOP))
        d.text((ox + 6, oy + 8), lab, font=f, fill=(235, 235, 235))
        if i:
            n = int((np.abs(im[k].astype(int) - ref).max(-1) > 16).sum())
            d.text((ox + 6, oy + TOP + PH + 6), f'{n:,} pixels off', font=fs, fill=(200, 200, 200))
        else:
            d.text((ox + 6, oy + TOP + PH + 6), 'reference', font=fs, fill=(150, 150, 150))
out.save('rel-2026-11-22-sparks.webp', lossless=True)
print('wrote rel-2026-11-22-sparks.webp', out.size)
