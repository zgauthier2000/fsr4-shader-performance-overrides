#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# gen_motion.py <truth.npy from gen_inputs.py> <out dir> <frames> <keep> [mv sign, default 1]
# Inputs for the moving scene of motion_scene.py: per frame color (RGBA16F), motion vectors
# (RG16F, render pixels, pointing from a pixel to where it was in the previous frame), depth (R32F)
# and jitter; and the true 4K image of the last <keep> frames (truth_NNN.npy).
import sys, os, numpy as np
import motion_scene as sc
src, out, frames, keep = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
mvs = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
os.makedirs(out, exist_ok=True)
world = np.pad(np.load(src), ((sc.PAD, sc.PAD), (sc.PAD, sc.PAD), (0, 0)), mode='reflect')
assert sc.PAD > max(sc.VB) * frames + 8
def halton(i, b):
    f, r = 1.0, 0.0
    while i > 0:
        f /= b; r += f * (i % b); i //= b
    return r
sx, sy = sc.RW / sc.OW, sc.RH / sc.OH
jit = []
for f in range(frames):
    jx, jy = halton(f % 16 + 1, 2) - 0.5, halton(f % 16 + 1, 3) - 0.5
    jit.append((jx, jy))
    img = sc.truth(world, f)
    truth_img = img
    wires = getattr(sc, 'WIRES', None)
    if wires:      # the game does not anti-alias a wire: a render pixel shows it only if its (jittered) center falls on it. Sample the picture without the wires...
        sc.WIRES = None; img = sc.truth(world, f); sc.WIRES = wires
    block, bars, _ = sc.masks(f)
    fg = block | bars
    u = (np.arange(sc.RW) + 0.5 - jx) / sx - 0.5          # jitter signs -1 -1, as in gen_inputs.py
    v = (np.arange(sc.RH) + 0.5 - jy) / sy - 0.5
    u0 = np.clip(np.floor(u).astype(int), 0, sc.OW - 2); fu = np.clip(u - u0, 0, 1).astype(np.float32)[None, :, None]
    v0 = np.clip(np.floor(v).astype(int), 0, sc.OH - 2); fv = np.clip(v - v0, 0, 1).astype(np.float32)[:, None, None]
    a = img[v0][:, u0]; b = img[v0][:, u0 + 1]; c = img[v0 + 1][:, u0]; d = img[v0 + 1][:, u0 + 1]
    col = (a * (1 - fu) + b * fu) * (1 - fv) + (c * (1 - fu) + d * fu) * fv
    if os.environ.get('SCENE_POINT') == '1':      # as a game renders: every render pixel takes the scene at its (jittered) center, nothing is smoothed, so thin things are hit or miss
        col = img[np.clip(np.rint(v).astype(int), 0, sc.OH - 1)][:, np.clip(np.rint(u).astype(int), 0, sc.OW - 1)]
    if wires:      # ...and draw each wire into the render pixels whose centers it covers
        wcol = np.float32([wires[2], wires[2], wires[2] * 1.05])
        for x0, ys in sc.wire_rows(f):
            yw = np.interp(u, x0 + np.arange(len(ys)), ys, left=np.nan, right=np.nan)       # the wire's height above each render column
            for i in np.nonzero(~np.isnan(yw))[0]:
                hit = np.nonzero(np.abs(v + 0.5 - (yw[i] + 0.5)) < wires[1] / 2)[0]
                col[hit, i] = wcol
    np.concatenate([col, np.ones((sc.RH, sc.RW, 1), np.float32)], axis=2).astype(np.float16).tofile(f'{out}/color_{f:03d}.raw')
    un = np.clip(np.rint(u).astype(int), 0, sc.OW - 1); vn = np.clip(np.rint(v).astype(int), 0, sc.OH - 1)
    m = fg[vn][:, un]
    mv = np.empty((sc.RH, sc.RW, 2), np.float32)
    mv[..., 0] = np.where(m, -sc.VO[0], sc.VB[0]) * sx * mvs     # previous position minus current position
    mv[..., 1] = np.where(m, -sc.VO[1], sc.VB[1]) * sy * mvs
    mv.astype(np.float16).tofile(f'{out}/motion_{f:03d}.raw')
    np.where(m, np.float32(sc.DEPTH_FG), np.float32(sc.DEPTH_BG)).astype(np.float32).tofile(f'{out}/depth_{f:03d}.raw')
    if f >= frames - keep:
        np.save(f'{out}/truth_{f:03d}.npy', truth_img.astype(np.float16))
open(f'{out}/jitter.txt', 'w').write(''.join(f'{x:.6f} {y:.6f}\n' for x, y in jit))
