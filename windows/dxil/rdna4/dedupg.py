#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""dedupg.py in.ll out.ll: within one basic block, an operand-load group (id byte 0x29) that repeats an earlier
group with the same buffer and the same address value is removed; its read-outs take the earlier group's values."""
import re, sys
L = open(sys.argv[1]).read().split('\n')
DEF = re.compile(r'\s+(%\d+) = (.*?)\s*(;.*)?$')
ACE = re.compile(r'atomicCompareExchange\.i32\(i32 79, %dx\.types\.Handle (%\d+), i32 (\d+), i32 undef, i32 undef, i32 ([^,]+), i32 ([^)]+)\)')
RAW = re.compile(r'rawBufferLoad\.i32\(i32 139, %dx\.types\.Handle (%\d+), i32 (%\d+), (.*)\)')
PURE = re.compile(r'(add|sub|mul|shl|lshr|ashr|and|or|xor|zext|sext|trunc|select|icmp)\b|call i32 @dx\.op\.(binary|unary|tertiary)\.')
defs = {}
for l in L:
    m = DEF.match(l)
    if m: defs[m.group(1)] = m.group(2)
memo = {}
def canon(v):
    if v in memo: return memo[v]
    e = defs.get(v)
    r = v if e is None or not PURE.match(e) else re.sub(r'%\d+', lambda m: canon(m.group(0)), e)
    memo[v] = r; return r
sub = {}; drop = set(); seen = {}; i = 0; ng = 0
while i < len(L):
    l = L[i]
    if l.startswith('; <label>') or l.startswith('define '): seen = {}
    m = ACE.search(l)
    if m and int(m.group(2)) == 0x50000029:
        d = [DEF.match(L[i + k]) for k in range(12)]
        r = RAW.search(L[i + 1]); a2 = ACE.search(L[i + 3])
        ro = [ACE.search(L[i + 4 + k]) for k in range(8)]
        ok = all(d) and r and r.group(2) == d[0].group(1) and 'extractvalue' in L[i + 2] and a2 and a2.group(3) == d[2].group(1) \
            and (int(a2.group(2)) >> 24, int(a2.group(2)) & 255) == (0x51, 0x29) and all(x and int(x.group(2)) >> 24 == 0x52 and int(x.group(2)) & 255 == 0x29 for x in ro)
        if not ok: sys.exit(f'unexpected group shape at line {i + 1}')
        ng += 1
        key = (m.group(1), canon(m.group(3)), m.group(4), r.group(1), r.group(3), a2.group(1), a2.group(2), a2.group(4), tuple((x.group(1), x.group(2), x.group(3), x.group(4)) for x in ro))
        if key in seen:
            for k in range(8): sub[d[4 + k].group(1)] = seen[key][k]
            drop.update(range(i, i + 12))
        else: seen[key] = [d[4 + k].group(1) for k in range(8)]
        i += 12; continue
    i += 1
rx = re.compile(r'%\d+\b')
out = [rx.sub(lambda m: sub.get(m.group(0), m.group(0)), l) if not l.startswith(';') else l for i, l in enumerate(L) if i not in drop]
open(sys.argv[2], 'w').write('\n'.join(out))
print(f'groups {ng}, removed {len(drop) // 12}')
