#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# gen_inputs.py <4K image> <out dir> <frames> <sx> <sy>: jittered render-resolution frames
# (RGBA16F, linear) point-sampled from a ground-truth image, plus jitter.txt. sx, sy: jitter signs.
import sys, os, numpy as np
from PIL import Image
src, out, frames, sgx, sgy = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
ow_, oh_, rw, rh = (int(x) for x in os.environ.get('SCENE', '3840 2160 2260 1272').split())
im_ = Image.open(src).convert('RGB')
if im_.size != (ow_, oh_): im_ = im_.resize((ow_, oh_), Image.LANCZOS)
im = np.asarray(im_, dtype=np.float32) / 255.0
lin = np.where(im <= 0.04045, im / 12.92, ((im + 0.055) / 1.055) ** 2.4).astype(np.float32)
oh, ow = lin.shape[:2]
os.makedirs(out, exist_ok=True)
def halton(i, b):
    f, r = 1.0, 0.0
    while i > 0:
        f /= b; r += f * (i % b); i //= b
    return r
jit = []
for f in range(frames):
    jx, jy = halton(f % 16 + 1, 2) - 0.5, halton(f % 16 + 1, 3) - 0.5
    jit.append((jx, jy))
    u = (np.arange(rw) + 0.5 + sgx * jx) * ow / rw - 0.5
    v = (np.arange(rh) + 0.5 + sgy * jy) * oh / rh - 0.5
    u0 = np.clip(np.floor(u).astype(int), 0, ow - 2); fu = np.clip(u - u0, 0, 1).astype(np.float32)[None, :, None]
    v0 = np.clip(np.floor(v).astype(int), 0, oh - 2); fv = np.clip(v - v0, 0, 1).astype(np.float32)[:, None, None]
    a = lin[v0][:, u0]; b = lin[v0][:, u0 + 1]; c = lin[v0 + 1][:, u0]; d = lin[v0 + 1][:, u0 + 1]
    img = (a * (1 - fu) + b * fu) * (1 - fv) + (c * (1 - fu) + d * fu) * fv
    rgba = np.concatenate([img, np.ones((rh, rw, 1), np.float32)], axis=2).astype(np.float16)
    rgba.tofile(f'{out}/color_{f:03d}.raw')
open(f'{out}/jitter.txt', 'w').write(''.join(f'{x:.6f} {y:.6f}\n' for x, y in jit))
np.save(f'{out}/truth.npy', lin)
