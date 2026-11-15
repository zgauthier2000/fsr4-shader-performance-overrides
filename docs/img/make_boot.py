#!/usr/bin/env python3
"""make_boot.py: the front page's banner in a CRT boot-log style.

Writes boot-{dark,light}.svg (wide banner), boot-{dark,light}-m.svg (phone layout, used below 600 px) and btn-*.svg\n(the link buttons under the summary) beside this file.
The README picks one with <picture> sources (prefers-color-scheme, max-width: 600px).

The text is drawn with a small condensed stroke font defined below (no font files, looks the same everywhere).
Animation is CSS inside the SVG: the boot lines appear one by one (once), ghost echoes fade under each new line,
the cursor blinks, the logo segments light up like neon tubes, and the logo gets a short RGB-split glitch every few seconds.
prefers-reduced-motion turns all of it off (everything then shows at rest).
"""
import math, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
G = HERE

# ---------- the stroke font: x 0..4, y 0..8 (cap line .. baseline), y down
O_ = [(1, 0), (3, 0), (4, 1), (4, 7), (3, 8), (1, 8), (0, 7), (0, 1), (1, 0)]
P_ = [(0, 8), (0, 0), (3, 0), (4, 1), (4, 3), (3, 4), (0, 4)]
F = {
    'A': [[(0, 8), (0, 1), (1, 0), (3, 0), (4, 1), (4, 8)], [(0, 4.5), (4, 4.5)]],
    'B': [[(0, 4), (3, 4), (4, 3), (4, 1), (3, 0), (0, 0), (0, 8), (3, 8), (4, 7), (4, 5), (3, 4)]],
    'C': [[(4, 0), (1, 0), (0, 1), (0, 7), (1, 8), (4, 8)]],
    'D': [[(0, 0), (3, 0), (4, 1), (4, 7), (3, 8), (0, 8), (0, 0)]],
    'E': [[(4, 0), (0, 0), (0, 8), (4, 8)], [(0, 4), (3, 4)]],
    'F': [[(4, 0), (0, 0), (0, 8)], [(0, 4), (3, 4)]],
    'G': [[(4, 0), (1, 0), (0, 1), (0, 7), (1, 8), (4, 8), (4, 4.5), (2.2, 4.5)]],
    'H': [[(0, 0), (0, 8)], [(4, 0), (4, 8)], [(0, 4), (4, 4)]],
    'I': [[(2, 0), (2, 8)], [(1, 0), (3, 0)], [(1, 8), (3, 8)]],
    'J': [[(4, 0), (4, 7), (3, 8), (1, 8), (0, 7)]],
    'K': [[(0, 0), (0, 8)], [(4, 0), (4, 1), (1, 4), (0, 4)], [(1, 4), (4, 7), (4, 8)]],
    'L': [[(0, 0), (0, 8), (4, 8)]],
    'M': [[(0, 8), (0, 0), (4, 0), (4, 8)], [(2, 0), (2, 6)]],
    'N': [[(0, 8), (0, 1), (1, 0), (3, 0), (4, 1), (4, 8)]],
    'O': [O_],
    'P': [P_],
    'Q': [O_, [(2.6, 6.2), (4, 8.4)]],
    'R': [P_, [(2.4, 4), (4, 6.5), (4, 8)]],
    'S': [[(4, 0), (1, 0), (0, 1), (0, 3), (1, 4), (3, 4), (4, 5), (4, 7), (3, 8), (0, 8)]],
    'T': [[(0, 0), (4, 0)], [(2, 0), (2, 8)]],
    'U': [[(0, 0), (0, 7), (1, 8), (3, 8), (4, 7), (4, 0)]],
    'V': [[(0, 0), (0, 5), (2, 8), (4, 5), (4, 0)]],
    'W': [[(0, 0), (0, 8), (4, 8), (4, 0)], [(2, 2), (2, 8)]],
    'X': [[(0, 0), (0, 2), (4, 6), (4, 8)], [(4, 0), (4, 2), (0, 6), (0, 8)]],
    'Y': [[(0, 0), (0, 2), (2, 4), (4, 2), (4, 0)], [(2, 4), (2, 8)]],
    'Z': [[(0, 0), (4, 0), (4, 1.5), (0, 6.5), (0, 8), (4, 8)]],
    '0': [O_, [(3.2, 1.6), (0.8, 6.4)]],
    '1': [[(0.8, 1.6), (2, 0), (2, 8)], [(0.8, 8), (3.2, 8)]],
    '2': [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (3, 4), (1, 4), (0, 5), (0, 8), (4, 8)]],
    '3': [[(0, 0), (3, 0), (4, 1), (4, 3), (3, 4), (1.2, 4)], [(3, 4), (4, 5), (4, 7), (3, 8), (0, 8)]],
    '4': [[(3, 8), (3, 0), (0, 5), (0, 5.4), (4, 5.4)]],
    '5': [[(4, 0), (0, 0), (0, 4), (3, 4), (4, 5), (4, 7), (3, 8), (0, 8)]],
    '6': [[(4, 0), (1, 0), (0, 1), (0, 7), (1, 8), (3, 8), (4, 7), (4, 5), (3, 4), (0, 4)]],
    '7': [[(0, 0), (4, 0), (4, 2), (2, 5), (2, 8)]],
    '8': [[(1, 4), (0, 3), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (3, 4), (1, 4), (0, 5), (0, 7), (1, 8), (3, 8), (4, 7), (4, 5), (3, 4)]],
    '9': [[(4, 4), (1, 4), (0, 3), (0, 1), (1, 0), (3, 0), (4, 1), (4, 7), (3, 8), (0, 8)]],
    '.': [[(1.5, 7.55), (1.5, 8)]],
    ',': [[(1.5, 7.4), (1.5, 8), (0.9, 9)]],
    ':': [[(2, 2.4), (2, 2.85)], [(2, 7.55), (2, 8)]],
    '/': [[(4, 0), (0, 8)]],
    '-': [[(0.6, 4.2), (3.4, 4.2)]],
    '_': [[(0, 8), (4, 8)]],
    '[': [[(3, 0), (1, 0), (1, 8), (3, 8)]],
    ']': [[(1, 0), (3, 0), (3, 8), (1, 8)]],
    "'": [[(2, 0), (2, 2)]],
    '>': [[(0.6, 1), (3.4, 4), (0.6, 7)]],
    '<': [[(3.4, 1), (0.6, 4), (3.4, 7)]],
    '=': [[(0.5, 2.9), (3.5, 2.9)], [(0.5, 5.3), (3.5, 5.3)]],
    '+': [[(0.5, 4.2), (3.5, 4.2)], [(2, 2.6), (2, 5.8)]],
    '%': [[(4, 0), (0, 8)], [(0, 0), (1.2, 0), (1.2, 1.6), (0, 1.6), (0, 0)], [(2.8, 6.4), (4, 6.4), (4, 8), (2.8, 8), (2.8, 6.4)]],
    '|': [[(2, -0.6), (2, 8.6)]],
    '*': [[(2, 1.5), (2, 6.5)], [(0, 2.5), (4, 5.5)], [(4, 2.5), (0, 5.5)]],
    '$': [[(4, 1), (1, 1), (0, 2), (0, 3), (1, 4), (3, 4), (4, 5), (4, 6), (3, 7), (0, 7)], [(2, -0.4), (2, 8.4)]],
    '~': [[(0, 4.6), (1, 3.6), (3, 4.6), (4, 3.6)]],
    'b': [[(0, 0), (0, 8), (3, 8), (4, 7), (4, 4), (3, 3), (0, 3)]],
    'y': [[(0, 3), (0, 6), (1, 7), (4, 7)], [(4, 3), (4, 9), (3, 10), (0.4, 10)]],
    ' ': [],
}
ADV = 5.7          # monospace advance in font units
SW = 0.9           # stroke width in font units


