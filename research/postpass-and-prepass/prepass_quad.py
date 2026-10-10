#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Rewrites the FSR 4.1.1 (INT8) prepass as dumped by vkd3d-proton so that the four lanes of each
# quad share the quantization of the model's input tensor.
#
#   spirv-dis <hash>.spv | prepass_quad.py > out.spvasm ; spirv-as --target-env spv1.3
#
# Each quad of lanes (a 2x2 block of pixels) reduces 16 channel sums with quad swaps; then only
# lane 0 of the quad turns them into four words of four int8 values each (add the bias, scale,
# round, clamp, pack) and stores the words, while the other three lanes of the quad idle. The
# reduction leaves the same sums in all four lanes (each lane adds the same two values, and float
# addition is commutative), so here every lane computes one of the four words, with the same
# operations, and stores it. The quantization runs once per lane instead of four times in a
# quarter of the lanes, and the quad writes its 16 bytes with one store. The output is bit-exact.
import re
import sys

lines = sys.stdin.read().split('\n')


def die(msg):
    sys.exit(f'prepass_quad: {msg}')


defs, def_line = {}, {}
for i, l in enumerate(lines):
    m = re.match(r'\s*(%\w+) = (.*)$', l)
    if m:
        defs[m[1]] = m[2]
        def_line[m[1]] = i

# The four tensor stores: consecutive uint stores at base, base+1, base+2, base+3.
stores = [i for i, l in enumerate(lines) if re.match(r'\s*OpStore (%\w+) (%\w+)$', l)
          and 'StorageBuffer_uint' in defs.get(re.match(r'\s*OpStore (%\w+)', l)[1], '')]
if len(stores) != 4:
    die(f'expected 4 tensor stores, found {len(stores)}')
ptrs = [re.match(r'\s*OpStore (%\w+) (%\w+)$', lines[i]).groups() for i in stores]
chain0 = re.match(r'OpAccessChain (%\w+) (%\w+) (%\w+) (%\w+)$', defs[ptrs[0][0]])
if not chain0:
    die('unexpected address of the first store')
ptr_t, buf, zero, base = chain0.groups()
for k in range(1, 4):
    c = re.match(r'OpAccessChain (%\w+) (%\w+) (%\w+) (%\w+)$', defs[ptrs[k][0]])
    off = c and re.match(rf'OpIAdd %uint {re.escape(base)} %uint_{k}$', defs.get(c[4], ''))
    if not off or c[2] != buf:
        die(f'store {k} is not at base + {k}')

# The guard: the stores sit in a block entered only when (lane & 3) == 0.
first = stores[0]
label = next(i for i in range(first, 0, -1) if re.match(r'\s*%\w+ = OpLabel$', lines[i]))
br = re.match(r'\s*OpBranchConditional (%\w+) (%\w+) (%\w+)$', lines[label - 1])
sm = re.match(r'\s*OpSelectionMerge (%\w+) None$', lines[label - 2])
if not br or not sm or br[2] != re.match(r'\s*(%\w+)', lines[label])[1]:
    die('the stores are not in a guarded block')
eq = re.match(r'OpIEqual %bool (%\w+) %uint_0$', defs.get(br[1], ''))
quad = eq and re.match(r'OpBitwiseAnd %uint (%\w+) %uint_3$', defs.get(eq[1], ''))
if not quad:
    die('the guard is not (lane & 3) == 0')
q = eq[1]

# Walk the four words' expressions in parallel. Where they differ, the value becomes a select by
# the lane's position in the quad; where they agree, it is shared.
out_code, memo, n = [], {}, [0]


def new():
    n[0] += 1
    return f'%qd{n[0]}'


def tokens(v):
    return defs[v].split() if v in defs else None


def walk(vs):
    if all(v == vs[0] for v in vs):
        return vs[0]
    if vs in memo:
        return memo[vs]
    ts = [tokens(v) for v in vs]
    same_shape = all(t and len(t) == len(ts[0]) and t[0] == ts[0][0] and t[1] == ts[0][1] for t in ts)
    if same_shape and ts[0][0] in ('OpBitcast', 'OpUConvert', 'OpExtInst', 'OpCompositeConstruct',
                                   'OpConvertFToS', 'OpFMul'):
        args = [walk(tuple(t[j] for t in ts)) if ts[0][j].startswith('%') else ts[0][j]
                for j in range(2, len(ts[0]))]
        if ts[0][0] == 'OpExtInst' and any(t[3] != ts[0][3] for t in ts):
            die('different instructions in the words')
        r = new()
        out_code.append(f'{r} = {ts[0][0]} {ts[0][1]} ' + ' '.join(args))
        memo[vs] = r
        return r
    if same_shape and ts[0][0] == 'OpFAdd':
        # the leaves: select each operand by quad position, then the same add
        args = []
        for j in (2, 3):
            ops = [t[j] for t in ts]
            v = ops[0]
            for k in (1, 2, 3):
                s = new()
                out_code.append(f'{s} = OpSelect {ts[0][1]} %qd_is{k} {ops[k]} {v}')
                v = s
            args.append(v)
        r = new()
        out_code.append(f'{r} = OpFAdd {ts[0][1]} {args[0]} {args[1]}')
        memo[vs] = r
        return r
    die(f'unexpected difference between the words: {[defs.get(v) for v in vs]}')


word = walk(tuple(v for _, v in ptrs))
pre = [f'%qd_is{k} = OpIEqual %bool {q} %uint_{k}' for k in (1, 2, 3)]
idx, ptr = new(), new()
store = [f'{idx} = OpIAdd %uint {base} {q}', f'{ptr} = OpAccessChain {ptr_t} {buf} {zero} {idx}',
         f'OpStore {ptr} {word}']

pad = '               '
res = []
for i, l in enumerate(lines):
    if i == label - 2:          # OpSelectionMerge of the guard: gone
        continue
    if i == label - 1:          # every lane enters the block
        res.append(f'{pad}OpBranch {br[2]}')
        continue
    if i in stores:
        if i == stores[0]:
            res += [pad + c for c in pre + out_code + store]
        continue
    res.append(l)
needed = ['%uint_1', '%uint_2', '%uint_3']
for c in needed:
    if c not in defs:
        die(f'{c} is not defined')
print('\n'.join(res))
