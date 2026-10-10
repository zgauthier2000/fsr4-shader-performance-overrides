#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# prepass_route_dxil.py < prepass.ll > out.ll
#
# The DXIL form of prepass_route.py (see there). AMD's prepass: every lane of a quad forms its
# share of 16 output channels, two quad reads and two adds per channel sum them (32 quad reads),
# and lane 0 alone adds the biases, scales, rounds, packs and stores all four words.
# Here a lane at position p works out the same 16 shares grouped by whose word they belong to
# (its own B, its horizontal neighbor's A, its vertical neighbor's D, the diagonal one's C), and
#     word(p) = (readAcrossX(A) + B) + readAcrossY(readAcrossX(C) + D)
# 12 quad reads, and each lane finishes and stores one word. The additions are AMD's, in the same
# grouping: bit-exact. AMD's own code for the sums and for lane 0 stays, without its store, and is
# dropped by the driver as dead code (removing it would renumber every value after it).
import re
import sys

L = sys.stdin.read().split('\n')
die = lambda m: sys.exit(f'prepass_route_dxil: {m}')
strip = lambda l: re.sub(r'\s*;.*$', '', l.rstrip())
name = lambda l: (re.match(r'\s*(%[\w.]+) = ', l) or [None, None])[1]
defs = {name(l): strip(l).split(' = ', 1)[1] for l in L if name(l)}
V = r'%[\w.]+'
sw = []
for n, l in enumerate(L):
    m = re.match(rf'\s*({V}) = call float @dx\.op\.quadOp\.f32\(i32 123, float ({V}), i8 0\)', l)
    if not m:
        continue
    a = re.match(rf'\s*({V}) = fadd fast float {re.escape(m[1])}, {re.escape(m[2])}\s*(;.*)?$', L[n + 1])
    b = a and re.match(rf'\s*({V}) = call float @dx\.op\.quadOp\.f32\(i32 123, float {re.escape(a[1])}, i8 1\)', L[n + 2])
    if b:
        sw.append(dict(n=n, x=m[2], s=a[1], v=b[1]))
if len(sw) != 16:
    die(f'{len(sw)} channel sums found, expected 16')


def norm(lines, off, drop):
    """the lines with their own values numbered in order and the weights' offset called OFF"""
    ren, out = {off: 'OFF'}, []
    for l in lines:
        l = strip(l)
        if not l.strip() or name(l) in drop:
            continue
        if name(l):
            ren[name(l)] = f'T{len(ren)}'
        out.append(re.sub(V, lambda t: ren.get(t[0], t[0]), l.strip()))
    return out


def block(k):
    lines = L[sw[k - 1]['n'] + 3:sw[k]['n']]
    m = re.match(rf'\s*({V}) = add i32 ({V}), (\d+)\s*(;.*)?$', lines[0])
    if m:
        return lines, m[1], m[2], int(m[3])
    m = re.match(rf'\s*({V}) = call i32 @dx\.op\.tertiary\.i32\(i32 49, i32 (\d+), i32 (\d+), i32 ({V})\)', lines[0]) or die(f'unexpected offset of channel {k}')      # UMad(step, k, base)
    return lines, m[1], m[4], int(m[2]) * int(m[3])


l1, off1, BASE, STEP = block(1)
T = norm(l1, off1, {off1})
for k in range(2, 16):
    lk, ok, bk, ck = block(k)
    if bk != BASE or ck != STEP * k or norm(lk, ok, {ok}) != T:
        die(f'channel {k} is not built like channel 1')
n0 = sw[0]['n']
cnt = 0
while cnt < len(T):          # channel 0: the same number of instructions before its first quad read
    n0 -= 1
    if strip(L[n0]).strip():
        cnt += 1
if norm(L[n0:sw[0]['n']], BASE, set()) != T:
    die('channel 0 is not built like channel 1')
if not re.match(r'T\d+ = call float @dx\.op\.dot2AddHalf\.f32\(', T[-1]):
    die('a channel does not end in its last product')
# lane 0's part
cn = sw[15]['n'] + 3
pm = re.match(rf'\s*({V}) = and i32 ({V}), 3\s*(;.*)?$', L[cn]) or die('quad position not where expected')
if not re.match(rf'\s*{V} = icmp eq i32 {re.escape(pm[1])}, 0', L[cn + 1]) or not re.match(r'\s*br i1 ', L[cn + 2]):
    die('the lane-0 test is not where expected')
t0 = cn + 3
t1 = next(n for n in range(t0, len(L)) if re.match(r'\s*br ', L[n]))
tail = L[t0:t1]
tdef = {name(l): n for n, l in enumerate(tail) if name(l)}
st = [(n, m) for n, l in enumerate(tail) for m in [re.match(rf'\s*call void @dx\.op\.rawBufferStore\.i32\(i32 140, %dx\.types\.Handle ({V}), i32 ({V}), i32 undef, i32 ({V}), i32 ({V}), i32 ({V}), i32 ({V}), i8 15, i32 4\)', l)] if m]
if len(st) != 1:
    die('lane 0 does not store its four words in one store')
sn, sm = st[0]
words = [sm[3], sm[4], sm[5], sm[6]]
if not all('@dx.op.pack4x8.i32(' in defs.get(w, '') for w in words):
    die('unexpected packing of the words')
