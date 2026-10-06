#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# skipblend_dxil.py < postpass.ll > out.ll      env SB_K, SB_CONST, SB_REL, SB_THR, SB_GUARD, SB_CLAMP, SB_BRANCH (as in skipblend.py)
# The DXIL form of skipblend.py (see there): on a skipped frame the weight of the new frame is
# reduced where the nearest sample is farther from the pixel than it was in the frame the model
# last ran for. Same arithmetic, so a DLL built with this and the Linux files give the same output.
import os, re, sys
K = float(os.environ.get('SB_K', '32'))
CLAMP = None if os.environ.get('SB_CLAMP') == 'off' else float(os.environ.get('SB_CLAMP', '0.5'))
GUARD = os.environ.get('SB_GUARD', '1') == '1'; REL = float(os.environ.get('SB_REL', '0.1')); THR = float(os.environ.get('SB_THR', '0'))
CONST = None if os.environ.get('SB_CONST') == 'off' else float(os.environ.get('SB_CONST', '0'))   # a further constant factor on skipped frames
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


def samples(cur):
    """The nine sample values (one channel) that the resampled colour `cur` = sum(value * weight) / sum(weight) is made of."""
    m = re.match(r'fdiv fast float (%[\w.]+), %[\w.]+$', defs.get(cur, '')) or sys.exit('skipblend_dxil: the resampled colour is not a quotient')
    vals, node = [], m[1]
    def term(t):
        f = re.match(r'fmul fast float (%[\w.]+), (%[\w.]+)$', defs.get(t, ''))
        if not f:
            return None
        w = [x for x in (f[1], f[2]) if re.match(r'call float @dx\.op\.unary\.f32\(i32 21, ', defs.get(x, ''))]
        return (f[2] if w[0] == f[1] else f[1]) if len(w) == 1 else None
    while True:
        v = term(node)
        if v:
            vals.append(v); break
        a = re.match(r'fadd fast float (%[\w.]+), (%[\w.]+)$', defs.get(node, '')) or sys.exit('skipblend_dxil: unexpected shape of the weighted sum')
        va, vb = term(a[1]), term(a[2])
        if va and not vb: vals.append(va); node = a[2]
        elif vb and not va: vals.append(vb); node = a[1]
        elif va and vb: vals += [va, vb]; break
        else: sys.exit('skipblend_dxil: unexpected shape of the weighted sum')
    if len(vals) != 9:
        sys.exit(f'skipblend_dxil: {len(vals)} samples found for a pixel, expected 9')
    return vals


