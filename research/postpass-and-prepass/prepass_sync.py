#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Experiment: the FSR 4.1.1 (INT8) prepass with its stores moved to the end of the shader.
#   prepass_sync.py late|sync < prepass.spvasm > out.spvasm
# The prepass writes one pixel of the reprojected image per thread in the middle of the shader,
# and four words of the model's input per quad at the end. Here the values are kept in registers
# and everything is stored at the end ("late"), optionally after a workgroup barrier ("sync"), so
# that a workgroup's 16x16 pixels are written together. Addresses and values are unchanged.
import re, sys
mode = sys.argv[1]
L = sys.stdin.read().split('\n')
defs = {}
for l in L:
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m: defs[m[1]] = m[2]
wi = next(i for i, l in enumerate(L) if 'OpImageWrite' in l)
img, coord, tex = L[wi].split()[1:4]
conv = re.match(r'OpFConvert %v4float (%\S+)$', defs[tex])
halfs = re.match(r'OpCompositeConstruct %v4half (%\S+) (%\S+) (%\S+) (%\S+)$', defs[conv[1]])
fl = [re.match(r'OpFConvert %half (%\S+)$', defs[h])[1] for h in halfs.groups()[:3]]
assert halfs[4] == halfs[1]
cx, cy = re.match(r'OpCompositeConstruct %v2uint (%\S+) (%\S+)$', defs[coord]).groups()
iload = re.match(r'OpLoad (%\S+) (%\S+)$', defs[img]); ichain = defs[iload[2]].split(); iadd = defs[ichain[3]].split()
ild = defs[iadd[2]].split(); ireg = defs[ild[2]].split()
st = [i for i, l in enumerate(L) if re.match(r'\s*OpStore (%\S+) (%\S+)$', l)
      and defs.get(l.split()[1], '').startswith('OpAccessChain %_ptr_StorageBuffer_uint')]
assert len(st) == 4
vals = [L[i].split()[2] for i in st]
c0 = defs[L[st[0]].split()[1]].split()       # OpAccessChain type base %uint_0 index
bbase, bidx = c0[2], c0[4]
bch = defs[bbase].split(); badd = defs[bch[3]].split(); bld = defs[badd[2]].split(); breg = defs[bld[2]].split()
ret = max(i for i, l in enumerate(L) if l.strip() == 'OpReturn')
fi = next(i for i, l in enumerate(L) if re.match(r'\s*%main = OpFunction', l))
li = next(i for i in range(fi, len(L)) if re.match(r'\s*%\S+ = OpLabel', L[i]))
vi = li + 1
while 'OpVariable' in L[vi]: vi += 1
pad = '               '
out = []
for i, l in enumerate(L):
    if i == fi:
        out += [pad + x for x in ['%ps_pf = OpTypePointer Function %float', '%ps_pu = OpTypePointer Function %uint',
                                  '%ps_264 = OpConstant %uint 264', '%ps_2 = OpConstant %uint 2', '%ps_0 = OpConstant %uint 0',
                                  '%ps_1 = OpConstant %uint 1', '%ps_c2 = OpConstant %uint 2', '%ps_c3 = OpConstant %uint 3']]
    if i == vi:
        out += [pad + f'%ps_f{k} = OpVariable %ps_pf Function' for k in range(3)]
        out += [pad + f'%ps_u{k} = OpVariable %ps_pu Function' for k in range(7)]
        out += [pad + 'OpStore %ps_u5 %ps_0', pad + 'OpStore %ps_u6 %ps_0']     # flags: image, tensor
    if i == wi:
        out += [pad + f'OpStore %ps_f{k} {fl[k]}' for k in range(3)] + [pad + 'OpStore %ps_u5 %ps_1']
        continue
    if i in st:
        k = st.index(i)
        out.append(pad + f'OpStore %ps_u{k} {vals[k]}')
        if k == 3:
            out += [pad + f'OpStore %ps_u4 {bidx}', pad + 'OpStore %ps_u6 %ps_1']
        continue
    if i == ret:
        if mode == 'sync':
            out.append(pad + 'OpControlBarrier %ps_2 %ps_2 %ps_264')
        e = ['%ps_fi = OpLoad %uint %ps_u5', '%ps_ci = OpINotEqual %bool %ps_fi %ps_0',
             'OpSelectionMerge %ps_m1 None', 'OpBranchConditional %ps_ci %ps_t1 %ps_m1', '%ps_t1 = OpLabel',
             f'%ps_r1 = OpAccessChain {ireg[1]} {ireg[2]} {ireg[3]}', '%ps_r2 = OpLoad %uint %ps_r1',
             f'%ps_r3 = OpIAdd %uint %ps_r2 {iadd[3]}', f'%ps_r4 = OpAccessChain {ichain[1]} {ichain[2]} %ps_r3',
             f'%ps_im = OpLoad {iload[1]} %ps_r4', f'%ps_co = OpCompositeConstruct %v2uint {cx} {cy}']
        e += [f'%ps_l{k} = OpLoad %float %ps_f{k}' for k in range(3)] + [f'%ps_h{k} = OpFConvert %half %ps_l{k}' for k in range(3)]
        e += ['%ps_hv = OpCompositeConstruct %v4half %ps_h0 %ps_h1 %ps_h2 %ps_h0', '%ps_tx = OpFConvert %v4float %ps_hv',
              'OpImageWrite %ps_im %ps_co %ps_tx', 'OpBranch %ps_m1', '%ps_m1 = OpLabel',
              '%ps_fb = OpLoad %uint %ps_u6', '%ps_cb = OpINotEqual %bool %ps_fb %ps_0',
              'OpSelectionMerge %ps_m2 None', 'OpBranchConditional %ps_cb %ps_t2 %ps_m2', '%ps_t2 = OpLabel',
              f'%ps_b1 = OpAccessChain {breg[1]} {breg[2]} {breg[3]}', '%ps_b2 = OpLoad %uint %ps_b1',
              f'%ps_b3 = OpIAdd %uint %ps_b2 {badd[3]}', f'%ps_b4 = OpAccessChain {bch[1]} {bch[2]} %ps_b3',
              '%ps_ix = OpLoad %uint %ps_u4']
        for k in range(4):
            e += [f'%ps_i{k} = OpIAdd %uint %ps_ix %ps_{["0","1","c2","c3"][k]}', f'%ps_w{k} = OpLoad %uint %ps_u{k}',
                  f'%ps_p{k} = OpAccessChain %_ptr_StorageBuffer_uint %ps_b4 {c0[3]} %ps_i{k}', f'OpStore %ps_p{k} %ps_w{k}']
        e += ['OpBranch %ps_m2', '%ps_m2 = OpLabel']
        out += [(pad + x) if not x.endswith('OpLabel') else x for x in e]
    out.append(l)
print('\n'.join(out))
