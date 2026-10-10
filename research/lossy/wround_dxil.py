#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# wround_dxil.py < passN.ll > out.ll
#
# NOT bit-exact. The DXIL form of wround.py: the rounding between a model pass's layers,
#     y = (x + (h - 1) + ((x >> n) & 1)) >> n,   h = 2^(n-1)      (halves to the even neighbor)
# becomes   y = (x + h) >> n   (halves up). The instructions no longer used are left in place;
# the driver removes them.
import re
import sys

L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*?)(\s*;.*)?$', l)
    if m:
        defs[m[1]] = (n, m[2].strip())
rhs = lambda v: defs.get(v, (0, ''))[1]

done = 0
for n, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = ashr i32 (%[\w.]+), (\d+)\s*$', l)
    s2 = re.match(r'add i32 (%[\w.]+), (%[\w.]+)$', rhs(m[2])) if m else None
    if not s2:
        continue
    N = int(m[3])
    for a, b in ((s2[1], s2[2]), (s2[2], s2[1])):
        s1 = re.match(r'add i32 (%[\w.]+), (\d+)$', rhs(a))
        bit = re.match(r'and i32 (%[\w.]+), 1$', rhs(b))
        if not s1 or not bit or int(s1[2]) != (1 << (N - 1)) - 1:
            continue
        sh = re.match(r'lshr i32 (%[\w.]+), (\d+)$', rhs(bit[1]))
        if not sh or sh[1] != s1[1] or int(sh[2]) != N:
            continue
        ln = defs[m[2]][0]
        L[ln] = re.sub(r'= add i32 .*$', f'= add i32 {s1[1]}, {1 << (N - 1)}', L[ln])
        done += 1
        break
if not done:
    sys.exit('wround_dxil: no rounding of that form in this shader')
sys.stderr.write(f'wround_dxil: {done} roundings changed\n')
sys.stdout.write('\n'.join(L))
