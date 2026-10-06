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
            '%fs_skip = OpLogicalAnd %bool %fs_k1 ' + '%fs_noreset'] + \
        ft1 + ft2 + [f'%fs_or = OpBitwiseOr %uint {a1} {a2}', '%fs_first = OpIEqual %bool %fs_or %fs_u0',
                     'OpSelectionMerge %fs_cont None', 'OpBranchConditional %fs_first %fs_do %fs_cont', '%fs_do = OpLabel'] + \
        word_ptr('%fs_a', '%fs_w1') + word_ptr('%fs_b', '%fs_w2') + [
            '%fs_v1 = OpSelect %uint %fs_skip %fs_m1 %fs_u0', '%fs_v2 = OpSelect %uint %fs_skip %fs_m2 %fs_u0',
            'OpStore %fs_aw %fs_v1', 'OpStore %fs_bw %fs_v2', 'OpBranch %fs_cont', '%fs_cont = OpLabel']
    consts.append('%fs_absmask = OpConstant %uint 2147483647')
    for need in ('%v4uint', '%_ptr_PhysicalStorageBuffer_v4uint', '%uint_4', '%uint_1', '%uint_0', '%bool'):
        if need not in defs:
            die(f'{need} is not defined')

    def is11(p):
        a = re.match(r'OpAccessChain %\w+ (%\w+) %uint_0 %\w+$', defs.get(p, ''))
        b = a and re.match(r'OpAccessChain %\w+ %\w+ (%\w+)$', defs.get(a[1], ''))
        return bool(b and re.match(r'OpIAdd %uint %\w+ %uint_11$', defs.get(b[1], '')))
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
        out.append(l)
        if n == at:
            out += [PAD + c for c in code]
    if not n_st:
        die('no tensor stores found in the prepass')
    sys.stderr.write(f'frameskip: {n_st} tensor stores made conditional, row size {S}\n')
sys.stdout.write('\n'.join(out))
