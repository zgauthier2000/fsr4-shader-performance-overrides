#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# postpass_411b_dxil.py < postpass.ll > out.ll
# The two small changes the fsr4xyz project's 4.1.1b makes to AMD's INT8 postpass besides splitting its dot products
# (dot4_split_dxil.py does that), written independently on AMD's shader text; no code from that project is used.
# Only for the timing kit's reference DLL (AMD's shaders plus these changes); the project's own DLLs do not use it.
#   - the two halvings of the render size: sdiv x, 2 -> lshr x, 1
#   - the clamps of neighbor coordinates, min(max(x, 0), limit) as signed numbers: the min becomes unsigned, and
#     where x is "coordinate +- 1" the max with 0 is dropped (a negative x then clamps to the limit, not to 0)
# The replaced max instructions stay in the text, unused (dce_dxil.py removes them).
import re, sys
L = sys.stdin.read().split('\n')
defs = {m[1]: m[2] for l in L if (m := re.match(r'\s+(%[\w.]+) = (.*)$', l))}
nd = nm = nx = 0
for i, l in enumerate(L):
    m = re.match(r'(\s+%[\w.]+ = )sdiv i32 (\S+), 2\s*$', l)
    if m:
        L[i] = f'{m[1]}lshr i32 {m[2]}, 1'; nd += 1; continue
    m = re.match(r'(\s+%[\w.]+ = call i32 @dx\.op\.binary\.i32\()i32 38, i32 (\S+), i32 (\S+)\)', l)
    if m:
        a = m[2]
        mx = re.match(r'call i32 @dx\.op\.binary\.i32\(i32 37, i32 (\S+), i32 0\)', defs.get(a, ''))
        if not mx:
            sys.exit('postpass_411b_dxil: a signed min that is not a clamp from 0')
        if defs.get(mx[1], '').startswith('add '):
            a = mx[1]; nx += 1
        L[i] = f'{m[1]}i32 40, i32 {a}, i32 {m[3]})'; nm += 1
if nd != 2 or not nm or not nx:
    sys.exit(f'postpass_411b_dxil: expected 2 divisions and clamps, some of them on a sum; found {nd}, {nm}, {nx}')
sys.stderr.write(f'postpass_411b_dxil: {nd} divisions, {nm} clamps, {nx} of them without the max\n')
# the unsigned min must be declared like the signed one (same function, another opcode): nothing to add
sys.stdout.write('\n'.join(L))
