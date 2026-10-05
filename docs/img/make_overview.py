#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes overview-light.svg and overview-dark.svg, the figure at the top of the front README:
# which of FSR 4.1.1's passes are rewritten and what that does to the upscaler's time and to the
# memory it reads. Data: docs/how-it-works.md, docs/results.md, research/postpass-and-prepass.
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7',
                  amd='#c3c2b7', exact='#2a78d6'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835',
                 amd='#4a4a46', exact='#3987e5'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W, H = 760, 392
PASSES = ['Prepass', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', 'Postpass']
UNTOUCHED = {'3', '6'}


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def hbar(x0, y, w, h, fill):
    r = min(4, w)
    x1 = x0 + w
    return (f'<path d="M{x0},{y} H{x1 - r:.1f} Q{x1:.1f},{y} {x1:.1f},{y + r} V{y + h - r} '
            f'Q{x1:.1f},{y + h} {x1 - r:.1f},{y + h} H{x0} Z" fill="{fill}"/>')


def figure(t):
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         'aria-label="Overview. Of FSR 4.1.1\'s fourteen main passes, twelve are rewritten with the same output: the prepass (10% less time), '
         'ten model passes (the same arithmetic in fewer steps; pass 11 takes 62% less time and reads 77% less memory) and the postpass '
         '(about 70% less time, 68% less memory read). On a Radeon RX 7800 XT at 4K the upscaler time goes from 4.16 to 3.05 ms per frame '
         'and the memory read per frame from 7,668 to 5,321 MB.">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, 'What this project changes in FSR 4.1.1', t, 16, 'ink', weight=600),
         text(24, 54, "FSR 4's passes in the order they run each frame. Twelve of fourteen are rewritten; the image stays AMD's, byte for byte.", t)]
    # ---- the passes
    X0, Y, BH, G = 24, 96, 34, 6
    wide, n = 84, len(PASSES)
    small = (W - 2 * X0 - 2 * wide - (n - 1) * G) / (n - 2)
    xs, x = [], X0
    for p in PASSES:
        w = wide if len(p) > 2 else small
        xs.append((x, w))
        if p in UNTOUCHED:
            o.append(f'<rect x="{x:.1f}" y="{Y}" width="{w:.1f}" height="{BH}" rx="4" fill="{t["surface"]}" stroke="{t["axis"]}" stroke-width="1"/>')
            o.append(text(x + w / 2, Y + BH / 2 + 4, p, t, 12, 'ink2', 'middle'))
        else:
            o.append(f'<rect x="{x:.1f}" y="{Y}" width="{w:.1f}" height="{BH}" rx="4" fill="{t["exact"]}"/>')
            o.append(f'<text x="{x + w / 2:.1f}" y="{Y + BH / 2 + 4}" {FONT} font-size="12" font-weight="600" text-anchor="middle" fill="#ffffff">{p}</text>')
        x += w + G
    m0, m1 = xs[1][0], xs[12][0] + xs[12][1]
    o.append(text((m0 + m1) / 2, Y - 8, 'the model: 12 passes', t, 11, 'muted', 'middle'))
    o.append(f'<path d="M{m0:.1f},{Y - 3} V{Y - 6} H{m1:.1f} V{Y - 3}" fill="none" stroke="{t["axis"]}" stroke-width="1"/>')
    # what was done, under each group
    yb = Y + BH + 22
    notes = [(xs[0][0], 'start', 'Prepass', ['each thread fetches its', "neighbours' inputs once"], '−10% time'),
             ((m0 + m1) / 2, 'middle', 'Model passes', ['same arithmetic in fewer steps;', 'pass 11 stores its output in groups'], 'pass 11: −62% time, −77% memory read'),
             (xs[13][0] + xs[13][1], 'end', 'Postpass', ['writes its output in phases', 'instead of scattered stores'], 'about −70% time, −68% memory read')]
    for x, anchor, title, lines, gain in notes:
        o.append(text(x, yb, title, t, 13, 'ink', anchor, 600))
        for k, l in enumerate(lines):
            o.append(text(x, yb + 18 + 16 * k, l, t, 12, 'ink2', anchor))
        o.append(text(x, yb + 18 + 16 * len(lines) + 2, gain, t, 12, 'ink', anchor, 600))
    lx = 24
    o.append(f'<rect x="{lx}" y="{yb + 78}" width="12" height="12" rx="2" fill="{t["exact"]}"/>')
    o.append(text(lx + 18, yb + 88, 'rewritten, same output', t))
    o.append(f'<rect x="{lx + 170}" y="{yb + 78}" width="12" height="12" rx="2" fill="{t["surface"]}" stroke="{t["axis"]}" stroke-width="1"/>')
    o.append(text(lx + 188, yb + 88, "AMD's shader, untouched", t))
    # ---- the two results
    ys = yb + 108
    o.append(f'<line x1="24" y1="{ys}" x2="{W - 24}" y2="{ys}" stroke="{t["grid"]}" stroke-width="1"/>')
    panels = [(24, 'Upscaler time per frame', 'Shadow of the Tomb Raider, 4K Balanced, RX 7800 XT',
               [("AMD's shaders", 4.16, 'amd', '4.16 ms  ·  97 FPS'), ('This project', 3.05, 'exact', '3.05 ms  ·  109 FPS')], 4.16, '27% less'),
              (400, 'Memory read per frame', 'All of FSR 4 at 4K, RX 7800 XT',
               [("AMD's shaders", 7668, 'amd', '7,668 MB'), ('This project', 5321, 'exact', '5,321 MB')], 7668, '31% less')]
    for x0, title, sub, rows, mx, verdict in panels:
        o.append(text(x0, ys + 28, title, t, 14, 'ink', weight=600))
        o.append(text(x0 + 336, ys + 28, verdict, t, 14, 'ink', 'end', 600))
        o.append(text(x0, ys + 46, sub, t, 11, 'muted'))
        bx, bw = x0 + 96, 120
        for i, (label, v, kind, note) in enumerate(rows):
            y = ys + 62 + i * 28
            o.append(text(bx - 10, y + 12, label, t, 12, 'ink', 'end'))
            o.append(hbar(bx, y, bw * v / mx, 16, t[kind]))
            o.append(text(bx + bw * v / mx + 8, y + 12, note, t))
    return o


for name, t in THEMES.items():
    open(f'overview-{name}.svg', 'w').write('\n'.join(figure(t) + ['</svg>']) + '\n')
