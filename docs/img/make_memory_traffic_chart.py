#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes memory-traffic-light.svg and memory-traffic-dark.svg: memory read by each part of FSR 4
# per frame at 4K, AMD's shaders against this repository's. Data: research/postpass-and-prepass.
ROWS = [('Postpass', 2295, 732), ('Model pass 11', 1018, 234), ('Prepass', 1712, 1712),
        ('Other 11 model passes', 2643, 2643), ('All passes', 7668, 5321)]
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7',
                  before='#86b6ef', after='#2a78d6'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835',
                 before='#184f95', after='#3987e5'),
}
W, X0, X1, TOP, ROWH, BAR, GAP = 760, 200, 650, 92, 54, 14, 2
MAXV = 8000
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""


def bar(x0, y, w, h, fill):
    r = min(4, w)
    x1 = x0 + w
    return (f'<path d="M{x0},{y} H{x1 - r:.1f} Q{x1:.1f},{y} {x1:.1f},{y + r} V{y + h - r} '
            f'Q{x1:.1f},{y + h} {x1 - r:.1f},{y + h} H{x0} Z" fill="{fill}"/>')


for name, t in THEMES.items():
    H = TOP + ROWH * len(ROWS) + 58
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Memory read by FSR 4 per frame at 4K: 7,668 MB with AMD\'s shaders, 5,321 MB with this release">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         f'<text x="24" y="34" {FONT} font-size="16" font-weight="600" fill="{t["ink"]}">Memory read by FSR 4 per frame at 4K</text>',
         f'<text x="24" y="54" {FONT} font-size="12" fill="{t["ink2"]}">MB read from memory by each part, Radeon RX 7800 XT. Lower is better.</text>',
         f'<rect x="24" y="66" width="12" height="12" rx="2" fill="{t["before"]}"/>',
         f'<text x="42" y="76" {FONT} font-size="12" fill="{t["ink2"]}">AMD\'s shaders</text>',
         f'<rect x="140" y="66" width="12" height="12" rx="2" fill="{t["after"]}"/>',
         f'<text x="158" y="76" {FONT} font-size="12" fill="{t["ink2"]}">This release</text>']
    base = TOP + ROWH * len(ROWS)
    for v in range(0, MAXV + 1, 2000):
        x = X0 + (X1 - X0) * v / MAXV
        o.append(f'<line x1="{x:.1f}" y1="{TOP - 4}" x2="{x:.1f}" y2="{base}" stroke="{t["grid"] if v else t["axis"]}" stroke-width="1"/>')
        o.append(f'<text x="{x:.1f}" y="{base + 18}" {FONT} font-size="11" text-anchor="middle" fill="{t["muted"]}">{v:,}</text>')
    o.append(f'<text x="{X1}" y="{base + 38}" {FONT} font-size="11" text-anchor="end" fill="{t["muted"]}">MB per frame</text>')
    for i, (label, a, b) in enumerate(ROWS):
        y = TOP + ROWH * i + (ROWH - 2 * BAR - GAP) / 2
        if label == 'All passes':
            o.append(f'<line x1="24" y1="{TOP + ROWH * i}" x2="{W - 24}" y2="{TOP + ROWH * i}" stroke="{t["grid"]}" stroke-width="1"/>')
        weight = ' font-weight="600"' if label == 'All passes' else ''
        o.append(f'<text x="{X0 - 12}" y="{y + BAR + GAP / 2 + 4:.1f}" {FONT} font-size="13"{weight} text-anchor="end" fill="{t["ink"]}">{label}</text>')
        for k, (v, fill) in enumerate(((a, t['before']), (b, t['after']))):
            w = (X1 - X0) * v / MAXV
            yy = y + k * (BAR + GAP)
            o.append(bar(X0, yy, w, BAR, fill))
            o.append(f'<text x="{X0 + w + 8:.1f}" y="{yy + BAR - 3:.1f}" {FONT} font-size="12" fill="{t["ink2"]}">{v:,}</text>')
    o.append('</svg>')
    open(f'memory-traffic-{name}.svg', 'w').write('\n'.join(o) + '\n')
