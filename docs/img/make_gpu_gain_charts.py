#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes gpu-gain-{light,dark}.svg and gpu-times-{light,dark}.svg from every before/after report
# collected so far (docs/results.md, docs/gpu-support.md). One entry per report:
# (GPU type, card, game, output size, upscaler time before, after, in ms).
R3, R2, IG = 'Desktop RX 7000 (RDNA3)', 'Desktop RX 6000 (RDNA2)', 'Integrated RDNA3 (Radeon 780M)'
REPORTS = [
    (R3, 'RX 7800 XT', 'Rise of the Tomb Raider', '4K', 4.30, 3.02),
    (R3, 'RX 7800 XT', 'Shadow of the Tomb Raider', '4K', 4.16, 3.12),
    (R3, 'RX 7800 XT', 'Control Resonant', '4K', 5.40, 3.50),
    (R3, 'RX 7800 XT', 'Mortal Shell II', '4K', 4.97, 3.58),
    (R3, 'RX 7800 XT', 'Rise of the Tomb Raider', '2560x1440', 1.79, 1.49),
    (R3, 'RX 7800 XT', 'Shadow of the Tomb Raider', '2560x1440', 1.76, 1.55),
    (R2, 'RX 6900 XT', 'Ready or Not', '4K', 3.79, 2.57),
    (R2, 'RX 6900 XT', 'Final Fantasy VII Rebirth', '4K', 3.79, 2.70),
    (R2, 'RX 6900 XT', 'S.T.A.L.K.E.R. 2', '3440x1440', 2.22, 1.79),
    (R2, 'RX 6900 XT', 'Final Fantasy VII Rebirth', '2560x1440', 1.38, 1.23),
    (R2, 'RX 6750 XT', 'Mafia: The Old Country, native', '2560x1440', 2.31, 2.22),
    (R2, 'RX 6750 XT', 'Mafia: The Old Country', '2560x1440', 2.17, 2.13),
    (R2, 'RX 6800', 'Control Resonant', '2560x1440', 1.96, 1.92),
    (R2, 'RX 6600', 'Clair Obscur: Expedition 33', '1080p', 2.24, 2.18),
    (R2, 'RX 6600', 'Code Vein 2', '1080p', 2.43, 2.41),
    (IG, 'Radeon 780M', 'Cyberpunk 2077', '1080p', 5.15, 5.04),
]
SIZES = ['4K', '3440x1440', '2560x1440', '1080p']
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7',
                  c={R3: '#2a78d6', R2: '#c2570c', IG: '#7a4fc9'}),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835',
                 c={R3: '#3987e5', R2: '#e8823a', IG: '#a98bf0'}),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W = 760
pct = lambda b, a: 100 * (b - a) / b


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    s = s.replace('&', '&amp;')
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def head(h, label, title, sub, t):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{label}">',
            f'<rect width="{W}" height="{h}" rx="8" fill="{t["surface"]}"/>',
            text(24, 34, title, t, 16, 'ink', weight=600), text(24, 54, sub, t)]


def mark(kind, x, y, r, fill, t):
    ring = f' stroke="{t["surface"]}" stroke-width="2"'
    if kind == R3:
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}"{ring}/>'
    if kind == R2:
        return f'<rect x="{x - r:.1f}" y="{y - r:.1f}" width="{2 * r}" height="{2 * r}" rx="1.5" fill="{fill}"{ring}/>'
    return f'<path d="M{x:.1f},{y - r - 1:.1f} L{x + r + 1:.1f},{y:.1f} L{x:.1f},{y + r + 1:.1f} L{x - r - 1:.1f},{y:.1f} Z" fill="{fill}"{ring}/>'