BRANCH = os.environ.get('SB_BRANCH', '1') == '1'
n_guard = 0
if not BRANCH:
    posx = posy = None; n_sites = 0; ren = {}; pend = None; n_guard = 0; taps = []
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
        if pend and GUARD:      # the guard against dark bands at the screen edge, as in skipblend.py
            m = re.match(r'\s*(%[\w.]+) = fmul fast float (%[\w.]+), (%[\w.]+)\s*$', L[n])
            if m and pend['w'] in (m[2], m[3]) and len(pend['cur']) < 3:
                pend['cur'][m[1]] = m[3] if m[2] == pend['w'] else m[2]
            elif m and pend['a'] in (m[2], m[3]) and len(pend['hist']) < 3:
                pend['hist'].append(m[3] if m[2] == pend['a'] else m[2])
            m = re.match(r'\s*(%[\w.]+) = fadd fast float (%[\w.]+), (%[\w.]+)\s*$', L[n])
            if m and len(pend['hist']) == 3 and (m[2] in pend['cur'] or m[3] in pend['cur']):
                pend['sum'].append((m[1], pend['cur'][m[2]] if m[2] in pend['cur'] else pend['cur'][m[3]]))
                if len(pend['sum']) == 3:
                    k = pend['k']; h = pend['hist']; curs = [cur for r, cur in pend['sum']]; sums = [r for r, cur in pend['sum']]
                    if CLAMP is not None:       # the history clamp on skipped frames, as in skipblend.py
                        a2 = ren[pend['a']]
                        for c in range(3):
                            tc = samples(curs[c]); mn, mx = tc[0], tc[0]
                            for i, v in enumerate(tc[1:]):
                                out += [f'  %sb.mn{c}{k}.{i} = call float @dx.op.binary.f32(i32 36, float {mn}, float {v})',
                                        f'  %sb.mx{c}{k}.{i} = call float @dx.op.binary.f32(i32 35, float {mx}, float {v})']
                                mn, mx = f'%sb.mn{c}{k}.{i}', f'%sb.mx{c}{k}.{i}'
                            out += [f'  %sb.rg{c}{k} = fsub fast float {mx}, {mn}', f'  %sb.sl{c}{k} = fmul fast float %sb.rg{c}{k}, {fl(CLAMP)}',
                                    f'  %sb.lo{c}{k} = fsub fast float {mn}, %sb.sl{c}{k}', f'  %sb.hi{c}{k} = fadd fast float {mx}, %sb.sl{c}{k}',
                                    f'  %sb.h1{c}{k} = call float @dx.op.binary.f32(i32 36, float {h[c]}, float %sb.hi{c}{k})',
                                    f'  %sb.hc{c}{k} = call float @dx.op.binary.f32(i32 35, float %sb.h1{c}{k}, float %sb.lo{c}{k})',
                                    f'  %sb.hd{c}{k} = fsub fast float %sb.hc{c}{k}, {h[c]}', f'  %sb.ha{c}{k} = fmul fast float %sb.hd{c}{k}, {a2}',
                                    f'  %sb.rc{c}{k} = fadd fast float {sums[c]}, %sb.ha{c}{k}', f'  %sb.rs{c}{k} = select i1 %sb.skip, float %sb.rc{c}{k}, float {sums[c]}']
                            sums[c] = f'%sb.rs{c}{k}'
                    for c in range(3):
                        out += [f'  %sb.zm{c}{k} = fmul fast float {curs[c]}, {fl(REL)}',
                                f'  %sb.zt{c}{k} = call float @dx.op.binary.f32(i32 35, float %sb.zm{c}{k}, float {fl(THR)})',
                                f'  %sb.z{c}{k} = fcmp fast ole float {h[c]}, %sb.zt{c}{k}']
                    out += [f'  %sb.zz{k} = and i1 %sb.z0{k}, %sb.z1{k}', f'  %sb.zb{k} = and i1 %sb.zz{k}, %sb.z2{k}', f'  %sb.gd{k} = and i1 %sb.zb{k}, %sb.skip']
                    for c, (r, cur) in enumerate(pend['sum']):
                        out.append(f'  %sb.r{c}{k} = select i1 %sb.gd{k}, float {cur}, float {sums[c]}'); ren[r] = f'%sb.r{c}{k}'
                    n_guard += 1; pend = None; taps = []
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
            pend = {'k': k, 'w': w, 'a': a, 'cur': {}, 'hist': [], 'sum': []}
