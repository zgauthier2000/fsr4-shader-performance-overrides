#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes rel-2026-10-22-gain-light.svg and rel-2026-10-22-gain-dark.svg: for each graphics card, how much faster than AMD's shaders the
# exact DLL is, the previous release's (dll-2026-10-19, one desktop build) against this release's build for that kind of card. Windows
# timing-kit study runs (kit 2026-10-19), 4K output, Balanced, moving scene, the same report for both bars (the median of two for the
# RX 7800 XT). The "this release" bar is the study DLL with the same change as the release build: RX 7000 without the split dot products
# (rdna3-s09), RX 6000 without the prepass change (rdna2-s08). RX 6000 cards are compared with AMD's shaders with the dot products split
# (AMD's own form differs in picture on them under Windows).
ROWS = [  # card, previous exact %, this release %, reports
    ('RX 7800 XT', -5.0, -8.2, 2), ('RX 7600', -22.0, -24.8, 1), ('RX 7900 XTX', -26.3, -28.5, 1),
    ('RX 6650 XT', -12.7, -14.6, 1), ('RX 6600', -3.3, -4.2, 1), ('RX 6800', -3.7, -4.4, 1),
    ('RX 6900 XT', -13.3, -14.0, 1), ('RX 6800 XT', -13.1, -13.3, 1),
]
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7', new='#2a78d6', old='#b8b7ae'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835', new='#3987e5', old='#5a5955'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W, X0, X1, MAXV, ROW, BAR, GAP = 760, 200, 640, 30, 40, 14, 2


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def bar(y, v, fill):
    w = (X1 - X0) * v / MAXV; r = min(4, w)
    return (f'<path d="M{X0},{y} H{X0 + w - r:.1f} Q{X0 + w:.1f},{y} {X0 + w:.1f},{y + r} V{y + BAR - r} '
            f'Q{X0 + w:.1f},{y + BAR} {X0 + w - r:.1f},{y + BAR} H{X0} Z" fill="{fill}"/>'), X0 + w


for name, t in THEMES.items():
    H = 108 + ROW * len(ROWS) + 60
    label = ('How much faster than AMD\'s shaders the exact DLL is at 4K, previous release against this release: '
             + '; '.join(f'{c} {-a:.1f} to {-b:.1f} percent' for c, a, b, _ in ROWS) + '.')
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, 'A build for each kind of card: the exact DLL’s gain at 4K', t, 16, 'ink', weight=600),
         text(24, 54, 'Faster than AMD’s shaders, % of FSR 4’s time per frame (Windows timing-kit reports, 4K Balanced, moving).', t)]
    ly = 76
    for i, (lab, key) in enumerate((('previous release (dll-2026-10-19)', 'old'), ('this release, the build for that card', 'new'))):
        lx = 24 + i * 260
        o.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="3" fill="{t[key]}"/>')
        o.append(text(lx + 18, ly, lab, t, 12, 'ink2'))
    top = 96; base = top + ROW * len(ROWS)
    for v in range(0, MAXV + 1, 5):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(text(x, base + 18, f'{v}%', t, 11, 'muted', 'middle'))
    for i, (card, a, b, n) in enumerate(ROWS):
        y = top + i * ROW + (ROW - 2 * BAR - GAP) / 2
        o.append(text(X0 - 12, y + BAR + 4, card + (f' ({n} reports)' if n > 1 else ''), t, 13, 'ink', 'end'))
        p, xo = bar(y, -a, t['old']); o.append(p); o.append(text(xo + 8, y + BAR - 3, f'{-a:.1f}%', t, 11, 'muted'))
        p, xe = bar(y + BAR + GAP, -b, t['new']); o.append(p)
        o.append(text(xe + 8, y + 2 * BAR + GAP - 2, f'{-b:.1f}% (+{a - b:.1f} pts)', t, 12, 'ink'))
    o.append(text(24, base + 42, 'One report per card except the RX 7800 XT. RX 6000: against AMD’s shaders with the dot products split. '
                  'Same picture in every build.', t, 11, 'muted'))
    o.append('</svg>')
    open(f'rel-2026-10-22-gain-{name}.svg', 'w').write('\n'.join(o) + '\n')
for c, a, b, n in ROWS:
    print(f'{c:20s} {a:+.1f}% -> {b:+.1f}% ({a - b:+.1f} pts, {n} report{"s" if n > 1 else ""})')
