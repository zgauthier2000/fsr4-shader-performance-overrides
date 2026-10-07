#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_comparison_crops.py <dir>: the comparison images of docs/exact-vs-lossy.md (cmp-still.png,
# cmp-motion.png, cmp-flicker.png), from test-rig output (research/pruning: fsr4img with
# gen_inputs.py / gen_motion.py, 4K Balanced, 40 frames, the last 8 kept). <dir> holds
#   still_exact/, still_lossy/, motion_exact/, motion_lossy/   output_3840x2160_fNNN.raw (RGBA16F)
#   still_truth.npy, truth_037.npy                              the true 4K images
# "exact" is the main files (the same bytes as AMD's shaders give), "lossy" the lossy test build.
# The moving scene is the "as if at 60 FPS" one: SCENE_VB="12 6" SCENE_VO="-6 6" SCENE_PAD=1000.
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

D = sys.argv[1]
W, H = 3840, 2160
BG, INK, MUTED = (26, 26, 25), (255, 255, 255), (195, 194, 183)


def font(size):
    for p in ('/usr/share/fonts/TTF/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def srgb(x):
    x = np.clip(x.astype(np.float32), 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def load(d, n):
    return srgb(np.fromfile(f'{D}/{d}/output_3840x2160_f{n:03d}.raw', dtype=np.float16).reshape(H, W, 4)[:, :, :3])


def box(a, k):
    c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / k / k


def zoom(a, z):
    return np.repeat(np.repeat(a, z, 0), z, 1)


def rgb8(a):
    return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)


def gray(a):
    return np.repeat(rgb8(a)[:, :, None], 3, 2)


def sheet(title, sub, rows, name, note=None):
    """rows: list of (row label, [(panel label, uint8 image)])"""
    pw, ph = rows[0][1][0][1].shape[1], rows[0][1][0][1].shape[0]
    n = len(rows[0][1]); gap, m = 16, 32
    w = 2 * m + n * pw + (n - 1) * gap
    top = 118
    h = top + len(rows) * (ph + 78) + (48 if note else 8)
    im = Image.new('RGB', (w, h), BG); d = ImageDraw.Draw(im)
    d.text((m, 24), title, font=font(32), fill=INK); d.text((m, 70), sub, font=font(22), fill=MUTED)
    y = top
    for rl, panels in rows:
        d.text((m, y), rl, font=font(22), fill=INK)
        for i, (pl, a) in enumerate(panels):
            x = m + i * (pw + gap)
            im.paste(Image.fromarray(a), (x, y + 34)); d.text((x, y + 34 + ph + 6), pl, font=font(20), fill=MUTED)
        y += ph + 78
    if note:
        d.text((m, y), note, font=font(20), fill=MUTED)
    im.save(name, optimize=True)
    print(name, im.size)


# ---- still scene: where the two differ most
K = 90
tru = srgb(np.load(f'{D}/still_truth.npy'))
E = [load('still_exact', n) for n in range(32, 40)]; L = [load('still_lossy', n) for n in range(32, 40)]
d = np.abs(E[7] - L[7]).mean(2)
s = box(d, K)[200:-200, 200:-200]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 200; x += 200
crop = lambda a: a[y:y + K, x:x + K]
print('still: window', x, y, 'mean difference %.2f of 255, whole frame %.3f' % (crop(d).mean() * 255, d.mean() * 255))
sheet('Still scene: the spot where the two differ most',
      f'A {K} x {K} pixel piece of the 4K output, enlarged 4 times. Whole-frame mean difference: {d.mean() * 255:.2f} of 255.',
      [('', [('true image', rgb8(zoom(crop(tru), 4))), ("exact files (= AMD's)", rgb8(zoom(crop(E[7]), 4))),
             ('lossy build', rgb8(zoom(crop(L[7]), 4))), ('difference, 16 times amplified', gray(zoom(crop(d) * 16, 4)))])],
      'cmp-still.png')

# ---- flicker at rest
fe = np.mean([np.abs(a - b).mean(2) for a, b in zip(E, E[1:])], 0) * 255
fl = np.mean([np.abs(a - b).mean(2) for a, b in zip(L, L[1:])], 0) * 255
kw, kh = 240, 160
s = box(fl - fe, kh)[200:-200, 200:-200 - (kw - kh)]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 200; x += 200
fy, fx0 = y, x
cr = lambda a: a[fy:fy + kh, fx0:fx0 + kw]
print('flicker: window', x, y, 'exact %.3f lossy %.3f; whole frame %.3f %.3f' % (cr(fe).mean(), cr(fl).mean(), fe.mean(), fl.mean()))
heat = lambda a: gray(zoom(np.clip(cr(a) / 1.0, 0, 1), 2))        # white = 1 step of 255 per frame or more
sheet('Shimmer at rest: how much each pixel changes from frame to frame',
      f'Nothing moves. A {kw} x {kh} pixel piece where the lossy build is furthest from the exact files, enlarged 2 times.',
      [('', [('the picture', rgb8(zoom(cr(E[7]), 2))), (f"exact files (= AMD's): {cr(fe).mean():.3f}", heat(fe)), (f'lossy build: {cr(fl).mean():.3f}', heat(fl))])],
      'cmp-flicker.png', note=f'Black: no change. White: 1 step of 255 per frame or more. Whole frame: exact {fe.mean():.3f}, lossy {fl.mean():.3f}.')

# ---- moving scene, a skipped frame: thin bars and the edge a moving block has just uncovered
N = 37
t = srgb(np.load(f'{D}/truth_{N:03d}.npy').astype(np.float32)); e = load('motion_exact', N); l = load('motion_lossy', N)
de, dl = np.abs(e - t).mean(2), np.abs(l - t).mean(2)
rows = []
for label, (x0, y0, x1, y1) in (('Thin bars moving in front of a moving background', (2078, 1222, 2978, 1642)),
                                 ('The edge a moving block has just uncovered', (1978, 422, 2178, 1182))):
    s = box(dl - de, K)[y0:y1 - K, x0:x1 - K]; y, x = np.unravel_index(np.argmax(s), s.shape); y += y0; x += x0
    c = lambda a: a[y:y + K, x:x + K]
    print(label, 'window', x, y, 'error exact %.2f lossy %.2f of 255' % (c(de).mean() * 255, c(dl).mean() * 255))
    rows.append((f'{label}   (error against the true image: exact {c(de).mean() * 255:.1f}, lossy {c(dl).mean() * 255:.1f} of 255)',
                 [('true image', rgb8(zoom(c(t), 4))), ("exact files (= AMD's)", rgb8(zoom(c(e), 4))), ('lossy build, a skipped frame', rgb8(zoom(c(l), 4))),
                  ('difference, 8 times amplified', gray(zoom(c(np.abs(e - l).mean(2)) * 8, 4)))]))
sheet('In motion, on a frame the lossy build skips the model for',
      f'As if at 60 FPS (12 pixels of camera pan per frame). {K} x {K} pixel pieces where the lossy build is furthest off, enlarged 4 times.',
      rows, 'cmp-motion.png', note=f'Whole frame, error against the true image: exact {de.mean() * 255:.2f}, lossy {dl.mean() * 255:.2f} of 255.')
