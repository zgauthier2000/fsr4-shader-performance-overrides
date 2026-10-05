# SPDX-License-Identifier: GPL-2.0-or-later
# The moving test scene shared by gen_motion.py and metric_motion.py. All positions are in output
# (3840x2160) pixels and all speeds in output pixels per frame, whole numbers, so that a point of
# the scene lands on a pixel centre in every frame and frames can be compared exactly.
import numpy as np

OW, OH, RW, RH = 3840, 2160, 2260, 1272
PAD = 384                      # mirror padding of the background, room for the pan
VB = (4, 2)                    # the camera pans: the background moves by -VB on screen each frame
VO = (-5, 3)                   # the foreground objects move by VO on screen each frame
BLOCK = (2300, 300, 800, 560)  # solid textured block: x, y, w, h at frame 0
RAIL = (2300, 1000, 900, 420)  # railing: thin bars with see-through gaps
BAR_W, BAR_STEP = 3, 24        # bar width and spacing
DEPTH_BG, DEPTH_FG = 0.9, 0.3


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
    tex = world[PAD + 1200 + ty, PAD + 400 + tx]
    stripe = (tx >= BLOCK[2] // 2) & ((tx + ty) % 12 < 2)
    tex = np.where(stripe[:, None], np.float32(0.9), tex)
    img[by, bx] = tex
    img[bars] = np.float32([0.02, 0.02, 0.025])
    return img
