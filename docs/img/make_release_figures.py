#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_release_figures.py <dir> <settings.json> : the pictures of a release's page in docs/releases (the first sheet is also the front page's example).
# <dir> holds test-rig output (4K, RGBA16F) of each scene in <scene>_amd/, <scene>_rel/ (the previous release's lossy build) and <scene>_new/
# (this release's), output_3840x2160_f<frame>.raw, and the true image <scene>_truth_<frame>.npy (linear RGB).
# settings.json (docs/img/release-<tag>.json): "tag", "sheets" and "fades".
#   Each sheet -> rel-<date>-<name>.png: scene, frame, the crop (x, y, w, h, zoom, optional bright), title, subtitle, the caption under each
#   picture (truth, amd, rel, new; figures as the rig's metric measured them), and "err": true for a second row with each build's error
#   against the true image, amplified 16 times. The script prints each crop's own mean error for reference.
#   "fades" -> rel-<date>-fades-light.svg / -dark.svg: frames behind per frame for AMD, the previous release and this one, one chart per fade.
import json, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

D = sys.argv[1]; J = json.load(open(sys.argv[2])); STEM = 'rel-' + J['tag'].removeprefix('dll-')
W, H = 3840, 2160
BG, INK, MUTED = (26, 26, 25), (255, 255, 255), (195, 194, 183)


def font(size):
    for p in ('/usr/share/fonts/TTF/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def srgb(x):
    x = np.clip(x.astype(np.float32), 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def sheet(S):
    s, n, x, y, w, h, z, br = S['scene'], S['frame'], S['x'], S['y'], S['w'], S['h'], S['zoom'], S.get('bright', 1.0)
    cut = lambda a: a[y:y + h, x:x + w]
    up = lambda a: np.repeat(np.repeat(a, z, 0), z, 1)
    rgb8 = lambda a: (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    truth = srgb(np.load(f'{D}/{s}_truth_{n:03d}.npy')[:, :, :3])
    out = {k: srgb(np.fromfile(f'{D}/{s}_{k}/output_3840x2160_f{n:03d}.raw', dtype=np.float16).reshape(H, W, 4)[:, :, :3]) for k in ('amd', 'rel', 'new')}
    cap = S['cap']
    rows = [[(cap['truth'], rgb8(up(cut(truth) * br)))] + [(cap[k], rgb8(up(cut(out[k]) * br))) for k in ('amd', 'rel', 'new')]]
    if S.get('err'):
        rows.append([None] + [(cap[k].split(':')[0], np.repeat(rgb8(up(np.abs(cut(out[k]) - cut(truth)).mean(2) * 16))[:, :, None], 3, 2)) for k in ('amd', 'rel', 'new')])
    for k in ('amd', 'rel', 'new'):
        print(' ', S['name'], k, 'mean error in the whole crop, of 255: %.2f' % (np.abs(cut(out[k]) - cut(truth)).mean() * 255))
    pw, ph = w * z, h * z; gap, m = 16, 32
    top = 118 + 30 * S['sub'].count('\n')
    im = Image.new('RGB', (2 * m + 4 * pw + 3 * gap, top + len(rows) * (ph + 78) + 8), BG); d = ImageDraw.Draw(im)
    d.text((m, 24), S['title'], font=font(32), fill=INK); d.multiline_text((m, 70), S['sub'], font=font(22), fill=MUTED, spacing=8)
    yy = top
    for r, row in enumerate(rows):
        d.text((m, yy), '' if r == 0 else 'Error against the true image, amplified 16 times', font=font(22), fill=INK)
        for i, p in enumerate(row):
            if p is None:
                continue
            xx = m + i * (pw + gap); im.paste(Image.fromarray(p[1]), (xx, yy + 34))
            d.text((xx, yy + 34 + ph + 6), p[0], font=font(20), fill=INK if i == 3 else MUTED)
        yy += ph + 78
    f = f"{STEM}-{S['name']}.png"; im.save(f, optimize=True); print(f, im.size)


def fades(F, dark):
    c = dict(bg='#1c1f22', ink='#e8e8e4', muted='#a2a8ab', rule='#33383c', amd='#7cb6d4', rel='#9aa2ad', new='#f0a050') if dark else \
        dict(bg='#ffffff', ink='#1d2124', muted='#5d6468', rule='#dcdcd6', amd='#2f6f8f', rel='#6b7280', new='#b45309')
    fr, kinds, lab, (lo, hi) = F['frames'], F['kinds'], F['labels'], F['range']
    cw, ch_, l, t, gw = 420, 280, 46, 34, 24
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {2 * cw + gw} {ch_ + 56}" width="{2 * cw + gw}" font-family="DejaVu Sans, sans-serif">',
         f'<rect width="100%" height="100%" fill="{c["bg"]}"/>']
    for j, ch in enumerate(F['charts']):
        ox = j * (cw + gw)
        px = lambda i: ox + l + i * (cw - l - 14) / (len(fr) - 1)
        py = lambda v: t + (hi - v) / (hi - lo) * (ch_ - t - 40)
        o.append(f'<text x="{ox + l}" y="20" font-size="15" font-weight="bold" fill="{c["ink"]}">{ch["title"]}</text>')
        for v in F['ticks']:
            o.append(f'<line x1="{ox + l}" x2="{ox + cw - 14}" y1="{py(v):.1f}" y2="{py(v):.1f}" stroke="{c["rule"]}"/>'
                     f'<text x="{ox + l - 6}" y="{py(v) + 4:.1f}" font-size="11" text-anchor="end" fill="{c["muted"]}">{v}</text>')
        for i, (f_, k) in enumerate(zip(fr, kinds)):
            o.append(f'<text x="{px(i):.1f}" y="{ch_ - 16}" font-size="11" text-anchor="middle" fill="{c["muted"]}">{f_}</text>'
                     f'<text x="{px(i):.1f}" y="{ch_}" font-size="11" text-anchor="middle" fill="{c["muted"]}">{k}</text>')
        for k, dash, sw in (('amd', '', 2), ('rel', ' stroke-dasharray="5 4"', 2), ('new', '', 2.5)):
            o.append(f'<polyline points="{" ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(ch[k]))}" fill="none" stroke="{c[k]}" stroke-width="{sw}"{dash}/>')
            o += [f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="4" fill="{c[k]}" stroke="{c["bg"]}" stroke-width="1.5"/>' for i, v in enumerate(ch[k])]
    lx = l
    for k in ('amd', 'rel', 'new'):
        o.append(f'<rect x="{lx}" y="{ch_ + 28}" width="12" height="12" rx="2" fill="{c[k]}"/><text x="{lx + 18}" y="{ch_ + 39}" font-size="13" fill="{c["ink"]}">{lab[k]}</text>')
        lx += 40 + 8 * len(lab[k])
    o.append(f'<text x="{2 * cw + gw - 14}" y="{ch_ + 39}" font-size="12" text-anchor="end" fill="{c["muted"]}">r = runs the network, s = skipped</text></svg>')
    f = f"{STEM}-fades-{'dark' if dark else 'light'}.svg"; open(f, 'w').write('\n'.join(o) + '\n'); print(f)


for S in J['sheets']:
    sheet(S)
if 'fades' in J:
    fades(J['fades'], False); fades(J['fades'], True)
