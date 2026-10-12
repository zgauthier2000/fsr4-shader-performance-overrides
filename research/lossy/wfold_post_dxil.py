#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# wfold_post_dxil.py <words to drop per output channel> [output channels, e.g. 0,1,2,3] < postpass.ll > out.ll
# wfold_post_dxil.py info < postpass.ll
# wfold_post_dxil.py weights < postpass.ll      the 576 weight words, one per line (as wfold_post.py weights)
#
# NOT bit-exact. The DXIL form of wfold_post.py (see there): in the 3x3 layer the postpass starts
# with, every output channel loses the K weight words with the smallest weights of its 36, each
# added to the nearest tap kept for the same four input channels. It makes the same choices as
# wfold_post.py, so a postpass folded here and one folded there give the same output.
# Only constants in existing lines change.
import collections
import re
import sys

L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*?)(\s*;.*)?$', l)
    if m:
        defs[m[1]] = m[2].strip()
DOT = re.compile(r'(\s*%[\w.]+ = call i32 @dx\.op\.dot4AddPacked\.i32\(i32 163, i32 \S+, i32 )(%[\w.]+)(, i32 )(-?\d+)(\).*)$')
taps = collections.OrderedDict()          # the load a tap's four words come from -> its dots, in line order
for n, l in enumerate(L):
    m = DOT.match(l)
    e = m and re.match(r'extractvalue %dx\.types\.ResRet\.i32 (%[\w.]+), (\d)$', defs.get(m[2], ''))
    if e and '@dx.op.rawBufferLoad.i32(' in defs.get(e[1], ''):
        taps.setdefault(e[1], []).append((n, int(e[2]), int(m[4]) & 0xffffffff))
if len(taps) != 9 or any(len(t) != 64 for t in taps.values()):
    sys.exit(f'wfold_post_dxil: expected 9 taps of 64 dot products, found {[len(t) for t in taps.values()]}')
W = {}                                    # (output i, tap t, word g) -> (line, weight value)
for t, ds in enumerate(taps.values()):
    seen = collections.Counter()
    for n, g, w in ds:
        i = seen[g]; seen[g] += 1         # the i-th use of a word belongs to output channel i
        W[(i, t, g)] = (n, w)
assert len(W) == 576


def bytes4(v):
    return [((v >> (8 * k)) & 0xff) - (256 if (v >> (8 * k)) & 0x80 else 0) for k in range(4)]


def word(b):
    return sum((max(-128, min(127, x)) & 0xff) << (8 * k) for k, x in enumerate(b))


if sys.argv[1] == 'weights':
    print('\n'.join(f'{i} {t} {g} {W[(i, t, g)][1]}' for i in range(16) for t in range(9) for g in range(4)))
    sys.exit(0)
if sys.argv[1] == 'info':
    z = sum(1 for _, v in W.values() if v == 0)
    print(f'3x3 layer: 9 taps x 16 output channels x 4 words = 576 words ({z} already zero)')
    for i in range(16):
        norms = sorted(sum(x * x for x in bytes4(W[(i, t, g)][1])) ** 0.5 for t in range(9) for g in range(4))
        print(f'  channel {i:2d}: weight-word norms min {norms[0]:.0f}, median {norms[18]:.0f}, max {norms[-1]:.0f}')
    sys.exit(0)

K = int(sys.argv[1])
only = set(int(x) for x in sys.argv[2].split(',')) if len(sys.argv) > 2 else None      # fold these output channels only
pos = [(t // 3, t % 3) for t in range(9)]
dropped = changed = 0
for i in range(16):
    if only is not None and i not in only:
        continue
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
            m = DOT.match(L[n])
            L[n] = m[1] + m[2] + m[3] + str(v - (1 << 32) if v & 0x80000000 else v) + m[5]
sys.stderr.write(f'wfold_post_dxil: {dropped} weight words dropped, {changed} words changed\n')
sys.stdout.write('\n'.join(L))
