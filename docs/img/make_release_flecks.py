#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes rel-flecks.webp (lossless): dark specks in foliage on one frame of a recorded game clip (Black Myth: Wukong
# Benchmark Tool, the bamboo bridge; 4K output from the game's own 2228x1256 frames), run through AMD's FSR 4.1.1 file, the lossy2 of
# release dll-2026-10-22 and the lossy of this release. A 480x270 area at 2x (nearest neighbor, so single pixels stay single pixels).
# Display mapping x / (1 + x), gamma 1/2.2: this project's, not the game's tone mapping (no game effects or UI).
# Usage: make_release_flecks.py <folder with amd/ old/ new/ display PNGs of the clip's last 16 frames> [frame index] [x,y]
# (the PNGs come from this project's local game-clip runs; the recorded clip itself is not published).
import sys
from PIL import Image, ImageDraw, ImageFont

SRC = sys.argv[1]
K = int(sys.argv[2]) if len(sys.argv) > 2 else 11
X, Y = (int(v) for v in (sys.argv[3] if len(sys.argv) > 3 else '2208,0').split(','))
W, H, Z, GAP, TOP = 480, 270, 2, 12, 46
LABELS = [('amd', 'AMD FSR 4.1.1'), ('old', 'lossy2 (dll-2026-10-22)'), ('new', 'lossy (this release)')]
FONT = '/usr/share/fonts/TTF/DejaVuSans.ttf'
import glob
out = Image.new('RGB', (3 * W * Z + 2 * GAP, H * Z + TOP + 30), (24, 24, 24))
d = ImageDraw.Draw(out)
f1, f2 = ImageFont.truetype(FONT, 26), ImageFont.truetype(FONT, 17)
for i, (b, label) in enumerate(LABELS):
    frame = sorted(glob.glob(f'{SRC}/{b}/*.png'))[K]
    im = Image.open(frame).convert('RGB').crop((X, Y, X + W, Y + H)).resize((W * Z, H * Z), Image.NEAREST)
    x0 = i * (W * Z + GAP)
    out.paste(im, (x0, TOP))
    d.text((x0 + 8, 10), label, fill=(240, 240, 240), font=f1)
d.text((8, TOP + H * Z + 6), 'Black Myth: Wukong Benchmark Tool, recorded game frames, 4K output, one frame, 2x zoom; '
       "this project's display mapping, not the game's", fill=(190, 190, 190), font=f2)
out.save('rel-flecks.webp', lossless=True, quality=100, method=6)
print('rel-flecks.webp', out.size)
