#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_comparison_crops.py <dir>: the comparison images of docs/exact-vs-lossy.md (cmp-still.png,
# cmp-motion.png, cmp-flicker.png, cmp-grain.png, cmp-particles.png), from test-rig output (research/pruning: fsr4img with
# gen_inputs.py / gen_motion.py, 4K Balanced, 40 frames, the last 8 kept). <dir> holds, for X = exact (the main
# files), prev (the lossy build of release dll-2026-10-07) and lossy (the current lossy build, release dll-2026-10-10):
#   still_X/                 output_3840x2160_f032..039.raw (RGBA16F), and still_truth.npy, the true 4K image
#   still_r9/, grain_X/, grain_r9/   the same frames with the lossy build of release dll-2026-10-09 (r9), and of the still scene
#       with random grain added to every input frame (standard deviation 6 of 255, sRGB)
#   motion_X/, part_X/, big_X/   frame 37 (a frame the lossy builds skip the model for) of the moving scene, of the scene
#       with tiny fast particles and of the one with large particles (camera still; the particles are in the color image
#       only, without motion vectors), and motion_truth_037.npy, part_truth_037.npy, big_truth_037.npy
#   ghost_exact/, ghost_r6/, ghost_lossy/, ghost_truth_037.npy   frame 37 of the ghost scene (research/pruning/ghost.py): camera
#       panning 40 pixels per frame, objects drifting 6 (SCENE_VB="40 0" SCENE_VO="6 0" SCENE_PAD=1700), with the exact files,
#       the lossy build of release dll-2026-10-06.6 and the current lossy build -> cmp-ghost.png
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


# ---- still scene: where the previous release differs most from the exact files
K = 90
tru = srgb(np.load(f'{D}/still_truth.npy'))
E = [load('still_exact', n) for n in range(32, 40)]; P = [load('still_prev', n) for n in range(32, 40)]; L = [load('still_lossy', n) for n in range(32, 40)]
dp, dl = np.abs(E[7] - P[7]).mean(2), np.abs(E[7] - L[7]).mean(2)
s = box(dp, K)[200:-200, 200:-200]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 200; x += 200
crop = lambda a: a[y:y + K, x:x + K]
print('still: window', x, y, 'difference from exact, previous %.2f now %.2f of 255; whole frame %.3f %.3f' % (crop(dp).mean() * 255, crop(dl).mean() * 255, dp.mean() * 255, dl.mean() * 255))
sheet('Still scene: the spot where release dll-2026-10-07 differed most',
      f'A {K} x {K} pixel piece of the 4K output, enlarged 4 times.\nWhole-frame mean difference from the exact files: dll-2026-10-07 {dp.mean() * 255:.2f}, this release {dl.mean() * 255:.2f} of 255.',
      [('', [('true image', rgb8(zoom(crop(tru), 4))), ("exact files (= AMD's)", rgb8(zoom(crop(E[7]), 4))),
             ('lossy, release dll-2026-10-07', rgb8(zoom(crop(P[7]), 4))), ('lossy, this release', rgb8(zoom(crop(L[7]), 4)))]),
       ('   difference from the exact files, 16 times amplified',
        [('', None), ('', None),
         (f'{crop(dp).mean() * 255:.2f} of 255', gray(zoom(crop(dp) * 16, 4))), (f'{crop(dl).mean() * 255:.2f} of 255', gray(zoom(crop(dl) * 16, 4)))])],
      'cmp-still.png')

# ---- flicker at rest
fl_ = lambda F: np.mean([np.abs(a - b).mean(2) for a, b in zip(F, F[1:])], 0) * 255
R9 = [load('still_r9', n) for n in range(32, 40)]
fe, fp, f9, fl = fl_(E), fl_(P), fl_(R9), fl_(L)
del R9
kw, kh = 240, 160
s = box(np.maximum(np.maximum(fp, f9), fl) - fe, kh)[200:-200, 200:-200 - (kw - kh)]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 200; x += 200
fy, fx0 = y, x
cr = lambda a: a[fy:fy + kh, fx0:fx0 + kw]
print('flicker: window', x, y, 'exact %.3f dll-2026-10-07 %.3f dll-2026-10-09 %.3f now %.3f; whole frame %.3f %.3f %.3f %.3f' % (cr(fe).mean(), cr(fp).mean(), cr(f9).mean(), cr(fl).mean(), fe.mean(), fp.mean(), f9.mean(), fl.mean()))
heat = lambda a: gray(zoom(np.clip(cr(a) / 1.0, 0, 1), 2))        # white = 1 step of 255 per frame or more
sheet('Shimmer at rest: how much each pixel changes from frame to frame',
      f'Nothing moves. A {kw} x {kh} pixel piece where a lossy build is furthest from the exact files, enlarged 2 times.\nBlack: no change. White: 1 step of 255 per frame or more.',
      [('', [('the picture', rgb8(zoom(cr(E[7]), 2))), (f"exact files (= AMD's): {cr(fe).mean():.3f}", heat(fe)),
             (f'lossy, dll-2026-10-07: {cr(fp).mean():.3f}', heat(fp)), (f'lossy, dll-2026-10-09: {cr(f9).mean():.3f}', heat(f9)),
             (f'lossy, this release: {cr(fl).mean():.3f}', heat(fl))])],
      'cmp-flicker.png', note=f'Whole frame: exact {fe.mean():.3f}, dll-2026-10-07 {fp.mean():.3f}, dll-2026-10-09 {f9.mean():.3f}, this release {fl.mean():.3f}.')

