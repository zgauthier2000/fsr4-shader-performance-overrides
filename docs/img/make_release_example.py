#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# make_release_example.py <dir> [<settings.json>] : release-example.png, the front page's example of what the current release improves most
# visibly over the one before it. <dir> holds test-rig output (4K, RGBA16F) of one scene in <scene>_amd/, <scene>_rel/ (the previous
# release's lossy build) and <scene>_new/ (this release's), output_3840x2160_f<frame>.raw, and the true image <scene>_truth_<frame>.npy.
# settings.json (default <dir>/release-example.json; the current release's is docs/img/release-example.json): scene, frame, the crop (x, y, w, h, zoom), title, subtitle, panel labels, and the
# error figures printed under the panels (measured by the rig's metric in the area it measures; the script also prints the crop's own
# mean error for reference). Top row: the pictures; bottom row: each build's error against the true image, amplified 16 times.
import json, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

D = sys.argv[1]; J = json.load(open(sys.argv[2] if len(sys.argv) > 2 else f'{D}/release-example.json'))
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


s, n, x, y, w, h, z = J['scene'], J['frame'], J['x'], J['y'], J['w'], J['h'], J['zoom']
cut = lambda a: a[y:y + h, x:x + w]
up = lambda a: np.repeat(np.repeat(a, z, 0), z, 1)
rgb8 = lambda a: (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
truth = srgb(np.load(f'{D}/{s}_truth_{n:03d}.npy'))
out = {k: srgb(np.fromfile(f'{D}/{s}_{k}/output_3840x2160_f{n:03d}.raw', dtype=np.float16).reshape(H, W, 4)[:, :, :3]) for k in ('amd', 'rel', 'new')}
pics = [(J['labels']['truth'], rgb8(up(cut(truth))))] + [(f"{J['labels'][k]}: {J['err'][k]:.2f}", rgb8(up(cut(out[k])))) for k in ('amd', 'rel', 'new')]
errs = [None] + [(J['labels'][k], np.repeat(rgb8(up(np.clip(np.abs(cut(out[k]) - cut(truth)).mean(2) * 16, 0, 1)))[:, :, None], 3, 2)) for k in ('amd', 'rel', 'new')]
for k in ('amd', 'rel', 'new'):
    print(k, 'mean error in the whole crop, of 255: %.2f' % (np.abs(cut(out[k]) - cut(truth)).mean() * 255))

pw, ph = w * z, h * z; gap, m = 16, 32; nc = 4
top = 118 + 30 * J['sub'].count('\n')
im = Image.new('RGB', (2 * m + nc * pw + (nc - 1) * gap, top + 2 * (ph + 78) + 8), BG); d = ImageDraw.Draw(im)
d.text((m, 24), J['title'], font=font(32), fill=INK); d.multiline_text((m, 70), J['sub'], font=font(22), fill=MUTED, spacing=8)
yy = top
for row, lab in ((pics, ''), (errs, 'Error against the true image, amplified 16 times')):
    d.text((m, yy), lab, font=font(22), fill=INK)
    for i, p in enumerate(row):
        if p is None:
            continue
        xx = m + i * (pw + gap); im.paste(Image.fromarray(p[1]), (xx, yy + 34))
        d.text((xx, yy + 34 + ph + 6), p[0], font=font(20), fill=INK if i == 3 else MUTED)
    yy += ph + 78
im.save('release-example.png', optimize=True); print('release-example.png', im.size)
