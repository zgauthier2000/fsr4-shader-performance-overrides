#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_upscaler_comparison.py [<dir>]: the figures of docs/upscaler-comparison.md.
#   cmp5-quality-{light,dark}.svg, cmp5-speed-{light,dark}.svg, cmp5-tradeoff-{light,dark}.svg: charts; the numbers in them are the
#       tables of that page (test rig, 4K output from 2260x1272, Radeon RX 7800 XT under Proton, single runs).
#   With <dir>: cmp5-still.png, cmp5-wires.png, cmp5-sparks.png, cmp5-foliage.png, cmp5-motion.png, cmp5-plate.png, cmp5-dots.png (frame 39 of the plate scene and of the hard-sampled foliage scene): the same piece of one frame from the
#       five upscalers beside the true image. <dir> holds <scene>_<name>/output_3840x2160_f037.raw (RGBA16F) for scene in still,
#       wires, sparks, foliage, motion and name in fsr4, lossy, fsr3, helix, xess, and <scene>_truth.npy (the true 4K image).
import sys
from make_explainers import THEMES, W, frame, line, rect, text

NAMES = ['FSR 4.1.1', 'Lossy', 'FSR 3.1', 'HelixSR', 'XeSS']
KEYS = ['fsr4', 'lossy', 'fsr3', 'helix', 'xess']
# (title, unit note, values in NAMES order, format, True if higher is better)
QUALITY = [
    ('Still picture', 'accuracy, dB', [44.33, 44.15, 39.94, 41.99, 42.14], '{:.1f}', True),
    ('Just-uncovered areas', 'accuracy in motion, dB', [34.48, 36.38, 29.22, 27.11, 30.20], '{:.1f}', True),
    ('Tiny fast sparks', 'share of brightness shown, %', [83, 75, 40, 79, 50], '{:.0f}', True),
    ('Swaying foliage', 'error, of 255', [12.1, 18.6, 16.8, 15.5, 15.5], '{:.1f}', False),
    ('Thin wire, slow pan', 'change per frame, of 255', [7.2, 16.0, 8.2, 5.6, 10.1], '{:.1f}', False),
    ('Film grain (10 of 255)', 'change per frame, of 255', [1.72, 0.98, 0.31, 0.30, 0.23], '{:.2f}', False),
]
SPEED_NAMES = ['FSR 4.1.1', "This project's exact DLL", 'Lossy', 'FSR 3.1', 'HelixSR', 'XeSS']
SPEED = [('1920x1080', [1.05, 0.89, 0.67, 0.41, 0.75, 1.42]), ('2560x1440', [2.18, 1.44, 1.10, 0.58, 1.01, 2.28]), ('3840x2160', [4.76, 3.17, 2.34, 1.16, 1.99, 4.98])]
STILL_DB = [44.33, 44.33, 44.15, 39.94, 41.99, 42.14]          # in SPEED_NAMES order: the exact DLL gives FSR 4.1.1's picture


def color(name):
    return 'lossy' if name == 'Lossy' else 'exact' if 'exact' in name else 'amd'


