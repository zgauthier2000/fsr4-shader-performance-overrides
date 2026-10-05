#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# metric_motion.py <input dir of gen_motion.py> <dir with output_3840x2160_fNNN.raw> [reference output dir]
# For the kept frames of the moving scene: error against the true image (PSNR in sRGB) per region,
# frame-to-frame instability (mean absolute change of a scene point between two frames, in 8-bit
# steps; 0 for a perfect upscaler), and, with a reference, PSNR against the reference's frames.
import sys, os, glob, numpy as np
import motion_scene as sc
inp, outd = sys.argv[1], sys.argv[2]
refd = sys.argv[3] if len(sys.argv) > 3 else None
def srgb(x):
    x = np.clip(x.astype(np.float32), 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)
def load(d, t):
    return srgb(np.fromfile(f'{d}/output_{sc.OW}x{sc.OH}_f{t:03d}.raw', dtype=np.float16).reshape(sc.OH, sc.OW, 4)[:, :, :3])
def shift(a, dx, dy):                       # result[y, x] = a[y + dy, x + dx]
    return np.roll(a, (-dy, -dx), axis=(0, 1))
def grow(m, r):
    o = m.copy()
    for dy in (-r, 0, r):
        for dx in (-r, 0, r):
            o |= shift(m, dx, dy)
    return o
frames = sorted(int(os.path.basename(f)[6:9]) for f in glob.glob(f'{inp}/truth_*.npy'))
edge = np.ones((sc.OH, sc.OW), bool); edge[96:-96, 96:-96] = False
acc, flick, refp = {}, {}, []
prev = None
for t in frames:
    out = load(outd, t)
    tru = srgb(np.load(f'{inp}/truth_{t:03d}.npy'))
    block, bars, rail = sc.masks(t)
    fg = block | bars
    yy, xx = np.mgrid[0:sc.OH, 0:sc.OW]
    stripes = block & (xx >= sc.BLOCK[0] + sc.VO[0] * t + sc.BLOCK[2] // 2)
    was = np.zeros_like(fg)
    for k in range(1, 5):
        b, r, _ = sc.masks(t - k); was |= b | r
    regions = {'whole frame': ~edge, 'background': ~grow(fg | rail | was, 8) & ~edge, 'block, texture half': block & ~stripes, 'block, fine stripes': stripes,
               'railing (bars and gaps)': rail, 'just uncovered': was & ~fg & ~rail}
    se = ((out - tru) ** 2).mean(axis=2)
    for n, m in regions.items():
        acc.setdefault(n, []).append(float(se[m].mean()))
    if prev is not None:
        d_bg = np.abs(out - shift(prev, sc.VB[0], sc.VB[1])).mean(axis=2) * 255
        d_fg = np.abs(out - shift(prev, -sc.VO[0], -sc.VO[1])).mean(axis=2) * 255
        pb, pr, prl = sc.masks(t - 1)
        bgm = regions['background'] & ~grow(shift(pb | pr | prl, sc.VB[0], sc.VB[1]), 8)
        flick.setdefault('background', []).append(float(d_bg[bgm].mean()))
        flick.setdefault('block, texture half', []).append(float(d_fg[block & ~stripes].mean()))
        flick.setdefault('block, fine stripes', []).append(float(d_fg[stripes].mean()))
        flick.setdefault('railing bars', []).append(float(d_fg[bars].mean()))
    if refd:
        refp.append(float(((out - load(refd, t)) ** 2).mean()))
    prev = out
db = lambda m: 99.0 if m == 0 else -10 * np.log10(m)
print(f'{len(frames)} frames ({frames[0]}..{frames[-1]})')
for n, v in acc.items():
    print(f'  PSNR vs true image, {n:24s} {db(np.mean(v)):6.2f} dB')
for n, v in flick.items():
    print(f'  frame-to-frame change, {n:22s} {np.mean(v):6.3f}')
if refd:
    print(f'  PSNR vs reference output                  {db(np.mean(refp)):6.2f} dB')
