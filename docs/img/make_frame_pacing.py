#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes frame-pacing-light.svg and frame-pacing-dark.svg, the figure of docs/frame-pacing.md: eight
# consecutive frames with the exact files and with the lossy build, against a frame cap of 116 FPS.
# The per-frame times are derived, not captured: the rest of a frame (everything that is not FSR 4) is about 6.15 ms in Shadow of the
# Tomb Raider's benchmark at 4K Balanced on an RX 7800 XT (109 FPS with exact files of 2.99 ms, 122 FPS with an earlier lossy build of
# 2.05 ms); FSR 4's times are release dll-2026-10-29's builds in the test rig's timing program (4K Balanced, moving scene, the same card,
# Linux): exact 3.14 ms, lossy 3.22 ms on a frame that runs the network and 1.25 ms on a skipped one. Up to that release: 2.99 / 2.9 / 1.2 ms
# against a 120 Hz refresh.
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7', exact='#2a78d6', lossy='#eb6834'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835', exact='#3987e5', lossy='#d95926'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W, H = 760, 400
REST = 6.15
EXACT = [REST + 3.14] * 8
LOSSY = [REST + (3.22 if i % 2 == 0 else 1.25) for i in range(8)]
CAP = 116
REFRESH = 1000 / CAP
YMAX = 10.0
ONBAR = '#0b0b0b'      # text set on the lossy color


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def panel(x0, title, sub, vals, color, t, labels=None):
    top, bot, pw = 118, 318, 316
    y = lambda v: bot - (bot - top) * v / YMAX
    o = [text(x0, 84, title, t, 14, 'ink', weight=600), text(x0, 102, sub, t, 12, 'ink2')]
    for g in (0, 2, 4, 6, 8, 10):
        o.append(f'<line x1="{x0 + 26}" y1="{y(g):.1f}" x2="{x0 + pw}" y2="{y(g):.1f}" stroke="{t["grid"]}" stroke-width="1"/>')
        o.append(text(x0 + 20, y(g) + 4, str(g), t, 11, 'muted', 'end'))
    bw, gap = 26, 9
    for i, v in enumerate(vals):
        x = x0 + 36 + i * (bw + gap)
        o.append(f'<path d="M{x},{bot} V{y(v) + 4:.1f} Q{x},{y(v):.1f} {x + 4},{y(v):.1f} H{x + bw - 4} Q{x + bw},{y(v):.1f} {x + bw},{y(v) + 4:.1f} V{bot} Z" fill="{t[color]}"/>')
        if labels and i < 2:      # what kind of frame, written up the bar
            o.append(f'<text transform="translate({x + bw / 2 + 4:.1f},{bot - 10}) rotate(-90)" {FONT} font-size="11" font-weight="600" fill="{ONBAR}">{labels[i]}</text>')
        if i < 2 or not labels:
            if i == 0 or labels:
                o.append(text(x + bw / 2, y(v) - 6, f'{v:.2f}', t, 11, 'ink', 'middle', 600))
        o.append(text(x + bw / 2, bot + 16, str(i + 1), t, 11, 'muted', 'middle'))
    # the refresh interval
    o.append(f'<line x1="{x0 + 26}" y1="{y(REFRESH):.1f}" x2="{x0 + pw}" y2="{y(REFRESH):.1f}" stroke="{t["ink"]}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    o.append(text(x0 + 36 + 4 * (bw + gap) - gap / 2, bot + 34, 'frame', t, 11, 'muted', 'middle'))
    return o


def figure(t):
    avg = sum(LOSSY) / len(LOSSY)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Frame time of eight consecutive frames, in milliseconds, against a frame cap of {CAP} FPS, {REFRESH:.2f} ms per frame. '
         f'Exact files: every frame takes {EXACT[0]:.2f} ms, above the interval. Lossy build: frames alternate between {LOSSY[0]:.2f} ms when the model runs '
         f'and {LOSSY[1]:.2f} ms when it is skipped; the average, {avg:.2f} ms, is below the cap\'s frame time, but every other frame is above it. '
         'Derived: the rest of a frame from Shadow of the Tomb Raider at 4K Balanced on a Radeon RX 7800 XT, FSR 4\'s times from the test rig on the same card.">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, f'The average fits a {CAP} FPS cap; every other frame does not', t, 16, 'ink', weight=600),
         text(24, 54, f'Frame time of eight consecutive frames, in ms. Dashed line: the frame time of a {CAP} FPS cap, {REFRESH:.2f} ms.', t)]
    o += panel(24, 'Exact files', f'every frame {EXACT[0]:.2f} ms  ·  {1000 / EXACT[0]:.0f} FPS', EXACT, 'exact', t)
    o += panel(404, 'Lossy build', f'average {avg:.2f} ms  ·  {1000 / avg:.0f} FPS', LOSSY, 'lossy', t, labels=['runs the model', 'skipped'])
    o.append(text(24, H - 20, 'Derived, not captured: the rest of a frame from Shadow of the Tomb Raider (4K Balanced, RX 7800 XT), FSR 4\'s times from the test rig.', t, 11, 'muted'))
    return o


for name, t in THEMES.items():
    open(f'frame-pacing-{name}.svg', 'w').write('\n'.join(figure(t) + ['</svg>']) + '\n')
