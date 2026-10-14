#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_comparison_crops.py <dir>: the comparison images of docs/exact-vs-lossy.md (cmp-still.png,
# cmp-motion.png, cmp-flicker.png, cmp-grain.png, cmp-particles.png, cmp-wires.png, cmp-plate.png, cmp-foliage-dots.png, cmp-rain.png; with "spokes": cmp-wires-pan.png,
# cmp-uncovered-still.png, cmp-ghost-still.png, cmp-bars.png, cmp-foliage.png), from test-rig output (research/pruning: fsr4img with
# gen_inputs.py / gen_motion.py, 4K Balanced, 40 frames, the last 8 kept). <dir> holds, for X = exact (the main
# files), prev (the lossy build of release dll-2026-10-07) and lossy (the current lossy build, release dll-2026-10-12):
#   still_X/                 output_3840x2160_f032..039.raw (RGBA16F), and still_truth.npy, the true 4K image
#   wires_exact/, wires_rel/ (the lossy build of release dll-2026-10-10), wires_lossy/, wires_truth_037.npy   frame 37 of the thin-wire scene
#   still_r9/, grain_X/, grain_r9/   the same frames with the lossy build of release dll-2026-10-09 (r9), and of the still scene
#       with random grain added to every input frame (standard deviation 6 of 255, sRGB)
#   motion_X/, part_X/, big_X/   frame 37 (a frame the lossy builds skip the model for) of the moving scene, of the scene
#       with tiny fast particles and of the one with large particles (camera still; the particles are in the color image
#       only, without motion vectors), and motion_truth_037.npy, part_truth_037.npy, big_truth_037.npy
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


if sys.argv[2:3] == ['spokes']:      # make_comparison_crops.py <dir> spokes : pictures of the radar chart's spokes that the sheets below do not show
    # <dir> is the data folder of docs/img/make_upscaler_comparison.py (the five-upscaler rig), which also holds <scene>_prev/: the lossy build of the
    # release before (dll-2026-10-13.2). exact = its fsr4 folders (AMD's shaders give the exact files' picture). Frame 37, a frame the lossy builds skip.
    #   wirepan = a thin wire under a slow pan; stillcam = camera still, objects moving (just-uncovered areas); ghost10 = the same scene's strip where the
    #   object's image of a frame ago would land; bars = thin bars fixed on screen, background panning 12 pixels per frame; foliage = leaves swaying
    #   without motion vectors. <scene>_mask.npy marks the part a measure looks at.
    def spoke(scene, title, sub, name, kw, kh, z, area=(200, 200, W - 200, H - 200), mask=None, shade=False, gain=1.0):
        tru = srgb(np.load(f'{D}/{scene}_truth.npy').astype(np.float32)); T = {k: load(f'{scene}_{k}', 37) for k in ('fsr4', 'prev', 'lossy')}
        diff = np.abs(T['lossy'] - T['fsr4']).mean(2); mk = np.load(f'{D}/{mask}.npy') if mask else None
        if mask: diff = diff * mk
        x0, y0, x1, y1 = area; c = np.cumsum(np.cumsum(np.pad(diff, ((1, 0), (1, 0))), 0), 1)
        sm = (c[kh:, kw:] - c[:-kh, kw:] - c[kh:, :-kw] + c[:-kh, :-kw])[y0:y1 - kh, x0:x1 - kw]; y, x = np.unravel_index(np.argmax(sm), sm.shape); y += y0; x += x0
        if mask:
            ys, xs = np.nonzero(mk[y:y + kh, x:x + kw]); y = int(np.clip(y + ys.mean() - kh / 2, 0, H - kh)); x = int(np.clip(x + xs.mean() - kw / 2, 0, W - kw))
        cp = lambda a: a[y:y + kh, x:x + kw]
        dim = np.where(cp(mk), 1.0, 0.4)[:, :, None] if (mask and shade) else 1.0
        pic = lambda a: rgb8(zoom(cp(a) * dim, z) * gain)
        err = {k: float((np.abs(cp(v) - cp(tru)).mean(2)[cp(mk)] if mask else np.abs(cp(v) - cp(tru))).mean() * 255) for k, v in T.items()}
        print(name, 'window', x, y, {k: round(v, 2) for k, v in err.items()})
        part = 'the measured part of this piece' if mask else 'this piece'
        sheet(title, sub, [('', [('true image', pic(tru)), ("exact files (= AMD's)", pic(T['fsr4'])), ('lossy, release dll-2026-10-13.2', pic(T['prev'])), ('lossy, this release', pic(T['lossy']))])],
              name, note=f"Mean error against the true image in {part}, of 255: exact %.2f, dll-2026-10-13.2 %.2f, this release %.2f." % (err['fsr4'], err['prev'], err['lossy']))
    S = 'on a frame that skips the network'
    spoke('wirepan', f'A wire far thinner than a rendered pixel while the camera pans slowly, {S}', 'The piece where the lossy build differs most from the exact files, enlarged 4 times.', 'cmp-wires-pan.png', 150, 90, 4, area=(250, 250, 1950, 1900))
    spoke('stillcam', f'Just uncovered by a moving object, camera still, {S}', 'What the object has uncovered in the last four frames is shown at full brightness, the rest dimmed.\nThe piece where the lossy build differs most from the exact files, enlarged 5 times.', 'cmp-uncovered-still.png', 120, 72, 5, mask='stillcam_mask', shade=True)
    spoke('ghost10', f'Old image beside a moving object, camera still, {S}', "Where the object's image of a frame ago would land is shown at full brightness, the rest dimmed.\nThe piece where the lossy build differs most from the exact files, enlarged 5 times.", 'cmp-ghost-still.png', 120, 72, 5, mask='ghost10_mask', shade=True)
    spoke('bars', f'Thin bars fixed on screen in front of a panning background, {S}', "The bars stay in place and the background moves by 12 pixels per frame. A piece between the bars, where their image of a frame ago\nwould land, enlarged 4 times and brightened 3 times.", 'cmp-bars.png', 150, 90, 4, mask='bars_mask', gain=3)
    spoke('foliage', f'Leaves swaying without motion vectors, camera still, {S}', 'The piece where the lossy build differs most from the exact files, enlarged 4 times.', 'cmp-foliage.png', 150, 90, 4, area=(300, 300, 1900, 1850))
    sys.exit(0)

