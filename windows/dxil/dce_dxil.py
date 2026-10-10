#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# dce_dxil.py < shader.ll > out.ll
#
# Removes the instructions of a DXIL shader whose results nothing uses, and numbers the unnamed
# values again. The rewrites in this folder add their code under names of their own and leave the
# code they replace where it is, because unnamed values are numbered in order of appearance and
# taking one out shifts every number after it. That leaves the replaced code for the driver's
# compiler to discard. This does the discarding here, so that what reaches the driver contains
# only the code that runs (for the prepass: 12 exchanges between threads, not 12 plus AMD's 32).
#
# Kept: every instruction with an effect (stores, calls that return nothing, atomic operations,
# branches, returns) and whatever those depend on; declarations of functions no longer called go
# too. Nothing else changes, so the output is bit-exact.
import re
import sys

L = sys.stdin.read().split('\n')
die = lambda m: sys.exit(f'dce_dxil: {m}')
start = next((n for n, l in enumerate(L) if l.startswith('define ')), None)
if start is None:
    die('no function')
end = next(n for n in range(start, len(L)) if L[n] == '}')
if any(l.startswith('define ') for l in L[end:]):
    die('more than one function')
V = r'%[\w.]+'
code = lambda l: re.sub(r'\s*;.*$', '', l)
uses = lambda text: set(re.findall(rf'(?<![\w.])({V})', text))
defs, roots = {}, []
for n in range(start + 1, end):
    c = code(L[n])
    if not c.strip():
        continue
    m = re.match(rf'\s+({V}) = (.*)$', c)
    if not m:
        roots.append(n)                         # store, br, ret, switch, a call that returns nothing
    else:
        if m[1] in defs:
            die(f'{m[1]} defined twice')
        defs[m[1]] = n
        effect = re.match(r'(tail )?call ', m[2]) and (not re.search(r'@dx\.op\.\w+\.\w+\(', m[2]) or '@dx.op.atomic' in m[2])
        if effect or re.match(r'(invoke|cmpxchg|atomicrmw|alloca) ', m[2]):
            roots.append(n)
live, todo = set(roots), list(roots)
while todo:
    n = todo.pop()
    c = code(L[n])
    for u in uses(c.split(' = ', 1)[1] if re.match(rf'\s+{V} = ', c) else c):
        d = defs.get(u)
        if d is not None and d not in live:
            live.add(d); todo.append(d)
dead = set(defs.values()) - live
# number the unnamed values and blocks again: the entry block is %0, then in order of appearance.
# A block nothing jumps to has no label line, only the comment "No predecessors!", and is numbered all the same.
ren, old, count = {'%0': '%0'}, 1, 1
body = []
for n in range(start + 1, end):
    lab = re.match(r'; <label>:(\d+)(.*)$', L[n])
    orphan = re.match(r'\s*; No predecessors!', L[n])
    m = re.match(r'\s+(%\d+) = ', code(L[n]))
    if lab or orphan or m:
        if (lab and int(lab[1]) != old) or (m and int(m[1][1:]) != old):
            die(f'value %{old} expected at line {n + 1}')
        if n not in dead:
            ren[f'%{old}'] = f'%{count}'; count += 1
        old += 1
    if n not in dead:
        body.append(L[n])
fix = lambda l: re.sub(r'(?<![\w.])%\d+(?![\w.])', lambda t: ren.get(t[0]) or die(f'{t[0]} used but not defined'), l)
body = [(lambda lab: f'; <label>:{ren["%" + lab[1]][1:]}{fix(lab[2])}' if lab else fix(l))(re.match(r'; <label>:(\d+)(.*)$', l)) for l in body]
sys.stderr.write(f'dce_dxil: {len(dead)} unused instructions removed\n')
# a function that nothing calls any more must not stay declared (the DXIL validator rejects it)
called = set(re.findall(r'@[\w.]+(?=\()', '\n'.join(body)))
keep = lambda l: not (m := re.match(r'declare .*?(@[\w.]+)\(', l)) or m[1] in called
sys.stdout.write('\n'.join([l for l in L[:start + 1] if keep(l)] + body + [l for l in L[end:] if keep(l)]))
