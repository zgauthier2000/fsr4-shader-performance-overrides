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
# SCENE_FADE = "<first frame> <change per frame> [step]": from that frame on the picture's brightness is multiplied by (1 + change) every frame
# (e.g. -0.01), or with "step" once by (1 + change); SCENE_FADEBOX = "x0 y0 x1 y1" (output pixels): only inside that box. Nothing moves.
FADE = os.environ.get('SCENE_FADE', '').split(); BOX = [int(x) for x in os.environ['SCENE_FADEBOX'].split()] if os.environ.get('SCENE_FADEBOX') else None
def mult(f):
    if not FADE or f < int(FADE[0]): return 1.0
    return 1 + float(FADE[1]) if len(FADE) > 2 else (1 + float(FADE[1])) ** (f - int(FADE[0]) + 1)
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
    m = mult(f)
    if m != 1.0:
        if BOX:      # only inside the box (output pixels): a light changing on part of the picture
            inb = ((v >= BOX[1]) & (v < BOX[3]))[:, None] & ((u >= BOX[0]) & (u < BOX[2]))[None, :]
            img = np.where(inb[:, :, None], img * m, img)
        else:
            img = img * m
    rgba = np.concatenate([img, np.ones((rh, rw, 1), np.float32)], axis=2).astype(np.float16)
    rgba.tofile(f'{out}/color_{f:03d}.raw')
open(f'{out}/jitter.txt', 'w').write(''.join(f'{x:.6f} {y:.6f}\n' for x, y in jit))
np.save(f'{out}/truth.npy', lin)
if FADE:
    open(f'{out}/fade.txt', 'w').write(''.join(f'{mult(f):.6f}\n' for f in range(frames)) )
    open(f'{out}/fade.env', 'w').write(os.environ.get('SCENE_FADE', '') + '\n' + os.environ.get('SCENE_FADEBOX', '') + '\n')