if sys.argv[2:3] == ['plate']:      # make_comparison_crops.py <dir> plate : only cmp-plate.png (needs only the plate_* data)
    # ---- a still bright object over ground that moves fast, at the same depth, on a skipped frame (research/pruning: SCENE_VB="0 -100"
    # SCENE_VO="0 0" SCENE_BLOCKCOL=0.85 SCENE_DEPTH="0.3 0.3" SCENE_PAD=4100); plate_exact/, plate_r11/ (the lossy build of release
    # dll-2026-10-11), plate_lossy/ and plate_truth_039.npy: frame 39
    y0, x0, kh, kw = 800, 2420, 160, 240
    cp = lambda a: a[y0:y0 + kh, x0:x0 + kw]
    tru = srgb(np.load(f'{D}/plate_truth_039.npy')); T = {k: load(f'plate_{k}', 39) for k in ('exact', 'r11', 'lossy')}
    err = {k: np.abs(cp(v) - cp(tru)).mean() * 255 for k, v in T.items()}
    print('plate: error in the crop', {k: round(float(v), 2) for k, v in err.items()})
    sheet('A still bright object over ground that moves fast, on a frame that skips the network',
          f'The ground moves down by 100 pixels per frame; the white object (top) stays where it is. A {kw} x {kh} pixel piece, enlarged 2 times.',
          [('', [('true image', rgb8(zoom(cp(tru), 2))), ("exact files (= AMD's)", rgb8(zoom(cp(T['exact']), 2))),
                 ('lossy, release dll-2026-10-11', rgb8(zoom(cp(T['r11']), 2))), ('lossy, this release', rgb8(zoom(cp(T['lossy']), 2)))])],
          'cmp-plate.png', note='Mean error against the true image in this piece, of 255: exact %.2f, dll-2026-10-11 %.2f, this release %.2f.' % (err['exact'], err['r11'], err['lossy']))
    sys.exit(0)

