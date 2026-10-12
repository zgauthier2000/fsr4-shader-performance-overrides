#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_upscaler_comparison.py [<dir>]: the figures of docs/upscaler-comparison.md.
#   cmp5-radar-{light,dark}.svg (one shape per upscaler), release-radar-{light,dark}.svg (this release's lossy DLL over the previous one's, and FSR 4.1.1 under this release's, for the front page), steady-quality-{light,dark}.svg (for docs/steady-test.md): charts; the numbers in them are the
#       tables of that page (test rig, 4K output from 2260x1272, Radeon RX 7800 XT under Proton, single runs).
#   With <dir>: cmp5-still.png, cmp5-wires.png, cmp5-sparks.png, cmp5-foliage.png, cmp5-motion.png, cmp5-big.png (large particles), cmp5-plate.png, cmp5-rain.png (frame 39 of the plate scene and of the rain scene): the same piece of one frame from the
#       five upscalers beside the true image. <dir> holds <scene>_<name>/output_3840x2160_f037.raw (RGBA16F) for scene in still,
#       wires, sparks, foliage, motion and name in fsr4, lossy, fsr3, helix, xess, and <scene>_truth.npy (the true 4K image).
import sys
from make_explainers import THEMES, W, frame, line, rect, text

NAMES = ['FSR 4.1.1', 'Lossy', 'FSR 3.1', 'HelixSR', 'XeSS']
KEYS = ['fsr4', 'lossy', 'fsr3', 'helix', 'xess']
# The measures of the radar charts, in NAMES order. kind: 'db' = accuracy in dB (higher is better), 'up' = higher is better, 'down' = lower is better.
# (short label, full name, unit, kind, values, format)
MEASURES = [
    ('Still', 'Still picture: accuracy', 'dB', 'db', [44.33, 44.26, 39.94, 41.99, 42.14], '{:.2f} dB'),
    ('Background', 'Moving background: accuracy', 'dB', 'db', [49.27, 48.98, 47.95, 46.92, 47.70], '{:.2f} dB'),
    ('Railing', 'Thin railing in motion: accuracy', 'dB', 'db', [41.82, 41.34, 38.36, 40.12, 40.86], '{:.2f} dB'),
    ('Uncovered', 'Areas a moving object has just uncovered: accuracy', 'dB', 'db', [34.48, 36.45, 29.22, 27.11, 30.20], '{:.2f} dB'),
    ('Sparks', 'Tiny fast sparks: share of their brightness shown', '%', 'up', [83, 74, 40, 79, 50], '{:.0f}%'),
    # foliage: the mean of the error at the rig's usual sway speed, two thirds and half of it (camera still; for the lossy DLL, frames it skips the network for)
    ('Foliage', 'Leaves swaying without motion vectors, mean of three sway speeds: error', 'of 255', 'down', [11.0, 14.5, 16.7, 14.3, 14.3], '{:.1f}'),
    ('At rest', 'Still picture: change per frame', 'of 255', 'down', [0.037, 0.024, 0.014, 0.020, 0.084], '{:.3f}'),
    ('Wire, pan', 'Thin wire under a slow pan: change per frame', 'of 255', 'down', [7.2, 11.0, 8.2, 5.6, 10.1], '{:.1f}'),
    ('Speed', 'Time per upscale call at 3840x2160', 'ms', 'down', [4.82, 2.21, 1.15, 2.00, 4.99], '{:.2f} ms'),
]
SPEED_NAMES = ['FSR 4.1.1', "This project's exact DLL", 'Lossy', 'FSR 3.1', 'HelixSR', 'XeSS']


def score(kind, vs, best=None):
    """each value as a share of the best (of vs, or the one given): 1 = the best; for dB, the ratio of the errors"""
    if kind == 'db':
        b = max(vs) if best is None else best; return [10 ** ((v - b) / 20) for v in vs]
    if kind == 'up':
        b = max(vs) if best is None else best; return [v / b for v in vs]
    b = min(vs) if best is None else best; return [b / v for v in vs]


SCORES = [score(m[3], m[4]) for m in MEASURES]      # [measure][upscaler]


