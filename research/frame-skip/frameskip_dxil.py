#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# frameskip_dxil.py prepass < prepass.ll > out.ll
# frameskip_dxil.py model <row bytes of the class: 15392, 30752 or 61472> <pass number> < passN.ll > out.ll
#
# NOT bit-exact. The DXIL form of frameskip.py (see there): every other frame the model is skipped
# and the postpass uses the model's output of the frame before. Same decisions, same mark, same
# place in the working buffer, so a DLL built with this and the Linux files give the same output.
import re
import sys

mode = sys.argv[1]
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
        '  %fs.neg = and i1 %fs.js, %fs.jnz', '  %fs.k1 = and i1 %fs.neg, %fs.big', '  %fs.skip = and i1 %fs.k1, %fs.nr',
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
    out, n_st = [], 0
    for n, l in enumerate(L):
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
    if not n_st:
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
               f'  %fs.mblk = select i1 %fs.mYb, i32 {4096 * 4}, i32 {48 * 4}', f'  %fs.mrw = mul i32 %fs.mYr, {MR}', f'  %fs.ma1 = add i32 %fs.mrw, {MB}', '  %fs.ma2 = add i32 %fs.ma1, %fs.mblk',
               '  %fs.mX2 = shl i32 %fs.mX, 3', '  %fs.madr = add i32 %fs.ma2, %fs.mX2']
    if dc:
        mv_code += [f'  %fs.mdn = select i1 {dc[1]}, float {dc[3]}, float {dc[4]}'] + (['  %fs.mds = fsub fast float -0.000000e+00, %fs.mdn'] if dc[2] == 'gt' else ['  %fs.mds = fmul fast float %fs.mdn, 1.000000e+00']) + [
                    '  %fs.mdb = call i32 @dx.op.bitcastF32toI32(i32 127, float %fs.mds)']
    else:
        mv_code += ['  %fs.mdb = and i32 0, 0']
    mv_code += [f'  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle {H}, i32 %fs.madr, i32 undef, i32 %fs.mval, i32 %fs.mdb, i32 undef, i32 undef, i8 3, i32 4)',
                '  br label %fs.mM', '', 'fs.mM:']
    # put it after the line L[mv_at] of the output; later phis that named the block now name fs.mM
    marker = L[mv_at]
    i = next(k for k, l in enumerate(out) if l == marker)
    tail = out[i + 1:]
    for k, l in enumerate(tail):
        if ' = phi ' in l:
            tail[k] = re.sub(rf'{re.escape(blk if blk != "%fs.cont" else "%0")} \]', '%fs.mM ]', l)
    out = out[:i + 1] + mv_code + tail
    if need_bc and dc:
        j = next(k for k, l in enumerate(out) if l.startswith('declare float @dx.op.unary.f32('))
        out[j:j] = [f'declare i32 @dx.op.bitcastF32toI32(i32, float) {out[j].rsplit(" ", 1)[1]}', '']
    sys.stderr.write(f"frameskip_dxil: motion store after line {mv_at}, depth {'yes' if dc else 'no'}\n")
    sys.stderr.write(f'frameskip_dxil: {n_st} tensor stores made conditional, row size {S}\n')
# the rest of the entry block is now the block fs.cont
res, past = [], False
LAST = 'fs.cont2' if 'fs.cont2:' in out else 'fs.cont'
for l in out:
    if l == LAST + ':':
        past = True
    elif past and ' = phi ' in l:
        l = re.sub(r'%0 \]', f'%{LAST} ]', l)
    res.append(l)
sys.stdout.write('\n'.join(res))