def text_d(s, x0, y0, k):
    """SVG path data for string s, cap line at y0, k px per font unit."""
    out = []
    for i, ch in enumerate(s):
        ch = ch if ch in F else ch.upper()
        for line in F[ch]:
            pts = [(x0 + (i * ADV + x) * k, y0 + y * k) for x, y in line]
            out.append('M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in pts))
    return ''.join(out)


def text_w(s, k):
    return (len(s) * ADV - (ADV - 4)) * k


# ---------- the emblem (a broken hexagon around a triangle with a bar; drawn here, no font or image files), and CYBOMAN in 9x15 bold pixels
EC, PX = 150, 10
R_IN, R_OUT, TRIM = 102, 126, 0.12
TRI = [(EC, 52), (EC - 82, 196), (EC + 82, 196)]
BAR = (EC - 58, 152, EC + 58, 170)


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
    o, n = hexpts(R_OUT), hexpts(R_IN); out = []
    lerp = lambda p, q, t: (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
    for i in range(6):
        a, b, c, d = o[i], o[(i + 1) % 6], n[(i + 1) % 6], n[i]
        out.append([lerp(a, b, TRIM), lerp(a, b, 1 - TRIM), lerp(d, c, 1 - TRIM), lerp(d, c, TRIM)])
    return out


def poly(pts):
    return 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in pts) + 'Z'


def emblem_paths():
    """(ink path d, accent path d) in emblem units: left half as blocks, right half smooth."""
    bar = [(BAR[0], BAR[1]), (BAR[2], BAR[1]), (BAR[2], BAR[3]), (BAR[0], BAR[3])]
    frame = edges()
    ink, acc = [], []
    for gy in range(0, 2 * EC, PX):
        for gx in range(0, EC, PX):
            cx, cy = gx + PX / 2, gy + PX / 2
            blk = f'M{gx} {gy}h{PX}v{PX}h-{PX}Z'
            if inside(bar, cx, cy):
                acc.append(blk)
            elif any(inside(e, cx, cy) for e in frame) or inside(TRI, cx, cy):
                ink.append(blk)
    smooth_ink = ''.join(poly(e) for e in frame) + poly(TRI) + poly(bar)
    return ''.join(ink), smooth_ink, ''.join(acc), poly(bar)


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


def name_d(x0, top, cap):
    p = cap / len(NAME); out = []
    for y, row in enumerate(NAME):
        x = 0
        while x < len(row):
            if row[x] == '#':
                e = x
                while e < len(row) and row[e] == '#':
                    e += 1
                out.append(f'M{x0 + x * p:.1f} {top + y * p:.1f}h{(e - x) * p:.1f}v{p * 0.72:.1f}h-{(e - x) * p:.1f}Z')
                x = e
            else:
                x += 1
    return ''.join(out), len(NAME[0]) * p



PIX = {  # bold 6x7 pixel capitals for the subtitle, drawn to match the 9x15-bold look of CYBOMAN
 'F': ['######','##....','##....','#####.','##....','##....','##....'],
 'S': ['.####.','##..##','##....','.####.','....##','##..##','.####.'],
 'R': ['#####.','##..##','##..##','#####.','##.##.','##..##','##..##'],
 '4': ['...##.','..###.','.#.##.','#..##.','######','...##.','...##.'],
 'P': ['#####.','##..##','##..##','#####.','##....','##....','##....'],
 'E': ['######','##....','##....','#####.','##....','##....','######'],
 'O': ['.####.','##..##','##..##','##..##','##..##','##..##','.####.'],
 'M': ['##..##','######','######','##..##','##..##','##..##','##..##'],
 'A': ['.####.','##..##','##..##','######','##..##','##..##','##..##'],
 'N': ['##..##','###.##','######','##.###','##..##','##..##','##..##'],
 'C': ['.####.','##..##','##....','##....','##....','##..##','.####.'],
 'V': ['##..##','##..##','##..##','##..##','##..##','.####.','..##..'],
 'I': ['.####.','..##..','..##..','..##..','..##..','..##..','.####.'],
 'D': ['#####.','##..##','##..##','##..##','##..##','##..##','#####.'],
 'b': ['##....','##....','#####.','##..##','##..##','##..##','#####.'],
 'y': ['......','......','##..##','##..##','##..##','.#####','....##','##..##','.####.'],
}


def pix_d(ch, x0, top, p):
    out = ''
    for y, row in enumerate(PIX[ch]):
        x = 0
        while x < len(row):
            if row[x] == '#':
                e = x
                while e < len(row) and row[e] == '#':
                    e += 1
                out += f'M{x0 + x * p:.1f} {top + y * p:.1f}h{(e - x) * p + 0.3:.1f}v{p * 0.72:.1f}h-{(e - x) * p + 0.3:.1f}Z'
                x = e
            else:
                x += 1
    return out



def logotype(word, x0, base, t, p=3.0):
    """word in the bold pixel font, caps sitting on the log's baseline, in the style CYBOS_STYLE."""
    d = ''; x = x0
    for ch in word:
        d += pix_d(ch, x, base - 7 * p, p)
        x += 7 * p
    w = x - x0 - p
    st = CYBOS_STYLE
    if st == 'inverse':      # inverse video: a lit block with the word cut out of it
        pad = 5
        return (f'<g><rect x="{x0 - pad:.1f}" y="{base - 7 * p - pad:.1f}" width="{w + 2 * pad:.1f}" height="{9 * p + 2 * pad - 2:.1f}" fill="{t["hi"]}" filter="url(#glow)" opacity="0.6"/>'
                f'<rect x="{x0 - pad:.1f}" y="{base - 7 * p - pad:.1f}" width="{w + 2 * pad:.1f}" height="{9 * p + 2 * pad - 2:.1f}" fill="{t["hi"]}"/>'
                f'<path d="{d}" fill="{t["bg"]}"/></g>')
    if st == 'split':        # like the big logo: pale letters with a wide red / cyan split
        return (f'<g><path d="{d}" fill="{t["hi"]}" filter="url(#glow)" opacity="0.7"/>'
                f'<path d="{d}" fill="{t["red"]}" opacity="0.6" transform="translate(-2.6 0)"/>'
                f'<path d="{d}" fill="{t["cyan"]}" opacity="0.6" transform="translate(2.6 0)"/>'
                f'<path d="{d}" fill="#d9ffe9"/></g>')
    # glow: bright green pixels, strong halo, with a lit underline like the emblem's bar
    return (f'<g><path d="{d}" fill="{t["hi"]}" filter="url(#glow)"/><path d="{d}" fill="{t["hi"]}" filter="url(#glow)"/>'
            f'<path d="{d}" fill="{t["red"]}" opacity="0.35" transform="translate(-1.6 0)"/>'
            f'<path d="{d}" fill="{t["cyan"]}" opacity="0.35" transform="translate(1.6 0)"/>'
            f'<path d="{d}" fill="#c8ffdf"/>'
            f'<rect x="{x0:.1f}" y="{base + 2 * p + 3:.1f}" width="{w:.1f}" height="{p * 0.9:.1f}" fill="{t["hi"]}" opacity="0.0"/></g>')

# ---------- colors
TH = {
    'dark': dict(page='#0d1117', frame='#1b2a21', bg='#040806', txt='#8affc1', hi='#3dff8f', dim='#4f8a68',
                 red='#ff2e63', cyan='#2ee6ff', fr=0.32, glow=0.55),
    'light': dict(page='#ffffff', frame='#c6d4cb', bg='#040806', txt='#8affc1', hi='#3dff8f', dim='#4f8a68',
                  red='#ff2e63', cyan='#2ee6ff', fr=0.32, glow=0.55),
}

LINES = [  # (text, style)  style: t = normal, h = highlight, d = dim
    ('... POWER ON SELF TEST ... OK', 'h'),
    ('... INITIALIZING FSR 4.1.2 + LITE', 't'),
    ('... SHADERS REWRITTEN FOR SPEED', 't'),
    ("... EXACT .... SAME PICTURE AS AMD'S", 't'),
    ('... LOSSY .... EVEN FASTER', 't'),
    ('... ONE FILE TO SWAP', 't'),
    ('... WINDOWS + LINUX', 't'),
    ('... READY', 'h'),
]

W, H = 1600, 380
MOBILE = False          # True: the phone layout (logo on top, log below), see the end of the file
CYBOS_STYLE = os.environ.get('CYBOS_STYLE', 'glow')
K = 2.05                # px per font unit in the log: cap height 16.4
LH = 31                 # line pitch
LX = 56
LY = (H - ((len(LINES) - 1) * LH + 8 * K)) / 2    # the log centered top to bottom
T0, DT = 0.5, 0.32      # first line time, gap between lines (s)
PAUSE0 = 0.6            # the first line's "..." drawn dot by dot before OK; later lines wait for it



def logo_dims():
    """sizes of the logo block: emblem scale, CYBOMAN cap height, gaps, widths, subtitle pixel, block height"""
    eu, cap, gap = (0.52, 58, 18) if MOBILE else (0.78, 88, 28)
    _, nw = name_d(0, 0, cap)
    ew = 2 * EC * eu
    lw = ew + gap + nw
    sub = 'FSR4 PERFORMANCE OVERRIDES'
    cols = sum(3 if c == ' ' else 7 for c in sub) - 1
    sgap = 14 if MOBILE else 20
    if MOBILE:                            # phone: two centered lines, larger
        sp = 5.3
        bh = 2 * EC * eu + sgap + 17 * sp
    else:
        sp = lw / cols                    # one subtitle pixel: the subtitle is as wide as emblem + CYBOMAN
        bh = 2 * EC * eu + sgap + 7 * sp  # the whole block's height
    return eu, cap, gap, ew, nw, lw, sub, cols, sp, sgap, bh

def banner(n, t, suffix=''):
    css = f"""
.ln{{animation:on .01s steps(1) both}}
@keyframes on{{from{{opacity:0}}to{{opacity:1}}}}
.gh{{opacity:0;animation:gh .7s linear both}}
@keyframes gh{{0%{{opacity:0}}15%{{opacity:.28}}45%{{opacity:.12}}60%{{opacity:.22}}100%{{opacity:0}}}}
.cur{{animation:blink 1.06s steps(1) infinite}}
@keyframes blink{{0%{{opacity:1}}50%{{opacity:0}}}}
.gr{{animation:gr 6.5s steps(1) 4.2s infinite}}
.gc{{animation:gc 6.5s steps(1) 4.2s infinite}}
.gs{{opacity:0;animation:gs 6.5s steps(1) 4.2s infinite}}
@keyframes gr{{0%{{transform:translate(-7px,0)}}2%{{transform:translate(4px,1px)}}4%{{transform:translate(-11px,-1px)}}6%,100%{{transform:translate(-2px,0)}}}}
@keyframes gc{{0%{{transform:translate(7px,0)}}2%{{transform:translate(-5px,-1px)}}4%{{transform:translate(10px,1px)}}6%,100%{{transform:translate(2px,0)}}}}
@keyframes gs{{0%{{transform:translate(16px,0);opacity:1}}2%{{transform:translate(-9px,0);opacity:1}}4%{{transform:translate(22px,0);opacity:1}}6%,100%{{transform:translate(0,0);opacity:0}}}}
.sg{{animation:sgA .75s linear both}}
.sg:nth-child(3n+2){{animation-name:sgB}}
.sg:nth-child(3n){{animation-name:sgC}}
@keyframes sgA{{0%{{opacity:.07}}5%{{opacity:1}}8%{{opacity:.07}}13%{{opacity:.85}}15%{{opacity:.07}}34%{{opacity:.07}}37%{{opacity:1}}41%{{opacity:.35}}45%,100%{{opacity:1}}}}
@keyframes sgB{{0%{{opacity:.07}}9%{{opacity:.07}}11%{{opacity:1}}14%{{opacity:.07}}24%{{opacity:.07}}26%{{opacity:.7}}28%{{opacity:.07}}47%{{opacity:.07}}50%,100%{{opacity:1}}}}
@keyframes sgC{{0%{{opacity:.07}}4%{{opacity:.9}}6%{{opacity:.07}}19%{{opacity:1}}22%{{opacity:.2}}25%,100%{{opacity:1}}}}
.tear{{opacity:0;animation:tear 9s steps(1) 6s infinite}}
@keyframes tear{{0%{{opacity:1;transform:translate(14px,0)}}1.2%{{opacity:1;transform:translate(-6px,0)}}2.4%,100%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}.gh,.tear,.gs{{opacity:0}}}}
"""
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         'aria-label="cyboman, FSR4 Performance Overrides. A terminal boot log: loading FSR 4.1.2 shaders, prepass, network and postpass OK; '
         'exact: same picture as AMD\'s, byte for byte; one file to swap, nothing else changes; Windows and Linux. Ready.">',
         f'<style>{css}</style>',
         '<defs>',
         '<radialGradient id="vig" cx="50%" cy="50%" r="75%"><stop offset="55%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.75"/></radialGradient>',
         '<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3dff8f" stop-opacity="0.07"/><stop offset="0.5" stop-color="#3dff8f" stop-opacity="0.02"/><stop offset="1" stop-color="#3dff8f" stop-opacity="0.05"/></linearGradient>',
         '<pattern id="scan" width="8" height="6" patternUnits="userSpaceOnUse"><rect width="8" height="2.2" y="3.8" fill="#000" opacity="0.38"/></pattern>',
         '<filter id="glow" x="-5%" y="-30%" width="110%" height="160%"><feGaussianBlur stdDeviation="3.2"/></filter>',
         '<filter id="glowL" x="-10%" y="-20%" width="120%" height="140%"><feGaussianBlur stdDeviation="6"/></filter>',
         f'<clipPath id="scr"><rect x="14" y="14" width="{W - 28}" height="{H - 28}" rx="22"/></clipPath>',
         '</defs>']
    # the window
    s.append(f'<rect x="4" y="4" width="{W - 8}" height="{H - 8}" rx="30" fill="{t["frame"]}"/>')
    s.append(f'<rect x="14" y="14" width="{W - 28}" height="{H - 28}" rx="22" fill="{t["bg"]}"/>')
    s.append('<g clip-path="url(#scr)">')
    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#sheen)"/>')

    # --- the log
    for i, (txt, sty) in enumerate(LINES):
        y = LY + i * LH
        mark = None
        if '{' in txt:                       # a word drawn as a small logotype
            pre, mark = txt.split('{')[0], txt.split('{')[1].rstrip('}')
            txt = pre
        d = text_d(txt, LX, y, K)
        col = {'h': t['hi'], 't': t['txt'], 'd': t['dim']}[sty]
        at = T0 + i * DT + (PAUSE0 if i > 0 else 0)
        gid = f'l{i}'
        s.append(f'<defs><path id="{gid}" d="{d}" fill="none" stroke-width="{SW * K:.2f}" stroke-linecap="square" stroke-linejoin="miter"/></defs>')
        # the line in pieces: (first character, last character + 1, extra delay); the first line types its "..." one dot at a time
        if i == 0 and '...' in txt[4:]:
            k0 = txt.index('...', 4)
            pieces = [(0, k0, 0)] + [(k0 + j, k0 + j + 1, (j + 1) * PAUSE0 / 3.6) for j in range(3)] + [(k0 + 3, len(txt), PAUSE0)]
        else:
            pieces = [(0, len(txt), 0)]
        for c0, c1, extra in pieces:
            pd = text_d(txt[c0:c1], LX + c0 * ADV * K, y, K)
            if not pd:
                continue
            pid = f'{gid}p{c0}'
            s.append(f'<defs><path id="{pid}" d="{pd}" fill="none" stroke-width="{SW * K:.2f}" stroke-linecap="square" stroke-linejoin="miter"/></defs>')
            s.append(f'<g class="ln" style="animation-delay:{at + extra:.2f}s">')
            s.append(f'<use href="#{pid}" xlink:href="#{pid}" filter="url(#glow)" opacity="{t["glow"]}" style="stroke:{col}"/>')
            s.append(f'<use href="#{pid}" xlink:href="#{pid}" x="-1.6" style="stroke:{t["red"]}" opacity="{t["fr"]}"/>')
            s.append(f'<use href="#{pid}" xlink:href="#{pid}" x="1.6" style="stroke:{t["cyan"]}" opacity="{t["fr"]}"/>')
            s.append(f'<use href="#{pid}" xlink:href="#{pid}" style="stroke:{col}"/>')
            if mark and c1 == len(txt):
                s.append(logotype(mark, LX + text_w(txt, K) + ADV * K * 0.4, y + 8 * K, t))
            s.append('</g>')
        # ghost echo just under the new line, while it settles
        if i < len(LINES) - 1:
            gat = at + (PAUSE0 if i == 0 else 0)
            s.append(f'<use class="gh" href="#{gid}" xlink:href="#{gid}" x="5" y="{LH * 0.72:.1f}" style="animation-delay:{gat:.2f}s;stroke:{col}"/>')
    # cursor after READY
    last = LINES[-1][0]
    cx = LX + text_w(last + ' ', K) + 2
    cy = LY + (len(LINES) - 1) * LH
    at = T0 + (len(LINES) - 1) * DT + PAUSE0
    s.append(f'<g class="ln" style="animation-delay:{at:.2f}s"><rect class="cur" x="{cx:.1f}" y="{cy - 1:.1f}" width="{3.6 * K:.1f}" height="{8.6 * K:.1f}" fill="{t["hi"]}"/></g>')

    # --- the logo, top right: emblem + CYBOMAN, subtitle under it
    eu, cap, gap, ew, nw, lw, sub, cols, sp, sgap, bh = logo_dims()
    if MOBILE:
        lx = (W - lw) / 2                 # phone: the block centered at the top
        ly = M_TOP
    else:
        log_r = LX + max(text_w(t_, K) for t_, _ in LINES)
        lx = (log_r + (W - LX)) / 2 - lw / 2  # the block centered in the space right of the log
        ly = (H - bh) / 2 - 16                # centered top to bottom, raised a little (the emblem has empty space at its top)
    ex, ey = lx, ly
    nx, ny = lx + ew + gap, ly + (2 * EC * eu - cap) / 2 - 6
    sx = lx
    sy = ly + 2 * EC * eu + sgap
    # --- the pieces, each with the moment it lights up
    bar = [(BAR[0], BAR[1]), (BAR[2], BAR[1]), (BAR[2], BAR[3]), (BAR[0], BAR[3])]
    frame = edges()
    def blocks(pred):
        out = ''
        for gy in range(0, 2 * EC, PX):
            for gx in range(0, EC, PX):
                if pred(gx + PX / 2, gy + PX / 2):
                    out += f'M{gx} {gy}h{PX}v{PX}h-{PX}Z'
        return out
    T1 = 0.35
    ink_parts, acc_parts, sub_parts = [], [], []
    def emb(px, sm, rule, at):
        return (f'<g class="sg" style="animation-delay:{at:.3f}s"><g transform="translate({ex:.1f} {ey:.1f}) scale({eu})">'
                f'<path d="{px}" stroke="none" clip-path="url(#lh)"/><path d="{sm}" stroke="none" fill-rule="{rule}" clip-path="url(#rh)"/></g></g>')
    for i, e in enumerate(frame):            # the frame, clockwise from the top
        ink_parts.append(emb(blocks(lambda x, y, e=e: inside(e, x, y)), poly(e), 'nonzero', T1 + i * 0.08))
    t_tri = T1 + 6 * 0.08 + 0.1
    ink_parts.append(emb(blocks(lambda x, y: inside(TRI, x, y) and not inside(bar, x, y) and not any(inside(e, x, y) for e in frame)),
                         poly(TRI) + poly(bar), 'evenodd', t_tri))
    t_bar = t_tri + 0.18
    acc_parts.append(emb(blocks(lambda x, y: inside(bar, x, y)), poly(bar), 'nonzero', t_bar))
    t_name = t_bar + 0.2
    for j in range(7):                       # CYBOMAN letter by letter (9 font columns each)
        p = cap / len(NAME); d = ''
        for y, row in enumerate(NAME):
            for x in range(j * 9, min(j * 9 + 9, len(row))):
                if row[x] == '#':
                    d += f'M{nx + x * p:.1f} {ny + y * p:.1f}h{p + 0.3:.1f}v{p * 0.72:.1f}h-{p + 0.3:.1f}Z'
        ink_parts.append(f'<path class="sg" style="animation-delay:{t_name + j * 0.09:.3f}s" d="{d}" stroke="none"/>')
    t_sub = t_name + 7 * 0.09 + 0.1
    def pw(txt):                             # width of a subtitle line
        return (sum(3 if c == ' ' else 7 for c in txt) - 1) * sp
    if MOBILE:
        rows = [('FSR4 PERFORMANCE', (W - pw('FSR4 PERFORMANCE')) / 2, sy), ('OVERRIDES', (W - pw('OVERRIDES')) / 2, sy + 10 * sp)]
    else:
        rows = [(sub, sx, sy)]
    i = 0
    for txt, cx_, ry in rows:
        for ch in txt:                       # the subtitle, in the pixel font
            if ch == ' ':
                cx_ += 3 * sp; i += 1
                continue
            d = pix_d(ch, cx_, ry, sp)
            cx_ += 7 * sp
            sub_parts.append(f'<path class="sg" style="animation-delay:{t_sub + i * 0.025:.3f}s" d="{d}" stroke="none"/>')
            i += 1
    clip = f'<clipPath id="rh"><rect x="{EC}" y="0" width="{EC + 20}" height="{2 * EC}"/></clipPath><clipPath id="lh"><rect x="0" y="0" width="{EC}" height="{2 * EC}"/></clipPath>'
    s.append(f'<defs>{clip}<g id="logo">' + ''.join(ink_parts) + '</g>'
             '<g id="logoacc">' + ''.join(acc_parts) + '</g>'
             '<g id="logosub">' + ''.join(sub_parts) + '</g>'
             f'<clipPath id="band1"><rect x="{lx - 40:.0f}" y="{ny + 20:.0f}" width="{lw + 80:.0f}" height="14"/></clipPath>'
             f'<clipPath id="band2"><rect x="{lx - 40:.0f}" y="{ey + 120:.0f}" width="{lw + 80:.0f}" height="9"/></clipPath>'
             '</defs>')
    # glow, then fringes (always slightly off, wider in a glitch), then the main logo; all inside the warm-up
    wx, wy = lx + lw / 2, ey + EC * eu + 20
    s.append('<g>')
    s.append(f'<g filter="url(#glowL)" opacity="0.45"><use href="#logo" xlink:href="#logo" style="fill:{t["hi"]};stroke:{t["hi"]}"/><use href="#logoacc" xlink:href="#logoacc" style="fill:{t["hi"]}"/></g>')
    s.append(f'<g class="gr" opacity="0.55" style="mix-blend-mode:screen"><use href="#logo" xlink:href="#logo" style="fill:{t["red"]};stroke:{t["red"]}"/></g>')
    s.append(f'<g class="gc" opacity="0.55" style="mix-blend-mode:screen"><use href="#logo" xlink:href="#logo" style="fill:{t["cyan"]};stroke:{t["cyan"]}"/></g>')
    s.append(f'<use href="#logo" xlink:href="#logo" style="fill:#d9ffe9;stroke:{t["txt"]}"/>')
    s.append(f'<use href="#logoacc" xlink:href="#logoacc" style="fill:{t["hi"]}"/>')
    s.append(f'<use href="#logosub" xlink:href="#logosub" filter="url(#glowL)" opacity="0.5" style="fill:{t["hi"]}"/>')
    s.append(f'<g class="gr" opacity="0.45"><use href="#logosub" xlink:href="#logosub" style="fill:{t["red"]}"/></g>')
    s.append(f'<g class="gc" opacity="0.45"><use href="#logosub" xlink:href="#logosub" style="fill:{t["cyan"]}"/></g>')
    s.append(f'<use href="#logosub" xlink:href="#logosub" style="fill:{t["hi"]}"/>')
    for b in ('band1', 'band2'):
        s.append(f'<g class="gs" clip-path="url(#{b})"><rect x="{lx - 40:.0f}" y="{ey - 10:.0f}" width="{lw + 80:.0f}" height="{2 * EC * eu + 80:.0f}" fill="{t["bg"]}"/>'
                 f'<use href="#logo" xlink:href="#logo" style="fill:#d9ffe9;stroke:{t["txt"]}"/></g>')
    s.append('</g>')
    # --- tear band across the log now and then
    s.append(f'<g class="tear"><rect x="20" y="{LY + 5 * LH - 6}" width="{W - 40}" height="22" fill="{t["bg"]}"/>'
             f'<g clip-path="url(#tb)"><use href="#l5" xlink:href="#l5" style="stroke:{t['txt']}"/><use href="#l6" xlink:href="#l6" style="stroke:{t['txt']}"/></g></g>')
    s.insert(s.index('</defs>') + 0, f'<clipPath id="tb"><rect x="0" y="{LY + 5 * LH - 6}" width="{W}" height="22"/></clipPath>')

    # --- scanlines, vignette, glass
    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#scan)"/>')
    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#vig)"/>')
    s.append('</g>')
    s.append(f'<rect x="14.5" y="14.5" width="{W - 29}" height="{H - 29}" rx="22" fill="none" stroke="#3dff8f" stroke-opacity="0.12"/>')
    s.append('</svg>')
    open(os.path.join(G, f'boot-{n}{suffix}.svg'), 'w').write('\n'.join(s) + '\n')


