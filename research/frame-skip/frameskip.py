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
# For the postpass's correction on skipped frames (skipblend.py) the jitter of the last frame that
# ran the model is carried over: prepass -> pass 11 -> pass 12 -> two words next to the mark.
# FS_TEST=same (prepass): test rule, skip a frame whose jitter equals that of the last frame that
# ran (used with a jitter list that repeats every entry, to show that jitter mismatch is the cause
# of the extra flicker).
#
# On a skipped frame the prepass leaves the model's input tensor as it is (each store writes back
# the word that was there) and its first thread writes a two-word mark into the working buffer; on
# other frames it clears it. Every model pass returns at once when it finds the mark.
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
# region's neighbourhood, copies it next to the mark, where it stays through the skipped frame.
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
            '%fs_k1 = OpLogicalAnd %bool %fs_neg ' + '%fs_big',
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
        consts += [f'%fs_mbase = OpConstant %uint {(REGION + S) // 4}', f'%fs_mrow = OpConstant %uint {S // 4}', '%fs_mb0 = OpConstant %uint 48', '%fs_mb1 = OpConstant %uint 4096',
                   '%fs_u1 = OpConstant %uint 1', '%fs_u2 = OpConstant %uint 2', '%fs_u3 = OpConstant %uint 3', '%fs_u16 = OpConstant %uint 16', '%fs_u65535 = OpConstant %uint 65535',
                   '%fs_fone = OpConstant %float 1', '%fs_fm = OpConstant %float -254', '%fs_fp = OpConstant %float 254']
        mv_code = [f'%fs_mxy = OpBitwiseOr %uint {px} {py}', '%fs_mev = OpBitwiseAnd %uint %fs_mxy %fs_u3', '%fs_mis = OpIEqual %bool %fs_mev %fs_u0',
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
                   'OpStore %fs_mvw %fs_mval', 'OpStore %fs_dvw %fs_mdb', 'OpBranch %fs_mM', '%fs_mM = OpLabel']
    out, n_st = [], 0
    for n, l in enumerate(L):
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
sys.stdout.write('\n'.join(out))
