#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Model pass 11 of FSR 4.1.1 (INT8) in DXIL form (LLVM IR text from "dxc -dumpbin"), after
# zconst_dxil.py: stores each row of its output together, as pass11_stores.py does for the SPIR-V.
#
#   dxc -dumpbin <pass11.dxil> | zconst_dxil.py | pass11_stores_dxil.py > out.ll     (then dxilasm)
#
# The pass computes a 2x2 block of output pixels per thread, four words each, and stores every
# word as soon as it is computed. Here the eight words of a row and their addresses are kept in
# two local arrays, and stored together when the row is complete. Addresses and values are those
# of the original stores, so the output is bit-exact.
import re
import sys

L = sys.stdin.read().split('\n')


def die(msg):
    sys.exit('pass11_stores_dxil: ' + msg)


STORE = re.compile(r'\s*call void @dx\.op\.rawBufferStore\.i32\(i32 140, %dx\.types\.Handle (%[\w.]+), i32 (%[\w.]+), '
                   r'i32 undef, i32 (%[\w.]+), i32 undef, i32 undef, i32 undef, i8 1, i32 4\)')
stores = [i for i, l in enumerate(L) if STORE.match(l)]
if not stores:
    die('no buffer store found')
si = stores[-1]
handle, index, value = STORE.match(L[si]).groups()
hdef = next((l for l in L if l.startswith(f'  {handle} = call %dx.types.Handle @dx.op.annotateHandle(')), None)
if not hdef:
    die('unexpected handle of the store')
hcall = hdef.split(' = ', 1)[1].split(')  ;')[0].rstrip() 
hcall = hcall if hcall.endswith(')') else hcall + ')'
# loop counters: the phi of the store's block, and the two loop phis above it
PHI = re.compile(r'\s*(%[\w.]+) = phi i32 \[ (%[\w.]+), %[\w.]+ \], \[ 0, %[\w.]+ \]')
phis = [(i, PHI.match(L[i])[1], PHI.match(L[i])[2]) for i in range(si, 0, -1) if PHI.match(L[i])][:3]
if len(phis) != 3:
    die('expected three nested loops around the store')
(_, inner, _), (_, mid, _), (_, outer, outer_next) = phis
# the outer loop's latch: the block that defines the outer counter's next value
ni = next((i for i, l in enumerate(L) if l.startswith(f'  {outer_next} = add ')), None)
if ni is None:
    die('outer loop increment not found')
latch = next(i for i in range(ni, 0, -1) if L[i].startswith('; <label>:'))
if any(PHI.match(L[i]) or ' phi ' in L[i] for i in range(latch + 1, ni)):
    die('unexpected phi in the outer latch')
alloca = max(i for i, l in enumerate(L) if re.match(r'\s*%[\w.]+ = alloca ', l))
A = '[16 x i32], [16 x i32]*'
out = []
for i, l in enumerate(L):
    if i == si:
        out += [f'  %df.s1 = shl i32 {outer}, 1', f'  %df.s2 = add i32 %df.s1, {mid}', '  %df.s3 = shl i32 %df.s2, 2',
                f'  %df.s4 = add i32 %df.s3, {inner}',
                f'  %df.pv = getelementptr inbounds {A} %df.val, i32 0, i32 %df.s4', f'  store i32 {value}, i32* %df.pv, align 4',
                f'  %df.pi = getelementptr inbounds {A} %df.idx, i32 0, i32 %df.s4', f'  store i32 {index}, i32* %df.pi, align 4']
        continue
    out.append(l)
    if i == alloca:
        out += ['  %df.val = alloca [16 x i32], align 4', '  %df.idx = alloca [16 x i32], align 4']
    if i == latch:
        out += [f'  %df.h = {hcall}', f'  %df.f = shl i32 {outer}, 3']
        for k in range(8):
            out += [f'  %df.k{k} = add i32 %df.f, {k}',
                    f'  %df.gv{k} = getelementptr inbounds {A} %df.val, i32 0, i32 %df.k{k}', f'  %df.v{k} = load i32, i32* %df.gv{k}, align 4',
                    f'  %df.gi{k} = getelementptr inbounds {A} %df.idx, i32 0, i32 %df.k{k}', f'  %df.i{k} = load i32, i32* %df.gi{k}, align 4',
                    f'  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %df.h, i32 %df.i{k}, i32 undef, '
                    f'i32 %df.v{k}, i32 undef, i32 undef, i32 undef, i8 1, i32 4)']
print('\n'.join(out))
