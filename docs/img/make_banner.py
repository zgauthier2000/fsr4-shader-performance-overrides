#!/usr/bin/env python3
"""make_banner.py: the front page's banner, docs/img/banner-light.svg and banner-dark.svg.

A wide banner, everything centered: on the first line the project's emblem and the name CYBOMAN, then
"FSR4 PERFORMANCE OVERRIDES" between two thin accent lines, then what the project does.

- The emblem: a hexagon frame broken at its corners, around a solid triangle with a bar across it. Its left half is
  drawn in coarse pixel blocks and its right half smooth, the way an upscaler turns a low-resolution picture into a
  sharp one. An original mark; not based on any other logo.
- CYBOMAN is drawn in the pixels of the X11 "9x15 bold" terminal font (misc-fixed, public domain), each pixel row
  with a dark gap like the lines of a CRT screen. The rows are copied into this script, so no font is needed for it.
- The subtitle and the last line are outlines of IBM Plex Mono SemiBold (docs/img/fonts, SIL Open Font License 1.1)
  and Noto Sans (SIL Open Font License 1.1; Arch / CachyOS package noto-fonts), not <text>, so the banner looks the
  same in every viewer. Needs fontTools.

    python3 docs/img/make_banner.py
"""
import math
import os

OUT = os.path.dirname(os.path.abspath(__file__))
W, H = 1600, 300
PLEX = os.path.join(OUT, 'fonts', 'IBMPlexMono-SemiBold.ttf')
NOTO = '/usr/share/fonts/noto/NotoSans-Regular.ttf'
SUB = 'FSR4 PERFORMANCE OVERRIDES'
TAG = 'Faster AMD FSR 4 upscaling on Windows and Linux'

THEMES = {
    'light': dict(ink='#1f2328', ink2='#3b4249', accent='#0b93a8', accent2='#3cb3c6', muted='#57606a'),
    'dark': dict(ink='#e6edf3', ink2='#c9d1d9', accent='#39c5d6', accent2='#6fd6e3', muted='#8b949e'),
}

# --- the emblem, drawn at its own scale around (EC, EC), then scaled into the banner
EC, PX = 150, 10            # the emblem's center in its own units, and one "low-resolution" block
R_IN, R_OUT, TRIM = 102, 126, 0.12      # the hexagon frame, and the share of each edge cut away at both ends
TRI = [(EC, 52), (EC - 82, 196), (EC + 82, 196)]
BAR = (EC - 58, 152, EC + 58, 170)      # x0, y0, x1, y1


def inside(pts, x, y):
    c = False
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def hexpts(r):
    return [(EC + r * math.cos(math.radians(-90 + 60 * i)), EC + r * math.sin(math.radians(-90 + 60 * i))) for i in range(6)]