if sys.argv[2:3] == ['rain']:      # make_comparison_crops.py <dir> rain : only cmp-rain.png (needs only the rain_* data)
    # ---- rain without motion vectors over a dark surface, camera still (research/pruning/rain.py: FF_MODE=rain FF_P=0.0005 FF_B=0.15 FF_R=12
    # RAIN_S=30), frame 39; rain_exact/, rain_r6/ (the lossy build of release dll-2026-10-11.6), rain_lossy/, rain_input_039.raw (the render-size
    # frame the game hands over, 2260x1272 RGBA16F) and rain_panel.npy (the surface without rain)
    RW, RH = 2260, 1272
    px0, px1, py0, py1 = 1120 + 24, (1120 + 2720) // 2 - 24, 480 + 24, 1680 - 24      # the half of the panel with rain (rain.py), clear of its edges
    pan = srgb(np.load(f'{D}/rain_panel.npy')); T = {k: load(f'rain_{k}', 39) for k in ('exact', 'r6', 'lossy')}
    lv = lambda a: a.mean(2) * 255
    over = {k: (lv(v) - lv(pan) > 20) for k, v in T.items()}
    per = {k: v[py0:py1, px0:px1].mean() * 1e6 for k, v in over.items()}
    kw, kh = 200, 130
    a = over['r6'][py0:py1, px0:px1].astype(np.float32); c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
    sm = c[kh:, kw:] - c[:-kh, kw:] - c[kh:, :-kw] + c[:-kh, :-kw]; y, x = np.unravel_index(np.argmax(sm), sm.shape); y += py0; x += px0
    cp = lambda a: a[y:y + kh, x:x + kw]
    cnt = {k: int(cp(v).sum()) for k, v in over.items()}
    inp = srgb(np.fromfile(f'{D}/rain_input_039.raw', dtype=np.float16).reshape(RH, RW, 4)[:, :, :3])
    iy = (np.arange(y, y + kh) * RH // H); ix = (np.arange(x, x + kw) * RW // W); game = inp[iy][:, ix]      # the same piece of the game's frame, nearest pixel
    print('rain: window', x, y, 'pixels more than 20 levels above the surface, per million, in the rain half', {k: round(float(v)) for k, v in per.items()}, 'in the piece', cnt)
    sheet('Rain drawn without motion vectors, on a frame that skips the network',
          f'Faint streaks one rendered pixel wide falling fast over a dark surface, camera still. A {kw} x {kh} pixel piece, enlarged 3 times.\nUnder each: pixels in this piece more than 20 of 255 brighter than the surface.',
          [('', [("the game's frame (what FSR is given)", rgb8(zoom(game, 3))), (f"exact files (= AMD's): {cnt['exact']}", rgb8(zoom(cp(T['exact']), 3))),
                 (f"lossy, release dll-2026-10-11.6: {cnt['r6']}", rgb8(zoom(cp(T['r6']), 3))), (f"lossy, this release: {cnt['lossy']}", rgb8(zoom(cp(T['lossy']), 3)))])],
          'cmp-rain.png', note='AMD\'s shaders blend streaks this faint and fast into the surface. Whole rain area, such pixels per million: exact %d, dll-2026-10-11.6 %d, this release %d.' % (round(per['exact']), round(per['r6']), round(per['lossy'])))
    sys.exit(0)

if sys.argv[2:3] == ['dots']:      # make_comparison_crops.py <dir> dots : only cmp-foliage-dots.png (needs only the dots_* data)
    # ---- dense dark leaves swaying in front of a bright sky, camera still, inputs sampled as a game samples them (research/pruning:
    # SCENE_FOLIAGE="50000 2 12" SCENE_POINT=1), on a skipped frame; dots_exact/, dots_r112/ (the lossy build of release dll-2026-10-11.2),
    # dots_lossy/ and dots_truth_039.npy: frame 39
    fx, fy, fw, fh = 250, 250, 1700, 1650            # the foliage area (motion_scene.FBOX at 4K)
    lum = lambda a: a[fy:fy + fh, fx:fx + fw].mean(2)
    def med3(a):
        q = np.pad(a, 1, mode='edge'); return np.median(np.stack([q[i:i + a.shape[0], j:j + a.shape[1]] for i in range(3) for j in range(3)]), 0)
    tru = srgb(np.load(f'{D}/dots_truth_039.npy')); T = {k: load(f'dots_{k}', 39) for k in ('exact', 'r112', 'lossy')}
    dark = med3(lum(tru)) < 0.3
    dots = {k: ((lum(v) - med3(lum(v)) > 0.15) & dark) for k, v in T.items()}
    per = {k: v.sum() / dark.sum() * 1000 for k, v in dots.items()}
    kw, kh = 200, 130
    c = np.cumsum(np.cumsum(np.pad(dots['r112'].astype(np.float32) - dots['exact'], ((1, 0), (1, 0))), 0), 1)
    sm = c[kh:, kw:] - c[:-kh, kw:] - c[kh:, :-kw] + c[:-kh, :-kw]; y, x = np.unravel_index(np.argmax(sm), sm.shape); y += fy; x += fx
    cp = lambda a: a[y:y + kh, x:x + kw]
    cnt = {k: int(v[y - fy:y - fy + kh, x - fx:x - fx + kw].sum()) for k, v in dots.items()}
    print('dots: window', x, y, 'per thousand dark pixels in the whole area', {k: round(float(v), 2) for k, v in per.items()}, 'dots in the piece', cnt)
    sheet('Sky seen through leaves, shown as bright dots on a frame that skips the network',
          f'Dark leaves swaying in front of a bright sky, camera still. A {kw} x {kh} pixel piece, enlarged 3 times.\nUnder each: single bright pixels inside the leaves in this piece.',
          [('', [('true image', rgb8(zoom(cp(tru), 3))), (f"exact files (= AMD's): {cnt['exact']}", rgb8(zoom(cp(T['exact']), 3))),
                 (f"lossy, release dll-2026-10-11.2: {cnt['r112']}", rgb8(zoom(cp(T['r112']), 3))), (f"lossy, this release: {cnt['lossy']}", rgb8(zoom(cp(T['lossy']), 3)))])],
          'cmp-foliage-dots.png', note='Whole foliage area, per thousand dark pixels on this frame: exact %.2f, dll-2026-10-11.2 %.2f, this release %.2f.' % (per['exact'], per['r112'], per['lossy']))
    sys.exit(0)

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
      rows, 'cmp-particles.png', note='Release dll-2026-10-07 kept them where they were, or dimmed them. Since dll-2026-10-09 they are taken from the\nnew frame, and since dll-2026-10-11 also wherever the network itself had asked for the new frame.')

