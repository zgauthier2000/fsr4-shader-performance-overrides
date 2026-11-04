#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes the four figures of docs/whats-moving.md, light and dark: wm-now, wm-path, wm-cards, wm-stats (from wm-stats.json).
from html import escape
THEMES = {
    'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', line='#c9c8c0', box='#f1f0ec', hi='#2a78d6', hibg='#e3eefb', hot='#eb6834', hotbg='#fdeae2'),
    'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', line='#45453f', box='#262624', hi='#3987e5', hibg='#1c2c40', hot='#d95926', hotbg='#3a2318'),
}
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
W = 760


def text(x, y, s, t, size=13, fill='ink2', anchor='start', weight=None):
    w = f' font-weight="{weight}"' if weight else ''
    return f'<text x="{x}" y="{y}" {FONT} font-size="{size}"{w} text-anchor="{anchor}" fill="{t[fill]}">{escape(s, quote=False)}</text>'


def box(x, y, w, h, t, fill='box', stroke='line'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{t[fill]}" stroke="{t[stroke]}"/>'


def arrow(x1, y1, x2, y2, t, col='muted'):
    dx = 7 if x2 > x1 else -7 if x2 < x1 else 0
    dy = 7 if y2 > y1 else -7 if y2 < y1 else 0
    tip = f'{x2},{y2} {x2 - dx - abs(dy) // 2 * 1},{y2 - dy - abs(dx) // 2 * 1} {x2 - dx + abs(dy) // 2 * 1},{y2 - dy + abs(dx) // 2 * 1}'
    return f'<line x1="{x1}" y1="{y1}" x2="{x2 - dx}" y2="{y2 - dy}" stroke="{t[col]}" stroke-width="1.5"/><polygon points="{tip}" fill="{t[col]}"/>'


def wrap(body, H, label, t):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(label)}">', f'<rect width="{W}" height="{H}" rx="8" fill="{t["surface"]}"/>'] + body + ['</svg>']


NOW = (('Tiled lossy (experiment only)', 'Not how released lossy builds work', 'slower on RX 6000 so far', 'Timing kit reports: RX 6000 cards'),
       ('Exact builds', "More speed, picture still AMD's, byte for byte", 'new speedups in the kit', 'Timing kit reports: RX 7600 and Steam Machine'),
       ('Small and handheld chips', 'Sizes between 1080p and 4K, and 800p', '800p now in the kit', 'Timing kit reports: handhelds and built-in graphics'),
       ('Lossy picture quality', 'Fewer twinkling specks in foliage', 'needs examples', 'Games and scenes where a lossy build looks wrong'),
       ('A cleaner Lite (early)', "Fixing weak spots of AMD's own FSR 4 Lite", 'one run at a time', "Games and scenes where AMD's Lite looks wrong"))


def now(t):
    o = [text(24, 32, 'Working on', t, 12, 'muted', weight=600), text(470, 32, 'What would help', t, 12, 'muted', weight=600)]
    y = 44
    for a, b, why, h in NOW:
        o += [box(24, y, 300, 62, t), text(38, y + 26, a, t, 14, 'ink', weight=600), text(38, y + 46, b, t, 11.5)]
        o += [arrow(324, y + 31, 470, y + 31, t), text(397, y + 23, why, t, 10.5, 'muted', 'middle')]
        o += [box(470, y, 266, 62, t, 'hibg', 'hi')]
        words = h.split(); l1 = ''
        while words and len(l1) + len(words[0]) < 34:
            l1 += words.pop(0) + ' '
        l2 = ' '.join(words)
        o += [text(484, y + (27 if l2 else 36), l1.strip(), t, 12.5, 'ink', weight=600)] + ([text(484, y + 45, l2, t, 12.5, 'ink', weight=600)] if l2 else [])
        y += 76
    return wrap(o, y + 6, 'Five parts being worked on, each with what would help: ' + '; '.join(f'{a}: {h}' for a, _, _, h in NOW), t)


