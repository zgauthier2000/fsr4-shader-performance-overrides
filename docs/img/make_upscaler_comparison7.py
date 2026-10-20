#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_upscaler_comparison7.py [<dir>]: the figures of docs/upscaler-comparison.md since 2026-10-20 (six upscalers; the regular lossy DLL is measured in
# cmp7-data.json but left out of the page, user 2026-10-20).
#   cmp7-radar-{light,dark}.svg: one radar chart per upscaler, ten spokes; lossy2 first, its shape the dashed outline in the other panels (user 2026-10-20).
#   The numbers come from cmp7-data.json (the test rig's result files, parsed; 4K output from 2260x1272, Radeon RX 7800 XT under Proton, single runs).
#   With <dir>: one picture per picture spoke, cmp7-<scene>.png: the same piece of one frame from the six upscalers beside the true image (<dir> holds
#   <scene>_<key>/output_3840x2160_f037.raw and <scene>_truth.npy, as make_upscaler_comparison.py's pictures). Swaying leaves: cmp7-foliage.gif, frames
#   32 to 39 looping (foliage_<key>/ f032..f039 and foliage_truth_0NN.npy), as the release pages' animated sheets.
# make_upscaler_comparison.py (five upscalers) still makes the older pages' charts; its numbers are not changed by this script.
import sys, os, json
from make_explainers import THEMES, W, frame, line, rect, text
from make_upscaler_comparison import score, radar_panel

NAMES = ['FSR 4.1.1', 'Lossy2', 'FSR 4.1.2 Lite', 'FSR 3.1', 'HelixSR 2.0', 'XeSS']
KEYS = ['fsr4', 'lossy2', 'lite', 'fsr3', 'helix2', 'xess']
OURS = {'lossy2'}
DAT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cmp7-data.json')))
v = lambda name: [DAT[name][k] for k in KEYS]
mean = lambda *rows: [round(sum(c) / len(c), 2) for c in zip(*rows)]
WIRE_TRUE = 110.7
wire_close = lambda b: round(100 * (1 - abs(b - WIRE_TRUE) / WIRE_TRUE), 1)      # how close to the true brightness, in percent (too bright counts like too dim)
GHOSTS = ['ghost_12_6_m6_6', 'ghost_12_6_6_m6', 'ghost_0_0_8_0', 'ghost_0_0_6_m6', 'ghost_0_0_m6_6', 'ghost_m16_4_8_0']
BARS = ['bars_6_0', 'bars_12_0', 'bars_30_0', 'bars_12_4']
SPEED = [[DAT['speed'][k][i] for k in KEYS] for i in range(3)] if 'speed' in DAT else None      # ms at 1080p, 1440p, 4K output (moving scene)
MEASURES = [
    ('Accuracy', 'Still picture and moving background, mean: accuracy', 'dB', 'db', mean(v('still_psnr'), v('bg_psnr')), '{:.2f} dB'),
    ('Railing', 'Thin railing in motion: accuracy', 'dB', 'db', v('rail_psnr'), '{:.2f} dB'),
    ('Uncovered', 'Areas a moving object has just uncovered, mean of a panning and a still camera: accuracy', 'dB', 'db', mean(v('unc_pan'), v('unc_still')), '{:.2f} dB'),
    ('Old image', 'Old image beside a moving object, mean of seven scenes: error', 'of 255', 'down', mean(*[v(g) for g in GHOSTS], v('plate')), '{:.2f}'),
    ('Fixed bars', 'Thin bars fixed on screen in front of a panning background, mean of four pans: error where their old image lands', 'of 255', 'down', mean(*[v(b) for b in BARS]), '{:.2f}'),
    ('Sparks', 'Tiny fast sparks: share of their brightness shown', '%', 'up', v('sparks_shown'), '{:.0f}%'),
    ('Foliage', 'Leaves swaying without motion vectors, mean of three sway speeds: error', 'of 255', 'down', mean(v('fol_still'), v('fol_23'), v('fol_half')), '{:.1f}'),
    ('At rest', 'Still picture: change per frame', 'of 255', 'down', v('still_change'), '{:.3f}'),
    ('Wire, pan', 'Thin wire under a slow pan: how close its brightness is to the true one', '%', 'up', [wire_close(b) for b in v('wire_pan_bright')], '{:.1f}%'),
] + ([('Speed', 'Time per upscale call, mean of 1080p, 1440p and 4K output', 'ms', 'down', mean(*SPEED), '{:.2f} ms')] if SPEED else [])
SCORES = [score(m[3], m[4]) for m in MEASURES]


def describe():
    return ' '.join(f'{m[1]} ({m[2]}): ' + ', '.join(f'{NAMES[k]} {m[5].format(m[4][k])}' for k in range(len(NAMES))) + '.' for m in MEASURES)


