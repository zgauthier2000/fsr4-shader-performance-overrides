#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# prepass_gather_dxil.py < prepass.ll > out.ll
#
# The DXIL form of the prepass rewrite (see research/postpass-and-prepass/prepass_gather.py for
# the SPIR-V one). The part of the FSR 4.1.1 INT8 prepass that prepares the model's input works on
# quads of four pixels. AMD's shader: every lane forms 16 channel sums d = dot(its pixel's 7
# features, its weights), 4 Dot2AddHalf each; two quad reads and two adds per channel make
# (d_own + d_across_x) + (d_across_y + d_diagonal), the same in all four lanes; then lane 0 alone
# adds the bias, scales, rounds, packs and stores all 16 channels as four words.
# Here every lane first reads the other three pixels' features (21 quad reads instead of 32) and
# then, for the four channels of "its" word only, computes the four d's itself, with the same
# instructions in the same order, and adds them in the same grouping; it then finishes and stores
# that one word. Same arithmetic on the same numbers: bit-exact. A pixel's weights sit at
# 512*y + 16*x + 32*channel, so a neighbor's weights are at the lane's own offset with bit 4 (x)
# or bit 9 (y) flipped. AMD's lane-0 code stays, without its store, and is dropped by the driver.
import re
import sys

L = sys.stdin.read().split('\n')


def die(msg):
    sys.exit(f'prepass_gather_dxil: {msg}')


defs, where = {}, {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*?)(\s*;.*)?$', l)
    if m:
        defs[m[1]] = m[2].strip(); where[m[1]] = n
rhs = lambda v: defs.get(v, '')


def call(v, name):
    """operands of  call ... @dx.op.<name>(...)  as a list of 'type value' strings' values"""
    m = re.match(rf'call .*? @dx\.op\.{re.escape(name)}\((.*)\)$', rhs(v))
    if not m:
        return None
    parts, depth, cur = [], 0, ''
    for ch in m[1]:
        if ch == '{': depth += 1
        if ch == '}': depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur.strip()); cur = ''
        else:
            cur += ch
    parts.append(cur.strip())
    return [p.rsplit(' ', 1)[-1] if not p.endswith('}') else p for p in parts]


def binop(v, op):
    m = re.match(rf'{op} (?:fast |nuw |nsw |exact )*\w+ (\S+), (\S+)$', rhs(v))
    return (m[1], m[2]) if m else None


# ---- the tensor store: the last rawBufferStore with four values
st = [n for n, l in enumerate(L) if re.match(r'\s*call void @dx\.op\.rawBufferStore\.i32\(i32 140,', l) and 'i8 15' in l]
if len(st) != 1:
    die(f'expected one four-word store, found {len(st)}')
sm = re.match(r'(\s*)call void @dx\.op\.rawBufferStore\.i32\(i32 140, %dx\.types\.Handle (%[\w.]+), i32 (%[\w.]+), i32 undef, i32 (%[\w.]+), i32 (%[\w.]+), i32 (%[\w.]+), i32 (%[\w.]+), i8 15, i32 4\)', L[st[0]])
if not sm:
    die('unexpected store')
ind, shandle, soff = sm[1], sm[2], sm[3]
words = sm.groups()[3:7]
# ---- the guard in front of the block with the store: br i1 (lane & 3) == 0
blk = max(n for n in range(st[0]) if L[n].startswith('; <label>:'))
gb = max(n for n in range(blk) if L[n].strip())
g = re.match(r'\s*br i1 (%[\w.]+), label', L[gb])
ic = re.match(r'icmp eq i32 (%[\w.]+), 0$', rhs(g[1])) if g else None
if not ic or not re.match(r'and i32 %[\w.]+, 3$', rhs(ic[1])):
    die('the store is not guarded by (lane & 3) == 0')
q = ic[1]


def total_d(v):
    """v = (d + across_x(d)) + across_y(d + across_x(d))  ->  d"""
    o = binop(v, 'fadd')
    if o:
        for s1, sv in (o, o[::-1]):
            c = call(sv, 'quadOp.f32')
            if c and c[1] == s1 and c[2] == '1':
                p = binop(s1, 'fadd')
                if p:
                    for d, sh in (p, p[::-1]):
                        c2 = call(sh, 'quadOp.f32')
                        if c2 and c2[1] == d and c2[2] == '0':
                            return d
    return None


