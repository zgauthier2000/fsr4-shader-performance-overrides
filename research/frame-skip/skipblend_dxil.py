#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# skipblend_dxil.py < postpass.ll > out.ll      env SB_K (default 32), SB_CONST (as in skipblend.py)
# The DXIL form of skipblend.py (see there): on a skipped frame the weight of the new frame is
# reduced where the nearest sample is farther from the pixel than it was in the frame the model
# last ran for. Same arithmetic, so a DLL built with this and the Linux files give the same output.
import os, re, sys
K = float(os.environ.get('SB_K', '32'))
CONST = float(os.environ['SB_CONST']) if os.environ.get('SB_CONST') else None   # a further constant factor on skipped frames
L = sys.stdin.read().split('\n')
text = '\n'.join(L)
S = next((x for x in (15392, 30752, 61472) if re.search(rf'\bi32 {x}\b', text)), None) or sys.exit('skipblend_dxil: no known row size')
width = S // 16 - 2
BYTE = (width * 9 // 16 + 2) * S + S + 128
M1, M2 = 0x5A17C0DE, 0x0A110E57
s32 = lambda v: v - (1 << 32) if v & 0x80000000 else v
defs = {m[1]: m[2] for l in L for m in [re.match(r'\s*(%[\w.]+) = (.*?)(\s*;.*)?$', l)] if m}
d0 = next(n for n, l in enumerate(L) if l.startswith('define void @'))
e1 = next(n for n in range(d0 + 1, len(L)) if re.match(r'\s*(br|ret|switch) ', L[n]))
ann = next((m for l in L for m in [re.search(r'@dx\.op\.annotateHandle\(i32 216, %dx\.types\.Handle (%[\w.]+), (%dx\.types\.ResourceProperties \{ i32 4107, i32 0 \})\)', l)] if m), None) or sys.exit('skipblend_dxil: working buffer not found')
cb = next((m for l in L for m in [re.search(r'@dx\.op\.cbufferLoadLegacy\.f32\(i32 59, %dx\.types\.Handle (%[\w.]+), i32 1\)', l)] if m), None) or sys.exit('skipblend_dxil: constants not found')
for v in (ann[1], cb[1]):
    n = next(i for i, l in enumerate(L) if re.match(rf'\s*{re.escape(v)} = ', l))
    if not d0 < n < e1:
        sys.exit('skipblend_dxil: a handle is not created in the entry block')
for fn in ('@dx.op.rawBufferLoad.i32', '@dx.op.unary.f32', '@dx.op.binary.f32', '@dx.op.cbufferLoadLegacy.f32'):
    if not any(l.startswith('declare') and fn + '(' in l for l in L):
        sys.exit(f'skipblend_dxil: {fn} is not declared')
head = [f'  %sb.h = call %dx.types.Handle @dx.op.annotateHandle(i32 216, %dx.types.Handle {ann[1]}, {ann[2]})',
        f'  %sb.r = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %sb.h, i32 {BYTE}, i32 undef, i8 15, i32 4)'] + \
       [f'  %sb.v{k} = extractvalue %dx.types.ResRet.i32 %sb.r, {k}' for k in range(4)] + [
        f'  %sb.e1 = icmp eq i32 %sb.v0, {s32(M1)}', f'  %sb.e2 = icmp eq i32 %sb.v1, {s32(M2)}', '  %sb.skip = and i1 %sb.e1, %sb.e2',
        '  %sb.pjx = call float @dx.op.bitcastI32toF32(i32 126, i32 %sb.v2)', '  %sb.pjy = call float @dx.op.bitcastI32toF32(i32 126, i32 %sb.v3)',
        f'  %sb.c1 = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle {cb[1]}, i32 1)',
        '  %sb.jx = extractvalue %dx.types.CBufRet.f32 %sb.c1, 2', '  %sb.jy = extractvalue %dx.types.CBufRet.f32 %sb.c1, 3',
        '  %sb.djx = fsub fast float %sb.pjx, %sb.jx', '  %sb.djy = fsub fast float %sb.pjy, %sb.jy']
fl = lambda v: '0x%016X' % __import__('struct').unpack('<Q', __import__('struct').pack('<d', __import__('struct').unpack('<f', __import__('struct').pack('<f', v))[0]))[0]
out = L[:e1] + head
posx = posy = None; n_sites = 0; ren = {}
for n in range(e1, len(L)):
    l = L[n]
    for a, b in ren.items():
        l = re.sub(rf'{re.escape(a)}(?![\w.])', b, l)
    m = re.match(r'\s*(%[\w.]+) = fadd fast float (%[\w.]+), (%[\w.]+)\s*$', L[n])
    if m:
        for u in (m[2], m[3]):
            e = re.match(r'fadd fast float (%[\w.]+), -5\.000000e-01$', defs.get(u, ''))
            j = e and re.match(r'extractvalue %dx\.types\.CBufRet\.f32 %[\w.]+, ([23])$', defs.get(e[1], ''))
            if j:
                if j[1] == '2': posx = m[1]
                else: posy = m[1]
    if l.startswith('declare float @dx.op.unary.f32(') and not any('@dx.op.bitcastI32toF32(' in x for x in L if x.startswith('declare')):
        attr = l.rsplit(' ', 1)[1]
        out += [f'declare float @dx.op.bitcastI32toF32(i32, i32) {attr}', '']
    out.append(l)
    m = re.match(r'\s*(%[\w.]+) = fsub fast float 1\.000000e\+00, (%[\w.]+)\s*$', L[n])
    if m and re.match(r'fdiv fast float 1\.000000e\+00, ', defs.get(m[2], '')):
        k = n_sites; n_sites += 1; w, a = m[1], m[2]; c = []
        for ax, pos, dj in (('x', posx, '%sb.djx'), ('y', posy, '%sb.djy')):
            c += [f'  %sb.rn{ax}{k} = call float @dx.op.unary.f32(i32 26, float {pos})', f'  %sb.dn{ax}{k} = fsub fast float {pos}, %sb.rn{ax}{k}',
                  f'  %sb.pp{ax}{k} = fadd fast float {pos}, {dj}', f'  %sb.rp{ax}{k} = call float @dx.op.unary.f32(i32 26, float %sb.pp{ax}{k})',
                  f'  %sb.dp{ax}{k} = fsub fast float %sb.pp{ax}{k}, %sb.rp{ax}{k}',
                  f'  %sb.n2{ax}{k} = fmul fast float %sb.dn{ax}{k}, %sb.dn{ax}{k}', f'  %sb.p2{ax}{k} = fmul fast float %sb.dp{ax}{k}, %sb.dp{ax}{k}']
        c += [f'  %sb.Dn{k} = fadd fast float %sb.n2x{k}, %sb.n2y{k}', f'  %sb.Dp{k} = fadd fast float %sb.p2x{k}, %sb.p2y{k}',
              f'  %sb.dd{k} = fsub fast float %sb.Dp{k}, %sb.Dn{k}', f'  %sb.ex{k} = fmul fast float %sb.dd{k}, {fl(K)}',
              f'  %sb.g{k} = call float @dx.op.unary.f32(i32 21, float %sb.ex{k})',
              f'  %sb.gc{k} = call float @dx.op.binary.f32(i32 36, float %sb.g{k}, float 1.000000e+00)',
              ] + ([f'  %sb.gm{k} = fmul fast float %sb.gc{k}, {fl(CONST)}'] if CONST is not None else []) + [
              f'  %sb.om{k} = fsub fast float 1.000000e+00, ' + (f'%sb.gm{k}' if CONST is not None else f'%sb.gc{k}'), f'  %sb.ao{k} = fmul fast float {a}, %sb.om{k}',
              f'  %sb.gw{k} = fsub fast float 1.000000e+00, %sb.ao{k}', f'  %sb.wm{k} = fmul fast float {w}, %sb.gw{k}',
              f'  %sb.wn{k} = call float @dx.op.binary.f32(i32 36, float %sb.wm{k}, float 1.000000e+00)',
              f'  %sb.an{k} = fsub fast float 1.000000e+00, %sb.wn{k}',
              f'  %sb.w2{k} = select i1 %sb.skip, float %sb.wn{k}, float {w}', f'  %sb.a2{k} = select i1 %sb.skip, float %sb.an{k}, float {a}']
        out += c; ren[w] = f'%sb.w2{k}'; ren[a] = f'%sb.a2{k}'
if n_sites != 4:
    sys.exit(f'skipblend_dxil: {n_sites} blend sites found, expected 4')
sys.stdout.write('\n'.join(out))
