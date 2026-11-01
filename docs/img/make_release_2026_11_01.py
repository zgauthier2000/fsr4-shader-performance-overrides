#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes rel-2026-11-01-gain-light.svg and -dark.svg: how much faster than AMD's FSR 4.1.2 Lite (less time per frame) 4.1.2l-lossy and 4.1.2l-exact are, previous release (dll-2026-10-29) beside this release, with the gain over the previous release in each panel's heading. Windows
# timing-kit reports (kits 2026-10-30.8 to 2026-10-31.2), same reports, moving scene, Balanced, median per family; results much slower than the same card model's median (Lite figures) or the row's median (gains, docs/releases/dll-2026-11-01.md#speed) left out.
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', prev='#b9b8b1', lossy='#eb6834', exact='#2a78d6'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', prev='#5c5b56', lossy='#d95926', exact='#3987e5'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
SIZES = ('1080p', '1440p', '4K')
DATA = {"RX 7000": {"lossy_new": [20.4, 24.5, 18.8], "lossy_prev": [14.2, 15.2, 11.8], "exact_new": [10.6, 11.3, 10.7], "exact_prev": [5.9, 6.4, 5.9]}, "RX 6000": {"lossy_new": [14.1, 16.9, 14.0], "lossy_prev": [12.8, 15.5, 12.4], "exact_new": [9.9, 9.7, 9.5], "exact_prev": [6.1, 6.0, 6.4]}}
GAIN = {"lossy": {"RX 7000": [7.8, 11.0, 8.5], "RX 6000": [1.6, 2.3, 1.9]}, "exact": {"RX 7000": [5.0, 5.5, 4.6], "RX 6000": [5.3, 3.9, 2.8]}}
W, H = 760, 612
PW, PH, MAX = 340, 130, 30


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def bar(x, base, v, bw, col, t, bold=False):
    y = base - PH * v / MAX; r = 4
    return [f'<path d="M{x:.1f},{base} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} H{x + bw - r:.1f} Q{x + bw:.1f},{y:.1f} {x + bw:.1f},{y + r:.1f} V{base} Z" fill="{t[col]}"/>',
            text(x + bw / 2, y - 5, f'{v:.0f}%', t, 12 if bold else 11, 'ink' if bold else 'muted', 'middle', 600 if bold else None)]


def panel(x0, top, build, fam, t):
    d = DATA[fam]; g = GAIN[build][fam]; lo, hi = min(g), max(g); base = top + 40 + PH
    o = [text(x0, top, f'4.1.2l-{build} on {fam}', t, 14, 'ink', weight=600), text(x0, top + 18, (f'About {hi:.0f}%' if round(lo) == round(hi) else f'{lo:.0f} to {hi:.0f}%') + ' faster than our previous release', t, 12, 'ink2')]
    for v in (0, 10, 20, 30):
        y = base - PH * v / MAX
        o.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + PW}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>')
    gw = PW / 3; bw = 42
    for j, s in enumerate(SIZES):
        cx = x0 + (j + 0.5) * gw
        o += bar(cx - bw - 1, base, d[build + '_prev'][j], bw, 'prev', t) + bar(cx + 1, base, d[build + '_new'][j], bw, build, t, True)
        o.append(text(cx, base + 17, s, t, 11.5, 'ink2', 'middle'))
    return o


def figure(t):
    desc = ' '.join(f"4.1.2l-{b} on {f}: faster than AMD's Lite at 1080p / 1440p / 4K, previous release {' / '.join(str(v) for v in DATA[f][b + '_prev'])}%, this release {' / '.join(str(v) for v in DATA[f][b + '_new'])}%." for b in ('lossy', 'exact') for f in DATA)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{desc}">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>', text(24, 34, "How much faster than AMD's FSR 4.1.2 Lite", t, 17, 'ink', weight=600),
         text(24, 54, "0% = AMD's Lite. Taller is faster.", t), f'<rect x="24" y="68" width="12" height="11" rx="3" fill="{t["prev"]}"/>', text(42, 78, 'Our previous release', t, 11.5),
         f'<rect x="180" y="68" width="12" height="11" rx="3" fill="{t["lossy"]}"/>', f'<rect x="194" y="68" width="12" height="11" rx="3" fill="{t["exact"]}"/>', text(212, 78, 'This release', t, 11.5)]
    o += panel(24, 112, 'lossy', 'RX 7000', t) + panel(396, 112, 'lossy', 'RX 6000', t) + panel(24, 336, 'exact', 'RX 7000', t) + panel(396, 336, 'exact', 'RX 6000', t)
    for k, l in enumerate(("Windows timing-kit reports, moving scene, Balanced, median; timing program, not games. Results much slower than the median of their group are left out,",
                           "because other work on a desktop PC can slow a run.",
                           "Worse: on an RX 7800 XT under Linux, 4.1.2l-lossy renders 0.9% fewer frames in Shadow of the Tomb Raider's benchmark.")):
        o.append(text(24, 552 + 15 * k, l, t, 10, 'muted'))
    return o


if __name__ == '__main__':
    for name, t in THEMES.items():
        open(f'rel-2026-11-01-gain-{name}.svg', 'w').write('\n'.join(figure(t) + ['</svg>']) + '\n')
