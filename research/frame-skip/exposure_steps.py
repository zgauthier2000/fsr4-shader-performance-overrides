#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# exposure_steps.py < prepass.spvasm > out.spvasm
#
# NOT bit-exact; for the lossy files. The prepass writes the history the last pass mixes with. In the
# versions used with auto exposure (and most others) it first re-encodes that history from the previous
# frame's exposure value to the current one, then stores it in 16-bit floats. On the driver this was
# found on (RADV) the store drops the bits that do not fit, so the smallest downward wobble of the
# exposure value lowers every stored value by a whole step and the picture then climbs back pixel by
# pixel: shimmer in bright flat areas at rest.
# Here the stored value is the one the prepass computes WITHOUT the re-encoding, plus the re-encoding's
# own change rounded to whole 16-bit steps: a wobble below half a step changes nothing, a real change
# of exposure passes. What the store does with the bits that do not fit is left to the driver, as
# before (rounding everything to nearest was tried: steadier still, but the network then follows a
# change of brightness much later). Versions without the re-encoding are left alone: exit status 3.
import re, sys
L = sys.stdin.read().split('\n'); defs = {}
for l in L:
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m: defs[m[1]] = m[2]
glsl = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpExtInstImport "GLSL.std.450"', l)] if m)
raw = [m[1] for l in L for m in [re.match(r'\s*%\w+ = OpFMul %float (%\w+) %float_12_2887039$', l)] if m]
first = next((i for i, l in enumerate(L) if re.search(r'OpFMul %float %\w+ %float_12_2887039$', l)), None)
if first is None: sys.stderr.write('exposure_steps: no exposure re-encoding in this version\n'); sys.exit(3)
if len(raw) != 3: sys.exit(f'exposure_steps: {len(raw)} re-encoded channels instead of 3 (run this before frameskip.py with FS_BRANCH=1)')
enc = []
for l in L[first:]:
    m = re.match(rf'\s*(%\w+) = OpExtInst %float {glsl} NMax (%\w+) %float_0$', l)
    if m and re.match(r'OpFMul %float (%\w+) %float_0_0813754797$', defs.get(m[2], '')) and len(enc) < 3: enc.append(m[1])
assert len(enc) == 3, 'three re-encoded channels expected'
out = []; n = 0
for l in L:
    m = re.match(r'\s*(%\w+) = OpFAdd %float (%\w+) (%\w+)$', l); f = m and re.match(r'OpFMul %float (%\w+) (%\w+)$', defs.get(m[2], ''))
    if f and f[1] in enc:
        k = enc.index(f[1]); n += 1; p = f'%px{k}_'
        out += [f'{p}x = OpFAdd %float {m[2]} {m[3]}', f'{p}a0 = OpFMul %float {raw[k]} {f[2]}', f'{p}x0 = OpFAdd %float {p}a0 {m[3]}', f'{p}d = OpFSub %float {p}x {p}x0',
                f'{p}xm = OpExtInst %float {glsl} NMax {p}x0 %px_tiny', f'{p}l = OpExtInst %float {glsl} Log2 {p}xm', f'{p}lb = OpFAdd %float {p}l %px_eps', f'{p}f = OpExtInst %float {glsl} Floor {p}lb',
                f'{p}e = OpFSub %float %px_10 {p}f', f'{p}iu = OpExtInst %float {glsl} Exp2 {p}e', f'{p}ds = OpFMul %float {p}d {p}iu', f'{p}dsb = OpFAdd %float {p}ds %px_half',
                f'{p}dr = OpExtInst %float {glsl} Floor {p}dsb', f'{p}du = OpFDiv %float {p}dr {p}iu', f'{p}r = OpFAdd %float {p}x0 {p}du',
                f'{p}big = OpFOrdGreaterThan %bool {p}x0 %px_tiny', f'{m[1]} = OpSelect %float {p}big {p}r {p}x']; continue
    out.append(l)
assert n == 3, f'{n} sites instead of 3'
at = max(i for i, l in enumerate(out) if re.match(r'\s*%\S+ = OpConstant %float ', l))
out[at] += '\n%px_tiny = OpConstant %float 0.0001\n%px_10 = OpConstant %float 10\n%px_half = OpConstant %float 0.5\n%px_eps = OpConstant %float 0.0001'
sys.stderr.write('exposure_steps: 3 channels\n'); sys.stdout.write('\n'.join(out))
