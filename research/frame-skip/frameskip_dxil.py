#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# frameskip_dxil.py prepass < prepass.ll > out.ll
# frameskip_dxil.py model <row bytes of the class: 15392, 30752 or 61472> <pass number> < passN.ll > out.ll
#
# NOT bit-exact. The DXIL form of frameskip.py (see there): every other frame the model is skipped
# and the postpass uses the model's output of the frame before. Same decisions, same mark, same
# place in the working buffer, so a DLL built with this and the Linux files give the same output.
# FS_BRANCH as in frameskip.py (default 1; run exposure_steps_dxil.py before this tool).
import os
import re
import sys

mode = sys.argv[1]
UP = None if os.environ.get('FS_UP', '-0.1666667') == 'off' else float(os.environ.get('FS_UP', '-0.1666667'))      # FS_UP=<y> (prepass; -0.1666667 since release dll-2026-10-15; off as before): as frameskip.py; y must be negative
if UP is not None:
    import struct
    assert UP < 0, 'FS_UP: only negative thresholds are supported here'
    UPB = struct.unpack('<I', struct.pack('<f', -UP))[0]      # y < UP  <=>  sign set and |y| > |UP| (as float32 bits)
L = sys.stdin.read().split('\n')


def die(msg):
    sys.exit(f'frameskip_dxil: {msg}')


text = '\n'.join(L)
if mode == 'model':
    S = int(sys.argv[2]); npass = int(sys.argv[3]) if len(sys.argv) > 3 else 0
else:
    S = next((x for x in (15392, 30752, 61472) if re.search(rf'\bi32 {x}\b', text)), None) or die('no known row size in the prepass')
width = S // 16 - 2
REGION = (width * 9 // 16 + 2) * S
BYTE = REGION + S + 128
# the jitter of the last frame that ran the model, carried to the postpass of the skipped frame (see frameskip.py)
RELAY = REGION * 3 // 2 + (width * 9 // 16 * 15 // 16) * S
HOP, SAVE = 0, BYTE + 8
M1, M2 = 0x5A17C0DE, 0x0A110E57
s32 = lambda v: v - (1 << 32) if v & 0x80000000 else v

d0 = next(n for n, l in enumerate(L) if l.startswith('define void @'))
# end of the entry block
e1 = next(n for n in range(d0 + 1, len(L)) if re.match(r'\s*(br|ret|switch) ', L[n]))
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*?)(\s*;.*)?$', l)
    if m:
        defs[m[1]] = (n, m[2])

# the working buffer: the handle the shader's own raw-buffer stores use, traced to one made in the entry block
st = next((m for l in L for m in [re.search(r'@dx\.op\.rawBufferStore\.i32\(i32 140, %dx\.types\.Handle (%[\w.]+),', l)] if m), None) or die('no raw-buffer store')
h = st[1]
ann = re.match(r'call %dx\.types\.Handle @dx\.op\.annotateHandle\(i32 216, %dx\.types\.Handle (%[\w.]+), (%dx\.types\.ResourceProperties \{[^}]*\})\)', defs[h][1])
if ann:
    base, props = ann[1], ann[2]
    if not (d0 < defs[base][0] < e1):
        die('the working buffer handle is not created in the entry block')
    make_h = [f'  %fs.h = call %dx.types.Handle @dx.op.annotateHandle(i32 216, %dx.types.Handle {base}, {props})']
    H, after = '%fs.h', defs[base][0]
else:
    if not (d0 < defs[h][0] < e1):
        die('the working buffer handle is not created in the entry block')
    make_h, H, after = [], h, defs[h][0]


def load2(p):
    return [f'  {p}r = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle {H}, i32 {BYTE}, i32 undef, i8 3, i32 4)',
            f'  {p}a = extractvalue %dx.types.ResRet.i32 {p}r, 0', f'  {p}b = extractvalue %dx.types.ResRet.i32 {p}r, 1']


# where to split the entry block: after its last alloca and after everything the new code needs
split = max([after] + [n for n in range(d0 + 1, e1) if ' = alloca ' in L[n]])