def chain(d):
    """the Dot2AddHalf chain ending in d -> (weights handle, weights offset, [features], zero)"""
    feats, v = [], d
    while True:
        c = call(v, 'dot2AddHalf.f32')
        if not c:
            die('unexpected dot-product chain')
        feats = [c[4], c[5]] + feats
        ax, acc = c[2], c[1]
        if not acc.startswith('%'):
            break
        v = acc
    f = re.match(r'fptrunc float (%[\w.]+) to half$', rhs(ax))
    lw = call(f[1], 'legacyF16ToF32')
    wd = re.match(r'and i32 (%[\w.]+), 65535$', rhs(lw[1]))
    ev = re.match(r'extractvalue %dx\.types\.ResRet\.i32 (%[\w.]+), 0$', rhs(wd[1]))
    ld = call(ev[1], 'rawBufferLoad.i32')
    return ld[1], ld[2], feats, acc


# ---- per word and element: the channel's weight offset and its bias
info = []           # [word][element] = (weight offset relative to the base, bias load offset, bias component)
base = wh = feats = None
for wv in words:
    pk = call(wv, 'pack4x8.i32')
    if not pk or pk[1] != '2':
        die('unexpected packing')
    row = []
    for e in pk[2:6]:
        fs = re.match(r'fptosi float (%[\w.]+) to i32$', rhs(e))
        rn = call(fs[1], 'unary.f32') if fs else None
        ml = binop(rn[1], 'fmul') if rn and rn[0] == '26' else None
        if not ml or ml[1] != '6.400000e+01':
            die('unexpected scaling')
        ad = binop(ml[0], 'fadd')
        tot = bias = None
        for a, b in (ad, ad[::-1]):
            if total_d(a):
                tot, bias = a, b
        bc = re.match(r'bitcast i32 (%[\w.]+) to float$', rhs(bias)) if bias else None
        be = re.match(r'extractvalue %dx\.types\.ResRet\.i32 (%[\w.]+), (\d)$', rhs(bc[1])) if bc else None
        bl = call(be[1], 'rawBufferLoad.i32') if be else None
        if not bl or not bl[2].isdigit():
            die('unexpected bias')
        h_, off, f_, zero = chain(total_d(tot))
        row.append((off, int(bl[2]), int(be[2]), h_, f_, zero))
    info.append(row)
# the base offset: every weight offset is the base, base + constant, or UMad(a, b, base) with constants
def split(o):
    ad = binop(o, 'add')
    if ad and ad[1].isdigit():
        return ad[0], int(ad[1])
    um = call(o, 'tertiary.i32')
    if um and um[0] == '49' and um[1].isdigit() and um[2].isdigit():
        return um[3], int(um[1]) * int(um[2])
    return o, 0
offs_all = [e[0] for r in info for e in r]
bases = {split(o)[0] for o in offs_all if split(o)[1]}
if len(bases) != 1 or any(split(o)[0] not in bases and o not in bases for o in offs_all):
    die('the weight offsets are not base + constant')
base = bases.pop()
rel = lambda o: 0 if o == base else split(o)[1]
feats = info[0][0][4]
zero = info[0][0][5]
if len(feats) != 8 or any(e[4] != feats for r in info for e in r):
    die('the channels do not share their features')
for r in info:
    if [e[2] for e in r] != [0, 1, 2, 3] or len({e[1] for e in r}) != 1:
        die('unexpected bias layout')
wh_line = L[where[info[0][0][3]]]
sh_line = L[where[shandle]]
hsrc = lambda line: re.search(r'(call %dx\.types\.Handle @dx\.op\.annotateHandle\(.*\))', line)[1]

code = []
emit = lambda s: code.append(ind + s)
# the store offset is computed inside the guarded block: repeat that computation here
first, last = blk, st[0]
cl = {}
def clone(v):
    if not v.startswith('%') or v not in where or not (first < where[v] < last):
        return v
    if v not in cl:
        new = f'%pg.c{len(cl)}'
        cl[v] = new
        text = re.sub(r'%[\w.]+', lambda m: clone(m[0]), rhs(v))
        emit(f'{new} = {text}')
    return cl[v]

emit(f'%pg.wh = {hsrc(wh_line)}')
emit(f'%pg.sh = {hsrc(sh_line)}')
for k in (1, 2, 3):
    emit(f'%pg.is{k} = icmp eq i32 {q}, {k}')
emit(f'%pg.b0 = add i32 {base}, 0')
for P, x in ((1, 16), (2, 512), (3, 528)):
    emit(f'%pg.b{P} = xor i32 {base}, {x}')
F = {0: feats}
for P in (1, 2, 3):
    F[P] = []
