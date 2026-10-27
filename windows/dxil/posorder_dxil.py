#!/usr/bin/env python3
# posorder_dxil.py < shader.ll > out.ll (2026-10-27, user: "before release, i also want to figure out how we can make our rdna2 versions show the same picture as
# amds driver 4.1.2"): the postpass's low-res sample position in the order of AMD's 4.1.2 RX 6000 driver postpass (n2diag postn2.ll) instead of 4.1.1's:
#     4.1.1:   x = (off - 0.5) + scale * (u + 0.5)
#     driver:  x = ((scale * 0.5 - 0.5) + off) + scale * u
# (u = uitofp of the pixel coordinate, scale / off = cbuffer components). Same value in exact arithmetic, other rounding: a picture change by design, toward
# the driver's picture. The numbered definition of x is redefined in place from named values; the old numbered steps stay (dead), so numbering is unchanged.
import sys, re
L = sys.stdin.read().split('\n'); defs = {}
for i, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*)', l)
    if m: defs[m.group(1)] = (i, m.group(2))
F = r'((?:fast |reassoc |nnan |ninf |nsz |arcp |contract |afn )*)'
n = 0; edits = {}
for v, (i, d) in list(defs.items()):
    m = re.match(r'fadd ' + F + r'float (%[\w.]+), (%[\w.]+)$', d)                   # x = c + b
    if not m: continue
    fl, c, b = m.groups()
    mc = re.match(r'fadd ' + F + r'float (%[\w.]+), -5\.000000e-01$', defs.get(c, (0, ''))[1])            # c = off - 0.5
    mb = re.match(r'fmul ' + F + r'float (%[\w.]+), (%[\w.]+)$', defs.get(b, (0, ''))[1])                  # b = scale * a
    if not (mc and mb): continue
    off = mc.group(2); scale, a = mb.group(2), mb.group(3)
    ma = re.match(r'fadd ' + F + r'float (%[\w.]+), 5\.000000e-01$', defs.get(a, (0, ''))[1])              # a = u + 0.5
    if not ma or not re.match(r'uitofp i32 ', defs.get(ma.group(2), (0, ''))[1]): continue
    u = ma.group(2)
    if not all(re.match(r'extractvalue %dx\.types\.CBufRet\.f32 ', defs.get(x, (0, ''))[1]) for x in (scale, off)): continue
    k = f'%po{n}_'; ind = re.match(r'\s*', L[i]).group(0)
    edits[i] = [f'{ind}{k}h = fmul {fl}float {scale}, 5.000000e-01', f'{ind}{k}h2 = fadd {fl}float {k}h, -5.000000e-01',
                f'{ind}{k}h3 = fadd {fl}float {k}h2, {off}', f'{ind}{k}m = fmul {fl}float {scale}, {u}', f'{ind}{v} = fadd {fl}float {k}h3, {k}m']
    n += 1
out = []
for i, l in enumerate(L): out.extend(edits.get(i, [l]))
sys.stdout.write('\n'.join(out)); print(f'posorder_dxil: {n} sample positions reordered', file=sys.stderr)
sys.exit(0 if n else 2)                 # a postpass without the pattern: not the expected structure