if mode == 'model':
    code = make_h + load2('%fs.m') + [
        f'  %fs.ea = icmp eq i32 %fs.ma, {s32(M1)}', f'  %fs.eb = icmp eq i32 %fs.mb, {s32(M2)}',
        '  %fs.skip = and i1 %fs.ea, %fs.eb', '  br i1 %fs.skip, label %fs.ret, label %fs.cont', '',
        'fs.ret:', '  ret void', '', 'fs.cont:']
    if npass in (11, 12):
        src, dst = (RELAY, HOP) if npass == 11 else (HOP, SAVE)
        if not any(l.startswith('declare') and '@dx.op.threadId.i32(' in l for l in L):
            die('@dx.op.threadId.i32 is not declared in this shader')
        for fn in ('@dx.op.rawBufferLoad.i32', '@dx.op.rawBufferStore.i32'):
            if not any(l.startswith('declare') and fn + '(' in l for l in L):
                die(f'{fn} is not declared in this shader')
        code += ['  %fs.i0 = call i32 @dx.op.threadId.i32(i32 93, i32 0)', '  %fs.i1 = call i32 @dx.op.threadId.i32(i32 93, i32 1)',
                 '  %fs.i2 = call i32 @dx.op.threadId.i32(i32 93, i32 2)', '  %fs.io = or i32 %fs.i0, %fs.i1', '  %fs.ip = or i32 %fs.io, %fs.i2',
                 '  %fs.first = icmp eq i32 %fs.ip, 0', '  br i1 %fs.first, label %fs.hop, label %fs.cont2', '', 'fs.hop:',
                 f'  %fs.jr = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle {H}, i32 {src}, i32 undef, i8 3, i32 4)',
                 '  %fs.jx = extractvalue %dx.types.ResRet.i32 %fs.jr, 0', '  %fs.jy = extractvalue %dx.types.ResRet.i32 %fs.jr, 1',
                 f'  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle {H}, i32 {dst}, i32 undef, i32 %fs.jx, i32 %fs.jy, i32 undef, i32 undef, i8 3, i32 4)',
                 '  br label %fs.cont2', '', 'fs.cont2:']
    out = L[:split + 1] + code + L[split + 1:]