def radar(t):
    n = len(MEASURES)
    lab = (f'Six radar charts, one per upscaler, each with {n} spokes; on every spoke the best of the six reaches the outer ring and the others reach in '
           'proportion to it, so a larger shape is better and a dent is a weakness. The lossy2 DLL comes first, and its shape is the dashed outline in the other five. ' + describe())
    H = 700
    o = frame(H, lab, f'The shape of each upscaler: {n} measures',
              'On every spoke the best of the six reaches the outer ring. Bigger is better; a dent is a weakness. Dashed: the lossy2 DLL.', t)
    cxs, cys, r = (128, 380, 632), (196, 446), 72
    short = [m[0] for m in MEASURES]
    first = KEYS.index('lossy2')
    for i, k in enumerate([first] + [k for k in range(len(NAMES)) if k != first]):      # lossy2 first; its outline is the dashed one in the others
        cx, cy = cxs[i % 3], cys[i // 3]
        o.append(text(cx, cy - r - 30, NAMES[k], t, 13, 'ink', 'middle', 600))
        radar_panel(o, t, cx, cy, r, k, short, ref=first, M=MEASURES, SC=SCORES, ours=KEYS[k] in OURS)
    x0, y0 = 24, 568
    o.append(text(x0, y0, 'The spokes', t, 12, 'ink', weight=600))
    key = [('Accuracy, Railing, Uncovered', 'against the true image'), ('Old image', 'left beside moving objects'), ('Fixed bars', 'old image of things fixed on screen'),
           ('Sparks', 'tiny fast sparks: share shown'), ('Foliage', 'swaying leaves, three speeds'), ('At rest', 'steadiness of a still picture'),
           ('Wire, pan', 'brightness close to the true one'), ('Speed', 'time per call, three sizes')]
    for i, (a, b) in enumerate(key):      # two columns
        x, y = x0 + (i // 2) * 182, y0 + 18 + (i % 2) * 27
        o += [text(x, y, a, t, 10, 'ink2', weight=600), text(x, y + 12, b, t, 10, 'muted')]
    o += [text(24, H - 42, 'A spoke at half length: twice the error (or the change per frame, or the time) of the best of the six; for sparks, half as much shown.', t, 10, 'muted'),
          text(24, H - 28, "Orange: this project's lossy2 DLL (release dll-2026-10-19; frame skipping, it changes the picture). FSR 4.1.2 Lite: AMD's small model,", t, 10, 'muted'),
          text(24, H - 14, "run in this project's test harness (not AMD's runtime). Test rig, 4K output, one card, single runs.", t, 10, 'muted')]
    return o


# ---- FSR 4.1.2 Lite against FSR 4.1.1, measure by measure (a diverging bar chart): how many times the error (or change per frame, or time) of
# FSR 4.1.1 Lite has, on a log scale centered on FSR 4.1.1, right = less (better), left = more (worse). dB rows: the ratio of the error amplitudes
# (10^(dB difference / 20)); "shown" rows: FSR 4.1.1's share over Lite's. Colors: a validated diverging pair (blue / red), not the project's orange.
DIV = {'light': ('#2a78d6', '#c8384f'), 'dark': ('#3987e5', '#e0566f')}


def lite_rows():
    f, l = KEYS.index('fsr4'), KEYS.index('lite')
    M = {m[0]: m for m in MEASURES}
    one = lambda name: (DAT[name]['fsr4'], DAT[name]['lite'])
    wire = lambda k: abs(DAT['wire_pan_bright'][k] - WIRE_TRUE)
    G = [('Speed', [('Time per upscale call, 4K', (SPEED[2][f], SPEED[2][l]), 'down', '{:.2f} ms')] if SPEED else []),
         ('Accuracy against the true image', [('Still picture', one('still_psnr'), 'db', '{:.2f} dB'), ('Moving background', one('bg_psnr'), 'db', '{:.2f} dB'),
                                               ('Thin railing in motion', one('rail_psnr'), 'db', '{:.2f} dB'),
                                               ('Just uncovered, camera panning', one('unc_pan'), 'db', '{:.2f} dB'),
                                               ('Just uncovered, camera still', one('unc_still'), 'db', '{:.2f} dB')]),
         ('Things that move', [('Swaying leaves, three speeds: error', (M['Foliage'][4][f], M['Foliage'][4][l]), 'down', '{:.1f}'),
                               ('Large particles: error', one('big_err'), 'down', '{:.2f}'),
                               ('Tiny fast sparks: share shown', one('sparks_shown'), 'up', '{:.0f}%'),
                               ('Old image beside moving things, 7 scenes', (M['Old image'][4][f], M['Old image'][4][l]), 'down', '{:.2f}'),
                               ('Thin bars fixed on screen, four pans', (M['Fixed bars'][4][f], M['Fixed bars'][4][l]), 'down', '{:.2f}')]),
         ('Steadiness and thin detail', [('Still picture: change per frame', one('still_change'), 'down', '{:.3f}'),
                                         ('Moving background: change per frame', one('bg_change'), 'down', '{:.3f}'),
                                         ('Thin wire, slow pan: change per frame', one('wire_pan_change'), 'down', '{:.1f}'),
                                         ('Thin wire, slow pan: brightness error', (wire('fsr4'), wire('lite')), 'down', '{:.0f} of 255')])]
    out = []
    for g, rows in G:
        rr = []
        for lab, (vf, vl), kind, fmt in rows:
            ratio = 10 ** ((vf - vl) / 20) if kind == 'db' else (vl / vf if kind == 'down' else vf / vl)      # Lite's error as a multiple of FSR 4.1.1's
            rr.append((lab, vf, vl, ratio, fmt, f'{(1 - vl / vf) * 100:.0f}% less shown' if kind == 'up' and vl < vf else None))
        out.append((g, rr))
    return out


def lite_vs_fsr4(t):
    import math
    G = lite_rows(); better, worse = DIV['light' if t is THEMES['light'] else 'dark']
    nrow = sum(len(r) for _, r in G)
    pct = lambda r: ('same' if abs(r - 1) < 0.005 else (f'{(1 - r) * 100:.0f}% less' if r < 1 else f'{(r - 1) * 100:.0f}% more') if r < 2 else f'{r:.1f}x as much')
    desc = ' '.join(f'{lab}: FSR 4.1.2 Lite {fmt.format(vl)}, FSR 4.1.1 {fmt.format(vf)} ({own or pct(r) + " error, change or time"}).' for _, rr in G for lab, vf, vl, r, fmt, own in rr)
    lab = ("A diverging bar chart comparing AMD's FSR 4.1.2 Lite with FSR 4.1.1 on the main measures of this page. The center line is FSR 4.1.1; a bar to the right "
           'means Lite has less error, change per frame or time (better), to the left more (worse), on a scale from four times less to four times more. ' + desc)
    y0, rh, gh = 132, 24, 30
    H = y0 + nrow * rh + len(G) * gh + 74
    o = frame(H, lab, "FSR 4.1.2 Lite against FSR 4.1.1, measure by measure",
              "AMD's small model has 3 network passes where FSR 4.1.1 has 12. Bars: Lite's error, change or time as a multiple of FSR 4.1.1's.", t)
    cx, half = 410, 120; xs = lambda r: cx - half / 2 * max(-2, min(2, math.log2(r)))      # 60 px per doubling, capped at 4x
    top = y0 - 8
    o += [text(cx - 8, 84, '← Lite worse: more error than FSR 4.1.1', t, 10.5, 'ink2', 'end'), text(cx + 8, 84, 'Lite better: less error →', t, 10.5, 'ink2'),
          text(640, 84, 'Lite', t, 10.5, 'ink2', 'end', 600), text(705, 84, 'FSR 4.1.1', t, 10.5, 'ink2', 'end', 600)]
    for r, s_ in ((4, '4x more'), (2, '2x more'), (1, 'same'), (0.5, '2x less'), (0.25, '4x less')):
        x = xs(r); o += [line(x, top - 4, x, H - 66, t, 'grid' if r != 1 else 'ink2', 1 if r != 1 else 1.5), text(x, top - 10, s_, t, 9.5, 'muted', 'middle')]
    y = y0
    for g, rr in G:
        y += 6; o.append(text(24, y + 8, g, t, 11.5, 'ink', weight=600)); y += gh - 6
        for labl, vf, vl, r, fmt, own in rr:
            x = xs(r); col = better if r < 1 else worse; lbl = own or pct(r)
            o.append(text(24, y + 4, labl, t, 11, 'ink2'))
            if abs(x - cx) >= 1:
                x0, w = (cx, x - cx) if x > cx else (x, cx - x)
                o.append(f'<rect x="{x0:.1f}" y="{y - 6:.1f}" width="{w:.1f}" height="12" rx="3" fill="{col}"/>')
            if abs(math.log2(r)) > 1.4:      # a long bar carries its label inside, at its outer end
                o.append(text(x + (-6 if x >= cx else 6), y + 4, lbl + (' (off the scale)' if abs(math.log2(r)) > 2.01 else ''), t, 10, 'on', 'end' if x >= cx else 'start', 600))
            else:
                o.append(text(x + (6 if x >= cx else -6), y + 4, lbl, t, 10, 'ink2', 'start' if x >= cx else 'end'))
            vt = lambda v: fmt.format(v).replace(' dB', '').replace(' ms', '').replace(' of 255', '')
            o += [text(640, y + 4, vt(vl), t, 11, 'ink', 'end', 600), text(705, y + 4, vt(vf), t, 11, 'ink2', 'end'),
                  text(712, y + 4, (fmt.format(0).split(' ', 1)[1] if ' ' in fmt.format(0) else ''), t, 9.5, 'muted')]
            y += rh
    o += [f'<rect x="24" y="{H - 52}" width="12" height="12" rx="3" fill="{better}"/>', text(42, H - 42, 'Lite better than FSR 4.1.1', t, 10.5, 'ink2'),
          f'<rect x="212" y="{H - 52}" width="12" height="12" rx="3" fill="{worse}"/>', text(230, H - 42, 'Lite worse than FSR 4.1.1', t, 10.5, 'ink2'),
          text(24, H - 24, 'Accuracy rows compare the size of the error (from the dB figures); sparks compare the share shown. Test rig, 4K output, one card, single runs.', t, 10, 'muted'),
          text(24, H - 10, "Lite run in this project's test harness, not AMD's runtime.", t, 10, 'muted')]
    return o

# ---- speed: time per upscale call at three output sizes, one panel per size on ONE shared ms scale (so the growth with size shows), rows in the
# same order in every panel (fastest to slowest at 4K); emphasis colors: this project's DLLs in their usual colors, the others gray; value at each bar.
SP_KEYS = ['fsr3', 'helix2', 'lite', 'lossy2', 'exact', 'fsr4', 'xess']
SP_NAMES = {'fsr3': 'FSR 3.1', 'helix2': 'HelixSR 2.0', 'lite': 'FSR 4.1.2 Lite', 'lossy2': 'Lossy2', 'exact': "This project's exact DLL", 'fsr4': 'FSR 4.1.1', 'xess': 'XeSS'}
SP_COL = {'lossy2': 'lossy', 'exact': 'exact'}


def speed_bars(t):
    S = DAT['speed']; keys = sorted(SP_KEYS, key=lambda k: S[k][2])
    lab = ('Time per upscale call on a Radeon RX 7800 XT, in milliseconds, at 1920x1080, 2560x1440 and 3840x2160 output, three panels on one scale. '
           + ' '.join(f'{SP_NAMES[k]}: ' + ', '.join(f'{v:.2f} ms' for v in S[k]) + '.' for k in keys))
    rh, y0 = 30, 118; H = y0 + len(keys) * rh + 56
    o = frame(H, lab, 'Time per upscale call', 'Milliseconds on a Radeon RX 7800 XT (Linux, Proton), same render ratio, one shared scale. Shorter is faster.', t)
    lx, px0, pw, step = 24, 196, 140, 186; mx = 5.0; k_ = pw / mx      # panel stride: bar room + its value text
    for j, (title, sub) in enumerate((('1920 x 1080', 'from 1130 x 636'), ('2560 x 1440', 'from 1506 x 848'), ('3840 x 2160', 'from 2260 x 1272'))):
        x0 = px0 + j * step
        o += [text(x0, 86, title, t, 12, 'ink', weight=600), text(x0, 100, sub, t, 9.5, 'muted')]
        for v in (0, 1, 2, 3, 4, 5):
            o.append(line(x0 + v * k_, y0 - 6, x0 + v * k_, y0 + len(keys) * rh - 8, t, 'grid', 1))
            o.append(text(x0 + v * k_, y0 + len(keys) * rh + 6, f'{v}', t, 9, 'muted', 'middle'))
        for i, k in enumerate(keys):
            y = y0 + i * rh; v = S[k][j]; col = t[SP_COL[k]] if k in SP_COL else t['amd']
            o += [f'<rect x="{x0:.1f}" y="{y:.1f}" width="{v * k_:.1f}" height="16" rx="3" fill="{col}"/>',
                  text(x0 + v * k_ + 5, y + 12.5, f'{v:.2f}', t, 10.5, 'ink' if k in SP_COL else 'ink2', weight=600 if k in SP_COL else None)]
    for i, k in enumerate(keys):
        o.append(text(lx, y0 + i * rh + 12.5, SP_NAMES[k], t, 11.5, 'ink' if k in SP_COL else 'ink2', weight=600 if k in SP_COL else None))
    o += [text(px0 + 2 * step + pw / 2, y0 + len(keys) * rh + 20, 'ms', t, 9, 'muted', 'middle'),
          text(24, H - 14, "Orange and blue: this project's DLLs (release dll-2026-10-19). Lossy2 is the mean over frames with and without the network. Single runs.", t, 10, 'muted')]
    return o

if __name__ == '__main__':
    for th, t in THEMES.items():
        open(f'cmp7-speed-{th}.svg', 'w').write('\n'.join(speed_bars(t) + ['</svg>']) + '\n')
        open(f'cmp7-lite-vs-fsr4-{th}.svg', 'w').write('\n'.join(lite_vs_fsr4(t) + ['</svg>']) + '\n')
        open(f'cmp7-radar-{th}.svg', 'w').write('\n'.join(radar(t) + ['</svg>']) + '\n')
if __name__ == '__main__' and len(sys.argv) >= 2:      # the pictures
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    D = sys.argv[1]
    WW, HH = 3840, 2160
    BG, INK, MUTED, ORANGE = (26, 26, 25), (255, 255, 255), (195, 194, 183), (255, 176, 102)
    COLS = 4

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

    def sheet(panels, title, sub, pw, ph, name):
        """panels: [(label, uint8 image, ours)], COLS per row"""
        gap, m = 14, 28
        top = 112 + 28 * sub.count('\n'); rows = (len(panels) + COLS - 1) // COLS
        im = Image.new('RGB', (2 * m + COLS * pw + (COLS - 1) * gap, top + rows * (ph + 44) + 8), BG); d = ImageDraw.Draw(im)
        d.text((m, 22), title, font=font(30), fill=INK); d.multiline_text((m, 66), sub, font=font(20), fill=MUTED, spacing=8)
        for i, pnl in enumerate(panels):
            if pnl is None:
                continue
            pl, a, ours = pnl
            px, py = m + (i % COLS) * (pw + gap), top + (i // COLS) * (ph + 44)
            im.paste(Image.fromarray(a), (px, py)); d.text((px, py + ph + 6), pl, font=font(20), fill=ORANGE if ours else MUTED)
        im.save(name, optimize=True)

    def crops(scene, title, sub, kw, kh, z, area, gain=1.0, name=None, only_changed=False, frame=37, mask=None, shade=False, err_amp=None):
        """the kw x kh piece inside `area` where the six differ most from each other, enlarged z times (as make_upscaler_comparison.py's crops)"""
        tru = srgb(np.load(f'{D}/{scene}_truth.npy').astype(np.float32))
        out = {k: srgb(np.fromfile(f'{D}/{scene}_{k}/output_3840x2160_f{frame:03d}.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3]) for k in KEYS}
        spread = np.std(np.stack([out[k].mean(2) for k in KEYS]), 0)
        if only_changed:
            spread = spread * (np.abs(tru - srgb(np.load(f'{D}/still_truth.npy').astype(np.float32))).mean(2) > 0.02)
        mk = np.load(f'{D}/{mask}.npy') if mask else None
        if mask:
            spread = spread * mk
        x0, y0, x1, y1 = area
        s = box(spread, kh, kw)[y0:y1 - kh, x0:x1 - kw]; y, x = np.unravel_index(np.argmax(s), s.shape); y += y0; x += x0
        if mask:
            ys, xs = np.nonzero(mk[y:y + kh, x:x + kw]); y = int(np.clip(y + ys.mean() - kh / 2, 0, HH - kh)); x = int(np.clip(x + xs.mean() - kw / 2, 0, WW - kw))
        c = lambda a: a[y:y + kh, x:x + kw]
        dim = np.where(c(mk), 1.0, 0.4)[:, :, None] if (mask and shade) else 1.0
        pic = lambda a: (np.clip(np.repeat(np.repeat(c(a) * dim, z, 0), z, 1) * gain, 0, 1) * 255 + 0.5).astype(np.uint8)
        err = lambda a: (np.abs(c(a) - c(tru)).mean(2)[c(mk)] if mask else np.abs(c(a) - c(tru))).mean() * 255
        panels = [('true image', pic(tru), False)] + [(f'{n}: {err(out[k]):.1f}', pic(out[k]), k in OURS) for n, k in zip(NAMES, KEYS)]
        print(name or scene, 'window', x, y, ' | '.join(p[0] for p in panels[1:]))
        if err_amp:      # each picture with its error, amplified, below it: rows of three upscalers, the true image first
            emap = lambda a: np.repeat((np.clip(np.repeat(np.repeat(np.abs(c(a) - c(tru)).mean(2) * (c(mk) if mask else 1) * err_amp, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)[:, :, None], 3, 2)
            lab = f'error x{err_amp}' + (', measured part' if mask else '')
            P = panels[1:]; E_ = [(lab, emap(out[k]), k in OURS) for k in KEYS]; panels = []
            for r in range(0, len(P), COLS - 1):
                panels += [panels_true if r == 0 else None for panels_true in [('true image', pic(tru), False)]] + P[r:r + COLS - 1] + [None] * (COLS - 1 - len(P[r:r + COLS - 1]))
                panels += [None] + E_[r:r + COLS - 1] + [None] * (COLS - 1 - len(E_[r:r + COLS - 1]))
        sheet(panels, title, sub, kw * z, kh * z, name or f'cmp7-{scene}.png')

    def restmap(kw=200, kh=125, z=2, gain=120):
        fr = lambda k, n: srgb(np.fromfile(f'{D}/rest_{k}/output_3840x2160_f{n:03d}.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3])
        ch = {k: np.abs(fr(k, 37) - fr(k, 36)).mean(2) for k in KEYS}
        s = box(ch['fsr4'], kh, kw)[200:HH - 200 - kh, 200:WW - 200 - kw]; y, x = np.unravel_index(np.argmax(s), s.shape); y += 200; x += 200
        c = lambda a: a[y:y + kh, x:x + kw]
        tru = srgb(np.load(f'{D}/rest_truth.npy').astype(np.float32))
        pic = lambda a: (np.clip(np.repeat(np.repeat(a, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)
        mp = lambda a: np.repeat(pic(np.clip(c(a) * gain, 0, 1))[:, :, None], 3, 2)
        panels = [('the picture (true image)', pic(c(tru)), False)] + [(f'{n}: {c(ch[k]).mean() * 255:.3f}', mp(ch[k]), k in OURS) for n, k in zip(NAMES, KEYS)]
        print('rest window', x, y, ' | '.join(p[0] for p in panels[1:]), '| whole frame:', ' '.join(f'{k} {ch[k].mean() * 255:.3f}' for k in KEYS))
        sheet(panels, 'Steadiness at rest: what changes from one frame to the next',
              'A still picture, nothing moves. The piece where FSR 4.1.1 changes most, enlarged 2 times; the maps show the change of each pixel\n'
              f'from one frame to the next, brightened {gain} times. Under each: mean change in this piece, of 255. Darker is steadier.', kw * z, kh * z, 'cmp7-rest.png')

    def rain_sheet(kw=180, kh=117, z=3):
        RW, RH = 2260, 1272
        px0, px1, py0, py1 = 1120 + 24, (1120 + 2720) // 2 - 24, 480 + 24, 1680 - 24
        pan = srgb(np.load(f'{D}/rain_panel.npy').astype(np.float32))
        out = {k: srgb(np.fromfile(f'{D}/rain_{k}/output_3840x2160_f039.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3]) for k in KEYS}
        over = {k: ((a.mean(2) - pan.mean(2)) * 255 > 20) for k, a in out.items()}
        spread = np.std(np.stack([out[k].mean(2) for k in KEYS]), 0)
        s_ = box(spread, kh, kw)[py0:py1 - kh, px0:px1 - kw]; y, x = np.unravel_index(np.argmax(s_), s_.shape); y += py0; x += px0
        c = lambda a_: a_[y:y + kh, x:x + kw]
        pic = lambda a_: (np.clip(np.repeat(np.repeat(a_, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)
        inp = srgb(np.fromfile(f'{D}/rain_input_039.raw', dtype=np.float16).reshape(RH, RW, 4)[:, :, :3])
        game = inp[(np.arange(y, y + kh) * RH // HH)][:, (np.arange(x, x + kw) * RW // WW)]
        gcount = int(((game.mean(2) - c(pan).mean(2)) * 255 > 20).sum())
        panels = [(f"the game's frame: {gcount}", pic(game), False)] + [(f'{n}: {int(c(over[k]).sum())}', pic(c(out[k])), k in OURS) for n, k in zip(NAMES, KEYS)]
        print('rain window', x, y, ' | '.join(p_[0] for p_ in panels))
        sheet(panels, 'Rain drawn without motion vectors',
              'Faint streaks one rendered pixel wide falling fast over a dark surface, camera still. The piece where the six differ most, enlarged 3 times.\n'
              'Under each: pixels in this piece more than 20 of 255 brighter than the surface.', kw * z, kh * z, 'cmp7-rain.png')

    E = 'Under each: mean error against the true image in this piece, of 255.'
    EM = 'Under each: mean error against the true image in the measured part of this piece, of 255.'
    ES = 'The measured part is shown at full brightness, the rest dimmed. Under each: mean error against the true image in that part, of 255.'
    FULL = (200, 200, WW - 200, HH - 200)
    crops('still', 'Still picture: fine detail', f'A piece of the 4K output where the six upscalers differ most from each other, enlarged 4 times.\n{E}', 130, 80, 4, FULL)
    crops('motion', 'Moving scene: a thin railing', f'Camera panning, the railing moving the other way. The piece of the railing where the six differ most, enlarged 5 times.\n{EM}\nBelow each picture: its error in the railing, amplified 16 times (brighter = more error).', 104, 64, 5, FULL, mask='motion_mask_rail', err_amp=16)
    crops('motion', 'Just uncovered, camera panning', f'What a moving object has uncovered in the last four frames. The piece of it where the six differ most, enlarged 5 times.\n{ES}', 104, 64, 5, FULL, mask='motion_mask_uncovered', name='cmp7-uncovered.png', shade=True)
    crops('stillcam', 'Just uncovered, camera still', f'The camera is still and the objects move. The piece of what they have just uncovered where the six differ most,\nenlarged 5 times. {ES}', 104, 64, 5, FULL, mask='stillcam_mask', name='cmp7-uncovered-still.png', shade=True)
    crops('ghost10', 'Old image beside a moving object', f'Camera still, the object moving. Where its image of a frame ago would land if it were left behind: the piece where the six\ndiffer most, enlarged 5 times. {ES}', 104, 64, 5, FULL, mask='ghost10_mask', name='cmp7-ghost.png', shade=True)
    crops('plate', 'A still bright object over ground that moves fast', f'The ground moves down by 100 pixels per frame; the white object (top) stays where it is, at the same depth.\nThe piece just below it where the six differ most, enlarged 2 times. {E}', 208, 140, 2, (2300, 800, 3100, 1000), frame=39)
    crops('bars', 'Thin bars fixed on screen in front of a moving background', f'The bars stay in place, the background pans by 12 pixels per frame. Between the bars, where their image of a frame ago\nwould land: the piece where the six differ most, enlarged 4 times and brightened 3 times. {EM}', 130, 80, 4, FULL, mask='bars_mask', gain=3)
    crops('sparks', 'Tiny fast sparks drawn without motion vectors', f'Camera still. Where the six differ most, enlarged 5 times. {E}', 104, 64, 5, (250, 250, 1950, 1900), only_changed=True)
    def foliage_anim(kw=130, kh=80, z=4, area=(300, 300, 1900, 1850), frames=range(32, 40), kinds='rsrsrsrs', ms=250):
        """swaying leaves (camera still) as a looping GIF, as the release pages' animated sheets: the piece where the six differ most at frame 37,
        frames 32 to 39, the true image of each frame first; one palette for all frames, no dithering (nothing flickers that the frames do not).
        <dir> holds foliage_<key>/output_3840x2160_f0NN.raw and foliage_truth_0NN.npy for those frames. kinds: r/s, whether lossy2 runs the
        network (the scene's jitter: it skips frames with negative horizontal jitter)."""
        ld = lambda k, n: srgb(np.fromfile(f'{D}/foliage_{k}/output_3840x2160_f{n:03d}.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3])
        out37 = {k: ld(k, 37) for k in KEYS}
        spread = np.std(np.stack([out37[k].mean(2) for k in KEYS]), 0)
        x0, y0, x1, y1 = area
        s_ = box(spread, kh, kw)[y0:y1 - kh, x0:x1 - kw]; y, x = np.unravel_index(np.argmax(s_), s_.shape); y += y0; x += x0
        c = lambda a: a[y:y + kh, x:x + kw]
        pic = lambda a: (np.clip(np.repeat(np.repeat(c(a), z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)
        tru = {n: srgb(np.load(f'{D}/foliage_truth_{n:03d}.npy')[:, :, :3].astype(np.float32)) for n in frames}
        outs = {n: {k: ld(k, n) for k in KEYS} for n in frames}
        err = {k: np.mean([np.abs(c(outs[n][k]) - c(tru[n])).mean() * 255 for n in frames]) for k in KEYS}
        print('foliage animation window', x, y, ' | '.join(f'{nm}: {err[k]:.1f}' for nm, k in zip(NAMES, KEYS)))
        title = 'Leaves swaying without motion vectors, camera still: frames 32 to 39, looping'
        sub = (f'The piece where the six differ most, enlarged {z} times. Under each: mean error against the true image in this piece over the eight frames, of 255.')
        pw, ph, gap, m = kw * z, kh * z, 14, 28
        top = 112 + 28 * sub.count('\n'); rows = 2
        ims = []
        for n, kind in zip(frames, kinds):
            panels = [('true image', pic(tru[n]), False)] + [(f'{nm}: {err[k]:.1f}', pic(outs[n][k]), k in OURS) for nm, k in zip(NAMES, KEYS)]
            im = Image.new('RGB', (2 * m + COLS * pw + (COLS - 1) * gap, top + rows * (ph + 44) + 40), BG); d = ImageDraw.Draw(im)
            d.text((m, 22), title, font=font(30), fill=INK); d.multiline_text((m, 66), sub, font=font(20), fill=MUTED, spacing=8)
            for i, (pl, a, ours) in enumerate(panels):
                px, py = m + (i % COLS) * (pw + gap), top + (i // COLS) * (ph + 44)
                im.paste(Image.fromarray(a), (px, py)); d.text((px, py + ph + 6), pl, font=font(20), fill=ORANGE if ours else MUTED)
            d.text((m, top + rows * (ph + 44) + 4), f'frame {n}: ' + ('lossy2 runs the network' if kind == 'r' else 'lossy2 skips the network'), font=font(20), fill=INK)
            ims.append(im)
        strip = Image.new('RGB', (ims[0].width, ims[0].height * len(ims)))
        for i, f_ in enumerate(ims):
            strip.paste(f_, (0, i * f_.height))
        pal = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)      # 255 + the labels' orange, which is too few pixels to get a color of its own
        pal.putpalette(pal.getpalette()[:255 * 3] + list(ORANGE))
        q = [f_.quantize(palette=pal, dither=Image.Dither.NONE) for f_ in ims]
        q[0].save('cmp7-foliage.gif', save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True)
        print('cmp7-foliage.gif', ims[0].size)

    def duel(examples, title, sub, name, kw=150, kh=90, z=3, pair=('lossy2', 'lite')):
        """lossy2 against FSR 4.1.2 Lite: per example, the piece where the winner's error is lowest against the loser's (box mean of
        loser error - winner error, inside the example's mask or area), as true image | lossy2 | Lite, and below them each one's error against
        the true image amplified. examples: [dict(scene, label, win, mask, area, frame, only, amp, gain, shade)]"""
        pw, ph, gap, m = kw * z, kh * z, 14, 28
        blocks = []
        for X in examples:
            scene, win, mask, area, fr, amp, gain, shade = X['scene'], X['win'], X.get('mask'), X['area'], X.get('frame', 37), X.get('amp', 16), X.get('gain', 1.0), X.get('shade', False)
            lose = pair[1] if win == pair[0] else pair[0]
            tru = srgb(np.load(f'{D}/{scene}_truth.npy').astype(np.float32))
            out = {k: srgb(np.fromfile(f'{D}/{scene}_{k}/output_3840x2160_f{fr:03d}.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3]) for k in pair}
            e = {k: np.abs(out[k] - tru).mean(2) for k in out}
            if X.get('db'):      # pick by squared error and label in dB (accuracy figures in dB weigh the largest errors most)
                e2 = {k: ((out[k] - tru) ** 2).mean(2) for k in out}; gainmap = e2[lose] - e2[win]
            else:
                gainmap = e[lose] - e[win]
            if X.get('only'):
                gainmap = gainmap * (np.abs(tru - srgb(np.load(f'{D}/still_truth.npy').astype(np.float32))).mean(2) > 0.02)
            if mask == 'bright':      # the measured part: the true image's bright thin things (a wire), widened by 3 pixels
                b_ = tru.mean(2) > 0.2; mk = b_.copy()
                for dy in range(-3, 4):
                    for dx in range(-3, 4): mk |= np.roll(np.roll(b_, dy, 0), dx, 1)
            else:
                mk = np.load(f'{D}/{mask}.npy') if mask else None
            if mask:
                gainmap = gainmap * mk
            x0, y0, x1, y1 = area
            s_ = box(gainmap, kh, kw)[y0:y1 - kh, x0:x1 - kw]; y, x = np.unravel_index(np.argmax(s_), s_.shape); y += y0; x += x0
            if mask:      # center the piece on the measured part inside it
                ys, xs = np.nonzero(mk[y:y + kh, x:x + kw]); y = int(np.clip(y + ys.mean() - kh / 2, 0, HH - kh)); x = int(np.clip(x + xs.mean() - kw / 2, 0, WW - kw))
            c = lambda a: a[y:y + kh, x:x + kw]
            dim = np.where(c(mk), 1.0, 0.35) if (mask and shade) else np.ones((kh, kw))
            pic = lambda a: (np.clip(np.repeat(np.repeat(c(a) * dim[:, :, None], z, 0), z, 1) * gain, 0, 1) * 255 + 0.5).astype(np.uint8)
            emap = lambda k: np.repeat((np.clip(np.repeat(np.repeat(c(e[k]) * (c(mk) if mask else 1) * amp, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)[:, :, None], 3, 2)
            err = lambda k: (c(e[k])[c(mk)] if mask else c(e[k])).mean() * 255
            if X.get('db'):
                fmt_e = lambda k: '%.1f dB' % (10 * np.log10(1 / (c(e2[k])[c(mk)] if mask else c(e2[k])).mean()))
            else:
                fmt_e = lambda k: f'{err(k):.1f}'
            print(name, scene, 'window', x, y, ' '.join('%s %s' % (k, fmt_e(k)) for k in pair))
            lab2 = 'error x%d' % amp + (', measured part only' if mask else '')
            nm = lambda k: NAMES[KEYS.index(k)]
            blocks.append((X['label'], [('true image', pic(tru), False)] + [(f'{nm(k)}: {fmt_e(k)}', pic(out[k]), k in OURS) for k in pair],
                           [None] + [(lab2, emap(k), k in OURS) for k in pair]))
        top = 112 + 28 * sub.count('\n'); bh = 40 + 2 * (ph + 40)
        im = Image.new('RGB', (2 * m + 3 * pw + 2 * gap, top + len(blocks) * bh + 8), BG); d = ImageDraw.Draw(im)
        d.text((m, 22), title, font=font(30), fill=INK); d.multiline_text((m, 66), sub, font=font(20), fill=MUTED, spacing=8)
        yy = top
        for lab, row1, row2 in blocks:
            d.text((m, yy), lab, font=font(22), fill=INK); yy += 34
            for row in (row1, row2):
                for i, pnl in enumerate(row):
                    if pnl is None:
                        continue
                    px = m + i * (pw + gap); im.paste(Image.fromarray(pnl[1]), (px, yy)); d.text((px, yy + ph + 6), pnl[0], font=font(20), fill=ORANGE if pnl[2] else MUTED)
                yy += ph + 40
            yy += 6
        im.save(name, optimize=True)

    U = ('Under each picture: mean error against the true image, of 255 (in the measured part, where there is one).\n'
         'Below: each one\'s error, amplified (brighter = more error).')
    duel([dict(scene='stillcam', win='lossy2', mask='stillcam_mask', area=FULL, shade=True, amp=4,
               label=f"Just uncovered, camera still: lossy2 {DAT['unc_still']['lossy2']:.2f} dB, Lite {DAT['unc_still']['lite']:.2f} dB over the whole frame"),
          dict(scene='bars', win='lossy2', mask='bars_mask', area=FULL, gain=3, amp=16,
               label=f"Thin bars fixed on screen, pan 12,0: lossy2 {DAT['bars_12_0']['lossy2']:.2f}, Lite {DAT['bars_12_0']['lite']:.2f} where their old image lands"),],
         'Where lossy2 beats FSR 4.1.2 Lite',
         'The piece of each scene where lossy2 is furthest ahead of Lite, enlarged 3 times; frame 37, a frame lossy2 skips the network on.\n'
         'Uncovered: the measured part at full brightness, the rest dimmed. Bars: brightened 3 times.\n' + U, 'cmp7-lossy2-beats-lite.png')
    duel([dict(scene='foliage', win='lite', area=(300, 300, 1900, 1850), amp=4,
               label=f"Leaves swaying without motion vectors, camera still: Lite {DAT['fol_still']['lite']:.1f}, lossy2 {DAT['fol_still']['lossy2']:.1f} over the whole scene"),
          dict(scene='big', win='lite', area=(250, 250, 1950, 1900), only=True, amp=16,
               label=f"Large glowing particles drawn without motion vectors: Lite {DAT['big_err']['lite']:.2f}, lossy2 {DAT['big_err']['lossy2']:.2f} over the whole scene")],
         'Where FSR 4.1.2 Lite beats lossy2',
         'The piece of each scene where Lite is furthest ahead of lossy2, enlarged 3 times (frame 37, a frame lossy2 skips the network on).\n' + U, 'cmp7-lite-beats-lossy2.png')
    duel([dict(scene='foliage', win='lite', area=(300, 300, 1900, 1850), amp=4,
               label=f"Leaves swaying without motion vectors, camera still: Lite {DAT['fol_still']['lite']:.1f}, FSR 4.1.1 {DAT['fol_still']['fsr4']:.1f} over the whole scene"),
          dict(scene='motion', win='lite', mask='motion_mask_uncovered', area=FULL, shade=True, amp=16, db=True,
               label=f"Just uncovered, camera panning: Lite {DAT['unc_pan']['lite']:.2f} dB, FSR 4.1.1 {DAT['unc_pan']['fsr4']:.2f} dB over the whole frame")],
         'Where FSR 4.1.2 Lite beats FSR 4.1.1',
         'The piece of each scene where Lite is furthest ahead of FSR 4.1.1, enlarged 3 times (frame 37).\n'
         'Uncovered: the measured part at full brightness, the rest dimmed; under each picture its accuracy there in dB (higher is better),\n'
         'picked by squared error, which weighs the largest errors most, as the dB figures do. Leaves: mean error, of 255.\n'
         "Below: each one's error, amplified (brighter = more error).", 'cmp7-lite-beats-fsr4.png', pair=('fsr4', 'lite'))
    duel([dict(scene='wirepan', win='fsr4', mask='bright', area=(250, 250, 1950, 1900), amp=8, gain=2,
               label=f"Thin wire, slow pan: brightness Lite {DAT['wire_pan_bright']['lite']:.0f}, FSR 4.1.1 {DAT['wire_pan_bright']['fsr4']:.0f} of 255 (true {WIRE_TRUE:.0f}) over the whole scene"),
          dict(scene='bars', win='fsr4', mask='bars_mask', area=FULL, gain=3, amp=16,
               label=f"Thin bars fixed on screen, pan 12,0: Lite {DAT['bars_12_0']['lite']:.2f}, FSR 4.1.1 {DAT['bars_12_0']['fsr4']:.2f} where their old image lands"),
          dict(scene='stillcam', win='fsr4', mask='stillcam_mask', area=FULL, shade=True, amp=16, db=True,
               label=f"Just uncovered, camera still: Lite {DAT['unc_still']['lite']:.2f} dB, FSR 4.1.1 {DAT['unc_still']['fsr4']:.2f} dB over the whole frame")],
         'Where FSR 4.1.2 Lite loses to FSR 4.1.1 the most',
         'The piece of each scene where FSR 4.1.1 is furthest ahead of Lite, enlarged 3 times (frame 37).\n'
         'Wire: brightened 2 times; mean error on the wires, of 255. Bars: brightened 3 times; mean error where their old image lands.\n'
         'Uncovered: the measured part at full brightness, the rest dimmed; accuracy there in dB (higher is better),\n'
         'picked by squared error, as the dB figures weigh it.\n'
         "Below: each one's error, amplified (brighter = more error).", 'cmp7-lite-loses-fsr4.png', pair=('fsr4', 'lite'))

    if os.path.exists(f'{D}/foliage_truth_032.npy'):
        foliage_anim()
    else:
        crops('foliage', 'Leaves swaying without motion vectors, camera still', f'Where the six differ most, enlarged 4 times. {E}', 130, 80, 4, (300, 300, 1900, 1850))
    restmap()
    crops('wirepan', 'A wire far thinner than a rendered pixel, camera panning slowly', f'Where the six differ most, enlarged 4 times. {E}', 130, 80, 4, (250, 250, 1950, 1900), name='cmp7-wires.png')
    crops('big', 'Large glowing particles drawn without motion vectors', f'Camera still. Where the six differ most, enlarged 4 times. {E}', 130, 80, 4, (250, 250, 1950, 1900), only_changed=True)
    rain_sheet()
