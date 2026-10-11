#!/usr/bin/env python3
# rain.py gen <out dir> <frames> <keep>      inputs for the rain scene
# rain.py metric <scene dir> <frames dir> [more frame dirs]
# The firefly scene (fireflies.py) with one more kind of input, FF_MODE=rain: still camera, 2260x1272 -> 3840x2160, a dark mottled panel; in its
# LEFT half the render-size input carries rain, without motion vectors.
#   FF_MODE=rain     FF_P streaks per render pixel of area, each one render pixel wide and FF_R long, falling RAIN_S render pixels a frame;
#                    FF_B is the light a streak adds (linear; the panel is about 0.004 to 0.04)
#   FF_MODE=random, glint    as in fireflies.py
# The metric prints, for the two kinds of frame (a = even, b = odd kept frames), how many output pixels are more than 20 display levels above
# the panel, per million, and the mean excess of the brightest 0.05%.
import sys, os, numpy as np
OW, OH, RW, RH = 3840, 2160, 2260, 1272
PX0, PX1, PY0, PY1 = 1120, 2720, 480, 1680          # the panel, output pixels; left half x < PXM
PXM = (PX0 + PX1) // 2
MODE = os.environ.get('FF_MODE', 'random'); P = float(os.environ.get('FF_P', '0.001')); B = float(os.environ.get('FF_B', '2.0')); R = float(os.environ.get('FF_R', '0.2'))
HERE = os.path.dirname(os.path.abspath(__file__))
def halton(i, b):
    f, r = 1.0, 0.0
    while i > 0:
        f /= b; r += f * (i % b); i //= b
    return r
def smooth_noise(rng, h, w, cell):
    g = rng.random((h // cell + 3, w // cell + 3), dtype=np.float32)
    y = np.arange(h) / cell; x = np.arange(w) / cell
    y0 = y.astype(int); x0 = x.astype(int); fy = (y - y0)[:, None].astype(np.float32); fx = (x - x0)[None, :].astype(np.float32)
    fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]; b = g[y0][:, x0 + 1]; c = g[y0 + 1][:, x0]; d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
def world():
    img = np.load(HERE + '/img/truth.npy').astype(np.float32).copy()
    rng = np.random.default_rng(7); h, w = PY1 - PY0, PX1 - PX0
    n = 0.6 * smooth_noise(rng, h, w, 160) + 0.3 * smooth_noise(rng, h, w, 40) + 0.1 * smooth_noise(rng, h, w, 6)
    n = np.clip((n - 0.3) / 0.4, 0, 1) ** 2                      # dark with lighter blotches
    lum = 0.004 + 0.036 * n
    img[PY0:PY1, PX0:PX1] = lum[:, :, None] * np.float32([0.85, 1.0, 0.8])
    return img
def lvl(x): return 255 * np.clip(x.astype(np.float32), 0, 1) ** (1 / 2.2)      # what a display shows
if sys.argv[1] == 'gen':
    out, frames, keep = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]); os.makedirs(out, exist_ok=True)
    img = world(); np.save(out + '/truth.npy', img.astype(np.float16))
    sx, sy = RW / OW, RH / OH
    rx0, rx1, ry0, ry1 = int(np.ceil(PX0 * sx)) + 2, int(PXM * sx) - 2, int(np.ceil(PY0 * sy)) + 2, int(PY1 * sy) - 2      # left half in render pixels
    rng = np.random.default_rng(11)
    if MODE == 'glint':
        n = int(P * (rx1 - rx0) * (ry1 - ry0)); gx = rng.uniform(rx0, rx1, n); gy = rng.uniform(ry0, ry1, n)
    jit = []; hits = []
    for f in range(frames):
        jx, jy = halton(f % 16 + 1, 2) - 0.5, halton(f % 16 + 1, 3) - 0.5; jit.append((jx, jy))
        u = (np.arange(RW) + 0.5 - jx) / sx - 0.5; v = (np.arange(RH) + 0.5 - jy) / sy - 0.5
        u0 = np.clip(np.floor(u).astype(int), 0, OW - 2); fu = np.clip(u - u0, 0, 1).astype(np.float32)[None, :, None]
        v0 = np.clip(np.floor(v).astype(int), 0, OH - 2); fv = np.clip(v - v0, 0, 1).astype(np.float32)[:, None, None]
        a = img[v0][:, u0]; b = img[v0][:, u0 + 1]; c = img[v0 + 1][:, u0]; d = img[v0 + 1][:, u0 + 1]
        col = (a * (1 - fu) + b * fu) * (1 - fv) + (c * (1 - fu) + d * fu) * fv
        if MODE == 'rain':      # FF_P streaks per render pixel of area, 1 render pixel wide, FF_R long, falling RAIN_S render pixels a frame; added light
            S = float(os.environ.get('RAIN_S', '30')); Lr = int(R); span = ry1 - ry0 + Lr
            if f == 0:
                nr = int(P * (rx1 - rx0) * (ry1 - ry0)); gx = rng.integers(rx0, rx1, nr); gy = rng.uniform(0, span, nr)
            top = ry0 - Lr + (gy + S * f) % span
            n_lit = 0
            for x, t in zip(gx, top):
                y0 = max(int(t), ry0); y1 = min(int(t) + Lr, ry1)
                if y1 > y0: col[y0:y1, x] += B; n_lit += y1 - y0
            hits.append(n_lit)
        else:
          if MODE == 'random':
            m = rng.random((ry1 - ry0, rx1 - rx0)) < P; ys, xs = np.nonzero(m); ys += ry0; xs += rx0
          else:
            px = np.floor(gx + jx).astype(int); py = np.floor(gy + jy).astype(int)
            near = (px + 0.5 - jx - gx) ** 2 + (py + 0.5 - jy - gy) ** 2 < R * R
            xs, ys = px[near], py[near]
          col[ys, xs] = B; hits.append(len(xs))
        np.concatenate([col, np.ones((RH, RW, 1), np.float32)], axis=2).astype(np.float16).tofile(f'{out}/color_{f:03d}.raw')
        np.zeros((RH, RW, 2), np.float16).tofile(f'{out}/motion_{f:03d}.raw')
        np.full((RH, RW), 0.5, np.float32).tofile(f'{out}/depth_{f:03d}.raw')
    open(out + '/jitter.txt', 'w').write(''.join(f'{x:.6f} {y:.6f}\n' for x, y in jit))
    area = (rx1 - rx0) * (ry1 - ry0)
    open(out + '/ff.txt', 'w').write(f'{MODE} P={P} B={B} R={R} keep={keep} mean_hits={np.mean(hits):.1f} share={np.mean(hits) / area:.6f}\n')
    print(open(out + '/ff.txt').read().strip())
