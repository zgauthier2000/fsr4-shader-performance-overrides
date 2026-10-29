#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes quickstart-light.svg and quickstart-dark.svg, the figure in the front page's "What to expect": how much of FSR 4's time per frame this
# project's builds save at 4K, card by card, against AMD's own FSR 4.1.2 (exact and lossy) and against AMD's FSR 4.1.2 Lite (4.1.2l-exact and
# 4.1.2l-lossy). Data: quickstart-data.json (moving scene, 4K Balanced):
#   - the first row: this project's Radeon RX 7800 XT under Linux (Proton), this release's builds, AMD's FSR 4.1.2 = the FSR SDK 2.4.0 game DLL
#     (RX 7000 model), two runs each in mirrored order;
#   - the others: Windows timing-kit reports (kits 2026-10-28, 2026-10-28.2 and 2026-10-29), median per card, each card's own AMD FSR 4.1.2 model
#     (RX 7000 / RX 6000) and AMD's Lite in the same report; test builds with this release's shaders (the lossy ones with test weights; RX 6000
#     exact and some RX 7000 reports without AMD's SDK pass 11, which this release's RX 7000 / RX 6000 exact DLLs add: up to 3% at 4K in two reports).
# Until release dll-2026-10-22 this figure showed Shadow of the Tomb Raider's benchmark on the RX 7800 XT (AMD's shaders, exact, lossy).
import json, os
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', amd='#a09f98', exact='#2a78d6', lossy='#eb6834'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', amd='#6d6c66', exact='#3987e5', lossy='#d95926'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
DAT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quickstart-data.json')))
ROWS = [r for r in DAT['rows'] if '3840x2160' in r['saved']]
W = 760
PA, PB, PW = 168, 468, 252               # left panel x, right panel x, panel width
SA, SB = 60, 20                          # % at each panel's right edge: each panel has its own scale (the Lite gains are small), shown on its own axis
Y0, RH, GAP, BH = 176, 44, 64, 15        # first row, row height, room between this project's row and the Windows rows (a rule and their heading), bar height


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def bar(x, y, v, smax, col, t):
    w = max(1.0, PW * max(v, 0) / smax); r = min(4, w / 2)
    return [f'<path d="M{x},{y} H{x + w - r:.1f} Q{x + w:.1f},{y} {x + w:.1f},{y + r} V{y + BH - r} Q{x + w:.1f},{y + BH} {x + w - r:.1f},{y + BH} H{x} Z" fill="{t[col]}"/>',
            text(x + w + 6, y + BH - 3, f'{v:.0f}%', t, 11.5, 'ink2')]


def ypos(i):
    return Y0 + i * RH + (GAP if i >= 1 else 0)


