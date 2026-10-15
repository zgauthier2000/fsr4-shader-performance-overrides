#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# frameskip.py prepass < prepass.spvasm > out.spvasm
# frameskip.py model <pass number> <row bytes: 15392, 30752 or 61472> < passN.spvasm > out.spvasm
#   (row bytes: 16 times the widest tensor's row of the output-size class, 962, 1922 or 3842 cells:
#    output up to 1080p, up to 4K, larger)
#
# NOT bit-exact. Every other frame the model (passes 1 to 12) is skipped, and the postpass uses the
# model's output of the frame before, which is still in the working buffer.
#
# Which frames: those whose jitter x is negative. FSR's and DLSS's usual jitter (a Halton base-2
# sequence minus one half) changes sign every frame, and never gives two negative frames in a row.
# The prepass also never skips a frame that the game marks as a reset, or one whose render size is
# under half the output size (there the border clearing after the prepass would reach into the
# kept output).
#
# FS_UP=<y> (prepass; -0.1666667 since release dll-2026-10-15; FS_UP=off as before): skip below half the output width too (Ultra Performance), but
# there a frame with jitter x < 0 still runs the model when its jitter y < y. The frames that run the model otherwise all have jitter x >= 0 and
# sample only one half of each render pixel; with Halton base-3 jitter in y, -1/6 picks every third frame with x < 0, so that half is seen now and
# then, and two skips never follow each other. The border clearing feared above did no visible harm in the Ultra Performance checks (1080p to 5K).
# For the postpass's correction on skipped frames (skipblend.py) the jitter of the last frame that
# ran the model is carried over: prepass -> pass 11 -> pass 12 -> two words next to the mark.
# FS_TEST=same (prepass): test rule, skip a frame whose jitter equals that of the last frame that
# ran (used with a jitter list that repeats every entry, to show that jitter mismatch is the cause
# of the extra flicker).
#
# On a skipped frame the prepass leaves the model's input tensor as it is and its first thread
# writes a two-word mark into the working buffer; on other frames it clears it. Every model pass
# returns at once when it finds the mark.
# FS_BRANCH (prepass; default 1 since release dll-2026-10-12.2): the prepass's work in two copies
# under one branch on skip, the one for skipped frames without the tensor stores. FS_BRANCH=0 is
# the form of the releases before: one copy, each store writes back the word that was there.
# With FS_BRANCH=1 run exposure_steps.py BEFORE this tool.
# FS_ALPHA (prepass; default 1 since release dll-2026-10-13, needs FS_BRANCH=1): a skipped frame's copy writes every pixel's own
# motion into the fourth channel of the image the prepass writes per output pixel, for skipblend.py's rules (see below, at ALPHA).
#
# Where the mark is: the border-clearing shaders that run after every pass zero the top row, the
# left column and the cells just past the valid width and height of each tensor, and the passes
# write unused values beyond the valid width. So the mark sits in an interior cell near the top
# left of the second tensor region (row 1, column 8 for a tensor of this row size; row 2, column 6
# for one of half the row size, which shares the region). On a frame that runs, pass 1 overwrites
# it with its output before anything reads that tensor; on a skipped frame nothing writes there.
import re
import sys

mode = sys.argv[1]
import os
UP = None if os.environ.get('FS_UP', '-0.1666667') == 'off' else os.environ.get('FS_UP', '-0.1666667')      # FS_UP=<y> (prepass; default -0.1666667, off = as before): Ultra Performance, see the head of the file
TEST = os.environ.get('FS_TEST', '')        # FS_TEST=same: the test rule described below
L = sys.stdin.read().split('\n')
defs = {}
for l in L:
    m = re.match(r'\s*(%\w+) = (.*)$', l)
    if m:
        defs[m[1]] = m[2]


def die(msg):
    sys.exit(f'frameskip: {msg}')


if mode == 'model':
    npass, S = int(sys.argv[2]), int(sys.argv[3])
else:
    S = next((x for x in (15392, 30752, 61472) if f'%uint_{x}' in defs), None) or die('no known row size in the prepass')
