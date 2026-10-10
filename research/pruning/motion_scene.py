# SPDX-License-Identifier: GPL-2.0-or-later
# The moving test scene shared by gen_motion.py and metric_motion.py. All positions are in output
# (3840x2160) pixels and all speeds in output pixels per frame, whole numbers, so that a point of
# the scene lands on a pixel center in every frame and frames can be compared exactly.
import numpy as np

import os
OW, OH, RW, RH = (int(x) for x in os.environ.get('SCENE', '3840 2160 2260 1272').split())
S = OW / 3840                  # the 4K scene scaled to the output size
_s = lambda *v: tuple(int(round(x * S)) for x in v)
PAD = int(os.environ.get('SCENE_PAD', '384'))   # mirror padding of the background, room for the pan
VB = tuple(int(x) for x in os.environ.get('SCENE_VB', '4 2').split())   # the camera pans: the background moves by -VB on screen each frame
VO = tuple(int(x) for x in os.environ.get('SCENE_VO', '-5 3').split())   # the foreground objects move by VO on screen each frame
BLOCK = _s(2300, 300, 800, 560)  # solid textured block: x, y, w, h at frame 0
RAIL = _s(2300, 1000, 900, 420)  # railing: thin bars with see-through gaps
BAR_W, BAR_STEP = max(1, int(round(3 * S))), int(round(24 * S))        # bar width and spacing
DEPTH_BG, DEPTH_FG = (float(x) for x in os.environ.get('SCENE_DEPTH', '0.9 0.3').split())   # depth of the background and of the objects


NP = int(os.environ.get('SCENE_PARTICLES', '0'))   # bright dots drawn into the color only: no motion vectors, no depth (like game particles)
PVEL = int(os.environ['SCENE_PVEL']) if os.environ.get('SCENE_PVEL') else None
PRAD = tuple(float(x) for x in os.environ.get('SCENE_PRAD', '1 2').split())
PGLOW = tuple(float(x) for x in os.environ['SCENE_PGLOW'].split()) if os.environ.get('SCENE_PGLOW') else None
PBOX = _s(250, 250, 1700, 1650)                    # where they fly, clear of the block and the railing


def particles(t):
    """(x, y, radius, brightness) of every particle at frame t, in output pixels; whole-number speeds, wrapping inside PBOX."""
    r = np.random.default_rng(7)
    x0 = r.integers(0, PBOX[2], NP); y0 = r.integers(0, PBOX[3], NP)
    vx = r.integers(-9, 10, NP); vy = r.integers(-9, 10, NP); vx[(vx == 0) & (vy == 0)] = 5
    rad = r.integers(3, 8, NP) * max(S, 0.5); br = r.uniform(0.6, 1.0, NP)
    if PVEL is not None:      # slow embers: SCENE_PVEL = highest speed, SCENE_PRAD = "smallest largest" radius (output pixels)
        vx = r.integers(-PVEL, PVEL + 1, NP); vy = r.integers(-PVEL, PVEL + 1, NP); rad = r.uniform(PRAD[0], PRAD[1], NP)
    return PBOX[0] + (x0 + vx * t) % PBOX[2], PBOX[1] + (y0 + vy * t) % PBOX[3], rad, br


def draw_particles(img, t):
    if not NP:
        return img
    for x, y, rad, br in zip(*particles(t)):
        k = int(3 * rad * (PGLOW[0] if PGLOW else 1)) + 1; ya, yb, xa, xb = max(0, y - k), min(OH, y + k + 1), max(0, x - k), min(OW, x + k + 1)
        yy, xx = np.mgrid[ya:yb, xa:xb]
        d2 = (xx - x) ** 2 + (yy - y) ** 2
        a = br * np.exp(-d2 / (2 * rad * rad))
        if PGLOW:      # a wide faint glow around the core (SCENE_PGLOW = "radius factor, strength")
            a = np.maximum(a, br * PGLOW[1] * np.exp(-d2 / (2 * (rad * PGLOW[0]) ** 2)))
        a = a[..., None].astype(np.float32)
        img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - a) + np.float32([1.0, 0.75, 0.35]) * a
    return img


# foliage: many small dark leaves over the background, fixed to the scene (they pan with the camera, so the background's motion
# vectors are right for them), each swaying a few whole pixels around its place with no motion vectors of its own, as wind-animated
# foliage often has in games. SCENE_FOLIAGE = "count amplitude period": amplitude in output pixels (0 = still leaves), period in frames.
FOL = tuple(float(x) for x in os.environ['SCENE_FOLIAGE'].split()) if os.environ.get('SCENE_FOLIAGE') else None
FBOX = _s(250, 250, 1700, 1650)