STEPS = (('Idea', 'more speed or a', 'better picture', 0), ('Train', 'network runs on', 'one RX 7800 XT', 0), ('Test here', 'Linux only, on', 'the same card', 0), ('Timing kit', 'your PC, your', 'Windows or Linux', 1), ('Release', 'if the numbers', 'hold up', 0))
HELP = ((1, ('One GPU with 16 GB: one run at a time,', 'about an hour per run', '30 GB of system memory', 'Each setting needs several runs'), ('More GPU memory, a faster GPU,', 'more system memory')),
        (2, ('Linux and one card: no Windows or', 'RX 6000 timing here', 'Clips and data on one slow USB drive'), ('A Windows PC with Radeon, an', 'RX 6000 card, a bigger, faster drive')),
        (3, ('Only the cards people own and report', 'New tests reach the kit by itself,', 'then reports take time to arrive'), ('Your timing kit report,', 'from any card')))


def path(t):
    bw, gap, y0 = 128, 18, 74
    xs = [24 + i * (bw + gap) for i in range(5)]
    o = [text(24, 32, 'How an improvement gets to you, and what limits each step', t, 15, 'ink', weight=600)]
    for i, (a, b, c, hot) in enumerate(STEPS):
        o += [box(xs[i], y0, bw, 78, t, 'hibg' if hot else 'box', 'hi' if hot else 'line'), text(xs[i] + bw // 2, y0 + 26, a, t, 14, 'ink', 'middle', 600), text(xs[i] + bw // 2, y0 + 46, b, t, 11, 'ink2', 'middle'), text(xs[i] + bw // 2, y0 + 62, c, t, 11, 'ink2', 'middle')]
        if i < 4:
            o.append(arrow(xs[i] + bw, y0 + 39, xs[i + 1], y0 + 39, t))
    # results go back to the next idea
    yb = y0 - 10; xa, xb = xs[3] + bw // 2, xs[0] + bw // 2
    o += [f'<polyline points="{xa},{y0} {xa},{yb} {xb},{yb}" fill="none" stroke="{t["muted"]}" stroke-width="1.5"/>', arrow(xb, yb, xb, y0, t), text((xa + xb) // 2, yb - 5, 'results point to the next change', t, 10.5, 'muted', 'middle')]
    yh = y0 + 112
    hw = 228
    hx = [24, 266, 508]
    for (si, lim, helps), x in zip(HELP, hx):
        hot = si == 3
        o += [f'<polyline points="{xs[si] + bw // 2},{y0 + 78} {xs[si] + bw // 2},{yh - 14} {x + hw // 2},{yh - 14} {x + hw // 2},{yh}" fill="none" stroke="{t["hi" if hot else "hot"]}" stroke-width="1.5" stroke-dasharray="4 3"/>']
        o += [box(x, yh, hw, 158, t, 'hibg' if hot else 'hotbg', 'hi' if hot else 'hot'), text(x + 12, yh + 20, 'LIMITED BY', t, 10, 'ink2', weight=600)]
        o += [text(x + 12, yh + 38 + 16 * k, l, t, 11.5, 'ink') for k, l in enumerate(lim)]
        o += [text(x + 12, yh + 104, 'WOULD HELP', t, 10, 'ink2', weight=600)]
        o += [text(x + 12, yh + 122 + 17 * k, l, t, 11.5, 'ink', weight=600) for k, l in enumerate(helps)]
    return wrap(o, yh + 174, 'The path of an improvement: idea, training on one RX 7800 XT, testing here on Linux, the timing kit on testers\' PCs, release; kit results lead to the next change. Training is limited by one GPU with 16 GB, one run at a time at about an hour per run, 30 GB of system memory and several runs per setting; more GPU or system memory or a faster GPU would help. Testing here is limited to Linux and one card, with data on one slow USB drive; a Windows PC with Radeon, an RX 6000 card or a bigger, faster drive would help. The kit is limited to the cards people report, and reports take time to arrive after new tests reach the kit; your report helps.', t)


CARDS = (('RX 6000', 'current focus', ['every card, even if already reported'], 1), ('RX 7000', '', ['RX 7600', 'Steam Machine', 'RX 7700 XT', 'RX 7900 GRE', 'laptop chips'], 1),
         ('Built-in', '', ['780M', '760M', '880M', '680M', '660M'], 1), ('Handhelds', 'Windows or Linux', ['Steam Deck', 'ROG Ally', 'Legion Go'], 1),
         ('Older Radeon', '', ['RX 5000', 'Vega'], 1), ('Others', '', ['GeForce', 'Arc'], 1))


def cards(t):
    o = [text(24, 32, 'Timing kit reports most wanted', t, 15, 'ink', weight=600), text(24, 52, 'Each new kit tests new things, so a card already reported still helps.', t, 12)]
    y = 72
    for a, sub, chips, _ in CARDS:
        o += [text(24, y + 15 if sub else y + 19, a, t, 13, 'ink', weight=600)] + ([text(24, y + 30, sub, t, 10.5, 'muted')] if sub else [])
        x = 140
        for c in chips:
            w = int(7.1 * len(c)) + 24
            o += [f'<rect x="{x}" y="{y}" width="{w}" height="28" rx="14" fill="{t["hibg"]}" stroke="{t["hi"]}"/>', text(x + w // 2, y + 19, c, t, 12, 'ink', 'middle')]
            x += w + 8
        y += 40
    return wrap(o, y + 6, 'Reports most wanted: ' + '; '.join(f'{a}: ' + ', '.join(c) for a, _, c, _ in CARDS), t)


def fmt_b(b):
    return f'{b / 1e12:.1f} TB' if b >= 1e12 else f'{b / 1e9:.0f} GB'


def stats(t):
    # wm-stats.json: written by the author's local measuring scripts (disk use per drive, the job recorder's CPU / GPU / I/O totals); this only draws it
    import json, os
    s = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wm-stats.json')))
    o = [text(24, 32, 'What the project uses', t, 15, 'ink', weight=600), text(24, 52, f"Measured {s['date']} on the author's PC.", t, 12)]
    y = 76
    o += [text(24, y, 'DISK SPACE', t, 10, 'ink2', weight=600)]
    y += 16; R = 58; cxs = (140, 380, 620)
    import math
    def arc(cx, cy, a0, a1, col, stroke):
        if a1 - a0 >= 0.9999:
            return f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="{col}" stroke="{t[stroke]}" stroke-width="1.5"/>'
        p0 = (cx + R * math.sin(2 * math.pi * a0), cy - R * math.cos(2 * math.pi * a0)); p1 = (cx + R * math.sin(2 * math.pi * a1), cy - R * math.cos(2 * math.pi * a1))
        big = 1 if a1 - a0 > 0.5 else 0
        return f'<path d="M{cx},{cy} L{p0[0]:.1f},{p0[1]:.1f} A{R},{R} 0 {big} 1 {p1[0]:.1f},{p1[1]:.1f} Z" fill="{col}" stroke="{t["surface"]}" stroke-width="2"/>'
    for d, cx in zip(s['drives'], cxs):
        cap, proj, other = d['capacity'], d['project'], max(d['used'] - d['project'], 0)
        cy = y + R + 4; f1 = proj / cap; f2 = f1 + other / cap
        o += [f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="{t["surface"]}" stroke="{t["line"]}" stroke-width="1.5"/>', arc(cx, cy, f1, f2, t['box'], 'line'), arc(cx, cy, 0, f1, t['hi'], 'hi'), f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{t["line"]}" stroke-width="1.5"/>']
        o += [text(cx, cy + R + 24, d['name'], t, 12.5, 'ink', 'middle', 600), text(cx, cy + R + 41, f"{fmt_b(proj)} of {fmt_b(cap)} ({100 * f1:.0f}%)", t, 11.5, 'ink2', 'middle')]
    y += 2 * R + 60
    lx = 220
    o += [f'<rect x="{lx}" y="{y + 2}" width="14" height="10" fill="{t["hi"]}"/>', text(lx + 20, y + 11, 'this project', t, 10.5, 'ink2'),
          f'<rect x="{lx + 110}" y="{y + 2}" width="14" height="10" fill="{t["box"]}" stroke="{t["line"]}"/>', text(lx + 130, y + 11, 'other files', t, 10.5, 'ink2'),
          f'<rect x="{lx + 220}" y="{y + 2}" width="14" height="10" fill="{t["surface"]}" stroke="{t["line"]}"/>', text(lx + 240, y + 11, 'free space', t, 10.5, 'ink2')]
    y += 40
    tot = sum(d['project'] for d in s['drives'])
    o += [text(24, y, f"Total: {fmt_b(tot)}, backups included ({fmt_b(s['backup'])} of it).", t, 12.5, 'ink', weight=600)]
    if s.get('files'):
        o += [text(24, y + 20, f"{s['files']:,} files, not counting the backup copies.", t, 12.5, 'ink2')]
        y += 20
    if s.get('grew_week') is not None:
        o += [text(24, y + 20, f"Grew by about {fmt_b(s['grew_week'])} in the past 7 days ({fmt_b(s['grew_week_backup'])} of it backups).", t, 12.5, 'ink2')]
        y += 20
    y += 34
    o += [text(24, y, 'WORK DONE', t, 10, 'ink2', weight=600), text(470, y, 'Past 7 days', t, 11, 'muted', 'end', 600), text(W - 24, y, f"Since {s['since']}", t, 11, 'muted', 'end', 600)]
    rows = (('Processor time', lambda x: f"{x['cpu_s'] / 3600:,.0f} h"), ('Graphics card time', lambda x: f"{x['gpu_s'] / 3600:,.0f} h"),
            ('Data read', lambda x: f"{fmt_b(x['all_r'])} ({fmt_b(x['disk_r'])} from drives)"), ('Data written', lambda x: f"{fmt_b(x['all_w'])} ({fmt_b(x['disk_w'])} to drives)"))
    y += 10
    for i, (a, f) in enumerate(rows):
        o += [f'<line x1="24" y1="{y + 4}" x2="{W - 24}" y2="{y + 4}" stroke="{t["line"]}"/>', text(24, y + 25, a, t, 12.5, 'ink', weight=600),
              text(470, y + 25, f(s['week']), t, 12.5, 'ink', 'end'), text(W - 24, y + 25, f(s['all']), t, 12.5, 'ink', 'end')]
        y += 32
    y += 18
    for l in s['notes']:
        o += [text(24, y, l, t, 10.5, 'muted')]; y += 15
    lab = (f"What the project uses, measured {s['date']}: disk space " + '; '.join(f"{d['name']} {fmt_b(d['project'])} of {fmt_b(d['capacity'])}" for d in s['drives'])
           + f"; total {fmt_b(tot)} including {fmt_b(s['backup'])} of backups" + (f", {s['files']:,} files not counting backup copies" if s.get('files') else '') + (f"; grew about {fmt_b(s['grew_week'])} in the past 7 days" if s.get('grew_week') is not None else '')
           + f". Past 7 days: {s['week']['cpu_s'] / 3600:.0f} processor hours, {s['week']['gpu_s'] / 3600:.0f} graphics card hours, {fmt_b(s['week']['all_r'])} read, {fmt_b(s['week']['all_w'])} written."
           + f" Since {s['since']}: {s['all']['cpu_s'] / 3600:.0f} processor hours, {s['all']['gpu_s'] / 3600:.0f} graphics card hours, {fmt_b(s['all']['all_r'])} read, {fmt_b(s['all']['all_w'])} written.")
    return wrap(o, y + 4, lab, t)


if __name__ == '__main__':
    for n, f in (('wm-now', now), ('wm-path', path), ('wm-cards', cards), ('wm-stats', stats)):
        for k, t in THEMES.items():
            open(f'{n}-{k}.svg', 'w').write('\n'.join(f(t)) + '\n')
