#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Model pass 11 of FSR 4.1.1 (INT8), DXIL form (LLVM IR text from "dxc -dumpbin"): the z components
# of the group id and thread id are always 0, because AMD's DLL dispatches every model pass with a
# z count of 1, but the pass uses them in its loop bounds, so a compiler cannot unroll the loops.
# This replaces those reads with the constant 0. The output is bit-exact.
#
#   dxc -dumpbin <pass11.dxil> | zconst_dxil.py > out.ll      (then dxilasm)
import re
import sys

out = []
n = 0
for line in sys.stdin.read().split('\n'):
    m = re.match(r'(\s*%[\w.]+ = )call i32 @dx\.op\.(groupId|threadId|threadIdInGroup)\.i32\(i32 \d+, i32 2\)', line)
    if m:
        line = m[1] + 'add i32 0, 0'
        n += 1
    out.append(line)
if not n:
    sys.exit('zconst_dxil: no z reads found')
# The validator rejects declarations that are no longer called.
text = '\n'.join(out)
for name in ('groupId', 'threadId', 'threadIdInGroup'):
    if f'call i32 @dx.op.{name}.i32(' not in text:
        out = [l for l in out if not l.startswith(f'declare i32 @dx.op.{name}.i32(')]
print('\n'.join(out))
