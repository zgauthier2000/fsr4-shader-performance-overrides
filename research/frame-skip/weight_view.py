#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# weight_view.py < skipblend.py output > text      (then the store rewrite, or assemble as it is)
#
# DEBUG, for the test rig. The output image shows the model's weight for the new frame (1 - a) of each pixel in all four channels;
# the history image is left alone, so the upscaler itself runs as usual.
import re, sys
L = sys.stdin.read().split('\n')
defs = {m[1]: m[2] for l in L for m in [re.match(r'\s*(%\w+) = (.*)$', l)] if m}
w = [re.match(r'OpFMul %float (%\w+) ', defs[f'%sb_wm{k}'])[1] for k in range(4)]
k = 0
for n, l in enumerate(L):
    m = re.match(r'\s*OpImageWrite (%\w+) (%\w+) (%\w+)', l)
    if not m: continue
    ac = re.match(r'OpAccessChain %\w+ %\w+ (%\w+)', defs[re.match(r'OpLoad %\w+ (%\w+)', defs[m[1]])[1]])
    if not ac or not defs.get(ac[1], '').endswith('%uint_2'): continue
    L[n] = f'%dbg_t{k} = OpCompositeConstruct %v4float {w[k]} {w[k]} {w[k]} {w[k]}\n               OpImageWrite {m[1]} {m[2]} %dbg_t{k}'; k += 1
assert k == 4, k
print('\n'.join(L))