# ---- a wire far thinner than a render pixel, camera still, on a skipped frame (research/pruning: SCENE_WIRES="24 0.5 0.6")
import os
import os
if os.path.isdir(f'{D}/wires_lossy'):
    wl = lambda d: srgb(np.fromfile(f'{D}/{d}/output_3840x2160_f037.raw', dtype=np.float16).reshape(H, W, 4)[:, :, :3])
    wt = srgb(np.load(f'{D}/wires_truth_037.npy').astype(np.float32)); we, wr, wn = wl('wires_exact'), wl('wires_rel'), wl('wires_lossy')
    ww, wh = 150, 60
    sm = box(np.abs(wr - we).mean(2), wh)[200:-200, 200:-200 - (ww - wh)]; y, x = np.unravel_index(np.argmax(sm), sm.shape); y += 200; x += 200
    wc = lambda a: a[y:y + wh, x:x + ww]
    lum = lambda a: wc(a).mean(2).max(0) * 255          # the brightest pixel of every column: the wire's brightness along its length
    print('wires: window', x, y, 'unevenness along the wire (std of its brightness, of 255): true %.1f exact %.1f previous %.1f now %.1f' % tuple(lum(a).std() for a in (wt, we, wr, wn)))
    sheet('A wire far thinner than a rendered pixel, on a skipped frame',
          f'Camera still. A {ww} x {wh} pixel piece of the 4K output where release dll-2026-10-10 differed most from the exact files, enlarged 4 times.\nBelow each: how uneven the wire is along its length (standard deviation of its brightness, of 255).',
          [('', [(f'true image: {lum(wt).std():.0f}', rgb8(zoom(wc(wt), 4))), (f"exact files (= AMD's): {lum(we).std():.0f}", rgb8(zoom(wc(we), 4))),
                 (f'lossy, dll-2026-10-10: {lum(wr).std():.0f}', rgb8(zoom(wc(wr), 4))), (f'lossy, this release: {lum(wn).std():.0f}', rgb8(zoom(wc(wn), 4)))])],
          'cmp-wires.png', note="A game does not smooth such a wire: each rendered pixel hits it or misses it. AMD's shaders average that into a dim line.\nThe earlier lossy build erased the wire where no sample hit it and showed every hit at full strength.")
