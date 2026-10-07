#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# motionpost_dxil.py < postpass.ll > out.ll      (AMD's postpass; run before skipblend_dxil.py)
# The DXIL form of motionpost.py (see there). On a skipped frame each output pixel takes the model's
# result from where its content was a frame ago (the motion the prepass stored, frameskip.py), and the
# cell vectors that result is made of are read back from where the last frame that ran the model kept
# them, instead of being worked out again. Same arithmetic and same places in the working buffer, so a
# DLL built with this and the Linux files give the same output.
import os, re, sys
L = sys.stdin.read().split('\n')
text = '\n'.join(L)
die = lambda m: sys.exit(f'motionpost_dxil: {m}')
S = next((x for x in (15392, 30752, 61472) if re.search(rf'\bi32 {x}\b', text)), None) or die('no known row size')
width = S // 16 - 2; REGION = (width * 9 // 16 + 2) * S
MARK = REGION + S + 128; MBASE = REGION + S; CBASE = REGION * 3 // 2 + S + 16
M1, M2, TAG = 0x5A17C0DE, 0x0A110E57, 0xA5A5A5A5
s32 = lambda v: v - (1 << 32) if v & 0x80000000 else v
strip = lambda l: re.sub(r'\s*;.*$', '', l.rstrip())
d0 = next(n for n, l in enumerate(L) if l.startswith('define void @'))
gl = [n for n in range(d0, len(L)) if re.match(r'\s*%[\w.]+ = icmp uge i32 (%[\w.]+), (%[\w.]+)', L[n])][:2]
ge = [re.match(r'\s*%[\w.]+ = icmp uge i32 (%[\w.]+), (%[\w.]+)', L[n]) for n in gl]
X, WC = ge[0][1], ge[0][2]; Y, HC = ge[1][1], ge[1][2]
e1 = next(n for n in range(d0 + 1, len(L)) if re.match(r'\s*(br|ret|switch) ', L[n]))
br = next(n for n in range(gl[1], len(L)) if re.match(r'\s*br i1 ', L[n]))      # the pass's own early-out
START = re.match(r'\s*br i1 %[\w.]+, label %[\w.]+, label %(\d+)', L[br])[1]
at = next(n for n, l in enumerate(L) if re.match(rf'; <label>:{START}\b', l))
end = next(n for n, l in enumerate(L) if re.match(rf'\s*%[\w.]+ = shl i32 {re.escape(X)}, 1\s*$', l))
PX = re.match(r'\s*(%[\w.]+) = ', L[end])[1]
m = re.match(rf'\s*(%[\w.]+) = shl i32 {re.escape(Y)}, 1\s*$', L[end + 1]) or die('pixel row not where expected'); PY = m[1]
region = L[at + 1:end]
name = lambda l: (re.match(r'\s*(%[\w.]+) = ', l) or [None, None])[1]
used_after = set(re.findall(r'%[\w.]+', '\n'.join(strip(l) for l in L[end:])))
words = [name(l) for l in region if name(l) in used_after and '@dx.op.pack4x8.i32(' in l]
if len(words) != 4:
    die(f'{len(words)} words of the cell vector found, expected 4')
cut = max(n for n, l in enumerate(region) if name(l) in words) + 1
tail = region[cut:]; region = region[:cut]
rdef = [name(l) for l in region if name(l)]
rlab = [m[1] for l in region for m in [re.match(r'; <label>:(\d+)', l)] if m]
LASTB = rlab[-1] if rlab else None
if any(l.startswith('; <label>') for l in tail) or set(rdef) & set(re.findall(r'%[\w.]+', '\n'.join(strip(l) for l in tail))) or (set(rdef) & used_after) - set(words):
    die('the head is not separable from what follows it')
ann = next((m for l in L for m in [re.search(r'@dx\.op\.annotateHandle\(i32 216, %dx\.types\.Handle (%[\w.]+), (%dx\.types\.ResourceProperties \{ i32 4107, i32 0 \})\)', l)] if m), None) or die('working buffer not found')
if not d0 < next(i for i, l in enumerate(L) if re.match(rf'\s*{re.escape(ann[1])} = ', l)) < e1:
    die('the working buffer handle is not created in the entry block')
