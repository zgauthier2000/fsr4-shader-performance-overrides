# SPDX-License-Identifier: GPL-2.0-or-later
# fade.py <scene dir> <label> : the picture's brightness changes with nothing moving (gen_inputs.py with SCENE_FADE). Kept frames in the current folder. Per class of area
# (inside the box if there is one, 24 pixels from its edge): how far the output's brightness is behind the true one. Ramp: in frames; step: share of the step still missing.
import sys, glob, os, numpy as np
d, label = sys.argv[1], sys.argv[2]; W, H = 3840, 2160
srgb = lambda x: (lambda x: np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055))(np.clip(x.astype(np.float32), 0, 1))
tl = np.load(d + '/truth.npy').astype(np.float32); lum = srgb(tl).mean(2); mul = [float(x) for x in open(d + '/fade.txt').read().split()]
fe = open(d + '/fade.env').read().split('\n'); fade = fe[0].split(); box = [int(x) for x in fe[1].split()] if fe[1].strip() else None
g = np.abs(np.diff(lum, axis=0, prepend=lum[:1])) + np.abs(np.diff(lum, axis=1, prepend=lum[:, :1])); flat = g < np.percentile(g, 50); fine = g > np.percentile(g, 90)
inb = np.ones((H, W), bool)
if box: inb[:] = False; inb[box[1] + 24:box[3] - 24, box[0] + 24:box[2] - 24] = True
areas = (('bright flat', (lum > 0.8) & flat & inb), ('mid flat', (lum > 0.3) & (lum < 0.8) & flat & inb), ('dark flat', (lum < 0.3) & flat & inb), ('fine detail', fine & inb))
fs = sorted(glob.glob('output_3840x2160_f*.raw')); res = {a: [] for a, _ in areas}; err = {a: [] for a, _ in areas}
step = len(fade) > 2; rate = float(fade[1])
for f in fs:
    n = int(f[-7:-4]); o = np.fromfile(f, dtype=np.float16).reshape(H, W, 4)[:, :, :3].astype(np.float32)
    if n < int(fade[0]): continue
    for a, m in areas:
        R = o[m].mean() / tl[m].mean()
        res[a].append((R - mul[n]) / (-rate) if step else np.log(R / mul[n]) / (-np.log(1 + rate)))
        err[a].append(np.abs(srgb(o[m]) - srgb(tl[m] * mul[n])).mean() * 255)
pick = (lambda v: ' '.join(f'{x:.2f}' for x in v[:8])) if step else (lambda v: f'{np.mean(v[-4:]):5.2f}')
print(f'{label:9s} ' + ' | '.join(f'{a}: {pick(res[a])} (err {np.mean(err[a][-4:]):.2f})' for a, _ in areas))
