#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# wfold.py <words to drop per output channel> [layer selection] < passN.spvasm > out.spvasm
# wfold.py info < passN.spvasm        prints the convolution layers found
#
# NOT bit-exact: removes part of an FSR 4.1.1 model pass's arithmetic.
#
# A model pass computes 3x3 convolutions with int8 weights. In the shader each of the nine taps is
# a loop over the output channels; per channel it adds G dot products (4 input channels each, one
# 32-bit "weight word") onto a running sum. So an output channel of a 3x3 layer has 9 x G weight
# words. This drops the K words with the smallest weights (L2 norm) of every output channel and
# adds each dropped word's weights to the nearest tap that is kept for the same four input
# channels ("folding": neighboring pixels are similar, so the sum changes little, and the
# layer's response to a flat area is unchanged). The compiler then removes the dot products whose
# weights are zero. The folding idea is from VALKKKS's notes of 2026-10-05.
import re
import sys

L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m:
        defs[m[1]] = (n, m[2])


def cval(v):
    m = re.match(r'OpConstant %uint (\d+)$', defs.get(v, (0, ''))[1])
    return int(m[1]) if m else None


def chain(p):
    m = re.match(r'OpAccessChain %_ptr_Function_uint (%\S+) (%\S+)$', defs.get(p, (0, ''))[1])
    return (m[1], m[2]) if m else None


def index_of(v):
    """Value of an array index expression: a constant, or  g + i*G  written as OpIAdd const mul."""
    if cval(v) is not None:
        return ('const', cval(v))
    m = re.match(r'OpIAdd %uint (%\S+) (%\S+)$', defs.get(v, (0, ''))[1])
    if m and cval(m[1]) is not None:
        return ('g', cval(m[1]))
    if m and cval(m[2]) is not None:
        return ('g', cval(m[2]))
    return None


# ---- find the tap loops
loops = []
last_store = {}                 # (var, idx) -> line of the latest constant store
n = 0
while n < len(L):
    m = re.match(r'\s*OpStore (%\S+) (%\S+)$', L[n])
    if m and cval(m[2]) is not None and chain(m[1]) and cval(chain(m[1])[1]) is not None:
        last_store[(chain(m[1])[0], cval(chain(m[1])[1]))] = n
    if 'OpPhi %uint' in L[n] and 'OpLabel' in L[n - 1]:
        phis = []
        k = n
        while 'OpPhi' in L[k]:
            phis.append(k); k += 1
        end = k
        while end < len(L) and 'OpLoopMerge' not in L[end] and 'OpLabel' not in L[end]:
            end += 1
        if end < len(L) and 'OpLoopMerge' in L[end]:
            body = range(k, end)
            dots = [(j, re.match(r'\s*(%\S+) = OpSDot %uint (%\S+) (%\S+)', L[j])) for j in body if 'OpSDot' in L[j]]
            phid = {L[p].split()[0]: p for p in phis}
            cnt0 = re.search(r'OpIEqual %bool (%\S+) (%\S+)', ' '.join(L[j] for j in body))
            cnt = None
            if cnt0:                                  # the counter phi feeds the compared value: cnt + 1
                inc = re.match(r'OpIAdd %uint (%\S+) %uint_1$', defs.get(cnt0[1], (0, ''))[1])
                cnt = (None, inc[1], cnt0[2]) if inc else None
            wd = {}                                  # g -> (phi line, input id)
            warr = None
            for j, d in dots:
                if d[3] in phid:
                    p = phid[d[3]]
                    t = L[p].split()
                    back = t[6]
                    ld = re.match(r'OpLoad %uint (%\S+)$', defs.get(back, (0, ''))[1])
                    ch = chain(ld[1]) if ld else None
                    ix = index_of(ch[1]) if ch else None
                    if ch and ix and ix[0] == 'g':
                        warr = ch[0]
                        wd[ix[1]] = (p, d[2])
            acc = None
            for j in body:
                s = re.match(r'\s*OpStore (%\S+) ', L[j])
                if s and chain(s[1]):
                    acc = chain(s[1])[0]
            if wd and cnt and cval(cnt[2]) and acc and len(wd) == len(dots):
                I, G = cval(cnt[2]), len(wd)
                words = {}                           # (i, g) -> [value, [(line, kind)]]
                ok = True
                for g, (p, inp) in wd.items():
                    words[(0, g)] = [cval(L[p].split()[4]), [(p, 'phi')]]
                    if (warr, g) in last_store:
                        words[(0, g)][1].append((last_store[(warr, g)], 'store'))
                    for i in range(1, I):
                        s = last_store.get((warr, i * G + g))
                        if s is None:
                            ok = False
                        else:
                            words[(i, g)] = [cval(L[s].split()[-1]), [(s, 'store')]]
                # the first tap of a sum starts from the bias (a phi); later taps load the sum from its array
                first = len(phis) - len(wd) >= 2
                base = 0
                for j in body:
                    b = re.match(rf'\s*(%\S+) = OpIAdd %uint {re.escape(cnt[1])} (%\S+)$', L[j]) or re.match(r'\s*(%\S+) = OpIAdd %uint (%\S+) ' + re.escape(cnt[1]) + '$', L[j])
                    if b and cval(b[2]) is not None:
                        base = cval(b[2]); break
                if ok:
                    loops.append(dict(line=n, I=I, G=G, acc=(acc, base), words=words, first=first, inputs=tuple(wd[g][1] for g in sorted(wd))))
            n = end
    n += 1

