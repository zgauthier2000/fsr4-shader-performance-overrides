#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# history_clamp_dxil.py [min] < postpass.ll > out.ll      (default min 0.8)
#
# EXPERIMENT, changes the image: gives the FSR 4.1.1 postpass's history weight a lower bound.
# The postpass blends  out = w * reprojected_history + (1 - w) * filtered_current  with
# w = sigmoid(model output), once per output pixel of the 2x2 block. This makes it max(w, min).
# Run it on AMD's disassembled postpass before postpass_lds_dxil.py.
import re
import struct
import sys

lo = float(sys.argv[1]) if len(sys.argv) > 1 else 0.8
const = '0x%016X' % struct.unpack('<Q', struct.pack('<d', struct.unpack('<f', struct.pack('<f', lo))[0]))[0]
DIV = re.compile(r'^(\s*)(%\d+) = fdiv fast float 1\.000000e\+00, (%\d+)\s*$')
lines = sys.stdin.read().split('\n')
out = []
n = 0
for i, l in enumerate(lines):
    m = DIV.match(l)
    if m and re.match(rf'\s*%\d+ = fsub fast float 1\.000000e\+00, {m[2]}\s*$', lines[i + 1]):
        n += 1
        out.append(f'{m[1]}%hw.{n} = fdiv fast float 1.000000e+00, {m[3]}')
        out.append(f'{m[1]}{m[2]} = call float @dx.op.binary.f32(i32 35, float %hw.{n}, float {const})')
    else:
        out.append(l)
if n != 4:
    sys.exit(f'expected 4 history weights, found {n}')
sys.stdout.write('\n'.join(out))
