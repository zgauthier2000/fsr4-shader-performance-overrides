#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""m2r.py in.ll out.ll: in the entry block, forward constant-index array stores to later loads of the same slot
and drop stores that are overwritten before the block ends. Values and arithmetic are unchanged."""
import re, sys
L = open(sys.argv[1]).read().split('\n')
s = next(i for i, l in enumerate(L) if l.startswith('define '))
e = next(i for i in range(s, len(L)) if re.match(r'\s+(br|ret) ', L[i]))
GEP = re.compile(r'\s+(%\d+) = getelementptr \[\d+ x i32\], \[\d+ x i32\]\* (%\d+), i32 0, i32 (\d+)\s*$')
ST = re.compile(r'\s+store i32 (\S+), i32\* (%\d+)')
LD = re.compile(r'\s+(%\d+) = load i32, i32\* (%\d+)')
gep = {}; cur = {}; last = {}; drop = set(); sub = {}
for i in range(s + 1, e):
    l = L[i]
    m = GEP.match(l)
    if m: gep[m.group(1)] = (m.group(2), int(m.group(3))); continue
    m = ST.match(l)
    if m:
        if m.group(2) not in gep: sys.exit('store through unknown pointer: ' + l)
        k = gep[m.group(2)]; v = m.group(1); v = sub.get(v, v)
        if k in last: drop.add(last[k])
        cur[k] = v; last[k] = i; continue
    m = LD.match(l)
    if m:
        if m.group(2) not in gep: sys.exit('load through unknown pointer: ' + l)
        k = gep[m.group(2)]
        if k not in cur: sys.exit('load before store: ' + l)
        sub[m.group(1)] = cur[k]; drop.add(i); continue
    if 'getelementptr' in l or re.search(r'\b(store|load)\b', l.split(';')[0]): sys.exit('unhandled: ' + l)
rx = re.compile(r'%\d+\b')
out = []
for i, l in enumerate(L):
    if i in drop: continue
    if i > s:
        c = l.split(';')[0] if not l.startswith(';') else l
        l = rx.sub(lambda m: sub.get(m.group(0), m.group(0)), l)
    out.append(l)
open(sys.argv[2], 'w').write('\n'.join(out))
print(f'forwarded {len(sub)} loads, dropped {len(drop) - len(sub)} stores, kept {len(last)}')