# ---------- buttons: same frame as before, label in the stroke font
BTNS = [('download', 'DOWNLOAD'), ('expect', 'WHAT TO EXPECT'), ('new', "WHAT'S NEW"), ('kit', 'TIMING KIT'),
        ('clips', 'GAME CLIPS'), ('pages', 'MORE PAGES'), ('coffee', 'BUY ME A COFFEE')]

# icons: (scale, (width, height) in icon units, stroke lines), drawn in amber (#ffb000 glow, #ffd27a core); the cup: two wavy steam lines, the cup, its handle
ICONS = {'coffee': (2.0, (5.6, 9.4), [[(1.3, 0), (1.9, 0.9), (1.3, 1.8), (1.9, 2.6)], [(3.0, 0), (3.6, 0.9), (3.0, 1.8), (3.6, 2.6)],
                                      [(0, 3.8), (0, 8.2), (1.2, 9.4), (3.4, 9.4), (4.6, 8.2), (4.6, 3.8), (0, 3.8)],
                                      [(4.6, 5.0), (5.6, 5.0), (5.6, 7.2), (4.6, 7.2)]])}


def button(key, label):
    k = 1.55
    tw = text_w('> ' + label, k)
    h = 32
    d = text_d('> ' + label, 15, (h - 8 * k) / 2, k)
    w = int(tw + 30); di = None
    if key in ICONS:      # an icon after the label, drawn at its own scale (taller than the letters), same strokes
        ki, (iw, ih), lines = ICONS[key]
        x0, y0 = 15 + tw + 2.2 * ADV * k / 2, (h - ih * ki) / 2
        di = ' '.join('M' + 'L'.join(f'{x0 + x * ki:.2f} {y0 + y * ki:.2f}' for x, y in ln) for ln in lines)
        w = int(x0 + iw * ki + 15)
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{label.title()}">'
         '<defs><filter id="g" x="-10%" y="-40%" width="120%" height="180%"><feGaussianBlur stdDeviation="1.6"/></filter>'
         f'<pattern id="sc" width="4" height="4" patternUnits="userSpaceOnUse"><rect y="2.6" width="4" height="1.4" fill="#000" opacity="0.35"/></pattern></defs>'
         f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="6" fill="#040806" stroke="#3dff8f" stroke-width="1.5"/>'
         f'<path d="{d}" fill="none" stroke="#3dff8f" stroke-width="{SW * k:.2f}" stroke-linecap="square" filter="url(#g)" opacity="0.6"/>'
         f'<path d="{d}" fill="none" stroke="#ff2e63" stroke-width="{SW * k:.2f}" stroke-linecap="square" opacity="0.3" transform="translate(-1 0)"/>'
         f'<path d="{d}" fill="none" stroke="#2ee6ff" stroke-width="{SW * k:.2f}" stroke-linecap="square" opacity="0.3" transform="translate(1 0)"/>'
         f'<path d="{d}" fill="none" stroke="#8affc1" stroke-width="{SW * k:.2f}" stroke-linecap="square"/>'
         + (f'<path d="{di}" fill="none" stroke="#ffb000" stroke-width="{SW * k:.2f}" stroke-linecap="square" stroke-linejoin="bevel" filter="url(#g)" opacity="0.75"/>'
            f'<path d="{di}" fill="none" stroke="#ff2e63" stroke-width="{SW * k:.2f}" stroke-linecap="square" stroke-linejoin="bevel" opacity="0.3" transform="translate(-1 0)"/>'
            f'<path d="{di}" fill="none" stroke="#ffd27a" stroke-width="{SW * k:.2f}" stroke-linecap="square" stroke-linejoin="bevel"/>' if di else '') +
         f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="5" fill="url(#sc)"/>'
         '</svg>')
    open(os.path.join(G, f'btn-{key}.svg'), 'w').write(s + '\n')
    return w


