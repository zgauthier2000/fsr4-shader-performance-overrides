#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes rel-lite-wires-light.svg and rel-lite-wires-dark.svg: shimmer of thin wires while the camera pans (the full check's "wires pan
# change" row: mean change per frame, lower is steadier; a scene type not used in training), for AMD's FSR 4.1.2 Lite, this project's
# 4.1.2l-lossy, AMD's FSR 4.1.1 and lossy2, with the game's auto exposure off and on. Linux test rig (Proton, RX 7800 XT), 4K Balanced,
# synthetic scene, one run each. Lite and FSR 4.1.1 measured in this project's local test harness.
ROWS = [  # build, auto exposure off, on, highlighted
    ('FSR 4.1.2 Lite (AMD)', 9.75, 7.81, False), ('4.1.2l-lossy (new)', 5.88, 3.83, True),
    ('FSR 4.1.1 (AMD)', 7.16, 6.79, False), ('lossy (former lossy2)', 4.56, 4.36, False),
]
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7', off='#2a78d6', on='#d9711c'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835', off='#3987e5', on='#e8843a'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W, X0, X1, MAXV, ROW, BAR, GAP = 760, 200, 640, 10, 44, 15, 2


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def bar(y, v, fill):
    w = (X1 - X0) * v / MAXV; r = min(4, w)
    return (f'<path d="M{X0},{y} H{X0 + w - r:.1f} Q{X0 + w:.1f},{y} {X0 + w:.1f},{y + r} V{y + BAR - r} '
            f'Q{X0 + w:.1f},{y + BAR} {X0 + w - r:.1f},{y + BAR} H{X0} Z" fill="{fill}"/>'), X0 + w


for name, t in THEMES.items():
    H = 108 + ROW * len(ROWS) + 76
    label = ('Shimmer of thin wires while the camera pans, mean change per frame, lower is steadier, auto exposure off then on: '
             + '; '.join(f'{b} {a:.2f} and {o:.2f}' for b, a, o, _ in ROWS) + '.')
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, 'Thin wires in a camera pan: 4.1.2l-lossy shimmers 40 to 50% less than Lite', t, 16, 'ink', weight=600),
         text(24, 54, 'Mean change per frame on thin wires while the camera pans; lower is steadier. Test rig, 4K Balanced.', t)]
    ly = 76
    for i, (lab, key) in enumerate((('game auto exposure off', 'off'), ('game auto exposure on', 'on'))):
        lx = 24 + i * 220
        o.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="3" fill="{t[key]}"/>')
        o.append(text(lx + 18, ly, lab, t, 12, 'ink2'))
    top = 96; base = top + ROW * len(ROWS)
    for v in range(0, MAXV + 1, 2):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(text(x, base + 18, f'{v}', t, 11, 'muted', 'middle'))
    for i, (b, a, on, hi) in enumerate(ROWS):
        y = top + i * ROW + (ROW - 2 * BAR - GAP) / 2
        o.append(text(X0 - 12, y + BAR + 4, b, t, 13, 'ink', 'end', 600 if hi else None))
        p, xa = bar(y, a, t['off']); o.append(p); o.append(text(xa + 8, y + BAR - 3, f'{a:.2f}', t, 11, 'ink' if hi else 'muted'))
        p, xb = bar(y + BAR + GAP, on, t['on']); o.append(p); o.append(text(xb + 8, y + 2 * BAR + GAP - 3, f'{on:.2f}', t, 11, 'ink' if hi else 'muted'))
    o.append(text(24, base + 42, 'One synthetic scene type, not used in training; one run each, Linux (Proton), Radeon RX 7800 XT. AMD’s Lite and', t, 11, 'muted'))
    o.append(text(24, base + 58, 'FSR 4.1.1 measured in this project’s local test harness. With the camera still, 4.1.2l-lossy and Lite are level (2.60 and 2.64).', t, 11, 'muted'))
    o.append('</svg>')
    open(f'rel-lite-wires-{name}.svg', 'w').write('\n'.join(o) + '\n')
for b, a, on, _ in ROWS:
    print(f'{b:24s} {a:5.2f} {on:5.2f}')