# ---- the same still scene with grain in every input frame (random, 6 steps of 255 in standard deviation)
G = {k: fl_([load(f'grain_{k}', n) for n in range(32, 40)]) for k in ('exact', 'prev', 'r9', 'lossy')}
gpic = load('grain_exact', 39)
s = box(G['r9'] - G['lossy'], kh)[200:-200, 200:-200 - (kw - kh)]; y, x = np.unravel_index(np.argmax(s), s.shape); gy, gx = y + 200, x + 200
gc = lambda a: a[gy:gy + kh, gx:gx + kw]
print('grain: window', gx, gy, ' '.join(f'{k} {gc(G[k]).mean():.3f}' for k in G), '; whole frame', ' '.join(f'{k} {G[k].mean():.3f}' for k in G))
gheat = lambda a: gray(zoom(np.clip(gc(a) / 4.0, 0, 1), 2))        # white = 4 steps of 255 per frame or more
sheet('Grain in the picture: how much each pixel changes from frame to frame',
      f'Nothing moves, but every input frame carries random grain. A {kw} x {kh} pixel piece where this release gained most\nover dll-2026-10-09, enlarged 2 times. Black: no change. White: 4 steps of 255 per frame or more.',
      [('', [('the picture (exact files)', rgb8(zoom(gc(gpic), 2))), (f"exact files (= AMD's): {gc(G['exact']).mean():.3f}", gheat(G['exact'])),
             (f"lossy, dll-2026-10-07: {gc(G['prev']).mean():.3f}", gheat(G['prev'])), (f"lossy, dll-2026-10-09: {gc(G['r9']).mean():.3f}", gheat(G['r9'])),
             (f"lossy, this release: {gc(G['lossy']).mean():.3f}", gheat(G['lossy']))])],
      'cmp-grain.png', note=f"Whole frame: exact {G['exact'].mean():.3f}, dll-2026-10-07 {G['prev'].mean():.3f}, dll-2026-10-09 {G['r9'].mean():.3f}, this release {G['lossy'].mean():.3f}.\nAMD's shaders pass grain through on every frame; the lossy builds hold the picture steadier on the frames they skip.")
del G

# ---- moving scene, a skipped frame: thin bars and the edge a moving block has just uncovered
N = 37
lm = lambda d: srgb(np.fromfile(f'{D}/{d}/output_3840x2160_f{N:03d}.raw', dtype=np.float16).reshape(H, W, 4)[:, :, :3])
t = srgb(np.load(f'{D}/motion_truth_{N:03d}.npy').astype(np.float32)); e, pv, l = lm('motion_exact'), lm('motion_prev'), lm('motion_lossy')
de, dv, dl = np.abs(e - t).mean(2), np.abs(pv - t).mean(2), np.abs(l - t).mean(2)
rows = []
for label, (x0, y0, x1, y1) in (('Thin bars moving in front of a moving background', (2078, 1222, 2978, 1642)),
                                 ('The edge a moving block has just uncovered', (1978, 422, 2178, 1182))):
    s = box(np.maximum(dv, dl) - de, K)[y0:y1 - K, x0:x1 - K]; y, x = np.unravel_index(np.argmax(s), s.shape); y += y0; x += x0
    c = lambda a: a[y:y + K, x:x + K]
    print(label, 'window', x, y, 'error exact %.2f previous %.2f now %.2f of 255' % (c(de).mean() * 255, c(dv).mean() * 255, c(dl).mean() * 255))
    rows.append((label + '   (error against the true image, of 255)',
                 [('true image', rgb8(zoom(c(t), 4))), (f"exact files (= AMD's): {c(de).mean() * 255:.1f}", rgb8(zoom(c(e), 4))), (f'lossy, release dll-2026-10-07: {c(dv).mean() * 255:.1f}', rgb8(zoom(c(pv), 4))),
                  (f'lossy, this release: {c(dl).mean() * 255:.1f}', rgb8(zoom(c(l), 4)))]))
sheet('In motion, on a frame the lossy builds skip the model for',
      f'As if at 60 FPS (12 pixels of camera pan per frame).\n{K} x {K} pixel pieces where a lossy build is furthest off, enlarged 4 times.',
      rows, 'cmp-motion.png', note=f'Whole frame, error against the true image: exact {de.mean() * 255:.2f}, dll-2026-10-07 {dv.mean() * 255:.2f}, this release {dl.mean() * 255:.2f} of 255.')

