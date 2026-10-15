#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_bias_comparison.py [<dir>]: the figures of docs/research-history-bias.md: the exact DLL, this project's steady test build (unreleased) and a
# community DLL that biases FSR 4.1.1's history blend (its "bias 0.5" file).
#   bias-radar-{light,dark}.svg: the ten spokes of the upscaler comparison's chart, on its scale (the outer ring is the best of the five upscalers there)
#   bias-differ-{light,dark}.svg: ten measures where the three differ, the best of the three at the outer ring
#   With <dir>: bias-rest.png (a change map), bias-motion.png (the railing), bias-wire.png, bias-rain.png, bias-uncovered.png: the piece where the three differ most.
#       <dir> holds <scene>_<fsr4|lossy|dll>/output_3840x2160_f03{6,7}.raw (RGBA16F; lossy = the steady test, dll = the community DLL) and <scene>_truth.npy.
# Figures: test rig, 4K output from 2260x1272 (Balanced), Radeon RX 7800 XT under Proton, single runs, auto exposure off unless marked; speed: Windows
# timing kit under Proton, all three in one run.
import sys
from make_explainers import THEMES, frame, text
from make_upscaler_comparison import MEASURES, score, radar_panel, wire_close, mean

B_NAMES = ["Exact DLL (AMD's picture)", 'Steady test (this project)', 'Community bias DLL (0.5)']
# The parts of the comparison chart's spokes, in B_NAMES order. The exact DLL's picture is AMD's byte for byte, so its picture figures are FSR 4.1.1's
# on the comparison page (the same rig gave the same figures again for this page).
STILL = [44.33, 44.42, 44.26]; BACKGROUND = [49.27, 49.36, 49.29]
UNC_PAN = [34.48, 34.44, 34.56]; UNC_STILL = [32.62, 32.58, 32.51]
GHOST = [[0.85, 0.85, 0.86], [1.07, 1.06, 1.10], [1.07, 1.07, 1.08], [1.74, 1.74, 1.79], [4.01, 4.03, 4.09], [3.11, 3.36, 3.52], [1.62, 1.61, 1.64]]
BARS = [[0.94, 0.945, 0.995], [0.73, 0.725, 0.76], [0.53, 0.535, 0.555], [1.095, 1.10, 1.12]]
FOLIAGE = [[12.09, 10.72, 10.17], [12.16, 10.81, 10.25], [12.42, 11.54, 10.62]]      # error at three sway speeds
SPEED = [[0.896, 1.445, 3.143], [0.903, 1.452, 3.159], [1.057, 2.181, 4.775]]          # ms at 1080p, 1440p, 4K output, moving picture
B_MEASURES = [
    ('Accuracy', MEASURES[0][1], 'dB', 'db', mean(STILL, BACKGROUND), '{:.2f} dB'),
    ('Railing', MEASURES[1][1], 'dB', 'db', [41.82, 41.82, 41.76], '{:.2f} dB'),
    ('Uncovered', MEASURES[2][1], 'dB', 'db', mean(UNC_PAN, UNC_STILL), '{:.2f} dB'),
    ('Old image', MEASURES[3][1], 'of 255', 'down', mean(*GHOST), '{:.2f}'),
    ('Fixed bars', MEASURES[4][1], 'of 255', 'down', mean(*BARS), '{:.2f}'),
    ('Sparks', MEASURES[5][1], '%', 'up', [83, 83, 83], '{:.0f}%'),
    ('Foliage', MEASURES[6][1], 'of 255', 'down', [round(sum(v) / 3, 1) for v in FOLIAGE], '{:.1f}'),
    ('At rest', MEASURES[7][1], 'of 255', 'down', [0.037, 0.026, 0.035], '{:.3f}'),
    ('Wire, pan', MEASURES[8][1], '%', 'up', [wire_close(v) for v in (100.2, 100.6, 94.4)], '{:.1f}%'),
    ('Speed', MEASURES[9][1], 'ms', 'down', [round(sum(v) / 3, 2) for v in SPEED], '{:.2f} ms'),
]
assert [m[0] for m in B_MEASURES] == [m[0] for m in MEASURES]
BEST = {m[0]: (min if m[3] == 'down' else max)(m[4]) for m in MEASURES}      # the comparison chart's scale
B_SCORES = [score(m[3], m[4], BEST[m[0]]) for m in B_MEASURES]
assert all(v <= 1.02 for sc in B_SCORES for v in sc), 'a build is beyond the best of the five: the scale needs it'


