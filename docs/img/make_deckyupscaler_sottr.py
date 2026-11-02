#!/usr/bin/env python3
# make_deckyupscaler_sottr.py <frame folder> <out.png>: comparison picture for docs/deckyupscaler.md. The folder holds lite/ du1/ du3/ ourll/, each with one output frame (float16 RGBA, 1920x1080).
# The left edge of the frame at 3x, display mapping x / (1 + x), gamma 1/2.2.
import glob, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1:3]
def rd(b):
    a = np.fromfile(glob.glob(f'{src}/{b}/output_*.raw')[-1], np.float16).astype(np.float32).reshape(1080, 1920, 4)[..., :3]
    return (a.clip(0) / (1 + a.clip(0))) ** (1 / 2.2)
P = [('AMD Lite', 'lite'), ('DeckyUpscaler, shipped set', 'du1'), ('DeckyUpscaler, exact set', 'du3'), ('This project, 4.1.2l-lossy', 'ourll')]
x, y, W, H, S, G, L = 0, 600, 240, 135, 3, 8, 30
font = ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf', 18) if glob.glob('/usr/share/fonts/TTF/DejaVuSans.ttf') else ImageFont.load_default()
im = Image.new('RGB', (2 * W * S + G, 2 * (H * S + L) + G), (24, 28, 32)); dr = ImageDraw.Draw(im)
for i, (t, b) in enumerate(P):
    cx, cy = (i % 2) * (W * S + G), (i // 2) * (H * S + L + G)
    dr.text((cx + 6, cy + 5), t, fill=(235, 238, 240), font=font)
    im.paste(Image.fromarray((rd(b)[y:y + H, x:x + W].clip(0, 1) * 255).astype('uint8')).resize((W * S, H * S), Image.NEAREST), (cx, cy + L))
im.save(out, optimize=True)
