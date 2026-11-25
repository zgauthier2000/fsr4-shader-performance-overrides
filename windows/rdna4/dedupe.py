#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Share repeated texture reads in an FSR 4 FP8 prepass (dxc -dumpbin .ll).

Two textureLoads of the same read-only SRV whose coordinates are equal for every input are the same read. The later
one is removed and its result replaced by the earlier one's, if the earlier one dominates it. Equality is checked
by evaluating both coordinate expressions in float32 / int32 on many random inputs (thread and group ids, loop phis,
constant-buffer values); the expressions themselves are not changed, so where the driver compiles them the same
way, the shared read returns the same value the removed one would have.

usage: dedupe.py in.ll out.ll [--count]   (--count: only report how many reads are shared)
"""
import re, sys, random

src, dst = sys.argv[1], sys.argv[2]
count_only = '--count' in sys.argv
text = open(src, encoding='utf-8').read()
L = text.split('\n')
fn = next(i for i, l in enumerate(L) if l.startswith('define void @'))
fn_end = next(i for i in range(fn, len(L)) if L[i] == '}')

# --- blocks and dominators
labels = {}          # line index of block start -> name
cur = '%0'; block_of = {}; succ = {'%0': []}; order = ['%0']
for i in range(fn + 1, fn_end):
    m = re.match(r'; <label>:(\d+)', L[i])
    if m:
        cur = '%' + m.group(1); succ.setdefault(cur, []); order.append(cur); continue
    block_of[i] = cur
    if re.match(r'\s+br ', L[i]):
        succ[cur] += re.findall(r'label (%\d+)', L[i])
pred = {b: [] for b in order}
for b, ss in succ.items():
    for s in ss: pred[s].append(b)
dom = {b: set(order) for b in order}; dom['%0'] = {'%0'}
changed = True
while changed:
    changed = False
    for b in order[1:]:
        ps = [dom[p] for p in pred[b]]
        nd = ({b} | set.intersection(*ps)) if ps else {b}
        if nd != dom[b]: dom[b] = nd; changed = True

# --- definitions
D = {}; line_of = {}
for i in range(fn + 1, fn_end):
    m = re.match(r'\s+(%\d+) = (.*)', L[i])
    if m: D[m.group(1)] = re.sub(r'\s+;.*', '', m.group(2)); line_of[m.group(1)] = i
srv = {m.group(1) for l in L[fn:fn_end] for m in [re.match(r'\s+(%\d+) = call %dx\.types\.Handle @dx\.op\.createHandle\(i32 57, i8 0,', l)] if m}

# --- numeric evaluation (pure Python, float32 emulated): each value is a tuple of N samples
import struct, math
N = 64
rnd = random.Random(1)
def f32(x):
    try: return struct.unpack('<f', struct.pack('<f', x))[0]
    except OverflowError: return math.copysign(math.inf, x)
def i32(x): x &= 0xffffffff; return x - (1 << 32) if x >> 31 else x
leaf = {}
def leafval(key, kind):
    if key not in leaf:
        g = {'tid': lambda: rnd.randrange(0, 32), 'gid': lambda: rnd.randrange(0, 200), 'phi': lambda: rnd.randrange(0, 2),
             'cbf': lambda: f32(rnd.uniform(0.3, 2.5)), 'cbi': lambda: rnd.randrange(64, 4096)}[kind]
        leaf[key] = tuple(g() for _ in range(N))
    return leaf[key]
cache = {}
class Opaque(Exception): pass
def hexd(s): return struct.unpack('>d', bytes.fromhex(s[2:].rjust(16, '0')))[0]
def ftoi(x):
    if math.isnan(x) or math.isinf(x): raise Opaque()
    return i32(int(x))
def val(v, t):
    if not v.startswith('%'):
        if v == 'undef': raise Opaque()
        if t == 'float': return (f32(hexd(v) if v.startswith('0x') else float(v)),) * N
        if v in ('true', 'false'): raise Opaque()
        return (i32(int(v)),) * N
    if v in cache: return cache[v]
    e = D.get(v)
    if e is None: raise Opaque()
    r = None
    if 'threadIdInGroup' in e or 'threadId.i32' in e: r = leafval(e, 'tid')
    elif 'groupId' in e: r = leafval(e, 'gid')
    elif e.startswith('phi '): r = leafval(v, 'phi')
    elif e.startswith('extractvalue %dx.types.CBufRet'):
        m = re.match(r'extractvalue %dx\.types\.CBufRet\.(\w+) (%\d+), (\d+)', e)
        mm = re.search(r'Handle (%\d+), i32 (\S+)\)', D[m.group(2)])
        r = leafval(('cb', mm.group(1), mm.group(2), m.group(3)), 'cbf' if m.group(1) == 'f32' else 'cbi')
    else:
        m = re.match(r'call (?:float|i32) @dx\.op\.unary\.\w+\(i32 (\d+), (\w+) (\S+)\)', e)
        if m:
            a = val(m.group(3), m.group(2))
            f = {'26': math.floor, '27': math.ceil, '6': abs, '7': lambda x: min(max(x, 0.0), 1.0)}.get(m.group(1))
            if f is None: raise Opaque()
            r = tuple(f32(float(f(x))) for x in a)
        m = re.match(r'call (?:float|i32) @dx\.op\.binary\.\w+\(i32 (\d+), (\w+) (\S+), \w+ (\S+)\)', e)
        if m:
            a = val(m.group(3), m.group(2)); b = val(m.group(4), m.group(2))
            f = {'35': max, '36': min, '37': max, '38': min}.get(m.group(1))
            if f is None: raise Opaque()
            r = tuple(f(x, y) for x, y in zip(a, b))
        m = re.match(r'(fadd|fsub|fmul|fdiv|add|sub|mul|shl|or|and|lshr|ashr|xor)(?: nsw| nuw| fast| exact)* (float|i32) (\S+), (\S+)', e)
        if m:
            op, t2 = m.group(1), m.group(2); a = val(m.group(3), t2); b = val(m.group(4), t2)
            F = {'fadd': lambda x, y: f32(x + y), 'fsub': lambda x, y: f32(x - y), 'fmul': lambda x, y: f32(x * y),
                 'fdiv': lambda x, y: f32(x / y) if y else (_ for _ in ()).throw(Opaque()),
                 'add': lambda x, y: i32(x + y), 'sub': lambda x, y: i32(x - y), 'mul': lambda x, y: i32(x * y),
                 'shl': lambda x, y: i32(x << (y & 31)), 'or': lambda x, y: i32(x | y), 'and': lambda x, y: i32(x & y),
                 'lshr': lambda x, y: i32((x & 0xffffffff) >> (y & 31)), 'ashr': lambda x, y: i32(x >> (y & 31)), 'xor': lambda x, y: i32(x ^ y)}[op]
            r = tuple(F(x, y) for x, y in zip(a, b))
        m = re.match(r'(fptosi|fptoui|sitofp|uitofp) (\w+) (\S+) to (\w+)', e)
        if m:
            a = val(m.group(3), m.group(2)); op = m.group(1)
            r = tuple(ftoi(x) for x in a) if op.startswith('fpto') else tuple(f32(float(x if op == 'sitofp' else x & 0xffffffff)) for x in a)
        if r is None: raise Opaque()
    cache[v] = r
    return r

TL = re.compile(r'\s+(%\d+) = call %dx\.types\.ResRet\.(\w+) @dx\.op\.textureLoad\.\w+\(i32 66, %dx\.types\.Handle (%\d+), i32 (\S+), i32 (\S+), i32 (\S+), i32 (\S+),')
loads = []
SL = re.compile(r'\s+(%\d+) = call %dx\.types\.ResRet\.(\w+) @dx\.op\.sampleLevel\.\w+\(i32 62, %dx\.types\.Handle (%\d+), %dx\.types\.Handle (%\d+), float (\S+), float (\S+), float undef, float undef, i32 (\S+), i32 (\S+), i32 undef, float (\S+)\)')
for i in range(fn + 1, fn_end):
    m = SL.match(L[i])
    if m and m.group(3) in srv:
        try:
            key = ('S', m.group(2), m.group(3), m.group(4), m.group(7), m.group(8)) + (val(m.group(5), 'float'), val(m.group(6), 'float'), val(m.group(9), 'float'))
        except Opaque:
            key = None
        loads.append((i, m.group(1), m.group(3), key)); continue
    m = TL.match(L[i])
    if m and m.group(3) in srv:
        try:
            key = (m.group(2), m.group(3), m.group(4)) + tuple(val(c, 'i32') if c != 'undef' else 'u' for c in (m.group(5), m.group(6), m.group(7)))
        except Opaque:
            key = None
        loads.append((i, m.group(1), m.group(3), key))
first = {}; replace = {}
for i, name, h, key in loads:
    if key is None: continue
    if key in first:
        j, n0 = first[key]
        if block_of[j] in dom[block_of[i]] and j < i:
            replace[name] = (n0, i); continue
    first[key] = (i, name)
by_handle = {}
for i, name, h, key in loads: by_handle.setdefault(h, [0, 0]); by_handle[h][0] += 1; by_handle[h][1] += name in replace
print('reads per handle (total, shared):', {h: tuple(v) for h, v in by_handle.items()}, '| unresolved:', sum(k is None for *_, k in loads))
if count_only: sys.exit(0)
drop = {i for n0, i in replace.values()}
out = []
for i, l in enumerate(L):
    if i in drop: continue
    out.append(l)
t = '\n'.join(out)
for name, (n0, _) in replace.items():
    t = re.sub(re.escape(name) + r'(?!\d)', n0, t)
t = re.sub(r'(?<![\w.])%(\d+)\b', r'%v\1', t)
t = re.sub(r'(?m)^; <label>:(\d+)', r'v\1:', t)
t = re.sub(r'(?m)^(define void @[^\n]*\{)\n', r'\1\nv0:\n', t, count=1)
open(dst, 'w', encoding='utf-8').write(t)
