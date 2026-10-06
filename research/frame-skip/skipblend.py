#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# skipblend.py [row bytes] < postpass.spvasm > out.spvasm     (AMD's postpass, before any store rewrite)
#
# NOT bit-exact. For use with frameskip.py: less shimmer on skipped frames.
# The postpass mixes each output pixel as  a * history + (1 - a) * (this frame, resampled), with a
# from the model. On a skipped frame a is the one of the frame before, whose samples fell
# elsewhere, so pixels whose nearest sample has moved away take too much of the new frame.
# Corrected with what is known exactly: Dn and Dp, the squared distance (render pixels) from the
# pixel to its nearest sample now and in the last frame that ran the model (its jitter is the two
# words frameskip.py leaves next to the mark):
#     (1 - a)  is multiplied by  1 - a * (1 - min(1, 2^(K * (Dp - Dn))))
# The factor a leaves areas alone where the model wants little history (just uncovered ones).
# Guard: where the history is far darker than the new frame in every channel (at most SB_REL of
# it), a skipped frame outputs the resampled new frame alone. That is the strip that scrolls in
# from outside the screen when the camera starts to turn: its history is nearly black, and the
# stale a would leave a dark band there for one frame.
# History clamp: on a skipped frame the history is limited to the range of the nine samples of
# the new frame around the pixel (per channel, widened by SB_CLAMP times that range). Where the
# picture has changed since the model last ran, the stale a then mixes in a plausible colour
# instead of an outdated one.
# All of this sits in one branch per output pixel that is taken on skipped frames only.
# Frames that ran the model keep the model's values bit for bit.
# Options (environment): SB_K (default 32), SB_AW (0, 1 or 2: power of a in the factor, default 1),
# SB_REL (default 0.1), SB_THR (absolute floor of the guard's limit, default 0), SB_GUARD=0 (no guard),
# SB_CLAMP (default 0.5; "off" for none), SB_BRANCH=0 (the layout of releases dll-2026-10-06.2 and .3:
# no branch, selects instead; with SB_CLAMP=off it rebuilds release .3's files),
# SB_CONST (a further constant factor on skipped frames), SB_CAP (upper limit of the 2^ term,
# default 1; above 1 also raises the new frame's weight where a sample came closer: more flicker).
import os, re, sys
K = float(os.environ.get('SB_K', '32')); CONST = os.environ.get('SB_CONST'); CAP = float(os.environ.get('SB_CAP', '1')); AW = int(os.environ.get('SB_AW', '1'))
CLAMP = None if os.environ.get('SB_CLAMP') == 'off' else float(os.environ.get('SB_CLAMP', '0.5'))
GUARD = os.environ.get('SB_GUARD', '1') == '1'
L = sys.stdin.read().split('\n')
S = int(sys.argv[1]) if len(sys.argv) > 1 else next((x for x in (15392, 30752, 61472) if any(f'%uint_{x} = ' in l for l in L)), None) or sys.exit('skipblend: no known row size')
defs = {m[1]: m[2] for l in L for m in [re.match(r'\s*(%\w+) = (.*)$', l)] if m}
width = S // 16 - 2; REGION = (width * 9 // 16 + 2) * S; WM = (REGION + S + 128) // 4
main = next(n for n, l in enumerate(L) if '= OpFunction' in l)
SSBO = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpVariable %_ptr_StorageBuffer__runtimearr_SSBO StorageBuffer', l)] if m)
GLSL = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpExtInstImport "GLSL.std.450"', l)] if m)
ge = [n for n, l in enumerate(L) if n > main and 'OpUGreaterThanEqual %bool' in l][:2]
br = next(n for n in range(ge[1], len(L)) if 'OpBranchConditional' in L[n])
lab = L[br].split()[-1]; lab0 = lab
at = next(n for n, l in enumerate(L) if re.match(rf'\s*{re.escape(lab)} = OpLabel', l))
c = ['%sb_m1 = OpConstant %uint 1511506142', '%sb_m2 = OpConstant %uint 168889943', f'%sb_k = OpConstant %float {K}', '%sb_one = OpConstant %float 1',
     f'%sb_cap = OpConstant %float {CAP}', '%sb_c0 = OpConstant %uint 0', '%sb_zero = OpConstant %float 0', f"%sb_thr = OpConstant %float {float(os.environ.get('SB_THR', '0'))}", f"%sb_rel = OpConstant %float {float(os.environ.get('SB_REL', '0.1'))}"] + ([f"%sb_slack = OpConstant %float {CLAMP}"] if CLAMP is not None else []) + [f'%sb_w{k} = OpConstant %uint {WM + k}' for k in range(4)]
