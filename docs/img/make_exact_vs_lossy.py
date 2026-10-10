#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes exact-vs-lossy-light.svg and exact-vs-lossy-dark.svg, the figure of docs/exact-vs-lossy.md:
# what each of FSR 4.1.1's passes does in AMD's shaders, in the exact files and in the lossy test
# builds (on a frame that runs the model and on a skipped frame), with the upscaler time of each and
# what the lossy builds cost. Data: docs/exact-vs-lossy.md, research/lossy, research/frame-skip.
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', axis='#c3c2b7',
                  amd='#c3c2b7', exact='#2a78d6', lossy='#eb6834', onlossy='#0b0b0b'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', axis='#383835',
                 amd='#4a4a46', exact='#3987e5', lossy='#d95926', onlossy='#0b0b0b'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W, H = 760, 856
PASSES = ['Prepass', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', 'Postpass']
MODEL = PASSES[1:13]
# state of every pass in each kind of frame: a = AMD's code, e = rewritten with the same output,
# l = changes the output, s = skipped
EXACT = {p: 'e' for p in PASSES} | {'3': 'a', '6': 'a'}
LOSSY_RUN = dict(EXACT)      # the model itself is the exact files' since release dll-2026-10-09: no folding, AMD's rounding
LOSSY_SKIP = {p: 's' for p in MODEL} | {'Prepass': 'l', 'Postpass': 'l'}
ROWS = [
    ("AMD's shaders", 'every frame', {p: 'a' for p in PASSES}, 4.16, '4.16 ms', 'amd',
     ['The reference: all fourteen passes as AMD ships them.']),
    ('Exact files', 'every frame', EXACT, 2.99, '2.99 ms', 'exact',
     ["Twelve passes do the same arithmetic, laid out so the GPU gets through it faster. The image is AMD's, byte for byte."]),
    ('Lossy build', 'a frame that runs the model (every other frame)', LOSSY_RUN, 3.0, 'about 3.0 ms', 'lossy',
     ["The same shaders as the exact files, with AMD's arithmetic in the model. The prepass also notes each area's motion",
      'for the next frame. The output of this frame is what the exact files would give from the same history.']),
    ('Lossy build', 'a skipped frame (every other frame)', LOSSY_SKIP, 1.3, 'about 1.3 ms', 'lossy',
     ["The model does not run, and its last result follows the picture's motion. The picture is almost entirely the",
      "previous one moved along with the scene; the new frame counts for very little, except where the model had asked",
      "for it. Repairs: the history limited to the new frame's colors around the pixel, less weight where the nearest",
      "sample moved away, and the new frame where the history is nearly black, was hidden behind a moving object, or",
      "where the content changed without motion (particles, sparks).",
      "Where the picture is at rest, nothing is taken from the new frame."]),
]


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def hbar(x0, y, w, h, fill):
    r = min(4, w)
    x1 = x0 + w
    return (f'<path d="M{x0},{y} H{x1 - r:.1f} Q{x1:.1f},{y} {x1:.1f},{y + r} V{y + h - r} '
            f'Q{x1:.1f},{y + h} {x1 - r:.1f},{y + h} H{x0} Z" fill="{fill}"/>')


def box(x, y, w, h, label, state, t):
    cx, cy = x + w / 2, y + h / 2 + 4
    if state == 'a':
        return [f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="4" fill="{t["surface"]}" stroke="{t["axis"]}" stroke-width="1"/>',
                text(cx, cy, label, t, 12, 'ink2', 'middle')]
    if state == 's':        # skipped: dashed outline, the number struck through
        return [f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="4" fill="{t["surface"]}" stroke="{t["muted"]}" stroke-width="1" stroke-dasharray="3 3"/>',
                text(cx, cy, label, t, 12, 'muted', 'middle'),
                f'<line x1="{x + 6:.1f}" y1="{y + h - 7}" x2="{x + w - 6:.1f}" y2="{y + 7}" stroke="{t["muted"]}" stroke-width="1"/>']
    fill = t['exact'] if state == 'e' else t['lossy']
    ink = '#ffffff' if state == 'e' else t['onlossy']
    o = [f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="4" fill="{fill}"/>',
         f'<text x="{cx:.1f}" y="{cy}" {FONT} font-size="12" font-weight="600" text-anchor="middle" fill="{ink}">{label}</text>']
    if state == 'l':        # second cue besides the color: a mark in the corner
        o.append(f'<path d="M{x + w - 10:.1f},{y} H{x + w - 4:.1f} Q{x + w:.1f},{y} {x + w:.1f},{y + 4} V{y + 10} Z" fill="{t["onlossy"]}"/>')
    return o


def legend(x, y, t):
    o, items = [], [('e', 'rewritten, same output', 150), ('l', 'changes the output', 132), ('s', 'skipped', 74), ('a', "AMD's code", 0)]
    for state, label, adv in items:
        o += box(x, y, 22, 16, '', state, t) if state != 's' else box(x, y, 22, 16, '', 's', t)[:1] + [
            f'<line x1="{x + 5}" y1="{y + 12}" x2="{x + 17}" y2="{y + 4}" stroke="{t["muted"]}" stroke-width="1"/>']
        o.append(text(x + 28, y + 12, label, t))
        x += 28 + adv
    return o


def figure(t):
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         'aria-label="How the exact files and the lossy test builds differ from AMD\'s FSR 4.1.1 shaders, pass by pass. '
         "AMD's shaders: all fourteen passes unchanged, 4.16 ms per frame. Exact files: twelve passes rewritten with the same output "
         '(model passes 3 and 6 untouched), 2.99 ms, the image is AMD\'s byte for byte. Lossy build on a frame that runs the model: '
         'the same shaders as the exact files, about 3.0 ms. '
         'Lossy build on a skipped frame: all twelve model passes are skipped and the prepass and postpass show mostly the reprojected history, with the model\'s last result following the motion and four repairs, and nothing taken from the new frame where the picture is at rest unless its content changed, about 1.3 ms. '
         'The two kinds of frame alternate, 2.15 ms on average, 48% less than AMD\'s. Cost of the lossy build in a test scene at 4K Balanced: '
         'still picture 44.06 dB against 44.31, flicker on fine detail at rest 0.109 against 0.110, areas just uncovered by a moving object 36.47 dB against 34.48. '
         'Shadow of the Tomb Raider, 4K Balanced, Radeon RX 7800 XT.">',
         f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>',
         text(24, 34, 'Exact files and lossy builds, pass by pass', t, 16, 'ink', weight=600),
         text(24, 54, "FSR 4.1.1's passes in the order they run each frame, and what each build does with them.", t)]
    o += legend(24, 70, t)
    X0, BH, G, wide = 24, 30, 6, 84
    small = (W - 2 * X0 - 2 * wide - (len(PASSES) - 1) * G) / (len(PASSES) - 2)
    full = W - 2 * X0
    y = 112
    for n, (name, when, states, ms, label, kind, notes) in enumerate(ROWS):
        if n:
            o.append(f'<line x1="24" y1="{y - 14}" x2="{W - 24}" y2="{y - 14}" stroke="{t["grid"]}" stroke-width="1"/>')
        o.append(text(X0, y + 8, name, t, 14, 'ink', weight=600))
        o.append(text(X0 + 8 + 7.6 * len(name), y + 8, when, t, 12, 'ink2'))
        o.append(text(W - X0, y + 8, label, t, 14, 'ink', 'end', 600))
        ys, x = y + 20 + (16 if n == 0 else 0), X0      # room for the label over the model's passes
        for p in PASSES:
            w = wide if len(p) > 2 else small
            o += box(x, ys, w, BH, p, states[p], t)
            x += w + G
        if n == 0:
            m0 = X0 + wide + G
            m1 = W - X0 - wide - G
            o.append(text((m0 + m1) / 2, ys - 6, 'the model: 12 passes, about 60% of the time', t, 11, 'muted', 'middle'))
        # time bar under the strip, full width = AMD's 4.16 ms
        yb = ys + BH + 8
        o.append(f'<rect x="{X0}" y="{yb}" width="{full}" height="8" rx="4" fill="{t["grid"]}"/>')
        o.append(hbar(X0, yb, full * ms / 4.16, 8, t[kind]))
        for k, l in enumerate(notes):
            o.append(text(X0, yb + 26 + 16 * k, l, t))
        y = yb + 26 + 16 * len(notes) + 22
    # ---- what it adds up to
    o.append(f'<line x1="24" y1="{y - 14}" x2="{W - 24}" y2="{y - 14}" stroke="{t["grid"]}" stroke-width="1"/>')
    o.append(text(24, y + 12, 'Upscaler time, average', t, 14, 'ink', weight=600))
    o.append(text(24, y + 30, 'Shadow of the Tomb Raider, 4K Balanced, RX 7800 XT', t, 11, 'muted'))
    bx, bw = 24 + 84, 150
    for i, (lab, v, kind, note) in enumerate([("AMD's", 4.16, 'amd', '4.16 ms  ·  97 FPS'), ('Exact', 2.99, 'exact', '2.99 ms  ·  109 FPS  ·  28% less'),
                                              ('Lossy', 2.15, 'lossy', '2.15 ms  ·  120 FPS  ·  48% less')]):
        yy = y + 46 + i * 26
        o.append(text(bx - 10, yy + 12, lab, t, 12, 'ink', 'end'))
        o.append(hbar(bx, yy, bw * v / 4.16, 16, t[kind]))
        o.append(text(bx + bw * v / 4.16 + 8, yy + 12, note, t))
    x2 = 452
    o.append(text(x2, y + 12, 'What the lossy build costs', t, 14, 'ink', weight=600))
    o.append(text(x2, y + 30, "Test scene, 4K Balanced. Exact files = AMD's.", t, 11, 'muted'))
    o.append(text(x2 + 196, y + 52, "AMD's", t, 11, 'muted', 'end'))
    o.append(text(x2 + 284, y + 52, 'Lossy', t, 11, 'muted', 'end'))
    for i, (lab, a, b) in enumerate([('Still picture', '44.31 dB', '44.06 dB'), ('Flicker at rest, fine detail', '0.110', '0.109'),
                                     ('Areas just uncovered', '34.48 dB', '36.47 dB')]):
        yy = y + 72 + i * 22
        o.append(text(x2, yy, lab, t, 12, 'ink'))
        o.append(text(x2 + 196, yy, a, t, 12, 'ink2', 'end'))
        o.append(text(x2 + 284, yy, b, t, 12, 'ink', 'end', 600))
    return o, y + 72 + 2 * 22 + 24


for name, t in THEMES.items():
    body, used = figure(t)
    assert used <= H, used
    open(f'exact-vs-lossy-{name}.svg', 'w').write('\n'.join(body + ['</svg>']) + '\n')
