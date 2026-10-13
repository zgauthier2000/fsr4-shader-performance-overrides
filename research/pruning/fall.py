# SPDX-License-Identifier: GPL-2.0-or-later
# fall.py <scene dir> <frames dir> ... : falling dark leaves in front of a dark sky (motion_scene.py SCENE_FALL; no motion vectors). Skipped and run frames apart:
#   shown  = how much of each leaf's darkness is shown where the leaf is now (share of the true contrast)
#   trail  = how much darkness is left where a leaf was 1 to 3 frames ago and is no longer (share of the leaf's contrast; and the darkest such pixel, 8-bit steps)
#   bright = pixels around the leaves (now or up to 3 frames ago) that are more than 6 / 15 steps of 255 BRIGHTER than the true image, per thousand; the largest excess
#   change over true = frame-to-frame change around the leaves minus the true image's own (flicker the leaves do not have), 8-bit steps
#   err    = mean error against the true image around the leaves, 8-bit steps
import sys, os, numpy as np
d = sys.argv[1]
for ln in open(d + '/scene.env'): k, v = ln.strip().split('=', 1); os.environ[k] = v
import motion_scene as sc
H, W = sc.OH, sc.OW
srgb = lambda x: (lambda x: np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055))(np.clip(x.astype(np.float32), 0, 1))
lum = lambda x: srgb(x).mean(2) * 255
jit = [l.split() for l in open(d + '/jitter.txt').read().split('\n') if l.strip()]
world = np.pad(np.load('img/truth.npy'), ((sc.PAD, sc.PAD), (sc.PAD, sc.PAD), (0, 0)), mode='reflect')
def bg(t):
    f = sc.FALL; sc.FALL = (0,) + tuple(f[1:]); im = sc.truth(world, t); sc.FALL = f; return im
B = lum(bg(36)); T = {}
def tr(n):
    if n not in T: T[n] = lum(sc.truth(world, n))
    return T[n]
box = np.zeros((H, W), bool); box[sc.FBOX[1] + 8:sc.FBOX[1] + sc.FBOX[3] - 8, sc.FBOX[0] + 8:sc.FBOX[0] + sc.FBOX[2] - 8] = True
for fd in sys.argv[2:]:
    acc = {}; po = None
    for n in range(32, 40):
        f = f'{fd}/output_{W}x{H}_f{n:03d}.raw'
        if not os.path.exists(f): continue
        o = lum(np.fromfile(f, dtype=np.float16).reshape(H, W, 4)[:, :, :3]); t = tr(n)
        now = (B - t > 4) & box; was = np.zeros((H, W), bool)
        for k in (1, 2, 3): was |= (B - tr(n - k) > 4)
        was &= box; gone = was & (np.abs(B - t) < 0.5)
        around = sc.fall_mask(n, 3) | sc.fall_mask(n - 1, 3) | sc.fall_mask(n - 2, 3); around &= box
        shown = (B - o)[now].sum() / max((B - t)[now].sum(), 1e-6)
        con = (B - t)[now].mean()                                   # mean contrast of a leaf pixel
        trail = np.clip(B - o, 0, None)[gone].mean() / con; tmax = (B - o)[gone].max()
        ex = (o - t)[around]; b6 = 1000 * (ex > 6).mean(); b15 = 1000 * (ex > 15).mean()
        kind = 'skipped' if float(jit[n][0]) < 0 else 'run'
        lit = (t - B > 25) & box; litp = (tr(n - 1) - B > 25) & box & ~lit
        gs = 100 * (o - B)[lit].sum() / max((t - B)[lit].sum(), 1e-6) if lit.sum() else np.nan; ga = 100 * (o - t)[litp].sum() / max((tr(n - 1) - B)[litp].sum(), 1e-6) if litp.sum() else np.nan
        ch = (np.abs(o - po)[around].mean() - np.abs(t - tr(n - 1))[around].mean()) if po is not None else np.nan; po = o
        acc.setdefault(kind, []).append((100 * shown, 100 * trail, tmax, b6, b15, ex.max(), np.abs(o - t)[around].mean(), ch, gs, ga))
    g = lambda k, i: np.nanmean([a[i] for a in acc[k]])
    print(f"{os.path.basename(fd.rstrip('/')):10s} " + '   '.join(f"{k}: shown {g(k, 0):5.1f}% trail {g(k, 1):5.1f}% (darkest {g(k, 2):4.1f}) bright >6: {g(k, 3):6.2f} >15: {g(k, 4):6.2f} per 1000 (max +{g(k, 5):5.1f}) err {g(k, 6):5.2f} change over true {g(k, 7):+5.2f} | glint shown {g(k, 8):5.1f}% left a frame later {g(k, 9):5.1f}%" for k in ('run', 'skipped') if k in acc))
