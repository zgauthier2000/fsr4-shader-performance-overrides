#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# model_tail_dxil.py < passN.ll > out.ll
#
# The DXIL form of ../../model_tail.py (bit-exact). A model pass ends by combining two integers in
# floating point for each output value:
#     out = int16(Round_ne((float(a) * ca + float(b) * cb) * cs))        ca, cb, cs powers of two
# Every floating-point step there is exact, so the same value is computed in integers: with
# A = ca*cs*2^k and B = cb*cs*2^k whole numbers, n = A*a + B*b and
#     r = (n + (h - 1) + ((n >> k) & 1)) >> k,   h = 2^(k-1)        (halves go to the even neighbour)
# The float instructions are left in place, unused; the driver removes them.
import math
import re
import struct
import sys

L = sys.stdin.read().split('\n')
defs = {}
for n, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*?)(\s*;.*)?$', l)
    if m:
        defs[m[1]] = m[2].strip()
rhs = lambda v: defs.get(v, '')


def fnum(t):
    if t.startswith('0x'):
        return struct.unpack('<d', struct.pack('<Q', int(t, 16)))[0]
    try:
        return float(t)
    except ValueError:
        return None


def scaled(v):
    m = re.match(r'fmul fast float (\S+), (\S+)$', rhs(v))
    if not m:
        return None
    for x, c in ((m[1], m[2]), (m[2], m[1])):
        s = re.match(r'sitofp i32 (%[\w.]+) to float$', rhs(x))
        if s and fnum(c) is not None:
            return s[1], fnum(c)
    return None


out = list(L)
done = 0
for n, l in enumerate(L):
    m = re.match(r'(\s*)(%[\w.]+) = sext i16 (%[\w.]+) to i32', l)
    c = re.match(r'fptosi float (%[\w.]+) to i16$', rhs(m[3])) if m else None
    r = re.match(r'call float @dx\.op\.unary\.f32\(i32 26, float (%[\w.]+)\)$', rhs(c[1])) if c else None
    t = re.match(r'fmul fast float (\S+), (\S+)$', rhs(r[1])) if r else None
    if not t:
        continue
    s, cs = (t[1], fnum(t[2])) if fnum(t[2]) is not None else (t[2], fnum(t[1]))
    add = re.match(r'fadd fast float (%[\w.]+), (%[\w.]+)$', rhs(s))
    if cs is None or not add:
        continue
    x, y = scaled(add[1]), scaled(add[2])
    if not x or not y:
        continue
    ea, eb = math.log2(x[1] * cs), math.log2(y[1] * cs)
    if ea != int(ea) or eb != int(eb):
        continue
    k = int(max(0, -ea, -eb))
    done += 1
    ind, p = m[1], f'%mt.{done}'
    code = []
    def term(v, sh, tag):
        if sh == 0:
            return v
        code.append(f'{ind}{p}.{tag} = shl i32 {v}, {sh}')
        return f'{p}.{tag}'
    ta, tb = term(x[0], int(ea) + k, 'a'), term(y[0], int(eb) + k, 'b')
    code.append(f'{ind}{p}.n = add i32 {ta}, {tb}')
    val = f'{p}.n'
    if k:
        code.append(f'{ind}{p}.q = lshr i32 {p}.n, {k}')
        code.append(f'{ind}{p}.e = and i32 {p}.q, 1')
        code.append(f'{ind}{p}.h = add i32 {p}.n, {(1 << (k - 1)) - 1}')
        code.append(f'{ind}{p}.g = add i32 {p}.h, {p}.e')
        code.append(f'{ind}{p}.r = ashr i32 {p}.g, {k}')
        val = f'{p}.r'
    code.append(f'{ind}{p}.t = trunc i32 {val} to i16')       # the original goes through a 16-bit integer: keep that
    code.append(f'{ind}{m[2]} = sext i16 {p}.t to i32')
    out[n] = '\n'.join(code)
if not done:
    sys.exit('model_tail_dxil: no floating-point output scaling in this shader')
sys.stderr.write(f'model_tail_dxil: {done} output values converted\n')
sys.stdout.write('\n'.join(out))
