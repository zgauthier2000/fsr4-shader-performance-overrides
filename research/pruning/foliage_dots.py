# SPDX-License-Identifier: GPL-2.0-or-later
# foliage_dots.py <scene dir> <frames dir> : single bright pixels inside dark foliage (sky seen through leaves and shown as a dot). In the foliage area of
# motion_scene.py (SCENE_FOLIAGE, inputs made with SCENE_POINT=1): pixels more than 0.15 (sRGB, of 1) brighter than the median of their 3x3 surroundings where
# the true image is dark there, per thousand dark pixels; the frames a frame-skip build skips (odd) and runs (even) apart. <scene dir> holds scene.env.
import sys, os, numpy as np
d, fd = sys.argv[1], sys.argv[2]
for ln in open(d + '/scene.env'): k, v = ln.strip().split('=', 1); os.environ[k] = v
sys.path.insert(0, os.getcwd()); import motion_scene as sc
H, W = sc.OH, sc.OW
srgb = lambda x: (lambda x: np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055))(np.clip(x.astype(np.float32), 0, 1))
jit = [l.split() for l in open(d + '/jitter.txt').read().split('\n') if l.strip()]
x0, y0, w, h = sc.FBOX
def med3(a):
    p = np.pad(a, 1, mode='edge'); return np.median(np.stack([p[i:i + a.shape[0], j:j + a.shape[1]] for i in range(3) for j in range(3)]), 0)
r = {'skipped': [], 'run': []}; e = []
for n in range(32, 40):
    f = f'{fd}/output_{W}x{H}_f{n:03d}.raw'
    if not os.path.exists(f): continue
    t = srgb(np.load(f'{d}/truth_{n:03d}.npy')[y0:y0 + h, x0:x0 + w].astype(np.float32)).mean(2)
    o = srgb(np.fromfile(f, dtype=np.float16).reshape(H, W, 4)[y0:y0 + h, x0:x0 + w, :3]).mean(2)
    dark = med3(t) < 0.3
    r['skipped' if float(jit[n][0]) < 0 else 'run'].append(((o - med3(o) > 0.15) & dark).sum() / max(dark.sum(), 1) * 1000); e.append(np.abs(o - t).mean() * 255)
print(f'isolated bright dots per thousand dark pixels: odd frames {np.mean(r["skipped"]):.2f}  even frames {np.mean(r["run"]):.2f}  all {np.mean(r["skipped"] + r["run"]):.2f}; error {np.mean(e):.2f}')
