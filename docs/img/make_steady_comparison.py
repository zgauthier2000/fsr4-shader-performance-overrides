#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_steady_comparison.py <dir>: the pictures of docs/steady-test.md (steady-flicker.png, steady-still.png, steady-motion.png): the exact files beside the
# unreleased "steady" test build (the exact files with the dead band of research/frame-skip/skipblend.py in the postpass, no frame skip), from test-rig output
# (research/pruning, 4K Balanced, 40 frames). <dir> holds, for X = exact and steady:
#   still_X/     output_3840x2160_f032..039.raw (RGBA16F), and still_truth.npy, the true 4K image
#   motion_X/    frames 36 and 37 of the moving scene (SCENE_VB="12 6" SCENE_VO="-6 6" SCENE_PAD=1000), and motion_truth_036.npy, motion_truth_037.npy
# The exact files give the same bytes as AMD's shaders, so their panels are also AMD's picture.
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
    top = 118 + 30 * sub.count('\n')
    h = top + len(rows) * (ph + 78) + ((48 + 28 * note.count('\n')) if note else 8)
    im = Image.new('RGB', (w, h), BG); d = ImageDraw.Draw(im)
    d.text((m, 24), title, font=font(32), fill=INK); d.multiline_text((m, 70), sub, font=font(22), fill=MUTED, spacing=8)
    y = top
    for rl, panels in rows:
        d.text((m, y), rl, font=font(22), fill=INK)
        for i, (pl, a) in enumerate(panels):
            x = m + i * (pw + gap)
            if a is None:      # an empty place
                continue
            im.paste(Image.fromarray(a), (x, y + 34)); d.text((x, y + 34 + ph + 6), pl, font=font(20), fill=MUTED)
        y += ph + 78
    if note:
        d.multiline_text((m, y), note, font=font(20), fill=MUTED, spacing=8)
    im.save(name, optimize=True)
    print(name, im.size)


# ---- shimmer at rest: how much each pixel changes from frame to frame, where the two builds differ most
tru = srgb(np.load(f'{D}/still_truth.npy'))
E = [load('still_exact', n) for n in range(32, 40)]; S = [load('still_steady', n) for n in range(32, 40)]
fl_ = lambda F: np.mean([np.abs(a - b).mean(2) for a, b in zip(F, F[1:])], 0) * 255
fe, fs = fl_(E), fl_(S)
kw, kh = 240, 160
s = box(fe - fs, kh)[200:-200, 200:-200 - (kw - kh)]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 200; x += 200
cr = lambda a: a[y:y + kh, x:x + kw]
heat = lambda a: gray(zoom(np.clip(cr(a) / 1.0, 0, 1), 2))
print('flicker: window', x, y, 'exact %.3f steady %.3f; whole frame %.3f %.3f' % (cr(fe).mean(), cr(fs).mean(), fe.mean(), fs.mean()))
sheet('Shimmer at rest: how much each pixel changes from frame to frame',
      f'Nothing moves. The {kw} x {kh} pixel piece where the two builds differ most, enlarged 2 times.\nBlack: no change. White: 1 step of 255 per frame or more.',
      [('', [('the picture', rgb8(zoom(cr(E[7]), 2))), (f"exact files (= AMD's): {cr(fe).mean():.3f}", heat(fe)), (f'steady test: {cr(fs).mean():.3f}', heat(fs))])],
      'steady-flicker.png', note=f'Whole frame: exact {fe.mean():.3f}, steady test {fs.mean():.3f}.')

# ---- the still picture: where the two builds differ most, and their difference amplified
K = 90
dd = np.abs(E[7] - S[7]).mean(2)
s = box(dd, K)[200:-200, 200:-200]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 200; x += 200
crop = lambda a: a[y:y + K, x:x + K]
ee, es = np.abs(E[7] - tru).mean(2), np.abs(S[7] - tru).mean(2)
ps = lambda F: np.mean([10 * np.log10(1 / np.mean((f - tru) ** 2)) for f in F])
print('still: window', x, y, 'difference between the two %.3f of 255 (whole frame %.3f); error exact %.2f steady %.2f; PSNR %.2f %.2f' % (crop(dd).mean() * 255, dd.mean() * 255, crop(ee).mean() * 255, crop(es).mean() * 255, ps(E), ps(S)))
sheet('Still picture: the spot where the two builds differ most',
      f'A {K} x {K} pixel piece of the 4K output, enlarged 4 times. Whole frame against the true image: exact {ps(E):.2f} dB, steady test {ps(S):.2f} dB.',
      [('', [('true image', rgb8(zoom(crop(tru), 4))), (f"exact files (= AMD's): error {crop(ee).mean() * 255:.2f}", rgb8(zoom(crop(E[7]), 4))),
             (f'steady test: error {crop(es).mean() * 255:.2f}', rgb8(zoom(crop(S[7]), 4))),
             (f'difference x 64 ({crop(dd).mean() * 255:.2f} of 255)', gray(zoom(crop(dd) * 64, 4)))])],
      'steady-still.png', note=f'Mean difference between the two builds over the whole frame: {dd.mean() * 255:.3f} of 255. Errors are against the true image, of 255.')
del E, S

# ---- the moving scene (frame 37): the piece where the steady build gains most over the exact files, and the piece where it loses most
tm = srgb(np.load(f'{D}/motion_truth_037.npy')); me, ms = load('motion_exact', 37), load('motion_steady', 37)
ee, es = np.abs(me - tm).mean(2), np.abs(ms - tm).mean(2)
rows = []
for label, sign in (('Where the steady test is closest to the true image compared with the exact files', 1), ('Where it is furthest behind them', -1)):
    s = box(sign * (ee - es), K)[200:-200, 200:-200]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 200; x += 200
    c = lambda a: a[y:y + K, x:x + K]
    print(label, 'window', x, y, 'error exact %.2f steady %.2f of 255' % (c(ee).mean() * 255, c(es).mean() * 255))
    rows.append((label + '   (error against the true image, of 255)',
                 [('true image', rgb8(zoom(c(tm), 4))), (f"exact files (= AMD's): {c(ee).mean() * 255:.2f}", rgb8(zoom(c(me), 4))), (f'steady test: {c(es).mean() * 255:.2f}', rgb8(zoom(c(ms), 4))),
                  ('difference between the two x 16', gray(zoom(c(np.abs(me - ms).mean(2)) * 16, 4)))]))
sheet('Moving scene: camera panning, objects moving', f'{K} x {K} pixel pieces of the 4K output, enlarged 4 times.', rows, 'steady-motion.png',
      note=f'Whole frame, error against the true image: exact {ee.mean() * 255:.3f}, steady test {es.mean() * 255:.3f} of 255.')