def leaves(t):
    """(x, y, radius a, radius b, shade) of every leaf at frame t, on screen, in output pixels (whole numbers for x, y)."""
    n, amp, per = int(FOL[0]), FOL[1], max(FOL[2], 1.0)
    r = np.random.default_rng(11)
    x0 = r.integers(0, FBOX[2], n); y0 = r.integers(0, FBOX[3], n)
    ra = r.uniform(1.5, 5.0, n) * max(S, 0.5); rb = ra * r.uniform(0.35, 0.8, n); sh = r.uniform(0.0, 1.0, n)
    ph = r.uniform(0, 2 * np.pi, n); ax = r.uniform(0.4, 1.0, n) * amp; ay = r.uniform(0.0, 0.5, n) * amp
    sx = np.rint(ax * np.sin(2 * np.pi * t / per + ph)).astype(int); sy = np.rint(ay * np.sin(2 * np.pi * t / per + ph + 1.3)).astype(int)
    return FBOX[0] + x0 - VB[0] * t + sx, FBOX[1] + y0 - VB[1] * t + sy, ra, rb, sh


def leaf_mask(t, grow=0):
    m = np.zeros((OH, OW), bool)
    for x, y, ra, rb, sh in zip(*leaves(t)):
        k = int(ra) + 1 + grow; m[max(0, y - k):max(0, y + k + 1), max(0, x - k):max(0, x + k + 1)] = True
    return m


def draw_foliage(img, t):
    if not FOL:
        return img
    # a bright sky behind the leaves, fixed to the scene like them: dark leaves against a bright sky is where foliage shimmers
    sx0, sy0 = FBOX[0] - VB[0] * t, FBOX[1] - VB[1] * t
    ya, yb, xa, xb = max(0, sy0), min(OH, sy0 + FBOX[3]), max(0, sx0), min(OW, sx0 + FBOX[2])
    if ya < yb and xa < xb:
        g = ((np.arange(ya, yb) - sy0) / FBOX[3]).astype(np.float32)[:, None, None]
        img[ya:yb, xa:xb] = np.float32([0.35, 0.50, 0.75]) * (1 - g) + np.float32([0.65, 0.72, 0.80]) * g
    for x, y, ra, rb, sh in zip(*leaves(t)):
        k = int(ra) + 2; ya, yb, xa, xb = max(0, y - k), min(OH, y + k + 1), max(0, x - k), min(OW, x + k + 1)
        if ya >= yb or xa >= xb:
            continue
        yy, xx = np.mgrid[ya:yb, xa:xb]
        d = np.sqrt(((xx - x) / ra) ** 2 + ((yy - y) / rb) ** 2)
        a = np.clip((1.0 - d) * min(ra, rb) + 0.5, 0, 1)[..., None].astype(np.float32)          # hard edge, one pixel of anti-aliasing
        col = np.float32([0.015, 0.05, 0.012]) * (1 - sh) + np.float32([0.08, 0.22, 0.04]) * sh
        img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - a) + col * a
    return img


def masks(t):
    """(block, bars, rail_box) boolean 4K masks at frame t."""
    yy, xx = np.mgrid[0:OH, 0:OW]
    ox, oy = VO[0] * t, VO[1] * t
    def box(b):
        return (xx >= b[0] + ox) & (xx < b[0] + ox + b[2]) & (yy >= b[1] + oy) & (yy < b[1] + oy + b[3])
    block = box(BLOCK)
    rb = box(RAIL)
    lx, ly = xx - (RAIL[0] + ox), yy - (RAIL[1] + oy)
    bars = rb & ((lx % BAR_STEP < BAR_W) | (ly < 2 * BAR_W) | (ly >= RAIL[3] - 2 * BAR_W))
    return block, bars, rb


def truth(world, t):
    """Linear RGB 4K image of frame t. world: the mirror-padded background."""
    x0, y0 = PAD + VB[0] * t, PAD + VB[1] * t
    img = world[y0:y0 + OH, x0:x0 + OW].copy()
    block, bars, _ = masks(t)
    ox, oy = VO[0] * t, VO[1] * t
    # block texture: another part of the picture, fixed to the block, with fine stripes on its right half
    by, bx = np.nonzero(block)
    ty, tx = by - (BLOCK[1] + oy), bx - (BLOCK[0] + ox)
    tex = world[PAD + int(1200 * S) + ty, PAD + int(400 * S) + tx]
    stripe = (tx >= BLOCK[2] // 2) & ((tx + ty) % 12 < 2)
    tex = np.where(stripe[:, None], np.float32(0.9), tex)
    img[by, bx] = tex
    img[bars] = np.float32([0.02, 0.02, 0.025])
    return draw_particles(draw_foliage(img, t), t)