def desc(names, M):
    return ' '.join(f'{m[1]} ({m[2]}): ' + ', '.join(f'{n} {m[5].format(m[4][k])}' for k, n in enumerate(names)) + '.' for m in M)


def bias_radar(t):
    lab = ("Three radar charts with the ten spokes of the upscaler comparison's chart and on its scale: on every spoke the best of the five upscalers compared "
           "there reaches the outer ring. Left: this project's exact DLL. Middle: the steady test, right: the community "
           "bias DLL, each with the exact DLL's shape as a dashed outline for comparison. The three shapes are nearly the same; the steady test reaches further at rest, the bias DLL "
           "is shorter on the wire and on speed. " + desc(B_NAMES, B_MEASURES))
    H = 430
    o = frame(H, lab, 'The three on the upscaler comparison\'s scale', 'The outer ring is the best of that page\'s five upscalers. Bigger is better. Dashed outline: the exact DLL.', t)
    short = [m[0] for m in B_MEASURES]
    for cx, k, ref, title in ((128, 0, None, B_NAMES[0]), (380, 1, 0, B_NAMES[1]), (632, 2, 0, B_NAMES[2])):
        o.append(text(cx, 96, title, t, 12.5, 'ink', 'middle', 600))
        radar_panel(o, t, cx, 228, 64, k, short, 8.5, ref=ref, values=True, M=B_MEASURES, SC=B_SCORES, ours=k == 1)
    o += [text(24, H - 42, 'Dashed outline: the exact DLL\'s shape. Old image: seven scenes; fixed bars: four pans; foliage: three sway speeds; speed: mean of 1080p, 1440p, 4K.', t, 10, 'muted'),
          text(24, H - 28, "Speed: Windows timing kit under Proton, the three in one run. The bias DLL runs AMD's own shaders, so it has AMD's speed.", t, 10, 'muted'),
          text(24, H - 14, 'Test rig, 4K output from 2260x1272, Radeon RX 7800 XT, single runs, auto exposure off. Neither test build has been tried in a game.', t, 10, 'muted')]
    return o


# Where the three differ: the best of the three at the outer ring (not the comparison page's scale). Full check of each build (shift/fc.sh), standard
# moving scene of the comparison rig for the railing and stripes; "AE" = the game's auto exposure flag on (the timing kit and many games use it).
D_MEASURES = [
    ('Flat at rest', 'Bright flat areas at rest: change per frame', 'of 255', 'down', [0.078, 0.008, 0.068], '{:.3f}'),
    ('Flat, AE', 'The same with auto exposure on', 'of 255', 'down', [0.186, 0.051, 0.185], '{:.3f}'),
    ('Background', 'Moving background: change per frame', 'of 255', 'down', [0.079, 0.067, 0.068], '{:.3f}'),
    ('Railing', 'Thin railing in motion: change per frame', 'of 255', 'down', [0.913, 0.906, 0.832], '{:.3f}'),
    ('Stripes', 'Fine stripes in motion: change per frame', 'of 255', 'down', [2.039, 2.012, 1.738], '{:.2f}'),
    ('Uncov. 1080p', 'Just uncovered at 1080p output, moving: accuracy', 'dB', 'db', [32.61, 32.67, 32.85], '{:.2f} dB'),
    ('Wire, pan', 'Thin wire under a slow pan: how close its brightness is to the true one', '%', 'up', [wire_close(v) for v in (100.2, 100.6, 94.4)], '{:.1f}%'),
    ('Bright rain', 'Bright rain without motion vectors: pixels more than 20 of 255 off', 'per frame', 'down', [1314, 403, 1810], '{:.0f}'),
    ('Fade', 'A region dimming 1% per frame: frames behind, bright flat areas', 'frames', 'down', [0.62, 0.90, 0.68], '{:.2f}'),
    ('Grain', 'Film grain of 10 of 255: change per frame', 'of 255', 'down', [1.724, 1.717, 1.660], '{:.2f}'),
]
D_SCORES = [score(m[3], m[4]) for m in D_MEASURES]


