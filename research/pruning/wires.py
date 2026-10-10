# SPDX-License-Identifier: GPL-2.0-or-later
# wires.py <scene dir> <frames dir> ... : thin wires of motion_scene.py (SCENE_WIRES). Along each wire's center line: how bright the upscaled wire is
# against the true one, how uneven it is along its length ("beads": standard deviation of the brightness along the line, minus the true
# image's), its brightest points, and how much it changes from frame to frame; skipped and run frames apart. 8-bit steps.
import sys, os, numpy as np
d = sys.argv[1]
for ln in open(d + '/scene.env'): k, v = ln.strip().split('=', 1); os.environ[k] = v
import motion_scene as sc
H, W = sc.OH, sc.OW
srgb = lambda x: (lambda x: np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055))(np.clip(x.astype(np.float32), 0, 1))
jit = [l.split() for l in open(d + '/jitter.txt').read().split('\n') if l.strip()]
def line(img, t):      # brightness along every wire: the brightest of the three rows around its center, per column
    out = []
    for x0, ys in sc.wire_rows(t):
        xs = x0 + np.arange(len(ys)); yy = np.rint(ys).astype(int); k = (xs >= 2) & (xs < W - 2) & (yy >= 2) & (yy < H - 2)
        out.append(np.max([img[yy[k] + dd, xs[k]] for dd in (-1, 0, 1)], 0))
    return np.concatenate(out)
for fd in sys.argv[2:]:
    acc = {'run': [], 'skipped': []}; prev = None
    for n in range(32, 40):
        f = f'{fd}/output_{W}x{H}_f{n:03d}.raw'
        if not os.path.exists(f): prev = None; continue
        o = line(srgb(np.fromfile(f, dtype=np.float16).reshape(H, W, 4)[:, :, :3]).mean(2), n) * 255; t = line(srgb(np.load(f'{d}/truth_{n:03d}.npy')).mean(2), n) * 255
        kind = 'skipped' if float(jit[n][0]) < 0 else 'run'
        ch = np.abs(o - prev).mean() if prev is not None and prev.shape == o.shape else np.nan
        acc[kind].append((o.mean(), t.mean(), o.std() - t.std(), np.percentile(o, 99.5) - np.percentile(t, 99.5), ch)); prev = o
    g = lambda k, i: np.nanmean([a[i] for a in acc[k]]) if acc[k] else float('nan')
    print(f"{os.path.basename(fd.rstrip('/')):10s} " + '   '.join(f"{k}: wire {g(k, 0):5.1f} (true {g(k, 1):5.1f}) beads {g(k, 2):+5.1f} peaks {g(k, 3):+6.1f} change/frame {g(k, 4):5.2f}" for k in ('run', 'skipped')))