# ---- particles without motion vectors, on a skipped frame
rows = []; KP = 72
for scene, label, z in (('part', 'Tiny, fast sparks (about 1 pixel in radius, up to 9 pixels per frame)', 5), ('big', 'Larger particles (3 to 7 pixels in radius)', 5)):
    t = srgb(np.load(f'{D}/{scene}_truth_{N:03d}.npy').astype(np.float32)); e, pv, l = lm(f'{scene}_exact'), lm(f'{scene}_prev'), lm(f'{scene}_lossy')
    de, dv, dl = np.abs(e - t).mean(2), np.abs(pv - t).mean(2), np.abs(l - t).mean(2)
    # the piece of the particles' area (motion_scene.PBOX) where this release gained most over the previous one
    s = box(dv - dl, KP)[250:1900 - KP, 250:1950 - KP]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 250; x += 250
    c = lambda a: a[y:y + KP, x:x + KP]
    print(label, 'window', x, y, 'error exact %.2f previous %.2f now %.2f of 255' % (c(de).mean() * 255, c(dv).mean() * 255, c(dl).mean() * 255))
    rows.append((label + '   (error against the true image, of 255)',
                 [('true image', rgb8(zoom(c(t), z))), (f"exact (= AMD's): {c(de).mean() * 255:.1f}", rgb8(zoom(c(e), z))), (f'lossy, dll-2026-10-07: {c(dv).mean() * 255:.1f}', rgb8(zoom(c(pv), z))),
                  (f'lossy, this release: {c(dl).mean() * 255:.1f}', rgb8(zoom(c(l), z)))]))
sheet('Particles the game draws without motion vectors, on a skipped frame',
      f'Camera still. Bright dots in the color image only, as games draw sparks and embers.\n{KP} x {KP} pixel pieces of the 4K output where this release gained most over dll-2026-10-07, enlarged 5 times.',
      rows, 'cmp-particles.png', note='Release dll-2026-10-07 kept them where they were, or dimmed them. Since dll-2026-10-09 they are taken from the\nnew frame; the seams and blockiness are where neighboring pixels were judged differently.')

# ---- the second outline beside a moving object (fixed in release dll-2026-10-07), on a skipped frame
GN = 37
gl = lambda d: srgb(np.fromfile(f'{D}/{d}/output_3840x2160_f{GN:03d}.raw', dtype=np.float16).reshape(H, W, 4)[:, :, :3])
import os
if not os.path.isdir(f'{D}/ghost_r6'):      # cmp-ghost.png documents the fix of release dll-2026-10-07 and is only redrawn when its data is there
    sys.exit(0)
gt = srgb(np.load(f'{D}/ghost_truth_{GN:03d}.npy').astype(np.float32))
ge, g6, gn = gl('ghost_exact'), gl('ghost_r6'), gl('ghost_lossy')
GAIN = 4.0          # this part of the test picture is dark: shown 4 times brighter
bx, by, rx, ry = 2300 + 6 * GN, 300, 2300 + 6 * GN, 1000          # the block's and the railing's left edges in this frame
rows = []
for label, (x0, y0, w, h), z in (("Beside the block's left edge: its image of a frame ago lands 40 to 46 pixels to the left", (bx - 96, by + 60, 128, 64), 3),
                                 ("Beside the railing: the first bars' images of a frame ago land to the left of it", (rx - 84, ry + 100, 128, 64), 3)):
    c = lambda a: a[y0:y0 + h, x0:x0 + w]
    err = lambda a: np.abs(a - gt).mean(2)
    pic = lambda a: rgb8(zoom(np.clip(c(a) * GAIN, 0, 1), z))
    print(label, 'error in the piece: exact %.2f, release 6 %.2f, now %.2f of 255' % tuple(c(err(a)).mean() * 255 for a in (ge, g6, gn)))
    rows.append((label, [('true image', pic(gt)), ("exact files (= AMD's)", pic(ge)), ('lossy, release dll-2026-10-06.6', pic(g6)), ('lossy, this release', pic(gn))]))
    rows.append(('   the same, as error against the true image (32 times amplified)',
                 [('', gray(zoom(np.zeros_like(c(err(ge))), z))), (f'{c(err(ge)).mean() * 255:.2f} of 255', gray(zoom(c(err(ge)) * 32, z))),
                  (f'{c(err(g6)).mean() * 255:.2f} of 255', gray(zoom(c(err(g6)) * 32, z))), (f'{c(err(gn)).mean() * 255:.2f} of 255', gray(zoom(c(err(gn)) * 32, z)))]))
sheet('A second outline beside a moving object, on a skipped frame',
      'Camera panning 40 pixels per frame, objects drifting 6. 128 x 64 pixel pieces of the 4K output, enlarged 3 times and shown 4 times brighter.',
      rows, 'cmp-ghost.png', note='Release dll-2026-10-06.6 shows a broken dark line (the block\'s old edge) and two faint extra bars; AMD\'s shaders and this release do not.')
