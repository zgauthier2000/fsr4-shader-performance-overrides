#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes the graphs of docs/releases/dll-2026-11-22.md (light and dark): rel-2026-11-22-<name>-<theme>.svg
#   gains     the largest speed gains over dll-2026-11-05, 1440p (timing-kit reports, both builds in the same report, median per card)
#   lossy, llossy, lexact, exactdeck   speed against dll-2026-11-05 per card and size (same source)
#   clips     dark specks per frame in recorded game clips, dll-2026-11-05 -> this release (this project's test rig, 4K Balanced)
#   synthetic synthetic test scenes: change against dll-2026-11-05 per row, auto exposure off / on
# Data: rel-2026-11-22-data.json. Timing-kit figures: Windows unless the row says Linux; one report is one run.
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'rel-2026-11-22-data.json')))
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', zero='#898781',
                  exact=('#9cc0ec', '#2a78d6', '#1a4f91'), lossy=('#f5b291', '#eb6834', '#b0451a'), llossy=('#c9b3ee', '#8a5cd6', '#5b3399')),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', zero='#898781',
                 exact=('#1f4f8c', '#3987e5', '#9fc4f2'), lossy=('#7f3415', '#d95926', '#f2a37c'), llossy=('#4a2c80', '#9a6fe0', '#cdb6f4')),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W = 760
SZ = {'1280x800': '800p', '1920x1080': '1080p', '2560x1440': '1440p', '3840x2160': '4K'}


