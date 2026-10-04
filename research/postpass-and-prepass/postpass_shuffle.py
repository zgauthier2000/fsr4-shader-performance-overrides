#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Experimental: the FSR 4.1.1 (INT8) postpass as dumped by vkd3d-proton, with its image stores made
# contiguous by a lane swap instead of workgroup memory.
#
#   spirv-dis <hash>.spv | postpass_shuffle.py > out.spvasm ; spirv-as --target-env spv1.3
#
# Each invocation computes a 2x2 block of pixels and writes each one separately, so one store
# instruction writes every other pixel of a row. Invocation pairs whose blocks are 8 apart in x
# (lanes 16 apart) swap one pixel once both pixels of a row are computed, so that the pair's
# two store instructions each write 16 contiguous pixels. No workgroup memory, no barriers, and
# each row is written as soon as it is computed, so at most one pixel waits in registers.
import re
import sys

lines = sys.stdin.read().split('\n')


def die(msg):
    sys.exit(f'postpass_shuffle: {msg}')


defs = {}
for line in lines:
    m = re.match(r'\s*(%\w+) = (.*)$', line)
    if m:
        defs[m[1]] = m[2]

# The thread bounds (W/2) of the pass's own early-out.
main_i = next(i for i, l in enumerate(lines) if re.match(r'\s*%main = OpFunction ', l))
sel_i = w2 = None
for i in range(main_i, len(lines)):
    m = re.match(r'\s*OpSelectionMerge (%\w+) None', lines[i])
    b = m and re.match(r'\s*OpBranchConditional (%\w+) (%\w+) (%\w+)', lines[i + 1])
    lor = b and re.match(r'OpLogicalOr %bool (%\w+) (%\w+)$', defs.get(b[1], ''))
    if lor and b[2] == m[1]:
        gx = re.match(r'OpUGreaterThanEqual %bool (%\w+) (%\w+)$', defs.get(lor[1], ''))
        if gx:
            sel_i, w2 = i, gx[2]
            break
if sel_i is None:
    die('no bounds check found')

# Pair the stores: per image, (x, y) and (x | 1, y).
stores = []
for i in range(sel_i, len(lines)):
    m = re.match(r'(\s*)OpImageWrite (%\w+) (%\w+) (%\w+)$', lines[i])
    if m:
        c = re.match(r'OpCompositeConstruct %v2uint (%\w+) (%\w+)$', defs[m[3]])
        if not c:
            die('unexpected store coordinate')
        stores.append((i, m[2], c[1], c[2], m[4]))


def image_key(img):
    """The (heap, offset) an image handle was loaded from: the same image in every block."""
    load = re.match(r'OpLoad \S+ (%\w+)$', defs[img])
    chain = re.match(r'OpAccessChain \S+ (%\w+) (%\w+)$', defs[load[1]])
    add = re.match(r'OpIAdd %uint (%\w+) (%\w+)$', defs[chain[2]])
    return (chain[1], add[2])


stores_by_line = {st[0]: st for st in stores}
first = {}   # (image, y) -> line of the even store
pairs = {}   # line of the odd store -> line of the even store
for i, img, x, y, tex in stores:
    key = (image_key(img), y)
    odd = re.match(r'OpBitwiseOr %uint (%\w+) %uint_1$', defs.get(x, ''))
    if odd and key in first and stores_by_line[first[key]][2] == odd[1]:
        pairs[i] = first.pop(key)
    else:
        first[key] = i
if len(pairs) != 6 or first:
    die(f'expected 6 pairs of stores, found {len(pairs)} (unpaired: {len(first)})')
even_lines = set(pairs.values())

n = [0]


def new(p):
    n[0] += 1
    return f'%sh_{p}{n[0]}'


decl = ['%sh_u16 = OpConstant %uint 16', '%sh_u17 = OpConstant %uint 17', '%sh_u15 = OpConstant %uint 15',
        '%sh_unot1 = OpConstant %uint 4294967294', '%sh_scope = OpConstant %uint 3',
        '%sh_pv4 = OpTypePointer Function %v4float']
if '%v4bool' not in defs:
    decl.append('%v4bool = OpTypeVector %bool 4')
