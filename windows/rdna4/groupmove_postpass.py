#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# groupmove_postpass.py in.ll out.ll D: the earlier groupmove, used for the postpass. The current groupmove.py also
# issues address math shared by several groups early; in the postpass that removes six more serialized waits but makes
# it about 0.7% slower, so the postpass keeps this version.
"""Issue FP8 model-pass operand loads earlier: move each complete load group (AMD's address intrinsic 0x50000029,
the placeholder rawBufferLoad, its extractvalue, the insert 0x5100xx29 and the eight read-outs 0x52xxxx29), with the
pure arithmetic computing its address, up past at most D matrix-multiply groups. Groups never pass one another and
never interleave, so each group's intrinsic sequence stays contiguous and in order; only operations on other ids
(the matrix multiplies, ids 0x28/0x2f/0x30/0x32/0x35) are crossed.
usage: groupmove.py in.ll out.ll D"""
import re, sys
src, dst, D = sys.argv[1], sys.argv[2], int(sys.argv[3])
L = open(src, encoding='utf-8').read().split('\n')
fn = next(i for i, l in enumerate(L) if l.startswith('define void @'))
fn_end = next(i for i in range(fn, len(L)) if L[i] == '}')
heads = [fn + 1] + [i + 1 for i in range(fn, fn_end) if L[i].startswith('; <label>:')]
blocks = [(h, next(i for i in range(h, fn_end + 1) if re.match(r'\s+(br|ret|switch) ', L[i]) or L[i] == '}')) for h in heads]
MAG = re.compile(r'atomicCompareExchange\.i32\(i32 79, %dx\.types\.Handle %\d+, i32 (\d+),')
DEF = re.compile(r'^\s+(%\d+) = ')
PURE = re.compile(r'= (add|sub|mul|shl|lshr|ashr|and|or|xor|icmp|select|zext|sext|trunc|extractvalue) |= call i32 @dx\.op\.(binary|unary|tertiary)\.')
def mag(l):
    m = MAG.search(l); return int(m.group(1)) if m else None
def uses(l):
    m = DEF.match(l); rhs = l[m.end():] if m else l
    return re.findall(r'%\d+', rhs.split('  ;')[0])
moved_total = 0
for bs, be in blocks:
    body = L[bs:be]
    # items: ('G', [lines]) load group, ('W', line) a matrix-op intrinsic (other id), ('X', line) anything else
    items = []; i = 0
    while i < len(body):
        v = mag(body[i])
        if v is not None and (v >> 16) == 0x5000 and (v & 0xff) == 0x29:
            j = i + 1; reads = 0; ok = True
            while j < len(body) and reads < 8:
                w = mag(body[j])
                if w is not None:
                    if (w & 0xff) != 0x29: ok = False; break
                    if (w >> 24) == 0x52: reads += 1
                elif 'rawBufferLoad' not in body[j] and 'extractvalue' not in body[j]: ok = False; break
                j += 1
            if ok and reads == 8: items.append(['G', body[i:j]]); i = j; continue
        v = mag(body[i])
        items.append(['W' if v is not None else 'X', [body[i]]]); i += 1
    if sum(t == 'G' for t, _ in items) < 2: continue
    # pull each group's pure address slice (defined in this block, used only by that group) into the group
    defs_at = {}
    for k, (t, ls) in enumerate(items):
        for l in ls:
            m = DEF.match(l)
            if m: defs_at[m.group(1)] = k
    users = {}
    for k, (t, ls) in enumerate(items):
        for l in ls:
            for u in uses(l): users.setdefault(u, set()).add(k)
    owner = {}
    for k, it in enumerate(items):
        if it[0] != 'G': continue
        work = [u for l in it[1] for u in uses(l)]
        while work:
            u = work.pop(); d = defs_at.get(u)
            if d is None or d == k or items[d][0] != 'X' or not PURE.search(items[d][1][0]): continue
            if {owner.get(x, x) for x in users.get(u, set())} - {k, d}: continue
            line = items[d][1][0]; items[d] = ['X', []]; owner[d] = k
            it[1].insert(0, line); defs_at[u] = k
            work += uses(line)
    items = [it for it in items if it[1]]
    # move groups up
    out = []
    for t, ls in items:
        if t != 'G': out.append([t, ls]); continue
        need = {u for l in ls for u in uses(l)}
        pos = len(out); runs = 0; best = pos
        while pos > 0:
            pt, pls = out[pos - 1]
            if pt == 'G': break
            if any(DEF.match(l) and DEF.match(l).group(1) in need for l in pls): break
            if pt == 'W' and (pos == len(out) or out[pos][0] != 'W'):
                runs += 1                      # entering a run of matrix-op calls from below
                if runs > D: break
            pos -= 1
            if pos == 0 or out[pos - 1][0] != 'W': best = pos   # never stop inside a run of matrix-op calls
        pos = best
        if pos != len(out): moved_total += 1
        out.insert(pos, [t, ls])
    L[bs:be] = [l for _, ls in out for l in ls]
text = '\n'.join(L)
text = re.sub(r'(?<![\w.])%(\d+)\b', r'%v\1', text)
text = re.sub(r'(?m)^; <label>:(\d+)', r'v\1:', text)
text = re.sub(r'(?m)^(define void @[^\n]*\{)\n', r'\1\nv0:\n', text, count=1)
open(dst, 'w', encoding='utf-8').write(text)
print('groups moved:', moved_total)