def radar_panel(o, t, cx, cy, r, k, labels, lsize=9.5, ref=0, values=False, M=None, SC=None, ours=None, was=None):
    """one upscaler's shape: the measures as spokes, the best of the set at the outer ring; the dashed outline is column ref; was: a column whose value is added in brackets where it differs"""
    import math
    MEASURES, SCORES = (M, SC) if M else (globals()['MEASURES'], globals()['SCORES'])
    n = len(MEASURES)
    ang = [math.radians(-90 + i * 360 / n) for i in range(n)]
    pt = lambda i, v: (cx + r * v * math.cos(ang[i]), cy + r * v * math.sin(ang[i]))
    ring = lambda v: ' '.join(f'{x:.1f},{y:.1f}' for x, y in (pt(i, v) for i in range(n)))
    for v in (0.25, 0.5, 0.75, 1.0):
        o.append(f'<polygon points="{ring(v)}" fill="none" stroke="{t["grid"]}" stroke-width="1"/>')
    for i in range(n):
        x, y = pt(i, 1); o.append(line(cx, cy, x, y, t, 'grid', 1))
    ours = NAMES[k] == 'Lossy' if ours is None else ours; col = t['lossy'] if ours else t['amd']
    shape = ' '.join(f'{x:.1f},{y:.1f}' for x, y in (pt(i, SCORES[i][k]) for i in range(n)))
    o.append(f'<polygon points="{shape}" fill="{col}" fill-opacity="0.35" stroke="{col}" stroke-width="2" stroke-linejoin="round"/>')
    if ref is not None and ref != k:
        rs = ' '.join(f'{x:.1f},{y:.1f}' for x, y in (pt(i, SCORES[i][ref]) for i in range(n)))
        o.append(f'<polygon points="{rs}" fill="none" stroke="{t["ink2"]}" stroke-width="1" stroke-dasharray="3 3" stroke-linejoin="round"/>')
    for i in range(n):
        x, y = pt(i, SCORES[i][k]); o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{col}" stroke="{t["surface"]}" stroke-width="1"/>')
    for i in range(n):
        c, sn = math.cos(ang[i]), math.sin(ang[i])
        x, y = cx + (r + 9) * c, cy + (r + 9) * sn
        an = 'middle' if abs(c) < 0.2 else 'start' if c > 0 else 'end'
        dy = (-2 if sn < -0.5 else 9 if sn > 0.5 else 3.5)
        if values:
            if sn < -0.5: dy -= 12
            f = MEASURES[i][5]; v = f.format(MEASURES[i][4][k])
            if was is not None and f.format(MEASURES[i][4][was]) != v: v += ' (' + f.format(MEASURES[i][4][was]).split(' ')[0] + ')'
            o += [text(x, y + dy, labels[i], t, lsize, 'ink2', an, 600), text(x, y + dy + 12.5, v, t, lsize, 'muted', an)]
        else:
            o.append(text(x, y + dy, labels[i], t, lsize, 'muted', an))


def describe(names):
    return ' '.join(f'{m[1]} ({m[2]}): ' + ', '.join(f'{NAMES[k]} {m[5].format(m[4][k])}' for k in names) + '.' for m in MEASURES)


