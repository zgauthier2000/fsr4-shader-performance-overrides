#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes gpu-gain-light.svg and gpu-gain-dark.svg: the average reduction in FSR 4's time per frame
# for each kind of graphics card and output resolution. One entry per before/after report
# (docs/results.md lists them): (card type, output, upscaler time before, after, in ms).
R3, R2, IG = 'Desktop RX 7000', 'Desktop RX 6000', 'Integrated Radeon 780M'
REPORTS = [
    (R3, '4K', 4.30, 3.02), (R3, '4K', 4.16, 3.12), (R3, '4K', 5.40, 3.50), (R3, '4K', 4.97, 3.58),
    (R3, '1440p', 1.79, 1.49), (R3, '1440p', 1.76, 1.55),
    (R2, '4K', 3.79, 2.57), (R2, '4K', 3.79, 2.70),
    (R2, '1440p', 1.38, 1.23), (R2, '1440p', 2.31, 2.22), (R2, '1440p', 2.17, 2.13), (R2, '1440p', 1.96, 1.92),
    (R2, '1080p', 2.24, 2.18), (R2, '1080p', 2.43, 2.41),
    (IG, '1080p', 5.15, 5.04),
]
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7', bar='#2a78d6'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835', bar='#3987e5'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W, X0, X1, MAXV, ROW, BAR = 760, 250, 620, 40, 34, 18
rows = []
for g in (R3, R2, IG):
    for size in ('4K', '1440p', '1080p'):
        v = [100 * (b - a) / b for k, s, b, a in REPORTS if k == g and s == size]
        if v:
            rows.append((g, size, sum(v) / len(v)))


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


for name, t in THEMES.items():
    groups = [g for g in (R3, R2, IG)]
    H = 76 + sum(12 + ROW * sum(1 for r in rows if r[0] == g) for g in groups) + 46
    label = 'Average reduction in FSR 4 time per frame: ' + '; '.join(f'{g} at {s} output {v:.0f} percent' for g, s, v in rows) + '.'
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, 'How much faster FSR 4 gets', t, 16, 'ink', weight=600),
         text(24, 54, 'Average reduction in FSR 4’s time per frame, by graphics card and output resolution.', t)]
    base = H - 46
    for v in range(0, MAXV + 1, 10):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="70" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(text(x, base + 18, f'{v}%', t, 11, 'muted', 'middle'))
    y = 76
    for g in groups:
        mine = [r for r in rows if r[0] == g]
        y += 12
        o.append(text(24, y + ROW * len(mine) / 2 + 4, g, t, 13, 'ink', weight=600))
        for _, size, v in mine:
            w = (X1 - X0) * v / MAXV
            by = y + (ROW - BAR) / 2
            o.append(text(X0 - 12, by + BAR - 4, size, t, 13, 'ink', 'end'))
            r = min(4, w)
            o.append(f'<path d="M{X0},{by} H{X0 + w - r:.1f} Q{X0 + w:.1f},{by} {X0 + w:.1f},{by + r} V{by + BAR - r} '
                     f'Q{X0 + w:.1f},{by + BAR} {X0 + w - r:.1f},{by + BAR} H{X0} Z" fill="{t["bar"]}"/>')
            o.append(text(X0 + w + 8, by + BAR - 4, f'{v:.0f}%', t, 13, 'ink'))
            y += ROW
    o.append('</svg>')
    open(f'gpu-gain-{name}.svg', 'w').write('\n'.join(o) + '\n')
for g, s, v in rows:
    print(f'{g:24s} {s:6s} {v:.1f}%')
