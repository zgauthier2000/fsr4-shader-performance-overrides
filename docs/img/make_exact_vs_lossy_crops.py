#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_exact_vs_lossy_crops.py <dir>: the pictures of docs/exact-vs-lossy.md from release dll-2026-10-29 on (evl-*.png): pieces of the test rig's
# 4K Balanced output (research/pruning: fsr4img with gen_inputs.py / gen_motion.py, 40 frames, the last 8 kept) with four panels each: the true
# image, the exact DLL (the same bytes as AMD's FSR 4.1.1 file, so also AMD's picture), the old lossy build (untrained, release dll-2026-10-22)
# and this release's lossy build (the former lossy2, trained further). Each piece is the one where THIS release's lossy differs most from the exact
# DLL (inside the scene's measured part where it has one), so the pictures show its largest differences, not a typical part of the frame.
# <dir> holds <scene>_<fsr4|old|rlossy>/output_3840x2160_fNNN.raw (RGBA16F) and <scene>_truth.npy / masks, as written by the comparison runs.
# make_comparison_crops.py made this page's pictures up to release dll-2026-10-22 (the old lossy against its predecessors).
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

D = sys.argv[1]
WW, HH = 3840, 2160
BG, INK, MUTED, ORANGE = (26, 26, 25), (255, 255, 255), (195, 194, 183), (255, 176, 102)
KEYS = ['fsr4', 'old', 'rlossy']
NAMES = {'fsr4': "exact (= AMD's)", 'old': 'old lossy (dll-2026-10-22)', 'rlossy': 'lossy, this release'}
FULL = (200, 200, WW - 200, HH - 200)


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


def load(scene, k, n):
    return srgb(np.fromfile(f'{D}/{scene}_{k}/output_3840x2160_f{n:03d}.raw', dtype=np.float16).reshape(HH, WW, 4)[:, :, :3])


def box(a, kh, kw):
    c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
    return (c[kh:, kw:] - c[:-kh, kw:] - c[kh:, :-kw] + c[:-kh, :-kw]) / kh / kw


def place(score, kh, kw, area, mk=None):
    """top-left corner of the kw x kh piece inside area with the largest mean score (centered on the measured part when there is a mask)"""
    x0, y0, x1, y1 = area
    s = box(score, kh, kw)[y0:y1 - kh, x0:x1 - kw]; y, x = np.unravel_index(np.argmax(s), s.shape); y += y0; x += x0
    if mk is not None:
        ys, xs = np.nonzero(mk[y:y + kh, x:x + kw])
        if len(ys):
            y = int(np.clip(y + ys.mean() - kh / 2, 0, HH - kh)); x = int(np.clip(x + xs.mean() - kw / 2, 0, WW - kw))
    return x, y


def sheet(rows, title, sub, pw, ph, name):
    """rows: lists of 4 panels (label, uint8 image, ours) or None"""
    gap, m = 14, 28
    top = 112 + 28 * sub.count('\n')
    im = Image.new('RGB', (2 * m + 4 * pw + 3 * gap, top + len(rows) * (ph + 44) + 8), BG); d = ImageDraw.Draw(im)
    d.text((m, 22), title, font=font(30), fill=INK); d.multiline_text((m, 66), sub, font=font(20), fill=MUTED, spacing=8)
    for r, row in enumerate(rows):
        for i, pnl in enumerate(row):
            if pnl is None:
                continue
            pl, a, ours = pnl
            px, py = m + i * (pw + gap), top + r * (ph + 44)
            im.paste(Image.fromarray(a), (px, py)); d.text((px, py + ph + 6), pl, font=font(20), fill=ORANGE if ours else MUTED)
    im.save(name, optimize=True)
    print(name, im.size)


