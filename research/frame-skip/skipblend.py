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
# Frames that ran the model keep the model's values bit for bit.
# Options (environment): SB_K (default 32), SB_AW (0, 1 or 2: power of a in the factor, default 1),
# SB_CONST (a further constant factor on skipped frames), SB_CAP (upper limit of the 2^ term,
# default 1; above 1 also raises the new frame's weight where a sample came closer: more flicker).
import os, re, sys
K = float(os.environ.get('SB_K', '32')); CONST = os.environ.get('SB_CONST'); CAP = float(os.environ.get('SB_CAP', '1')); AW = int(os.environ.get('SB_AW', '1'))
L = sys.stdin.read().split('\n')
S = int(sys.argv[1]) if len(sys.argv) > 1 else next((x for x in (15392, 30752, 61472) if any(f'%uint_{x} = ' in l for l in L)), None) or sys.exit('skipblend: no known row size')
defs = {m[1]: m[2] for l in L for m in [re.match(r'\s*(%\w+) = (.*)$', l)] if m}
width = S // 16 - 2; REGION = (width * 9 // 16 + 2) * S; WM = (REGION + S + 128) // 4
main = next(n for n, l in enumerate(L) if '= OpFunction' in l)
SSBO = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpVariable %_ptr_StorageBuffer__runtimearr_SSBO StorageBuffer', l)] if m)
GLSL = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpExtInstImport "GLSL.std.450"', l)] if m)
ge = [n for n, l in enumerate(L) if n > main and 'OpUGreaterThanEqual %bool' in l][:2]
br = next(n for n in range(ge[1], len(L)) if 'OpBranchConditional' in L[n])
lab = L[br].split()[-1]
at = next(n for n, l in enumerate(L) if re.match(rf'\s*{re.escape(lab)} = OpLabel', l))
c = ['%sb_m1 = OpConstant %uint 1511506142', '%sb_m2 = OpConstant %uint 168889943', f'%sb_k = OpConstant %float {K}', '%sb_one = OpConstant %float 1',
     f'%sb_cap = OpConstant %float {CAP}', '%sb_c0 = OpConstant %uint 0', '%sb_zero = OpConstant %float 0'] + [f'%sb_w{k} = OpConstant %uint {WM + k}' for k in range(4)]
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
posx = posy = None; n_sites = 0; ren = {}
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
if n_sites != 4:
    sys.exit(f'skipblend: {n_sites} blend sites found, expected 4')
sys.stdout.write('\n'.join(out))