# ---- group the loops into layers: taps that add onto the same sums
layers = []
for lp in loops:
    if layers and not lp['first'] and layers[-1][-1]['acc'] == lp['acc'] and layers[-1][-1]['I'] == lp['I'] and layers[-1][-1]['G'] == lp['G']:
        layers[-1].append(lp)
    else:
        layers.append([lp])


def bytes4(v):
    return [((v >> (8 * k)) & 0xff) - (256 if (v >> (8 * k)) & 0x80 else 0) for k in range(4)]


def word(b):
    return sum((max(-128, min(127, x)) & 0xff) << (8 * k) for k, x in enumerate(b))


if len(sys.argv) > 1 and sys.argv[1] == 'info':
    total = sum(lp['I'] * lp['G'] for lp in loops)
    print(f'{len(loops)} tap loops, {total} weight words, {len(layers)} layers')
    for n, ly in enumerate(layers):
        z = sum(1 for lp in ly for v, _ in lp['words'].values() if v == 0)
        print(f'  layer {n}: {len(ly)} taps x {ly[0]["I"]} output channels x {ly[0]["G"]} words = {len(ly) * ly[0]["I"] * ly[0]["G"]} words ({z} already zero), sums in {ly[0]["acc"]}')
    sys.exit(0)

K = int(sys.argv[1])
only = set(int(x) for x in sys.argv[2].split(',')) if len(sys.argv) > 2 else None
new_consts = {}
dropped = folded = 0
for n, ly in enumerate(layers):
    if len(ly) != 9 or (only is not None and n not in only):
        continue
    I, G = ly[0]['I'], ly[0]['G']
    pos = [(t // 3, t % 3) for t in range(9)]            # taps in the order they run: rows, then columns
    for i in range(I):
        W = {(t, g): bytes4(ly[t]['words'][(i, g)][0]) for t in range(9) for g in range(G)}
        norm = {k: sum(x * x for x in b) for k, b in W.items()}
        order = sorted(W, key=lambda k: (norm[k], k))
        drop = []
        kept_per_g = {g: 9 for g in range(G)}
        for k in order:
            if len(drop) == K:
                break
            if kept_per_g[k[1]] > 1 and norm[k] > 0:        # always keep one tap per input group
                drop.append(k); kept_per_g[k[1]] -= 1
        ds = set(drop)
        for (t, g) in drop:
            tgt = min((k for k in W if k[1] == g and k not in ds),
                      key=lambda k: ((pos[k[0]][0] - pos[t][0]) ** 2 + (pos[k[0]][1] - pos[t][1]) ** 2, -norm[k], k))
            W[tgt] = [max(-128, min(127, a + b)) for a, b in zip(W[tgt], W[(t, g)])]
            W[(t, g)] = [0, 0, 0, 0]
            dropped += 1
        for (t, g), b in W.items():
            old, where = ly[t]['words'][(i, g)]
            v = word(b)
            if v != old:
                folded += 1
                name = f'%uint_{v}'
                if name not in defs:
                    name = f'%wf_{v}'
                    new_consts[name] = v
                for ln, kind in where:
                    t_ = L[ln].split(' ')
                    if kind == 'phi':
                        idx = [q for q, x in enumerate(t_) if x.startswith('%')][2]   # result, type, first incoming value
                        t_[idx] = name
                    else:
                        t_[-1] = name
                    L[ln] = ' '.join(t_)
if new_consts:
    at = max(n for n, l in enumerate(L) if re.match(r'\s*%\S+ = OpConstant %uint ', l))
    L[at] = L[at] + ''.join(f'\n{name} = OpConstant %uint {v}' for name, v in new_consts.items())
sys.stderr.write(f'wfold: {dropped} weight words dropped, {folded} words changed\n')
sys.stdout.write('\n'.join(L))
