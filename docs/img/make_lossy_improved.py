#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes lossy-improved-light.svg and lossy-improved-dark.svg, the front page's figure of what changed in the lossy
# DLL: how much of a particle drawn without motion vectors is shown where it truly is on a skipped frame, and how
# far a still picture is from AMD's. Test rig, 4K Balanced (research/frame-skip, docs/exact-vs-lossy.md).
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', prev='#b9b8b0', now='#eb6834', amd='#0b0b0b'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', prev='#55544f', now='#d95926', amd='#ffffff'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W, H = 760, 372
PART = [('Tiny, fast sparks', 16, 77, 83), ('Tiny, slow embers', 67, 77, 81), ('Larger particles', 70, 98, 98)]      # previous release, this release, AMD's (%)
STILL = (0.71, 0.25)                                                                                                 # dB below AMD's: previous, this release


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def bar(x, y, w, h, c):
    w = max(w, 5)
    return f'<path d="M{x},{y} H{x + w - 4:.1f} Q{x + w:.1f},{y} {x + w:.1f},{y + 4} V{y + h - 4} Q{x + w:.1f},{y + h} {x + w - 4:.1f},{y + h} H{x} Z" fill="{c}"/>'


def figure(t):
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         'aria-label="What changed in the lossy DLL, measured in the test rig at 4K. Share of a particle drawn without motion vectors that is shown where it truly is, on the frames that skip the model: '
         + ' '.join(f'{n.lower()}, {a} percent in the previous release, {b} percent now, {c} percent with AMD\'s shaders;' for n, a, b, c in PART)
         + f' and how far a still picture is from AMD\'s: {STILL[0]} dB in the previous release, {STILL[1]} dB now.">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, 'The lossy DLL: what changed in this release', t, 16, 'ink', weight=600),
         text(24, 54, 'Particles and sparks that games draw without motion information: how much of each is shown', t),
         text(24, 70, "where it really is, on the frames that skip the model (more is better). Gray: the previous release. Dashed line: AMD's shaders.", t)]
    x0, x1, xl = 200, 540, 560      # bars, then the figures in a column of their own (clear of the dashed line)
    for g in (0, 25, 50, 75, 100):
        x = x0 + (x1 - x0) * g / 100
        o.append(f'<line x1="{x:.1f}" y1="92" x2="{x:.1f}" y2="258" stroke="{t["grid"]}" stroke-width="1"/>')
        o.append(text(x, 274, f'{g}%', t, 11, 'muted', 'middle'))
    for i, (name, a, b, c) in enumerate(PART):
        y = 100 + i * 54
        o += [text(24, y + 26, name, t, 13, 'ink', weight=600),
              bar(x0, y, (x1 - x0) * a / 100, 18, t['prev']), text(xl, y + 13, f'{a}%  before', t, 12, 'ink2'),
              bar(x0, y + 22, (x1 - x0) * b / 100, 18, t['now']), text(xl, y + 35, f'{b}%  now', t, 12, 'ink', weight=600),
              text(W - 24, y + 24, f"AMD's: {c}%", t, 12, 'ink2', 'end')]
        xa = x0 + (x1 - x0) * c / 100
        o.append(f'<line x1="{xa:.1f}" y1="{y - 3}" x2="{xa:.1f}" y2="{y + 43}" stroke="{t["amd"]}" stroke-width="2" stroke-dasharray="4 3"/>')
    y = 300
    o += [f'<line x1="24" y1="{y - 10}" x2="{W - 24}" y2="{y - 10}" stroke="{t["grid"]}" stroke-width="1"/>',
          text(24, y + 16, 'Still picture: how far from AMD\'s (less is better)', t, 13, 'ink', weight=600),
          bar(380, y, 160 * STILL[0] / 0.8, 16, t['prev']), text(xl, y + 12, f'{STILL[0]} dB  before', t, 12, 'ink2'),
          bar(380, y + 20, 160 * STILL[1] / 0.8, 16, t['now']), text(xl, y + 32, f'{STILL[1]} dB  now', t, 12, 'ink', weight=600),
          text(24, H - 12, 'Test rig, 4K output, Balanced, camera still. The exact DLL is not shown: its picture is AMD\'s, byte for byte.', t, 11, 'muted')]
    return o


for name, t in THEMES.items():
    open(f'lossy-improved-{name}.svg', 'w').write('\n'.join(figure(t) + ['</svg>']) + '\n')
