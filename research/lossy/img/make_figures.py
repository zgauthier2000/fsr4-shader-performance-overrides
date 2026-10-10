#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes the figures of ../README.md, each in a light and a dark version:
#   folding-*.svg          what folding does to one 3x3 set of weights (a schematic)
#   what-is-lossy-*.svg    which FSR 4 passes the main files and the lossy test build change
#   upscaler-time-*.svg    upscaler time in a game with AMD's shaders, the main files and the lossy build
#   still-accuracy-*.svg   accuracy in the still scene at eight output sizes and presets
#   motion-change-*.svg    frame-to-frame change in the moving scene, lossy build against AMD's shaders
# Data: the tables in ../README.md.
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7',
                  amd='#c3c2b7', exact='#2a78d6', small='#f0b46a', lossy='#c2570c'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835',
                 amd='#4a4a46', exact='#3987e5', small='#b9833f', lossy='#e8823a'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W = 760
CONFIGS = ['4K Balanced', '4K Performance', '1440p Quality', '1440p Balanced', '1440p Performance',
           '1080p Quality', '1080p Balanced', '1080p Performance']


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def head(h, label, title, sub, t):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{label}">',
            f'<rect width="{W}" height="{h}" rx="8" fill="{t["surface"]}"/>',
            text(24, 34, title, t, 16, 'ink', weight=600), text(24, 54, sub, t)]


def hbar(x0, y, w, h, fill):
    r = min(4, abs(w))
    x1 = x0 + w
    s = 1 if w >= 0 else -1
    return (f'<path d="M{x0:.1f},{y} H{x1 - s * r:.1f} Q{x1:.1f},{y} {x1:.1f},{y + r} V{y + h - r} '
            f'Q{x1:.1f},{y + h} {x1 - s * r:.1f},{y + h} H{x0:.1f} Z" fill="{fill}"/>')


def swatch(o, x, y, kind, label, t):
    stroke = f' stroke="{t["axis"]}" stroke-width="1"' if kind == 'amd0' else ''
    o.append(f'<rect x="{x}" y="{y - 10}" width="12" height="12" rx="2" fill="{t["surface"] if kind == "amd0" else t[kind]}"{stroke}/>')
    o.append(text(x + 18, y, label, t))
    return x + 34 + 6.3 * len(label)


# ---- folding: a schematic of the nine taps' weights for one group of four input channels
BEFORE = [[3, 14, 5], [22, 60, 9], [4, 18, 2]]          # size of each tap's weights (illustrative)
DROP = {(0, 0): (0, 1), (0, 2): (0, 1), (2, 0): (2, 1), (2, 2): (2, 1), (1, 2): (1, 1)}   # dropped tap -> the kept tap it is added to


