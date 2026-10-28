#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# i32conv_dxil.py < pass.ll > out.ll (build_dxil_overrides.sh INTCONV=direct): AMD's FSR 4.1.2 RX 7000 driver model passes convert each rounded output
# straight to i32 (fptosi float -> i32) where 4.1.1 goes fptosi -> i16 then sext -> i32.
# Here each `%b = sext i16 %a to i32` whose %a is `fptosi float %x to i16` is redefined in place as `%b = fptosi float %x to i32` (numbered values stay; %a is left dead).
# Same value whenever the rounded float fits i16 (the outputs are packed to 8 bits next). Exit 2 when nothing matched.
import sys, re
L = sys.stdin.read().split('\n'); defs = {}
for i, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*)', l)
    if m: defs[m[1]] = (i, m[2])
n = 0
for i, l in enumerate(L):
    m = re.match(r'(\s*)(%[\w.]+) = sext i16 (%[\w.]+) to i32(.*)$', l)
    if not m: continue
    d = defs.get(m[3]); f = d and re.match(r'fptosi float (%[\w.]+) to i16', d[1])
    if not f: continue
    L[i] = f'{m[1]}{m[2]} = fptosi float {f[1]} to i32{m[4]}'; n += 1
sys.stdout.write('\n'.join(L)); print(f'i32conv_dxil: {n} conversions made direct', file=sys.stderr)
sys.exit(0 if n else 2)