def gain(t):
    X0, X1, MAXV, ROW = 250, 600, 40, 30
    groups = [(g, [s for s in SIZES if any(r[0] == g and r[3] == s for r in REPORTS)]) for g in (R3, R2, IG)]
    H = 78 + sum(30 + ROW * len(s) for _, s in groups) + 44
    o = head(H, 'Upscaling time saved by GPU type and output size. Desktop RX 7000: 25 to 35 percent at 4K, 12 to 17 percent at 1440p. '
             'Desktop RX 6000: 29 to 32 percent at 4K, 19 percent at 3440x1440, 2 to 11 percent at 2560x1440, 1 to 3 percent at 1080p. '
             'Integrated Radeon 780M: 2 percent at 1080p.',
             'How much upscaling time the rewrites save, by GPU type and output size',
             'Each mark is one before/after report: percent less FSR 4 time per frame than with AMD’s shaders.', t)
    base = H - 44
    for v in range(0, MAXV + 1, 10):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="70" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(text(x, base + 18, f'{v}%', t, 11, 'muted', 'middle'))
    o.append(text(X1, base + 36, 'less upscaling time', t, 11, 'muted', 'end'))
    y = 78
    for g, sizes in groups:
        o.append(f'<rect x="24" y="{y}" width="{W - 48}" height="22" rx="4" fill="{t["grid"]}" opacity="0.55"/>')
        o.append(mark(g, 38, y + 11, 5, t['c'][g], t))
        o.append(text(52, y + 15, g, t, 13, 'ink', weight=600))
        y += 30
        for s in sizes:
            vals = sorted(pct(r[4], r[5]) for r in REPORTS if r[0] == g and r[3] == s)
            cy = y + ROW / 2
            o.append(text(X0 - 14, cy + 4, s + ' output', t, 13, 'ink', 'end'))
            if len(vals) > 1:
                o.append(f'<line x1="{X0 + (X1 - X0) * vals[0] / MAXV:.1f}" y1="{cy}" x2="{X0 + (X1 - X0) * vals[-1] / MAXV:.1f}" y2="{cy}" '
                         f'stroke="{t["c"][g]}" stroke-width="2" opacity="0.35"/>')
            last = -99
            for k, v in enumerate(vals):
                dy = 0 if v - last > 1.6 else (6 if k % 2 else -6)
                last = v
                o.append(mark(g, X0 + (X1 - X0) * v / MAXV, cy + dy, 5, t['c'][g], t))
            rng = f'{vals[0]:.0f}%' if round(vals[0]) == round(vals[-1]) else f'{vals[0]:.0f}–{vals[-1]:.0f}%'
            n = len(vals)
            o.append(text(X1 + 14, cy + 4, f'{rng}  ·  {n} report{"s" if n > 1 else ""}', t))
            y += ROW
    return o


def times(t):
    X0, X1, MAXV, ROW = 352, 622, 6, 24
    order = [r for g in (R3, R2, IG) for r in REPORTS if r[0] == g]
    H = 78 + 3 * 30 + ROW * len(order) + 48
    o = head(H, 'FSR 4 upscaling time per frame before and after, for every report, grouped by GPU type. '
             + '; '.join(f'{r[1]} {r[2]} {r[3]}: {r[4]} to {r[5]} ms' for r in order) + '.',
             'FSR 4 time per frame, before and after, for every report',
             'Milliseconds per frame. Hollow mark: AMD’s shaders. Filled mark: with the rewrites. Shorter is better.', t)
    base = H - 48
    for v in range(0, MAXV + 1):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="70" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(text(x, base + 18, f'{v}', t, 11, 'muted', 'middle'))
    o.append(text(X1, base + 36, 'ms per frame', t, 11, 'muted', 'end'))
    y, cur = 78, None
    for g, card, game, size, b, a in order:
        if g != cur:
            cur = g
            o.append(f'<rect x="24" y="{y}" width="{W - 48}" height="22" rx="4" fill="{t["grid"]}" opacity="0.55"/>')
            o.append(mark(g, 38, y + 11, 5, t['c'][g], t))
            o.append(text(52, y + 15, g, t, 13, 'ink', weight=600))
            y += 30
        cy = y + ROW / 2
        xb, xa = X0 + (X1 - X0) * b / MAXV, X0 + (X1 - X0) * a / MAXV
        o.append(text(X0 - 14, cy + 4, f'{card} · {game} · {size}', t, 11.5, 'ink', 'end'))
        o.append(f'<line x1="{xa:.1f}" y1="{cy}" x2="{xb:.1f}" y2="{cy}" stroke="{t["c"][g]}" stroke-width="2"/>')
        o.append(f'<circle cx="{xb:.1f}" cy="{cy}" r="4.5" fill="{t["surface"]}" stroke="{t["c"][g]}" stroke-width="2"/>')
        o.append(mark(g, xa, cy, 4.5, t['c'][g], t))
        o.append(text(max(xb, xa) + 12, cy + 4, f'{b:.2f} → {a:.2f}  (−{pct(b, a):.0f}%)', t, 11))
        y += ROW
    return o


for name, t in THEMES.items():
    for fig, fn in (('gpu-gain', gain), ('gpu-times', times)):
        open(f'{fig}-{name}.svg', 'w').write('\n'.join(fn(t) + ['</svg>']) + '\n')