if CONST:
    c.append(f'%sb_const = OpConstant %float {float(CONST)}')
head = ['%sb_r1 = OpAccessChain %_ptr_PushConstant_uint %registers %uint_1', '%sb_r = OpLoad %uint %sb_r1', '%sb_bi = OpIAdd %uint %sb_r %uint_11',
        f'%sb_bp = OpAccessChain %_ptr_StorageBuffer_SSBO {SSBO} %sb_bi']
for k in range(4):
    head += [f'%sb_p{k} = OpAccessChain %_ptr_StorageBuffer_uint %sb_bp %uint_0 %sb_w{k}', f'%sb_v{k} = OpLoad %uint %sb_p{k}']
head += ['%sb_e1 = OpIEqual %bool %sb_v0 %sb_m1', '%sb_e2 = OpIEqual %bool %sb_v1 %sb_m2', '%sb_skip = OpLogicalAnd %bool %sb_e1 %sb_e2',
         '%sb_pjx = OpBitcast %float %sb_v2', '%sb_pjy = OpBitcast %float %sb_v3',
         '%sb_pc = OpAccessChain %_ptr_PushConstant_v2uint %registers %uint_0', '%sb_ad = OpLoad %v2uint %sb_pc',
         '%sb_cb = OpBitcast %_ptr_PhysicalStorageBuffer_PhysicalPointerFloat4NonWriteCBVArray %sb_ad',
         '%sb_f1p = OpInBoundsAccessChain %_ptr_PhysicalStorageBuffer_v4float %sb_cb %uint_0 %uint_1', '%sb_f1 = OpLoad %v4float %sb_f1p Aligned 16',
         '%sb_jx = OpCompositeExtract %float %sb_f1 2', '%sb_jy = OpCompositeExtract %float %sb_f1 3',
         '%sb_djx = OpFSub %float %sb_pjx %sb_jx', '%sb_djy = OpFSub %float %sb_pjy %sb_jy']
out = L[:main] + c + L[main:at + 1] + head
n_guard = 0


def samples(cur):
    """The nine sample values (one channel) that the resampled colour `cur` = sum(value * weight) / sum(weight) is made of."""
    m = re.match(r'OpFDiv %float (%\w+) %\w+$', defs.get(cur, '')) or sys.exit('skipblend: the resampled colour is not a quotient')
    vals, node = [], m[1]
    def term(t):
        f = re.match(r'OpFMul %float (%\w+) (%\w+)$', defs.get(t, ''))
        if not f:
            return None
        w = [x for x in (f[1], f[2]) if re.match(r'OpExtInst %float %\w+ Exp2 ', defs.get(x, ''))]
        return (f[2] if w[0] == f[1] else f[1]) if len(w) == 1 else None
    while True:
        v = term(node)
        if v:
            vals.append(v); break
        a = re.match(r'OpFAdd %float (%\w+) (%\w+)$', defs.get(node, '')) or sys.exit('skipblend: unexpected shape of the weighted sum')
        va, vb = term(a[1]), term(a[2])
        if va and not vb: vals.append(va); node = a[2]
        elif vb and not va: vals.append(vb); node = a[1]
        elif va and vb: vals += [va, vb]; break
        else: sys.exit('skipblend: unexpected shape of the weighted sum')
    if len(vals) != 9:
        sys.exit(f'skipblend: {len(vals)} samples found for a pixel, expected 9')
    return vals


