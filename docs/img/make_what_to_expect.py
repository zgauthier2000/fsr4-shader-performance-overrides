#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes wte-<section>-light.svg / -dark.svg, the charts of docs/what-to-expect.md: per graphics chip, how much less time FSR 4 takes per frame with
# this project's builds than with AMD's own (moving scene, Balanced), at one size per row (the page's collapsed tables hold all sizes).
# Left panel: exact, lossy and AMD's Lite itself against AMD's FSR 4.1.2 on the same chip; right panel: 4.1.2l-exact and 4.1.2l-lossy against AMD's Lite.
# Data: what-to-expect-data.json (testers' timing-kit reports, each build against AMD's in the same report, median per chip; this project's RX 7800 XT
# under Linux). A build no report has timed on a chip says "no report"; a build that takes more time than AMD's says "slower".
import json, os, math
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', amd='#a09f98', exact='#2a78d6', lossy='#eb6834'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', amd='#6d6c66', exact='#3987e5', lossy='#d95926'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
HERE = os.path.dirname(os.path.abspath(__file__))
DAT = json.load(open(os.path.join(HERE, 'what-to-expect-data.json')))
W, PA, PB, PW = 760, 190, 486, 230
BH, RH, HEAD = 11, 50, 34          # bar height, row height (three bars), group heading height


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def bar(x, y, v, smax, col, t):
    if v is None:
        return [text(x + 2, y + BH - 1.5, 'no report', t, 10.5, 'muted')]
    if v < -0.5:
        return [f'<rect x="{x}" y="{y}" width="1.5" height="{BH}" fill="{t[col]}"/>', text(x + 7, y + BH - 1.5, f'{-v:.0f}% slower', t, 10.5, 'ink2')]
    w = max(1.5, PW * max(v, 0) / smax); r = min(3, w / 2)
    return [f'<path d="M{x},{y} H{x + w - r:.1f} Q{x + w:.1f},{y} {x + w:.1f},{y + r} V{y + BH - r} Q{x + w:.1f},{y + BH} {x + w - r:.1f},{y + BH} H{x} Z" fill="{t[col]}"/>',
            text(x + w + 5, y + BH - 1.5, f'{v:.0f}%', t, 10.5, 'ink2')]


def chart(sec, t):
    rows = sec['rows']
    vals = [r['saved'][k] for r in rows if 'saved' in r for k in r['saved'] if r['saved'][k] is not None]
    left = [r['saved'][k] for r in rows if 'saved' in r for k in ('exact', 'lossy', 'lite') if r['saved'][k] is not None]
    right = [r['saved'][k] for r in rows if 'saved' in r for k in ('lexact', 'llossy') if r['saved'][k] is not None]
    SA = max(20, 10 * math.ceil(max(left) / 10)); SB = max(10, 5 * math.ceil(max(right) / 5))
    y = 128 if 'heading' not in sec['rows'][0] else 120; pos = []
    for r in rows:
        pos.append(y); y += HEAD if 'heading' in r else RH
    H = y + 34 + 14 * (len(sec['notes']) + 1)
    desc = ' '.join(f"{r['card']} ({r['sub']}): exact {fmt(r['saved']['exact'])}, lossy {fmt(r['saved']['lossy'])}, AMD's Lite itself {fmt(r['saved']['lite'])} "
                    f"less time than AMD's FSR 4.1.2; 4.1.2l-exact {fmt(r['saved']['lexact'])}, 4.1.2l-lossy {fmt(r['saved']['llossy'])} less than AMD's Lite."
                    for r in rows if 'saved' in r)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{sec["title"]}: how much less time FSR 4 takes per frame '
         f'with this project\'s builds than with AMD\'s own, moving scene, Balanced. {desc}">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 32, sec['title'], t, 16, 'ink', weight=600),
         text(24, 52, sec['subtitle'], t, 12)]
    for x0, title, keys in ((PA, "Against AMD's FSR 4.1.2", (('exact', 'exact'), ('lossy', 'lossy'), ('amd', "AMD's Lite"))),
                            (PB, "Against AMD's FSR 4.1.2 Lite", (('exact', '4.1.2l-exact'), ('lossy', '4.1.2l-lossy')))):
        o.append(text(x0, 86, title, t, 13, 'ink', weight=600)); kx = x0
        for col, lab in keys:
            o += [f'<rect x="{kx}" y="96" width="11" height="11" rx="3" fill="{t[col]}"/>', text(kx + 16, 106, lab, t, 11.5, 'ink', weight=600)]
            kx += 16 + 7.0 * len(lab) + 16
    ytop, ybot = 120, y - 6
    for x0, smax, step in ((PA, SA, 10 if SA <= 40 else 20), (PB, SB, 5)):
        for g in range(0, smax + 1, step):
            x = x0 + PW * g / smax
            o.append(f'<line x1="{x:.1f}" y1="{ytop}" x2="{x:.1f}" y2="{ybot}" stroke="{t["grid"]}" stroke-width="1"/>')
            o.append(text(x, ybot + 14, f'{g}%', t, 10, 'muted', 'middle'))
    for r, yy in zip(rows, pos):
        if 'heading' in r:
            o += [f'<rect x="20" y="{yy + 4}" width="{W - 40}" height="{HEAD - 10}" fill="{t["surface"]}"/>', text(24, yy + 22, r['heading'], t, 11, 'muted', weight=600)]
            continue
        s = r['saved']
        o += [text(24, yy + 16, r['card'], t, 12.5, 'ink', weight=600), text(24, yy + 31, r['sub'], t, 10.5, 'muted')]
        for i, (k, col) in enumerate((('exact', 'exact'), ('lossy', 'lossy'), ('lite', 'amd'))):
            o += bar(PA, yy + 4 + i * (BH + 3), s[k], SA, col, t)
        for i, (k, col) in enumerate((('lexact', 'exact'), ('llossy', 'lossy'))):
            o += bar(PB, yy + 4 + i * (BH + 3), s[k], SB, col, t)
    for k, line_ in enumerate(sec['notes'] + [f"The two panels have different scales: 0 to {SA}% on the left, 0 to {SB}% on the right."]):
        o.append(text(24, ybot + 34 + 14 * k, line_, t, 10, 'muted'))
    return o, H


def fmt(v):
    return 'no report' if v is None else (f'{v:.0f}%' if v >= -0.5 else f'{-v:.0f}% more')


if __name__ == '__main__':
    for sec in DAT['sections']:
        for name, t in THEMES.items():
            body, H = chart(sec, t)
            open(os.path.join(HERE, f'wte-{sec["id"]}-{name}.svg'), 'w').write('\n'.join(body + ['</svg>']) + '\n')
        print('wrote', sec['id'], len([r for r in sec['rows'] if 'saved' in r]), 'rows')