else:
    # as in skipblend.py: one branch per output pixel, taken on skipped frames only
    posx = posy = None; n_sites = 0; ren = {}; lab = {}; pend = None; cur_label = '%0'
    for n in range(e1, len(L)):
        l = L[n]
        for a, b in ren.items():
            l = re.sub(rf'{re.escape(a)}(?![\w.])', b, l)
        if ' = phi ' in l:
            for a, b in lab.items():
                l = re.sub(rf', {re.escape(a)} \]', f', {b} ]', l)
        m = re.match(r'; <label>:(\d+)', L[n])
        if m:
            cur_label = '%' + m[1]
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
        if pend:
            m = re.match(r'\s*(%[\w.]+) = fmul fast float (%[\w.]+), (%[\w.]+)\s*$', L[n])
            if m and pend['w'] in (m[2], m[3]) and len(pend['cur']) < 3:
                pend['cur'][m[1]] = m[3] if m[2] == pend['w'] else m[2]; pend['lines'].append(L[n])
            elif m and pend['a'] in (m[2], m[3]) and len(pend['hist']) < 3:
                pend['hist'].append(m[3] if m[2] == pend['a'] else m[2]); pend['lines'].append(L[n])
            m = re.match(r'\s*(%[\w.]+) = fadd fast float (%[\w.]+), (%[\w.]+)\s*$', L[n])
            if m and len(pend['hist']) == 3 and (m[2] in pend['cur'] or m[3] in pend['cur']):
                pend['sum'].append((m[1], pend['cur'][m[2]] if m[2] in pend['cur'] else pend['cur'][m[3]])); pend['lines'].append(L[n])
                if len(pend['sum']) == 3:
                    k = pend['k']; h = pend['hist']; w, a = pend['w'], pend['a']
                    curs = [cur for r, cur in pend['sum']]; sums = [r for r, cur in pend['sum']]
                    c_ = [f'  br i1 %sb.skip, label %sb.T{k}, label %sb.M{k}', '', f'sb.T{k}:']
                    for ax, pos, dj in (('x', pend['posx'], '%sb.djx'), ('y', pend['posy'], '%sb.djy')):
                        c_ += [f'  %sb.rn{ax}{k} = call float @dx.op.unary.f32(i32 26, float {pos})', f'  %sb.dn{ax}{k} = fsub fast float {pos}, %sb.rn{ax}{k}',
                               f'  %sb.pp{ax}{k} = fadd fast float {pos}, {dj}', f'  %sb.rp{ax}{k} = call float @dx.op.unary.f32(i32 26, float %sb.pp{ax}{k})',
                               f'  %sb.dp{ax}{k} = fsub fast float %sb.pp{ax}{k}, %sb.rp{ax}{k}',
                               f'  %sb.n2{ax}{k} = fmul fast float %sb.dn{ax}{k}, %sb.dn{ax}{k}', f'  %sb.p2{ax}{k} = fmul fast float %sb.dp{ax}{k}, %sb.dp{ax}{k}']
                    c_ += [f'  %sb.Dn{k} = fadd fast float %sb.n2x{k}, %sb.n2y{k}', f'  %sb.Dp{k} = fadd fast float %sb.p2x{k}, %sb.p2y{k}',
                           f'  %sb.dd{k} = fsub fast float %sb.Dp{k}, %sb.Dn{k}', f'  %sb.ex{k} = fmul fast float %sb.dd{k}, {fl(K)}',
                           f'  %sb.g{k} = call float @dx.op.unary.f32(i32 21, float %sb.ex{k})',
                           f'  %sb.gc{k} = call float @dx.op.binary.f32(i32 36, float %sb.g{k}, float 1.000000e+00)'] + (
                           [f'  %sb.gm{k} = fmul fast float %sb.gc{k}, {fl(CONST)}'] if CONST is not None else []) + [
                           f'  %sb.om{k} = fsub fast float 1.000000e+00, ' + (f'%sb.gm{k}' if CONST is not None else f'%sb.gc{k}'), f'  %sb.ao{k} = fmul fast float {a}, %sb.om{k}',
                           f'  %sb.gw{k} = fsub fast float 1.000000e+00, %sb.ao{k}', f'  %sb.wm{k} = fmul fast float {w}, %sb.gw{k}',
                           f'  %sb.wn{k} = call float @dx.op.binary.f32(i32 36, float %sb.wm{k}, float 1.000000e+00)',
                           f'  %sb.an{k} = fsub fast float 1.000000e+00, %sb.wn{k}']
                    sub = {w: f'%sb.wn{k}', a: f'%sb.an{k}'}
                    for x in pend['lines']:
                        r = re.match(r'\s*(%[\w.]+) = ', x)[1]
                        sub[r] = f'%sb.t{k}.{r[1:]}'
                    for x in pend['lines']:
                        y = re.sub(r'\s*;.*$', '', x.rstrip())
                        for p, q in sub.items():
                            y = re.sub(rf'{re.escape(p)}(?![\w.])', q, y)
                        c_.append(y)
                    mix = [sub[r] for r in sums]
                    if CLAMP is not None:
                        for c in range(3):
                            tc = samples(curs[c]); mn, mx = tc[0], tc[0]
                            for i, v in enumerate(tc[1:]):
                                c_ += [f'  %sb.mn{c}{k}.{i} = call float @dx.op.binary.f32(i32 36, float {mn}, float {v})',
                                       f'  %sb.mx{c}{k}.{i} = call float @dx.op.binary.f32(i32 35, float {mx}, float {v})']
                                mn, mx = f'%sb.mn{c}{k}.{i}', f'%sb.mx{c}{k}.{i}'
                            c_ += [f'  %sb.rg{c}{k} = fsub fast float {mx}, {mn}', f'  %sb.sl{c}{k} = fmul fast float %sb.rg{c}{k}, {fl(CLAMP)}',
                                   f'  %sb.lo{c}{k} = fsub fast float {mn}, %sb.sl{c}{k}', f'  %sb.hi{c}{k} = fadd fast float {mx}, %sb.sl{c}{k}',
                                   f'  %sb.h1{c}{k} = call float @dx.op.binary.f32(i32 36, float {h[c]}, float %sb.hi{c}{k})',
                                   f'  %sb.hc{c}{k} = call float @dx.op.binary.f32(i32 35, float %sb.h1{c}{k}, float %sb.lo{c}{k})',
                                   f'  %sb.hd{c}{k} = fsub fast float %sb.hc{c}{k}, {h[c]}', f'  %sb.ha{c}{k} = fmul fast float %sb.hd{c}{k}, %sb.an{k}',
                                   f'  %sb.rc{c}{k} = fadd fast float {mix[c]}, %sb.ha{c}{k}']
                            mix[c] = f'%sb.rc{c}{k}'
                    if GUARD:
                        for c in range(3):
                            c_ += [f'  %sb.zm{c}{k} = fmul fast float {curs[c]}, {fl(REL)}',
                                   f'  %sb.zt{c}{k} = call float @dx.op.binary.f32(i32 35, float %sb.zm{c}{k}, float {fl(THR)})',
                                   f'  %sb.z{c}{k} = fcmp fast ole float {h[c]}, %sb.zt{c}{k}']
                        c_ += [f'  %sb.zz{k} = and i1 %sb.z0{k}, %sb.z1{k}', f'  %sb.gd{k} = and i1 %sb.zz{k}, %sb.z2{k}'] + [
                               f'  %sb.rg.{c}{k} = select i1 %sb.gd{k}, float {curs[c]}, float {mix[c]}' for c in range(3)]
                        mix = [f'%sb.rg.{c}{k}' for c in range(3)]
                    c_ += [f'  br label %sb.M{k}', '', f'sb.M{k}:'] + [f'  %sb.r{c}{k} = phi float [ {mix[c]}, %sb.T{k} ], [ {sums[c]}, {cur_label} ]' for c in range(3)]
                    out += c_
                    for c in range(3):
                        ren[sums[c]] = f'%sb.r{c}{k}'
                    for p in list(lab):
                        if lab[p] == cur_label:
                            lab[p] = f'%sb.M{k}'
                    lab[cur_label] = f'%sb.M{k}'; cur_label = f'%sb.M{k}'
                    n_guard += 1; pend = None
        m = re.match(r'\s*(%[\w.]+) = fsub fast float 1\.000000e\+00, (%[\w.]+)\s*$', L[n])
        if m and re.match(r'fdiv fast float 1\.000000e\+00, ', defs.get(m[2], '')):
            pend = {'k': n_sites, 'w': m[1], 'a': m[2], 'cur': {}, 'hist': [], 'sum': [], 'lines': [], 'posx': posx, 'posy': posy}
            n_sites += 1
if (GUARD or BRANCH) and n_guard != 4:
    sys.exit(f'skipblend_dxil: {n_guard} guard sites found, expected 4')
if n_sites != 4:
    sys.exit(f'skipblend_dxil: {n_sites} blend sites found, expected 4')
sys.stdout.write('\n'.join(out))