BRANCH = os.environ.get('SB_BRANCH', '1') == '1'
if not BRANCH:
    posx = posy = None; n_sites = 0; ren = {}; pend = None; GUARD = os.environ.get('SB_GUARD', '1') == '1'; taps = []
    for n in range(at + 1, len(L)):
        l = L[n]
        for a, b in ren.items():
            l = re.sub(rf'{re.escape(a)}(?!\w)', b, l)
        m = re.match(r'\s*(%\w+) = OpFAdd %float (%\w+) (%\w+)$', L[n])
        if m:   # position of the output pixel among this frame's samples: (jitter - 0.5) + (pixel + 0.5) / scale
            for u in (m[2], m[3]):
                e = re.match(r'OpFAdd %float (%\w+) %float_n0_5$', defs.get(u, ''))
                j = e and re.match(r'OpCompositeExtract %float %\w+ ([23])$', defs.get(e[1], ''))
                if j:
                    if j[1] == '2': posx = m[1]
                    else: posy = m[1]
        out.append(l)
        if pend and GUARD:
            # the guard: where the reprojected history is far darker than the new frame in every channel (it
            # scrolled in from outside the screen when a pan started, and is nearly black), a skipped frame
            # takes the new frame alone; the stale weight would leave a dark band at the screen edge
            m = re.match(r'\s*(%\w+) = OpFMul %float (%\w+) (%\w+)$', L[n])
            if m and pend['w'] in (m[2], m[3]) and len(pend['cur']) < 3:
                pend['cur'][m[1]] = m[3] if m[2] == pend['w'] else m[2]
            elif m and pend['a'] in (m[2], m[3]) and len(pend['hist']) < 3:
                pend['hist'].append(m[3] if m[2] == pend['a'] else m[2])
            m = re.match(r'\s*(%\w+) = OpFAdd %float (%\w+) (%\w+)$', L[n])
            if m and len(pend['hist']) == 3 and (m[2] in pend['cur'] or m[3] in pend['cur']):
                pend['sum'].append((m[1], pend['cur'][m[2]] if m[2] in pend['cur'] else pend['cur'][m[3]]))
                if len(pend['sum']) == 3:
                    k = pend['k']; h = pend['hist']
                    curs = [cur for r, cur in pend['sum']]
                    sums = [r for r, cur in pend['sum']]
                    if CLAMP is not None:
                        # on a skipped frame the history is clamped to the range of the nine samples of the new frame
                        # (widened by SB_CLAMP times that range): where the picture changed, the stale weight then
                        # mixes in a plausible colour instead of an outdated one
                        a2 = ren[pend['a']]
                        for c in range(3):
                            tc = samples(curs[c]); mn, mx = tc[0], tc[0]
                            for i, v in enumerate(tc[1:]):
                                out += [f'%sb_mn{c}{k}_{i} = OpExtInst %float {GLSL} NMin {mn} {v}', f'%sb_mx{c}{k}_{i} = OpExtInst %float {GLSL} NMax {mx} {v}']
                                mn, mx = f'%sb_mn{c}{k}_{i}', f'%sb_mx{c}{k}_{i}'
                            out += [f'%sb_rg{c}{k} = OpFSub %float {mx} {mn}', f'%sb_sl{c}{k} = OpFMul %float %sb_rg{c}{k} %sb_slack',
                                    f'%sb_lo{c}{k} = OpFSub %float {mn} %sb_sl{c}{k}', f'%sb_hi{c}{k} = OpFAdd %float {mx} %sb_sl{c}{k}',
                                    f'%sb_h1{c}{k} = OpExtInst %float {GLSL} NMin {h[c]} %sb_hi{c}{k}', f'%sb_hc{c}{k} = OpExtInst %float {GLSL} NMax %sb_h1{c}{k} %sb_lo{c}{k}',
                                    f'%sb_hd{c}{k} = OpFSub %float %sb_hc{c}{k} {h[c]}', f'%sb_ha{c}{k} = OpFMul %float %sb_hd{c}{k} {a2}',
                                    f'%sb_rc{c}{k} = OpFAdd %float {sums[c]} %sb_ha{c}{k}', f'%sb_rs{c}{k} = OpSelect %float %sb_skip %sb_rc{c}{k} {sums[c]}']
                            sums[c] = f'%sb_rs{c}{k}'
                    out += [x for c in range(3) for x in (f'%sb_zm{c}{k} = OpFMul %float {curs[c]} %sb_rel', f'%sb_zt{c}{k} = OpExtInst %float {GLSL} NMax %sb_zm{c}{k} %sb_thr',
                                                          f'%sb_z{c}{k} = OpFOrdLessThanEqual %bool {h[c]} %sb_zt{c}{k}')] + [
                        f'%sb_zz{k} = OpLogicalAnd %bool %sb_z0{k} %sb_z1{k}', f'%sb_zb{k} = OpLogicalAnd %bool %sb_zz{k} %sb_z2{k}',
                        f'%sb_gd{k} = OpLogicalAnd %bool %sb_zb{k} %sb_skip'] + [
                        f'%sb_r{c}{k} = OpSelect %float %sb_gd{k} {cur} {sums[c]}' for c, (r, cur) in enumerate(pend['sum'])]
                    for c, (r, cur) in enumerate(pend['sum']):
                        ren[r] = f'%sb_r{c}{k}'
                    n_guard += 1; pend = None; taps = []
        m = re.match(r'\s*(%\w+) = OpFSub %float %float_1 (%\w+)$', L[n])
        if m and re.match(r'OpFDiv %float %float_1 ', defs.get(m[2], '')):
            k = n_sites; n_sites += 1; w, a = m[1], m[2]
            if True:
                code = []
                for ax, pos, dj in (('x', posx, '%sb_djx'), ('y', posy, '%sb_djy')):
                    code += [f'%sb_rn{ax}{k} = OpExtInst %float {GLSL} RoundEven {pos}', f'%sb_dn{ax}{k} = OpFSub %float {pos} %sb_rn{ax}{k}',
                             f'%sb_pp{ax}{k} = OpFAdd %float {pos} {dj}', f'%sb_rp{ax}{k} = OpExtInst %float {GLSL} RoundEven %sb_pp{ax}{k}',
                             f'%sb_dp{ax}{k} = OpFSub %float %sb_pp{ax}{k} %sb_rp{ax}{k}',
                             f'%sb_n2{ax}{k} = OpFMul %float %sb_dn{ax}{k} %sb_dn{ax}{k}', f'%sb_p2{ax}{k} = OpFMul %float %sb_dp{ax}{k} %sb_dp{ax}{k}']
                code += [f'%sb_Dn{k} = OpFAdd %float %sb_n2x{k} %sb_n2y{k}', f'%sb_Dp{k} = OpFAdd %float %sb_p2x{k} %sb_p2y{k}',
                         f'%sb_dd{k} = OpFSub %float %sb_Dp{k} %sb_Dn{k}', f'%sb_ex{k} = OpFMul %float %sb_dd{k} %sb_k',
                         f'%sb_g{k} = OpExtInst %float {GLSL} Exp2 %sb_ex{k}', f'%sb_gc{k} = OpExtInst %float {GLSL} NMin %sb_g{k} %sb_cap',
                         f'%sb_gm{k} = OpFMul %float %sb_gc{k} ' + ('%sb_const' if CONST else '%sb_one'), f'%sb_om{k} = OpFSub %float %sb_one %sb_gm{k}'] + (
                         [f'%sb_ap{k} = OpFMul %float {a} {a}'] if AW == 2 else [f'%sb_ap{k} = OpFMul %float {a} %sb_one'] if AW == 1 else [f'%sb_ap{k} = OpFMul %float %sb_one %sb_one']) + [
                         f'%sb_ao{k} = OpFMul %float %sb_ap{k} %sb_om{k}', f'%sb_gw{k} = OpFSub %float %sb_one %sb_ao{k}',
                         f'%sb_cf{k} = OpSelect %float %sb_skip %sb_gw{k} %sb_one']
            # frames that ran the model keep the model's values bit for bit
            code += [f'%sb_wm{k} = OpFMul %float {w} %sb_cf{k}', f'%sb_wn{k} = OpExtInst %float {GLSL} NMin %sb_wm{k} %sb_one',
                     f'%sb_an{k} = OpFSub %float %sb_one %sb_wn{k}', f'%sb_w2{k} = OpSelect %float %sb_skip %sb_wn{k} {w}',
                     f'%sb_a2{k} = OpSelect %float %sb_skip %sb_an{k} {a}']
            out += code; ren[w] = f'%sb_w2{k}'; ren[a] = f'%sb_a2{k}'
            pend = {'k': k, 'w': w, 'a': a, 'cur': {}, 'hist': [], 'sum': []}
