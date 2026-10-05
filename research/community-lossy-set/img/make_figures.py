#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes the figures of ../README.md, each in a light and a dark version:
#   what-is-replaced-*.svg   which FSR 4 passes each shader set replaces, and what that does to the output
#   model-pass-time-*.svg    time of the twelve model passes with each set
#   motion-stability-*.svg   frame-to-frame change in the moving test scene, relative to AMD's shaders
# Data: the tables in ../README.md.
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7',
                  amd='#c3c2b7', exact='#2a78d6', small='#f0b46a', lossy='#c2570c', untested='#fcfcfb'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835',
                 amd='#4a4a46', exact='#3987e5', small='#b9833f', lossy='#e8823a', untested='#1a1a19'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W = 760
# state of each pass's output: amd = AMD's shader left alone, exact = rewritten, same bytes,
# small = rounding rule changed, lossy = weights removed, untested = replaced, not measured here
PASSES = ['Pre', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', 'Post']
SETS = [('This repository', ['amd'] * 11 + ['exact', 'amd', 'exact']),
        ('Community set', ['untested', 'lossy', 'lossy', 'exact', 'lossy', 'lossy', 'exact', 'small', 'small', 'small',
                           'lossy', 'small', 'lossy', 'lossy'])]
KINDS = [('amd', "AMD's shader, untouched", ''), ('exact', 'rewritten, same output', '='),
         ('small', 'rounding changed', '≈'), ('lossy', 'weights removed', '≠'),
         ('untested', 'replaced, not measured here', '?')]
GLYPH = {k: g for k, _, g in KINDS}


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def head(h, label, title, sub, t):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{label}">',
            f'<rect width="{W}" height="{h}" rx="8" fill="{t["surface"]}"/>',
            text(24, 34, title, t, 16, 'ink', weight=600), text(24, 54, sub, t)]


def hbar(x0, y, w, h, fill):
    r = min(4, w)
    x1 = x0 + w
    return (f'<path d="M{x0},{y} H{x1 - r:.1f} Q{x1:.1f},{y} {x1:.1f},{y + r} V{y + h - r} '
            f'Q{x1:.1f},{y + h} {x1 - r:.1f},{y + h} H{x0} Z" fill="{fill}"/>')


