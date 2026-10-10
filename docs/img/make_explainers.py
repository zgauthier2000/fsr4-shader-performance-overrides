#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes the plain-language figures at the top of the technical pages (explain-*-light.svg, explain-*-dark.svg):
#   explain-skip        how the lossy DLL saves time: the model runs on every other frame
#   explain-particles   a spark over four frames: as it should look, in the previous lossy release, in this one
#   explain-folding     what weight folding traded: heavy, none, and the light form in the first layer
#   explain-rows        scattered writes against ordered rows, and the code that was left in the files
#   explain-downloads   four builds became two downloads
#   explain-kits        what the Linux kit and the Windows kit each time
# They are schematics: the numbers in them are quoted from the pages they sit on.
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', box='#efeee8', amd='#a09f98', exact='#2a78d6', lossy='#eb6834', on='#ffffff'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', box='#262624', amd='#6d6c66', exact='#3987e5', lossy='#d95926', on='#ffffff'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W = 760


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t.get(fill, fill)}">{s}</text>'


def rect(x, y, w, h, fill, t, r=4, stroke=None, dash=False):
    st = f' stroke="{t.get(stroke, stroke)}" stroke-width="1.5"' + (' stroke-dasharray="4 3"' if dash else '') if stroke else ''
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{t.get(fill, fill)}"{st}/>'


def line(x1, y1, x2, y2, t, c='grid', w=1, dash=False):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{t.get(c, c)}" stroke-width="{w}"' + (' stroke-dasharray="4 3"' if dash else '') + '/>'


def arrow(x1, y1, x2, y2, t, c='muted'):
    import math
    a = math.atan2(y2 - y1, x2 - x1); h = 7
    p = [(x2, y2), (x2 - h * math.cos(a - 0.45), y2 - h * math.sin(a - 0.45)), (x2 - h * math.cos(a + 0.45), y2 - h * math.sin(a + 0.45))]
    return line(x1, y1, x2 - 4 * math.cos(a), y2 - 4 * math.sin(a), t, c, 1.5) + '<polygon points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in p) + f'" fill="{t[c]}"/>'


def frame(H, label, title, sub, t):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">',
            rect(0, 0, W, H, 'surface', t, 8), text(24, 34, title, t, 16, 'ink', weight=600), text(24, 54, sub, t)]


def skip(t):
    o = frame(250, "How the lossy DLL saves time. AMD's shaders and the exact DLL run FSR 4's neural network on every frame. The lossy DLL runs it on every other frame "
              'and, on the frames in between, reuses the last result moved along with the picture. About 3.0 ms on a frame that runs the network and about 1.3 ms on one that skips it, at 4K on a Radeon RX 7800 XT.',
              'How the lossy DLL saves time', "FSR 4's neural network is about 60% of its work. The lossy DLL runs it on every other frame.", t)
    for r, (name, kinds, c) in enumerate((("AMD's shaders and the exact DLL", [1] * 6, 'exact'), ('Lossy DLL', [1, 0, 1, 0, 1, 0], 'lossy'))):
        y = 84 + r * 78
        o.append(text(24, y + 12, name, t, 13, 'ink', weight=600))
        for i, k in enumerate(kinds):
            x = 24 + i * 120
            o.append(rect(x, y + 22, 112, 34, 'box', t))
            o.append(rect(x, y + 22, 112 if k else 48, 34, c, t))
            if k:
                o.append(text(x + 8, y + 43, 'network runs', t, 11, 'on', weight=600))
            else:
                o.append(text(x + 56, y + 43, 'skipped', t, 11, 'muted'))
    o.append(text(24, 236, 'Each box is one frame; the colored part is the time FSR 4 takes. 4K on an RX 7800 XT: about 3.0 ms with the network, about 1.3 ms without.', t, 11, 'muted'))
    return o