# ---------- divider: "..." in the font, a faint line, a faint ghost
def divider(n):
    dark = n == 'dark'
    ink = '#3dff8f' if dark else '#0a9d4f'
    sz, gap, y = 3.6, 9.0, 15.0          # dot size, dot pitch, center line
    dots = ''.join(f'M{4 + i * gap:.1f} {y - sz / 2:.1f}h{sz}v{sz}h-{sz}Z' for i in range(3))
    lx = 4 + 2 * gap + sz + 12
    fr = 0.35 if dark else 0.22
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="30" viewBox="0 0 1000 30" role="img" aria-label="section divider">'
         '<defs><filter id="g" x="-50%" y="-200%" width="200%" height="500%"><feGaussianBlur stdDeviation="2"/></filter></defs>'
         f'<path d="{dots}" fill="{ink}" filter="url(#g)" opacity="{0.5 if dark else 0.25}"/>'
         f'<path d="{dots}" fill="#ff2e63" opacity="{fr}" transform="translate(-1.2 0)"/>'
         f'<path d="{dots}" fill="#2ee6ff" opacity="{fr}" transform="translate(1.2 0)"/>'
         f'<path d="{dots}" fill="{ink}"/>'
         f'<rect x="{lx:.1f}" y="{y - 0.5:.1f}" width="{1000 - lx:.1f}" height="1" fill="{ink}" opacity="{0.35 if dark else 0.4}"/>'
         '</svg>')
    open(os.path.join(G, f'bdiv-{n}.svg'), 'w').write(s + '\n')


for n, t in TH.items():
    banner(n, t)
for k_, l_ in BTNS:
    button(k_, l_)



# ---------- the phone layout: a narrower, taller banner, logo on top and a larger log below it
_save = (W, H, K, LH, LX, LY)
MOBILE = True
M_TOP = 30
W, K, LH = 760, 2.6, 36
_bh = logo_dims()[-1]
_logw = max(text_w(t_, K) for t_, _ in LINES)
LX = (W - _logw) / 2
LY = M_TOP + _bh + 44
H = int(LY + (len(LINES) - 1) * LH + 8 * K + 40)
for n, t in TH.items():
    banner(n, t, '-m')
MOBILE = False
W, H, K, LH, LX, LY = _save
print('ok')