def radar(t):
    lab = ('Five radar charts, one per upscaler, each with nine spokes; on every spoke the best of the five reaches the outer ring and the others reach in '
           'proportion to it, so a larger shape is better and a dent is a weakness. ' + describe(range(5)))
    H = 612
    o = frame(H, lab, 'The shape of each upscaler: nine measures', 'On every spoke the best of the five reaches the outer ring. Bigger is better; a dent is a weakness. Dashed: FSR 4.1.1.', t)
    cxs, cys, r = (128, 380, 632), (196, 446), 72
    short = [m[0] for m in MEASURES]
    for k, n in enumerate(NAMES):
        cx, cy = cxs[k % 3], cys[k // 3]
        o.append(text(cx, cy - r - 30, n, t, 13, 'ink', 'middle', 600))
        radar_panel(o, t, cx, cy, r, k, short)
    # the sixth place: what the spokes are
    x0, y0 = 520, 344
    o.append(text(x0, y0, 'The spokes', t, 12, 'ink', weight=600))
    key = [('Still, Background, Railing, Uncovered', 'accuracy against the true image'), ('Sparks', 'tiny fast sparks: share shown'), ('Foliage', 'swaying leaves, three speeds: accuracy'),
           ('At rest', 'steadiness of a still picture'), ('Wire, pan', 'steadiness of a thin wire in a slow pan'), ('Speed', 'time per call at 4K')]
    y = y0 + 20
    for a, b in key:
        o += [text(x0, y, a, t, 10.5, 'ink2', weight=600), text(x0, y + 13, b, t, 10.5, 'muted')]; y += 31
    o += [text(24, H - 28, 'A spoke at half length: twice the error (or the change per frame, or the time) of the best of the five; for sparks, half as much shown.', t, 10, 'muted'),
          text(24, H - 14, "Test rig, 4K output, one card, single runs. This project's exact DLL has FSR 4.1.1's shape with a longer speed spoke (3.16 ms against 4.82).", t, 10, 'muted')]
    return o


# ---- the front page: AMD's FSR 4.1.1, the previous release's lossy DLL and this release's. Same rig and scenes as above (single runs, auto exposure off).
# The foliage spoke is the mean over three sway speeds of the error on frames the lossy DLL skips the network for; the previous release's speed is from a timing-kit run of both releases (2.36 against 2.22 ms), the other two from the comparison page's timing.
R_NAMES = ['FSR 4.1.1', 'the lossy DLL of dll-2026-10-12', 'the lossy DLL of dll-2026-10-12.2']
R_MEASURES = [
    ('Still', 'Still picture: accuracy', 'dB', 'db', [44.33, 44.26, 44.26], '{:.2f} dB'),
    ('Background', 'Moving background: accuracy', 'dB', 'db', [49.27, 49.00, 48.98], '{:.2f} dB'),
    ('Uncovered', 'Areas a moving object has just uncovered: accuracy', 'dB', 'db', [34.48, 36.53, 36.45], '{:.2f} dB'),
    ('Sparks', 'Tiny fast sparks: share of their brightness shown', '%', 'up', [83, 74, 74], '{:.0f}%'),
    ('Foliage', 'Leaves swaying without motion vectors, mean of three sway speeds: error', 'of 255', 'down', [11.0, 14.6, 14.5], '{:.1f}'),
    ('Film grain', 'Still picture with grain of 6 of 255: change per frame', 'of 255', 'down', [0.785, 0.460, 0.330], '{:.3f}'),
    ('Wire, pan', 'Thin wire under a slow pan: change per frame', 'of 255', 'down', [7.2, 10.3, 11.0], '{:.1f}'),
    ('At rest', 'Still picture: change per frame', 'of 255', 'down', [0.037, 0.024, 0.024], '{:.3f}'),
    ('Speed', 'Time per upscale call at 3840x2160', 'ms', 'down', [4.82, 2.36, 2.21], '{:.2f} ms'),
]
# One scale for every radar chart: a spoke that the comparison page's chart has too is scaled by the best of its five upscalers, so a build has the same
# shape in both charts. Film grain is on this chart only: there the best of the three.
BEST = {m[0]: (min if m[3] == 'down' else max)(m[4]) for m in MEASURES}
R_SCORES = [score(m[3], m[4], BEST.get(m[0])) for m in R_MEASURES]
# The previous release is not one of the five, so its dashed outline may pass the outer ring a little (just-uncovered areas, 36.53 against this release's 36.45 dB).
assert all(v <= 1.02 for sc in R_SCORES for v in sc), 'a build of the front-page chart is well beyond the best of the five: the scale needs it'


def release_radar(t):
    lab = ("Two radar charts with nine spokes each. Left: this release's lossy DLL, with the previous release's as a dashed outline. Right: AMD's FSR 4.1.1, with this "
           "release's lossy DLL as a dashed outline. The spokes have the scale of the upscaler comparison's chart: the outer ring is the best of the five upscalers "
           "compared there (FSR 4.1.1, the lossy DLL, FSR 3.1, HelixSR, XeSS), and for film grain the best of these three. A larger shape is better. "
           + ' '.join(f'{m[1]} ({m[2]}): ' + ', '.join(f'{R_NAMES[k]} {m[5].format(m[4][k])}' for k in range(3)) + '.' for m in R_MEASURES))
    H = 460
    o = frame(H, lab, "This release's lossy DLL beside the previous one and AMD's FSR 4.1.1", 'Same scale as the upscaler comparison: the outer ring is the best of the five upscalers there. Bigger is better.', t)
    short = [m[0] for m in R_MEASURES]
    for cx, k, ref, title in ((196, 2, 1, 'Lossy DLL, this release'), (566, 0, 2, "AMD's FSR 4.1.1")):
        o.append(text(cx, 92, title, t, 13, 'ink', 'middle', 600))
        radar_panel(o, t, cx, 240, 100, k, short, 10, ref=ref, values=True, M=R_MEASURES, SC=R_SCORES, ours=k > 0, was=1 if k == 2 else None)
    o += [text(24, H - 56, 'Outer ring: FSR 4.1.1, except uncovered (this release), wire (HelixSR), at rest and speed (FSR 3.1) and film grain (previous release, best of these three).', t, 10, 'muted'),
          text(24, H - 42, "Dashed, left: the previous release (dll-2026-10-12), its figure in brackets where it differs. Dashed, right: this release's lossy DLL.", t, 10, 'muted'),
          text(24, H - 28, 'Foliage: leaves swaying without motion vectors, the mean over three sway speeds of the error on frames the lossy DLL skips the network for.', t, 10, 'muted'),
          text(24, H - 14, 'Test rig, 4K output, one card, single runs. Speed: the previous release is from another run (2.36 against 2.22 there).', t, 10, 'muted')]
    return o


# ---- docs/steady-test.md: the unreleased "steady" test build (the exact files with the postpass's dead band, no frame skip) among the others.
# FSR 4.1.1's column is also the exact files'. Same scenes and runs as above; the steady build's own figures are on that page.
S_NAMES = ['FSR 4.1.1 (= exact)', 'Steady test', 'Lossy', 'FSR 3.1', 'HelixSR', 'XeSS']
S_QUALITY = [
    ('Still picture', 'accuracy, dB', [44.33, 44.42, 44.31, 39.94, 41.99, 42.14], '{:.1f}', True),
    ('Shimmer at rest', 'change per frame, of 255', [0.037, 0.026, 0.024, 0.014, 0.020, 0.084], '{:.3f}', False),
    ('Moving background', 'accuracy, dB', [49.27, 49.37, 49.07, 47.95, 46.92, 47.70], '{:.1f}', True),
    ('Moving background', 'change per frame, of 255', [0.079, 0.067, 0.024, 0.077, 0.193, 0.085], '{:.3f}', False),
    ('Just-uncovered areas', 'accuracy in motion, dB', [34.48, 34.38, 36.48, 29.22, 27.11, 30.20], '{:.1f}', True),
    ('Tiny fast sparks', 'share of brightness shown, %', [83, 83, 75, 40, 79, 50], '{:.0f}', True),
    ('Swaying foliage', 'error, of 255', [12.1, 12.2, 18.6, 16.8, 15.5, 15.5], '{:.1f}', False),
    ('Thin wire, slow pan', 'change per frame, of 255', [7.2, 7.2, 14.6, 8.2, 5.6, 10.1], '{:.1f}', False),
    ('Film grain (10 of 255)', 'change per frame, of 255', [1.72, 1.72, 1.08, 0.31, 0.30, 0.23], '{:.2f}', False),
]


def steady_quality(t):
    lab = 'Nine quality measures for six upscalers, each as dots on its own scale; the steady test build is the one this page is about. ' + ' '.join(
        f"{ti} ({un}; {'higher' if up else 'lower'} is better): " + ', '.join(f'{n} {f.format(v)}' for n, v in zip(S_NAMES, vs)) + '.' for ti, un, vs, f, up in S_QUALITY)
    o = frame(742, lab, 'Picture quality: the steady test build among the others', 'Each panel has its own scale. The better end of every scale is on the right. Test rig, 4K output, one card.', t)
    pw, x0s = 232, (20, 264, 508)
    for i, (ti, un, vs, f, up) in enumerate(S_QUALITY):
        x0, y0 = x0s[i % 3], 78 + (i // 3) * 220
        o += [text(x0, y0 + 12, ti, t, 13, 'ink', weight=600), text(x0, y0 + 28, f"{un}; {'higher' if up else 'lower'} is better", t, 10.5, 'muted')]
        lo, hi = min(vs), max(vs); pad = (hi - lo) * 0.12 or 1
        lo, hi = lo - pad, hi + pad
        tx0, tx1 = x0 + 116, x0 + pw - 42
        pos = lambda v: tx0 + (tx1 - tx0) * ((v - lo) / (hi - lo) if up else (hi - v) / (hi - lo))
        for k, (n, v) in enumerate(zip(S_NAMES, vs)):
            y = y0 + 50 + k * 24
            ours = n == 'Steady test'; col = 'exact' if ours else 'lossy' if n == 'Lossy' else 'amd'
            o += [text(x0, y + 4, n, t, 11, 'ink' if ours else 'ink2', weight=600 if ours else None), line(tx0, y, tx1, y, t, 'grid', 1),
                  f'<circle cx="{pos(v):.1f}" cy="{y}" r="{6 if ours else 5}" fill="{t[col]}" stroke="{t["surface"]}" stroke-width="2"/>',
                  text(tx1 + 8, y + 4, f.format(v), t, 11, 'ink' if ours else 'ink2', weight=600 if ours else None)]
        o.append(text(tx1, y0 + 50 + 6 * 24 - 4, 'better →', t, 9.5, 'muted', 'end'))
    return o


for th, t in THEMES.items():
    open(f'steady-quality-{th}.svg', 'w').write('\n'.join(steady_quality(t) + ['</svg>']) + '\n')


for name, fn in (('cmp5-radar', radar), ('release-radar', release_radar)):
    for th, t in THEMES.items():
        open(f'{name}-{th}.svg', 'w').write('\n'.join(fn(t) + ['</svg>']) + '\n')
if len(sys.argv) < 2:
    sys.exit(0)

# ---- crops: the same piece of frame 37 from each upscaler, beside the true image
import numpy as np
from PIL import Image, ImageDraw, ImageFont

D = sys.argv[1]
WW, HH = 3840, 2160
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


def box(a, kh, kw):
    c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
    return (c[kh:, kw:] - c[:-kh, kw:] - c[kh:, :-kw] + c[:-kh, :-kw]) / kh / kw


def crops(scene, title, sub, kw, kh, z, area, gain=1.0, name=None, only_changed=False, frame=37):
    """the kw x kh piece inside `area` (x0, y0, x1, y1) where the five differ most from each other, enlarged z times"""
    tru = srgb(np.load(f'{D}/{scene}_truth.npy').astype(np.float32))
    out = {k: srgb(np.fromfile(f'{D}/{scene}_{k}/output_3840x2160_f{frame:03d}.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3]) for k in KEYS}
    spread = np.std(np.stack([out[k].mean(2) for k in KEYS]), 0)
    if only_changed:      # only where this scene's true image differs from the still scene's: the particles, not the picture behind them
        spread = spread * (np.abs(tru - srgb(np.load(f'{D}/still_truth.npy').astype(np.float32))).mean(2) > 0.02)
    x0, y0, x1, y1 = area
    s = box(spread, kh, kw)[y0:y1 - kh, x0:x1 - kw]; y, x = np.unravel_index(np.argmax(s), s.shape); y += y0; x += x0
    c = lambda a: a[y:y + kh, x:x + kw]
    pic = lambda a: (np.clip(np.repeat(np.repeat(c(a), z, 0), z, 1) * gain, 0, 1) * 255 + 0.5).astype(np.uint8)
    panels = [('true image', pic(tru))] + [(f'{n}: {np.abs(c(out[k]) - c(tru)).mean() * 255:.1f}', pic(out[k])) for n, k in zip(NAMES, KEYS)]
    print(scene, 'window', x, y, ' '.join(p[0] for p in panels[1:]))
    pw, ph, gap, m = kw * z, kh * z, 14, 28
    top = 112 + 28 * sub.count('\n')
    im = Image.new('RGB', (2 * m + 3 * pw + 2 * gap, top + 2 * (ph + 44) + 8), BG); d = ImageDraw.Draw(im)
    d.text((m, 22), title, font=font(30), fill=INK); d.multiline_text((m, 66), sub, font=font(20), fill=MUTED, spacing=8)
    for i, (pl, a) in enumerate(panels):
        px, py = m + (i % 3) * (pw + gap), top + (i // 3) * (ph + 44)
        im.paste(Image.fromarray(a), (px, py)); d.text((px, py + ph + 6), pl, font=font(20), fill=INK if pl.startswith('Lossy') else MUTED)
    im.save(name or f'cmp5-{scene}.png', optimize=True)


E = 'Under each: mean error against the true image in this piece, of 255.'
crops('still', 'Still picture: fine detail', f'A piece of the 4K output where the five upscalers differ most from each other, enlarged 4 times.\n{E}', 150, 90, 4, (200, 200, WW - 200, HH - 200))
crops('wires', 'A wire far thinner than a rendered pixel, camera still', f'Where the five differ most, enlarged 4 times. {E}', 150, 90, 4, (250, 250, 1950, 1900))
crops('sparks', 'Tiny fast sparks drawn without motion vectors', f'Camera still. Where the five differ most, enlarged 5 times. {E}', 120, 72, 5, (250, 250, 1950, 1900), only_changed=True)
crops('foliage', 'Leaves swaying without motion vectors, camera still', f'Where the five differ most, enlarged 4 times. {E}', 150, 90, 4, (300, 300, 1900, 1850))
crops('motion', 'Moving scene: fine stripes on a moving object', f'Camera panning. Where the five differ most, enlarged 4 times. {E}', 150, 90, 4, (1900, 250, 3300, 1500))
crops('plate', 'A still bright object over ground that moves fast', f'The ground moves down by 100 pixels per frame; the white object (top) stays where it is, at the same depth.\nThe piece just below it where the five differ most, enlarged 2 times. {E}', 240, 160, 2, (2300, 800, 3100, 1000), frame=39)
crops('big', 'Large glowing particles drawn without motion vectors', f'Camera still. Where the five differ most, enlarged 4 times. {E}', 150, 90, 4, (250, 250, 1950, 1900), only_changed=True)

# ---- rain: thin fast streaks without motion vectors over a dark surface (research/pruning/rain.py), frame 39. There is no "true image" to score against
# that would be fair to all (the streaks are in a different place every frame), so the first panel is the game's own frame and the figure under each
# panel is how many pixels of the piece stand more than 20 of 255 above the surface.
def rain_sheet(kw=200, kh=130, z=3):
    RW, RH = 2260, 1272
    px0, px1, py0, py1 = 1120 + 24, (1120 + 2720) // 2 - 24, 480 + 24, 1680 - 24      # the half of the panel with rain, clear of its edges
    pan = srgb(np.load(f'{D}/rain_panel.npy').astype(np.float32))
    out = {k: srgb(np.fromfile(f'{D}/rain_{k}/output_3840x2160_f039.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3]) for k in KEYS}
    over = {k: ((v.mean(2) - pan.mean(2)) * 255 > 20) for k, v in out.items()}
    spread = np.std(np.stack([out[k].mean(2) for k in KEYS]), 0)
    s_ = box(spread, kh, kw)[py0:py1 - kh, px0:px1 - kw]; y, x = np.unravel_index(np.argmax(s_), s_.shape); y += py0; x += px0
    c = lambda a_: a_[y:y + kh, x:x + kw]
    pic = lambda a_: (np.clip(np.repeat(np.repeat(a_, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)
    inp = srgb(np.fromfile(f'{D}/rain_input_039.raw', dtype=np.float16).reshape(RH, RW, 4)[:, :, :3])
    game = inp[(np.arange(y, y + kh) * RH // HH)][:, (np.arange(x, x + kw) * RW // WW)]
    gcount = int(((game.mean(2) - c(pan).mean(2)) * 255 > 20).sum())
    panels = [(f"the game's frame: {gcount}", pic(game))] + [(f'{n}: {int(c(over[k]).sum())}', pic(c(out[k]))) for n, k in zip(NAMES, KEYS)]
    per = {k: over[k][py0:py1, px0:px1].mean() * 1e6 for k in KEYS}
    print('rain window', x, y, ' | '.join(p_[0] for p_ in panels), '| rain area, per million:', ' '.join(f'{k} {per[k]:.0f}' for k in KEYS))
    title = 'Rain drawn without motion vectors'
    sub = ('Faint streaks one rendered pixel wide falling fast over a dark surface, camera still. The piece where the five differ most, enlarged 3 times.\n'
           'Under each: pixels in this piece more than 20 of 255 brighter than the surface.')
    pw, ph, gap, m = kw * z, kh * z, 14, 28
    top = 112 + 28 * sub.count('\n')
    im = Image.new('RGB', (2 * m + 3 * pw + 2 * gap, top + 2 * (ph + 44) + 8), BG); d = ImageDraw.Draw(im)
    d.text((m, 22), title, font=font(30), fill=INK); d.multiline_text((m, 66), sub, font=font(20), fill=MUTED, spacing=8)
    for i, (pl, a_) in enumerate(panels):
        px, py = m + (i % 3) * (pw + gap), top + (i // 3) * (ph + 44)
        im.paste(Image.fromarray(a_), (px, py)); d.text((px, py + ph + 6), pl, font=font(20), fill=INK if pl.startswith('Lossy') else MUTED)
    im.save('cmp5-rain.png', optimize=True)


rain_sheet()