tot = {}          # channel -> its total in lane 0's code
for k in range(16):
    m = next((nm for nm in tdef if re.match(rf'fadd fast float {re.escape(sw[k]["s"])}, {re.escape(sw[k]["v"])}$', defs[nm])), None) or die(f'total of channel {k} not found')
    tot[m] = k
bl = [(nm, m) for nm in tdef for m in [re.match(rf'call %dx\.types\.ResRet\.i32 @dx\.op\.rawBufferLoad\.i32\(i32 139, %dx\.types\.Handle ({V}), i32 (\d+), i32 undef, i8 15, i32 4\)$', defs[nm])] if m]
if len(bl) != 4 or [int(m[2]) for _, m in bl] != [int(bl[0][1][2]) + 16 * i for i in range(4)]:
    die('unexpected bias loads')


def needs(ids, stop=()):
    want, todo = set(), list(ids)
    while todo:
        i = todo.pop()
        if i in tdef and i not in stop and tdef[i] not in want:
            want.add(tdef[i]); todo += re.findall(V, defs[i])
    return [tail[n] for n in sorted(want)]


# word 0's code from its totals and bias words to its pack, as the pattern for every lane's word
bias0 = [nm for nm in tdef if re.match(rf'extractvalue %dx\.types\.ResRet\.i32 {re.escape(bl[0][0])}, [0-3]$', defs[nm])]
w0 = needs([words[0]], stop=set(tot) | set(bias0))
used_tot = [t for t in tot if any(re.search(rf'{re.escape(t)}(?![\w.])', strip(l).split(' = ', 1)[1]) for l in w0)]
if sorted(tot[t] for t in used_tot) != [0, 1, 2, 3] or len(bias0) != 4:
    die('word 0 is not made of channels 0 to 3')
P = '  '
new = [f'{P}%rt.p = and i32 {pm[2]}, 3', f'{P}%rt.c1 = xor i32 %rt.p, 1', f'{P}%rt.c2 = xor i32 %rt.p, 2', f'{P}%rt.c3 = xor i32 %rt.p, 3']
X = {}
for r, wid in (('B', '%rt.p'), ('A', '%rt.c1'), ('D', '%rt.c2'), ('C', '%rt.c3')):
    new += [f'{P}%rt.w{r} = mul i32 {wid}, {STEP * 4}', f'{P}%rt.o{r}0 = add i32 {BASE}, %rt.w{r}'] + [f'{P}%rt.o{r}{j} = add i32 %rt.o{r}0, {STEP * j}' for j in range(1, 4)]
    for j in range(4):
        sub = lambda t: f'%rt.o{r}{j}' if t[0] == 'OFF' else f'%rt.{r}{j}.{t[0][1:]}'
        code = [re.sub(r'\b(OFF|T\d+)\b', sub, l) for l in T]
        new += [P + c for c in code]; X[r, j] = code[-1].split(' = ')[0]
for j in range(4):
    new += [f'{P}%rt.ha{j} = call float @dx.op.quadOp.f32(i32 123, float {X["A", j]}, i8 0)', f'{P}%rt.s1{j} = fadd fast float %rt.ha{j}, {X["B", j]}',
            f'{P}%rt.hc{j} = call float @dx.op.quadOp.f32(i32 123, float {X["C", j]}, i8 0)', f'{P}%rt.s2{j} = fadd fast float %rt.hc{j}, {X["D", j]}']
for j in range(4):
    new += [f'{P}%rt.v{j} = call float @dx.op.quadOp.f32(i32 123, float %rt.s2{j}, i8 1)', f'{P}%rt.t{j} = fadd fast float %rt.s1{j}, %rt.v{j}']
# the bias word of this lane, then word 0's code on this lane's totals
hb = bl[0][1][1]
ren = {}
pre = needs([hb, sm[1], sm[2]])
for l in pre + w0:
    ren[name(l)] = f'%rt.x{name(l)[1:]}'
for t in used_tot:
    ren[t] = f'%rt.t{tot[t]}'
for nm in bias0:
    ren[nm] = f'%rt.b{defs[nm][-1]}'
fix = lambda l: re.sub(V, lambda t: ren.get(t[0], t[0]), strip(l))
new += [fix(l) for l in pre]
new += [f'{P}%rt.bo1 = shl i32 %rt.p, 4', f'{P}%rt.bo = add i32 %rt.bo1, {bl[0][1][2]}',
        f'{P}%rt.br = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle {ren.get(hb, hb)}, i32 %rt.bo, i32 undef, i8 15, i32 4)'] + \
       [f'{P}%rt.b{i} = extractvalue %dx.types.ResRet.i32 %rt.br, {i}' for i in range(4)]
new += [fix(l) for l in w0]
new += [f'{P}%rt.so = shl i32 %rt.p, 2', f'{P}%rt.sa = add i32 {ren.get(sm[2], sm[2])}, %rt.so',
        f'{P}call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle {ren.get(sm[1], sm[1])}, i32 %rt.sa, i32 undef, i32 {ren[words[0]]}, i32 undef, i32 undef, i32 undef, i8 1, i32 4)']
out = L[:cn + 2] + new + L[cn + 2:t0 + sn] + L[t0 + sn + 1:]
sys.stdout.write('\n'.join(out))