else:
    cb = next((m for l in L for m in [re.search(r'@dx\.op\.cbufferLoadLegacy\.\w+\(i32 59, %dx\.types\.Handle (%[\w.]+),', l)] if m), None) or die('no constant buffer load')
    C = cb[1]
    if not (d0 < defs[C][0] < e1):
        die('the constant buffer handle is not created in the entry block')
    split = max(split, defs[C][0])
    for fn in ('@dx.op.cbufferLoadLegacy.i32', '@dx.op.groupId.i32', '@dx.op.threadIdInGroup.i32', '@dx.op.rawBufferLoad.i32'):
        if not any(l.startswith('declare') and fn + '(' in l for l in L):
            die(f'{fn} is not declared in this shader')
    code = make_h + [
        f'  %fs.c4 = call %dx.types.CBufRet.i32 @dx.op.cbufferLoadLegacy.i32(i32 59, %dx.types.Handle {C}, i32 4)',
        '  %fs.width = extractvalue %dx.types.CBufRet.i32 %fs.c4, 0', '  %fs.reset = extractvalue %dx.types.CBufRet.i32 %fs.c4, 2',
        '  %fs.wlr = extractvalue %dx.types.CBufRet.i32 %fs.c4, 3',
        '  %fs.wl2 = shl i32 %fs.wlr, 1', '  %fs.big = icmp uge i32 %fs.wl2, %fs.width', '  %fs.nr = icmp eq i32 %fs.reset, 0',
        f'  %fs.c1 = call %dx.types.CBufRet.i32 @dx.op.cbufferLoadLegacy.i32(i32 59, %dx.types.Handle {C}, i32 1)',
        '  %fs.jb = extractvalue %dx.types.CBufRet.i32 %fs.c1, 2',
        '  %fs.jm = and i32 %fs.jb, 2147483647', '  %fs.jnz = icmp ne i32 %fs.jm, 0', '  %fs.js = icmp slt i32 %fs.jb, 0',
        '  %fs.neg = and i1 %fs.js, %fs.jnz', *(['  %fs.k1 = and i1 %fs.neg, %fs.big'] if UP is None else [      # FS_UP (as frameskip.py): jitter y >= FS_UP, compared on the float's bits
            '  %fs.upj = extractvalue %dx.types.CBufRet.i32 %fs.c1, 3', '  %fs.ups = icmp slt i32 %fs.upj, 0', '  %fs.upm = and i32 %fs.upj, 2147483647',
            f'  %fs.upg = icmp ugt i32 %fs.upm, {UPB}', '  %fs.uplt = and i1 %fs.ups, %fs.upg', '  %fs.upok = xor i1 %fs.uplt, true',
            '  %fs.upor = or i1 %fs.big, %fs.upok', '  %fs.k1 = and i1 %fs.neg, %fs.upor']), '  %fs.skip = and i1 %fs.k1, %fs.nr',
        '  %fs.g0 = call i32 @dx.op.groupId.i32(i32 94, i32 0)', '  %fs.g1 = call i32 @dx.op.groupId.i32(i32 94, i32 1)',
        '  %fs.t0 = call i32 @dx.op.threadIdInGroup.i32(i32 95, i32 0)',
        '  %fs.o1 = or i32 %fs.g0, %fs.g1', '  %fs.o2 = or i32 %fs.o1, %fs.t0', '  %fs.first = icmp eq i32 %fs.o2, 0',
        '  br i1 %fs.first, label %fs.do, label %fs.cont', '', 'fs.do:',
        f'  %fs.v1 = select i1 %fs.skip, i32 {s32(M1)}, i32 0', f'  %fs.v2 = select i1 %fs.skip, i32 {s32(M2)}, i32 0',
        f'  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle {H}, i32 {BYTE}, i32 undef, i32 %fs.v1, i32 %fs.v2, i32 undef, i32 undef, i8 3, i32 4)',
        '  %fs.jy = extractvalue %dx.types.CBufRet.i32 %fs.c1, 3',
        f'  %fs.or = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle {H}, i32 {RELAY}, i32 undef, i8 3, i32 4)',
        '  %fs.ox = extractvalue %dx.types.ResRet.i32 %fs.or, 0', '  %fs.oy = extractvalue %dx.types.ResRet.i32 %fs.or, 1',
        '  %fs.nx = select i1 %fs.skip, i32 %fs.ox, i32 %fs.jb', '  %fs.ny = select i1 %fs.skip, i32 %fs.oy, i32 %fs.jy',
        f'  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle {H}, i32 {RELAY}, i32 undef, i32 %fs.nx, i32 %fs.ny, i32 undef, i32 undef, i8 3, i32 4)',
        '  br label %fs.cont', '', 'fs.cont:']
    BRANCH = os.environ.get('FS_BRANCH', '1') == '1'       # two copies of the shader's work under one branch on skip, as in frameskip.py
    out, n_st = [], 0
    for n, l in enumerate(L if not BRANCH else []):
        m = re.match(r'(\s*)call void @dx\.op\.rawBufferStore\.i32\(i32 140, %dx\.types\.Handle (%[\w.]+), i32 ([^,]+), i32 undef, i32 ([^,]+), i32 ([^,]+), i32 ([^,]+), i32 ([^,]+), i8 (\d+), i32 4\)', l)
        if m and n > split:
            n_st += 1
            mask, vals = int(m[8]), [m[4], m[5], m[6], m[7]]
            out.append(f'{m[1]}%fs.s{n_st} = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle {m[2]}, i32 {m[3]}, i32 undef, i8 {mask}, i32 4)')
            new = []
            for c in range(4):
                if mask >> c & 1:
                    out += [f'{m[1]}%fs.s{n_st}c{c} = extractvalue %dx.types.ResRet.i32 %fs.s{n_st}, {c}',
                            f'{m[1]}%fs.n{n_st}c{c} = select i1 %fs.skip, i32 %fs.s{n_st}c{c}, i32 {vals[c]}']
                    new.append(f'%fs.n{n_st}c{c}')
                else:
                    new.append('undef')
            out.append(f'{m[1]}call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle {m[2]}, i32 {m[3]}, i32 undef, i32 {new[0]}, i32 {new[1]}, i32 {new[2]}, i32 {new[3]}, i8 {mask}, i32 4)')
            continue
        out.append(l)
        if n == split:
            out += code
    if not n_st and not BRANCH:
        die('no tensor stores found in the prepass')
    # Motion and nearest depth for the postpass of a skipped frame, as in frameskip.py: one entry (two words) per 4x4 output
    # pixels, written by the thread of the block's first pixel, into the second region of the working buffer.
    D = {k: v[1] for k, v in defs.items()}
    mv = None
    for n in range(split, len(L) - 3):
        a = re.match(r'\s*(%[\w.]+) = fadd fast float (%[\w.]+), (%[\w.]+)\s*$', L[n]); b = re.match(r'\s*(%[\w.]+) = fadd fast float (%[\w.]+), (%[\w.]+)\s*$', L[n + 1])
        c = re.match(r'\s*%[\w.]+ = fadd fast float (%[\w.]+), 5\.000000e-01\s*$', L[n + 2]); d = re.match(r'\s*%[\w.]+ = fadd fast float (%[\w.]+), 5\.000000e-01\s*$', L[n + 3])
        if a and b and c and d and c[1] == a[1] and d[1] == b[1]:
            def sp(m):
                p, q = m[2], m[3]
                if D.get(q, '').startswith('uitofp i32') and D.get(p, '').startswith('fmul fast float'): return p, q
                if D.get(p, '').startswith('uitofp i32') and D.get(q, '').startswith('fmul fast float'): return q, p
            sa, sb = sp(a), sp(b)
            if sa and sb:
                px = re.match(r'uitofp i32 (%[\w.]+) to float', D[sa[1]])[1]; py = re.match(r'uitofp i32 (%[\w.]+) to float', D[sb[1]])[1]
                mv = (sa[0], sb[0], n + 1, px, py); break
    if mv is None:
        die('the reprojection displacement was not found in the prepass')
    mvx, mvy, mv_at, px, py = mv
    fetch_at = None
    for k in range(split, mv_at):
        m = re.match(r'\s*%[\w.]+ = fmul fast float (%[\w.]+), (%[\w.]+)\s*$', L[k])
        if m:
            for p_, q_ in ((m[1], m[2]), (m[2], m[1])):
                e = re.match(r'extractvalue %dx\.types\.CBufRet\.f32 (%[\w.]+), 0$', D.get(p_, '')); f = re.match(r'extractvalue %dx\.types\.ResRet\.f32 (%[\w.]+), 0$', D.get(q_, ''))
                if e and f and re.search(r'@dx\.op\.cbufferLoadLegacy\.f32\(i32 59, %dx\.types\.Handle %[\w.]+, i32 2\)', D.get(e[1], '')) and '@dx.op.textureLoad.f32(' in D.get(f[1], ''):
                    fetch_at = defs[f[1]][0]
        if fetch_at:
            break
    if fetch_at is None:
        die('the motion-vector fetch was not found in the prepass')
    dc = next((m for n in range(fetch_at, split, -1) for m in [re.match(r'\s*(%[\w.]+) = fcmp fast o(lt|gt) float (%[\w.]+), (%[\w.]+)\s*$', L[n])] if m), None)
    blk = next(('%' + m[1] for k in range(mv_at, split, -1) for m in [re.match(r'; <label>:(\d+)', L[k])] if m), '%fs.cont')
    for fn in ('@dx.op.unary.f32', '@dx.op.binary.f32', '@dx.op.rawBufferStore.i32'):
        if not any(l.startswith('declare') and fn + '(' in l for l in L):
            die(f'{fn} is not declared in this shader')
    need_bc = not any(l.startswith('declare') and '@dx.op.bitcastF32toI32(' in l for l in L)
    MB, MR = REGION + S, S
    mv_code = [f'  %fs.mxy = or i32 {px}, {py}', '  %fs.mev = and i32 %fs.mxy, 3', '  %fs.mis = icmp eq i32 %fs.mev, 0', '  %fs.mdo = and i1 %fs.mis, %fs.skip',
               '  br i1 %fs.mdo, label %fs.mT, label %fs.mM', '', 'fs.mT:',
               f'  %fs.mrx = call float @dx.op.unary.f32(i32 26, float {mvx})', f'  %fs.mry = call float @dx.op.unary.f32(i32 26, float {mvy})',
               '  %fs.mcx1 = call float @dx.op.binary.f32(i32 35, float %fs.mrx, float -2.540000e+02)', '  %fs.mcx = call float @dx.op.binary.f32(i32 36, float %fs.mcx1, float 2.540000e+02)',
               '  %fs.mcy1 = call float @dx.op.binary.f32(i32 35, float %fs.mry, float -2.540000e+02)', '  %fs.mcy = call float @dx.op.binary.f32(i32 36, float %fs.mcy1, float 2.540000e+02)',
               '  %fs.mix = fptosi float %fs.mcx to i32', '  %fs.miy = fptosi float %fs.mcy to i32', '  %fs.mlx = and i32 %fs.mix, 65535', '  %fs.mly = shl i32 %fs.miy, 16', '  %fs.mval = or i32 %fs.mlx, %fs.mly',
               f'  %fs.mX = lshr i32 {px}, 2', f'  %fs.mY = lshr i32 {py}, 2', '  %fs.mYr = lshr i32 %fs.mY, 1', '  %fs.mYo = and i32 %fs.mY, 1', '  %fs.mYb = icmp ne i32 %fs.mYo, 0',
               f'  %fs.mblk = select i1 %fs.mYb, i32 {(2048 if S == 15392 else 4096) * 4}, i32 {48 * 4}', f'  %fs.mrw = mul i32 %fs.mYr, {MR}', f'  %fs.ma1 = add i32 %fs.mrw, {MB}', '  %fs.ma2 = add i32 %fs.ma1, %fs.mblk',
               '  %fs.mX2 = shl i32 %fs.mX, 3', '  %fs.madr = add i32 %fs.ma2, %fs.mX2']
    if dc:
        mv_code += [f'  %fs.mdn = select i1 {dc[1]}, float {dc[3]}, float {dc[4]}'] + (['  %fs.mds = fsub fast float -0.000000e+00, %fs.mdn'] if dc[2] == 'gt' else ['  %fs.mds = fmul fast float %fs.mdn, 1.000000e+00']) + [
                    '  %fs.mdb = call i32 @dx.op.bitcastF32toI32(i32 127, float %fs.mds)']
    else:
        mv_code += ['  %fs.mdb = and i32 0, 0']
    mv_code += [f'  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle {H}, i32 %fs.madr, i32 undef, i32 %fs.mval, i32 %fs.mdb, i32 undef, i32 undef, i8 3, i32 4)']
    need_at = False
    if dc and os.environ.get('FS_PLANE', '1') == '1':
        # "who was here a frame ago", as in frameskip.py: the block's nearness and number go to the blocks its previous position touches (atomic maximum)
        from frameskip_layout import plane_layout
        L_ = plane_layout(S); need_at = not any(l.startswith('declare') and '@dx.op.atomicBinOp.i32(' in l for l in L)
        mv_code += ['  %fs.pw = fadd float %fs.mdn, -0.000000e+00' if dc[2] == 'gt' else '  %fs.pw = fsub float 1.000000e+00, %fs.mdn',
                    '  %fs.pbits = call i32 @dx.op.bitcastF32toI32(i32 127, float %fs.pw)', f'  %fs.pk0 = lshr i32 %fs.pbits, {23 - L_["m"]}', f'  %fs.pk1 = sub i32 %fs.pk0, {(127 - 31) << L_["m"]}',
                    '  %fs.pc1 = icmp slt i32 %fs.pk1, 1', '  %fs.pc2 = select i1 %fs.pc1, i32 1, i32 %fs.pk1', f'  %fs.pc3 = icmp sgt i32 %fs.pc2, {(1 << L_["kb"]) - 1}',
                    f'  %fs.pk = select i1 %fs.pc3, i32 {(1 << L_["kb"]) - 1}, i32 %fs.pc2',
                    f'  %fs.pidy = shl i32 %fs.mY, {L_["xb"]}', '  %fs.pid = or i32 %fs.pidy, %fs.mX', f'  %fs.pkh = shl i32 %fs.pk, {L_["idb"]}', '  %fs.pkey = or i32 %fs.pkh, %fs.pid',
                    f'  %fs.pBx = add i32 {px}, %fs.mix', f'  %fs.pBy = add i32 {py}, %fs.miy', '  %fs.pBx3 = add i32 %fs.pBx, 3', '  %fs.pBy3 = add i32 %fs.pBy, 3',
                    '  %fs.ptx0 = ashr i32 %fs.pBx, 2', '  %fs.ptx1 = ashr i32 %fs.pBx3, 2', '  %fs.pty0 = ashr i32 %fs.pBy, 2', '  %fs.pty1 = ashr i32 %fs.pBy3, 2']
        for i_, (tx, ty) in enumerate((('0', '0'), ('1', '0'), ('0', '1'), ('1', '1'))):
            q = f'%fs.pt{i_}'
            mv_code += [f'  {q}ix = icmp ult i32 %fs.ptx{tx}, {L_["nx"]}', f'  {q}iy = icmp ult i32 %fs.pty{ty}, {L_["ny"]}', f'  {q}in = and i1 {q}ix, {q}iy',
                        f'  {q}x = select i1 {q}in, i32 %fs.ptx{tx}, i32 0', f'  {q}y = select i1 {q}in, i32 %fs.pty{ty}, i32 0', f'  {q}v = select i1 {q}in, i32 %fs.pkey, i32 0',
                        f'  {q}yr = lshr i32 {q}y, 1', f'  {q}yo = and i32 {q}y, 1', f'  {q}yb = icmp ne i32 {q}yo, 0', f'  {q}blk = select i1 {q}yb, i32 {L_["pb1"] * 4}, i32 {L_["pb0"] * 4}',
                        f'  {q}rw = mul i32 {q}yr, {MR}', f'  {q}a1 = add i32 {q}rw, {MB}', f'  {q}a2 = add i32 {q}a1, {q}blk', f'  {q}x4 = shl i32 {q}x, 2', f'  {q}adr = add i32 {q}a2, {q}x4',
                        f'  {q}old = call i32 @dx.op.atomicBinOp.i32(i32 78, %dx.types.Handle {H}, i32 7, i32 {q}adr, i32 undef, i32 undef, i32 {q}v)']
    mv_code += ['  br label %fs.mM', '', 'fs.mM:']
    from frameskip_layout import holes_dxil
    mv_code = holes_dxil(mv_code, S, 1)      # step past the cleared diagonals (frameskip_layout.py)
    # FS_ALPHA (default 1 with FS_BRANCH=1, since release dll-2026-10-13; as in frameskip.py): on a skipped frame every pixel's own displacement goes into the fourth channel of the
    # image the prepass writes per output pixel: dx + 64 * dy + 32 for |dx|, |dy| <= 31, -2048 for anything faster.
    ALPHA = os.environ.get('FS_ALPHA', '1' if BRANCH else '0') == '1'
    if ALPHA:
        if not BRANCH:
            die('FS_ALPHA needs the two-copy form (FS_BRANCH=1)')
        mv_code = [f'  %fs.arx = call float @dx.op.unary.f32(i32 26, float {mvx})', f'  %fs.ary = call float @dx.op.unary.f32(i32 26, float {mvy})',
                   '  %fs.aax = call float @dx.op.unary.f32(i32 6, float %fs.arx)', '  %fs.aay = call float @dx.op.unary.f32(i32 6, float %fs.ary)',
                   '  %fs.ao1 = fcmp ole float %fs.aax, 3.100000e+01', '  %fs.ao2 = fcmp ole float %fs.aay, 3.100000e+01', '  %fs.aok = and i1 %fs.ao1, %fs.ao2',
                   '  %fs.am = fmul float %fs.ary, 6.400000e+01', '  %fs.as = fadd float %fs.arx, %fs.am', '  %fs.at = fadd float %fs.as, 3.200000e+01',
                   '  %fs.acode = select i1 %fs.aok, float %fs.at, float -2.048000e+03'] + mv_code
    if BRANCH:
        # FS_BRANCH=1 (see frameskip.py): the rest of the function twice. A frame that runs the model gets AMD's code
        # unchanged; a skipped frame gets a copy without the tensor stores, which holds the motion store. The copy's
        # values and blocks are named (k.<old name>), so the numbering of the unnamed ones stays as it is.
        fe = next(n for n in range(split + 1, len(L)) if L[n] == '}')
        blk0 = blk if blk != '%fs.cont' else '%0'
        ren = {}
        for n in range(split + 1, fe):
            m = re.match(r'\s*(%[\w.]+) = ', L[n]) or re.match(r'; <label>:()(\d+)', L[n]) or re.match(r'()([A-Za-z_.][\w.]*):', L[n])
            if m:
                v = m[1] or '%' + m[2]
                ren[v] = '%k.' + v[1:]
        tok = lambda l: re.sub(r'%[\w.]+', lambda m: ren.get(m[0], m[0]), l)
        a_st = a_phi = None
        if ALPHA:
            # the image store of the skipped frame's copy; where its block can be reached without passing the motion code (the thread's
            # pixel outside the picture), the code gets a phi with the escape value on that path
            STORE = re.compile(r'(\s*call void @dx\.op\.textureStore\.f16\(i32 67, %dx\.types\.Handle %[\w.]+, i32 %[\w.]+, i32 %[\w.]+, i32 undef, half (%[\w.]+), half %[\w.]+, half %[\w.]+, half )(%[\w.]+)(, i8 15\).*)$')
            cs = [n for n in range(split + 1, fe) for m in [STORE.match(L[n])] if m and m[2] == m[3]]
            if len(cs) != 1:
                die(f'FS_ALPHA: {len(cs)} image stores of the form (r, g, b, r) found, expected 1')
            a_st = cs[0]
            if a_st < mv_at:
                die('FS_ALPHA: the image store lies before the motion code')
            b0_ = max(n for n in range(split, a_st) if re.match(r'; <label>:\d+', L[n]) or re.match(r'[A-Za-z_.][\w.]*:', L[n]) or n == split)
            ph = [n for n in range(b0_ + 1, a_st) if ' = phi ' in L[n]]
            if ph:
                a_phi = ph[-1]
                lab_at = {'%' + m[1]: n for n in range(d0, fe) for m in [re.match(r'; <label>:(\d+)', L[n])] if m}
                a_vals = []
                for lb in re.findall(r'\[ [^,\]]+, (%[\w.]+) \]', L[a_phi]):
                    if lb != '%0' and lb not in lab_at:
                        die(f'FS_ALPHA: block {lb} not found')
                    a_vals.append('%fs.acode' if lb == blk0 or (lb != '%0' and lab_at[lb] > mv_at) else '-2.048000e+03')
                if len(set(a_vals)) != 2:
                    die('FS_ALPHA: cannot tell which way into the image store passes the motion code')
            elif b0_ < mv_at:
                die('FS_ALPHA: the image store is not reached through the motion code alone')
        run, skp = [], []
        for n in range(split + 1, fe):
            l = L[n]
            run.append(re.sub(r'%0 \]', '%fs.R ]', l) if ' = phi ' in l else l)
            if re.match(r'\s*call void @dx\.op\.rawBufferStore\.i32\(', l):
                n_st += 1
                continue
            if ' = phi ' in l:
                if n > mv_at:
                    l = re.sub(rf'{re.escape(blk0)} \]', '%fs.mM ]', l)
                l = re.sub(r'%0 \]', '%fs.S ]', l)
            m = re.match(r'; <label>:(\d+)', l) or re.match(r'([A-Za-z_.][\w.]*):', l)
            if n == a_st:
                skp.append(f"  %fs.ah = fptrunc float {'%fs.aph' if a_phi else '%fs.acode'} to half")
                l = STORE.sub(lambda t: t[1] + '%fs.ah' + t[4], l)
            skp.append(f'k.{m[1]}:' if m else tok(l))
            if n == a_phi:      # the labels as the phi above names them now
                labs = re.findall(r'\[ [^,\]]+, (%[\w.]+) \]', skp[-1])
                skp.append('  %fs.aph = phi float ' + ', '.join(f'[ {v}, {lb} ]' for v, lb in zip(a_vals, labs)))
            if n == mv_at:
                skp += [tok(c) for c in mv_code]
        if not n_st:
            die('no tensor stores found in the prepass')
        out = L[:split + 1] + code + ['  br i1 %fs.skip, label %fs.S, label %fs.R', '', 'fs.R:'] + run + ['', 'fs.S:'] + skp + L[fe:]
    else:
        # put it after the line L[mv_at] of the output; later phis that named the block now name fs.mM
        marker = L[mv_at]
        i = next(k for k, l in enumerate(out) if l == marker)
        tail = out[i + 1:]
        for k, l in enumerate(tail):
            if ' = phi ' in l:
                tail[k] = re.sub(rf'{re.escape(blk if blk != "%fs.cont" else "%0")} \]', '%fs.mM ]', l)
        out = out[:i + 1] + mv_code + tail
    if need_at:
        grp = next((m[1] for l in out for m in [re.match(r'attributes (#\d+) = \{ nounwind \}\s*$', l)] if m), None) or die('no plain "nounwind" attribute group')
        j = next(k for k, l in enumerate(out) if l.startswith('declare float @dx.op.unary.f32('))
        out[j:j] = [f'declare i32 @dx.op.atomicBinOp.i32(i32, %dx.types.Handle, i32, i32, i32, i32, i32) {grp}', '']
    if need_bc and dc:
        j = next(k for k, l in enumerate(out) if l.startswith('declare float @dx.op.unary.f32('))
        out[j:j] = [f'declare i32 @dx.op.bitcastF32toI32(i32, float) {out[j].rsplit(" ", 1)[1]}', '']
    sys.stderr.write(f"frameskip_dxil: motion store after line {mv_at}, depth {'yes' if dc else 'no'}\n")
    sys.stderr.write(f"frameskip_dxil: {n_st} tensor stores {'left out of the skipped frame\'s copy' if BRANCH else 'made conditional'}, row size {S}\n")
