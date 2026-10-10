#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# wround.py < passN.spvasm > out.spvasm
#
# NOT bit-exact. Between its layers a model pass divides each sum by a power of two, rounding
# halves to the even neighbor:   y = (x + (h - 1) + ((x >> n) & 1)) >> n,   h = 2^(n-1).
# This replaces it with rounding halves up:   y = (x + h) >> n,   which is two instructions
# shorter. The result differs by one step, and only when x is exactly halfway (one value in 2^n).
# The idea is from VALKKKS's notes of 2026-10-05.
import re
import sys

L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m:
        defs[m[1]] = (n, m[2])


def cval(v):
    m = re.match(r'OpConstant %uint (\d+)$', defs.get(v, (0, ''))[1])
    return int(m[1]) if m else None


new = {}
done = 0
for n, l in enumerate(L):
    m = re.match(r'(\s*)(%\S+) = OpShiftRightArithmetic %uint (%\S+) (%\S+)$', l)
    if not m or cval(m[4]) is None:
        continue
    N = cval(m[4])
    s2 = re.match(r'OpIAdd %uint (%\S+) (%\S+)$', defs.get(m[3], (0, ''))[1])
    if not s2:
        continue
    for a, b in ((s2[1], s2[2]), (s2[2], s2[1])):
        s1 = re.match(r'OpIAdd %uint (%\S+) (%\S+)$', defs.get(a, (0, ''))[1])
        bit = re.match(r'OpBitwiseAnd %uint (%\S+) %uint_1$', defs.get(b, (0, ''))[1])
        if not s1 or not bit or cval(s1[2]) != (1 << (N - 1)) - 1:
            continue
        sh = re.match(r'OpShiftRightLogical %uint (%\S+) (%\S+)$', defs.get(bit[1], (0, ''))[1])
        if not sh or sh[1] != s1[1] or cval(sh[2]) != N:
            continue
        h = 1 << (N - 1)
        name = f'%uint_{h}'
        if name not in defs:
            name = f'%wr_{h}'; new[name] = h
        ln = defs[m[3]][0]
        L[ln] = re.sub(r'OpIAdd %uint .*$', f'OpIAdd %uint {s1[1]} {name}', L[ln])
        done += 1
        break
if new:
    at = max(n for n, l in enumerate(L) if re.match(r'\s*%\S+ = OpConstant %uint ', l))
    L[at] += ''.join(f'\n{k} = OpConstant %uint {v}' for k, v in new.items())
sys.stderr.write(f'wround: {done} roundings changed\n')
sys.stdout.write('\n'.join(L))
