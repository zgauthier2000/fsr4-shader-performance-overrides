#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# exposure_steps_dxil.py < prepass.ll > out.ll
# The DXIL form of exposure_steps.py (see there): the history's exposure re-encoding changes the stored
# value only by whole 16-bit steps. Same arithmetic, so a DLL built with this and the Linux files give
# the same output. Named values only are added. Versions without the re-encoding: exit status 3.
import re, sys
L = sys.stdin.read().split('\n'); defs = {}
for l in L:
    m = re.match(r'\s*(%[\w.]+) = (.*?)\s*$', l)
    if m: defs[m[1]] = m[2]
K12, K08 = '0x402893D100000000', '0x3FB4D50600000000'
raw = [m[1] for l in L for m in [re.match(rf'\s*%[\w.]+ = fmul fast float (%[\w.]+), {K12}\s*$', l)] if m]
first = next((i for i, l in enumerate(L) if re.search(rf'fmul fast float %[\w.]+, {K12}\s*$', l)), None)
if first is None or len(raw) != 3: sys.stderr.write('exposure_steps_dxil: no exposure re-encoding in this version\n'); sys.exit(3)
enc = []
for l in L[first:]:
    m = re.match(r'\s*(%[\w.]+) = call float @dx\.op\.binary\.f32\(i32 35, float (%[\w.]+), float 0\.000000e\+00\)', l)
    if m and re.match(rf'fmul fast float %[\w.]+, {K08}$', defs.get(m[2], '')) and len(enc) < 3: enc.append(m[1])
assert len(enc) == 3, 'three re-encoded channels expected'
out = []; ren = {}; code = []; n = 0
for l in L:
    for a, b in ren.items(): l = re.sub(rf'{re.escape(a)}(?![\w.])', b, l)
    out.append(l)
    m = re.match(r'\s*(%[\w.]+) = fadd fast float (%[\w.]+), (%[\w.]+)\s*$', l); f = m and re.match(r'fmul fast float (%[\w.]+), (%[\w.]+)$', defs.get(m[2], ''))
    if f and f[1] in enc:
        k = enc.index(f[1]); n += 1; p = f'%px{k}.'
        code += [f'  {p}a0 = fmul fast float {raw[k]}, {f[2]}', f'  {p}x0 = fadd fast float {p}a0, {m[3]}', f'  {p}d = fsub fast float {m[1]}, {p}x0',
                 f'  {p}xm = call float @dx.op.binary.f32(i32 35, float {p}x0, float 0x3F1A36E2E0000000)', f'  {p}l = call float @dx.op.unary.f32(i32 23, float {p}xm)',
                 f'  {p}lb = fadd fast float {p}l, 0x3F1A36E2E0000000', f'  {p}f = call float @dx.op.unary.f32(i32 27, float {p}lb)', f'  {p}e = fsub fast float 1.000000e+01, {p}f',
                 f'  {p}iu = call float @dx.op.unary.f32(i32 21, float {p}e)', f'  {p}ds = fmul fast float {p}d, {p}iu', f'  {p}dsb = fadd fast float {p}ds, 5.000000e-01',
                 f'  {p}dr = call float @dx.op.unary.f32(i32 27, float {p}dsb)', f'  {p}du = fdiv fast float {p}dr, {p}iu', f'  {p}r = fadd fast float {p}x0, {p}du',
                 f'  {p}big = fcmp fast ogt float {p}x0, 0x3F1A36E2E0000000', f'  {p}o = select i1 {p}big, float {p}r, float {m[1]}']
        ren[m[1]] = f'{p}o'
        if n == 3: out += code
if n != 3: sys.exit(f'exposure_steps_dxil: {n} sites instead of 3')
sys.stderr.write('exposure_steps_dxil: 3 channels\n'); sys.stdout.write('\n'.join(out))