def folding(t):
    H, C, G = 330, 54, 6
    o = head(H, 'Schematic of folding. A 3 by 3 set of weights has four large and five small entries. The five small '
             'ones are removed and each is added to the nearest entry that is kept, leaving four dot products instead of nine.',
             'What folding does', 'One output value sums 3x3 neighboring pixels, each multiplied by its weights. A schematic for one group of inputs.', t)

    def grid(x0, y0, after):
        for r in range(3):
            for c in range(3):
                x, y = x0 + c * (C + G), y0 + r * (C + G)
                v = BEFORE[r][c]
                dropped = (r, c) in DROP
                if after:
                    v += sum(BEFORE[a][b] for (a, b), tgt in DROP.items() if tgt == (r, c))
                if after and dropped:
                    o.append(f'<rect x="{x}" y="{y}" width="{C}" height="{C}" rx="4" fill="{t["surface"]}" stroke="{t["axis"]}" stroke-width="1" stroke-dasharray="3 3"/>')
                    o.append(text(x + C / 2, y + C / 2 + 4, '0', t, 13, 'muted', 'middle'))
                    continue
                kind = 'small' if (dropped and not after) else 'exact'
                side = 14 + (C - 14) * min(1.0, (v / 70) ** 0.5)       # square size shows the weights' size
                o.append(f'<rect x="{x}" y="{y}" width="{C}" height="{C}" rx="4" fill="{t["surface"]}" stroke="{t["axis"]}" stroke-width="1"/>')
                o.append(f'<rect x="{x + (C - side) / 2:.1f}" y="{y + (C - side) / 2:.1f}" width="{side:.1f}" height="{side:.1f}" rx="3" fill="{t[kind]}"/>')

    XA, XB, Y0 = 70, 470, 96
    o.append(text(XA + (3 * C + 2 * G) / 2, 84, "AMD's weights: 9 dot products", t, 13, 'ink', 'middle'))
    o.append(text(XB + (3 * C + 2 * G) / 2, 84, 'After folding: 4 dot products', t, 13, 'ink', 'middle'))
    grid(XA, Y0, False)
    grid(XB, Y0, True)
    # arrows inside the left grid: each small tap goes to its kept neighbor
    o.append(f'<defs><marker id="ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="{t["ink2"]}"/></marker></defs>')
    for (r, c), (a, b) in DROP.items():
        x1, y1 = XA + c * (C + G) + C / 2, Y0 + r * (C + G) + C / 2
        x2, y2 = XA + b * (C + G) + C / 2, Y0 + a * (C + G) + C / 2
        dx, dy = (x2 - x1), (y2 - y1)
        o.append(f'<line x1="{x1 + dx * 0.22:.1f}" y1="{y1 + dy * 0.22:.1f}" x2="{x1 + dx * 0.62:.1f}" y2="{y1 + dy * 0.62:.1f}" stroke="{t["ink2"]}" stroke-width="1.5" marker-end="url(#ah)"/>')
    xm = (XA + 3 * C + 2 * G + XB) / 2
    o.append(f'<line x1="{xm - 60}" y1="{Y0 + 87}" x2="{xm + 56}" y2="{Y0 + 87}" stroke="{t["ink2"]}" stroke-width="1.5" marker-end="url(#ah)"/>')
    o.append(text(xm, Y0 + 74, 'small weights are', t, 12, 'ink2', 'middle'))
    o.append(text(xm, Y0 + 108, 'added to a neighbor', t, 12, 'ink2', 'middle'))
    x = swatch(o, 24, 300, 'exact', 'weights that are kept', t)
    x = swatch(o, x, 300, 'small', 'small weights, removed', t)
    o.append(text(x, 300, 'Square size: how large the weights are.', t, 12, 'muted'))
    return o


