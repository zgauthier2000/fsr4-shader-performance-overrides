#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# metric.py <output.raw> <reference .raw or truth.npy> : PSNR in sRGB display space (dB), max abs diff in 8-bit steps
import sys, os, numpy as np
OW, OH = (int(x) for x in os.environ.get('SCENE', '3840 2160').split()[:2])
def load(p):
    if p.endswith('.npy'): return np.load(p)
    return np.fromfile(p, dtype=np.float16).reshape(OH, OW, 4)[:, :, :3].astype(np.float32)
def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)
a, b = srgb(load(sys.argv[1])), srgb(load(sys.argv[2]))
e = a - b
mse = float((e * e).mean())
psnr = 99.0 if mse == 0 else -10 * np.log10(mse)
ae = np.abs(e) * 255
print(f'{psnr:.2f} dB  mean {ae.mean():.3f}  p99 {np.percentile(ae, 99):.2f}  max {ae.max():.1f}  (8-bit steps)')