def particles(t):
    o = frame(334, 'A spark that the game draws without motion information, over four frames. As it should look and with AMD\'s shaders, it moves a step every frame. '
              'In the previous lossy release it stayed where it was on every other frame, so it moved at half the frame rate, or showed dimmed. In this release it moves every frame again.',
              'A spark over four frames', 'Games draw sparks and embers without telling FSR that they move. On skipped frames the old lossy DLL left them behind.', t)
    cols = [200 + i * 136 for i in range(4)]
    for i, x in enumerate(cols):
        o.append(text(x + 56, 86, f'frame {i + 1}' + ('' if i % 2 == 0 else '  (skipped)'), t, 11, 'muted', 'middle'))
    rows = (("As it should look", "(and with AMD's shaders)", [0, 1, 2, 3], [1, 1, 1, 1]), ('Previous lossy release', 'stuck on skipped frames', [0, 0, 2, 2], [1, 0.55, 1, 0.55]),
            ('This release', 'taken from the new frame', [0, 1, 2, 3], [1, 0.93, 1, 0.93]))
    for r, (name, sub, pos, br) in enumerate(rows):
        y = 98 + r * 66
        o += [text(24, y + 24, name, t, 13, 'ink', weight=600), text(24, y + 42, sub, t, 11, 'ink2')]
        for i, x in enumerate(cols):
            o.append(rect(x, y, 112, 54, '#101010' if t is THEMES['light'] else '#0c0c0c', t, 4, 'grid'))
            cx = x + 20 + pos[i] * 24
            if r and pos[i] != i:      # where it should be
                o.append(f'<circle cx="{x + 20 + i * 24}" cy="{y + 27}" r="6" fill="none" stroke="#8a8a84" stroke-width="1" stroke-dasharray="2 2"/>')
            o.append(f'<circle cx="{cx}" cy="{y + 27}" r="9" fill="#f2c56a" opacity="{0.35 * br[i]:.2f}"/><circle cx="{cx}" cy="{y + 27}" r="4.5" fill="#ffe4a8" opacity="{br[i]:.2f}"/>')
    o.append(text(24, 304, 'Dashed circle: where the spark really is. Measured on tiny fast sparks: 16% of their brightness was shown on', t, 11, 'muted'))
    o.append(text(24, 320, 'skipped frames before, 77% now (AMD\'s shaders: 83%).', t, 11, 'muted'))
    return o


def folding(t):
    o = frame(336, 'Weight folding in the lossy DLL over three releases. Still picture, distance from AMD\'s: 0.65 dB with heavy folding in several layers in release dll-2026-10-07, '
              '0.21 dB with no folding in dll-2026-10-09, 0.27 dB with light folding in the first layer only in dll-2026-10-10. Flat areas at rest, change per frame in the worst piece: '
              '0.111, 0.157 and 0.109, against 0.126 with AMD\'s shaders. Frame rate in Shadow of the Tomb Raider at 4K: 122, 120, and not measured for the last, whose upscaler time is unchanged.',
              'Weight folding: taken out for accuracy, a little put back for steadiness',
              'Folding merges the network\'s smallest weights into their neighbors. Heavy folding cost accuracy; none let flat areas shimmer.', t)
    names = ('heavy, several layers (dll-2026-10-07)', 'none (dll-2026-10-09)', 'light, first layer only (this release)')
    rows = (('Still picture: distance from AMD\'s', 'test scene, 4K; less is better', (0.65, 0.21, 0.27), 0.8, '{:.2f} dB', None),
            ('Flat areas at rest: change per frame', "worst piece of the test scene; AMD's shaders: 0.126", (0.111, 0.157, 0.109), 0.2, '{:.3f}', None),
            ('Frame rate', 'Shadow of the Tomb Raider, 4K; more is better', (122, 120, None), 130, '{} FPS', None))
    for r, (name, sub, v, mx, fmt, ref) in enumerate(rows):
        y = 84 + r * 78
        o += [text(24, y + 16, name, t, 13, 'ink', weight=600), text(24, y + 34, sub, t, 11, 'ink2')]
        for k, (val, lab) in enumerate(zip(v, names)):
            last = k == 2
            if val is None:
                o.append(text(300, y + k * 20 + 12, 'not measured (upscaler time unchanged)  ' + lab, t, 11, 'ink', weight=600))
                continue
            o += [rect(300, y + k * 20, 200 * val / mx, 16, 'lossy' if last else 'amd', t), text(300 + 200 * val / mx + 8, y + k * 20 + 12, fmt.format(val) + '  ' + lab, t, 11, 'ink' if last else 'ink2', weight=600 if last else None)]
        if ref:
            x = 300 + 200 * ref / mx
            o += [line(x, y - 4, x, y + 60, t, 'ink2', 1), text(x + 4, y - 6, f"AMD's shaders: {ref}", t, 10, 'muted')]
    o.append(text(24, 322, 'The releases differ in other ways too (particle handling since dll-2026-10-09). Same build with and without heavy folding: 122 against 121 FPS.', t, 11, 'muted'))
    return o