# the rest of the entry block is now the block fs.cont
res, past = [], False
LAST = 'fs.cont2' if 'fs.cont2:' in out else 'fs.cont'
for l in out:
    if l == LAST + ':':
        past = True
    elif past and ' = phi ' in l:
        l = re.sub(r'%0 \]', f'%{LAST} ]', l)
    res.append(l)
# FS_PERSIST (prepass; default 1 with FS_ALPHA since release dll-2026-10-14; 0 = as before; as in frameskip.py): on a skipped frame the fourth channel of the
# image store carries the fourth channel of the center history tap (the fifth of the nine samples of the history image in the skipped frame's copy) instead
# of the motion code, except at the first pixel of each 2x2 cell. The tap lies in a block of its own; its value reaches the store through phis that carry 0
# on every path that does not pass it (frameskip.py: a function variable set to 0 first). It is passed on as the half it was read as (no float round trip).
if mode != 'model' and ALPHA and os.environ.get('FS_PERSIST', '1') == '1':
    L = '\n'.join(res).split('\n')
    s0 = next((n for n, l in enumerate(L) if l == 'fs.S:'), None)
    if s0 is None: die("FS_PERSIST: the skipped frame's copy (fs.S) was not found")
    fe = next(n for n in range(s0, len(L)) if L[n] == '}')
    # the motion code as narrowed for the store, and the store
    ah = [n for n in range(s0, fe) if re.match(r'\s*%fs\.ah = fptrunc float %[\w.]+ to half$', L[n])]
    if len(ah) != 1: die(f'FS_PERSIST: {len(ah)} motion-code values found, expected 1')
    st = [n for n in range(s0, fe) if re.match(r'\s*call void @dx\.op\.textureStore\.f16\(.*half %fs\.ah, i8 15\)', L[n])]
    if len(st) != 1: die(f'FS_PERSIST: {len(st)} stores of the motion code found, expected 1')
    sm = re.match(r'\s*call void @dx\.op\.textureStore\.f16\(i32 67, %dx\.types\.Handle %[\w.]+, i32 (%[\w.]+), i32 (%[\w.]+), ', L[st[0]])
    xy = [m for l in L[s0:fe] for m in [re.match(r'\s*%fs\.mxy = or i32 (%[\w.]+), (%[\w.]+)$', l)] if m]
    if len(xy) != 1 or (xy[0][1], xy[0][2]) != (sm[1], sm[2]): die('FS_PERSIST: ' + 'the pixel position of the store is not the one of the motion code')
    # the nine history taps of the skipped copy: one handle with nine samples
    taps = {}
    for n in range(s0, fe):
        m = re.match(r'\s*(%[\w.]+) = call %dx\.types\.ResRet\.f16 @dx\.op\.sampleLevel\.f16\(i32 62, %dx\.types\.Handle (%[\w.]+),', L[n])
        if m: taps.setdefault(m[2], []).append((n, m[1]))
    nine = [v for v in taps.values() if len(v) == 9]
    if len(nine) != 1: die(f'FS_PERSIST: {len(nine)} groups of nine taps in the skipped copy, expected 1')
    tn, tv = nine[0][4]
    # blocks of the skipped copy, their successors and predecessors
    blk_at, starts = {}, []
    cur = 'fs.S'
    for n in range(s0, fe):
        m = re.match(r'([A-Za-z_.][\w.]*):', L[n])
        if m: cur = m[1]; starts.append((cur, n))
        blk_at[n] = cur
    succ = {b: [] for b, _ in starts}
    for n in range(s0, fe):
        for t in re.findall(r'label %([\w.]+)', L[n]):
            if t not in succ[blk_at[n]]: succ[blk_at[n]].append(t)
    pred = {b: [] for b, _ in starts}
    for b, ts in succ.items():
        for t in ts:
            if t in pred: pred[t].append(b)
    T, S = blk_at[tn], blk_at[st[0]]
    reach, todo = set(), list(succ[T])
    while todo:
        b = todo.pop()
        if b in reach or b not in succ: continue
        reach.add(b); todo += succ[b]
    phis, memo = {}, {}
    def v_end(b): return '%pp.w' if b == T else v_start(b)
    def v_start(b):
        if b not in reach: return '0xH0000'
        if b in memo: return memo[b]
        nm = f'%pp.p{len(memo)}'; memo[b] = nm
        phis[b] = f'  {nm} = phi half ' + ', '.join(f'[ {v_end(p)}, %{p} ]' for p in pred[b])
        return nm
    if S == T:
        if tn > st[0]: die('FS_PERSIST: ' + 'the store lies before the tap in the same block')
        val = '%pp.w'
    else:
        val = v_start(S)
    out = []
    lab_line = {n: b for b, n in starts}
    for n, l in enumerate(L):
        if n == st[0]:
            out += [f'  %pp.xy = or i32 {sm[1]}, {sm[2]}', '  %pp.o = and i32 %pp.xy, 1', '  %pp.first = icmp eq i32 %pp.o, 0', f'  %pp.v = select i1 %pp.first, half %fs.ah, half {val}']
            out.append(l.replace('half %fs.ah, i8 15)', 'half %pp.v, i8 15)')); continue
        out.append(l)
        if n in lab_line and lab_line[n] in phis: out.append(phis[lab_line[n]])
        if n == tn: out.append(f'  %pp.w = extractvalue %dx.types.ResRet.f16 {tv}, 3')
    res = out
    sys.stderr.write(f'frameskip_dxil: FS_PERSIST: center tap {tv} in {T}, store in {S}, {len(phis)} phis\n')
