#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes quickstart-light.svg and quickstart-dark.svg, the figure in the front page's quick start: what FSR 4.1.1 costs
# per frame with AMD's shaders, with the exact DLL and with the lossy DLL, and the frame rate that goes with each.
# Measured: Shadow of the Tomb Raider's built-in benchmark, 4K output, FSR 4.1.1 Balanced, Radeon RX 7800 XT
# (AMD's and the exact files under Proton with the Linux files; the lossy figure with the Linux lossy files).
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', amd='#a09f98', exact='#2a78d6', lossy='#eb6834'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', amd='#6d6c66', exact='#3987e5', lossy='#d95926'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W, H = 760, 318
ROWS = [  # label, what happens to the picture, ms per frame, FPS, color
    ("AMD's shaders", 'the reference', 4.16, 97, 'amd'),
    ('Exact DLL', 'same picture, byte for byte', 2.99, 109, 'exact'),
    ('Lossy DLL', 'very close picture, opt-in', 2.15, 120, 'lossy'),
]
X0, XMAX, MS_MAX = 232, 600, 4.5


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def figure(t):
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         'aria-label="What to expect at 4K on a Radeon RX 7800 XT in Shadow of the Tomb Raider, FSR 4.1.1 Balanced. '
         + ' '.join(f'{n}: {ms:.2f} milliseconds of upscaling per frame, {fps} frames per second, {what}.' for n, what, ms, fps, _ in ROWS)
         + ' Lower output resolutions gain less.">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, 'What to expect at 4K', t, 16, 'ink', weight=600),
         text(24, 54, 'Time FSR 4.1.1 takes per frame (shorter is better), and the frame rate that goes with it', t),
         text(XMAX + 136, 84, 'frame rate', t, 11, 'muted', 'end')]
    for g in range(0, 5):
        x = X0 + (XMAX - X0) * g / MS_MAX
        o.append(f'<line x1="{x:.1f}" y1="94" x2="{x:.1f}" y2="262" stroke="{t["grid"]}" stroke-width="1"/>')
        o.append(text(x, 278, f'{g} ms', t, 11, 'muted', 'middle'))
    for i, (name, what, ms, fps, col) in enumerate(ROWS):
        y = 102 + i * 54; w = (XMAX - X0) * ms / MS_MAX
        o += [text(24, y + 17, name, t, 14, 'ink', weight=600), text(24, y + 35, what, t, 12, 'ink2'),
              f'<path d="M{X0},{y} H{X0 + w - 4:.1f} Q{X0 + w:.1f},{y} {X0 + w:.1f},{y + 4} V{y + 32} Q{X0 + w:.1f},{y + 36} {X0 + w - 4:.1f},{y + 36} H{X0} Z" fill="{t[col]}"/>',
              text(X0 + w + 8, y + 23, f'{ms:.2f} ms', t, 13, 'ink', weight=600),
              text(XMAX + 136, y + 23, f'{fps} FPS', t, 14, 'ink', 'end', 600)]
    o.append(text(24, H - 14, 'Shadow of the Tomb Raider benchmark, 4K output, Balanced, Radeon RX 7800 XT. Lower resolutions and slower cards gain less.', t, 11, 'muted'))
    return o


for name, t in THEMES.items():
    open(f'quickstart-{name}.svg', 'w').write('\n'.join(figure(t) + ['</svg>']) + '\n')