if not any(l.startswith('declare') and '@dx.op.rawBufferLoad.i32(' in l for l in L):
    die('@dx.op.rawBufferLoad.i32 is not declared')
H = '%mp.hd'
ld = lambda p, adr, mask: [f'  {p}r = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle {H}, i32 {adr}, i32 undef, i8 {mask}, i32 4)'] + \
                          [f'  {p}{k} = extractvalue %dx.types.ResRet.i32 {p}r, {k}' for k in range(4) if mask >> k & 1]


def sclamp(p, v, lo, hi):
    return [f'  {p}c1 = icmp slt i32 {v}, {lo}', f'  {p}c2 = select i1 {p}c1, i32 {lo}, i32 {v}', f'  {p}c3 = icmp sgt i32 {p}c2, {hi}', f'  {p} = select i1 {p}c3, i32 {hi}, i32 {p}c2']


head = [f'  {H} = call %dx.types.Handle @dx.op.annotateHandle(i32 216, %dx.types.Handle {ann[1]}, {ann[2]})'] + ld('%mp.v', MARK, 3) + [
        f'  %mp.e1 = icmp eq i32 %mp.v0, {s32(M1)}', f'  %mp.e2 = icmp eq i32 %mp.v1, {s32(M2)}', '  %mp.skip = and i1 %mp.e1, %mp.e2',
        # one stored entry per 4x4 output pixels (2x2 cells)
        f'  %mp.xq = lshr i32 {X}, 1', f'  %mp.yq = lshr i32 {Y}, 1', '  %mp.yr = lshr i32 %mp.yq, 1', '  %mp.yo = and i32 %mp.yq, 1', '  %mp.yb = icmp ne i32 %mp.yo, 0',
        f'  %mp.blk = select i1 %mp.yb, i32 {4096 * 4}, i32 {48 * 4}', f'  %mp.rw = mul i32 %mp.yr, {S}', f'  %mp.a1 = add i32 %mp.rw, {MBASE}', '  %mp.a2 = add i32 %mp.a1, %mp.blk',
        '  %mp.x2 = shl i32 %mp.xq, 3', '  %mp.adr = add i32 %mp.a2, %mp.x2'] + ld('%mp.m', '%mp.adr', 1) + [
        '  %mp.xs = shl i32 %mp.m0, 16', '  %mp.dx0 = ashr i32 %mp.xs, 16', '  %mp.dy0 = ashr i32 %mp.m0, 16'] + sclamp('%mp.dx1', '%mp.dx0', -254, 254) + sclamp('%mp.dy1', '%mp.dy0', -254, 254) + [
        '  %mp.dx = select i1 %mp.skip, i32 %mp.dx1, i32 0', '  %mp.dy = select i1 %mp.skip, i32 %mp.dy1, i32 0',
        '  %mp.mx = ashr i32 %mp.dx, 1', '  %mp.my = ashr i32 %mp.dy, 1', '  %mp.rx = and i32 %mp.dx, 1', '  %mp.ry = and i32 %mp.dy, 1',
        '  %mp.nrx = xor i32 %mp.rx, 1', '  %mp.nry = xor i32 %mp.ry, 1',
        '  %mp.ox = icmp ne i32 %mp.rx, 0', '  %mp.oy = icmp ne i32 %mp.ry, 0', '  %mp.oxy = and i1 %mp.ox, %mp.oy',
        f'  %mp.wm = add i32 {WC}, -1', f'  %mp.hm = add i32 {HC}, -1',
        f'  %mp.xa = add i32 {X}, %mp.mx', f'  %mp.ya = add i32 {Y}, %mp.my', '  %mp.xb = add i32 %mp.xa, 1', '  %mp.yb2 = add i32 %mp.ya, 1'] + \
       sclamp('%mp.X0', '%mp.xa', 0, '%mp.wm') + sclamp('%mp.Y0', '%mp.ya', 0, '%mp.hm') + sclamp('%mp.X1', '%mp.xb', 0, '%mp.wm') + sclamp('%mp.Y1', '%mp.yb2', 0, '%mp.hm')


def addr(p, x, y):
    return [f'  {p}ar = mul i32 {y}, {S}', f'  {p}ab = add i32 {p}ar, {CBASE}', f'  {p}ax = shl i32 {x}, 4', f'  {p}a = add i32 {p}ab, {p}ax']