def quality(t):
    lab = 'Six quality measures for five upscalers, each as dots on its own scale. ' + ' '.join(
        f"{ti} ({un}; {'higher' if up else 'lower'} is better): " + ', '.join(f'{n} {f.format(v)}' for n, v in zip(NAMES, vs)) + '.' for ti, un, vs, f, up in QUALITY)
    o = frame(470, lab, 'Quality: six measures, five upscalers', 'Each panel has its own scale. The better end of every scale is on the right. Test rig, 4K output, one card.', t)
    pw, ph, x0s = 216, 178, (24, 272, 520)
    for i, (ti, un, vs, f, up) in enumerate(QUALITY):
        x0, y0 = x0s[i % 3], 78 + (i // 3) * 192
        o += [text(x0, y0 + 12, ti, t, 13, 'ink', weight=600), text(x0, y0 + 28, f"{un}; {'higher' if up else 'lower'} is better", t, 10.5, 'muted')]
        lo, hi = min(vs), max(vs); pad = (hi - lo) * 0.12 or 1
        lo, hi = lo - pad, hi + pad
        tx0, tx1 = x0 + 62, x0 + pw - 40
        pos = lambda v: tx0 + (tx1 - tx0) * ((v - lo) / (hi - lo) if up else (hi - v) / (hi - lo))
        for k, (n, v) in enumerate(zip(NAMES, vs)):
            y = y0 + 50 + k * 24
            ours = n == 'Lossy'
            o += [text(x0, y + 4, n, t, 11, 'ink' if ours else 'ink2', weight=600 if ours else None), line(tx0, y, tx1, y, t, 'grid', 1),
                  f'<circle cx="{pos(v):.1f}" cy="{y}" r="5" fill="{t[color(n)]}" stroke="{t["surface"]}" stroke-width="2"/>',
                  text(tx1 + 8, y + 4, f.format(v), t, 11, 'ink' if ours else 'ink2', weight=600 if ours else None)]
        o.append(text(tx1, y0 + 50 + 5 * 24 - 4, 'better →', t, 9.5, 'muted', 'end'))
    return o


def speed(t):
    lab = 'Graphics-card time per upscale call in milliseconds, lower is faster. ' + ' '.join(
        f'{s}: ' + ', '.join(f'{n} {v:.2f}' for n, v in zip(SPEED_NAMES, vs)) + '.' for s, vs in SPEED)
    o = frame(312, lab, 'Speed: graphics-card time for one upscale call', 'Milliseconds, lower is faster. Render size is the output size divided by 1.7. Radeon RX 7800 XT under Proton.', t)
    x0s, bw = (190, 386, 582), 120
    for k, n in enumerate(SPEED_NAMES):
        ours = n == 'Lossy' or 'exact' in n
        o.append(text(24, 112 + k * 28 + 12, n, t, 12, 'ink' if ours else 'ink2', weight=600 if ours else None))
    for j, (s, vs) in enumerate(SPEED):
        x0 = x0s[j]; mx = max(vs)
        o += [text(x0, 96, s, t, 12, 'ink', weight=600), line(x0, 104, x0, 104 + 6 * 28, t, 'grid', 1)]
        for k, (n, v) in enumerate(zip(SPEED_NAMES, vs)):
            y = 112 + k * 28; ours = n == 'Lossy' or 'exact' in n
            o += [rect(x0, y, bw * v / mx, 16, color(n), t, 3), text(x0 + bw * v / mx + 6, y + 12, f'{v:.2f}', t, 11, 'ink' if ours else 'ink2', weight=600 if ours else None)]
    o.append(text(24, 296, 'XeSS was timed by a second program over fewer calls; it runs a slower network on cards that are not Intel\'s. Bars are scaled within each size.', t, 10.5, 'muted'))
    return o


def tradeoff(t):
    lab = 'Still-picture accuracy against time per upscale call at 4K. ' + ', '.join(f'{n}: {ms:.2f} ms, {db:.2f} dB' for n, ms, db in zip(SPEED_NAMES, SPEED[2][1], STILL_DB)) + '.'
    H = 380
    o = frame(H, lab, 'Accuracy against cost at 4K', 'Up is a more accurate still picture; left is less graphics-card time. One scene and one card: a sketch, not a verdict.', t)
    px0, px1, py0, py1 = 70, 720, 84, 320
    xlo, xhi, ylo, yhi = 0.0, 5.5, 39.0, 45.0
    X = lambda v: px0 + (px1 - px0) * (v - xlo) / (xhi - xlo); Y = lambda v: py1 - (py1 - py0) * (v - ylo) / (yhi - ylo)
    for g in range(40, 46):
        o += [line(px0, Y(g), px1, Y(g), t, 'grid', 1), text(px0 - 8, Y(g) + 4, f'{g} dB', t, 10.5, 'muted', 'end')]
    for g in range(0, 6):
        o += [line(X(g), py1, X(g), py1 + 4, t, 'muted', 1), text(X(g), py1 + 18, f'{g} ms', t, 10.5, 'muted', 'middle')]
    o += [line(px0, py1, px1, py1, t, 'muted', 1), text((px0 + px1) / 2, H - 14, 'graphics-card time per upscale call, 3840x2160 output', t, 11, 'ink2', 'middle')]
    place = {'FSR 4.1.1': (10, 4, 'start'), "This project's exact DLL": (0, -12, 'middle'), 'Lossy': (0, -12, 'middle'), 'FSR 3.1': (10, 4, 'start'), 'HelixSR': (10, 4, 'start'), 'XeSS': (0, 20, 'middle')}
    for n, ms, db in zip(SPEED_NAMES, SPEED[2][1], STILL_DB):
        ours = n == 'Lossy' or 'exact' in n; dx, dy, an = place[n]
        o += [f'<circle cx="{X(ms):.1f}" cy="{Y(db):.1f}" r="6" fill="{t[color(n)]}" stroke="{t["surface"]}" stroke-width="2"/>',
              text(X(ms) + dx, Y(db) + dy, n, t, 11.5, 'ink' if ours else 'ink2', an, 600 if ours else None)]
    return o


for name, fn in (('quality', quality), ('speed', speed), ('tradeoff', tradeoff)):
    for th, t in THEMES.items():
        open(f'cmp5-{name}-{th}.svg', 'w').write('\n'.join(fn(t) + ['</svg>']) + '\n')
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
# ---- bright dots in foliage: the piece of the hard-sampled foliage scene where the lossy DLL shows the most single bright pixels inside the leaves,
# each panel with its count of them (as research/pruning/foliage_dots.py counts: more than 0.15 brighter than the median of the 3x3 surroundings, where
# the true image is dark there)
def dots_sheet(kw=200, kh=130, z=3, area=(250, 250, 1950, 1900)):
    def med3(a_):
        q = np.pad(a_, 1, mode='edge'); return np.median(np.stack([q[i:i + a_.shape[0], j:j + a_.shape[1]] for i in range(3) for j in range(3)]), 0)
    x0, y0, x1, y1 = area
    tru = srgb(np.load(f'{D}/dots_truth.npy').astype(np.float32))[y0:y1, x0:x1]
    out = {k: srgb(np.fromfile(f'{D}/dots_{k}/output_3840x2160_f039.raw', dtype=np.float16).reshape(HH, WW, 4)[y0:y1, x0:x1, :3]) for k in KEYS}
    dark = med3(tru.mean(2)) < 0.3
    dots = {k: ((v.mean(2) - med3(v.mean(2)) > 0.15) & dark).astype(np.float32) for k, v in out.items()}
    s_ = box(dots['lossy'], kh, kw); y, x = np.unravel_index(np.argmax(s_), s_.shape)
    c = lambda a_: a_[y:y + kh, x:x + kw]
    pic = lambda a_: (np.clip(np.repeat(np.repeat(c(a_), z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)
    panels = [('true image', pic(tru))] + [(f'{n}: {int(c(dots[k]).sum())}', pic(out[k])) for n, k in zip(NAMES, KEYS)]
    print('dots window', x + x0, y + y0, ' '.join(p_[0] for p_ in panels[1:]), '| whole area per thousand dark pixels:', ' '.join(f'{k} {dots[k].sum() / dark.sum() * 1000:.2f}' for k in KEYS))
    title = 'Bright dots in foliage: sky seen through leaves'
    sub = ('Dark leaves swaying in front of a bright sky, camera still, inputs sampled as a game samples them. A frame the lossy DLL skips the network on.\n'
           'The piece where the lossy DLL shows the most single bright pixels inside the leaves, enlarged 3 times. Under each: how many it shows in this piece.')
    pw, ph, gap, m = kw * z, kh * z, 14, 28
    top = 112 + 28 * sub.count('\n')
    im = Image.new('RGB', (2 * m + 3 * pw + 2 * gap, top + 2 * (ph + 44) + 8), BG); d = ImageDraw.Draw(im)
    d.text((m, 22), title, font=font(30), fill=INK); d.multiline_text((m, 66), sub, font=font(20), fill=MUTED, spacing=8)
    for i, (pl, a_) in enumerate(panels):
        px, py = m + (i % 3) * (pw + gap), top + (i // 3) * (ph + 44)
        im.paste(Image.fromarray(a_), (px, py)); d.text((px, py + ph + 6), pl, font=font(20), fill=INK if pl.startswith('Lossy') else MUTED)
    im.save('cmp5-dots.png', optimize=True)


dots_sheet()
