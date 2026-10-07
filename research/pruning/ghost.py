# SPDX-License-Identifier: GPL-2.0-or-later
# ghost.py <scene dir> <frames dir> ... : error against the true image where a moving object's previous image would land
# if the history were shown unchanged (the object's last position, carried along with the background), in 8-bit steps.
#   outline = the part of that area which the object's own motion has left (width |VO|): the "second outline"
#   body    = the rest of the area the block uncovered;   bars = where the thin bars' previous image lands
import sys, os, numpy as np
d = sys.argv[1]
for ln in open(d + '/scene.env') if os.path.exists(d + '/scene.env') else []:
    k, v = ln.strip().split('=', 1); os.environ[k] = v
import motion_scene as sc
H, W = sc.OH, sc.OW
def srgb(x):
    x = np.clip(x.astype(np.float32), 0, 1); return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)
def shift(m, dx, dy):
    o = np.zeros_like(m); ys, xs = np.nonzero(m); xs = xs + dx; ys = ys + dy; k = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H); o[ys[k], xs[k]] = True; return o
jit = [l.split() for l in open(d + '/jitter.txt').read().split('\n') if l.strip()]
for fd in sys.argv[2:]:
    acc = {}
    for n in range(32, 40):
        f = f'{fd}/output_{W}x{H}_f{n:03d}.raw'
        if not os.path.exists(f) or not os.path.exists(f'{d}/truth_{n:03d}.npy'): continue
        out = srgb(np.fromfile(f, dtype=np.float16).reshape(H, W, 4)[:, :, :3]); t = srgb(np.load(f'{d}/truth_{n:03d}.npy').astype(np.float32))
        e = np.abs(out - t).mean(2) * 255
        blk, bars, rb = sc.masks(n); pb, pbars, prb = sc.masks(n - 1)
        now = blk | bars
        gb = shift(pb, -sc.VB[0], -sc.VB[1]) & ~now          # where the block's previous image lands
        seen = shift(blk, -sc.VB[0], -sc.VB[1])              # what a test "is the object now where this content was?" covers
        outline = gb & ~seen; body = gb & seen
        gbar = shift(pbars, -sc.VB[0], -sc.VB[1]) & ~now & ~gb
        # only the bars' images that land clear of the railing itself (beside it), so that the bars' own error does not count
        ys, xs = np.nonzero(rb); clear = np.ones_like(gbar)
        clear[:, max(0, xs.min() - 4):min(W, xs.max() + 5)] = False; gbar &= clear
        kind = 'skip' if float(jit[n][0]) < 0 else 'run'
        for nm, m in (('outline', outline), ('body', body), ('bars', gbar)):
            if m.any(): acc.setdefault((kind, nm), []).append(e[m].mean())
    print(f'{os.path.basename(fd):12s} ' + '  '.join(f'{k} {nm}: {np.mean(acc[k, nm]):5.2f}' for k in ('skip', 'run') for nm in ('outline', 'body', 'bars') if (k, nm) in acc))