def bias_differ(t):
    lab = ("Three radar charts with ten spokes each, on measures where the three builds differ; on every spoke the best of the three reaches the outer ring. "
           "Left: the exact DLL (AMD's picture), middle: the steady test, right: the community bias DLL; in the middle and right charts the dashed outline is the exact DLL's shape. "
           + desc(B_NAMES, D_MEASURES))
    H = 430
    o = frame(H, lab, 'Where the three differ', 'On every spoke the best of the three reaches the outer ring. Bigger is better. Dashed outline: the exact DLL.', t)
    short = [m[0] for m in D_MEASURES]
    for cx, k, ref, title in ((128, 0, None, B_NAMES[0]), (380, 1, 0, B_NAMES[1]), (632, 2, 0, B_NAMES[2])):
        o.append(text(cx, 96, title, t, 12.5, 'ink', 'middle', 600))
        radar_panel(o, t, cx, 228, 64, k, short, 8.5, ref=ref, values=True, M=D_MEASURES, SC=D_SCORES, ours=k == 1)
    o += [text(24, H - 42, 'Flat at rest, Fade, Grain, Uncovered 1080p, Wire, Bright rain: the full check of each build. Background, Railing, Stripes: the comparison rig\'s moving scene.', t, 10, 'muted'),
          text(24, H - 28, 'AE: the game\'s auto exposure flag on (the timing kit and many games set it). Everything else with it off.', t, 10, 'muted'),
          text(24, H - 14, 'Test rig, 4K output from 2260x1272, Radeon RX 7800 XT, single runs.', t, 10, 'muted')]
    return o


if __name__ == '__main__':
    for name, fn in (('bias-radar', bias_radar), ('bias-differ', bias_differ)):
        for th, t in THEMES.items():
            open(f'{name}-{th}.svg', 'w').write('\n'.join(fn(t) + ['</svg>']) + '\n')

