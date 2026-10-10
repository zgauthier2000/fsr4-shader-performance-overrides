#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# model_tail.py [up] < passN.spvasm > out.spvasm      (a model pass, or the postpass)
#
# A model pass ends by combining two integers in floating point for each output value:
#     out = int16(RoundEven((float(a) * ca + float(b) * cb) * cs))        ca, cb, cs powers of two
# With A = ca*cs*2^k and B = cb*cs*2^k whole numbers this is RoundEven(n / 2^k) for the integer
# n = A*a + B*b, and every floating-point step is exact as long as |n| < 2^24 (a is an int8, b a sum
# of at most a few dozen int8 dot products, so it is). This computes the same value in integers:
#     r = (n + (h - 1) + ((n >> k) & 1)) >> k,   h = 2^(k-1)        (halves go to the even neighbor)
# With "up" it rounds halves up instead, r = (n + h) >> k, which is shorter and NOT bit-exact.
import math
import re
import sys

up = len(sys.argv) > 1 and sys.argv[1] == 'up'
L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m:
        defs[m[1]] = (n, m[2])
rhs = lambda v: defs.get(v, (0, ''))[1]


def fconst(v):
    m = re.match(r'OpConstant %float (\S+)$', rhs(v))
    return float(m[1]) if m else None


def scaled(v):
    """v = float(x) * c  ->  (x, c)"""
    m = re.match(r'OpFMul %float (%\S+) (%\S+)$', rhs(v))
    if not m:
        return None
    for x, c in ((m[1], m[2]), (m[2], m[1])):
        s = re.match(r'OpConvertSToF %float (%\S+)$', rhs(x))
        if s and fconst(c) is not None:
            return s[1], fconst(c)
    return None


consts = {}
def uc(v):
    name = f'%uint_{v}'
    if name not in defs and name not in consts:
        consts[name] = v
        return name
    return name if name in defs else name


out = list(L)
done = 0
for n, l in enumerate(L):
    m = re.match(r'(\s*)(%\S+) = OpSConvert %uint (%\S+)$', l)
    c = re.match(r'OpConvertFToS %ushort (%\S+)$', rhs(m[3])) if m else None
    wide = False
    if not c:      # the postpass's form: straight to a 32-bit integer
        m = re.match(r'(\s*)(%\S+) = OpConvertFToS %uint (%\S+)$', l); c = m and [None, m[3]]; wide = bool(m)
    r = re.match(r'OpExtInst %float %\S+ RoundEven (%\S+)$', rhs(c[1])) if c else None
    t = re.match(r'OpFMul %float (%\S+) (%\S+)$', rhs(r[1])) if r else None
    if not t:
        continue
    s, cs = (t[1], fconst(t[2])) if fconst(t[2]) is not None else (t[2], fconst(t[1]))
    add = re.match(r'OpFAdd %float (%\S+) (%\S+)$', rhs(s))
    if cs is None or not add:
        continue
    x, y = scaled(add[1]), scaled(add[2])
    if not x or not y:
        continue
    ea, eb = math.log2(x[1] * cs), math.log2(y[1] * cs)
    if ea != int(ea) or eb != int(eb):
        continue
    k = int(max(0, -ea, -eb))
    sa, sb = int(ea) + k, int(eb) + k
    ind, res = m[1], m[2]
    code = []
    def term(v, sh, tag):
        if sh == 0:
            return v
        code.append(f'{ind}{res}_{tag} = OpShiftLeftLogical %uint {v} {uc(sh)}')
        return f'{res}_{tag}'
    ta, tb = term(x[0], sa, 'a'), term(y[0], sb, 'b')
    code.append(f'{ind}{res}_n = OpIAdd %uint {ta} {tb}')
    if k == 0:
        val = f'{res}_n'
    elif up:
        code.append(f'{ind}{res}_h = OpIAdd %uint {res}_n {uc(1 << (k - 1))}')
        code.append(f'{ind}{res}_r = OpShiftRightArithmetic %uint {res}_h {uc(k)}')
        val = f'{res}_r'
    else:
        code.append(f'{ind}{res}_q = OpShiftRightLogical %uint {res}_n {uc(k)}')
        code.append(f'{ind}{res}_e = OpBitwiseAnd %uint {res}_q {uc(1)}')
        code.append(f'{ind}{res}_h = OpIAdd %uint {res}_n {uc((1 << (k - 1)) - 1)}')
        code.append(f'{ind}{res}_g = OpIAdd %uint {res}_h {res}_e')
        code.append(f'{ind}{res}_r = OpShiftRightArithmetic %uint {res}_g {uc(k)}')
        val = f'{res}_r'
    # the original converts to a 16-bit integer and widens again: keep that
    if wide:
        code.append(f'{ind}{res} = OpCopyObject %uint {val}')
    else:
        code.append(f'{ind}{res}_t = OpUConvert %ushort {val}')
        code.append(f'{ind}{res} = OpSConvert %uint {res}_t')
    out[n] = '\n'.join(code)
    done += 1
if consts:
    at = max(n for n, l in enumerate(L) if re.match(r'\s*%\S+ = OpConstant %uint ', l))
    out[at] += ''.join(f'\n{k_} = OpConstant %uint {v}' for k_, v in consts.items())
sys.stderr.write(f'model_tail: {done} output values converted ({"halves up" if up else "exact"})\n')
sys.stdout.write('\n'.join(out))
