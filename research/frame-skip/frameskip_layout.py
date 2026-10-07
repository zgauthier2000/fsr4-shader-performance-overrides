# SPDX-License-Identifier: GPL-2.0-or-later
# Layout shared by frameskip.py, motionpost.py and skipblend.py (and their DXIL forms).

def plane_layout(S):
    """Where the "who was here a frame ago" plane sits and how its words are packed (shared by frameskip, motionpost, skipblend).
    One word per 4x4 output pixels, in the same rows of the second region as the motion entries, in word ranges those leave free.
    A word is (nearness << IDB) | (block row << XB) | block column, 0 = nobody; the nearest surface wins (atomic maximum)."""
    width = S // 16 - 2; nx, ny = width // 2, (width * 9 // 16) // 2
    xb, yb = (nx - 1).bit_length(), (ny - 1).bit_length()
    pb0, pb1 = {15392: (1040, 3040), 30752: (2048, 6144), 61472: (8192, 10240)}[S]
    return dict(nx=nx, ny=ny, xb=xb, idb=xb + yb, kb=32 - xb - yb, m=32 - xb - yb - 5, pb0=pb0, pb1=pb1)
