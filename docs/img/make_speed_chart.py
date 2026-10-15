#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_speed_chart.py <settings.json> : the "speed" chart of a release (docs/img/release-<tag>.json, key "speed": title, sub, note, sizes, series)
#   -> rel-<date>-speed-light.svg / -dark.svg: grouped bars, one group per output size, one bar per build, with the value above each bar.
import json, sys
J = json.load(open(sys.argv[1])); S = J['speed']; STEM = 'rel-' + J['tag'].removeprefix('dll-')
def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
for dark in (False, True):
    bg, ink, muted, grid = ('#0d1117', '#e6edf3', '#9198a1', '#30363d') if dark else ('#ffffff', '#1f2328', '#59636e', '#d1d9e0')
    cols = ['#8b949e', '#d4a72c', '#2f81f7'] if dark else ['#6e7781', '#bf8700', '#0969da']
    W, H, L, T, B = 900, 420, 60, 110, 70
    top = max(v for _, vs in S['series'] for v in vs) * 1.15; ch = H - T - B
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="{bg}"/>',
         f'<text x="{L}" y="32" font-size="20" font-weight="700" fill="{ink}">{esc(S["title"])}</text>',
         f'<text x="{L}" y="58" font-size="14" fill="{ink}">{esc(S["sub"])}</text>',
         f'<text x="{L}" y="80" font-size="12" fill="{muted}">{esc(S["note"])}</text>']
    gw = (W - L - 30) / len(S['sizes']); bw = gw * 0.8 / len(S['series'])
    o.append(f'<line x1="{L}" y1="{T + ch}" x2="{W - 30}" y2="{T + ch}" stroke="{grid}"/>')
    for i, sz in enumerate(S['sizes']):
        x0 = L + i * gw + gw * 0.1
        for j, (name, vs) in enumerate(S['series']):
            h = vs[i] / top * ch; x = x0 + j * bw
            o.append(f'<rect x="{x:.1f}" y="{T + ch - h:.1f}" width="{bw - 4:.1f}" height="{h:.1f}" fill="{cols[j]}"/>')
            o.append(f'<text x="{x + (bw - 4) / 2:.1f}" y="{T + ch - h - 6:.1f}" font-size="13" text-anchor="middle" fill="{ink}">{vs[i]:.2f}</text>')
        o.append(f'<text x="{L + i * gw + gw / 2:.1f}" y="{T + ch + 22}" font-size="15" text-anchor="middle" fill="{ink}">{esc(sz)} output</text>')
    lx = L
    for j, (name, _) in enumerate(S['series']):
        o.append(f'<rect x="{lx}" y="{H - 26}" width="12" height="12" fill="{cols[j]}"/><text x="{lx + 18}" y="{H - 16}" font-size="13" fill="{ink}">{esc(name)}</text>')
        lx += 30 + 7.2 * len(name)
    o.append('</svg>')
    f = f"{STEM}-speed-{'dark' if dark else 'light'}.svg"; open(f, 'w').write('\n'.join(o) + '\n'); print(f)
