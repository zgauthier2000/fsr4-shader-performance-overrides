#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# wfold_post.py <words to drop per output channel> < postpass.spvasm > out.spvasm
# wfold_post.py info < postpass.spvasm
#
# NOT bit-exact. The postpass form of wfold.py. The postpass starts with a 3x3 convolution over
# the model's 16-channel output: nine taps, each 4 weight words (four input channels per word) for
# each of 16 output channels, written out as 576 separate dot products with constant weights.
# For every output channel this drops the K words with the smallest weights of its 36 and adds
# each one's weights to the nearest tap kept for the same four input channels. The compiler
# removes the dot products whose weights are zero.
import collections
import re
import sys

L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%\w+) = (.*)$', l)
    if m:
        defs[m[1]] = (n, m[2])


def cval(v):
    m = re.match(r'OpConstant %uint (\d+)$', defs.get(v, (0, ''))[1])
    return int(m[1]) if m else None


dots = []
for v, (n, d) in defs.items():
    m = re.match(r'OpSDot %uint (%\w+) (%\w+) PackedVectorFormat4x8Bit', d)
    if m and cval(m[2]) is not None and cval(m[1]) is None:
        dots.append((n, v, m[1], m[2]))
dots.sort()
uses = collections.Counter(d[2] for d in dots)
taps = collections.OrderedDict()          # source vector of a tap -> its dots, in line order
for n, v, data, w in dots:
    e = re.match(r'OpCompositeExtract %uint (%\w+) (\d)$', defs[data][1])
    if e and uses[data] == 16 and defs[e[1]][1].startswith('OpCompositeConstruct'):
        taps.setdefault(e[1], []).append((n, int(e[2]), w))
if len(taps) != 9 or any(len(t) != 64 for t in taps.values()):
    sys.exit(f'wfold_post: expected 9 taps of 64 dot products, found {[len(t) for t in taps.values()]}')
W = {}                                    # (output i, tap t, word g) -> (line, weight value)
for t, ds in enumerate(taps.values()):
    seen = collections.Counter()
    for n, g, w in ds:
        i = seen[g]; seen[g] += 1         # the i-th use of a word belongs to output channel i
        W[(i, t, g)] = (n, cval(w))
assert len(W) == 576


def bytes4(v):
    return [((v >> (8 * k)) & 0xff) - (256 if (v >> (8 * k)) & 0x80 else 0) for k in range(4)]


def word(b):
    return sum((max(-128, min(127, x)) & 0xff) << (8 * k) for k, x in enumerate(b))


if sys.argv[1] == 'info':
    z = sum(1 for _, v in W.values() if v == 0)
    print(f'3x3 layer: 9 taps x 16 output channels x 4 words = 576 words ({z} already zero); {len(dots)} constant-weight dot products in all')
    for i in range(16):
        norms = sorted(sum(x * x for x in bytes4(W[(i, t, g)][1])) ** 0.5 for t in range(9) for g in range(4))
        print(f'  channel {i:2d}: weight-word norms min {norms[0]:.0f}, median {norms[18]:.0f}, max {norms[-1]:.0f}')
    sys.exit(0)

K = int(sys.argv[1])
pos = [(t // 3, t % 3) for t in range(9)]
new_consts = {}
dropped = changed = 0
for i in range(16):
    B = {(t, g): bytes4(W[(i, t, g)][1]) for t in range(9) for g in range(4)}
    norm = {k: sum(x * x for x in b) for k, b in B.items()}
    drop, kept = [], {g: 9 for g in range(4)}
    for k in sorted(B, key=lambda k: (norm[k], k)):
        if len(drop) == K:
            break
        if kept[k[1]] > 1 and norm[k] > 0:
            drop.append(k); kept[k[1]] -= 1
    ds = set(drop)
    for (t, g) in drop:
        tgt = min((k for k in B if k[1] == g and k not in ds),
                  key=lambda k: ((pos[k[0]][0] - pos[t][0]) ** 2 + (pos[k[0]][1] - pos[t][1]) ** 2, -norm[k], k))
        B[tgt] = [max(-128, min(127, a + b)) for a, b in zip(B[tgt], B[(t, g)])]
        B[(t, g)] = [0, 0, 0, 0]
        dropped += 1
    for (t, g), b in B.items():
        n, old = W[(i, t, g)]
        v = word(b)
        if v != old:
            changed += 1
            name = f'%uint_{v}' if f'%uint_{v}' in defs else f'%wf_{v}'
            if name.startswith('%wf_'):
                new_consts[name] = v
            parts = L[n].split(' ')
            idx = [q for q, x in enumerate(parts) if x.startswith('%')]
            parts[idx[3]] = name          # result, type, data, weight
            L[n] = ' '.join(parts)
if new_consts:
    at = max(n for n, l in enumerate(L) if re.match(r'\s*%\S+ = OpConstant %uint ', l))
    L[at] += ''.join(f'\n{name} = OpConstant %uint {v}' for name, v in new_consts.items())
sys.stderr.write(f'wfold_post: {dropped} weight words dropped, {changed} words changed\n')
sys.stdout.write('\n'.join(L))