def text(x, y, s, t, size=12, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'


def rbar(x0, y, v, scale, h, col, t, lab, neg_word):
    """Bar from the zero line x0: positive to the right, negative to the left; label at its end."""
    w = abs(v) * scale
    if w < 1.5: w = 1.5
    if v >= 0:
        x, xl, an = x0, x0 + w + 5, 'start'
    else:
        x, xl, an = x0 - w, x0 - w - 5, 'end'
    return [f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{min(3, w / 2):.1f}" fill="{col}"/>',
            text(xl, y + h - 1.5, lab if v >= 0 else f'{lab} {neg_word}', t, 10.5, 'ink2', an)]


def frame(title, subtitle, H, t, aria):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{aria}">',
            f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>', text(24, 32, title, t, 16, 'ink', weight=600), text(24, 52, subtitle, t, 12)]


def axis(x0, scale, lo, hi, step, y_a, y_b, t, suffix='%', plus=True):
    o = []
    g = lo
    while g <= hi + 1e-9:
        x = x0 + g * scale
        o.append(f'<line x1="{x:.1f}" y1="{y_a}" x2="{x:.1f}" y2="{y_b}" stroke="{t["zero"] if g == 0 else t["grid"]}" stroke-width="1"/>')
        o.append(text(x, y_b + 14, (f'{g:+.0f}' if plus else f'{g:.0f}') + suffix if g else f'0{suffix}', t, 10, 'muted', 'middle'))
        g += step
    return o


def notes(o, lines, y, t):
    for k, l in enumerate(lines):
        o.append(text(24, y + 14 * k, l, t, 10, 'muted'))


# ---- the gains graph: one bar per row, 1440p
def gains(t):
    pick = [('lossy', 'RX 7700 XT, Windows'), ('lossy', 'RX 7900 XT, Windows'), ('lossy', 'RX 7900 XTX, Windows'), ('lossy', 'RX 7600, Windows'),
            ('lossy', 'RX 6000, Windows'), ('lossy', 'Radeon 880M, Windows'), ('llossy', 'RX 7700 XT, Windows'), ('lossy', 'Radeon 780M, Windows'),
            ('exact_deck', 'Steam Deck, SteamOS'), ('llossy', 'RX 6700 XT, Linux'), ('lexact', 'RX 7000, Windows')]
    name = {'lossy': 'lossy', 'llossy': '4.1.2l-lossy', 'lexact': '4.1.2l-exact', 'exact_deck': 'exact'}
    col = {'lossy': t['lossy'][1], 'llossy': t['llossy'][1], 'lexact': t['exact'][1], 'exact_deck': t['exact'][1]}
    rows = []
    for b, lab in pick:
        r = next(r for r in D['speed'][b] if r['label'] == lab)
        rows.append((b, r, r['sizes']['2560x1440']))
    rows.sort(key=lambda x: -x[2])
    X0, SC, RH = 340, 34, 26
    y0 = 104; H = y0 + RH * len(rows) + 64
    aria = 'Biggest speed gains over dll-2026-11-05 at 1440p: ' + '; '.join(f"{name[b]} on {r['label']} {v:.1f}% less time ({r['reports']} reports)" for b, r, v in rows) + '.'
    o = frame('Biggest speed gains over dll-2026-11-05, 1440p', 'How much less time FSR 4 takes per frame than with the same build of the last release. Longer is faster.', H, t, aria)
    lx = 24
    for b in ('lossy', 'llossy', 'exact_deck'):
        lab = {'lossy': 'lossy', 'llossy': '4.1.2l-lossy', 'exact_deck': 'exact / 4.1.2l-exact'}[b]
        o += [f'<rect x="{lx}" y="68" width="12" height="11" rx="3" fill="{col[b]}"/>', text(lx + 18, 78, lab, t, 11.5, 'ink', weight=600)]
        lx += 18 + 7.2 * len(lab) + 22
    o += axis(X0, SC, 0, 10, 2, y0 - 6, y0 + RH * len(rows), t)
    for i, (b, r, v) in enumerate(rows):
        y = y0 + i * RH
        rep = f"{r['reports']} report{'s' if r['reports'] != 1 else ''}"
        o += [text(24, y + 13, f"{name[b]}", t, 12, 'ink', weight=600), text(120, y + 13, f"{r['label']}", t, 12, 'ink2'),
              text(X0 - 10, y + 13, rep, t, 10, 'muted', 'end')]
        o += rbar(X0, y + 3, v, SC, 13, col[b], t, f'{v:.1f}%', 'slower')
    notes(o, ["Testers' timing-kit reports with both builds in the same report, moving scene, Balanced, median per card (RX 6000: six models pooled).",
              "Linux (Proton) speeds of lossy are about the same as before. Every card and size: the Speed section."], y0 + RH * len(rows) + 30, t)
    return o, H


# ---- speed per build: rows of up to three bars (one per size), zero line in the middle
def speed(key, title, hue, t, lo, hi, drop=(), dropnote=None):
    rows = [r for r in D['speed'][key] if r['label'] not in drop]
    SC = 300 / (hi - lo); X0 = 230 + (-lo) * SC
    y0 = 104; heights = [len(r['sizes']) * 13 + 12 for r in rows]; H = y0 + sum(heights) + 70 + (14 if dropnote else 0)
    aria = f'{title}: ' + '; '.join(f"{r['label']} ({r['reports']} reports): " + ', '.join(f"{SZ[s]} {'no report' if v is None else (f'{v:.1f}% less time' if v >= 0 else f'{-v:.1f}% more time')}" for s, v in r['sizes'].items()) for r in rows) + '.'
    o = frame(title, 'Time per frame against the same build of dll-2026-11-05. Right of the line: faster; left: slower.', H, t, aria)
    o.append(text(24, 78, 'One bar per output size, smallest first; each bar names its size.', t, 11, 'muted'))
    o += axis(X0, SC, lo, hi, 2 if hi - lo <= 16 else 4, y0 - 6, y0 + sum(heights) - 6, t)
    y = y0
    for r, h in zip(rows, heights):
        rep = f"{r['reports']} report{'s' if r['reports'] != 1 else ''}" + (f", {r['models']} models" if r['models'] > 1 else '')
        o += [text(24, y + 13, r['label'], t, 12, 'ink', weight=600), text(24, y + 27, rep, t, 10, 'muted')]
        for i, (s, v) in enumerate(r['sizes'].items()):
            shade = t[hue][i]
            if v is None:
                o.append(text(X0 + 4, y + 4 + i * 13 + 9, f'{SZ[s]}: no report', t, 10, 'muted'))
            else:
                o += rbar(X0, y + 4 + i * 13, v, SC, 10, shade, t, f'{SZ[s]} {abs(v):.1f}%', 'slower')
        y += h
    notes(o, ["Testers' timing-kit reports with both builds in the same report, moving scene, Balanced, median per row. Windows unless the row says Linux (Proton).",
              "The kit's test builds carry other weights than the release (same shaders, same speed). One report is one run."] + ([dropnote] if dropnote else []), y + 24, t)
    return o, H


# ---- game clips: dark specks per frame, old -> new, two panels
def clips(t):
    C = D['clips']; PA, PB, PW = 200, 470, 190
    mx = max(max(c['lossy']['dark'] + c['llossy']['dark']) for c in C); top = 200 * (int(mx / 200) + 1); sc = PW / top
    y0, RH = 120, 30; H = y0 + RH * len(C) + 74
    aria = 'Dark specks per frame in recorded game clips, dll-2026-11-05 to this release: ' + '; '.join(
        f"{c['clip']}: lossy {c['lossy']['dark'][0]:.0f} to {c['lossy']['dark'][1]:.0f}, 4.1.2l-lossy {c['llossy']['dark'][0]:.0f} to {c['llossy']['dark'][1]:.0f}" for c in C) + '.'
    o = frame('Dark specks in recorded game clips', 'Pixels per frame much darker than in AMD FSR 4.1.2\'s picture: dll-2026-11-05 (ring) to this release (dot). Lower is better.', H, t, aria)
    for x0, lab, hue in ((PA, 'lossy', 'lossy'), (PB, '4.1.2l-lossy', 'llossy')):
        o.append(text(x0, 86, lab, t, 13, 'ink', weight=600))
        for g in range(0, top + 1, 200 if top > 600 else 100):
            x = x0 + g * sc
            o += [f'<line x1="{x:.1f}" y1="{y0 - 8}" x2="{x:.1f}" y2="{y0 + RH * len(C) - 8}" stroke="{t["grid"]}" stroke-width="1"/>', text(x, y0 + RH * len(C) + 6, f'{g:,}', t, 10, 'muted', 'middle')]
    o += [f'<circle cx="30" cy="99" r="4.5" fill="none" stroke="{t["muted"]}" stroke-width="2"/>', text(40, 103, 'dll-2026-11-05', t, 11, 'ink2'),
          f'<circle cx="140" cy="99" r="4.5" fill="{t["ink2"]}"/>', text(150, 103, 'this release', t, 11, 'ink2')]
    for i, c in enumerate(C):
        y = y0 + i * RH + 4
        o.append(text(24, y + 4, c['clip'].replace('Shadow of the Tomb Raider', 'SOTTR').replace('Black Myth: Wukong', 'Wukong'), t, 11.5, 'ink', weight=600))
        for x0, k, hue in ((PA, 'lossy', 'lossy'), (PB, 'llossy', 'llossy')):
            a, b = c[k]['dark']; xa, xb = x0 + a * sc, x0 + b * sc; col = t[hue][1]
            o += [f'<line x1="{xa:.1f}" y1="{y}" x2="{xb:.1f}" y2="{y}" stroke="{col}" stroke-width="2"/>',
                  f'<circle cx="{xa:.1f}" cy="{y}" r="4.5" fill="{t["surface"]}" stroke="{col}" stroke-width="2"/>', f'<circle cx="{xb:.1f}" cy="{y}" r="4.5" fill="{col}"/>',
                  (text(max(xa, xb) + 9, y + 4, f'{a:,.0f} → {b:,.0f}', t, 10, 'ink2') if max(xa, xb) < x0 + PW - 40 else
                   text(min(xa, xb) - 9, y + 4, f'{a:,.0f} → {b:,.0f}', t, 10, 'ink2', 'end'))]
    notes(o, ["Ten recorded clips, 10 frames each, 4K Balanced, RX 7000 archive's DLLs on this project's test rig, one run each (the rig gives the same frames every run).",
              "SOTTR: Shadow of the Tomb Raider. White specks, closeness to AMD's picture: the table below. Display mapping is ours, not the game's."],
          y0 + RH * len(C) + 30, t)
    return o, H


# ---- synthetic scenes: % less (better) or more (worse) than dll-2026-11-05, auto exposure off / on
def synthetic(t):
    S = D['synthetic']; PA, PB, PW = 250, 520, 200; lo, hi = -100, 100; sc = PW / (hi - lo)
    def ch(o, n):
        if o is None or n is None: return None
        if o == 0: return 0.0 if n == 0 else -100.0
        return 100 * (o - n) / o
    y0, RH = 120, 34; H = y0 + RH * len(S) + 74
    aria = 'Synthetic test scenes, change against dll-2026-11-05 (positive = better), auto exposure off / on: ' + '; '.join(
        f"{s['row']}: lossy {ch(s['lossy_old'][0], s['lossy_new'][0]):+.0f}% / {ch(s['lossy_old'][1], s['lossy_new'][1]):+.0f}%, 4.1.2l-lossy {ch(s['llossy_old'][0], s['llossy_new'][0]):+.0f}% / {ch(s['llossy_old'][1], s['llossy_new'][1]):+.0f}%" for s in S) + '.'
    o = frame('Synthetic test scenes against dll-2026-11-05', 'How much lower (better, right of the line) or higher (worse, left) each figure is than with the last release.', H, t, aria)
    for x0, lab, hue in ((PA, 'lossy', 'lossy'), (PB, '4.1.2l-lossy', 'llossy')):
        o.append(text(x0, 86, lab, t, 13, 'ink', weight=600))
        z = x0 + (-lo) * sc
        for g in (-100, -50, 0, 50, 100):
            x = z + g * sc
            o += [f'<line x1="{x:.1f}" y1="{y0 - 6}" x2="{x:.1f}" y2="{y0 + RH * len(S) - 6}" stroke="{t["zero"] if g == 0 else t["grid"]}" stroke-width="1"/>',
                  text(x, y0 + RH * len(S) + 8, f'{g:+d}%' if g else '0', t, 10, 'muted', 'middle')]
        kx = x0
        for i, l in enumerate(('auto exposure off', 'on')):
            o += [f'<rect x="{kx}" y="94" width="11" height="10" rx="3" fill="{t[hue][1 + i]}"/>', text(kx + 15, 103, l, t, 10.5, 'ink2')]
            kx += 15 + 6.2 * len(l) + 14
    for i, s in enumerate(S):
        y = y0 + i * RH
        words = s['row'].split(', ')
        if len(words) == 1 and len(words[0]) > 28:
            cut = words[0].rfind(' ', 0, 26); words = [words[0][:cut]]; o.append(text(24, y + 25, s['row'][cut + 1:], t, 11.5, 'ink', weight=600))
        o.append(text(24, y + 11, words[0], t, 11.5, 'ink', weight=600))
        if len(words) > 1: o.append(text(24, y + 25, ', '.join(words[1:]), t, 10, 'muted'))
        for x0, k, hue in ((PA, 'lossy', 'lossy'), (PB, 'llossy', 'llossy')):
            z = x0 + (-lo) * sc; old, new = s[f'{k}_old'], s[f'{k}_new']
            if old is None:
                o.append(text(z + 4, y + 16, 'not measured', t, 10, 'muted')); continue
            for j in range(2):
                v = ch(old[j], new[j])
                if old[j] == 0 and new[j] == 0:
                    o.append(text(z + 4, y + 3 + j * 13 + 9, '0 → 0', t, 10, 'muted')); continue
                o += rbar(z, y + 3 + j * 13, max(lo, min(hi, v)), sc, 10, t[hue][1 + j], t, f'{abs(v):.0f}%', 'worse')
    notes(o, ["4K Balanced, this project's test rig. All rows: lower is better (frames, counts, change per frame). Bars stop at 100%.",
              "The figures themselves: the table below; full lists in each build's WARNING.txt. Synthetic scenes, not games."], y0 + RH * len(S) + 30, t)
    return o, H


# ---- one game: SOTTR benchmark, average FPS per build
def game(t):
    G = D['game']; X0, SC, RH = 290, 2.35, 30; MX = 160; y0 = 104; H = y0 + RH * len(G) + 20 + 78
    ref = {g['build']: g for g in G if g.get('ref')}
    col = {'exact': t['exact'][1], 'lossy': t['lossy'][1], '4.1.2l-exact': t['exact'][1], '4.1.2l-lossy': t['llossy'][1]}
    aria = ("Shadow of the Tomb Raider benchmark, 4K Balanced, this project's RX 7800 XT under Linux, one run each: " + '; '.join(
        f"{g['build']} {g['fps']} FPS, FSR {g['ms']:.2f} ms" + ('' if g.get('ref') else f" ({100 * (g['frames'] / ref[g['vs']]['frames'] - 1):+.1f}% frames against {g['vs']})") for g in G) + '.')
    o = frame("One game: Shadow of the Tomb Raider's benchmark", "This project's RX 7800 XT under Linux (Proton), 4K Balanced, average FPS. Longer is faster.", H, t, aria)
    lx = 24
    for c, lab in ((t['amd'] if 'amd' in t else t['muted'], "AMD's own (reference)"), (t['exact'][1], 'exact builds'), (t['lossy'][1], 'lossy'), (t['llossy'][1], '4.1.2l-lossy')):
        o += [f'<rect x="{lx}" y="68" width="12" height="11" rx="3" fill="{c}"/>', text(lx + 18, 78, lab, t, 11.5, 'ink2')]
        lx += 18 + 6.6 * len(lab) + 22
    o += axis(X0, SC, 0, 140, 20, y0 - 6, y0 + RH * len(G) + 14, t, '', False)
    o += [text(MX, y0 - 12, 'FSR time per frame', t, 10.5, 'muted'), text(X0, y0 - 12, 'average FPS', t, 10.5, 'muted')]
    y = y0
    for i, g in enumerate(G):
        if i == 3: y += 20
        c = t['muted'] if g.get('ref') else col[g['build']]
        o.append(text(24, y + 13, g['build'], t, 12, 'ink', weight=600))
        lab = f"{g['fps']} FPS" + ('' if g.get('ref') else f" ({100 * (g['frames'] / ref[g['vs']]['frames'] - 1):+.0f}%)")
        o += rbar(X0, y + 3, g['fps'], SC, 14, c, t, lab, '')
        o.append(text(MX, y + 13, f"{g['ms']:.2f} ms" + ('' if g.get('ref') else f" ({100 * (g['ms'] / ref[g['vs']]['ms'] - 1):+.0f}%)").replace('-', '−'), t, 11.5, 'ink2'))
        y += RH
    notes(o, ["One run each, DLSS 5 plugin off. FSR time per frame as the overlay shows it on the result screen (a still menu).",
              "% = frames rendered against AMD's own: exact and lossy against AMD's FSR 4.1.2 (SDK 2.4.0 DLL), the Lite builds against AMD's",
              "FSR 4.1.2 Lite (the same DLL set to Lite in OptiScaler). Windows not measured in this game; Linux gains do not carry over to Windows."], y + 30, t)
    return o, H


GRAPHS = {
    'game': game,
    'gains': gains,
    'lossy': lambda t: speed('lossy', 'lossy: speed against dll-2026-11-05', 'lossy', t, -4, 12),
    'llossy': lambda t: speed('llossy', '4.1.2l-lossy: speed against dll-2026-11-05', 'llossy', t, -6, 10, ('RX 7600, Windows',), 'Not shown: RX 7600, Windows (1 report), within 0.2% at every size: about the same.'),
    'lexact': lambda t: speed('lexact', '4.1.2l-exact: speed against dll-2026-11-05', 'exact', t, -4, 4, ('Steam Deck, Linux', 'Radeon 780M / 880M, Windows'), 'Not shown: Steam Deck, Linux (23 reports) and Radeon 780M / 880M, Windows (5 reports), within 0.4% at every size: about the same.'),
    'exactdeck': lambda t: speed('exact_deck', 'exact, Steam Deck archive: speed against dll-2026-11-05', 'exact', t, -4, 4),
    'clips': clips,
    'synthetic': synthetic,
}

if __name__ == '__main__':
    for n, f in GRAPHS.items():
        for th, t in THEMES.items():
            body, H = f(t)
            open(os.path.join(HERE, f'rel-2026-11-22-{n}-{th}.svg'), 'w').write('\n'.join(body + ['</svg>']) + '\n')
        print('wrote', n)
