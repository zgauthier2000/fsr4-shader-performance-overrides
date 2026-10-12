#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# store_gate.py <rec|hist|both> < skipblend.py output > text      (assemble as it is, without the store rewrite)
#
# EXPERIMENT, for the test rig, on a postpass used with AMD's other shaders (the model runs on every frame). On frames whose jitter x is negative the postpass does not store the recurrent image / the history image,
# so the next frame sees that input two frames old while everything else is one frame old.
import re, sys
what = sys.argv[1]; L = sys.stdin.read().split('\n')
defs = {m[1]: m[2] for l in L for m in [re.match(r'\s*(%\w+) = (.*)$', l)] if m}
out = []; cur = None; ren = {}; n = 0
for l in L:
    m = re.match(r'\s*(%\w+) = OpLabel', l)
    if m: cur = m[1]; first = m[1]
    m = re.match(r'\s*OpImageWrite (%\w+) (%\w+) (%\w+)', l)
    if m and re.match(r'OpLoad', defs.get(m[1], '')):
        ac = re.match(r'OpAccessChain %\w+ (%\w+) (%\w+)', defs[re.match(r'OpLoad %\w+ (%\w+)', defs[m[1]])[1]])
        kind = 'rec' if ac and ac[1] == '%30' else 'hist' if ac and defs.get(ac[2], '').endswith('%uint_1') else None
        if kind and what in (kind, 'both'):
            out += [f'%gt_c{n} = OpFOrdGreaterThanEqual %bool %sb_jx %float_0', f'OpSelectionMerge %gt_m{n} None', f'OpBranchConditional %gt_c{n} %gt_w{n} %gt_m{n}', f'%gt_w{n} = OpLabel', l, f'OpBranch %gt_m{n}', f'%gt_m{n} = OpLabel']
            ren[first] = f'%gt_m{n}'; n += 1; continue
    out.append(l)
for i, l in enumerate(out):
    if '= OpPhi' in l:
        h, ops = l.split('OpPhi', 1); t = ops.split()
        out[i] = h + 'OpPhi ' + ' '.join([t[0]] + [x if k % 2 == 0 else ren.get(x, x) for k, x in enumerate(t[1:])])
sys.stderr.write(f'gate {what}: {n} writes gated\n'); print('\n'.join(out))
