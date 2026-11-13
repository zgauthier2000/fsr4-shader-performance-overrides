#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Hoist read-only SRV textureLoads (and the pure arithmetic computing their coordinates) from a later block into an
earlier block that dominates it: the loads of the prepass's second half (the block that starts with a textureStore and
then reads depth/motion again) go into the loop's first block, right after that block's own loads. SRV reads have no side
effects and nothing in the shader writes these resources, so the program computes the same values.
usage: xhoist.py in.ll out.ll"""
import re, sys
src, dst = sys.argv[1], sys.argv[2]
L = open(src, encoding='utf-8').read().split('\n')
fn = next(i for i, l in enumerate(L) if l.startswith('define void @'))
fn_end = next(i for i in range(fn, len(L)) if L[i] == '}')
srv = {m.group(1) for l in L for m in [re.match(r'\s+(%\d+) = call %dx\.types\.Handle @dx\.op\.createHandle\(i32 57, i8 0,', l)] if m}
# blocks
starts = {'%0': fn + 1}; order = ['%0']; cur = '%0'; blk = {}; succ = {'%0': []}
for i in range(fn + 1, fn_end):
    m = re.match(r'; <label>:(\d+)', L[i])
    if m: cur = '%' + m.group(1); starts[cur] = i + 1; order.append(cur); succ[cur] = []; continue
    blk[i] = cur
    if re.match(r'\s+br ', L[i]): succ[cur] += re.findall(r'label (%\d+)', L[i])
pred = {b: [] for b in order}
for b, ss in succ.items():
    for s in ss: pred[s].append(b)
dom = {b: set(order) for b in order}; dom['%0'] = {'%0'}; ch = True
while ch:
    ch = False
    for b in order[1:]:
        ps = [dom[p] for p in pred[b]]; nd = ({b} | set.intersection(*ps)) if ps else {b}
        if nd != dom[b]: dom[b] = nd; ch = True
TL = re.compile(r'\s+(%\d+) = call %dx\.types\.ResRet\.\w+ @dx\.op\.textureLoad\.\w+\(i32 66, %dx\.types\.Handle (%\d+),')
DEF = re.compile(r'^\s+(%\d+) = ')
PURE = re.compile(r'= (add|sub|mul|shl|lshr|ashr|and|or|xor|icmp|fcmp|select|zext|sext|trunc|fadd|fsub|fmul|fdiv|sitofp|uitofp|fptosi|fptoui|fptrunc|fpext|extractvalue)\b|'
                  r'= call (i32|float|half) @dx\.op\.(binary|unary|tertiary)\.|= call %dx\.types\.CBufRet\.\w+ @dx\.op\.cbufferLoadLegacy\.')
defline = {DEF.match(L[i]).group(1): i for i in range(fn + 1, fn_end) if DEF.match(L[i])}
loads_in = {}
for i in range(fn + 1, fn_end):
    m = TL.match(L[i])
    if m and m.group(2) in srv: loads_in.setdefault(blk[i], []).append(i)
blocks_with = [b for b in order if b in loads_in]
# source: a block with loads whose immediate loads-block dominator also has loads
moves = []
for b in blocks_with:
    cands = [d for d in blocks_with if d != b and d in dom[b]]
    if not cands: continue
    tgt = max(cands, key=lambda d: len(dom[d]))     # nearest dominating block with loads
    moves.append((b, tgt))
def uses(l):
    m = DEF.match(l); rhs = l[m.end():] if m else l
    return re.findall(r'%\d+', rhs.split('  ;')[0])
remove = set(); inserts = {}
for b, tgt in moves:
    sl = set(loads_in[b]); work = [u for i in loads_in[b] for u in uses(L[i])]; ok = True
    while work:
        u = work.pop(); d = defline.get(u)
        if d is None or d in sl: continue
        if blk[d] in dom[tgt]: continue            # already available in the target (target's own block: checked below)
        if blk[d] != b or not PURE.search(L[d]): ok = False; break
        sl.add(d); work += uses(L[d])
    if not ok: print('skip', b, '->', tgt, '(operand not available)'); continue
    # insertion point in tgt: after its last load and after every operand defined in tgt
    pos = max(loads_in[tgt])
    for i in sl:
        for u in uses(L[i]):
            d = defline.get(u)
            if d is not None and d not in sl and blk.get(d) == tgt: pos = max(pos, d)
    # moved values used in b only (their uses stay below, dominated by tgt)
    inserts.setdefault(pos, []).extend(sorted(sl)); remove |= sl
    print(f'{b} -> {tgt}: {len(loads_in[b])} loads, {len(sl)} instructions, after line {pos + 1}')
out = []
for i, l in enumerate(L):
    if i not in remove: out.append(l)
    if i in inserts: out += [L[j] for j in inserts[i]]
t = '\n'.join(out)
t = re.sub(r'(?<![\w.])%(\d+)\b', r'%v\1', t)
t = re.sub(r'(?m)^; <label>:(\d+)', r'v\1:', t)
t = re.sub(r'(?m)^(define void @[^\n]*\{)\n', r'\1\nv0:\n', t, count=1)
open(dst, 'w', encoding='utf-8').write(t)