else:
    d = sys.argv[2]; info = open(d + '/ff.txt').read().split(); share = float(info[-1].split('=')[1]); b_in = float(info[2].split('=')[1])
    truth = np.load(d + '/truth.npy').astype(np.float32).mean(2)
    M = 24      # stay clear of the panel's edges and of the border between the halves
    reg = {'fireflies': (slice(PY0 + M, PY1 - M), slice(PX0 + M, PXM - M)), 'control': (slice(PY0 + M, PY1 - M), slice(PXM + M, PX1 - M))}
    print(f'# {" ".join(info)}; true mean lift of the firefly half: {share * b_in:.4f} linear')
    print(f'# {"":14s} {"":9s}  mean level  over truth by >10 / >20 / >40 levels (pixels per million)   brightest  change/frame  specks still there next frame')
    ys, xs = reg['fireflies']; t = lvl(truth[ys, xs])
    print('# per kept frame: output pixels more than 20 levels over the background, per million | mean excess of the brightest 0.05% of pixels (levels)')
    for fd in sys.argv[3:]:
        files = sorted(f for f in os.listdir(fd) if f.endswith('.raw') and '_f' in f)
        c = []; p = []
        for f in files:
            e = lvl(np.fromfile(f'{fd}/{f}', dtype=np.float16).reshape(OH, OW, 4)[:, :, :3].astype(np.float32).mean(2)[ys, xs]) - t
            c.append((e > 20).mean() * 1e6); k = max(1, e.size // 2000); p.append(np.sort(e, axis=None)[-k:].mean())
        c = np.array(c); p = np.array(p)
        print(f'{os.path.basename(fd):16s} >20: a {c[0::2].mean():8.0f}  b {c[1::2].mean():8.0f}   peak: a {p[0::2].mean():6.1f}  b {p[1::2].mean():6.1f}   series >20: ' + ' '.join(f'{x:.0f}' for x in c[:8]))