fvars = []
out = []
pad = '               '
block = None
phi_fix = {}
for i, l in enumerate(lines):
    s = l.strip()
    m = re.match(r'(%\w+) = OpLabel$', s)
    if m:
        block = m[1]
    if s.startswith('%main = OpFunction'):
        out += [pad + d for d in decl]
    if i in even_lines:
        _, img, x, y, tex = stores_by_line[i]
        var = f'%sh_v{i}'
        fvars.append(var)
        out.append(f'{pad}OpStore {var} {tex}')
        continue
    if i in pairs:
        _, img, x1, y, tex1 = stores_by_line[i]
        var = f'%sh_v{pairs[i]}'
        v0, x0, recv, bit, hi, px, ph, pact = (new(p) for p in ('v0', 'x0', 'recv', 'bit', 'hi', 'px', 'ph', 'pact'))
        code = [f'{v0} = OpLoad %v4float {var}', f'{x0} = OpBitwiseAnd %uint {x1} %sh_unot1',
                f'{recv} = OpGroupNonUniformShuffleXor %v4float %sh_scope {tex1} %sh_u16',
                f'{bit} = OpBitwiseAnd %uint {x0} %sh_u16', f'{hi} = OpINotEqual %bool {bit} %uint_0',
                f'{px} = OpBitwiseXor %uint {x0} %sh_u16', f'{ph} = OpShiftRightLogical %uint {px} %uint_1',
                f'{pact} = OpULessThan %bool {ph} {w2}']
        pxo, hi4 = new('pxo'), new('hi4')
        code += [f'{pxo} = OpBitwiseOr %uint {px} %uint_1',          # the partner's odd pixel
                 f'{hi4} = OpCompositeConstruct %v4bool {hi} {hi} {hi} {hi}']
        # A: low lanes their even pixel, high lanes the partner's odd pixel (if the partner ran)
        # B: high lanes their even pixel, low lanes the partner's odd pixel (if the partner ran)
        # C: lanes whose partner did not run write their own odd pixel
        writes = []
        for name, take_recv_if_hi in (('a', True), ('b', False)):
            val, xx, c, nhi, coord = new('val'), new('x'), new('c'), new('nhi'), new('co')
            if take_recv_if_hi:
                code += [f'{val} = OpSelect %v4float {hi4} {recv} {v0}', f'{xx} = OpSelect %uint {hi} {pxo} {x0}',
                         f'{nhi} = OpLogicalNot %bool {hi}', f'{c} = OpLogicalOr %bool {nhi} {pact}']
            else:
                code += [f'{val} = OpSelect %v4float {hi4} {v0} {recv}', f'{xx} = OpSelect %uint {hi} {x0} {pxo}',
                         f'{c} = OpLogicalOr %bool {hi} {pact}']
            code.append(f'{coord} = OpCompositeConstruct %v2uint {xx} {y}')
            writes.append((c, coord, val))
        npact, coord1 = new('npact'), new('co')
        code += [f'{npact} = OpLogicalNot %bool {pact}', f'{coord1} = OpCompositeConstruct %v2uint {x1} {y}']
        writes.append((npact, coord1, tex1))
        out += [pad + c for c in code]
        for c, coord, val in writes:
            yes, after = new('w'), new('wd')
            out += [f'{pad}OpSelectionMerge {after} None', f'{pad}OpBranchConditional {c} {yes} {after}',
                    f'{yes} = OpLabel', f'{pad}OpImageWrite {img} {coord} {val}', f'{pad}OpBranch {after}',
                    f'{after} = OpLabel']
            phi_fix[block] = after
            block = after
        continue
    out.append(l)

# Blocks split above end in a new label now: fix the phis that named them.
res = []
for l in out:
    if 'OpPhi' in l:
        for old, nw in phi_fix.items():
            l = re.sub(re.escape(old) + r'(?=\s|$)', nw, l)
    res.append(l)
out = res

# Function variables at the top of main's first block; capabilities.
first_label = next(i for i, l in enumerate(out) if i > main_i and re.match(r'\s*%\w+ = OpLabel$', l))
out[first_label + 1:first_label + 1] = [f'{pad}{v} = OpVariable %sh_pv4 Function' for v in fvars]
caps = {re.match(r'\s*OpCapability (\w+)', l)[1] for l in out if re.match(r'\s*OpCapability', l)}
cap_at = next(i for i, l in enumerate(out) if re.match(r'\s*OpCapability', l))
for c in ('GroupNonUniform', 'GroupNonUniformShuffle'):
    if c not in caps:
        out.insert(cap_at, f'{pad}OpCapability {c}')
print('\n'.join(out))