# ---- which passes change
PASSES = ['Pre', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', 'Post']
MAIN = ['exact', 'exact', 'exact', 'amd0', 'exact', 'exact', 'amd0', 'exact', 'exact', 'exact', 'exact', 'exact', 'exact', 'exact']
LOSSY = ['exact', 'lossy', 'small', 'amd0', 'small', 'lossy', 'amd0', 'small', 'small', 'small', 'lossy', 'exact', 'lossy', 'exact']
GLYPH = {'amd0': '', 'exact': '=', 'small': '≈', 'lossy': '≠'}


def what(t):
    H, X0, BW, GAPX, BH = 250, 164, 36, 6, 30
    o = head(H, 'Which FSR 4 passes each build changes. Main files: twelve passes rewritten with unchanged output, passes 3 and 6 '
             'untouched. Lossy test build: passes 1, 5, 10 and 12 have weights folded and rounding changed; passes 2, 4, 7, 8 and 9 '
             'have rounding changed; the prepass, pass 11 and the postpass are the exact rewrites; passes 3 and 6 untouched.',
             'What the lossy test build changes', 'The fourteen main passes of FSR 4.1.1 in the order they run, and what happens to each one\'s output.', t)
    for i, p in enumerate(PASSES):
        o.append(text(X0 + i * (BW + GAPX) + BW / 2, 84, p, t, 11, 'muted', 'middle'))
    for r, (name, kinds) in enumerate((('Main files', MAIN), ('Lossy test build', LOSSY))):
        y = 94 + r * 58
        o.append(text(X0 - 14, y + BH / 2 + 4, name, t, 13, 'ink', 'end'))
        for i, k in enumerate(kinds):
            x = X0 + i * (BW + GAPX)
            stroke = f' stroke="{t["axis"]}" stroke-width="1"' if k == 'amd0' else ''
            o.append(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="4" fill="{t["surface"] if k == "amd0" else t[k]}"{stroke}/>')
            if GLYPH[k]:
                o.append(text(x + BW / 2, y + BH + 15, GLYPH[k], t, 13, 'ink2', 'middle'))
    x = swatch(o, 24, 226, 'amd0', "AMD's shader, untouched", t)
    x = swatch(o, x, 226, 'exact', '=  rewritten, same output', t)
    x = swatch(o, x, 226, 'small', '≈  rounding changed', t)
    swatch(o, x, 226, 'lossy', '≠  weights folded', t)
    return o


def times(t):
    rows = [("AMD's shaders", 4.16, 'amd', '97 FPS'), ('Main files', 3.05, 'exact', "109 FPS  ·  AMD's image"),
            ('Lossy test build', 2.91, 'lossy', '111 FPS  ·  image changed')]
    X0, X1, TOP, ROWH, BAR, MAXV = 160, 560, 76, 34, 16, 5.0
    H = TOP + ROWH * len(rows) + 50
    o = head(H, "Upscaler time in Shadow of the Tomb Raider's benchmark at 4K Balanced on a Radeon RX 7800 XT: AMD's shaders 4.16 ms, "
             'main files 3.05 ms with the same image, lossy test build 2.91 ms with a changed image.',
             'Upscaler time in a game', "Shadow of the Tomb Raider's benchmark, 4K Balanced, Radeon RX 7800 XT, Linux. Milliseconds per frame; lower is better.", t)
    base = TOP + ROWH * len(rows)
    for v in range(6):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="{TOP - 4}" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(text(x, base + 18, f'{v}', t, 11, 'muted', 'middle'))
    o.append(text(X1, base + 38, 'ms', t, 11, 'muted', 'end'))
    for i, (label, v, kind, note) in enumerate(rows):
        y = TOP + ROWH * i + (ROWH - BAR) / 2
        w = (X1 - X0) * v / MAXV
        o.append(text(X0 - 12, y + BAR - 4, label, t, 13, 'ink', 'end'))
        o.append(hbar(X0, y, w, BAR, t[kind]))
        o.append(text(X0 + w + 10, y + BAR - 4, f'{v:.2f} ms  ·  {note}', t))
    return o


STILL = [(44.31, 43.71), (43.90, 43.23), (43.17, 42.82), (42.86, 42.41), (42.58, 42.11), (42.61, 42.34), (42.37, 42.06), (42.04, 41.68)]


def still(t):
    X0, X1, TOP, ROWH, LO, HI = 170, 620, 78, 28, 41.0, 45.0
    H = TOP + ROWH * len(STILL) + 74
    o = head(H, 'Accuracy of the still scene against the true image, AMD then lossy, in dB: ' +
             '; '.join(f'{c} {a} and {b}' for c, (a, b) in zip(CONFIGS, STILL)) + '.',
             'Accuracy at rest: a little lower at every size', 'Still scene against the true image (PSNR, dB). Higher is more accurate. The axis does not start at zero.', t)
    base = TOP + ROWH * len(STILL)
    X = lambda v: X0 + (X1 - X0) * (v - LO) / (HI - LO)
    for v in (41, 42, 43, 44, 45):
        o.append(f'<line x1="{X(v):.1f}" y1="{TOP - 4}" x2="{X(v):.1f}" y2="{base}" stroke="{t["grid"]}" stroke-width="1"/>')
        o.append(text(X(v), base + 18, f'{v}', t, 11, 'muted', 'middle'))
    o.append(text(X1, base + 38, 'dB', t, 11, 'muted', 'end'))
    for i, (c, (a, b)) in enumerate(zip(CONFIGS, STILL)):
        y = TOP + ROWH * i + ROWH / 2
        o.append(text(X0 - 12, y + 4, c, t, 13, 'ink', 'end'))
        o.append(f'<line x1="{X(b):.1f}" y1="{y}" x2="{X(a):.1f}" y2="{y}" stroke="{t["axis"]}" stroke-width="2"/>')
        o.append(f'<circle cx="{X(a):.1f}" cy="{y}" r="5.5" fill="{t["exact"]}" stroke="{t["surface"]}" stroke-width="2"/>')
        o.append(f'<circle cx="{X(b):.1f}" cy="{y}" r="5.5" fill="{t["lossy"]}" stroke="{t["surface"]}" stroke-width="2"/>')
        o.append(text(X(a) + 12, y + 4, f'−{a - b:.2f} dB', t))
    y = base + 56
    o.append(f'<circle cx="30" cy="{y - 4}" r="5.5" fill="{t["exact"]}"/>')
    o.append(text(42, y, "AMD's shaders and the main files (identical)", t))
    o.append(f'<circle cx="330" cy="{y - 4}" r="5.5" fill="{t["lossy"]}"/>')
    o.append(text(342, y, 'Lossy test build', t))
    return o


# frame-to-frame change, (AMD, lossy), per region
MOTION = [('Background', [(0.079, 0.079), (0.092, 0.086), (0.077, 0.080), (0.091, 0.092), (0.101, 0.094), (0.083, 0.086), (0.096, 0.096), (0.103, 0.097)]),
          ('Railing bars', [(0.913, 0.948), (0.549, 0.626), (1.252, 1.217), (1.572, 1.606), (1.528, 1.588), (1.227, 1.276), (1.577, 1.573), (1.403, 1.406)]),
          ('Fine stripes', [(2.039, 1.953), (1.779, 1.847), (1.225, 1.602), (1.523, 1.784), (1.562, 2.042), (2.708, 2.204), (2.093, 2.019), (1.778, 1.879)])]


def motion(t):
    X0, PW, GAP, TOP, ROWH, BAR, R = 160, 176, 18, 100, 28, 14, 40
    H = TOP + ROWH * len(CONFIGS) + 74
    desc = '; '.join(f'{n}: ' + ', '.join(f'{c} {100 * b / a - 100:+.0f}%' for c, (a, b) in zip(CONFIGS, v)) for n, v in MOTION)
    o = head(H, 'Frame-to-frame change in the moving scene with the lossy test build, relative to AMD\'s shaders. ' + desc + '.',
             'Stability in motion: the lossy build against AMD’s shaders',
             'Frame-to-frame change of a scene point, difference from AMD’s shaders. Right of the line means more shimmer.', t)
    base = TOP + ROWH * len(CONFIGS)
    for i, c in enumerate(CONFIGS):
        o.append(text(X0 - 12, TOP + ROWH * i + ROWH / 2 + 4, c, t, 13, 'ink', 'end'))
    for p, (name, vals) in enumerate(MOTION):
        x0 = X0 + p * (PW + GAP)
        xc = x0 + PW / 2
        o.append(text(xc, TOP - 14, name, t, 13, 'ink', 'middle', 600))
        for v in (-R, -R // 2, 0, R // 2, R):
            x = xc + (PW / 2) * v / R
            o.append(f'<line x1="{x:.1f}" y1="{TOP - 4}" x2="{x:.1f}" y2="{base}" stroke="{t["axis"] if v == 0 else t["grid"]}" stroke-width="{2 if v == 0 else 1}"/>')
            if v in (-R, 0, R):
                o.append(text(x, base + 18, (f'{v:+d}%' if v else '0').replace('-', '−'), t, 11, 'muted', 'start' if v < 0 else 'end' if v > 0 else 'middle'))
        for i, (a, b) in enumerate(vals):
            d = 100 * b / a - 100
            y = TOP + ROWH * i + (ROWH - BAR) / 2
            w = (PW / 2) * d / R
            if abs(w) >= 1:
                o.append(hbar(xc, y, w, BAR, t['lossy'] if d > 0 else t['exact']))
            lab = f'{d:+.0f}%'.replace('-', '−') if round(d) else '0%'
            o.append(text(xc + w + (6 if d >= 0 else -6), y + BAR - 3, lab, t, 11, 'ink2', 'start' if d >= 0 else 'end'))
    y = base + 56
    x = swatch(o, 24, y, 'lossy', 'less steady than AMD’s shaders', t)
    swatch(o, x, y, 'exact', 'steadier than AMD’s shaders', t)
    return o


for name, t in THEMES.items():
    for fig, fn in (('folding', folding), ('what-is-lossy', what), ('upscaler-time', times), ('still-accuracy', still), ('motion-change', motion)):
        open(f'{fig}-{name}.svg', 'w').write('\n'.join(fn(t) + ['</svg>']) + '\n')