def figure(t):
    n = len(ROWS); H = ypos(n - 1) + RH + 132
    desc = ' '.join(f"{r['card']}, {r['os']}" + (f" ({r['reports']} report{'s' if r['reports'] > 1 else ''})" if r['reports'] else ' (this project)') + ': '
                    + f"exact {r['saved']['3840x2160']['exact']:.0f}%, lossy {r['saved']['3840x2160']['lossy']:.0f}% less time than AMD's FSR 4.1.2; "
                    + f"4.1.2l-exact {r['saved']['3840x2160']['lexact']:.0f}%, 4.1.2l-lossy {r['saved']['3840x2160']['llossy']:.0f}% less than AMD's Lite." for r in ROWS)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="What to expect at 4K: how much less time FSR 4 takes per frame with this project\'s builds than with AMD\'s own, card by card, moving scene, Balanced. {desc} '
         'The Windows rows come from testers\' timing-kit reports of test builds with this release\'s shaders. Other resolutions give other numbers.">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, 'What to expect at 4K', t, 16, 'ink', weight=600),
         text(24, 54, "How much less time FSR 4 takes per frame than with AMD's own. Longer is faster.", t)]
    lx = 24      # legend
    for col, lab in (('exact', "exact / 4.1.2l-exact: same picture as AMD's"), ('lossy', 'lossy / 4.1.2l-lossy: picture changed, opt-in')):
        o += [f'<rect x="{lx}" y="68" width="12" height="11" rx="3" fill="{t[col]}"/>', text(lx + 18, 78, lab, t, 11.5, 'ink2')]
        lx += 18 + 6.4 * len(lab) + 22
    for x0, title, keys in ((PA, "Against AMD's FSR 4.1.2", (('exact', 'exact'), ('lossy', 'lossy'))),
                            (PB, "Against AMD's FSR 4.1.2 Lite", (('exact', '4.1.2l-exact'), ('lossy', '4.1.2l-lossy')))):
        o.append(text(x0, 112, title, t, 13, 'ink', weight=600)); kx = x0      # each panel names its own two bars
        for col, lab in keys:
            o += [f'<rect x="{kx}" y="122" width="11" height="11" rx="3" fill="{t[col]}"/>', text(kx + 16, 132, lab, t, 11.5, 'ink', weight=600)]
            kx += 16 + 7.2 * len(lab) + 18
    o += [
          text(24, Y0 - 12, "This project's RX 7800 XT, Linux (Proton): the release's builds", t, 11, 'muted', weight=600)]
    ybot = ypos(n - 1) + RH - 6
    for x0, smax, step in ((PA, SA, 20), (PB, SB, 5)):
        for g in range(0, smax + 1, step):
            x = x0 + PW * g / smax
            for y_a, y_b in ((Y0 - 4, ypos(0) + RH - 6), (ypos(1) - 4, ybot)):      # grid in each section, not across the gap between them
                o.append(f'<line x1="{x:.1f}" y1="{y_a}" x2="{x:.1f}" y2="{y_b}" stroke="{t["grid"]}" stroke-width="1"/>')
            o.append(text(x, ybot + 14, f'{g}%', t, 10, 'muted', 'middle'))
    yr = (ypos(0) + RH + ypos(1) - 26) // 2      # the rule between this project's row and the Windows rows
    o += [f'<line x1="24" y1="{yr}" x2="{W - 24}" y2="{yr}" stroke="{t["muted"]}" stroke-width="1"/>',
          text(24, ypos(1) - 12, "Windows, testers' timing-kit reports (test builds with this release's shaders; median per card)", t, 11, 'muted', weight=600)]
    for i, r in enumerate(ROWS):
        y = ypos(i); s = r['saved']['3840x2160']
        sub = 'two runs each' if r['os'] == 'Linux' else f"{r['reports']} report{'s' if r['reports'] > 1 else ''}"
        o += [text(24, y + 17, r['card'], t, 13, 'ink', weight=600), text(24, y + 32, sub, t, 10.5, 'muted')]
        o += bar(PA, y + 4, s['exact'], SA, 'exact', t) + bar(PA, y + 7 + BH, s['lossy'], SA, 'lossy', t)
        o += bar(PB, y + 4, s['lexact'], SB, 'exact', t) + bar(PB, y + 7 + BH, s['llossy'], SB, 'lossy', t)
    yf = ybot + 36
    for k, line_ in enumerate((
            "Moving scene, 4K output, Balanced. AMD's FSR 4.1.2 is the card's own model: on RX 7000 it gives FSR 4.1.1's picture, on RX 6000 a picture that",
            "differs only in rounding. Linux row: AMD's FSR 4.1.2 = its FSR SDK 2.4.0 game DLL; Lite in this project's local test harness; two runs each.",
            "Windows rows: the lossy builds with test weights (same speed); RX 6000 exact and some RX 7000 reports without AMD's SDK pass 11, which this",
            "release's exact DLLs add (up to 3% at 4K so far). 1080p, 1440p and other cards: the tables below. Linux gains do not carry over to Windows.",
            "The two panels have different scales: 0 to 60% on the left, 0 to 20% on the right.")):
        o.append(text(24, yf + 15 * k, line_, t, 10, 'muted'))
    return o, H


if __name__ == '__main__':
    for name, t in THEMES.items():
        body, H = figure(t)
        open(f'quickstart-{name}.svg', 'w').write('\n'.join(body + ['</svg>']) + '\n')