def replaced(t):
    H, X0, BW, GAPX, BH = 272, 164, 36, 6, 30
    o = head(H, 'Which FSR 4 passes each shader set replaces. This repository: model pass 11 and the postpass, both with '
             'unchanged output. Community set: all fourteen; two with unchanged output, four with changed rounding, '
             'seven with weights removed, one not measured.',
             'What each shader set replaces', 'The fourteen main passes of FSR 4.1.1 in the order they run, and what happens to each one\'s output.', t)
    for i, p in enumerate(PASSES):
        o.append(text(X0 + i * (BW + GAPX) + BW / 2, 84, p, t, 11, 'muted', 'middle'))
    for r, (name, kinds) in enumerate(SETS):
        y = 94 + r * 58
        o.append(text(X0 - 14, y + BH / 2 + 4, name, t, 13, 'ink', 'end'))
        for i, k in enumerate(kinds):
            x = X0 + i * (BW + GAPX)
            stroke = f' stroke="{t["axis"]}" stroke-width="1"' + (' stroke-dasharray="3 3"' if k == 'untested' else '') if k in ('amd', 'untested') else ''
            fill = t['surface'] if k == 'amd' else t[k]
            o.append(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="4" fill="{fill}"{stroke}/>')
            if GLYPH[k]:
                o.append(text(x + BW / 2, y + BH + 15, GLYPH[k], t, 13, 'ink2', 'middle'))
    x, y = 24, 226
    for n, (k, label, g) in enumerate(KINDS):
        if n == 3:
            x, y = 24, y + 22
        stroke = f' stroke="{t["axis"]}" stroke-width="1"' + (' stroke-dasharray="3 3"' if k == 'untested' else '') if k in ('amd', 'untested') else ''
        o.append(f'<rect x="{x}" y="{y - 10}" width="12" height="12" rx="2" fill="{t["surface"] if k == "amd" else t[k]}"{stroke}/>')
        s = (g + '  ' if g else '') + label
        o.append(text(x + 18, y, s, t))
        x += 30 + 6.3 * len(s)
    return o


def times(t):
    rows = [("AMD's shaders", 2.42, 'amd', 'reference'),
            ('This repository', 2.04, 'exact', 'same output'),
            ('Community set', 2.03, 'lossy', 'output changed'),
            ('Community set + this repository’s pass 11', 1.70, 'lossy', 'output changed')]
    X0, X1, TOP, ROWH, BAR, MAXV = 290, 650, 76, 34, 16, 2.5
    H = TOP + ROWH * len(rows) + 50
    o = head(H, 'Time of the twelve model passes on a Radeon RX 7800 XT: AMD 2.42 ms, this repository 2.04 ms, '
             'community set 2.03 ms, community set with this repository\'s pass 11 1.70 ms.',
             'Time of the twelve model passes', 'Milliseconds per frame at 4K, Radeon RX 7800 XT. Lower is better.', t)
    base = TOP + ROWH * len(rows)
    for v in (0, 0.5, 1.0, 1.5, 2.0, 2.5):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="{TOP - 4}" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(text(x, base + 18, f'{v:g}', t, 11, 'muted', 'middle'))
    o.append(text(X1, base + 38, 'ms', t, 11, 'muted', 'end'))
    for i, (label, v, kind, note) in enumerate(rows):
        y = TOP + ROWH * i + (ROWH - BAR) / 2
        w = (X1 - X0) * v / MAXV
        o.append(text(X0 - 12, y + BAR - 4, label, t, 13, 'ink', 'end'))
        o.append(hbar(X0, y, w, BAR, t[kind]))
        o.append(text(X0 + w + 8, y + BAR - 4, f'{v:.2f}  ·  {note}', t))
    return o


def stability(t):
    rows = [('Background', 0.079, 0.138), ('Railing bars', 0.913, 1.140), ('Fine stripes', 2.04, 2.47)]
    X0, X1, TOP, ROWH, BAR, MAXV = 150, 600, 76, 40, 16, 200
    H = TOP + ROWH * len(rows) + 68
    o = head(H, 'Frame-to-frame change in the moving test scene with the community set, relative to AMD\'s shaders: '
             'background 175%, railing bars 125%, fine stripes 121%. This repository equals AMD at 100%.',
             'Stability in motion: the community set against AMD’s shaders',
             'Frame-to-frame change of a scene point, AMD’s shaders = 100%. Higher means more shimmer.', t)
    base = TOP + ROWH * len(rows)
    for v in (0, 50, 100, 150, 200):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="{TOP - 4}" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(text(x, base + 18, f'{v}%', t, 11, 'muted', 'middle'))
    xr = X0 + (X1 - X0) * 100 / MAXV
    o.append(f'<line x1="{xr:.1f}" y1="{TOP - 8}" x2="{xr:.1f}" y2="{base + 4}" stroke="{t["exact"]}" stroke-width="2"/>')
    for i, (label, a, b) in enumerate(rows):
        y = TOP + ROWH * i + (ROWH - BAR) / 2
        w = (X1 - X0) * (100 * b / a) / MAXV
        o.append(text(X0 - 12, y + BAR - 4, label, t, 13, 'ink', 'end'))
        o.append(hbar(X0, y, w, BAR, t['lossy']))
        o.append(f'<line x1="{xr:.1f}" y1="{y - 2}" x2="{xr:.1f}" y2="{y + BAR + 2}" stroke="{t["exact"]}" stroke-width="2"/>')
        o.append(text(X0 + w + 8, y + BAR - 4, f'+{100 * b / a - 100:.0f}%  ({a:g} → {b:g})', t))
    y = base + 48
    o.append(f'<rect x="24" y="{y - 10}" width="12" height="12" rx="2" fill="{t["lossy"]}"/>')
    o.append(text(42, y, 'Community set', t))
    o.append(f'<line x1="150" y1="{y - 11}" x2="150" y2="{y + 3}" stroke="{t["exact"]}" stroke-width="2"/>')
    o.append(text(160, y, 'AMD’s shaders and this repository (identical frames)', t))
    return o


for name, t in THEMES.items():
    for fig, fn in (('what-is-replaced', replaced), ('model-pass-time', times), ('motion-stability', stability)):
        open(f'{fig}-{name}.svg', 'w').write('\n'.join(fn(t) + ['</svg>']) + '\n')
