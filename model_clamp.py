#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# model_clamp.py < passN.spvasm > out.spvasm
#
# BIT-EXACT: gives the same output as its input, on AMD's pass or after research/lossy/wround.py. A pass turns
# each sum into an int8 like this, four at a time (r(m) is m + h, or AMD's rounding to even):
#     m = max(x, 0)   (in layers with a ReLU)      y = r(m) >> n
#     pack = bytes of clamp(vec4(y0..y3), -128, 127)
# Clamping before the shift gives the same number, and the ReLU becomes the clamp's lower bound:
#     c = clamp(x + h, lo, (128 << n) - 1)         lo = h with a ReLU, (-128 << n) without
#     y = c >> n      (already within -128..127, so the vector clamp goes)
# and when n is 8, y is simply byte 1 of c, so the four bytes are picked out directly.
import re
import sys

L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m:
        defs[m[1]] = (n, m[2])
rhs = lambda v: defs.get(v, (0, ''))[1]


def cval(v):
    m = re.match(r'OpConstant %uint (\d+)$', rhs(v))
    return int(m[1]) if m else None


glsl = next(m[1] for l in L if (m := re.match(r'\s*(%\S+) = OpExtInstImport "GLSL.std.450"', l)))
uchar = next((m[1] for l in L if (m := re.match(r'\s*(%\S+) = OpTypeInt 8 0', l))), None)
v4uchar = next((m[1] for l in L if uchar and (m := re.match(rf'\s*(%\S+) = OpTypeVector {re.escape(uchar)} 4', l))), None)
consts = {}
def uc(v):
    v &= 0xffffffff
    name = f'%uint_{v}'
    if name not in defs:
        name = f'%wc_{v}'
        consts[name] = v
    return name


out = list(L)
done = 0
for n, l in enumerate(L):
    m = re.match(r'(\s*)(%\S+) = OpExtInst (%\S+) %\S+ SClamp (%\S+) (%\S+) (%\S+)$', l)
    cc = re.match(r'OpCompositeConstruct %v4uint (%\S+) (%\S+) (%\S+) (%\S+)$', rhs(m[4])) if m else None
    if not cc:
        continue
    vals, ok, N = [], True, None
    for y in cc.groups():
        sh = re.match(r'OpShiftRightArithmetic %uint (%\S+) (%\S+)$', rhs(y))
        ad = re.match(r'OpIAdd %uint (%\S+) (%\S+)$', rhs(sh[1])) if sh else None
        if not ad or cval(sh[2]) is None or (N is not None and N != cval(sh[2])):
            ok = False; break
        N = cval(sh[2])
        h = 1 << (N - 1)
        if cval(ad[2]) == h:                           # halves up (after wround.py): base + h
            base, even = ad[1], False
        else:                                          # halves to even (AMD's): (base + (h-1)) + ((base >> N) & 1)
            base = None
            for p_, q_ in ((ad[1], ad[2]), (ad[2], ad[1])):
                s1 = re.match(r'OpIAdd %uint (%\S+) (%\S+)$', rhs(p_))
                bit = re.match(r'OpBitwiseAnd %uint (%\S+) %uint_1$', rhs(q_))
                srl = re.match(r'OpShiftRightLogical %uint (%\S+) (%\S+)$', rhs(bit[1])) if bit else None
                if s1 and srl and cval(s1[2]) == h - 1 and srl[1] == s1[1] and cval(srl[2]) == N:
                    base = s1[1]
            even = True
            if base is None:
                ok = False; break
        mx = re.match(rf'OpExtInst %uint {re.escape(glsl)} SMax (%\S+) %uint_0$', rhs(base))
        # the ReLU can be skipped only if nothing else reads its result
        others = sum(len(re.findall(rf'{re.escape(base)}(?!\w)', l2)) for l2 in L) - 1 - (2 if even else 1)
        vals.append((sh[1], base, mx[1] if mx and others == 0 else None, even))
    if not ok:
        continue
    ind, res = m[1], m[2]
    h = 1 << (N - 1)
    code = []
    cs = []
    for k, (S, base, x, even) in enumerate(vals):
        if x is None:                                  # keep the sum as it is; only move the clamp before the shift
            src, lo = S, -128 << N
        elif even:
            code.append(f'{ind}{res}_q{k} = OpShiftRightLogical %uint {x} {uc(N)}')
            code.append(f'{ind}{res}_o{k} = OpBitwiseAnd %uint {res}_q{k} {uc(1)}')
            code.append(f'{ind}{res}_a{k} = OpIAdd %uint {x} {uc(h - 1)}')
            code.append(f'{ind}{res}_s{k} = OpIAdd %uint {res}_a{k} {res}_o{k}')
            src, lo = f'{res}_s{k}', h - 1
        else:
            code.append(f'{ind}{res}_s{k} = OpIAdd %uint {x} {uc(h)}')
            src, lo = f'{res}_s{k}', h
        code.append(f'{ind}{res}_c{k} = OpExtInst %uint {glsl} SClamp {src} {uc(lo)} {uc((128 << N) - 1)}')
        cs.append(f'{res}_c{k}')
    # what uses the clamp: UConvert to four bytes, then a bitcast to one word
    user = next((j for j in range(n + 1, min(n + 6, len(L))) if re.match(rf'\s*%\S+ = OpUConvert \S+ {re.escape(res)}$', L[j])), None)
    if N == 8 and v4uchar and user is not None:
        ures = re.match(r'\s*(%\S+) = ', L[user])[1]
        for k, c in enumerate(cs):
            code.append(f'{ind}{res}_b{k} = OpBitcast {v4uchar} {c}')
            code.append(f'{ind}{res}_e{k} = OpCompositeExtract {uchar} {res}_b{k} 1')
        code.append(f'{ind}{ures} = OpCompositeConstruct {v4uchar} ' + ' '.join(f'{res}_e{k}' for k in range(4)))
        out[n] = '\n'.join(code)
        out[user] = None
    else:
        for k, c in enumerate(cs):
            code.append(f'{ind}{res}_y{k} = OpShiftRightArithmetic %uint {c} {uc(N)}')
        code.append(f'{ind}{res}_v = OpCompositeConstruct %v4uint ' + ' '.join(f'{res}_y{k}' for k in range(4)))
        code.append(f'{ind}{res} = OpBitcast {m[3]} {res}_v')
        out[n] = '\n'.join(code)
    done += 1
out = [l for l in out if l is not None]
if consts:
    at = max(n for n, l in enumerate(out) if re.match(r'\s*%\S+ = OpConstant %uint ', l))
    out[at] += ''.join(f'\n{k} = OpConstant %uint {v}' for k, v in consts.items())
sys.stderr.write(f'model_clamp: {done} groups of four rewritten\n')
sys.stdout.write('\n'.join(out))
