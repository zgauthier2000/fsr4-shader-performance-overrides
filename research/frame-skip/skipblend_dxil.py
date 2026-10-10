#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# skipblend_dxil.py < postpass.ll > out.ll      env SB_K, SB_CONST, SB_REL, SB_THR, SB_GUARD, SB_CLAMP, SB_BRANCH, SB_UNCOV, SB_UNCOV_OFFS, SB_REST (as in skipblend.py)
# The DXIL form of skipblend.py (see there): on a skipped frame the weight of the new frame is
# reduced where the nearest sample is farther from the pixel than it was in the frame the model
# last ran for. Same arithmetic, so a DLL built with this and the Linux files give the same output.
import os, re, sys
# the changed-content tests of skipblend.py are on by default; "off" switches one off
for _k, _v in (('SB_PART', '0.25'), ('SB_BRIGHT', '0.25'), ('SB_BRIGHTSYM', '1'), ('SB_SAMPLE', '1'), ('SB_SAMPLEFULL', '1'), ('SB_SAMPLEALL', '1')):
    os.environ.setdefault(_k, _v)
    if os.environ[_k] == 'off':
        del os.environ[_k]
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
UNCOV = os.environ.get('SB_UNCOV', 'depth') == 'depth'
REST = UNCOV and os.environ.get('SB_REST', '1') == '1'
ENTRY_LABEL = '%0'
if UNCOV:
    # as in skipblend.py: a cell is flagged when a nearer surface that moves differently was in front of its content a frame ago
    gl_ = [n for n in range(d0, len(L)) if re.match(r'\s*%[\w.]+ = icmp uge i32 (%[\w.]+), (%[\w.]+)', L[n])][:2]
    ge_ = [re.match(r'\s*%[\w.]+ = icmp uge i32 (%[\w.]+), (%[\w.]+)', L[n]) for n in gl_]
    if len(ge_) != 2:
        sys.exit('skipblend_dxil: thread bounds not found')
    BLINE = next(n for n in range(gl_[1], len(L)) if re.match(r'\s*br i1 ', L[n]))      # the pass's own early-out: the flag is worked out just before it
    FL_BLOCK = next(('%' + m[1] for k in range(BLINE, e1, -1) for m in [re.match(r'; <label>:(\d+)', L[k])] if m), '%0')
    Xc, WCc = ge_[0][1], ge_[0][2]; Yc, HCc = ge_[1][1], ge_[1][2]
    REGION_ = (width * 9 // 16 + 2) * S; MBASE = REGION_ + S

    def sclamp(p, v, lo, hi):
        return [f'  {p}k1 = icmp slt i32 {v}, {lo}', f'  {p}k2 = select i1 {p}k1, i32 {lo}, i32 {v}', f'  {p}k3 = icmp sgt i32 {p}k2, {hi}', f'  {p} = select i1 {p}k3, i32 {hi}, i32 {p}k2']

    def sabs(p, v):
        return [f'  {p}n = sub i32 0, {v}', f'  {p}s = icmp slt i32 {v}, 0', f'  {p} = select i1 {p}s, i32 {p}n, i32 {v}']

    def mread(p, x, y):
        return sclamp(f'{p}xc', x, 0, '%sm.wm') + sclamp(f'{p}yc', y, 0, '%sm.hm') + [
            f'  {p}xq = lshr i32 {p}xc, 1', f'  {p}yq = lshr i32 {p}yc, 1', f'  {p}yr = lshr i32 {p}yq, 1', f'  {p}yo = and i32 {p}yq, 1', f'  {p}yb = icmp ne i32 {p}yo, 0',
            f'  {p}bk = select i1 {p}yb, i32 {(2048 if S == 15392 else 4096) * 4}, i32 {48 * 4}', f'  {p}rw = mul i32 {p}yr, {S}', f'  {p}a1 = add i32 {p}rw, {MBASE}', f'  {p}a2 = add i32 {p}a1, {p}bk',
            f'  {p}x2 = shl i32 {p}xq, 3', f'  {p}ix = add i32 {p}a2, {p}x2',
            f'  {p}mr = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %sb.h, i32 {p}ix, i32 undef, i8 1, i32 4)', f'  {p}m = extractvalue %dx.types.ResRet.i32 {p}mr, 0',
            f'  {p}xs = shl i32 {p}m, 16', f'  {p}d0 = ashr i32 {p}xs, 16', f'  {p}e0 = ashr i32 {p}m, 16'] + sclamp(f'{p}dx', f'{p}d0', -254, 254) + sclamp(f'{p}dy', f'{p}e0', -254, 254)

    def dread(p):
        return [f'  {p}di = add i32 {p}ix, 4', f'  {p}dr = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %sb.h, i32 {p}di, i32 undef, i8 1, i32 4)',
                f'  {p}du = extractvalue %dx.types.ResRet.i32 {p}dr, 0', f'  {p}z = call float @dx.op.bitcastI32toF32(i32 126, i32 {p}du)']

    def near(p, ax, ay, bx, by, lim):
        return [f'  {p}sx = sub i32 {ax}, {bx}', f'  {p}sy = sub i32 {ay}, {by}'] + sabs(f'{p}ux', f'{p}sx') + sabs(f'{p}uy', f'{p}sy') + [
                f'  {p}mc = icmp ugt i32 {p}ux, {p}uy', f'  {p}mx = select i1 {p}mc, i32 {p}ux, i32 {p}uy', f'  {p} = icmp ule i32 {p}mx, {lim}']

    mh = ['  br i1 %sb.skip, label %sm.T, label %sm.M', '', 'sm.T:', f'  %sm.wm = add i32 {WCc}, -1', f'  %sm.hm = add i32 {HCc}, -1'] + mread('%sm.p', Xc, Yc)
    OFFS = [int(x) for x in os.environ.get('SB_UNCOV_OFFS', '3,8').split(',') if x]
    offs = [o for d in OFFS for o in ((d, 0), (-d, 0), (0, d), (0, -d))]
    flag, any_, stage2 = 'false', None, []
    for i, nm in enumerate(['q'] + [f'n{i}' for i in range(len(offs))]):
        p = f'%sm.{nm}'
        if nm == 'q':
            mh += [f'  {p}hx = ashr i32 %sm.pdx, 1', f'  {p}hy = ashr i32 %sm.pdy, 1', f'  {p}X = add i32 {Xc}, {p}hx', f'  {p}Y = add i32 {Yc}, {p}hy']
        else:
            mh += [f'  {p}X = add i32 {Xc}, {offs[i - 1][0]}', f'  {p}Y = add i32 {Yc}, {offs[i - 1][1]}']
        mh += mread(p, f'{p}X', f'{p}Y') + near(f'{p}same', f'{p}dx', f'{p}dy', '%sm.pdx', '%sm.pdy', 1) + [f'  {p}diff = xor i1 {p}same, true']
        if any_:
            mh.append(f'  {p}any = or i1 {any_}, {p}diff'); any_ = f'{p}any'
        else:
            any_ = f'{p}diff'
        stage2 += [f'  {p}tx = sub i32 %sm.pdx, {p}dx', f'  {p}ty = sub i32 %sm.pdy, {p}dy', f'  {p}thx = ashr i32 {p}tx, 1', f'  {p}thy = ashr i32 {p}ty, 1',
                   f'  {p}tX = add i32 {Xc}, {p}thx', f'  {p}tY = add i32 {Yc}, {p}thy'] + mread(f'{p}t', f'{p}tX', f'{p}tY') + near(f'{p}there', f'{p}tdx', f'{p}tdy', f'{p}dx', f'{p}dy', 1) + \
                  dread(f'{p}t') + [f'  {p}front = fcmp olt float {p}tz, %sm.pz', f'  {p}okd = icmp ne i32 {p}tdu, 0', f'  {p}fr = and i1 {p}front, {p}okd', f'  {p}th2 = and i1 {p}there, {p}fr',
                                    f'  {p}hit = and i1 {p}diff, {p}th2', f'  {p}acc = or i1 {flag}, {p}hit']
        flag = f'{p}acc'
    # at rest: this cell does not move, and neither does anything looked at around it
    if REST:
        mh += ['  %sm.por = or i32 %sm.pdx, %sm.pdy', '  %sm.c0u = icmp eq i32 %sm.por, 0', f'  %sm.nany = xor i1 {any_}, true', '  %sm.rin = and i1 %sm.c0u, %sm.nany']
    if os.environ.get('SB_PLANE', '1') == '1':
        # the exact test, as in skipblend.py: who was, a frame ago, where this pixel's content was (the plane frameskip.py records)
        from frameskip_layout import plane_layout
        L_ = plane_layout(S); B1_ = (2048 if S == 15392 else 4096)
        mh += [f'  %sm.Px0 = shl i32 {Xc}, 1', f'  %sm.Py0 = shl i32 {Yc}, 1', '  %sm.Px = add i32 %sm.Px0, %sm.pdx', '  %sm.Py = add i32 %sm.Py0, %sm.pdy', '  %sm.Pbx = ashr i32 %sm.Px, 2', '  %sm.Pby = ashr i32 %sm.Py, 2',
               f'  %sm.Pix = icmp ult i32 %sm.Pbx, {L_["nx"]}', f'  %sm.Piy = icmp ult i32 %sm.Pby, {L_["ny"]}', '  %sm.Pin = and i1 %sm.Pix, %sm.Piy',
               '  %sm.Pxs = select i1 %sm.Pin, i32 %sm.Pbx, i32 0', '  %sm.Pys = select i1 %sm.Pin, i32 %sm.Pby, i32 0', '  %sm.Pyr = lshr i32 %sm.Pys, 1', '  %sm.Pyo = and i32 %sm.Pys, 1', '  %sm.Pyb = icmp ne i32 %sm.Pyo, 0',
               f'  %sm.Pbk = select i1 %sm.Pyb, i32 {L_["pb1"] * 4}, i32 {L_["pb0"] * 4}', f'  %sm.Prw = mul i32 %sm.Pyr, {S}', f'  %sm.Pa1 = add i32 %sm.Prw, {MBASE}', '  %sm.Pa2 = add i32 %sm.Pa1, %sm.Pbk',
               '  %sm.Px4 = shl i32 %sm.Pxs, 2', '  %sm.Padr = add i32 %sm.Pa2, %sm.Px4',
               '  %sm.Pr = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %sb.h, i32 %sm.Padr, i32 undef, i8 1, i32 4)', '  %sm.Pk0 = extractvalue %dx.types.ResRet.i32 %sm.Pr, 0',
               '  %sm.Pk = select i1 %sm.Pin, i32 %sm.Pk0, i32 0', '  %sm.Pany = icmp ne i32 %sm.Pk, 0']
        win = [f'  %sm.Wid = and i32 %sm.Pk, {(1 << L_["idb"]) - 1}', f'  %sm.Wx = and i32 %sm.Wid, {(1 << L_["xb"]) - 1}', f'  %sm.Wy = lshr i32 %sm.Wid, {L_["xb"]}',
               '  %sm.Wyr = lshr i32 %sm.Wy, 1', '  %sm.Wyo = and i32 %sm.Wy, 1', '  %sm.Wyb = icmp ne i32 %sm.Wyo, 0', f'  %sm.Wbk = select i1 %sm.Wyb, i32 {B1_ * 4}, i32 {48 * 4}',
               f'  %sm.Wrw = mul i32 %sm.Wyr, {S}', f'  %sm.Wa1 = add i32 %sm.Wrw, {MBASE}', '  %sm.Wa2 = add i32 %sm.Wa1, %sm.Wbk', '  %sm.Wx2 = shl i32 %sm.Wx, 3', '  %sm.Wix = add i32 %sm.Wa2, %sm.Wx2',
               '  %sm.Wmr = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %sb.h, i32 %sm.Wix, i32 undef, i8 1, i32 4)', '  %sm.Wm = extractvalue %dx.types.ResRet.i32 %sm.Wmr, 0',
               '  %sm.Wxs = shl i32 %sm.Wm, 16', '  %sm.Wd0 = ashr i32 %sm.Wxs, 16', '  %sm.We0 = ashr i32 %sm.Wm, 16'] + sclamp('%sm.Wdx', '%sm.Wd0', -254, 254) + sclamp('%sm.Wdy', '%sm.We0', -254, 254) + \
              near('%sm.Wsame', '%sm.Wdx', '%sm.Wdy', '%sm.pdx', '%sm.pdy', 1) + dread('%sm.W') + [
               '  %sm.Wdiff = xor i1 %sm.Wsame, true', '  %sm.Wfront = fcmp olt float %sm.Wz, %sm.pz', '  %sm.Wokd = icmp ne i32 %sm.Wdu, 0', '  %sm.Wh1 = and i1 %sm.Wdiff, %sm.Wfront', '  %sm.Whit = and i1 %sm.Wh1, %sm.Wokd']
        any_, stage2, flag = '%sm.Pany', win, '%sm.Whit'
    mh += [f'  br i1 {any_}, label %sm.T2, label %sm.M2', '', 'sm.T2:'] + dread('%sm.p') + stage2 + ['  br label %sm.M2', '', 'sm.M2:', f'  %sm.fl2 = phi i1 [ {flag}, %sm.T2 ], [ false, %sm.T ]',
           '  br label %sm.M', '', 'sm.M:', f'  %sm.flag = phi i1 [ %sm.fl2, %sm.M2 ], [ false, {FL_BLOCK} ]'] + ([f'  %sm.rest = phi i1 [ %sm.rin, %sm.M2 ], [ false, {FL_BLOCK} ]'] if REST else [])
fl = lambda v: '0x%016X' % __import__('struct').unpack('<Q', __import__('struct').pack('<d', __import__('struct').unpack('<f', __import__('struct').pack('<f', v))[0]))[0]
out = L[:e1] + head


def samples_w(cur):
    """as samples(), but (value, weight) pairs"""
    m = re.match(r'fdiv fast float (%[\w.]+), %[\w.]+$', defs.get(cur, '')) or sys.exit('skipblend_dxil: the resampled color is not a quotient')
    out, todo = [], [m[1]]
    while todo:
        t = todo.pop(); f = re.match(r'fmul fast float (%[\w.]+), (%[\w.]+)$', defs.get(t, ''))
        w = [x for x in (f[1], f[2]) if re.match(r'call float @dx\.op\.unary\.f32\(i32 21, ', defs.get(x, ''))] if f else []
        if len(w) == 1:
            out.append((f[2] if w[0] == f[1] else f[1], w[0])); continue
        a = re.match(r'fadd fast float (%[\w.]+), (%[\w.]+)$', defs.get(t, '')) or sys.exit('skipblend_dxil: unexpected shape of the weighted sum')
        todo += [a[1], a[2]]
    if len(out) != 9:
        sys.exit(f'skipblend_dxil: {len(out)} samples found for a pixel, expected 9')
    return out


PART = os.environ.get('SB_PART'); BRIGHT = os.environ.get('SB_BRIGHT'); SAMPLE = os.environ.get('SB_SAMPLE')
FMIN = lambda r, a, b: f'  {r} = call float @dx.op.binary.f32(i32 36, float {a}, float {b})'
FMAX = lambda r, a, b: f'  {r} = call float @dx.op.binary.f32(i32 35, float {a}, float {b})'


def part(k, curs, h, at):
    """Content that changed without motion vectors, as in skipblend.py: %sb.rq = the rest rule applies, %sb.pf = the share of
    the new frame the pixel takes at least. at: the line of the pixel's mix (its history load is the last one before it)."""
    c_, outs = [], []
    if PART is not None or BRIGHT is not None:
        for c in range(3):
            tc = samples(curs[c]); mn, mx = tc[0], tc[0]
            for i, v in enumerate(tc[1:]):
                c_ += [FMIN(f'%sb.qn{c}{k}.{i}', mn, v), FMAX(f'%sb.qx{c}{k}.{i}', mx, v)]; mn, mx = f'%sb.qn{c}{k}.{i}', f'%sb.qx{c}{k}.{i}'
            c_.append(f'  %sb.qr{c}{k} = fsub fast float {mx}, {mn}')
            flags = []
            if PART is not None:
                c_ += [f'  %sb.qs{c}{k} = fmul fast float %sb.qr{c}{k}, {fl(float(PART))}', f"  %sb.qt{c}{k} = fadd fast float %sb.qs{c}{k}, {fl(float(os.environ.get('SB_PARTABS', '0')))}",
                       f'  %sb.ql{c}{k} = fsub fast float {mn}, %sb.qt{c}{k}', f'  %sb.qh{c}{k} = fadd fast float {mx}, %sb.qt{c}{k}',
                       f'  %sb.qa{c}{k} = fcmp olt float {h[c]}, %sb.ql{c}{k}', f'  %sb.qb{c}{k} = fcmp ogt float {h[c]}, %sb.qh{c}{k}', f'  %sb.qox{c}{k} = or i1 %sb.qa{c}{k}, %sb.qb{c}{k}']
                flags.append(f'%sb.qox{c}{k}')
            if BRIGHT is not None:
                c_ += [f'  %sb.bs{c}{k} = fmul fast float %sb.qr{c}{k}, {fl(float(BRIGHT))}', f"  %sb.bt{c}{k} = fadd fast float %sb.bs{c}{k}, {fl(float(os.environ.get('SB_BRIGHTABS', '0.05')))}",
                       f'  %sb.bd{c}{k} = fsub fast float {curs[c]}, {h[c]}', f'  %sb.bg{c}{k} = fcmp ogt float %sb.bd{c}{k}, %sb.bt{c}{k}']
                if os.environ.get('SB_BRIGHTSYM') == '1':
                    c_ += [f'  %sb.bn{c}{k} = fsub fast float 0.000000e+00, %sb.bd{c}{k}', f'  %sb.bl{c}{k} = fcmp ogt float %sb.bn{c}{k}, %sb.bt{c}{k}', f'  %sb.bgs{c}{k} = or i1 %sb.bg{c}{k}, %sb.bl{c}{k}']
                    flags.append(f'%sb.bgs{c}{k}')
                else:
                    flags.append(f'%sb.bg{c}{k}')
            cur_ = flags[0]
            for i, f_ in enumerate(flags[1:]):
                c_.append(f'  %sb.qo{c}{k}.{i} = or i1 {cur_}, {f_}'); cur_ = f'%sb.qo{c}{k}.{i}'
            outs.append(cur_)
        c_ += [f'  %sb.qo01{k} = or i1 {outs[0]}, {outs[1]}', f'  %sb.chg{k} = or i1 %sb.qo01{k}, {outs[2]}', f'  %sb.nchg{k} = xor i1 %sb.chg{k}, true', f'  %sb.rqO{k} = and i1 %sm.rest, %sb.nchg{k}']
    else:
        c_.append(f'  %sb.rqO{k} = and i1 %sm.rest, %sm.rest')
    if SAMPLE is None:
        return c_ + [f'  %sb.rq{k} = and i1 %sb.rqO{k}, %sb.rqO{k}', f'  %sb.pf{k} = fmul fast float 0.000000e+00, 0.000000e+00']
    # the nearest new sample against the range of the 3x3 history pixels around this one
    ld = next((m_ for n_ in range(at, 0, -1) for m_ in [re.match(r'\s*%[\w.]+ = call %dx\.types\.ResRet\.f16 @dx\.op\.textureLoad\.f16\(i32 66, %dx\.types\.Handle (%[\w.]+), i32 0, i32 (%[\w.]+), i32 (%[\w.]+),', L[n_])] if m_), None) \
        or sys.exit('skipblend_dxil: the history load of a pixel was not found')
    img, cx, cy = ld[1], ld[2], ld[3]
    mn = [None] * 3; mx = [None] * 3
    for j, (dx, dy) in enumerate([(a_, b_) for b_ in (-1, 0, 1) for a_ in (-1, 0, 1)]):
        t = f'%ss.{k}.{j}'
        c_ += [f'  {t}x0 = add i32 {cx}, {dx}', f'  {t}y0 = add i32 {cy}, {dy}', f'  {t}x = call i32 @dx.op.binary.i32(i32 37, i32 {t}x0, i32 0)', f'  {t}y = call i32 @dx.op.binary.i32(i32 37, i32 {t}y0, i32 0)',
               f'  {t}f = call %dx.types.ResRet.f16 @dx.op.textureLoad.f16(i32 66, %dx.types.Handle {img}, i32 0, i32 {t}x, i32 {t}y, i32 undef, i32 undef, i32 undef, i32 undef)']
        for c in range(3):
            c_ += [f'  {t}h{c} = extractvalue %dx.types.ResRet.f16 {t}f, {c}', f'  {t}v{c} = fpext half {t}h{c} to float']
            if mn[c] is None:
                mn[c] = mx[c] = f'{t}v{c}'
            else:
                c_ += [FMIN(f'{t}n{c}', mn[c], f'{t}v{c}'), FMAX(f'{t}m{c}', mx[c], f'{t}v{c}')]; mn[c], mx[c] = f'{t}n{c}', f'{t}m{c}'
    t = f'%ss.{k}.s'; fs = []
    m_, ab, full = float(SAMPLE), float(os.environ.get('SB_SAMPLEABS', '0.05')), float(os.environ.get('SB_SAMPLEFULL', '1'))
    for c in range(3):
        tc = samples_w(curs[c]); bv, bw = tc[0]
        for i, (v, w) in enumerate(tc[1:]):
            c_ += [f'  {t}cg{c}.{i} = fcmp ogt float {w}, {bw}', f'  {t}cw{c}.{i} = select i1 {t}cg{c}.{i}, float {w}, float {bw}', f'  {t}cv{c}.{i} = select i1 {t}cg{c}.{i}, float {v}, float {bv}']
            bv, bw = f'{t}cv{c}.{i}', f'{t}cw{c}.{i}'
        c_ += [f'  {t}r{c} = fsub fast float {mx[c]}, {mn[c]}', f'  {t}a{c} = fmul fast float {t}r{c}, {fl(m_)}', f'  {t}b{c} = fadd fast float {t}a{c}, {fl(ab)}',
               f'  {t}hi{c} = fsub fast float {bv}, {mx[c]}', f'  {t}lo{c} = fsub fast float {mn[c]}, {bv}', FMAX(f'{t}e0{c}', f'{t}hi{c}', f'{t}lo{c}'), f'  {t}e{c} = fsub fast float {t}e0{c}, {t}b{c}',
               f'  {t}d0{c} = fmul fast float {t}r{c}, {fl(full)}', f'  {t}d{c} = fadd fast float {t}d0{c}, {fl(ab)}', f'  {t}q{c} = fdiv fast float {t}e{c}, {t}d{c}',
               FMAX(f'{t}u{c}', f'{t}q{c}', '0.000000e+00'), FMIN(f'{t}g{c}', f'{t}u{c}', '1.000000e+00')]
        fs.append(f'{t}g{c}')
    c_ += [FMAX(f'{t}gm', fs[0], fs[1]), FMAX(f'{t}g', f'{t}gm', fs[2]),
           (f'  %sb.pf{k} = fmul fast float {t}g, 1.000000e+00' if os.environ.get('SB_SAMPLEALL') == '1' else f'  %sb.pf{k} = select i1 %sm.rest, float {t}g, float 0.000000e+00'),
           f'  {t}z = fcmp ole float %sb.pf{k}, 0.000000e+00', f'  %sb.rqS{k} = and i1 %sm.rest, {t}z', f'  %sb.rq{k} = and i1 %sb.rqO{k}, %sb.rqS{k}']
    return c_


def samples(cur):
    """The nine sample values (one channel) that the resampled color `cur` = sum(value * weight) / sum(weight) is made of."""
    m = re.match(r'fdiv fast float (%[\w.]+), %[\w.]+$', defs.get(cur, '')) or sys.exit('skipblend_dxil: the resampled color is not a quotient')
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
        m = re.match(r'([\w.]+):\s*$', L[n])
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
        if UNCOV and n == BLINE:
            if cur_label != FL_BLOCK:
                sys.exit('skipblend_dxil: lost track of the block that holds the early-out')
            out += mh; lab[cur_label] = '%sm.M'; cur_label = '%sm.M'
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
                           f'  %sb.gw{k} = fsub fast float 1.000000e+00, %sb.ao{k}', f'  %sb.wm{k} = fmul fast float {w}, %sb.gw{k}'] + (
                           (part(k, curs, h, n) + [f'  %sb.wq{k} = select i1 %sb.rq{k}, float 0.000000e+00, float %sb.wm{k}', FMAX(f'%sb.wqq{k}', f'%sb.wq{k}', f'%sb.pf{k}'),
                                                   f'  %sb.wn{k} = call float @dx.op.binary.f32(i32 36, float %sb.wqq{k}, float 1.000000e+00)'])
                           if REST else [f'  %sb.wn{k} = call float @dx.op.binary.f32(i32 36, float %sb.wm{k}, float 1.000000e+00)']) + [
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
                        c_ += [f'  %sb.zz{k} = and i1 %sb.z0{k}, %sb.z1{k}'] + ([f'  %sb.gda{k} = and i1 %sb.zz{k}, %sb.z2{k}', f'  %sb.gd{k} = or i1 %sb.gda{k}, %sm.flag'] if UNCOV else [f'  %sb.gd{k} = and i1 %sb.zz{k}, %sb.z2{k}']) + [
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
