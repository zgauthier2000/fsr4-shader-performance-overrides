#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# postpass_taps.py < postpass.spvasm > out.spvasm
#
# The FSR 4.1.1 INT8 postpass reads a 3x3 neighbourhood of the model's output; each of the nine
# reads (4 words, then 64 dot products onto 16 running sums) sits in its own branch that skips it
# when the neighbour is outside the tensor. This removes the branches: the read always happens
# (at word 0 of the tensor when the neighbour is outside, so the address stays valid) and the four
# words are replaced by 0 when it is outside. A dot product with 0 adds nothing, so the sums are
# the same as when the branch was skipped. Idea from VALKKKS's v45 notes (2026-10-05), who measured
# the driver waiting for each read separately because of the branches.
import re
import sys

L = sys.stdin.read().split('\n')
ALLOWED = {'OpIAdd', 'OpIMul', 'OpShiftLeftLogical', 'OpShiftRightLogical', 'OpAccessChain', 'OpLoad',
           'OpCompositeConstruct', 'OpCompositeExtract', 'OpSDot'}
op = lambda l: (re.search(r'\bOp\w+', l) or [''])[0]
rid = lambda l: (re.match(r'\s*(%\w+) = ', l) or [None, None])[1]
label_alias, value_alias, out, done = {}, {}, [], 0
cur = None
i = 0
while i < len(L):
    l = L[i]
    if op(l) == 'OpLabel':
        cur = rid(l)
    m = re.match(r'\s*OpSelectionMerge (%\w+) None', l)
    b = re.match(r'\s*OpBranchConditional (%\w+) (%\w+) (%\w+)', L[i + 1]) if m else None
    if b and rid(L[i + 2]) == b[2] and op(L[i + 2]) == 'OpLabel' and b[2] != m[1]:
        cond, T, F, M = b[1], b[2], b[3], m[1]
        j = i + 3
        while op(L[j]) in ALLOWED:
            j += 1
        body = L[i + 3:j]
        k = j
        ok = re.match(rf'\s*OpBranch {M}\s*$', L[k]) is not None
        k += 1
        fbody = []
        if ok and F != M:                      # a false block that only repeats arithmetic of the true one
            ok = rid(L[k]) == F
            k += 1
            while op(L[k]) in ALLOWED:
                fbody.append(L[k]); k += 1
            ok = ok and re.match(rf'\s*OpBranch {M}\s*$', L[k]) is not None
            k += 1
        ok = ok and rid(L[k]) == M and op(L[k]) == 'OpLabel'
        k += 1
        phis = []
        while ok and op(L[k]) == 'OpPhi':
            phis.append(L[k]); k += 1
        ptrs = {rid(x): x.split()[-1] for x in body if '_ptr_StorageBuffer_uint' in x}
        base = None
        for x in body:
            if rid(x) in ptrs:
                base = base or ptrs[rid(x)]
        rhs = lambda x: x.split(' = ', 1)[1].strip()
        tdef = {rid(x): rhs(x) for x in body}
        fdef = {rid(x): rhs(x) for x in fbody}
        for p in phis:                             # a value made in the false block must equal the true one's
            t = p.split()
            pairs = dict(zip(t[5::2], t[4::2]))
            other = next(v for lab, v in pairs.items() if lab != T)
            if T not in pairs or (other in fdef and fdef[other] != tdef.get(pairs[T])):
                ok = False
        if ok and phis and base and len(ptrs) == 4:
            new = []
            for x in body:
                x = re.sub(rf'{re.escape(base)}\b', base + '_in', x) if rid(x) != base and base in x.split() else x
                if op(x) == 'OpLoad' and x.split()[-1] in ptrs:
                    r = rid(x)
                    new.append(x.replace(f'{r} = ', f'{r}_raw = ', 1))
                    new.append(f'{r} = OpSelect %uint {cond} {r}_raw %uint_0')
                else:
                    new.append(x)
                if rid(x) == base:
                    new.append(f'{base}_in = OpSelect %uint {cond} {base} %uint_0')
            for p in phis:
                t = p.split()
                pairs = dict(zip(t[5::2], t[4::2]))        # label -> value
                value_alias[t[0]] = pairs[T]
            for lab in (T, F, M):
                label_alias[lab] = cur
            out += new
            done += 1
            i = k
            continue
    out.append(l)
    i += 1
if done != 9:
    sys.exit(f'postpass_taps: expected 9 guarded neighbourhood reads, found {done}')


def resolve(d, x):
    while x in d:
        x = d[x]
    return x


res = []
for l in out:
    if op(l) == 'OpPhi':
        t = l.split()
        for n in range(4, len(t), 2):
            t[n] = resolve(value_alias, t[n]); t[n + 1] = resolve(label_alias, t[n + 1])
        l = ' '.join(t)
    else:
        l = re.sub(r'%\w+', lambda m: resolve(value_alias, m[0]), l)
    res.append(l)
sys.stdout.write('\n'.join(res))