def crops(scene, title, sub, name, kw=130, kh=80, z=4, frame=37, area=FULL, mask=None, shade=False, gain=1.0, amp=16, only_changed=False):
    tru = srgb(np.load(f'{D}/{scene}_truth.npy').astype(np.float32))
    out = {k: load(scene, k, frame) for k in KEYS}
    mk = np.load(f'{D}/{mask}.npy').astype(bool) if mask else None
    score = np.abs(out['rlossy'] - out['fsr4']).mean(2)
    if only_changed:
        score = score * (np.abs(tru - srgb(np.load(f'{D}/still_truth.npy').astype(np.float32))).mean(2) > 0.02)
    if mk is not None:
        score = score * mk
    x, y = place(score, kh, kw, area, mk)
    c = lambda a: a[y:y + kh, x:x + kw]
    dim = np.where(c(mk), 1.0, 0.4)[:, :, None] if (mk is not None and shade) else 1.0
    pic = lambda a: (np.clip(np.repeat(np.repeat(c(a) * dim, z, 0), z, 1) * gain, 0, 1) * 255 + 0.5).astype(np.uint8)
    e = {k: np.abs(c(out[k]) - c(tru)).mean(2) * (c(mk) if mk is not None else 1) for k in KEYS}
    err = lambda k: (e[k][c(mk)] if mk is not None else e[k]).mean() * 255
    emap = lambda k: np.repeat((np.clip(np.repeat(np.repeat(e[k] * amp, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)[:, :, None], 3, 2)
    print(name, 'window', x, y, ' | '.join(f'{k} {err(k):.2f}' for k in KEYS))
    lab = f'error x{amp}' + (', measured part' if mk is not None else '')
    sheet([[('true image', pic(tru), False)] + [(f'{NAMES[k]}: {err(k):.1f}', pic(out[k]), k == 'rlossy') for k in KEYS],
           [None] + [(lab, emap(k), k == 'rlossy') for k in KEYS]], title, sub, kw * z, kh * z, name)


def changemap(scene, title, sub, name, kw=200, kh=125, z=2, gain=120, f0=36, f1=37):
    """how much each pixel changes from frame f0 to f1, as maps; the piece where this release's lossy differs most from the exact DLL in that change"""
    ch = {k: np.abs(load(scene, k, f1) - load(scene, k, f0)).mean(2) for k in KEYS}
    x, y = place(np.abs(ch['rlossy'] - ch['fsr4']), kh, kw, FULL)
    c = lambda a: a[y:y + kh, x:x + kw]
    tru = load(scene, 'fsr4', f1)
    pic = lambda a: (np.clip(np.repeat(np.repeat(a, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)
    mp = lambda a: np.repeat(pic(np.clip(c(a) * gain, 0, 1))[:, :, None], 3, 2)
    print(name, 'window', x, y, ' | '.join(f'{k} {c(ch[k]).mean() * 255:.3f}' for k in KEYS), '| whole frame', ' '.join(f'{k} {ch[k].mean() * 255:.3f}' for k in KEYS))
    sheet([[('the picture (exact)', pic(c(tru)), False)] + [(f'{NAMES[k]}: {c(ch[k]).mean() * 255:.3f}', mp(ch[k]), k == 'rlossy') for k in KEYS]],
          title, sub, kw * z, kh * z, name)


def rain(name, kw=180, kh=117, z=3):
    RW, RH = 2260, 1272
    px0, px1, py0, py1 = 1120 + 24, (1120 + 2720) // 2 - 24, 480 + 24, 1680 - 24
    pan = srgb(np.load(f'{D}/rain_panel.npy').astype(np.float32))
    out = {k: load('rain', k, 39) for k in KEYS}
    over = {k: ((a.mean(2) - pan.mean(2)) * 255 > 20) for k, a in out.items()}
    x, y = place(np.abs(out['rlossy'] - out['old']).mean(2) + np.abs(out['rlossy'] - out['fsr4']).mean(2), kh, kw, (px0, py0, px1, py1))
    c = lambda a: a[y:y + kh, x:x + kw]
    pic = lambda a: (np.clip(np.repeat(np.repeat(a, z, 0), z, 1), 0, 1) * 255 + 0.5).astype(np.uint8)
    inp = srgb(np.fromfile(f'{D}/rain_input_039.raw', dtype=np.float16).reshape(RH, RW, 4)[:, :, :3])
    game = inp[(np.arange(y, y + kh) * RH // HH)][:, (np.arange(x, x + kw) * RW // WW)]
    gcount = int(((game.mean(2) - c(pan).mean(2)) * 255 > 20).sum())
    print(name, 'window', x, y, 'game', gcount, ' | '.join(f'{k} {int(c(over[k]).sum())}' for k in KEYS))
    sheet([[(f"the game's frame: {gcount}", pic(game), False)] + [(f'{NAMES[k]}: {int(c(over[k]).sum())}', pic(c(out[k])), k == 'rlossy') for k in KEYS]],
          'Rain drawn without motion vectors, on a skipped frame',
          'Faint streaks one rendered pixel wide falling fast over a dark surface, camera still, enlarged 3 times.\n'
          'Under each: pixels in this piece more than 20 of 255 brighter than the surface.', kw * z, kh * z, name)


if __name__ == '__main__':
    E = 'Under each picture: mean error against the true image in this piece, of 255.'
    EM = 'Under each picture: mean error against the true image in the measured part of this piece, of 255.'
    P = 'The piece where this release\'s lossy differs most from the exact DLL'
    crops('still', 'Still picture: fine detail', f'{P}, enlarged 4 times.\n{E} Below: each one\'s error, amplified 16 times.', 'evl-still.png')
    changemap('rest', 'Steadiness at rest: what changes from one frame to the next',
              f'A still picture. {P} in how much it changes, enlarged 2 times;\nthe maps show the change of each pixel, brightened 120 times. '
              'Under each: mean change in this piece, of 255. Darker is steadier.', 'evl-rest.png')
    changemap('grain', 'Film grain: what changes from one frame to the next',
              f'The still picture with random grain of 6 of 255 in every input frame. {P} in how much it changes,\nenlarged 2 times; '
              'maps brightened 30 times. Under each: mean change in this piece, of 255.', 'evl-grain.png', gain=30)
    crops('motion', 'Moving scene, a skipped frame: a thin railing',
          f'Camera panning, the railing moving the other way. {P} on the railing, enlarged 5 times.\n{EM} Below: the error in the railing, amplified 16 times.',
          'evl-motion.png', kw=104, kh=64, z=5, mask='motion_mask_rail')
    crops('stillcam', 'Just uncovered, camera still, a skipped frame',
          f'The camera is still and the objects move. {P} in what they have just uncovered,\nenlarged 5 times; the measured part at full brightness, the rest dimmed. {EM}',
          'evl-uncovered-still.png', kw=104, kh=64, z=5, mask='stillcam_mask', shade=True, amp=8)
    crops('ghost10', 'Old image beside a moving object, a skipped frame',
          f'Camera still, the object moving. Where its image of a frame ago would land: {P.lower()[4:]},\nenlarged 5 times; the measured part at full brightness, the rest dimmed. {EM}',
          'evl-ghost.png', kw=104, kh=64, z=5, mask='ghost10_mask', shade=True, amp=8)
    crops('bars', 'Thin bars fixed on screen in front of a moving background, a skipped frame',
          f'The bars stay in place, the background pans by 12 pixels per frame. Between the bars, where their image of a frame ago would land:\n'
          f'{P.lower()[4:]}, enlarged 4 times and brightened 3 times. {EM}', 'evl-bars.png', mask='bars_mask', gain=3)
    crops('plate', 'A still bright object over ground that moves fast, a skipped frame',
          f'The ground moves down by 100 pixels per frame; the white object stays where it is, at the same depth.\n{P} just below it, enlarged 2 times. {E}',
          'evl-plate.png', kw=208, kh=140, z=2, frame=39, area=(2300, 800, 3100, 1000), amp=8)
    crops('sparks', 'Tiny fast sparks drawn without motion vectors, a skipped frame', f'Camera still. {P}, enlarged 5 times. {E}',
          'evl-sparks.png', kw=104, kh=64, z=5, area=(250, 250, 1950, 1900), only_changed=True)
    crops('big', 'Large glowing particles drawn without motion vectors, a skipped frame', f'Camera still. {P}, enlarged 4 times. {E}',
          'evl-big.png', area=(250, 250, 1950, 1900), only_changed=True)
    crops('wirepan', 'A wire far thinner than a rendered pixel, camera panning slowly, a skipped frame', f'{P}, enlarged 4 times. {E}',
          'evl-wires.png', area=(250, 250, 1950, 1900), amp=8)
    crops('foliage', 'Leaves swaying without motion vectors, camera still, a skipped frame', f'{P}, enlarged 4 times. {E}',
          'evl-foliage.png', area=(300, 300, 1900, 1850), amp=4)
    # rain('evl-rain.png'): not on the page (0 pixels standing out for all three in the faint-rain scene; the page gives the counts)
