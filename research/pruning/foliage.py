# SPDX-License-Identifier: GPL-2.0-or-later
# foliage.py <scene dir> <frames dir> ... : the foliage area of motion_scene.py (SCENE_FOLIAGE): error against the true image, and how much that
# error changes from frame to frame (flicker that is not the scene's own motion), on leaves and their surroundings; skipped and run frames apart.
import sys, os, numpy as np
d = sys.argv[1]
for ln in open(d + '/scene.env'): k, v = ln.strip().split('=', 1); os.environ[k] = v
import motion_scene as sc
H, W = sc.OH, sc.OW
srgb = lambda x: (lambda x: np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055))(np.clip(x.astype(np.float32), 0, 1))
jit = [l.split() for l in open(d + '/jitter.txt').read().split('\n') if l.strip()]
x0, y0, w, h = sc.FBOX
for fd in sys.argv[2:]:
    acc = {'run': [], 'skipped': []}; chg = {'run': [], 'skipped': []}; prev = None
    for n in range(32, 40):
        f = f'{fd}/output_{W}x{H}_f{n:03d}.raw'
        if not os.path.exists(f): prev = None; continue
        out = srgb(np.fromfile(f, dtype=np.float16).reshape(H, W, 4)[:, :, :3]); t = srgb(np.load(f'{d}/truth_{n:03d}.npy'))
        m = sc.leaf_mask(n, 2)[y0:y0 + h, x0:x0 + w]
        e = (out - t)[y0:y0 + h, x0:x0 + w]
        kind = 'skipped' if float(jit[n][0]) < 0 else 'run'
        acc[kind].append((np.abs(e).mean(2)[m].mean() * 255, 10 * np.log10(1 / np.mean(e[m] ** 2))))
        if prev is not None:
            chg[kind].append(np.abs(e - prev).mean(2)[m].mean() * 255)
        prev = e
    g = lambda k, i: np.mean([a[i] for a in acc[k]]) if acc[k] else float('nan')
    c = lambda k: np.mean(chg[k]) if chg[k] else float('nan')
    print(f"{os.path.basename(fd.rstrip('/')):12s} run: err {g('run', 0):.2f} ({g('run', 1):.2f} dB) flicker {c('run'):.2f}   skipped: err {g('skipped', 0):.2f} ({g('skipped', 1):.2f} dB) flicker {c('skipped'):.2f}")