def kept(p, x, y):
    """the vector kept for cell (x, y): {p}d0..3, and {p}ok when no word of it was cleared"""
    o = addr(p, x, y) + ld(f'{p}l', f'{p}a', 15)
    for i in range(4):
        o += [f'  {p}d{i} = xor i32 {p}l{i}, {s32(TAG)}', f'  {p}n{i} = icmp ne i32 {p}l{i}, 0']
    return o + [f'  {p}n01 = and i1 {p}n0, {p}n1', f'  {p}n23 = and i1 {p}n2, {p}n3', f'  {p}ok = and i1 {p}n01, {p}n23']


def body(k, xs, ys):
    """the head for cell (xs, ys); k = '00' keeps the shader's own names (their numbering must stay as it was)"""
    sub = {X: xs, Y: ys}
    if k != '00':
        for d in rdef:
            sub[d] = f'%mp{k}.v{d[1:]}'
        for b in rlab:
            sub['%' + b] = f'%mp{k}.b{b}'
    sub['%' + START] = f'%mp.T{k}'
    o = []
    for l in region:
        m = re.match(r'; <label>:(\d+)', l)
        if m:
            o += [l] if k == '00' else ['', f'mp{k}.b{m[1]}:']
            continue
        l = strip(l) if k != '00' else l
        code, sep, com = l.partition(';')
        code = re.sub(r'%[\w.]+', lambda t: sub.get(t[0], t[0]), code)
        o.append(code + sep + com)
    last = (('%' + LASTB) if k == '00' else f'%mp{k}.b{LASTB}') if LASTB else f'%mp.T{k}'
    return o, [sub.get(w, w) for w in words], last


out = L[:at + 1] + head
b, bw, blast = body('00', '%mp.X0', '%mp.Y0')
out += ['  br i1 %mp.skip, label %mp.C00, label %mp.L00', '', 'mp.C00:'] + kept('%mp.k00', '%mp.X0', '%mp.Y0') + ['  br label %mp.L00', '', 'mp.L00:']
out += [f'  %mp.h{i} = phi i32 [ 0, %{START} ], [ %mp.k00d{i}, %mp.C00 ]' for i in range(4)] + [f'  %mp.have = phi i1 [ false, %{START} ], [ %mp.k00ok, %mp.C00 ]']
out += ['  br i1 %mp.have, label %mp.M00, label %mp.T00', '', 'mp.T00:'] + b + addr('%mp.s', '%mp.X0', '%mp.Y0') + [f'  %mp.sv{i} = xor i32 {bw[i]}, {s32(TAG)}' for i in range(4)]
out += [f'  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle {H}, i32 %mp.sa, i32 undef, i32 %mp.sv0, i32 %mp.sv1, i32 %mp.sv2, i32 %mp.sv3, i8 15, i32 4)', '  br label %mp.M00', '', 'mp.M00:']
W = {'00': [f'%mp.W00.{i}' for i in range(4)]}
out += [f'  {W["00"][i]} = phi i32 [ %mp.h{i}, %mp.L00 ], [ {bw[i]}, {blast} ]' for i in range(4)]
cur = '%mp.M00'
for k, (xs, ys, cond) in (('10', ('%mp.X1', '%mp.Y0', '%mp.ox')), ('01', ('%mp.X0', '%mp.Y1', '%mp.oy')), ('11', ('%mp.X1', '%mp.Y1', '%mp.oxy'))):
    b, bw, blast = body(k, xs, ys)
    out += [f'  br i1 {cond}, label %mp.C{k}, label %mp.M{k}', '', f'mp.C{k}:'] + kept(f'%mp.k{k}', xs, ys)
    out += [f'  br i1 %mp.k{k}ok, label %mp.J{k}, label %mp.T{k}', '', f'mp.T{k}:'] + b + [f'  br label %mp.J{k}', '', f'mp.J{k}:']
    out += [f'  %mp.v{k}.{i} = phi i32 [ %mp.k{k}d{i}, %mp.C{k} ], [ {bw[i]}, {blast} ]' for i in range(4)] + [f'  br label %mp.M{k}', '', f'mp.M{k}:']
    W[k] = [f'%mp.W{k}.{i}' for i in range(4)]
    out += [f'  {W[k][i]} = phi i32 [ %mp.v{k}.{i}, %mp.J{k} ], [ {W["00"][i]}, {cur} ]' for i in range(4)]
    cur = f'%mp.M{k}'