else:
    # Everything that applies to skipped frames only sits in one branch per output pixel, taken on
    # skipped frames; the condition is the same for the whole dispatch, so frames that run the
    # model pay one untaken branch per pixel and keep the model's values bit for bit.
    posx = posy = None; n_sites = 0; ren = {}; lab = {}; pend = None; cur_label = lab0
    for n in range(at + 1, len(L)):
        l = L[n]
        for a, b in ren.items():
            l = re.sub(rf'{re.escape(a)}(?!\w)', b, l)
        if ' OpPhi ' in l:
            for a, b in lab.items():
                l = re.sub(rf'{re.escape(a)}(?!\w)', b, l)
        m = re.match(r'\s*(%\w+) = OpLabel', L[n])
        if m:
            cur_label = m[1]
        m = re.match(r'\s*(%\w+) = OpFAdd %float (%\w+) (%\w+)$', L[n])
        if m:   # position of the output pixel among this frame's samples: (jitter - 0.5) + (pixel + 0.5) / scale
            for u in (m[2], m[3]):
                e = re.match(r'OpFAdd %float (%\w+) %float_n0_5$', defs.get(u, ''))
                j = e and re.match(r'OpCompositeExtract %float %\w+ ([23])$', defs.get(e[1], ''))
                if j:
                    if j[1] == '2': posx = m[1]
                    else: posy = m[1]
        out.append(l)
        if pend:
            m = re.match(r'\s*(%\w+) = OpFMul %float (%\w+) (%\w+)$', L[n])
            if m and pend['w'] in (m[2], m[3]) and len(pend['cur']) < 3:
                pend['cur'][m[1]] = m[3] if m[2] == pend['w'] else m[2]; pend['lines'].append(L[n])
            elif m and pend['a'] in (m[2], m[3]) and len(pend['hist']) < 3:
                pend['hist'].append(m[3] if m[2] == pend['a'] else m[2]); pend['lines'].append(L[n])
            m = re.match(r'\s*(%\w+) = OpFAdd %float (%\w+) (%\w+)$', L[n])
            if m and len(pend['hist']) == 3 and (m[2] in pend['cur'] or m[3] in pend['cur']):
                pend['sum'].append((m[1], pend['cur'][m[2]] if m[2] in pend['cur'] else pend['cur'][m[3]])); pend['lines'].append(L[n])
                if len(pend['sum']) == 3:
                    k = pend['k']; h = pend['hist']; w, a = pend['w'], pend['a']
                    curs = [cur for r, cur in pend['sum']]; sums = [r for r, cur in pend['sum']]
                    code = ['OpSelectionMerge %sb_M' + str(k) + ' None', f'OpBranchConditional %sb_skip %sb_T{k} %sb_M{k}', f'%sb_T{k} = OpLabel']
                    # the weight of the new frame, corrected for where its samples fall now
                    for ax, pos, dj in (('x', pend['posx'], '%sb_djx'), ('y', pend['posy'], '%sb_djy')):
                        code += [f'%sb_rn{ax}{k} = OpExtInst %float {GLSL} RoundEven {pos}', f'%sb_dn{ax}{k} = OpFSub %float {pos} %sb_rn{ax}{k}',
                                 f'%sb_pp{ax}{k} = OpFAdd %float {pos} {dj}', f'%sb_rp{ax}{k} = OpExtInst %float {GLSL} RoundEven %sb_pp{ax}{k}',
                                 f'%sb_dp{ax}{k} = OpFSub %float %sb_pp{ax}{k} %sb_rp{ax}{k}',
                                 f'%sb_n2{ax}{k} = OpFMul %float %sb_dn{ax}{k} %sb_dn{ax}{k}', f'%sb_p2{ax}{k} = OpFMul %float %sb_dp{ax}{k} %sb_dp{ax}{k}']
                    code += [f'%sb_Dn{k} = OpFAdd %float %sb_n2x{k} %sb_n2y{k}', f'%sb_Dp{k} = OpFAdd %float %sb_p2x{k} %sb_p2y{k}',
                             f'%sb_dd{k} = OpFSub %float %sb_Dp{k} %sb_Dn{k}', f'%sb_ex{k} = OpFMul %float %sb_dd{k} %sb_k',
                             f'%sb_g{k} = OpExtInst %float {GLSL} Exp2 %sb_ex{k}', f'%sb_gc{k} = OpExtInst %float {GLSL} NMin %sb_g{k} %sb_cap',
                             f'%sb_gm{k} = OpFMul %float %sb_gc{k} ' + ('%sb_const' if CONST else '%sb_one'), f'%sb_om{k} = OpFSub %float %sb_one %sb_gm{k}'] + (
                             [f'%sb_ap{k} = OpFMul %float {a} {a}'] if AW == 2 else [f'%sb_ap{k} = OpFMul %float {a} %sb_one'] if AW == 1 else [f'%sb_ap{k} = OpFMul %float %sb_one %sb_one']) + [
                             f'%sb_ao{k} = OpFMul %float %sb_ap{k} %sb_om{k}', f'%sb_gw{k} = OpFSub %float %sb_one %sb_ao{k}',
                             f'%sb_wm{k} = OpFMul %float {w} %sb_gw{k}', f'%sb_wn{k} = OpExtInst %float {GLSL} NMin %sb_wm{k} %sb_one',
                             f'%sb_an{k} = OpFSub %float %sb_one %sb_wn{k}']
                    # the mix again with the corrected weights: the shader's own nine lines, renamed
                    sub = {w: f'%sb_wn{k}', a: f'%sb_an{k}'}
                    for x in pend['lines']:
                        r = re.match(r'\s*(%\w+) = ', x)[1]
                        sub[r] = f'%sb_t{k}_{r[1:]}'
                    for x in pend['lines']:
                        y = x.strip()
                        for p, q in sub.items():
                            y = re.sub(rf'{re.escape(p)}(?!\w)', q, y)
                        code.append(y)
                    mix = [sub[r] for r in sums]
                    if CLAMP is not None:
                        # the history clamped to the range of the nine samples of the new frame, widened by SB_CLAMP
                        # times that range: where the picture changed, the stale weight then mixes in a plausible colour
                        for c in range(3):
                            tc = samples(curs[c]); mn, mx = tc[0], tc[0]
                            for i, v in enumerate(tc[1:]):
                                code += [f'%sb_mn{c}{k}_{i} = OpExtInst %float {GLSL} NMin {mn} {v}', f'%sb_mx{c}{k}_{i} = OpExtInst %float {GLSL} NMax {mx} {v}']
                                mn, mx = f'%sb_mn{c}{k}_{i}', f'%sb_mx{c}{k}_{i}'
                            code += [f'%sb_rg{c}{k} = OpFSub %float {mx} {mn}', f'%sb_sl{c}{k} = OpFMul %float %sb_rg{c}{k} %sb_slack',
                                     f'%sb_lo{c}{k} = OpFSub %float {mn} %sb_sl{c}{k}', f'%sb_hi{c}{k} = OpFAdd %float {mx} %sb_sl{c}{k}',
                                     f'%sb_h1{c}{k} = OpExtInst %float {GLSL} NMin {h[c]} %sb_hi{c}{k}', f'%sb_hc{c}{k} = OpExtInst %float {GLSL} NMax %sb_h1{c}{k} %sb_lo{c}{k}',
                                     f'%sb_hd{c}{k} = OpFSub %float %sb_hc{c}{k} {h[c]}', f'%sb_ha{c}{k} = OpFMul %float %sb_hd{c}{k} %sb_an{k}',
                                     f'%sb_rc{c}{k} = OpFAdd %float {mix[c]} %sb_ha{c}{k}']
                            mix[c] = f'%sb_rc{c}{k}'
                    if GUARD:
                        # where the history is far darker than the new frame in every channel (it scrolled in from outside
                        # the screen when a pan started), the new frame alone: no dark band at the screen edge
                        code += [x for c in range(3) for x in (f'%sb_zm{c}{k} = OpFMul %float {curs[c]} %sb_rel', f'%sb_zt{c}{k} = OpExtInst %float {GLSL} NMax %sb_zm{c}{k} %sb_thr',
                                                              f'%sb_z{c}{k} = OpFOrdLessThanEqual %bool {h[c]} %sb_zt{c}{k}')] + [
                            f'%sb_zz{k} = OpLogicalAnd %bool %sb_z0{k} %sb_z1{k}', f'%sb_gd{k} = OpLogicalAnd %bool %sb_zz{k} %sb_z2{k}'] + [
                            f'%sb_rg_{c}{k} = OpSelect %float %sb_gd{k} {curs[c]} {mix[c]}' for c in range(3)]
                        mix = [f'%sb_rg_{c}{k}' for c in range(3)]
                    code += [f'OpBranch %sb_M{k}', f'%sb_M{k} = OpLabel'] + [f'%sb_r{c}{k} = OpPhi %float {mix[c]} %sb_T{k} {sums[c]} {cur_label}' for c in range(3)]
                    out += code
                    for c in range(3):
                        ren[sums[c]] = f'%sb_r{c}{k}'
                    for p in list(lab):
                        if lab[p] == cur_label:
                            lab[p] = f'%sb_M{k}'
                    lab[cur_label] = f'%sb_M{k}'; cur_label = f'%sb_M{k}'
                    n_guard += 1; pend = None
        m = re.match(r'\s*(%\w+) = OpFSub %float %float_1 (%\w+)$', L[n])
        if m and re.match(r'OpFDiv %float %float_1 ', defs.get(m[2], '')):
            pend = {'k': n_sites, 'w': m[1], 'a': m[2], 'cur': {}, 'hist': [], 'sum': [], 'lines': [], 'posx': posx, 'posy': posy}
            n_sites += 1
if (GUARD or BRANCH) and n_guard != 4:
    sys.exit(f'skipblend: {n_guard} guard sites found, expected 4')
if n_sites != 4:
    sys.exit(f'skipblend: {n_sites} blend sites found, expected 4')
sys.stdout.write('\n'.join(out))
