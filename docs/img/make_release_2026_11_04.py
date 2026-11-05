#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# timing-kit reports (kits 2026-10-30.8 to 2026-10-31.2), same reports, moving scene, Balanced, median per family; results much slower than the same card model's median (Lite figures) or the row's median (gains, docs/releases/dll-2026-11-01.md#speed) left out.
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', prev='#b9b8b1', lossy='#eb6834', exact='#2a78d6'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', prev='#5c5b56', lossy='#d95926', exact='#3987e5'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
SIZES = ('1080p', '1440p', '4K')
DATA = {"RX 7000": {"lossy_new": [21.3, 26.8, 19.2], "lossy_prev": [21.8, 23.8, 19.6], "exact_new": [13.3, 19.4, 11.8], "exact_prev": [12.5, 11.6, 10.8]}, "RX 6000": {"lossy_new": [15.2, 21.1, 14.9], "lossy_prev": [13.8, 17.0, 13.5], "exact_new": [13.8, 18.6, 10.6], "exact_prev": [11.7, 10.8, 9.0]}}
GAIN = {"lossy": {"RX 7000": [0.0, 4.5, -0.0], "RX 6000": [1.9, 5.2, 1.7]}, "exact": {"RX 7000": [1.1, 8.6, 1.1], "RX 6000": [2.4, 8.7, 2.0]}}
W, H = 760, 612
PW, PH, MAX = 340, 130, 30


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def bar(x, base, v, bw, col, t, bold=False):
    y = base - PH * v / MAX; r = 4
    return [f'<path d="M{x:.1f},{base} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} H{x + bw - r:.1f} Q{x + bw:.1f},{y:.1f} {x + bw:.1f},{y + r:.1f} V{base} Z" fill="{t[col]}"/>',
            text(x + bw / 2, y - 5, f'{v:.0f}%', t, 12 if bold else 11, 'ink' if bold else 'muted', 'middle', 600 if bold else None)]


def panel(x0, top, build, fam, t, d=None, g=None, sizes=SIZES, sub=None):
    d = d or DATA[fam]; g = g if g is not None else GAIN[build][fam]; base = top + 40 + PH
    lo, hi = (min(g), max(g)) if g else (0, 0)
    o = [text(x0, top, f'4.1.2l-{build} on {fam}', t, 14, 'ink', weight=600), text(x0, top + 18, sub if sub else (f'About {hi:.0f}%' if round(lo) == round(hi) else (f'Up to {hi:.0f}%' if lo < 0.5 else f'{lo:.0f} to {hi:.0f}%')) + ' faster than the previous release', t, 12, 'ink2')]
    for v in (0, 10, 20, 30):
        y = base - PH * v / MAX
        o.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + PW}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>')
    gw = PW / len(sizes); bw = 42
    for j, s in enumerate(sizes):
        cx = x0 + (j + 0.5) * gw
        pv = d[build + '_prev'][j]
        o += (bar(cx - bw - 1, base, pv, bw, 'prev', t) if pv is not None else [text(cx - bw / 2 - 1, base - 6, 'n/a', t, 11, 'muted', 'middle')]) + bar(cx + 1, base, d[build + '_new'][j], bw, build, t, True)
        o.append(text(cx, base + 17, s, t, 11.5, 'ink2', 'middle'))
    return o


def figure(t):
    desc = ' '.join(f"4.1.2l-{b} on {f}: faster than AMD's Lite at 1080p / 1440p / 4K, previous release {' / '.join(str(v) for v in DATA[f][b + '_prev'])}%, this release {' / '.join(str(v) for v in DATA[f][b + '_new'])}%." for b in ('lossy', 'exact') for f in DATA)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{desc}">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>', text(24, 34, "How much faster than AMD's FSR 4.1.2 Lite", t, 17, 'ink', weight=600),
         text(24, 54, "0% = AMD's Lite. Taller is faster.", t), f'<rect x="24" y="68" width="12" height="11" rx="3" fill="{t["prev"]}"/>', text(42, 78, 'Previous release (dll-2026-11-01)', t, 11.5),
         f'<rect x="250" y="68" width="12" height="11" rx="3" fill="{t["lossy"]}"/>', f'<rect x="264" y="68" width="12" height="11" rx="3" fill="{t["exact"]}"/>', text(282, 78, 'This release (dll-2026-11-04)', t, 11.5)]
    o += panel(24, 112, 'lossy', 'RX 7000', t) + panel(396, 112, 'lossy', 'RX 6000', t) + panel(24, 336, 'exact', 'RX 7000', t) + panel(396, 336, 'exact', 'RX 6000', t)
    for k, l in enumerate(("Windows timing-kit reports with this release's builds and dll-2026-11-01's in the same report, moving scene, Balanced, median; timing program, not games.",
                           "RX 7000: 4 reports (RX 7600, RX 7800 XT, RX 7900 XT, RX 7900 XTX); RX 6000: 9 reports. Steam Deck and Steam Machine: the second chart.",
                           "Not faster: 4.1.2l-lossy on RX 7000 at 1080p and 4K (0.0%).")):
        o.append(text(24, 552 + 15 * k, l, t, 10, 'muted'))
    return o


if __name__ == '__main__':
    for name, t in THEMES.items():
        open(f'rel-2026-11-04-gain-{name}.svg', 'w').write('\n'.join(figure(t) + ['</svg>']) + '\n')
