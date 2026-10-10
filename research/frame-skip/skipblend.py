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
# picture has changed since the model last ran, the stale a then mixes in a plausible color
# instead of an outdated one.
# All of this sits in one branch per output pixel that is taken on skipped frames only.
# Frames that ran the model keep the model's values bit for bit.
# Options (environment): SB_K (default 32), SB_AW (0, 1 or 2: power of a in the factor, default 1),
# SB_REL (default 0.1), SB_THR (absolute floor of the guard's limit, default 0), SB_GUARD=0 (no guard),
# SB_CLAMP (default 0.5; "off" for none), SB_BRANCH=0 (the layout of releases dll-2026-10-06.2 and .3:
# no branch, selects instead; with SB_CLAMP=off it rebuilds release .3's files),
# SB_UNCOV (default "depth": a pixel whose content was hidden a frame ago behind a nearer surface that moves
# differently takes the new frame alone, from the motion and depth frameskip.py's prepass stores; "off" for none,
# as up to release dll-2026-10-06.5; "1": without the depth test), SB_UNCOV_OFFS (how far, in cells, the other
# surface is looked for on each side, default "3,8"; "8" in release dll-2026-10-06.6),
# SB_REST (default 1: where the cell's stored motion is zero and nothing looked at around it moves differently, a
# skipped frame takes nothing from the new frame, so fine detail at rest shimmers no more than with AMD's shaders;
# 0 for release dll-2026-10-06.6's behavior),
# Content that changes without motion vectors (particles, sparks, embers): the rest rule would freeze it on every skipped
# frame, and the weight the model worked out a frame ago says "keep the old picture" where it has only just arrived.
# Three tests find it; where one fires, the rest rule does not apply:
#   SB_PART (default 0.25; "off"): the history lies outside the range of the nine new samples, widened by SB_PART x range;
#   SB_BRIGHT (default 0.25; "off"; SB_BRIGHTABS 0.05; SB_BRIGHTSYM=0: brighter only): the resampled new frame differs from
#     the history by more than SB_BRIGHT x range + SB_BRIGHTABS (slow things that still overlap their last image);
#   SB_SAMPLE (default 1; "off"; SB_SAMPLEABS 0.05; SB_SAMPLEFULL 1): the nearest new sample (the one of the nine with the
#     largest weight) lies outside the range of the 3x3 history pixels around the pixel by more than SB_SAMPLE x range +
#     SB_SAMPLEABS. A sample is one point of the scene, so for unchanged content it lies inside that range however fine the
#     detail; this is what tells an arriving spark from still detail under another jitter. Such a pixel takes the new frame
#     by how far outside the sample is: all of it SB_SAMPLEFULL x range beyond the threshold. SB_SAMPLEALL=0: at rest only
#     (default: also in motion, where the history is already aligned to the frame).
# SB_SAMPLEABS=0.02 SB_BRIGHTABS=0.02 gives release dll-2026-10-09's behavior (it let film grain and noise through on
# skipped frames: the grain trips the sample test as a spark does). SB_PART=off SB_BRIGHT=off SB_SAMPLE=off gives release dll-2026-10-07's behavior. SB_FULLW is a rejected experiment
# (the new frame in proportion to the SB_BRIGHT difference: two to three times the shimmer at rest).
# SB_CONST (a constant factor on the 2^ term on skipped frames, default 0: (1 - a) becomes (1 - a)^2,
# the new frame counts for very little where the model keeps history; "off" for none, as in release
# dll-2026-10-06.4), SB_CAP (upper limit of the 2^ term,
# default 1; above 1 also raises the new frame's weight where a sample came closer: more flicker).
import os, re, sys
# the changed-content tests (below) are on by default; "off" switches one off
for _k, _v in (('SB_PART', '0.25'), ('SB_BRIGHT', '0.25'), ('SB_BRIGHTSYM', '1'), ('SB_SAMPLE', '1'), ('SB_SAMPLEFULL', '1'), ('SB_SAMPLEALL', '1')):
    os.environ.setdefault(_k, _v)
    if os.environ[_k] == 'off':
        del os.environ[_k]