def rows(t):
    import random
    o = frame(330, 'Two changes inside the Windows DLLs. Left: AMD\'s shader writes its output pixels in a scattered order, which is slow on Radeon chips; the rewrite collects them and writes row after row. '
              'Right: the previous DLL still carried the code the rewrites had replaced, for example 45 exchanges between threads in one shader where 13 are used; this release removes it.',
              'Two changes inside the Windows DLLs', 'Neither changes the picture. Whether they make Windows faster is what the timing kit is meant to find out.', t)
    rnd = random.Random(4)
    for k, (title, order) in enumerate((("AMD's shader: scattered writes", None), ('Rewritten: row after row', 'rows'))):
        x0, y0 = 24 + k * 200, 104
        o.append(text(x0, 90, title, t, 12, 'ink', weight=600))
        cells = [(c, r) for r in range(6) for c in range(8)]
        seq = cells[:] if order else rnd.sample(cells, len(cells))
        for n, (c, r) in enumerate(seq):
            o.append(rect(x0 + c * 21, y0 + r * 21, 18, 18, 'exact' if order else 'amd', t, 2))
            if n < 12:
                o.append(text(x0 + c * 21 + 9, y0 + r * 21 + 13, str(n + 1), t, 9, 'on', 'middle', 600))
        o.append(text(x0, y0 + 6 * 21 + 16, 'numbers: the order of the first 12 writes', t, 10, 'muted'))
    x0 = 452
    o += [text(x0, 90, 'Code in one shader file (the prepass)', t, 12, 'ink', weight=600), text(x0, 118, 'previous DLL', t, 11, 'ink2'),
          rect(x0, 126, 284 * 13 / 45, 22, 'exact', t), rect(x0 + 284 * 13 / 45 + 2, 126, 284 * 32 / 45 - 2, 22, 'amd', t),
          text(x0 + 6, 141, '13 used', t, 10, 'on', weight=600), text(x0 + 284 * 13 / 45 + 10, 141, '32 left over, for the driver to discard', t, 10, 'on'),
          text(x0, 178, 'this release', t, 11, 'ink2'), rect(x0, 186, 284 * 13 / 45, 22, 'exact', t), text(x0 + 6, 201, '13 used', t, 10, 'on', weight=600),
          text(x0, 232, 'Counted in exchanges between threads.', t, 10, 'muted')]
    o.append(text(24, 300, 'Measured so far (one RX 7800 XT, Linux with Proton): the last pass alone is faster (0.42 to 0.30 ms at 1440p); the whole', t, 11, 'muted'))
    o.append(text(24, 316, 'upscaler is the same as before, because that driver already discarded the leftover code. Windows: not measured yet.', t, 11, 'muted'))
    return o


