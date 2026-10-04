#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Rewrites every accumulating int8 dot product in a DXIL shader (LLVM IR text from "dxc -dumpbin")
# as a plain dot product followed by an add:
#
#     x = Dot4AddI8Packed(acc, a, b)      ->      d = Dot4AddI8Packed(0, a, b) ;  x = d + acc
#
# The result is the same number (32-bit wrap-around arithmetic either way), so the output stays
# bit-exact. It exists for RDNA2: the fsr4xyz project (https://github.com/the3rdparty1917/fsr4xyz)
# found that FSR 4's INT8 postpass ghosts on RDNA2 under Windows unless its dot products are
# written this way, which points at how AMD's RDNA2 driver handles the accumulating form. This is
# an independent implementation of that idea on AMD's shaders; no code from that project is used.
#
#   dxc -dumpbin <shader.dxil> | dot4_split_dxil.py > out.ll      (then dxilasm)
import re
import sys

DOT = re.compile(r'^(\s*)(%[\w.]+) = call i32 @dx\.op\.dot4AddPacked\.i32\(i32 163, i32 ([^,]+), i32 ([^,]+), i32 ([^)]+)\)')
out = []
n = 0
for l in sys.stdin.read().split('\n'):
    m = DOT.match(l)
    if m and m[3] != '0':
        n += 1
        out.append(f'{m[1]}%ds.{n} = call i32 @dx.op.dot4AddPacked.i32(i32 163, i32 0, i32 {m[4]}, i32 {m[5]})')
        out.append(f'{m[1]}{m[2]} = add i32 %ds.{n}, {m[3]}')
    else:
        out.append(l)
if not n:
    sys.exit('dot4_split_dxil: no accumulating dot product found')
print('\n'.join(out))
print(f'dot4_split_dxil: {n} dot products split', file=sys.stderr)
