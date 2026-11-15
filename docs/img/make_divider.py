#!/usr/bin/env python3
"""make_divider.py: the front page's section divider (a signal line with a short square-wave glitch, faint RGB fringes and glow).
Writes divider-{dark,light}.svg beside this file; the README shows one per theme with <picture> before each main section."""
import os, random, math
HERE = os.path.dirname(os.path.abspath(__file__))
W, Hh, Y = 1000, 30, 15

def wrap(n, path_d, extra_style='', cls='', fade=False, sw=1.4):
    dark = n == 'dark'; ink = '#3dff8f' if dark else '#0a9d4f'; fr = 0.35 if dark else 0.2
    stroke = 'url(#fd)' if fade else ink
    p = lambda col, op, tr='': f'<path d="{path_d}" fill="none" stroke="{col}" stroke-width="{sw}" stroke-linejoin="bevel" opacity="{op}" {tr}/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{Hh}" viewBox="0 0 {W} {Hh}" role="img" aria-label="section divider">'
            + (f'<style>{extra_style}</style>' if extra_style else '') +
            '<defs><filter id="g" x="-5%" y="-300%" width="110%" height="700%"><feGaussianBlur stdDeviation="2"/></filter>'
            f'<linearGradient id="fd" gradientUnits="userSpaceOnUse" x1="0" x2="{W}"><stop offset="0" stop-color="{ink}"/><stop offset="0.5" stop-color="{ink}" stop-opacity="0.6"/><stop offset="1" stop-color="{ink}" stop-opacity="0"/></linearGradient></defs>'
            f'<g class="{cls}">'
            f'<g filter="url(#g)" opacity="{0.45 if dark else 0.2}">{p(ink, 1)}</g>'
            f'{p("#ff2e63", fr, "transform=\"translate(-1.5 0)\"")}{p("#2ee6ff", fr, "transform=\"translate(1.5 0)\"")}'
            f'{p(stroke, 0.85)}</g></svg>')

def burst(x0, x1, amp, seed, step=4, shape='noise'):
    r = random.Random(seed); pts = []
    mid, half = (x0 + x1) / 2, (x1 - x0) / 2
    for i, x in enumerate(range(int(x0), int(x1), step)):
        env = 1 - abs(x - mid) / half
        if shape == 'noise':
            y = r.uniform(-amp, amp) * env
        elif shape == 'sine':
            y = amp * env * math.sin((x - x0) / 5.0)
        elif shape == 'square':
            y = (amp * 0.8 if (i // 2) % 2 else -amp * 0.8) * (1 if env > 0.2 else 0)
        pts.append((x, Y + y))
    return pts

def line(*segs):
    pts = [(0, Y)]
    for s in segs:
        pts += s
    pts.append((W, Y))
    return 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)

def ecg(x):
    return [(x, Y), (x + 6, Y - 2), (x + 10, Y), (x + 14, Y), (x + 17, Y + 4), (x + 21, Y - 11), (x + 25, Y + 8), (x + 29, Y), (x + 38, Y), (x + 44, Y - 3), (x + 50, Y)]

for n in ('dark', 'light'):
    open(os.path.join(HERE, f'divider-{n}.svg'), 'w').write(wrap(n, path_d=line(burst(60, 160, 6, 0, step=4, shape='square'))) + '\n')
print('ok')
