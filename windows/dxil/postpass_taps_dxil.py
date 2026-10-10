#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# postpass_taps_dxil.py < postpass.ll > out.ll
#
# The FSR 4.1.1 INT8 postpass reads a 3x3 neighborhood of the model's output; each of the nine
# reads (4 words, then 64 dot products onto 16 running sums) sits in its own branch that skips it
# when the neighbor is outside the tensor. This removes the branches: the read always happens (at
# offset 0 of the buffer when the neighbor is outside, so the address stays valid) and the four
# words are replaced by 0 when it is outside. A dot product with 0 adds nothing, so the sums are
# the same as when the branch was skipped. Run it on AMD's disassembled postpass, before
# postpass_lds_dxil.py.
#
# Idea from VALKKKS's notes of 2026-10-05, who measured the reads being waited on one at a time
# because of the branches (10% of the postpass on an RX 6700M). On an RX 7800 XT the Linux form of
# this change (research/postpass-and-prepass/postpass_taps.py) is 3% slower, so it is only built
# into the RDNA2 test build (build option TAPS=1).
import re
import sys

L = sys.stdin.read().split('\n')
BR = re.compile(r'^(\s*)br i1 (%\w+), label (%\w+), label (%\w+)\s*$')
LABEL = re.compile(r'^; <label>:(\w+)')
ALLOWED = re.compile(r'= (shl|add|or|and|lshr|mul) i32 |@dx\.op\.(tertiary|annotateHandle|rawBufferLoad|dot4AddPacked)\b|= extractvalue %dx\.types\.ResRet\.i32 ')
label_at = {('%' + m[1]): i for i, l in enumerate(L) if (m := LABEL.match(l))}
out = list(L)
done = 0
for i, l in enumerate(L):
    m = BR.match(l)
    if not m or m[3] not in label_at:
        continue
    cond, T = m[2], m[3]
    j = label_at[T] + 1
    body = []
    while j < len(L) and ALLOWED.search(L[j]):
        body.append(j); j += 1
    loads = [k for k in body if 'rawBufferLoad' in L[k]]
    if len(loads) != 1 or not re.match(r'\s*br label %\w+\s*$', L[j]):
        continue
    M = re.match(r'\s*br label (%\w+)', L[j])[1]
    done += 1
    out[i] = f'{m[1]}br label {T}'
    # the read: a valid offset when the neighbor is outside
    k = loads[0]
    lm = re.search(r'(rawBufferLoad\.i32\(i32 139, %dx\.types\.Handle %\w+, i32 )(%\w+)', L[k])
    res = re.match(r'\s*(%\w+) = ', L[k])[1]
    out[k] = f'{m[1]}%tapix.{done} = select i1 {cond}, i32 {lm[2]}, i32 0\n' + L[k].replace(lm[0], f'{lm[1]}%tapix.{done}', 1)
    # its four words: 0 when the neighbor is outside
    words = [kk for kk in body if re.search(rf'= extractvalue %dx\.types\.ResRet\.i32 {re.escape(res)}, [0-3]\s*$', L[kk])]
    if len(words) != 4:
        sys.exit('postpass_taps_dxil: expected four words per read')
    ren = {}
    for n, kk in enumerate(words):
        v = re.match(r'\s*(%\w+) = ', L[kk])[1]
        ren[v] = f'%tap.{done}.{n}'
        out[kk] = L[kk] + f'\n{m[1]}%tap.{done}.{n} = select i1 {cond}, i32 {v}, i32 0'
    for kk in body:
        if 'dot4AddPacked' in L[kk]:
            out[kk] = re.sub(r'i32 (%\w+)(?=[,)])', lambda x: 'i32 ' + ren.get(x[1], x[1]), L[kk])
    # the merge block is no longer reached from the block that held the branch
    if M != m[4]:
        continue                                   # a false block of its own still jumps to the merge: its phis stay valid
    pred = None
    for kk in range(i, -1, -1):
        if (pm := LABEL.match(L[kk])):
            pred = '%' + pm[1]; break
    kk = label_at[M] + 1
    while ' = phi ' in L[kk]:
        t = re.sub(rf'\[ [^\]]*, {re.escape(pred)} \],? ?', '', out[kk]).replace(' ,', ',').rstrip()
        out[kk] = t.rstrip(',')
        kk += 1
    out[label_at[M]] = re.sub(r'preds = .*', f'preds = {T}', out[label_at[M]])
if done != 9:
    sys.exit(f'postpass_taps_dxil: expected 9 guarded neighborhood reads, found {done}')
sys.stdout.write('\n'.join(out))
