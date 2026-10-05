#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# wfold_dxil.py <words to drop per output channel> [layer selection] < passN.ll > out.ll
# wfold_dxil.py info < passN.ll        prints the convolution layers found
#
# NOT bit-exact. The DXIL form of wfold.py (see there): in every output channel of a model pass's
# 3x3 convolution it drops the K weight words with the smallest weights and adds each one's weights
# to the nearest tap that is kept for the same four input channels. It makes the same choices as
# wfold.py, so a pass folded here and one folded there give the same output.
import re
import sys

L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*?)(\s*;.*)?$', l)
    if m:
        defs[m[1]] = m[2].strip()
rhs = lambda v: defs.get(v, '')
INT = r'-?\d+'
u32 = lambda s: int(s) & 0xffffffff
s32 = lambda v: v - (1 << 32) if v & 0x80000000 else v


def gep(p):
    """(array, index operand) of a pointer into a local i32 array."""
    m = re.match(r'getelementptr \[\d+ x i32\], \[\d+ x i32\]\* (%[\w.]+), i32 0, i32 (\S+)$', rhs(p))
    return (m[1], m[2]) if m else None


def index_of(v):
    """A weight index  g + i*G : the constant g."""
    m = re.match(r'add i32 (\S+), (\S+)$', rhs(v))
    if not m:
        return None
    for c, x in ((m[1], m[2]), (m[2], m[1])):
        if re.fullmatch(INT, c) and rhs(x).startswith('mul i32'):
            return int(c)
    return None


# Blocks are not in the order they run, so a tap's weights are looked up in the block that jumps
# into its loop, not in the lines before it.
block_stores = {}               # label -> {(array, index): line of the constant store}
cur = None
for n, l in enumerate(L):
    b = re.match(r'; <label>:(\d+)', l)
    if b:
        cur = '%' + b[1]
    m = re.match(rf'\s*store i32 ({INT}), i32\* (%[\w.]+)', l)
    if m and gep(m[2]) and re.fullmatch(INT, gep(m[2])[1]):
        block_stores.setdefault(cur, {})[(gep(m[2])[0], int(gep(m[2])[1]))] = n

loops = []
n = 0
while n < len(L):
    if re.match(r'\s*%[\w.]+ = phi i32', L[n]) and L[n - 1].startswith('; <label>'):
        phis = []
        k = n
        while ' = phi ' in L[k]:
            phis.append(k); k += 1
        end = k
        while not re.match(r'\s*br ', L[end]):
            end += 1
        body = range(k, end)
        cond = re.match(r'\s*br i1 (%[\w.]+),', L[end])
        cmp_ = re.match(rf'icmp eq i32 (%[\w.]+), ({INT})$', rhs(cond[1])) if cond else None
        inc = re.match(r'add nuw nsw i32 (%[\w.]+), 1$', rhs(cmp_[1])) if cmp_ else None
        dots = [re.match(r'\s*(%[\w.]+) = call i32 @dx\.op\.dot4AddPacked\.i32\(i32 163, i32 (\S+), i32 (\S+), i32 (\S+)\)', L[j]) for j in body if 'dot4AddPacked' in L[j]]
        phid = {L[p].split()[0]: p for p in phis}
        wd = {}                                      # g -> phi line
        warr = None
        for d in dots:
            if d[4] in phid:
                p = phid[d[4]]
                inc_ = re.findall(r'\[ (\S+), %[\w.]+ \]', L[p])
                back = [x for x in inc_ if x.startswith('%')]
                ld = re.match(r'load i32, i32\* (%[\w.]+)', rhs(back[0])) if len(back) == 1 else None
                ch = gep(ld[1]) if ld else None
                g = index_of(ch[1]) if ch else None
                if g is not None:
                    warr = ch[0]
                    wd[g] = p
        acc = None
        for j in body:
            s = re.match(r'\s*store i32 %[\w.]+, i32\* (%[\w.]+)', L[j])
            if s and gep(s[1]):
                a, ix = gep(s[1])
                b = re.match(rf'add i32 (%[\w.]+), ({INT})$', rhs(ix))
                acc = (a, int(b[2]) if b else 0)
        if wd and inc and acc and len(wd) == len(dots):
            I, G = int(cmp_[2]), len(wd)
            words = {}                               # (i, g) -> [value, [(line, kind)]]
            ok = True
            for g, p in wd.items():
                c, pre = [x for x in re.findall(r'\[ (\S+), (%[\w.]+) \]', L[p]) if not x[0].startswith('%')][0]
                c = [c]
                last_store = block_stores.get(pre, {})
                words[(0, g)] = [u32(c[0]), [(p, 'phi')]]
                if (warr, g) in last_store:
                    words[(0, g)][1].append((last_store[(warr, g)], 'store'))
                for i in range(1, I):
                    s = last_store.get((warr, i * G + g))
                    if s is None:
                        ok = False
                    else:
                        words[(i, g)] = [u32(re.match(rf'\s*store i32 ({INT})', L[s])[1]), [(s, 'store')]]
            first = len(phis) - len(wd) >= 2         # the first tap starts from the bias (a phi)
            if ok:
                loops.append(dict(line=n, I=I, G=G, acc=acc, words=words, first=first))
        n = end
    n += 1

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
                for ln, kind in where:
                    if kind == 'phi':
                        L[ln] = re.sub(rf'\[ {INT}, ', f'[ {s32(v)}, ', L[ln], count=1)
                    else:
                        L[ln] = re.sub(rf'store i32 {INT},', f'store i32 {s32(v)},', L[ln], count=1)
sys.stderr.write(f'wfold_dxil: {dropped} weight words dropped, {folded} words changed\n')
sys.stdout.write('\n'.join(L))
