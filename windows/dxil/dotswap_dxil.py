#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# dotswap_dxil.py < shader.ll > out.ll (build_dxil_overrides.sh DOT4=swap; the RX 6000 picture fix without splitting the dot products): every int8
# dot product whose FIRST operand is a constant and second a value gets its two operands swapped, as in FSR 4.1.2's postpasses (RX 7000 and RX 6000 both:
# value first, constant weights second on all 960 dots; 4.1.1 has 128 the other way, the 16 bias-started chains of the float -> int8 layer):
#     Dot4AddI8Packed(acc, <const>, %v)  ->  Dot4AddI8Packed(acc, %v, <const>)
# Signed 8-bit x signed 8-bit products: the same number either way, so the output stays bit-exact. Test of whether RDNA2's Windows driver ghosts on the
# constant-first form (the dot split fixes it too, but costs time; a Windows RX 6700 timing-kit report: same picture as the split, about 2% faster).
# Value numbering is unchanged (operands only).
import sys, re
D = re.compile(r'(@dx\.op\.dot4AddPacked\.i32\(i32 163, i32 [^,]+, )i32 (-?\d+), i32 (%[\w.]+)\)')
t, n = D.subn(r'\1i32 \3, i32 \2)', sys.stdin.read())
sys.stdout.write(t); print(f'dotswap_dxil: {n} dot products swapped', file=sys.stderr)      # 0 is fine: a shader already in 4.1.2's order passes through