K = float(os.environ.get('SB_K', '32')); CONST = None if os.environ.get('SB_CONST') == 'off' else os.environ.get('SB_CONST', '0'); CAP = float(os.environ.get('SB_CAP', '1')); AW = int(os.environ.get('SB_AW', '1'))
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
c = ([f'%ss_m = OpConstant %float {float(os.environ["SB_SAMPLE"])}', f'%ss_abs = OpConstant %float {float(os.environ.get("SB_SAMPLEABS", "0.05"))}', f'%ss_full = OpConstant %float {float(os.environ.get("SB_SAMPLEFULL", "0.5"))}', '%ss_o4294967295 = OpConstant %uint 4294967295', '%ss_o0 = OpConstant %uint 0', '%ss_o1 = OpConstant %uint 1'] if os.environ.get('SB_SAMPLE') else []) + ([f'%sb_fullw = OpConstant %float {float(os.environ["SB_FULLW"])}', '%sb_feps = OpConstant %float 0.0001'] if os.environ.get('SB_FULLW') else []) + ([f'%sb_brw = OpConstant %float {float(os.environ["SB_BRIGHT"])}', f'%sb_bra = OpConstant %float {float(os.environ.get("SB_BRIGHTABS", "0.05"))}'] if os.environ.get('SB_BRIGHT') else []) + ([f'%sb_partw = OpConstant %float {float(os.environ["SB_PART"])}', f'%sb_parta = OpConstant %float {float(os.environ.get("SB_PARTABS", "0"))}'] if os.environ.get('SB_PART') else []) + (['%sb_tt = OpConstantTrue %bool'] if os.environ.get('SB_FORCESKIP') else []) + ['%sb_m1 = OpConstant %uint 1511506142', '%sb_m2 = OpConstant %uint 168889943', f'%sb_k = OpConstant %float {K}', '%sb_one = OpConstant %float 1',
     f'%sb_cap = OpConstant %float {CAP}', '%sb_c0 = OpConstant %uint 0', '%sb_zero = OpConstant %float 0', f"%sb_thr = OpConstant %float {float(os.environ.get('SB_THR', '0'))}", f"%sb_rel = OpConstant %float {float(os.environ.get('SB_REL', '0.1'))}"] + ([f"%sb_slack = OpConstant %float {CLAMP}"] if CLAMP is not None else []) + [f'%sb_w{k} = OpConstant %uint {WM + k}' for k in range(4)]
if CONST:
    c.append(f'%sb_const = OpConstant %float {float(CONST)}')
head = ['%sb_r1 = OpAccessChain %_ptr_PushConstant_uint %registers %uint_1', '%sb_r = OpLoad %uint %sb_r1', '%sb_bi = OpIAdd %uint %sb_r %uint_11',
        f'%sb_bp = OpAccessChain %_ptr_StorageBuffer_SSBO {SSBO} %sb_bi']
for k in range(4):
    head += [f'%sb_p{k} = OpAccessChain %_ptr_StorageBuffer_uint %sb_bp %uint_0 %sb_w{k}', f'%sb_v{k} = OpLoad %uint %sb_p{k}']
head += ['%sb_e1 = OpIEqual %bool %sb_v0 %sb_m1', '%sb_e2 = OpIEqual %bool %sb_v1 %sb_m2', *(['%sb_e3 = OpINotEqual %bool %sb_v0 %sb_m1', '%sb_skip = OpLogicalOr %bool %sb_e1 %sb_e3'] if os.environ.get('SB_FORCESKIP') else ['%sb_skip = OpLogicalAnd %bool %sb_e1 %sb_e2']),
         '%sb_pjx = OpBitcast %float %sb_v2', '%sb_pjy = OpBitcast %float %sb_v3',
         '%sb_pc = OpAccessChain %_ptr_PushConstant_v2uint %registers %uint_0', '%sb_ad = OpLoad %v2uint %sb_pc',
         '%sb_cb = OpBitcast %_ptr_PhysicalStorageBuffer_PhysicalPointerFloat4NonWriteCBVArray %sb_ad',
         '%sb_f1p = OpInBoundsAccessChain %_ptr_PhysicalStorageBuffer_v4float %sb_cb %uint_0 %uint_1', '%sb_f1 = OpLoad %v4float %sb_f1p Aligned 16',
         '%sb_jx = OpCompositeExtract %float %sb_f1 2', '%sb_jy = OpCompositeExtract %float %sb_f1 3',
         '%sb_djx = OpFSub %float %sb_pjx %sb_jx', '%sb_djy = OpFSub %float %sb_pjy %sb_jy']
BRIGHT = os.environ.get('SB_BRIGHT'); FULLW = os.environ.get('SB_FULLW')
SAMPLE = os.environ.get('SB_SAMPLE')      # test: at rest, compare the nearest new sample with the range of the history around the pixel
def _heap(img):
    ld = re.match(r'OpLoad %\w+ (%\w+)', defs.get(img, '')); ac = ld and re.match(r'OpAccessChain %\w+ (%\w+) (%\w+)', defs.get(ld[1], '')); ia = ac and re.match(r'OpIAdd %uint %\w+ (%\w+)', defs.get(ac[2], ''))
    return ia[1] if ia else None
HFETCH = []; CIMG = []
def _scan():
    for l in L:
        m = re.match(r'\s*(%\w+) = OpImageFetch %v4float (%\w+) (%\w+) Lod', l)
        if m and _heap(m[2]) == '%uint_9':
            cc = re.match(r'OpCompositeConstruct %v2uint (%\w+) (%\w+)', defs.get(m[3], '')) or sys.exit('skipblend: unexpected history coordinate')
            HFETCH.append((m[2], cc[1], cc[2]))
        if m and _heap(m[2]) == '%uint_3':
            CIMG.append(m[2])