out += tail
# the vector each position's pixel code gets
w0 = W['00']; sel = {(1, 1): w0, (0, 0): [], (1, 0): [], (0, 1): []}
for i in range(4):
    out += [f'  %mp.s00a{i} = select i1 %mp.oy, i32 {W["11"][i]}, i32 {W["10"][i]}', f'  %mp.s00b{i} = select i1 %mp.oy, i32 {W["01"][i]}, i32 {w0[i]}',
            f'  %mp.s00.{i} = select i1 %mp.ox, i32 %mp.s00a{i}, i32 %mp.s00b{i}', f'  %mp.s10.{i} = select i1 %mp.oy, i32 {W["01"][i]}, i32 {w0[i]}',
            f'  %mp.s01.{i} = select i1 %mp.ox, i32 {W["10"][i]}, i32 {w0[i]}']
    sel[(0, 0)].append(f'%mp.s00.{i}'); sel[(1, 0)].append(f'%mp.s10.{i}'); sel[(0, 1)].append(f'%mp.s01.{i}')
# the pixel each position's code writes
out += [f'  %mp.bx = shl i32 {X}, 1', f'  %mp.by = shl i32 {Y}, 1', f'  {PX} = add i32 %mp.bx, %mp.rx', f'  {PY} = add i32 %mp.by, %mp.ry']
rest = L[end + 2:]
xor = {}
for n, l in enumerate(rest):
    m = re.match(rf'(\s*)(%[\w.]+) = or i32 ({re.escape(PX)}|{re.escape(PY)}), 1\s*(;.*)?$', l)
    if m:
        rest[n] = f'{m[1]}{m[2]} = add i32 ' + ('%mp.bx, %mp.nrx' if m[3] == PX else '%mp.by, %mp.nry'); xor[m[2]] = m[3]
blocks, b0, nw = [], 0, 0
fin = next(n for n, l in enumerate(rest) if l.startswith('}'))
for n in range(fin):
    if '@dx.op.textureStore.' in rest[n]:
        nw += 1
        if nw % 3 == 0 and nw < 12:
            blocks.append((b0, n + 1)); b0 = n + 1
blocks.append((b0, fin))
if len(blocks) != 4 or nw != 12:
    die(f'{nw} stores in {len(blocks)} blocks of pixel code found, expected 12 in 4')
for a, b in blocks:
    st = next(l for l in rest[a:b] if '@dx.op.textureStore.' in l)
    cx, cy = re.search(r'@dx\.op\.textureStore\.\w+\(i32 67, %dx\.types\.Handle %[\w.]+, i32 (%[\w.]+), i32 (%[\w.]+),', st).groups()
    s = 0 if cx == PX else 1 if xor.get(cx) == PX else die('unknown pixel column'); t = 0 if cy == PY else 1 if xor.get(cy) == PY else die('unknown pixel row')
    wsub = {words[i]: sel[(s, t)][i] for i in range(4)}
    for n in range(a, b):
        code, sep, com = rest[n].partition(';')
        rest[n] = re.sub(r'%[\w.]+', lambda t_: wsub.get(t_[0], t_[0]), code) + sep + com
# what followed the head is now in the last new block
old = '%' + (LASTB or START)
for n in range(fin):
    if ' = phi ' in rest[n]:
        rest[n] = re.sub(rf'{re.escape(old)} \]', f'{cur} ]', rest[n])
if not any(l.startswith('declare') and '@dx.op.rawBufferStore.i32(' in l for l in rest):
    grp = next((m[1] for l in L for m in [re.match(r'attributes (#\d+) = \{ nounwind \}\s*$', l)] if m), None) or die('no plain "nounwind" attribute group')
    j = next(n for n, l in enumerate(rest) if l.startswith('declare'))
    rest[j:j] = [f'declare void @dx.op.rawBufferStore.i32(i32, %dx.types.Handle, i32, i32, i32, i32, i32, i32, i8, i32) {grp}', '']
sys.stdout.write('\n'.join(out + rest))