# FS_PERSISTRUN (prepass; default 1 with FS_PERSIST since release dll-2026-10-14; 0 = as before; as in frameskip.py): the copy that runs on frames with the network
# (fs.R ... fs.S) writes the center history tap's fourth channel in place of AMD's repeated red, at every pixel, carried to the store through phis as above.
if mode != 'model' and ALPHA and os.environ.get('FS_PERSIST', '1') == '1' and os.environ.get('FS_PERSISTRUN', '1') == '1':
    L = '\n'.join(res).split('\n')
    r0 = next((n for n, l in enumerate(L) if l == 'fs.R:'), None); r1 = next((n for n, l in enumerate(L) if l == 'fs.S:'), None)
    if r0 is None or r1 is None or r1 < r0: die('FS_PERSISTRUN: the run copy (fs.R ... fs.S) was not found')
    ST = re.compile(r'(\s*call void @dx\.op\.textureStore\.f16\(i32 67, %dx\.types\.Handle %[\w.]+, i32 %[\w.]+, i32 %[\w.]+, i32 undef, half (%[\w.]+), half %[\w.]+, half %[\w.]+, half )(%[\w.]+)(, i8 15\).*)$')
    st = [n for n in range(r0, r1) for m in [ST.match(L[n])] if m and m[2] == m[3]]
    if len(st) != 1: die(f'FS_PERSISTRUN: {len(st)} image stores of the form (r, g, b, r) in the run copy, expected 1')
    taps = {}
    for n in range(r0, r1):
        m = re.match(r'\s*(%[\w.]+) = call %dx\.types\.ResRet\.f16 @dx\.op\.sampleLevel\.f16\(i32 62, %dx\.types\.Handle (%[\w.]+),', L[n])
        if m: taps.setdefault(m[2], []).append((n, m[1]))
    nine = [v for v in taps.values() if len(v) == 9]
    if len(nine) != 1: die(f'FS_PERSISTRUN: {len(nine)} groups of nine taps in the run copy, expected 1')
    tn, tv = nine[0][4]
    blk_at, starts = {}, []; cur = 'fs.R'
    for n in range(r0, r1):
        m = re.match(r'; <label>:(\d+)', L[n]) or re.match(r'([A-Za-z_.][\w.]*):', L[n])
        if m: cur = m[1]; starts.append((cur, n))
        blk_at[n] = cur
    succ = {b: [] for b, _ in starts}
    for n in range(r0, r1):
        for t in re.findall(r'label %([\w.]+)', L[n]):
            if t not in succ[blk_at[n]]: succ[blk_at[n]].append(t)
    pred = {b: [] for b, _ in starts}
    for b, ts in succ.items():
        for t in ts:
            if t in pred: pred[t].append(b)
    T, S = blk_at[tn], blk_at[st[0]]
    reach, todo = set(), list(succ[T])
    while todo:
        b = todo.pop()
        if b in reach or b not in succ: continue
        reach.add(b); todo += succ[b]
    phis, memo = {}, {}
    def v_end(b): return '%pr.w' if b == T else v_start(b)
    def v_start(b):
        if b not in reach: return '0xH0000'
        if b in memo: return memo[b]
        nm = f'%pr.p{len(memo)}'; memo[b] = nm
        phis[b] = f'  {nm} = phi half ' + ', '.join(f'[ {v_end(p)}, %{p} ]' for p in pred[b])
        return nm
    if S == T:
        if tn > st[0]: die('FS_PERSISTRUN: the store lies before the tap in the same block')
        val = '%pr.w'
    else:
        val = v_start(S)
    out = []; lab_line = {n: b for b, n in starts}
    for n, l in enumerate(L):
        if n == st[0]:
            m = ST.match(l); out.append(f'{m[1]}{val}{m[4]}'); continue
        out.append(l)
        if n in lab_line and lab_line[n] in phis: out.append(phis[lab_line[n]])
        if n == tn: out.append(f'  %pr.w = extractvalue %dx.types.ResRet.f16 {tv}, 3')
    res = out
    sys.stderr.write(f'frameskip_dxil: FS_PERSISTRUN: center tap {tv} in {T}, store in {S}, {len(phis)} phis\n')
sys.stdout.write('\n'.join(res))