def part_sample(k, h, curs):
    """f = how far the nearest new sample lies outside the range of the 3x3 history pixels around this one (0..1), at rest only"""
    if not HFETCH:
        _scan()
    site = int(k) if str(k).isdigit() else None
    idx = PART_SITE[0]; PART_SITE[0] += 1
    img, cx, cy = HFETCH[idx % len(HFETCH)]; cimg = CIMG[(idx % len(HFETCH)) * (len(CIMG) // len(HFETCH))]
    code = []; mn = [None] * 3; mx = [None] * 3
    for j, (dx, dy) in enumerate([(a, b) for b in (-1, 0, 1) for a in (-1, 0, 1)]):
        t = f'%ss_{k}_{j}'
        code += [f'{t}x0 = OpIAdd %uint {cx} {SU(dx)}', f'{t}y0 = OpIAdd %uint {cy} {SU(dy)}', f'{t}x = OpExtInst %uint {GLSL} SMax {t}x0 %sb_c0', f'{t}y = OpExtInst %uint {GLSL} SMax {t}y0 %sb_c0',
                 f'{t}c = OpCompositeConstruct %v2uint {t}x {t}y', f'{t}f = OpImageFetch %v4float {img} {t}c Lod %sb_c0']
        for c in range(3):
            code.append(f'{t}v{c} = OpCompositeExtract %float {t}f {c}')
            if mn[c] is None:
                mn[c] = mx[c] = f'{t}v{c}'
            else:
                code += [f'{t}n{c} = OpExtInst %float {GLSL} NMin {mn[c]} {t}v{c}', f'{t}m{c} = OpExtInst %float {GLSL} NMax {mx[c]} {t}v{c}']; mn[c], mx[c] = f'{t}n{c}', f'{t}m{c}'
    t = f'%ss_{k}_s'
    fs = []
    for c in range(3):
        # the nearest sample: the one of the nine with the largest weight, as the shader has prepared it for the mix
        tc = samples_w(curs[c]); bv, bw = tc[0]
        for i, (v, w) in enumerate(tc[1:]):
            code += [f'{t}cg{c}_{i} = OpFOrdGreaterThan %bool {w} {bw}', f'{t}cw{c}_{i} = OpSelect %float {t}cg{c}_{i} {w} {bw}', f'{t}cv{c}_{i} = OpSelect %float {t}cg{c}_{i} {v} {bv}']
            bv, bw = f'{t}cv{c}_{i}', f'{t}cw{c}_{i}'
        code += [f'{t}v{c} = OpFMul %float {bv} %sb_one', f'{t}r{c} = OpFSub %float {mx[c]} {mn[c]}', f'{t}a{c} = OpFMul %float {t}r{c} %ss_m', f'{t}b{c} = OpFAdd %float {t}a{c} %ss_abs',
                 f'{t}hi{c} = OpFSub %float {t}v{c} {mx[c]}', f'{t}lo{c} = OpFSub %float {mn[c]} {t}v{c}', f'{t}e0{c} = OpExtInst %float {GLSL} NMax {t}hi{c} {t}lo{c}', f'{t}e{c} = OpFSub %float {t}e0{c} {t}b{c}',
                 f'{t}d0{c} = OpFMul %float {t}r{c} %ss_full', f'{t}d{c} = OpFAdd %float {t}d0{c} %ss_abs', f'{t}q{c} = OpFDiv %float {t}e{c} {t}d{c}', f'{t}g{c} = OpExtInst %float {GLSL} NClamp {t}q{c} %sm_fz %sb_one']
        fs.append(f'{t}g{c}')
    code += [f'{t}g01 = OpExtInst %float {GLSL} NMax {fs[0]} {fs[1]}', f'{t}g = OpExtInst %float {GLSL} NMax {t}g01 {fs[2]}', (f'%sb_pf{k} = OpFMul %float {t}g %sb_one' if os.environ.get('SB_SAMPLEALL') == '1' else f'%sb_pf{k} = OpSelect %float %sm_rest {t}g %sm_fz'),
             f'{t}z = OpFOrdLessThanEqual %bool %sb_pf{k} %sm_fz', f'%sb_rq{k} = OpLogicalAnd %bool %sm_rest {t}z']
    return code
PART_SITE = [0]
SUC = {}
def SU(v):
    SUC[v] = f'%ss_o{v & 0xffffffff}'; return SUC[v]
PART = os.environ.get('SB_PART'); PARTABS = float(os.environ.get('SB_PARTABS', '0'))
def part(k, curs, h):
    if SAMPLE is not None:      # both tests: the rest rule holds only where neither sees a change; the share of the new frame is the larger of the two
        a = [l.replace(f'%sb_rq{k} ', f'%sb_rqO{k} ').replace(f'%sb_pf{k} ', f'%sb_pfO{k} ') for l in part_old(k, curs, h)]
        b = [l.replace(f'%sb_rq{k} ', f'%sb_rqS{k} ').replace(f'%sb_pf{k} ', f'%sb_pfS{k} ').replace(f'%sb_pf{k}\n', f'%sb_pfS{k}\n') for l in part_sample(k, h, curs)]
        b = [re.sub(rf'%sb_pf{k}(?!\w)', f'%sb_pfS{k}', l) for l in b]
        return a + b + [f'%sb_rq{k} = OpLogicalAnd %bool %sb_rqO{k} %sb_rqS{k}', f'%sb_pf{k} = OpExtInst %float {GLSL} NMax %sb_pfO{k} %sb_pfS{k}']
    return part_old(k, curs, h)


def part_old(k, curs, h):
    if PART is None:
        return [f'%sb_rq{k} = OpLogicalAnd %bool %sm_rest %sm_rest', f'%sb_pf{k} = OpFMul %float %sm_fz %sm_fz']
    code, outs = [], []
    for c in range(3):
        tc = samples(curs[c]); mn, mx = tc[0], tc[0]
        for i, v in enumerate(tc[1:]):
            code += [f'%sb_qn{c}{k}_{i} = OpExtInst %float {GLSL} NMin {mn} {v}', f'%sb_qx{c}{k}_{i} = OpExtInst %float {GLSL} NMax {mx} {v}']
            mn, mx = f'%sb_qn{c}{k}_{i}', f'%sb_qx{c}{k}_{i}'
        code += [f'%sb_qr{c}{k} = OpFSub %float {mx} {mn}', f'%sb_qs{c}{k} = OpFMul %float %sb_qr{c}{k} %sb_partw', f'%sb_qt{c}{k} = OpFAdd %float %sb_qs{c}{k} %sb_parta',
                 f'%sb_ql{c}{k} = OpFSub %float {mn} %sb_qt{c}{k}', f'%sb_qh{c}{k} = OpFAdd %float {mx} %sb_qt{c}{k}',
                 f'%sb_qa{c}{k} = OpFOrdLessThan %bool {h[c]} %sb_ql{c}{k}', f'%sb_qb{c}{k} = OpFOrdGreaterThan %bool {h[c]} %sb_qh{c}{k}', f'%sb_qo{c}{k}' + ('x' if BRIGHT is not None else '') + f' = OpLogicalOr %bool %sb_qa{c}{k} %sb_qb{c}{k}']
        if BRIGHT is not None:      # SB_BRIGHT (test): also where the resampled new frame is brighter than the history by SB_BRIGHT x range + SB_BRIGHTABS (SB_BRIGHTSYM=1: or darker)
            code += [f'%sb_bs{c}{k} = OpFMul %float %sb_qr{c}{k} %sb_brw', f'%sb_bt{c}{k} = OpFAdd %float %sb_bs{c}{k} %sb_bra', f'%sb_bd{c}{k} = OpFSub %float {curs[c]} {h[c]}',
                     f'%sb_bg{c}{k} = OpFOrdGreaterThan %bool %sb_bd{c}{k} %sb_bt{c}{k}']
            if FULLW is not None:      # SB_FULLW (test): how much of the new frame such a pixel takes: from nothing at the threshold to all of it SB_FULLW x range above
                code += [f'%sb_fa{c}{k} = OpExtInst %float {GLSL} FAbs %sb_bd{c}{k}', f'%sb_fb{c}{k} = OpFSub %float %sb_fa{c}{k} %sb_bt{c}{k}',
                         f'%sb_fc{c}{k} = OpFMul %float %sb_qr{c}{k} %sb_fullw', f'%sb_fd{c}{k} = OpFAdd %float %sb_fc{c}{k} %sb_feps', f'%sb_fe{c}{k} = OpFDiv %float %sb_fb{c}{k} %sb_fd{c}{k}',
                         f'%sb_ff{c}{k} = OpExtInst %float {GLSL} NClamp %sb_fe{c}{k} %sm_fz %sb_one']
            if os.environ.get('SB_BRIGHTSYM') == '1':
                code += [f'%sb_bn{c}{k} = OpFNegate %float %sb_bd{c}{k}', f'%sb_bl{c}{k} = OpFOrdGreaterThan %bool %sb_bn{c}{k} %sb_bt{c}{k}', f'%sb_bgs{c}{k} = OpLogicalOr %bool %sb_bg{c}{k} %sb_bl{c}{k}']
                code.append(f'%sb_qo{c}{k} = OpLogicalOr %bool %sb_qo{c}{k}x %sb_bgs{c}{k}')
            else:
                code.append(f'%sb_qo{c}{k} = OpLogicalOr %bool %sb_qo{c}{k}x %sb_bg{c}{k}')
        outs.append(f'%sb_qo{c}{k}')
    if FULLW is not None and BRIGHT is not None:
        code += [f'%sb_fm{k} = OpExtInst %float {GLSL} NMax %sb_ff0{k} %sb_ff1{k}', f'%sb_fn{k} = OpExtInst %float {GLSL} NMax %sb_fm{k} %sb_ff2{k}', f'%sb_pf{k} = OpSelect %float %sm_rest %sb_fn{k} %sm_fz']
    else:
        code += [f'%sb_pf{k} = OpFMul %float %sm_fz %sm_fz']
    return code + [f'%sb_qo01{k} = OpLogicalOr %bool {outs[0]} {outs[1]}', f'%sb_chg{k} = OpLogicalOr %bool %sb_qo01{k} {outs[2]}', f'%sb_nchg{k} = OpLogicalNot %bool %sb_chg{k}',
                   f'%sb_rq{k} = OpLogicalAnd %bool %sm_rest %sb_nchg{k}']
CLAMPM = float(os.environ['SB_CLAMPM']) if os.environ.get('SB_CLAMPM') else None
UNCOV = os.environ.get('SB_UNCOV', 'depth') in ('1', 'depth'); DEPTH = os.environ.get('SB_UNCOV', 'depth') == 'depth'
REST = UNCOV and os.environ.get('SB_REST', '1') == '1'
HEAD_LABEL = None
if CLAMPM is not None or UNCOV:
    Xc, WCc = L[ge[0]].split()[-2:]; Yc, HCc = L[ge[1]].split()[-2:]
    c += ['%sm_c1 = OpConstant %uint 1', '%sm_c16 = OpConstant %uint 16', f'%sm_base = OpConstant %uint {(REGION + S) // 4}', f'%sm_row = OpConstant %uint {S // 4}',
          '%sm_b0 = OpConstant %uint 48', f'%sm_b1 = OpConstant %uint {(2048 if S == 15392 else 4096)}', f'%sm_lo = OpConstant %uint {(-254) & 0xffffffff}', '%sm_hi = OpConstant %uint 254',
          f'%sm_dbase = OpConstant %uint {(REGION * 3 // 2 + 2 * S) // 4}', '%sm_db1 = OpConstant %uint 5120', '%sm_two = OpConstant %uint 2', '%sm_false = OpConstantFalse %bool', '%sm_m1 = OpConstant %uint 4294967295', '%sm_fz = OpConstant %float 0', '%sm_fone = OpConstant %float 1'] + (
          [f'%sm_inv = OpConstant %float {1.0 / CLAMPM}'] if CLAMPM is not None else [])

    def mread(p, x, y):
        """motion (output pixels, signed) stored for the cell (x, y), clamped into the frame; one entry per 2x2 cells"""
        return [f'{p}xc = OpExtInst %uint {GLSL} SClamp {x} %sb_c0 %sm_wm', f'{p}yc = OpExtInst %uint {GLSL} SClamp {y} %sb_c0 %sm_hm',
                f'{p}xq = OpShiftRightLogical %uint {p}xc %sm_c1', f'{p}yq = OpShiftRightLogical %uint {p}yc %sm_c1',
                f'{p}yr = OpShiftRightLogical %uint {p}yq %sm_c1', f'{p}yo = OpBitwiseAnd %uint {p}yq %sm_c1', f'{p}yb = OpINotEqual %bool {p}yo %sb_c0',
                f'{p}bk = OpSelect %uint {p}yb %sm_b1 %sm_b0', f'{p}rw = OpIMul %uint {p}yr %sm_row', f'{p}a1 = OpIAdd %uint %sm_base {p}rw', f'{p}a2 = OpIAdd %uint {p}a1 {p}bk',
                f'{p}x2 = OpShiftLeftLogical %uint {p}xq %sm_c1', f'{p}ix = OpIAdd %uint {p}a2 {p}x2',
                f'{p}pm = OpAccessChain %_ptr_StorageBuffer_uint %sb_bp %uint_0 {p}ix', f'{p}m = OpLoad %uint {p}pm',
                f'{p}xs = OpShiftLeftLogical %uint {p}m %sm_c16', f'{p}d0 = OpShiftRightArithmetic %uint {p}xs %sm_c16', f'{p}e0 = OpShiftRightArithmetic %uint {p}m %sm_c16',
                f'{p}dx = OpExtInst %uint {GLSL} SClamp {p}d0 %sm_lo %sm_hi', f'{p}dy = OpExtInst %uint {GLSL} SClamp {p}e0 %sm_lo %sm_hi']

    def dread(p):
        """the nearest depth stored in the same entry (smaller = nearer); 0 where the border clearing wiped it"""
        return [f'{p}di = OpIAdd %uint {p}ix %sm_c1', f'{p}dp = OpAccessChain %_ptr_StorageBuffer_uint %sb_bp %uint_0 {p}di', f'{p}du = OpLoad %uint {p}dp', f'{p}z = OpBitcast %float {p}du']

    def near(p, ax, ay, bx, by, lim):
        """bool: |a - b| <= lim in both components"""
        return [f'{p}sx = OpISub %uint {ax} {bx}', f'{p}sy = OpISub %uint {ay} {by}', f'{p}ux = OpExtInst %uint {GLSL} SAbs {p}sx', f'{p}uy = OpExtInst %uint {GLSL} SAbs {p}sy',
                f'{p}mx = OpExtInst %uint {GLSL} UMax {p}ux {p}uy', f'{p} = OpULessThanEqual %bool {p}mx {lim}']

    mh = ['OpSelectionMerge %sm_M None', 'OpBranchConditional %sb_skip %sm_T %sm_M', '%sm_T = OpLabel',
          f'%sm_wm = OpIAdd %uint {WCc} %sm_m1', f'%sm_hm = OpIAdd %uint {HCc} %sm_m1'] + mread('%sm_p', Xc, Yc) + [
          '%sm_ax = OpExtInst %uint ' + GLSL + ' SAbs %sm_pdx', '%sm_ay = OpExtInst %uint ' + GLSL + ' SAbs %sm_pdy', '%sm_am = OpExtInst %uint ' + GLSL + ' UMax %sm_ax %sm_ay',
          '%sm_af = OpConvertUToF %float %sm_am'] + (dread('%sm_p') if DEPTH else [])
    flag = '%sm_false'; pred = '%sm_T'
    if UNCOV:
        # Candidates for "another surface": what now sits where this pixel's content was, and what sits a little
        # way off on each side (SB_UNCOV_OFFS, in cells). First only their motion is read; the rest of the test
        # (two more reads per candidate) runs in a branch taken only where one of them moves differently from this
        # pixel, which is a small part of the picture.
        OFFS = [int(x) for x in os.environ.get('SB_UNCOV_OFFS', '3,8').split(',') if x]
        offs = [o for d in OFFS for o in ((d, 0), (-d, 0), (0, d), (0, -d))]
        # more candidates around q (SB_UNCOV_QOFFS, in cells): an object that has itself moved on screen is no longer exactly
        # where this pixel's content was, but close to it
        QOFFS = [int(x) for x in os.environ.get('SB_UNCOV_QOFFS', '').split(',') if x]
        qoffs = [o for d in QOFFS for o in ((d, 0), (-d, 0), (0, d), (0, -d))]
        cands = ['q'] + [f'n{i}' for i in range(len(offs))] + [f'm{i}' for i in range(len(qoffs))]
        consts_done = set(); any_ = None; stage2 = []
        if DEPTH:
            i0 = mh.index(dread('%sm_p')[0]); own_depth = mh[i0:]; mh = mh[:i0]       # this pixel's own depth: only needed in the branch
        else:
            own_depth = []
        for i, nm in enumerate(cands):
            p = f'%sm_{nm}'
            if nm == 'q':
                mh += [f'{p}hx = OpShiftRightArithmetic %uint %sm_pdx %sm_c1', f'{p}hy = OpShiftRightArithmetic %uint %sm_pdy %sm_c1',
                       f'{p}X = OpIAdd %uint {Xc} {p}hx', f'{p}Y = OpIAdd %uint {Yc} {p}hy']
            elif nm[0] == 'm':
                ox, oy = qoffs[int(nm[1:])]
                for v in (ox, oy):
                    if v not in consts_done:
                        c.append(f'%sm_k{v & 0xffffffff} = OpConstant %uint {v & 0xffffffff}'); consts_done.add(v)
                mh += [f'{p}X0 = OpIAdd %uint {Xc} %sm_qhx', f'{p}Y0 = OpIAdd %uint {Yc} %sm_qhy', f'{p}X = OpIAdd %uint {p}X0 %sm_k{ox & 0xffffffff}', f'{p}Y = OpIAdd %uint {p}Y0 %sm_k{oy & 0xffffffff}']
            else:
                ox, oy = offs[i - 1]
                for v in (ox, oy):
                    if v not in consts_done:
                        c.append(f'%sm_k{v & 0xffffffff} = OpConstant %uint {v & 0xffffffff}'); consts_done.add(v)
                mh += [f'{p}X = OpIAdd %uint {Xc} %sm_k{ox & 0xffffffff}', f'{p}Y = OpIAdd %uint {Yc} %sm_k{oy & 0xffffffff}']
            # the other surface's motion differs from this pixel's by 2 pixels or more ...
            mh += mread(p, f'{p}X', f'{p}Y') + near(f'{p}same', f'{p}dx', f'{p}dy', '%sm_pdx', '%sm_pdy', '%sm_c1') + [f'{p}diff = OpLogicalNot %bool {p}same']
            if any_:
                mh.append(f'{p}any = OpLogicalOr %bool {any_} {p}diff')
                any_ = f'{p}any'
            else:
                any_ = f'{p}diff'
            # ... and the point of that surface that was where this pixel's content was now sits at r = p + D_p - D_n, moving the same way
            stage2 += [f'{p}tx = OpISub %uint %sm_pdx {p}dx', f'{p}ty = OpISub %uint %sm_pdy {p}dy',
                       f'{p}thx = OpShiftRightArithmetic %uint {p}tx %sm_c1', f'{p}thy = OpShiftRightArithmetic %uint {p}ty %sm_c1',
                       f'{p}tX = OpIAdd %uint {Xc} {p}thx', f'{p}tY = OpIAdd %uint {Yc} {p}thy'] + mread(f'{p}t', f'{p}tX', f'{p}tY') + \
                      near(f'{p}there', f'{p}tdx', f'{p}tdy', f'{p}dx', f'{p}dy', '%sm_c1') + (
                       # ... and it is in front of this pixel's surface (so this pixel's content was hidden behind it)
                       dread(f'{p}t') + [f'{p}front = OpFOrdLessThan %bool {p}tz %sm_pz', f'{p}wiped = OpIEqual %bool {p}tdu %sb_c0', f'{p}okd = OpLogicalNot %bool {p}wiped',
                                         f'{p}fr = OpLogicalAnd %bool {p}front {p}okd', f'{p}th2 = OpLogicalAnd %bool {p}there {p}fr'] if DEPTH else [f'{p}th2 = OpLogicalAnd %bool {p}there {p}there']) + [
                       f'{p}hit = OpLogicalAnd %bool {p}diff {p}th2', f'{p}acc = OpLogicalOr %bool {flag} {p}hit']
            flag = f'{p}acc'
        # at rest: this cell does not move, and neither does anything looked at around it
        if REST:
            mh += ['%sm_c0u = OpIEqual %bool %sm_am %sb_c0', f'%sm_nany = OpLogicalNot %bool {any_}', '%sm_rin = OpLogicalAnd %bool %sm_c0u %sm_nany']
        if DEPTH and os.environ.get('SB_PLANE', '1') == '1':
            # The exact form of that test: the prepass has recorded, for every block, the nearest surface that was there a
            # frame ago (frameskip.py). This pixel's content was at p + D_p then; if the surface recorded there is another
            # one (it moves differently) and nearer, the content was hidden behind it. One read, and three more where
            # anything is recorded; it replaces the guessing above, which missed objects that had themselves moved.
            from frameskip_layout import plane_layout
            L_ = plane_layout(S)
            c += [f'%sm_pb0 = OpConstant %uint {L_["pb0"]}', f'%sm_pb1 = OpConstant %uint {L_["pb1"]}', f'%sm_pnx = OpConstant %uint {L_["nx"]}', f'%sm_pny = OpConstant %uint {L_["ny"]}',
                  f'%sm_pxb = OpConstant %uint {L_["xb"]}', f'%sm_pxm = OpConstant %uint {(1 << L_["xb"]) - 1}', f'%sm_pim = OpConstant %uint {(1 << L_["idb"]) - 1}']
            mh += [f'%sm_Px0 = OpShiftLeftLogical %uint {Xc} %sm_c1', f'%sm_Py0 = OpShiftLeftLogical %uint {Yc} %sm_c1', '%sm_Px = OpIAdd %uint %sm_Px0 %sm_pdx', '%sm_Py = OpIAdd %uint %sm_Py0 %sm_pdy',
                   '%sm_Pbx = OpShiftRightArithmetic %uint %sm_Px %sm_two', '%sm_Pby = OpShiftRightArithmetic %uint %sm_Py %sm_two',
                   '%sm_Pix = OpULessThan %bool %sm_Pbx %sm_pnx', '%sm_Piy = OpULessThan %bool %sm_Pby %sm_pny', '%sm_Pin = OpLogicalAnd %bool %sm_Pix %sm_Piy',
                   '%sm_Pxs = OpSelect %uint %sm_Pin %sm_Pbx %sb_c0', '%sm_Pys = OpSelect %uint %sm_Pin %sm_Pby %sb_c0',
                   '%sm_Pyr = OpShiftRightLogical %uint %sm_Pys %sm_c1', '%sm_Pyo = OpBitwiseAnd %uint %sm_Pys %sm_c1', '%sm_Pyb = OpINotEqual %bool %sm_Pyo %sb_c0',
                   '%sm_Pbk = OpSelect %uint %sm_Pyb %sm_pb1 %sm_pb0', '%sm_Prw = OpIMul %uint %sm_Pyr %sm_row', '%sm_Pa1 = OpIAdd %uint %sm_base %sm_Prw', '%sm_Pa2 = OpIAdd %uint %sm_Pa1 %sm_Pbk',
                   '%sm_Pidx = OpIAdd %uint %sm_Pa2 %sm_Pxs', '%sm_Pp = OpAccessChain %_ptr_StorageBuffer_uint %sb_bp %uint_0 %sm_Pidx', '%sm_Pk0 = OpLoad %uint %sm_Pp',
                   '%sm_Pk = OpSelect %uint %sm_Pin %sm_Pk0 %sb_c0', '%sm_Pany = OpINotEqual %bool %sm_Pk %sb_c0']
            win = ['%sm_Wid = OpBitwiseAnd %uint %sm_Pk %sm_pim', '%sm_Wx = OpBitwiseAnd %uint %sm_Wid %sm_pxm', '%sm_Wy = OpShiftRightLogical %uint %sm_Wid %sm_pxb',
                   '%sm_Wyr = OpShiftRightLogical %uint %sm_Wy %sm_c1', '%sm_Wyo = OpBitwiseAnd %uint %sm_Wy %sm_c1', '%sm_Wyb = OpINotEqual %bool %sm_Wyo %sb_c0',
                   '%sm_Wbk = OpSelect %uint %sm_Wyb %sm_b1 %sm_b0', '%sm_Wrw = OpIMul %uint %sm_Wyr %sm_row', '%sm_Wa1 = OpIAdd %uint %sm_base %sm_Wrw', '%sm_Wa2 = OpIAdd %uint %sm_Wa1 %sm_Wbk',
                   '%sm_Wx2 = OpShiftLeftLogical %uint %sm_Wx %sm_c1', '%sm_Wix = OpIAdd %uint %sm_Wa2 %sm_Wx2',
                   '%sm_Wpm = OpAccessChain %_ptr_StorageBuffer_uint %sb_bp %uint_0 %sm_Wix', '%sm_Wm = OpLoad %uint %sm_Wpm',
                   '%sm_Wxs = OpShiftLeftLogical %uint %sm_Wm %sm_c16', '%sm_Wd0 = OpShiftRightArithmetic %uint %sm_Wxs %sm_c16', '%sm_We0 = OpShiftRightArithmetic %uint %sm_Wm %sm_c16',
                   f'%sm_Wdx = OpExtInst %uint {GLSL} SClamp %sm_Wd0 %sm_lo %sm_hi', f'%sm_Wdy = OpExtInst %uint {GLSL} SClamp %sm_We0 %sm_lo %sm_hi'] + \
                  near('%sm_Wsame', '%sm_Wdx', '%sm_Wdy', '%sm_pdx', '%sm_pdy', '%sm_c1') + dread('%sm_W') + [
                   '%sm_Wdiff = OpLogicalNot %bool %sm_Wsame', '%sm_Wfront = OpFOrdLessThan %bool %sm_Wz %sm_pz', '%sm_Wokd = OpINotEqual %bool %sm_Wdu %sb_c0',
                   '%sm_Wh1 = OpLogicalAnd %bool %sm_Wdiff %sm_Wfront', '%sm_Whit = OpLogicalAnd %bool %sm_Wh1 %sm_Wokd']
            mh += ['OpSelectionMerge %sm_M2 None', 'OpBranchConditional %sm_Pany %sm_T2 %sm_M2', '%sm_T2 = OpLabel'] + own_depth + win + [
                   'OpBranch %sm_M2', '%sm_M2 = OpLabel', '%sm_fl2 = OpPhi %bool %sm_Whit %sm_T2 %sm_false %sm_T']
        else:
            mh += ['OpSelectionMerge %sm_M2 None', f'OpBranchConditional {any_} %sm_T2 %sm_M2', '%sm_T2 = OpLabel'] + own_depth + stage2 + [
                   'OpBranch %sm_M2', '%sm_M2 = OpLabel', f'%sm_fl2 = OpPhi %bool {flag} %sm_T2 %sm_false %sm_T']
        flag = '%sm_fl2'; pred = '%sm_M2'
    mh += ['OpBranch %sm_M', '%sm_M = OpLabel', f'%sm_flag = OpPhi %bool {flag} {pred} %sm_false {lab0}', f'%sm_mag = OpPhi %float %sm_af {pred} %sm_fz {lab0}'] + ([f'%sm_rest = OpPhi %bool %sm_rin {pred} %sm_false {lab0}'] if REST else [])
    head = head + mh
    HEAD_LABEL = '%sm_M'
out = L[:main] + c + L[main:at + 1] + head
n_guard = 0


def samples_w(cur):
    """as samples(), but (value, weight) pairs"""
    m = re.match(r'OpFDiv %float (%\w+) %\w+$', defs.get(cur, '')) or sys.exit('skipblend: the resampled color is not a quotient')
    out, todo = [], [m[1]]
    while todo:
        t = todo.pop(); f = re.match(r'OpFMul %float (%\w+) (%\w+)$', defs.get(t, ''))
        w = [x for x in (f[1], f[2]) if re.match(r'OpExtInst %float %\w+ Exp2 ', defs.get(x, ''))] if f else []
        if len(w) == 1:
            out.append((f[2] if w[0] == f[1] else f[1], w[0])); continue
        a = re.match(r'OpFAdd %float (%\w+) (%\w+)$', defs.get(t, '')) or sys.exit('skipblend: unexpected shape of the weighted sum')
        todo += [a[1], a[2]]
    if len(out) != 9:
        sys.exit(f'skipblend: {len(out)} samples found for a pixel, expected 9')
    return out


def samples(cur):
    """The nine sample values (one channel) that the resampled color `cur` = sum(value * weight) / sum(weight) is made of."""
    m = re.match(r'OpFDiv %float (%\w+) %\w+$', defs.get(cur, '')) or sys.exit('skipblend: the resampled color is not a quotient')
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
                        # mixes in a plausible color instead of an outdated one
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
    if HEAD_LABEL:
        lab[lab0] = HEAD_LABEL; cur_label = HEAD_LABEL
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
                             f'%sb_wm{k} = OpFMul %float {w} %sb_gw{k}'] + (
                             # where the picture does not move, a skipped frame takes nothing from the new frame
                             (part(k, curs, h) + [f'%sb_wq{k} = OpSelect %float %sb_rq{k} %sm_fz %sb_wm{k}', f'%sb_wqq{k} = OpExtInst %float {GLSL} NMax %sb_wq{k} %sb_pf{k}', f'%sb_wn{k} = OpExtInst %float {GLSL} NMin %sb_wqq{k} %sb_one'])
                             if REST else [f'%sb_wn{k} = OpExtInst %float {GLSL} NMin %sb_wm{k} %sb_one']) + [
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
                        # times that range: where the picture changed, the stale weight then mixes in a plausible color
                        if CLAMPM is not None:
                            code += [f'%sb_slm{k} = OpFMul %float %sm_mag %sm_inv', f'%sb_sln{k} = OpFSub %float %sm_fone %sb_slm{k}',
                                     f'%sb_slp{k} = OpExtInst %float {GLSL} NMax %sb_sln{k} %sm_fz', f'%sb_sle{k} = OpFMul %float %sb_slack %sb_slp{k}']
                        for c in range(3):
                            tc = samples(curs[c]); mn, mx = tc[0], tc[0]
                            for i, v in enumerate(tc[1:]):
                                code += [f'%sb_mn{c}{k}_{i} = OpExtInst %float {GLSL} NMin {mn} {v}', f'%sb_mx{c}{k}_{i} = OpExtInst %float {GLSL} NMax {mx} {v}']
                                mn, mx = f'%sb_mn{c}{k}_{i}', f'%sb_mx{c}{k}_{i}'
                            code += [f'%sb_rg{c}{k} = OpFSub %float {mx} {mn}', f'%sb_sl{c}{k} = OpFMul %float %sb_rg{c}{k} ' + (f'%sb_sle{k}' if CLAMPM is not None else '%sb_slack'),
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
                            f'%sb_zz{k} = OpLogicalAnd %bool %sb_z0{k} %sb_z1{k}', f'%sb_gd{k}' + ('a' if UNCOV else '') + f' = OpLogicalAnd %bool %sb_zz{k} %sb_z2{k}'] + (
                            [f'%sb_gd{k} = OpLogicalOr %bool %sb_gd{k}a %sm_flag'] if UNCOV else []) + [
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
