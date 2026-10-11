#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Model pass 11 of FSR 4.1.1 (INT8) reads gl_WorkGroupID.z / gl_GlobalInvocationID.z and uses them
# in its loop bounds. They are always 0, because AMD's DLL dispatches every model pass with a z
# count of 1, but the compiler cannot know that and so cannot unroll the loops. This replaces
# those loads with the constant 0. The output is bit-exact.
#
#   spirv-dis <hash>.spv | zconst.py > out.spvasm ; spirv-as --target-env spv1.3
import re, sys
lines = sys.stdin.read().split('\n')
defs = {}
for l in lines:
    m = re.match(r'\s*(%\w+) = (.*)$', l)
    if m:
        defs[m[1]] = m[2]
n = 0
out = []
for l in lines:
    m = re.match(r'(\s*)(%\w+) = OpLoad %uint (%\w+)$', l)
    if m and re.match(r'OpAccessChain %_ptr_Input_uint %gl_(WorkGroupID|GlobalInvocationID) %uint_2$', defs.get(m[3], '')):
        l = f'{m[1]}{m[2]} = OpCopyObject %uint %uint_0'
        n += 1
    out.append(l)
if not n:
    sys.exit('zconst: no z loads found')
print('\n'.join(out))