def edges():
    """The broken frame: six edge pieces, each shortened at both ends."""
    o, n = hexpts(R_OUT), hexpts(R_IN); out = []
    lerp = lambda p, q, t: (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
    for i in range(6):
        a, b, c, d = o[i], o[(i + 1) % 6], n[(i + 1) % 6], n[i]
        out.append([lerp(a, b, TRIM), lerp(a, b, 1 - TRIM), lerp(d, c, 1 - TRIM), lerp(d, c, TRIM)])
    return out


def path(pts):
    return 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z'


def emblem(t, key):
    bar = [(BAR[0], BAR[1]), (BAR[2], BAR[1]), (BAR[2], BAR[3]), (BAR[0], BAR[3])]
    frame = edges()
    shapes = [  # (is this point inside?, smooth outline, fill rule, colors)
        (lambda x, y: any(inside(e, x, y) for e in frame), ' '.join(path(e) for e in frame), 'nonzero', ('ink', 'ink2')),
        (lambda x, y: inside(TRI, x, y) and not inside(bar, x, y), path(TRI) + ' ' + path(bar), 'evenodd', ('ink', 'ink2')),
        (lambda x, y: inside(bar, x, y), path(bar), 'nonzero', ('accent', 'accent2')),
    ]
    s = [f'<defs><clipPath id="right-{key}"><rect x="{EC}" y="0" width="{2 * EC}" height="{2 * EC}"/></clipPath></defs>']
    for pred, d, rule, (c1, c2) in shapes:
        for gy in range(0, 2 * EC, PX):      # the left half as blocks: a block where its center is inside the shape
            for gx in range(0, EC, PX):
                if pred(gx + PX / 2, gy + PX / 2):
                    s.append(f'<rect x="{gx}" y="{gy}" width="{PX}" height="{PX}" fill="{t[c2] if (gx // PX + gy // PX) % 4 == 0 else t[c1]}"/>')
        s.append(f'<path d="{d}" fill="{t[c1]}" fill-rule="{rule}" clip-path="url(#right-{key})"/>')
    s.append(f'<line x1="{EC}" y1="14" x2="{EC}" y2="{2 * EC - 14}" stroke="{t["accent"]}" stroke-width="2" stroke-dasharray="6 6"/>')     # the seam
    return s


# --- CYBOMAN in the X11 9x15 bold terminal font (public domain), its 10 rows from the cap line to the baseline
NAME = ['..#####..##....##.######.....####...##....##....##....##....##.',
        '.##...##.##....##.##...##...##..##..###..###...####...###...##.',
        '##.....#..##..##..##....##.##....##.########..##..##..####..##.',
        '##.........####...##...##..##....##.##.##.##.##....##.####..##.',
        '##..........##....######...##....##.##.##.##.##....##.##.##.##.',
        '##..........##....##...##..##....##.##.##.##.##....##.##.##.##.',
        '##..........##....##....##.##....##.##....##.########.##..####.',
        '##.....#....##....##....##.##....##.##....##.##....##.##...###.',
        '.##...##....##....##...##...##..##..##....##.##....##.##...###.',
        '..#####.....##....######.....####...##....##.##....##.##....##.']
CAP = 64                     # the name's height, px
NPX = CAP / len(NAME)        # one font pixel
NAME_W = len(NAME[0]) * NPX


def name(t, x0, base):
    out = []
    for y, row in enumerate(NAME):
        for x, ch in enumerate(row):
            if ch == '#':     # each pixel row a little shorter than the pixel: the gap reads as a CRT line
                out.append(f'<rect x="{x0 + x * NPX:.1f}" y="{base - CAP + y * NPX:.1f}" width="{NPX + 0.3:.1f}" height="{NPX * 0.72:.1f}" fill="{t["ink"]}"/>')
    return out


def outline(s, font, size, spacing=0.0):
    """The text as one SVG path at the origin (baseline y = 0), and its advance width."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    f = TTFont(font); gs = f.getGlyphSet(); cmap = f.getBestCmap(); k = size / f['head'].unitsPerEm
    pen = SVGPathPen(gs); x = 0.0
    for i, ch in enumerate(s):
        g = cmap[ord(ch)]
        gs[g].draw(TransformPen(pen, (k, 0, 0, -k, x, 0)))
        x += gs[g].width * k + (spacing if i < len(s) - 1 else 0)
    return pen.getCommands(), x


# --- the layout
SCALE = 0.46                 # the emblem in the banner
ER = SCALE * R_OUT           # its radius there
GAP = 30                     # between the emblem and the name
SUB_SIZE, SUB_SPACING, SUB_BASE = 34, 2, 196
TAG_SIZE, TAG_BASE = 22, 240
LINE_LEN, LINE_GAP = 250, 28  # the accent lines either side of the subtitle


def svg(n, t):
    x0 = (W - (2 * ER + GAP + NAME_W)) / 2
    ex, ey = x0 + ER, 102
    sub_d, sub_w = outline(SUB, PLEX, SUB_SIZE, SUB_SPACING)
    tag_d, tag_w = outline(TAG, NOTO, TAG_SIZE)
    ly = SUB_BASE - 0.35 * SUB_SIZE          # the lines at the middle of the capitals
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
             f'aria-label="cyboman, FSR4 Performance Overrides: an emblem of a broken hexagon around a triangle with a glowing bar, '
             f'drawn half in coarse pixels and half smooth, beside the name in a pixel terminal font">',
             f'<g transform="translate({ex - SCALE * EC:.1f} {ey - SCALE * EC:.1f}) scale({SCALE})">', *emblem(t, n), '</g>',
             *name(t, x0 + 2 * ER + GAP, 134),
             f'<path transform="translate({(W - sub_w) / 2:.1f} {SUB_BASE})" d="{sub_d}" fill="{t["accent"]}"/>']
    for x1, x2 in (((W - sub_w) / 2 - LINE_GAP - LINE_LEN, (W - sub_w) / 2 - LINE_GAP), ((W + sub_w) / 2 + LINE_GAP, (W + sub_w) / 2 + LINE_GAP + LINE_LEN)):
        parts.append(f'<line x1="{x1:.0f}" y1="{ly:.0f}" x2="{x2:.0f}" y2="{ly:.0f}" stroke="{t["accent"]}" stroke-width="3" opacity="0.6"/>')
    parts.append(f'<path transform="translate({(W - tag_w) / 2:.1f} {TAG_BASE})" d="{tag_d}" fill="{t["muted"]}"/>')
    parts.append('</svg>')
    p = os.path.join(OUT, f'banner-{n}.svg')
    open(p, 'w').write('\n'.join(parts) + '\n')
    print(p)


for name_, theme in THEMES.items():
    svg(name_, theme)