width = S // 16 - 2
REGION = (width * 9 // 16 + 2) * S                   # where the second tensor region starts
W_MARK = (REGION + S + 128) // 4
M1, M2 = 0x5A17C0DE, 0x0A110E57
# The jitter of the last frame that ran the model, for the postpass of the skipped frame after it.
# The model passes do not see the frame's constants, so the prepass leaves the jitter in a cell
# that nothing writes before pass 11 (the left edge cell of a row near the end of pass 11's
# output, which pass 11 itself does not write), and pass 11, the last pass to write in the second
# region's neighborhood, copies it next to the mark, where it stays through the skipped frame.
W_RELAY = (REGION * 3 // 2 + (width * 9 // 16 * 15 // 16) * S) // 4
W_SAVE = W_MARK + 2
# Pass 11 reads the cell next to the mark (it is part of pass 10's output), so it cannot put the
# jitter there itself: it parks it in the buffer's first cell (a corner edge cell that no pass
# reads and that the border clearing zeroes again later), and pass 12, which reads only pass 11's
# output, moves it next to the mark.
W_HOP = 0

# How this shader writes to the working buffer (heap slot 11 of its table of writable buffers):
# taken from one of its own stores, because the same buffer is also bound read-only.
def chain_of(p):
    a = re.match(r'OpAccessChain (%\w+) (%\w+) %uint_0 %\w+$', defs.get(p, ''))
    b = a and re.match(r'OpAccessChain (%\w+) (%\w+) (%\w+)$', defs.get(a[2], ''))
    c = b and re.match(r'OpIAdd %uint (%\w+) %uint_11$', defs.get(b[3], ''))
    d = c and re.match(r'OpLoad %uint (%\w+)$', defs.get(c[1], ''))
    e = d and re.match(r'OpAccessChain (%\w+) (%\w+) (%\w+)$', defs.get(d[1], ''))
    return (e, b, a[1]) if e else None


st = next((chain_of(m[1]) for l in L for m in [re.match(r'\s*OpStore (%\w+) %\w+$', l)] if m and chain_of(m[1])), None) or die('no store to the working buffer')
rp, heap, elem_t = st
PAD = '               '


from frameskip_layout import plane_layout, holes_spv


def word_ptr(p, word):
    return [f'{p}rp = OpAccessChain {rp[1]} {rp[2]} {rp[3]}', f'{p}r = OpLoad %uint {p}rp', f'{p}i = OpIAdd %uint {p}r %uint_11',
            f'{p}b = OpAccessChain {heap[1]} {heap[2]} {p}i', f'{p}w = OpAccessChain {elem_t} {p}b %uint_0 {word}']


v3 = next((v for v, d in defs.items() if d == 'OpTypeVector %uint 3'), None) or die('no v3uint')
consts = [f'%fs_w1 = OpConstant %uint {W_MARK}', f'%fs_w2 = OpConstant %uint {W_MARK + 1}',
          f'%fs_m1 = OpConstant %uint {M1}', f'%fs_m2 = OpConstant %uint {M2}', '%fs_u0 = OpConstant %uint 0']
main_i = next(n for n, l in enumerate(L) if l.strip().startswith('%main = OpFunction'))


def first_thread(p, var, comps):
    c = [f'{p}v = OpLoad {v3} {var}']
    acc = None
    for k in comps:
        c.append(f'{p}c{k} = OpCompositeExtract %uint {p}v {k}')
        if acc:
            c.append(f'{p}o{k} = OpBitwiseOr %uint {acc} {p}c{k}')
            acc = f'{p}o{k}'
        else:
            acc = f'{p}c{k}'
    return c, acc


if mode == 'model':
    entry = re.match(r'\s*(%\w+) = OpLabel', L[main_i + 1])[1]
    k = main_i + 2
    while 'OpVariable' in L[k]:
        k += 1
    code = word_ptr('%fs_a', '%fs_w1') + word_ptr('%fs_b', '%fs_w2') + [
        '%fs_av = OpLoad %uint %fs_aw', '%fs_bv = OpLoad %uint %fs_bw',
        '%fs_ae = OpIEqual %bool %fs_av %fs_m1', '%fs_be = OpIEqual %bool %fs_bv %fs_m2',
        '%fs_skip = OpLogicalAnd %bool %fs_ae %fs_be',
        'OpSelectionMerge %fs_cont None', 'OpBranchConditional %fs_skip %fs_ret %fs_cont', '%fs_ret = OpLabel',
        'OpReturn', '%fs_cont = OpLabel']
    last = '%fs_cont'
    if npass in (11, 12):
        SRC, DST = (W_RELAY, W_HOP) if npass == 11 else (W_HOP, W_SAVE)
        if '%gl_GlobalInvocationID' in defs:
            ft, acc = first_thread('%fs_g', '%gl_GlobalInvocationID', (0, 1, 2))
        else:
            ft1, a1 = first_thread('%fs_wg', '%gl_WorkGroupID', (0, 1, 2))
            ft2, a2 = first_thread('%fs_li', '%gl_LocalInvocationID', (0, 1, 2))
            ft, acc = ft1 + ft2 + [f'%fs_gor = OpBitwiseOr %uint {a1} {a2}'], '%fs_gor'
        consts += [f'%fs_s1 = OpConstant %uint {DST}', f'%fs_s2 = OpConstant %uint {DST + 1}',
                   f'%fs_r1 = OpConstant %uint {SRC}', f'%fs_r2 = OpConstant %uint {SRC + 1}']
        code += ft + [f'%fs_first = OpIEqual %bool {acc} %fs_u0', 'OpSelectionMerge %fs_cont2 None',
                      'OpBranchConditional %fs_first %fs_save %fs_cont2', '%fs_save = OpLabel'] + \
            word_ptr('%fs_e', '%fs_r1') + word_ptr('%fs_f', '%fs_r2') + word_ptr('%fs_p', '%fs_s1') + word_ptr('%fs_q', '%fs_s2') + [
            '%fs_jx = OpLoad %uint %fs_ew', '%fs_jy = OpLoad %uint %fs_fw',
            'OpStore %fs_pw %fs_jx', 'OpStore %fs_qw %fs_jy', 'OpBranch %fs_cont2', '%fs_cont2 = OpLabel']
        last = '%fs_cont2'
    rest = [re.sub(rf'{re.escape(entry)}(?=\s|$)', last, x) if 'OpPhi' in x else x for x in L[k:]]
    out = L[:main_i] + [PAD + c for c in consts] + L[main_i:k] + [PAD + c for c in code] + rest
else:
    cb = next((n for n, l in enumerate(L) if re.search(r'= OpBitcast %_ptr_PhysicalStorageBuffer_PhysicalPointer(Float|Uint)4NonWriteCBVArray (%\w+)', l)), None)
    if cb is None or '%_ptr_PhysicalStorageBuffer_PhysicalPointerUint4NonWriteCBVArray' not in defs:
        die('the prepass does not read its constants the expected way')
    cbv = re.search(r'NonWriteCBVArray (%\w+)', L[cb])[1]
    at = next(n for n, l in enumerate(L) if re.match(rf'\s*{re.escape(cbv)} = ', l))
    blk = next(re.match(r'\s*(%\w+) = OpLabel', L[n])[1] for n in range(at, 0, -1) if 'OpLabel' in L[n])
    ft1, a1 = first_thread('%fs_wg', '%gl_WorkGroupID', (0, 1))
    ft2, a2 = first_thread('%fs_li', '%gl_LocalInvocationID', (0,))
    code = ['%fs_cb = OpBitcast %_ptr_PhysicalStorageBuffer_PhysicalPointerUint4NonWriteCBVArray ' + cbv,
            '%fs_e4p = OpInBoundsAccessChain %_ptr_PhysicalStorageBuffer_v4uint %fs_cb %uint_0 %uint_4',
            '%fs_e4 = OpLoad %v4uint %fs_e4p Aligned 16',
            '%fs_width = OpCompositeExtract %uint %fs_e4 0', '%fs_reset = OpCompositeExtract %uint %fs_e4 2',
            '%fs_wlr = OpCompositeExtract %uint %fs_e4 3',
            '%fs_wl2 = OpShiftLeftLogical %uint %fs_wlr %uint_1', '%fs_big = OpUGreaterThanEqual %bool %fs_wl2 %fs_width',
            '%fs_noreset = OpIEqual %bool %fs_reset %fs_u0',
            '%fs_e1p = OpInBoundsAccessChain %_ptr_PhysicalStorageBuffer_v4uint %fs_cb %uint_0 %uint_1',
            '%fs_e1 = OpLoad %v4uint %fs_e1p Aligned 16', '%fs_jbits = OpCompositeExtract %uint %fs_e1 2',
            '%fs_jmag = OpBitwiseAnd %uint %fs_jbits %fs_absmask', '%fs_jnz = OpINotEqual %bool %fs_jmag %fs_u0',
            '%fs_jsign = OpUGreaterThan %bool %fs_jbits %fs_absmask', '%fs_neg = OpLogicalAnd %bool %fs_jsign %fs_jnz',
            *(['%fs_k1 = OpLogicalAnd %bool %fs_neg ' + '%fs_big'] if UP is None else [      # FS_UP: below half the output width too, but there jitter y < FS_UP runs the model
                '%fs_upj = OpCompositeExtract %uint %fs_e1 3', '%fs_upf = OpBitcast %float %fs_upj', '%fs_upok = OpFOrdGreaterThanEqual %bool %fs_upf %fs_upthr',
                '%fs_upor = OpLogicalOr %bool %fs_big %fs_upok', '%fs_k1 = OpLogicalAnd %bool %fs_neg %fs_upor']),
            '%fs_skipn = OpLogicalAnd %bool %fs_k1 ' + '%fs_noreset',
            '%fs_jyy = OpCompositeExtract %uint %fs_e1 3'] + word_ptr('%fs_t', '%fs_t1') + word_ptr('%fs_u', '%fs_t2') + [
            '%fs_tv = OpLoad %uint %fs_tw', '%fs_uv = OpLoad %uint %fs_uw', '%fs_sx = OpIEqual %bool %fs_tv %fs_jbits',
            '%fs_sy = OpIEqual %bool %fs_uv %fs_jyy', '%fs_same = OpLogicalAnd %bool %fs_sx %fs_sy',
            # test rule: skip a frame whose jitter equals that of the last frame that ran
            '%fs_skip = OpLogicalAnd %bool ' + ('%fs_same %fs_noreset' if TEST == 'same' else '%fs_skipn %fs_skipn')] + \
        ft1 + ft2 + [f'%fs_or = OpBitwiseOr %uint {a1} {a2}', '%fs_first = OpIEqual %bool %fs_or %fs_u0',
                     'OpSelectionMerge %fs_cont None', 'OpBranchConditional %fs_first %fs_do %fs_cont', '%fs_do = OpLabel'] + \
        word_ptr('%fs_a', '%fs_w1') + word_ptr('%fs_b', '%fs_w2') + [
            '%fs_v1 = OpSelect %uint %fs_skip %fs_m1 %fs_u0', '%fs_v2 = OpSelect %uint %fs_skip %fs_m2 %fs_u0',
            'OpStore %fs_aw %fs_v1', 'OpStore %fs_bw %fs_v2', '%fs_jy = OpCompositeExtract %uint %fs_e1 3'] + \
        word_ptr('%fs_y', '%fs_r1') + word_ptr('%fs_z', '%fs_r2') + [
            '%fs_ox = OpLoad %uint %fs_yw', '%fs_oy = OpLoad %uint %fs_zw',
            '%fs_nx = OpSelect %uint %fs_skip %fs_ox %fs_jbits', '%fs_ny = OpSelect %uint %fs_skip %fs_oy %fs_jy',
            'OpStore %fs_yw %fs_nx', 'OpStore %fs_zw %fs_ny', 'OpBranch %fs_cont', '%fs_cont = OpLabel']
    consts += [f'%fs_r1 = OpConstant %uint {W_RELAY}', f'%fs_r2 = OpConstant %uint {W_RELAY + 1}']
    consts += [f'%fs_t1 = OpConstant %uint {W_SAVE}', f'%fs_t2 = OpConstant %uint {W_SAVE + 1}']
    consts.append('%fs_absmask = OpConstant %uint 2147483647')
    if UP is not None:
        consts.append(f'%fs_upthr = OpConstant %float {UP}')
    for need in ('%v4uint', '%_ptr_PhysicalStorageBuffer_v4uint', '%uint_4', '%uint_1', '%uint_0', '%bool'):
        if need not in defs:
            die(f'{need} is not defined')

    def is11(p):
        a = re.match(r'OpAccessChain %\w+ (%\w+) %uint_0 %\w+$', defs.get(p, ''))
        b = a and re.match(r'OpAccessChain %\w+ %\w+ (%\w+)$', defs.get(a[1], ''))
        return bool(b and re.match(r'OpIAdd %uint %\w+ %uint_11$', defs.get(b[1], '')))
    # Motion for the postpass of a skipped frame: where the prepass has a valid motion vector, the
    # thread of every even output pixel stores the displacement to the previous frame (in output
    # pixels, two signed 16-bit halves) into the second region, which is unused while
    # the model is skipped. Row 2 + Y/2 of the region, two blocks of words per row (even and odd
    # cell rows), clear of the edge cells the border clearing zeroes at full size; a zeroed entry
    # reads as "no motion".
    MV = os.environ.get('FS_MOTION', '1') == '1'
    mvx = mvy = None
    if MV:
        for n in range(at, len(L) - 3):
            a = re.match(r'\s*(%\w+) = OpFAdd %float (%\w+) (%\w+)$', L[n]); b = re.match(r'\s*(%\w+) = OpFAdd %float (%\w+) (%\w+)$', L[n + 1])
            c = re.match(r'\s*%\w+ = OpFAdd %float (%\w+) %float_0_5$', L[n + 2]); d = re.match(r'\s*%\w+ = OpFAdd %float (%\w+) %float_0_5$', L[n + 3])
            if a and b and c and d and c[1] == a[1] and d[1] == b[1]:
                def split(m):
                    p, q = m[2], m[3]
                    if defs.get(q, '').startswith('OpConvertUToF') and defs.get(p, '').startswith('OpFMul'): return p, q
                    if defs.get(p, '').startswith('OpConvertUToF') and defs.get(q, '').startswith('OpFMul'): return q, p
                sa, sb = split(a), split(b)
                if sa and sb:
                    mvx, mvy, mv_at = sa[0], sb[0], n + 1
                    px = re.match(r'OpConvertUToF %float (%\w+)$', defs[sa[1]])[1]; py = re.match(r'OpConvertUToF %float (%\w+)$', defs[sb[1]])[1]
                    break
        if mvx is None:
            die('the reprojection displacement was not found in the prepass')
        # the depth the prepass already picks as nearest around the pixel (it takes the motion vector from there):
        # the last comparison of its search before the motion-vector fetch. Stored so that smaller = nearer.
        fetch_at = None
        for k in range(at, mv_at):
            m = re.match(r'\s*%\w+ = OpFMul %float (%\w+) (%\w+)$', L[k])
            if m:
                for p_, q_ in ((m[1], m[2]), (m[2], m[1])):
                    e = re.match(r'OpCompositeExtract %float (%\w+) 0$', defs.get(p_, '')); f = re.match(r'OpCompositeExtract %float (%\w+) 0$', defs.get(q_, ''))
                    ld = e and re.match(r'OpLoad %v4float (%\w+)', defs.get(e[1], ''))
                    ch = ld and re.match(r'OpInBoundsAccessChain %_ptr_PhysicalStorageBuffer_v4float %\w+ %uint_0 %uint_2$', defs.get(ld[1], ''))
                    if ch and f and defs.get(f[1], '').startswith('OpImageFetch'):
                        fetch_at = next(n for n in range(at, mv_at) if re.match(rf'\s*{re.escape(f[1])} = ', L[n]))
            if fetch_at:
                break
        if fetch_at is None:
            die('the motion-vector fetch was not found in the prepass')
        dc = next((m for n in range(fetch_at, at, -1) for m in [re.match(r'\s*(%\w+) = OpFOrd(LessThan|GreaterThan) %bool (%\w+) (%\w+)$', L[n])] if m), None)
        mv_block = next(re.match(r'\s*(%\w+) = OpLabel', L[k])[1] for k in range(mv_at, 0, -1) if 'OpLabel' in L[k])
        glsl = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpExtInstImport "GLSL.std.450"', l)] if m)
        consts += [f'%fs_mbase = OpConstant %uint {(REGION + S) // 4}', f'%fs_mrow = OpConstant %uint {S // 4}', '%fs_mb0 = OpConstant %uint 48', f'%fs_mb1 = OpConstant %uint {(2048 if S == 15392 else 4096)}',
                   '%fs_u1 = OpConstant %uint 1', '%fs_u2 = OpConstant %uint 2', '%fs_u3 = OpConstant %uint 3', '%fs_u16 = OpConstant %uint 16', '%fs_u65535 = OpConstant %uint 65535',
                   '%fs_fone = OpConstant %float 1', '%fs_fm = OpConstant %float -254', '%fs_fp = OpConstant %float 254']
        # FS_ALPHA (default 1 with FS_BRANCH=1, since release dll-2026-10-13; 0 = as before): on a skipped frame every pixel's own displacement goes into the fourth channel of the image the prepass
        # writes per output pixel (AMD writes red there again; the postpass does not read it): dx + 64 * dy + 32 for |dx|, |dy| <= 31
        # (whole numbers a 16-bit float holds exactly), -2048 for anything faster. skipblend.py reads it per 2x2 cell (SB_ALPHA).
        ALPHA = os.environ.get('FS_ALPHA', os.environ.get('FS_BRANCH', '1')) == '1'
        a_code = []
        if ALPHA:
            consts += ['%fs_a31 = OpConstant %float 31', '%fs_a64 = OpConstant %float 64', '%fs_a32 = OpConstant %float 32', '%fs_aesc = OpConstant %float -2048']
            a_code = [f'%fs_arx = OpExtInst %float {glsl} RoundEven {mvx}', f'%fs_ary = OpExtInst %float {glsl} RoundEven {mvy}',
                      f'%fs_aax = OpExtInst %float {glsl} FAbs %fs_arx', f'%fs_aay = OpExtInst %float {glsl} FAbs %fs_ary',
                      '%fs_ao1 = OpFOrdLessThanEqual %bool %fs_aax %fs_a31', '%fs_ao2 = OpFOrdLessThanEqual %bool %fs_aay %fs_a31', '%fs_aok = OpLogicalAnd %bool %fs_ao1 %fs_ao2',
                      '%fs_am = OpFMul %float %fs_ary %fs_a64', '%fs_as = OpFAdd %float %fs_arx %fs_am', '%fs_at = OpFAdd %float %fs_as %fs_a32',
                      '%fs_acode = OpSelect %float %fs_aok %fs_at %fs_aesc']
        mv_code = a_code + [f'%fs_mxy = OpBitwiseOr %uint {px} {py}', '%fs_mev = OpBitwiseAnd %uint %fs_mxy %fs_u3', '%fs_mis = OpIEqual %bool %fs_mev %fs_u0',
                   '%fs_mdo = OpLogicalAnd %bool %fs_mis %fs_skip', 'OpSelectionMerge %fs_mM None', 'OpBranchConditional %fs_mdo %fs_mT %fs_mM', '%fs_mT = OpLabel',
                   f'%fs_mrx = OpExtInst %float {glsl} RoundEven {mvx}', f'%fs_mry = OpExtInst %float {glsl} RoundEven {mvy}',
                   f'%fs_mcx = OpExtInst %float {glsl} NClamp %fs_mrx %fs_fm %fs_fp', f'%fs_mcy = OpExtInst %float {glsl} NClamp %fs_mry %fs_fm %fs_fp',
                   '%fs_mix = OpConvertFToS %uint %fs_mcx', '%fs_miy = OpConvertFToS %uint %fs_mcy',
                   '%fs_mlx = OpBitwiseAnd %uint %fs_mix %fs_u65535', '%fs_mly = OpShiftLeftLogical %uint %fs_miy %fs_u16', '%fs_mval = OpBitwiseOr %uint %fs_mlx %fs_mly',
                   f'%fs_mX = OpShiftRightLogical %uint {px} %fs_u2', f'%fs_mY = OpShiftRightLogical %uint {py} %fs_u2',
                   '%fs_mYr = OpShiftRightLogical %uint %fs_mY %fs_u1', '%fs_mYo = OpBitwiseAnd %uint %fs_mY %fs_u1', '%fs_mYb = OpINotEqual %bool %fs_mYo %fs_u0',
                   '%fs_mblk = OpSelect %uint %fs_mYb %fs_mb1 %fs_mb0', '%fs_mrw = OpIMul %uint %fs_mYr %fs_mrow', '%fs_ma1 = OpIAdd %uint %fs_mbase %fs_mrw',
                   '%fs_ma2 = OpIAdd %uint %fs_ma1 %fs_mblk', '%fs_mX2 = OpShiftLeftLogical %uint %fs_mX %fs_u1', '%fs_midx = OpIAdd %uint %fs_ma2 %fs_mX2',
                   '%fs_mid2 = OpIAdd %uint %fs_midx %fs_u1'] + word_ptr('%fs_mv', '%fs_midx') + word_ptr('%fs_dv', '%fs_mid2') + (
                   [f'%fs_mdn = OpSelect %float {dc[1]} {dc[3]} {dc[4]}'] + (['%fs_mds = OpFNegate %float %fs_mdn'] if dc[2] == 'GreaterThan' else ['%fs_mds = OpFMul %float %fs_mdn %fs_fone']) + [
                   '%fs_mdb = OpBitcast %uint %fs_mds'] if dc else
                   # versions without a depth search (the game hands in motion vectors that need none): no depth, so nothing is ever flagged
                   ['%fs_mdb = OpBitwiseAnd %uint %fs_u0 %fs_u0']) + [
                   'OpStore %fs_mvw %fs_mval', 'OpStore %fs_dvw %fs_mdb']
        if dc and os.environ.get('FS_PLANE', '1') == '1':
            # For the postpass's test "was this pixel's content hidden a frame ago": this block's surface was, a frame ago, at
            # the block's position plus its motion. It leaves its nearness and its own block number in the (up to four)
            # blocks that area touches; of several surfaces the nearest one stays (atomic maximum). The postpass of the last
            # frame that ran the model has cleared the plane.
            L_ = plane_layout(S)
            consts += [f'%fs_psh = OpConstant %uint {23 - L_["m"]}', f'%fs_pbias = OpConstant %uint {(127 - 31) << L_["m"]}', f'%fs_pmax = OpConstant %uint {(1 << L_["kb"]) - 1}',
                       f'%fs_pxb = OpConstant %uint {L_["xb"]}', f'%fs_pidb = OpConstant %uint {L_["idb"]}', f'%fs_pnx = OpConstant %uint {L_["nx"]}', f'%fs_pny = OpConstant %uint {L_["ny"]}',
                       f'%fs_pb0 = OpConstant %uint {L_["pb0"]}', f'%fs_pb1 = OpConstant %uint {L_["pb1"]}']
            mv_code += ['%fs_pw = OpCopyObject %float %fs_mdn' if dc[2] == 'GreaterThan' else '%fs_pw = OpFSub %float %fs_fone %fs_mdn',      # nearness: larger = nearer, fine steps far away
                        '%fs_pbits = OpBitcast %uint %fs_pw', '%fs_pk0 = OpShiftRightLogical %uint %fs_pbits %fs_psh', '%fs_pk1 = OpISub %uint %fs_pk0 %fs_pbias',
                        f'%fs_pk = OpExtInst %uint {glsl} SClamp %fs_pk1 %fs_u1 %fs_pmax',
                        '%fs_pidy = OpShiftLeftLogical %uint %fs_mY %fs_pxb', '%fs_pid = OpBitwiseOr %uint %fs_pidy %fs_mX',
                        '%fs_pkh = OpShiftLeftLogical %uint %fs_pk %fs_pidb', '%fs_pkey = OpBitwiseOr %uint %fs_pkh %fs_pid',
                        f'%fs_pBx = OpIAdd %uint {px} %fs_mix', f'%fs_pBy = OpIAdd %uint {py} %fs_miy', '%fs_pBx3 = OpIAdd %uint %fs_pBx %fs_u3', '%fs_pBy3 = OpIAdd %uint %fs_pBy %fs_u3',
                        '%fs_ptx0 = OpShiftRightArithmetic %uint %fs_pBx %fs_u2', '%fs_ptx1 = OpShiftRightArithmetic %uint %fs_pBx3 %fs_u2',
                        '%fs_pty0 = OpShiftRightArithmetic %uint %fs_pBy %fs_u2', '%fs_pty1 = OpShiftRightArithmetic %uint %fs_pBy3 %fs_u2']
            for i_, (tx, ty) in enumerate((('0', '0'), ('1', '0'), ('0', '1'), ('1', '1'))):
                q = f'%fs_pt{i_}'
                mv_code += [f'{q}ix = OpULessThan %bool %fs_ptx{tx} %fs_pnx', f'{q}iy = OpULessThan %bool %fs_pty{ty} %fs_pny', f'{q}in = OpLogicalAnd %bool {q}ix {q}iy',
                            f'{q}x = OpSelect %uint {q}in %fs_ptx{tx} %fs_u0', f'{q}y = OpSelect %uint {q}in %fs_pty{ty} %fs_u0', f'{q}v = OpSelect %uint {q}in %fs_pkey %fs_u0',
                            f'{q}yr = OpShiftRightLogical %uint {q}y %fs_u1', f'{q}yo = OpBitwiseAnd %uint {q}y %fs_u1', f'{q}yb = OpINotEqual %bool {q}yo %fs_u0',
                            f'{q}blk = OpSelect %uint {q}yb %fs_pb1 %fs_pb0', f'{q}rw = OpIMul %uint {q}yr %fs_mrow', f'{q}a1 = OpIAdd %uint %fs_mbase {q}rw', f'{q}a2 = OpIAdd %uint {q}a1 {q}blk',
                            f'{q}idx = OpIAdd %uint {q}a2 {q}x'] + word_ptr(q, f'{q}idx') + [f'{q}old = OpAtomicUMax %uint {q}w %fs_u1 %fs_u0 {q}v']
        mv_code += ['OpBranch %fs_mM', '%fs_mM = OpLabel']
        mv_code, _hc = holes_spv(mv_code, 'fs', S, 1); consts += _hc      # step past the cleared diagonals (frameskip_layout.py)
    BRANCH = os.environ.get('FS_BRANCH', '1') == '1'
    out, n_st = [], 0
    if BRANCH:
        # FS_BRANCH=1: one branch on "this frame is skipped" around the shader's work, each side with its own copy of the
        # code. The copy for frames that run the model is AMD's code unchanged; the copy for skipped frames has no tensor
        # stores (so the compiler drops the work that only fed them) and holds the motion store.
        # Not the same picture as FS_BRANCH=0 at every render size: there the motion store's code sits in the one copy
        # that also serves the frames that run the model, and its extra uses of the reprojection values make the compiler
        # round a few of them differently (seen at 1506x846 and 3012x1694, not at 2260x1272 or 1280x720). With the
        # branch, a frame that runs the model gets exactly AMD's prepass.
        # The branch goes inside the shader's leading tests ("is this thread inside the picture"), which stay as they are.
        end = next(n for n in range(at, len(L)) if L[n].strip() == 'OpFunctionEnd')
        lab_at = {m[1]: n for n, l in enumerate(L) for m in [re.match(r'\s*(%\w+) = OpLabel', l)] if m}
        split, inner, tail_at, pos = at, blk, end, at
        while True:
            t = next(n for n in range(pos + 1, end) if re.match(r'\s*Op(SelectionMerge|LoopMerge|Branch|BranchConditional|Switch|Return|Kill|Unreachable)\b', L[n]))
            a = re.match(r'\s*OpSelectionMerge (%\w+) None$', L[t]); b = a and re.match(r'\s*OpBranchConditional %\w+ (%\w+) (%\w+)$', L[t + 1])
            if not (b and (b[1] == a[1]) != (b[2] == a[1])):
                break
            tgt = b[2] if b[1] == a[1] else b[1]
            mg = lab_at[a[1]]
            if lab_at.get(tgt) != t + 2 or not all(re.match(r'\s*(%\w+ = OpLabel|OpBranch %\w+|OpReturn)$', L[k]) for k in range(mg, tail_at)):
                break      # not a leading test: its merge block does more than leave
            split, inner, tail_at, pos, merge = t + 2, tgt, mg, t + 2, a[1]
        if MV and mv_at <= split:
            die('the motion code lies before the place of the branch')
        top = split == at

        # FS_ALPHA: the image write of the skipped frame's copy. Its first channel comes through a phi where the thread's pixel can also be
        # outside the picture; the code gets a phi beside it (escape value on that path).
        a_comp = a_phi = None
        if MV and ALPHA:
            cs = [n for n in range(split + 1, tail_at) if re.match(r'\s*%\w+ = OpCompositeConstruct %v4half (%\w+) %\w+ %\w+ \1$', L[n])]
            if len(cs) != 1:
                die(f'FS_ALPHA: {len(cs)} image values of the form (r, g, b, r) found, expected 1')
            a_comp = cs[0]; r0 = re.match(r'\s*%\w+ = OpCompositeConstruct %v4half (%\w+)', L[a_comp])[1]
            src = re.match(r'OpFConvert %half (%\w+)$', defs.get(r0, (0, ''))[1] if isinstance(defs.get(r0), tuple) else defs.get(r0, ''))
            sd = src and (defs[src[1]][1] if isinstance(defs[src[1]], tuple) else defs[src[1]])
            ph = sd and re.match(r'OpPhi %float (%\w+) (%\w+) (%\w+) (%\w+)$', sd)
            if ph:
                a_phi = max(n for n in range(split + 1, a_comp) if 'OpPhi' in L[n]); la, lb = lab_at[ph[2]], lab_at[ph[4]]
                if (la > mv_at) == (lb > mv_at):
                    die('FS_ALPHA: cannot tell which way into the image write passes the motion code')
                a_labels = (ph[2], ph[4]); a_vals = ('%fs_acode' if la > mv_at else '%fs_aesc', '%fs_acode' if lb > mv_at else '%fs_aesc')

        def body(skipped):
            global n_st
            o = []
            for n in range(split + 1, tail_at):
                l = L[n]
                m = re.match(r'(\s*)OpStore (%\w+) (%\w+)$', l)
                if m and is11(m[2]):
                    n_st += 1
                    if skipped:
                        continue
                if 'OpPhi' in l:
                    l = re.sub(rf'{re.escape(inner)}(?=\s|$)', '%fs_S' if skipped else '%fs_R', l)
                    if MV and skipped and n > mv_at:
                        l = re.sub(rf'{re.escape(mv_block)}(?=\s|$)', '%fs_mM', l)
                elif not top:
                    l = re.sub(rf'{re.escape(merge)}(?=\s|$)', '%fs_end', l)
                if skipped and a_comp == n:
                    l = re.sub(r'%\w+$', '%fs_ah', l); o.append(PAD + f"%fs_ah = OpFConvert %half {'%fs_aph' if a_phi else '%fs_acode'}")
                o.append(l)
                if skipped and a_phi == n:      # the labels as the phi above names them (already renamed where the branch was put in)
                    lab = re.match(r'\s*%\w+ = OpPhi %\w+ %\w+ (%\w+) %\w+ (%\w+)$', l)
                    o.append(PAD + f'%fs_aph = OpPhi %float {a_vals[0]} {lab[1]} {a_vals[1]} {lab[2]}')
                if MV and skipped and n == mv_at:
                    o += [PAD + c for c in mv_code]
            return o
        run, skp = body(False), body(True)
        n_st //= 2
        ren = {m[1]: m[1] + '_k' for l in skp for m in [re.match(r'\s*(%\w+) = ', l)] if m}
        skp = [re.sub(r'%\w+', lambda m: ren.get(m[0], m[0]), l) for l in skp]
        for n, l in enumerate(L[:split + 1]):
            if n == main_i:
                out += [PAD + c for c in consts]
            if n > at and re.match(r'\s*OpStore (%\w+) %\w+$', l) and is11(re.match(r'\s*OpStore (%\w+)', l)[1]):
                die('a tensor store before the place of the branch')
            if n > at and 'OpPhi' in l:
                l = re.sub(rf'{re.escape(blk)}(?=\s|$)', '%fs_cont', l)
            out.append(l)
            m = re.match(r'(\s*OpDecorate )(%\w+)( .*)$', l)
            if m and m[2] in ren:
                out.append(m[1] + ren[m[2]] + m[3])
            if n == at:
                out += [PAD + c for c in code]
        out += [PAD + c for c in ['OpSelectionMerge %fs_end None', 'OpBranchConditional %fs_skip %fs_S %fs_R', '%fs_R = OpLabel']] + run + \
            [PAD + '%fs_S = OpLabel'] + skp + [PAD + '%fs_end = OpLabel'] + ([PAD + 'OpUnreachable'] if top else [PAD + f'OpBranch {merge}']) + L[tail_at:]
        if any('OpPhi' in l for l in L[tail_at:end]):
            die('a phi after the place of the branch')
    for n, l in enumerate(L if not BRANCH else []):
        if n == main_i:
            out += [PAD + c for c in consts]
        m = re.match(r'(\s*)OpStore (%\w+) (%\w+)$', l)
        if m and n > at and is11(m[2]):
            n_st += 1
            out += [f'{m[1]}%fs_old{n_st} = OpLoad %uint {m[2]}', f'{m[1]}%fs_new{n_st} = OpSelect %uint %fs_skip %fs_old{n_st} {m[3]}',
                    f'{m[1]}OpStore {m[2]} %fs_new{n_st}']
            continue
        if n > at and 'OpPhi' in l:
            l = re.sub(rf'{re.escape(blk)}(?=\s|$)', '%fs_cont', l)
            if MV and n > mv_at:
                l = re.sub(rf'{re.escape(mv_block)}(?=\s|$)', '%fs_mM', l)
        out.append(l)
        if MV and n == mv_at:
            out += [PAD + c for c in mv_code]
        if n == at:
            out += [PAD + c for c in code]
    if not n_st:
        die('no tensor stores found in the prepass')
    sys.stderr.write(f'frameskip: {n_st} tensor stores made conditional, row size {S}\n')
# FS_PERSIST (prepass; default 1 with FS_ALPHA since release dll-2026-10-14; 0 = as before): on a skipped frame the prepass passes on, in the fourth channel of its
# per-pixel image, the fourth channel of its center history tap: the flag the postpass stored there on the frame before (skipblend.py SB_PERSIST), moved with
# the picture. The first pixel of each 2x2 cell keeps the motion code (the only place the postpass reads it); the others carry the flag.
if mode == 'prepass' and globals().get('ALPHA') and os.environ.get('FS_PERSIST', '1') == '1':
    L = '\n'.join(out).split('\n')
    ai = [n for n, l in enumerate(L) if re.match(r'\s*%fs_ah_k = OpFConvert %half (%\w+)$', l)]
    if len(ai) != 1: die(f'FS_PERSIST: {len(ai)} motion-code values found, expected 1')
    code = re.match(r'\s*%fs_ah_k = OpFConvert %half (%\w+)$', L[ai[0]])[1]
    # the skipped copy's nine history taps (renamed with _k), the fifth = the center (measured with a probe in the test rig)
    taps = [(n, m[1], m[2]) for n, l in enumerate(L) for m in [re.match(r'\s*(%\w+_k) = OpImageSampleExplicitLod %v4float (%\w+) ', l)] if m]
    img = {}
    for n, v, si in taps: img.setdefault(si, []).append((n, v))
    nine = [x for x in img.values() if len(x) == 9]
    if len(nine) != 1: die(f'FS_PERSIST: {len(nine)} groups of nine taps in the skipped copy, expected 1')
    tn, tv = nine[0][4]
    xy = [m for l in L for m in [re.match(r'\s*%fs_mxy_k = OpBitwiseOr %uint (%\w+) (%\w+)$', l)] if m]
    if len(xy) != 1: die('FS_PERSIST: pixel position not found')
    px, py = xy[0][1], xy[0][2]
    out = []; first_lab = False; consts_done = False
    for n, l in enumerate(L):
        if not consts_done and re.match(r'\s*%\w+ = OpFunction ', l):
            out += ['%pp_pf = OpTypePointer Function %float', '%pp_z = OpConstant %float 0', '%pp_u1 = OpConstant %uint 1', '%pp_u0 = OpConstant %uint 0']; consts_done = True
        if n == ai[0]:
            out += ['%pp_xy = OpBitwiseOr %uint ' + px + ' ' + py, '%pp_o = OpBitwiseAnd %uint %pp_xy %pp_u1', '%pp_first = OpIEqual %bool %pp_o %pp_u0',
                    '%pp_fl = OpLoad %float %pp_var', f'%pp_v = OpSelect %float %pp_first {code} %pp_fl']
            out.append(l.replace(f'OpFConvert %half {code}', 'OpFConvert %half %pp_v')); continue
        out.append(l)
        if not first_lab and re.match(r'\s*%\w+ = OpLabel', l):
            out += ['%pp_var = OpVariable %pp_pf Function', 'OpStore %pp_var %pp_z']; first_lab = True
        if n == tn:
            out += [f'%pp_e = OpCompositeExtract %float {tv} 3', 'OpStore %pp_var %pp_e']
    # FS_PERSISTRUN (default 1 with FS_PERSIST since release dll-2026-10-14; 0 = as before): the copy that runs on frames with the network does the same at every
    # pixel (there is no motion code on those frames), so the note reaches every frame (skipblend.py SB_FADE)
    if os.environ.get('FS_PERSISTRUN', '1') == '1':
        L = '\n'.join(out).split('\n')
        cs = [(n, m) for n, l in enumerate(L) for m in [re.match(r'(\s*)(%\w+) = OpCompositeConstruct %v4half (%\w+) (%\w+) (%\w+) \3$', l)] if m and not m[2].endswith('_k')]
        if len(cs) != 1: die(f'FS_PERSISTRUN: {len(cs)} image values of the form (r, g, b, r) in the run copy, expected 1')
        cn, cm = cs[0]
        taps = [(n, m[1], m[2]) for n, l in enumerate(L) for m in [re.match(r'\s*(%\w+) = OpImageSampleExplicitLod %v4float (%\w+) ', l)] if m and not m[1].endswith('_k')]
        img = {}
        for n, v, si in taps: img.setdefault(si, []).append((n, v))
        nine = [x for x in img.values() if len(x) == 9]
        if len(nine) != 1: die(f'FS_PERSISTRUN: {len(nine)} groups of nine taps in the run copy, expected 1')
        tn, tv = nine[0][4]
        out = []
        for n, l in enumerate(L):
            if n == cn:
                out += ['%pr_fl = OpLoad %float %pr_var', '%pr_h = OpFConvert %half %pr_fl', f'{cm[1]}{cm[2]} = OpCompositeConstruct %v4half {cm[3]} {cm[4]} {cm[5]} %pr_h']; continue
            out.append(l)
            if l.strip() == '%pp_var = OpVariable %pp_pf Function': out.append('%pr_var = OpVariable %pp_pf Function')
            if l.strip() == 'OpStore %pp_var %pp_z': out.append('OpStore %pr_var %pp_z')
            if n == tn:
                out += [f'%pr_e = OpCompositeExtract %float {tv} 3', 'OpStore %pr_var %pr_e']
sys.stdout.write('\n'.join(out))