for i, f in enumerate(feats):
    if not f.startswith('%'):
        for P in (1, 2, 3):
            F[P].append(f)                         # a constant feature (the padding zero)
        continue
    # read as halves: converting them to float for the read would make vkd3d-proton translate the
    # whole shader with different floating-point rules (it switches mode when it meets such a
    # conversion), and the picture would no longer match AMD's
    for P in (1, 2, 3):
        emit(f'%pg.f{P}.{i} = call half @dx.op.quadOp.f16(i32 123, half {f}, i8 {P - 1})')
        F[P].append(f'%pg.f{P}.{i}')
def select(name, vals):
    cur = str(vals[0])
    for k in (1, 2, 3):
        emit(f'{name}.{k} = select i1 %pg.is{k}, i32 {vals[k]}, i32 {cur}')
        cur = f'{name}.{k}'
    return cur
bo = select('%pg.bo', [r[0][1] for r in info])
emit(f'%pg.bl = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %pg.wh, i32 {bo}, i32 undef, i8 15, i32 4)')
es = []
for j in range(4):
    off = select(f'%pg.o{j}', [rel(info[k][j][0]) for k in range(4)])
    ds = []
    for P in range(4):
        t = f'%pg.{j}.{P}'
        emit(f'{t}.a = add i32 %pg.b{P}, {off}')
        emit(f'{t}.l = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %pg.wh, i32 {t}.a, i32 undef, i8 15, i32 4)')
        acc = zero
        for w in range(4):
            u = f'{t}.{w}'
            emit(f'{u}.w = extractvalue %dx.types.ResRet.i32 {t}.l, {w}')
            emit(f'{u}.lo = and i32 {u}.w, 65535')
            emit(f'{u}.hi = lshr i32 {u}.w, 16')
            emit(f'{u}.fl = call float @dx.op.legacyF16ToF32(i32 131, i32 {u}.lo)')
            emit(f'{u}.fh = call float @dx.op.legacyF16ToF32(i32 131, i32 {u}.hi)')
            emit(f'{u}.hl = fptrunc float {u}.fl to half')
            emit(f'{u}.hh = fptrunc float {u}.fh to half')
            emit(f'{u}.d = call float @dx.op.dot2AddHalf.f32(i32 162, float {acc}, half {u}.hl, half {u}.hh, half {F[P][2 * w]}, half {F[P][2 * w + 1]})')
            acc = f'{u}.d'
        ds.append(acc)
    t = f'%pg.t{j}'
    emit(f'{t}.x = fadd fast float {ds[0]}, {ds[1]}')
    emit(f'{t}.y = fadd fast float {ds[2]}, {ds[3]}')
    emit(f'{t}.s = fadd fast float {t}.x, {t}.y')
    emit(f'{t}.bi = extractvalue %dx.types.ResRet.i32 %pg.bl, {j}')
    emit(f'{t}.bf = bitcast i32 {t}.bi to float')
    emit(f'{t}.a = fadd fast float {t}.s, {t}.bf')
    emit(f'{t}.m = fmul fast float {t}.a, 6.400000e+01')
    emit(f'{t}.r = call float @dx.op.unary.f32(i32 26, float {t}.m)')
    emit(f'{t}.e = fptosi float {t}.r to i32')
    es.append(f'{t}.e')
emit('%pg.word = call i32 @dx.op.pack4x8.i32(i32 220, i8 2, ' + ', '.join(f'i32 {e}' for e in es) + ')')
so = clone(soff)
emit(f'%pg.q4 = shl i32 {q}, 2')
emit(f'%pg.so = add i32 {so}, %pg.q4')
emit('call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %pg.sh, i32 %pg.so, i32 undef, i32 %pg.word, i32 undef, i32 undef, i32 undef, i8 1, i32 4)')

if not any(l.startswith('declare half @dx.op.quadOp.f16') for l in L):
    at = next(n for n, l in enumerate(L) if l.startswith('declare float @dx.op.quadOp.f32'))
    L[at] = L[at] + '\n\n' + L[at].replace('declare float @dx.op.quadOp.f32(i32, float, i8)', 'declare half @dx.op.quadOp.f16(i32, half, i8)')
out = []
for n, l in enumerate(L):
    if n == gb:
        out += code
    if n == st[0]:
        continue                                   # AMD's store goes; its block is now dead code
    out.append(l)
sys.stderr.write(f'prepass_gather_dxil: rewritten ({len(code)} instructions added)\n')
sys.stdout.write('\n'.join(out))
