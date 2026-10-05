#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# prep.py in.spv out.spv : benchmark copy of a prepass or postpass (arrays of sampled images moved
# from set 1 binding 1 to binding 0, because the benchmark has no mutable descriptor heap).
import re, subprocess, sys
s = subprocess.run(['spirv-dis', sys.argv[1]], capture_output=True, text=True, check=True).stdout
sampled = set(m[1] for m in re.finditer(r'(%\S+) = OpTypeImage %\S+ \S+ \d \d \d 1 \S+', s))
arrays = set(m[1] for m in re.finditer(r'(%\S+) = OpType(?:Runtime)?Array (%\S+)', s) if m[2] in sampled) | sampled
ptrs = set(m[1] for m in re.finditer(r'(%\S+) = OpTypePointer \S+ (%\S+)', s) if m[2] in arrays)
vars_ = set(m[1] for m in re.finditer(r'(%\S+) = OpVariable (%\S+) ', s) if m[2] in ptrs)
n = 0
for v in vars_:
    s, k = re.subn(rf'OpDecorate {re.escape(v)} Binding 1\n', f'OpDecorate {v} Binding 0\n', s)
    n += k
open(sys.argv[2] + '.spvasm', 'w').write(s)
subprocess.run(['spirv-as', '--target-env', 'spv1.3', sys.argv[2] + '.spvasm', '-o', sys.argv[2]], check=True)
subprocess.run(['spirv-val', '--target-env', 'vulkan1.3', sys.argv[2]], check=True)
print(f'{sys.argv[1]}: {n} sampled-image arrays moved')
