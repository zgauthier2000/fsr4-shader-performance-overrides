#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Experiment: FSR 4.1.1 (INT8) model pass 11 (after zconst.py) with its output stores deferred.
#   p11defer.py row|all < pass11.zconst.spvasm > out.spvasm
# The pass computes a 2x2 block of output pixels per thread, 4 words each, and stores every word
# as soon as it is computed, with the next word's arithmetic in between; one store instruction
# therefore writes 4 bytes in every 32. Here the words are kept in registers and stored together:
# "row" after each row of the block (2 pixels, 32 contiguous bytes per thread), "all" after the
# whole block. Addresses and values are exactly those of the original stores.
import re, sys
level = sys.argv[1]
L = sys.stdin.read().split('\n')
defs = {}
for l in L:
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m: defs[m[1]] = m[2]
# the store inside the innermost of three nested loops: the last buffer store of the function
si = max(i for i, l in enumerate(L) if re.match(r'\s*OpStore (%\S+) (%\S+)$', l)
         and defs.get(l.split()[1], '').startswith('OpAccessChain %_ptr_StorageBuffer_uint'))
ptr, val = L[si].split()[1:3]
chain = defs[ptr].split()            # OpAccessChain type base %uint_0 index
base, index = chain[2], chain[4]
bchain = defs[base].split()          # OpAccessChain %_ptr_StorageBuffer_SSBO_0 heap idx
heap = bchain[2]
badd = defs[bchain[3]].split()       # OpIAdd %uint load const
bload = defs[badd[2]].split()        # OpLoad %uint regptr
breg = defs[bload[2]].split()        # OpAccessChain ptrtype %registers member
# loop headers enclosing the store: phis of the three loops, innermost first
heads = [i for i in range(si, 0, -1) if 'OpLoopMerge' in L[i]]
merges = {L[i].split()[1]: i for i in heads}
def phi_before(i):
    j = i
    while 'OpPhi' not in L[j] or 'OpLabel' in L[j]: j -= 1
    return re.match(r'\s*(%\S+) = OpPhi', L[j])[1]
# inner loop: its LoopMerge is after the store (single-block loop)
inner_lm = next(i for i in range(si, len(L)) if 'OpLoopMerge' in L[i])
inner_phi = next(re.match(r'\s*(%\S+) = OpPhi', L[j])[1] for j in range(si, 0, -1) if 'OpPhi %uint' in L[j])
inner_merge = L[inner_lm].split()[1]
mid_i, outer_i = heads[0], heads[1]
mid_phi, outer_phi = phi_before(mid_i), phi_before(outer_i)
mid_merge, outer_merge = L[mid_i].split()[1], L[outer_i].split()[1]
n = [0]
def new():
    n[0] += 1; return f'%df{n[0]}'
pad = '               '
out = []
for i, l in enumerate(L):
    s = l.strip()
    if s.startswith('%main = OpFunction') or (re.match(r'%\S+ = OpFunction ', s) and 'df_decl' not in globals()):
        df_decl = True
    if i == si:
        a, b, c, d, p1, p2 = (new() for _ in range(6))
        out += [f'{pad}{a} = OpShiftLeftLogical %uint {outer_phi} %uint_1', f'{pad}{b} = OpIAdd %uint {a} {mid_phi}',
                f'{pad}{c} = OpShiftLeftLogical %uint {b} %uint_2', f'{pad}{d} = OpIAdd %uint {c} {inner_phi}',
                f'{pad}{p1} = OpAccessChain %_ptr_Function_uint %df_val {d}', f'{pad}OpStore {p1} {val}',
                f'{pad}{p2} = OpAccessChain %_ptr_Function_uint %df_idx {d}', f'{pad}OpStore {p2} {index}']
        continue
    out.append(l)
    target = mid_merge if level == 'row' else outer_merge
    if s == f'{target} = OpLabel':
        r1, r2, r3, bp = (new() for _ in range(4))
        out += [f'{pad}{r1} = OpAccessChain {breg[1]} {breg[2]} {breg[3]}', f'{pad}{r2} = OpLoad %uint {r1}',
                f'{pad}{r3} = OpIAdd %uint {r2} {badd[3]}', f'{pad}{bp} = OpAccessChain {bchain[1]} {heap} {r3}']
        count = 8 if level == 'row' else 16
        if level == 'row':
            first = new()
            out.append(f'{pad}{first} = OpShiftLeftLogical %uint {outer_phi} %uint_3')
        for k in range(count):
            sl, p1, v, p2, ix, bptr = (new() for _ in range(6))
            kc = f'%df_k{k}'
            out.append(f'{pad}{sl} = OpIAdd %uint {first} {kc}' if level == 'row' else f'{pad}{sl} = OpCopyObject %uint {kc}')
            out += [f'{pad}{p1} = OpAccessChain %_ptr_Function_uint %df_val {sl}', f'{pad}{v} = OpLoad %uint {p1}',
                    f'{pad}{p2} = OpAccessChain %_ptr_Function_uint %df_idx {sl}', f'{pad}{ix} = OpLoad %uint {p2}',
                    f'{pad}{bptr} = OpAccessChain %_ptr_StorageBuffer_uint {bp} %uint_0 {ix}', f'{pad}OpStore {bptr} {v}']
# declarations: constants before the function, variables at the top of its first block
fi = next(i for i, l in enumerate(out) if re.match(r'\s*%main = OpFunction', l))
out[fi:fi] = [f'{pad}%df_k{k} = OpConstant %uint {k}' for k in range(16)]
li = next(i for i in range(fi + 16, len(out)) if re.match(r'\s*%\S+ = OpLabel', out[i]))
out[li + 1:li + 1] = [f'{pad}%df_val = OpVariable %_ptr_Function__arr_uint_uint_16 Function',
                      f'{pad}%df_idx = OpVariable %_ptr_Function__arr_uint_uint_16 Function']
print('\n'.join(out))