if __name__ == '__main__' and len(sys.argv) >= 2:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

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

    D = sys.argv[1]
    WW, HH = 3840, 2160
    BG, INK, MUTED = (26, 26, 25), (255, 255, 255), (195, 194, 183)
    KEYS = ['fsr4', 'lossy', 'dll']
    LABELS = ['Exact DLL', 'Steady test', 'Community bias 0.5']
    FULL = (200, 200, WW - 200, HH - 200)
    fr = lambda sc, k, n: srgb(np.fromfile(f'{D}/{sc}_{k}/output_3840x2160_f{n:03d}.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3])

    def sheet(name, title, sub, panels, z):
        """panels: (label, image array 0..1) in a 2 x 2 grid"""
        kh, kw = panels[0][1].shape[:2]
        pw, ph, gap, m = kw * z, kh * z, 14, 28
        top = 112 + 28 * sub.count('\n')
        im = Image.new('RGB', (2 * m + 2 * pw + gap, top + 2 * (ph + 44) + 8), BG); d = ImageDraw.Draw(im)
        d.text((m, 22), title, font=font(30), fill=INK); d.multiline_text((m, 66), sub, font=font(20), fill=MUTED, spacing=8)
        for i, (pl, a) in enumerate(panels):
            a = (np.clip(np.repeat(np.repeat(a, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)
            if a.ndim == 2:
                a = np.repeat(a[:, :, None], 3, 2)
            px, py = m + (i % 2) * (pw + gap), top + (i // 2) * (ph + 44)
            im.paste(Image.fromarray(a), (px, py)); d.text((px, py + ph + 6), pl, font=font(20), fill=INK if pl.startswith('Steady') else MUTED)
        im.save(name, optimize=True)

    def where(spread, kw, kh, area, mask=None):
        if mask is not None:
            spread = spread * mask
        x0, y0, x1, y1 = area
        s = box(spread, kh, kw)[y0:y1 - kh, x0:x1 - kw]; y, x = np.unravel_index(np.argmax(s), s.shape); y += y0; x += x0
        if mask is not None:      # center the piece on the measured part inside it
            ys, xs = np.nonzero(mask[y:y + kh, x:x + kw]); y = int(np.clip(y + ys.mean() - kh / 2, 0, HH - kh)); x = int(np.clip(x + xs.mean() - kw / 2, 0, WW - kw))
        return x, y

    def picture(sc, name, title, sub, kw, kh, z, area=FULL, mask=None, gain=1.0):
        """frame 37 beside the true image, at the piece where the steady test and the bias DLL differ most from the exact DLL"""
        tru = srgb(np.load(f'{D}/{sc}_truth.npy').astype(np.float32)); out = {k: fr(sc, k, 37) for k in KEYS}
        mk = np.load(f'{D}/{mask}.npy') if mask else None
        x, y = where(np.abs(out['lossy'] - out['fsr4']).mean(2) + np.abs(out['dll'] - out['fsr4']).mean(2), kw, kh, area, mk)
        c = lambda a: a[y:y + kh, x:x + kw]
        err = lambda a: (np.abs(c(a) - c(tru)).mean(2)[c(mk)] if mask else np.abs(c(a) - c(tru))).mean() * 255
        panels = [('true image', c(tru) * gain)] + [(f'{n}: {err(out[k]):.2f}', c(out[k]) * gain) for n, k in zip(LABELS, KEYS)]
        print(name, 'window', x, y, ' | '.join(p[0] for p in panels[1:]))
        sheet(name, title, sub, panels, z)

    def change(sc, name, title, sub, kw, kh, z, gain, area=FULL):
        """how much each pixel changes from frame 36 to 37, as a map, at the piece where the three differ most"""
        ch = {k: np.abs(fr(sc, k, 37) - fr(sc, k, 36)).mean(2) for k in KEYS}
        x, y = where(np.abs(ch['lossy'] - ch['fsr4']) + np.abs(ch['dll'] - ch['fsr4']), kw, kh, area)
        c = lambda a: a[y:y + kh, x:x + kw]
        tru = srgb(np.load(f'{D}/{sc}_truth.npy').astype(np.float32))
        panels = [('the picture (true image)', c(tru))] + [(f'{n}: {c(ch[k]).mean() * 255:.3f}', c(ch[k]) * gain) for n, k in zip(LABELS, KEYS)]
        print(name, 'window', x, y, ' | '.join(p[0] for p in panels[1:]), '| whole frame:', ' '.join(f'{k} {ch[k].mean() * 255:.3f}' for k in KEYS))
        sheet(name, title, sub, panels, z)

    E = 'Under each: mean error against the true image in this piece, of 255.'
    change('rest', 'bias-rest.png', 'At rest: what changes from one frame to the next',
           'A still picture, nothing moves. The piece where the three differ most, enlarged 2 times; the maps show each pixel\'s change\n'
           'from one frame to the next, brightened 120 times. Under each: mean change in this piece, of 255. Darker is steadier.', 300, 170, 2, 120)
    picture('motion', 'bias-motion.png', 'Moving scene: a thin railing',
            'Camera panning, the railing moving the other way. The piece of the railing where the three differ most, enlarged 4 times.\n'
            'Under each: mean error against the true image in the railing part of this piece, of 255.', 150, 84, 4, mask='motion_mask_rail')
    tw = srgb(np.load(f'{D}/wirepan_truth.npy').astype(np.float32)).mean(2)
    np.save(f'{D}/wirepan_mask.npy', tw > 0.25)      # the wire's own pixels in the true image
    picture('wirepan', 'bias-wire.png', 'A wire far thinner than a rendered pixel, camera panning slowly',
            'The piece of the wire where the three differ most, enlarged 5 times.\n'
            'Under each: mean error against the true image on the wire in this piece, of 255.', 120, 40, 5, (250, 250, 1950, 1900), mask='wirepan_mask')
    picture('rain', 'bias-rain.png', 'Bright rain drawn without motion vectors, camera still',
            'Fast streaks over a dark surface. The piece where the three differ most, enlarged 3 times. The first panel is the surface\n'
            'without rain; under the others: mean difference from it in this piece, of 255 (lower: fewer streaks and trails).', 200, 112, 3)
    picture('stillcam', 'bias-uncovered.png', 'Just uncovered, camera still',
            'The objects move, the camera does not. The piece of what they have just uncovered where the three differ most,\n'
            'enlarged 5 times. Under each: mean error against the true image in the uncovered part of this piece, of 255.', 120, 68, 5, mask='stillcam_mask')