def downloads(t):
    o = frame(300, 'Four builds became two downloads. The builds for RX 7000 and for RX 6000 are now one download, fsr4.1.1-cyboman.zip. The compact RX 6000 build and the integrated-graphics build are now one, fsr4.1.1-igpu-cyboman.zip. '
              'Each download holds an exact DLL, with the same picture as AMD\'s, and a lossy DLL, which is faster.', 'Four builds became two downloads', 'Pick by the name of your graphics chip. Each zip holds two DLLs.', t)
    old = (('RX 7000', 0), ('RX 6000', 0), ('RX 6000, compact', 1), ('integrated graphics', 1))
    new = (('fsr4.1.1-cyboman.zip', 'Radeon RX 7000 and RX 6000', 'the name has "RX" and four digits'), ('fsr4.1.1-igpu-cyboman.zip', 'graphics built into the processor', 'most laptops, mini PCs, handhelds'))
    o.append(text(24, 86, 'before: one file per kind of chip', t, 11, 'muted'))
    o.append(text(300, 86, 'now', t, 11, 'muted'))
    for i, (n, g) in enumerate(old):
        y = 96 + i * 46
        o += [rect(24, y, 190, 34, 'box', t, 4, 'grid'), text(36, y + 22, n, t, 12, 'ink'), arrow(216, y + 17, 296, 96 + g * 92 + 40, t)]
    for g, (zipn, who, how) in enumerate(new):
        y = 96 + g * 92
        o += [rect(300, y, 436, 80, 'box', t, 6, 'grid'), text(314, y + 24, zipn, t, 14, 'ink', weight=600), text(314, y + 44, who, t, 12, 'ink'), text(314, y + 62, how, t, 11, 'ink2'),
              rect(586, y + 12, 138, 24, 'exact', t), text(655, y + 28, 'exact: same picture', t, 11, 'on', 'middle', 600),
              rect(586, y + 44, 138, 24, 'lossy', t), text(655, y + 60, 'lossy: faster', t, 11, 'on', 'middle', 600)]
    o.append(text(24, 288, 'Radeon RX 9000: neither. Those cards run a different FSR 4.', t, 11, 'muted'))
    return o


def kits(t):
    o = frame(318, 'What the two timing kits measure. The Linux kit times each of FSR 4\'s fourteen passes on its own, with AMD\'s shaders and with the rewritten ones. '
              'The Windows kit times the whole upscaler in one piece, as a game runs it, with each DLL: AMD\'s shaders, the exact DLL and the lossy DLL, and checks that the exact DLL\'s picture is AMD\'s.',
              'What the two timing kits measure', 'Neither needs a game. Both show a summary at the end and ask before sending anything.', t)
    names = ['pre'] + [str(i) for i in range(1, 13)] + ['post']
    for r, (title, sub) in enumerate((('Linux kit: every pass on its own', "shows which part of FSR 4 is slow on a chip, and which rewrite helps"),
                                      ('Windows kit (experimental): the whole upscaler in one piece', "what a game sees, with each DLL; also checks the exact DLL's picture"))):
        y = 84 + r * 112
        o += [text(24, y + 12, title, t, 13, 'ink', weight=600), text(24, y + 30, sub, t, 11, 'ink2')]
        for i, n in enumerate(names):
            w = 62 if n in ('pre', 'post') else 44
            x = 24 + (0 if i == 0 else 66 + (i - 1) * 48)
            o.append(rect(x, y + 42, w, 28, 'exact' if r == 0 else 'box', t, 4, None if r == 0 else 'grid'))
            o.append(text(x + w / 2, y + 60, n, t, 11, 'on' if r == 0 else 'ink2', 'middle', 600 if r == 0 else None))
            if r == 0:
                o.append(text(x + w / 2, y + 84, 'ms', t, 9, 'muted', 'middle'))
        if r == 1:
            o += [line(24, y + 80, 736, y + 80, t, 'lossy', 2), line(24, y + 74, 24, y + 86, t, 'lossy', 2), line(736, y + 74, 736, y + 86, t, 'lossy', 2),
                  text(380, y + 98, 'one time for all of it, per DLL:   AMD\'s shaders   ·   exact   ·   lossy   ·   any other you add', t, 11, 'ink', 'middle', 600)]
    return o


FIGS = {'skip': skip, 'particles': particles, 'folding': folding, 'rows': rows, 'downloads': downloads, 'kits': kits}
if __name__ == '__main__':
    for name, fn in FIGS.items():
        for th, t in THEMES.items():
            open(f'explain-{name}-{th}.svg', 'w').write('\n'.join(fn(t) + ['</svg>']) + '\n')
