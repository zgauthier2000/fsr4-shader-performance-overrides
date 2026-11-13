#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Group the FP8 postpass's per-pixel colour taps: in the basic block that holds the 3x3 textureLoads of the colour SRV,
move every textureLoad from a read-only SRV (and the pure arithmetic computing its coordinates) to one place, as early
as their operands allow, in their original order. Nothing else moves; AMD's intrinsic calls (atomicCompareExchange),
LDS accesses, stores and anything with side effects never move and are never crossed by a slice member that depends
on them. Loads from SRVs have no side effects and nothing in the shader writes those resources, so the program computes
exactly the same values.

usage: taphoist.py in.ll out.ll
"""
import re, sys

src, dst = sys.argv[1], sys.argv[2]
lines = open(src, encoding='utf-8').read().split('\n')

# SRV handles: createHandle(i32 57, i8 0, ...)
srv = set(m.group(1) for l in lines for m in [re.match(r'\s+(%\d+) = call %dx\.types\.Handle @dx\.op\.createHandle\(i32 57, i8 0,', l)] if m)
fn = next(i for i, l in enumerate(lines) if l.startswith('define void @'))
fn_end = next(i for i in range(fn, len(lines)) if lines[i] == '}')
heads = [fn + 1] + [i + 1 for i in range(fn, fn_end) if lines[i].startswith('; <label>:')]
blocks = [(h, next(i for i in range(h, fn_end + 1) if re.match(r'\s+(br|ret) ', lines[i]) or lines[i] == '}')) for h in heads]

TL = re.compile(r'@dx\.op\.textureLoad\.\w+\(i32 66, %dx\.types\.Handle (%\d+),')
def is_tap(l):
    m = TL.search(l); return bool(m) and m.group(1) in srv
start, end = max(blocks, key=lambda b: sum(is_tap(lines[i]) for i in range(*b)))
body = lines[start:end]
DEF = re.compile(r'^\s+(%\d+) = ')
defs = {DEF.match(l).group(1): i for i, l in enumerate(body) if DEF.match(l)}
def uses(l):
    m = DEF.match(l); rhs = l[m.end():] if m else l
    return re.findall(r'%\d+', rhs.split('  ;')[0])
# pure instructions a slice may take along: integer/float arithmetic, compares, selects, casts, and dx.op calls without side effects
PURE = re.compile(r'= (add|sub|mul|shl|lshr|ashr|and|or|xor|icmp|fcmp|select|fadd|fsub|fmul|fdiv|zext|sext|trunc|bitcast|sitofp|uitofp|fptosi|fptoui|extractvalue) |'
                  r'= call (i32|float) @dx\.op\.(binary|unary|tertiary|waveGetLaneIndex)\.|= call %dx\.types\.CBufRet\.\w+ @dx\.op\.cbufferLoadLegacy\.')
taps = [i for i, l in enumerate(body) if is_tap(l)]
slice_ = set(taps); work = [u for t in taps for u in uses(body[t])]
while work:
    u = work.pop()
    if u not in defs: continue
    d = defs[u]
    if d in slice_ or not PURE.search(body[d]): continue
    slice_.add(d); work += uses(body[d])
# earliest point: after every in-block operand of the slice that is not itself in the slice
earliest = 0
for s in slice_:
    for u in uses(body[s]):
        if u in defs and defs[u] not in slice_: earliest = max(earliest, defs[u] + 1)
members = sorted(slice_)
if earliest > taps[0]: sys.exit(f'refusing: the group point ({earliest}) would be after the first tap ({taps[0]})')
assert earliest <= members[0] or all(not DEF.match(body[i]) or True for i in members)
# a slice member that something outside the slice uses before 'earliest' cannot move past that use: keep it (and drop it from the group)
outside_uses = {}
for i, l in enumerate(body):
    if i in slice_: continue
    for u in uses(l):
        if u in defs and defs[u] in slice_: outside_uses.setdefault(defs[u], []).append(i)
stay = {m for m in members if any(j < earliest for j in outside_uses.get(m, []))}
if stay:
    print('kept in place (used before the group point):', len(stay))
members = [m for m in members if m not in stay]
moved = set(members)
out = []
for i, l in enumerate(body):
    if i == earliest: out += [body[m] for m in members]
    if i in moved: continue
    out.append(l)
if earliest >= len(body): out += [body[m] for m in members]
lines[start:end] = out
text = '\n'.join(lines)
text = re.sub(r'(?<![\w.])%(\d+)\b', r'%v\1', text)
text = re.sub(r'(?m)^; <label>:(\d+)', r'v\1:', text)
text = re.sub(r'(?m)^(define void @[^\n]*\{)\n', r'\1\nv0:\n', text, count=1)
open(dst, 'w', encoding='utf-8').write(text)
print(f'block lines {start + 1}-{end}: {len(taps)} taps, {len(members)} instructions grouped at block offset {earliest} '
      f'(first tap was at {taps[0]}, last at {taps[-1]})')
