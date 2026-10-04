#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# wprune.py <fraction 0..1> < passN.spvasm > out.spvasm
# Experiment: sets the smallest weight words (4 int8 weights of one output channel for 4 input
# channels at one tap; one dot-product instruction) of a model pass to zero. NOT bit-exact.
import re, sys
frac = float(sys.argv[1])
L = sys.stdin.read().split('\n')
defs = {}
for l in L:
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m: defs[m[1]] = m[2]
def cval(v):
    m = re.match(r'OpConstant %uint (\d+)$', defs.get(v, ''))
    return int(m[1]) if m else None
def chain(p):
    m = re.match(r'OpAccessChain %_ptr_Function_uint (%\S+) (%\S+)$', defs.get(p, ''))
    return (m[1], cval(m[2])) if m else None
# the weight array: the Function array whose elements are loaded in loop continue blocks into phis
words = []        # (line index, kind, value)
cur = {}          # (var, idx) -> line of the latest constant store
i = 0
while i < len(L):
    m = re.match(r'\s*OpStore (%\S+) (%\S+)$', L[i])
    if m and cval(m[2]) is not None and chain(m[1]):
        cur[chain(m[1])] = i
    if 'OpPhi %uint' in L[i]:
        g = []
        while 'OpPhi' in L[i]: g.append(i); i += 1
        if len(g) >= 5:
            wphis = g[:len(g) - 2]
            n = len(wphis)
            # the array feeding these phis: back-edge values are loads of var[idx]
            var = None
            for p in wphis:
                back = L[p].split()[6]
                ld = re.match(r'OpLoad %uint (%\S+)$', defs.get(back, ''))
                if ld and chain(ld[1]): var = chain(ld[1])[0]
            for p in wphis:
                words.append((p, 'phi', cval(L[p].split()[4])))
            for (v, idx), ln in list(cur.items()):
                if v == var and idx is not None and idx >= n:
                    words.append((ln, 'store', cval(L[ln].split()[-1])))
            cur = {k: v for k, v in cur.items() if k[0] != var}
        continue
    i += 1
def l1(w):
    return sum(abs(b - 256 if b > 127 else b) for b in w.to_bytes(4, 'little'))
words = [w for w in words if w[2] is not None]
order = sorted(range(len(words)), key=lambda k: l1(words[k][2]))
kill = set(order[:int(round(frac * len(words)))])
zero = next(k for k, v in defs.items() if v == 'OpConstant %uint 0')
for k in kill:
    ln, kind, val = words[k]
    t = L[ln].split()
    if kind == 'phi': t[4] = zero
    else: t[-1] = zero
    L[ln] = '        ' + ' '.join(t)
print('\n'.join(L))
print(f'wprune: {len(words)} weight words, {len(kill)} zeroed (L1 <= {max([l1(words[k][2]) for k in kill], default=0)})', file=sys.stderr)
