# SPDX-License-Identifier: GPL-2.0-or-later
# particles.py <scene dir> <frames dir> ... : how much of each particle (no motion vectors) is shown where it is now, and how much is left where it
# was a frame ago, as a share of its true brightness over the true background; skipped and run frames apart.
import sys, os, numpy as np
d = sys.argv[1]
for ln in open(d + '/scene.env'): k, v = ln.strip().split('=', 1); os.environ[k] = v
import motion_scene as sc
H, W = sc.OH, sc.OW
lum = lambda x: np.clip(x.astype(np.float32), 0, 4).mean(2)
jit = [l.split() for l in open(d + '/jitter.txt').read().split('\n') if l.strip()]
world = np.pad(np.load('img/truth.npy'), ((sc.PAD, sc.PAD), (sc.PAD, sc.PAD), (0, 0)), mode='reflect')
def bg(t):      # the true frame without particles
    n = sc.NP; sc.NP = 0; im = sc.truth(world, t); sc.NP = n; return im
WIDE = os.environ.get('WIDE') == '1'      # WIDE=1: measure over the glow as well, not just the core
def core(t):
    m = np.zeros((H, W), bool)
    for x, y, rad, br in zip(*sc.particles(t)):
        k = max(1, int(round(rad * (2 * sc.PGLOW[0] if (sc.PGLOW and WIDE) else 1)))); m[max(0, y - k):y + k + 1, max(0, x - k):x + k + 1] = True
    return m
for fd in sys.argv[2:]:
    acc = {}
    for n in range(32, 40):
        f = f'{fd}/output_{W}x{H}_f{n:03d}.raw'
        if not os.path.exists(f): continue
        out = lum(np.fromfile(f, dtype=np.float16).reshape(H, W, 4)[:, :, :3]); t = lum(np.load(f'{d}/truth_{n:03d}.npy')); b = lum(bg(n))
        now = core(n); was = np.roll(np.roll(core(n - 1), -sc.VB[1], 0), -sc.VB[0], 1) & ~now      # last frame's place, carried along with the background
        shown = (out - b)[now].sum() / max((t - b)[now].sum(), 1e-6)
        prev = lum(np.load(f'{d}/truth_{n - 1:03d}.npy')) if os.path.exists(f'{d}/truth_{n - 1:03d}.npy') else None
        left = (out - b)[was].sum() / max((t - b)[now].sum(), 1e-6)
        kind = 'skipped' if float(jit[n][0]) < 0 else 'run'
        import numpy as _n
        wide = _n.zeros((H, W), bool)
        for x_, y_, r_, b_ in zip(*sc.particles(n)):
            k_ = int(3 * r_ * (sc.PGLOW[0] if sc.PGLOW else 1)) + 2; wide[max(0, y_ - k_):y_ + k_ + 1, max(0, x_ - k_):x_ + k_ + 1] = True
        outc = np.clip(np.fromfile(f, dtype=np.float16).reshape(H, W, 4)[:, :, :3].astype(np.float32), 0, 4); tc_ = np.clip(np.load(f'{d}/truth_{n:03d}.npy').astype(np.float32), 0, 4)
        err = float(np.abs(outc - tc_).mean(2)[wide].mean()) * 255
        acc.setdefault(kind, []).append((shown, left, err))
    allv = [a[0] for k in acc for a in acc[k]]
    print(f'{os.path.basename(fd):12s} ' + '   '.join(f'{k}: shown {100 * np.mean([a[0] for a in acc[k]]):5.1f}%  left behind {100 * np.mean([a[1] for a in acc[k]]):5.1f}%  err {np.mean([a[2] for a in acc[k]]):.2f}' for k in ('run', 'skipped') if k in acc))
