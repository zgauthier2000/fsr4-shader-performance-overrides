#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Rewrites the FSR 4.1.1 (INT8) postpass as dumped by vkd3d-proton (VKD3D_SHADER_DUMP_PATH) so
# that its image stores go through workgroup memory.
#
#   spirv-dis <hash>.spv | postpass_lds_vkd3d.py > out.spvasm ; spirv-as --target-env spv1.3
#
# Each invocation computes a 2x2 block of output pixels (the workgroup: 32x32) and writes it into
# three images one pixel per store; on RDNA3 those scattered stores cost most of the pass. Here
# every store saves its value in workgroup memory (10 floats per pixel: two images' xyz, with x
# repeated in alpha, and the recurrent state's xyzw), and after the pass's bounds check the
# workgroup writes its 32x32 block in contiguous rows. Nothing else in the shader changes, so the
# output is bit-exact.
#
# Adapted from tools/fsr4cap/postpass_lds.py of bbport (https://github.com/deadinside28/bloodborne_pc,
# GPL-2.0-or-later), which expects dxil-spirv command-line output with reflection names.
# vkd3d-proton indexes descriptor heaps instead, so the three target images are identified here by
# (heap variable, offset from the root constant), and the bounds check by its shape.
import re
import sys

lines = sys.stdin.read().split('\n')
out = []

def die(msg):
    sys.exit(f'postpass_lds_vkd3d: {msg}')

def find(pattern, start=0):
    for i in range(start, len(lines)):
        m = re.search(pattern, lines[i])
        if m:
            return i, m
    die(f'no match for {pattern}')

defs = {}
def_line = {}
for number, line in enumerate(lines):
    m = re.match(r'\s*(%\w+) = (.*)$', line)
    if m:
        defs[m[1]] = m[2]
        def_line[m[1]] = number

for need in ('%uint', '%float', '%bool', '%v2uint', '%v4float', '%uint_0', '%uint_1',
             '%_ptr_Input_uint', '%gl_WorkGroupID', '%gl_LocalInvocationID'):
    if need not in defs:
        die(f'{need} is not defined')
if not any(re.search(r'OpExecutionMode %main LocalSize 256 1 1$', l) for l in lines):
    die('local size is not 256x1x1')

# The thread bounds (W/2, H/2) of the pass's own early-out.
main_i, _ = find(r'^\s*%main = OpFunction ')
sel_i = None
for i in range(main_i, len(lines)):
    m = re.match(r'\s*OpSelectionMerge (%\w+) None', lines[i])
    if not m:
        continue
    b = re.match(r'\s*OpBranchConditional (%\w+) (%\w+) (%\w+)', lines[i + 1])
    lor = b and re.match(r'OpLogicalOr %bool (%\w+) (%\w+)$', defs.get(b[1], ''))
    if lor and b[2] == m[1] and all(defs.get(v, '').startswith('OpUGreaterThanEqual %bool') for v in lor.groups()):
        sel_i, merge = i, m[1]
        gx = re.match(r'OpUGreaterThanEqual %bool (%\w+) (%\w+)$', defs[lor[1]])
        gy = re.match(r'OpUGreaterThanEqual %bool (%\w+) (%\w+)$', defs[lor[2]])
        break
if sel_i is None:
    die('no bounds check found')
w2, h2 = gx[2], gy[2]

def target(image_id):
    """(image type, pointer type, heap variable, base pointer chain, offset constant) of a store."""
    load = re.match(r'OpLoad (%\w+) (%\w+)$', defs[image_id])
    chain = load and re.match(r'OpAccessChain (%\w+) (%\w+) (%\w+)$', defs[load[2]])
    add = chain and re.match(r'OpIAdd %uint (%\w+) (%\w+)$', defs[chain[3]])
    base = add and re.match(r'OpLoad %uint (%\w+)$', defs[add[1]])
    reg = base and re.match(r'OpAccessChain (%\w+) (%\w+) (%\w+)$', defs[base[1]])
    if not reg or not defs[add[2]].startswith('OpConstant %uint '):
        die(f'unexpected image of a store: {image_id} = {defs[image_id]}')
    return (load[1], chain[1], chain[2], (reg[1], reg[2], reg[3]), add[2])

n = [0]

def new(prefix):
    n[0] += 1
    return f'%bb_{prefix}{n[0]}'

decl = [
    '%bb_u5 = OpConstant %uint 5', '%bb_u31 = OpConstant %uint 31', '%bb_u10 = OpConstant %uint 10',
    '%bb_u2 = OpConstant %uint 2', '%bb_u264 = OpConstant %uint 264',
    '%bb_u10240 = OpConstant %uint 10240',
] + [f'%bb_c{c} = OpConstant %uint {c}' for c in range(10)] + [
    f'%bb_k{k} = OpConstant %uint {256 * k}' for k in range(4)] + [
    '%bb_arr = OpTypeArray %float %bb_u10240',
    '%bb_ptr_arr = OpTypePointer Workgroup %bb_arr',
    '%bb_ptr_f = OpTypePointer Workgroup %float',
    '%bb_lds = OpVariable %bb_ptr_arr Workgroup',
]
preamble = [
    '%bb_wgx_p = OpAccessChain %_ptr_Input_uint %gl_WorkGroupID %uint_0',
    '%bb_wgx = OpLoad %uint %bb_wgx_p',
    '%bb_wgy_p = OpAccessChain %_ptr_Input_uint %gl_WorkGroupID %uint_1',
    '%bb_wgy = OpLoad %uint %bb_wgy_p',
    '%bb_lid_p = OpAccessChain %_ptr_Input_uint %gl_LocalInvocationID %uint_0',
    '%bb_lid = OpLoad %uint %bb_lid_p',
    '%bb_x0 = OpShiftLeftLogical %uint %bb_wgx %bb_u5',
    '%bb_y0 = OpShiftLeftLogical %uint %bb_wgy %bb_u5',
]

slots = {}   # target -> (first float of the pixel's 10, 'xyzx' or 'xyzw')
conds = {}   # target -> (condition id, polarity) when the pass writes that image conditionally

def clone(v, code, done):
    """Recomputes a value of the bounds-checked region (a flag from the constant buffer) in the
    flush block, which that region does not dominate."""
    if v in done:
        return done[v]
    if v not in def_line or def_line[v] < sel_i:
        return v
    p = defs[v].split()
    if p[0] not in ('OpIEqual', 'OpINotEqual', 'OpCompositeExtract', 'OpLoad', 'OpInBoundsAccessChain', 'OpAccessChain',
                    'OpBitcast', 'OpLogicalNot', 'OpBitwiseAnd'):
        die(f'cannot recompute the store condition: {v} = {defs[v]}')
    args = [clone(a, code, done) if a.startswith('%') and a in def_line and i > 0 else a for i, a in enumerate(p[1:])]
    r = new('cond')
    code.append(f'{r} = {p[0]} ' + ' '.join(args))
    done[v] = r
    return r

def flush():
    code = ['OpControlBarrier %bb_u2 %bb_u2 %bb_u264']
    images = {}
    for tgt in slots:
        image_t, ptr_t, heap, (reg_t, reg_var, reg_member), offset = tgt
        rp, r, idx, p, img = new('rp'), new('r'), new('idx'), new('ip'), new('img')
        code += [f'{rp} = OpAccessChain {reg_t} {reg_var} {reg_member}', f'{r} = OpLoad %uint {rp}',
                 f'{idx} = OpIAdd %uint {r} {offset}', f'{p} = OpAccessChain {ptr_t} {heap} {idx}',
                 f'{img} = OpLoad {image_t} {p}']
        images[tgt] = img
    cloned, flags = {}, {}
    for tgt, (c, polarity) in ((t, c) for t, c in conds.items() if c):
        v = clone(c, code, cloned)
        if not polarity:
            inv = new('cond')
            code.append(f'{inv} = OpLogicalNot %bool {v}')
            v = inv
        flags[tgt] = v
    for k in range(4):
        i, lx, ly, px, py = new('i'), new('lx'), new('ly'), new('px'), new('py')
        code += [
            f'{i} = OpIAdd %uint %bb_lid %bb_k{k}',
            f'{lx} = OpBitwiseAnd %uint {i} %bb_u31',
            f'{ly} = OpShiftRightLogical %uint {i} %bb_u5',
            f'{px} = OpIAdd %uint %bb_x0 {lx}',
            f'{py} = OpIAdd %uint %bb_y0 {ly}',
        ]
        tx, ty, cx, cy, c = new('tx'), new('ty'), new('cx'), new('cy'), new('c')
        code += [
            f'{tx} = OpShiftRightLogical %uint {px} %uint_1',
            f'{ty} = OpShiftRightLogical %uint {py} %uint_1',
            f'{cx} = OpULessThan %bool {tx} {w2}',
            f'{cy} = OpULessThan %bool {ty} {h2}',
            f'{c} = OpLogicalAnd %bool {cx} {cy}',
        ]
        then, done = f'%bb_then{k}', f'%bb_done{k}'
        code += [f'OpSelectionMerge {done} None', f'OpBranchConditional {c} {then} {done}', f'{then} = OpLabel']
        base = new('base')
        code.append(f'{base} = OpIMul %uint {i} %bb_u10')
        vals = []
        for comp in range(10):
            e, p, v = new('e'), new('p'), new('v')
            code += [f'{e} = OpIAdd %uint {base} %bb_c{comp}', f'{p} = OpAccessChain %bb_ptr_f %bb_lds {e}',
                     f'{v} = OpLoad %float {p}']
            vals.append(v)
        coord = new('coord')
        code.append(f'{coord} = OpCompositeConstruct %v2uint {px} {py}')
        for tgt, (first, kind) in slots.items():
            comps = vals[first:first + 3] + [vals[first] if kind == 'xyzx' else vals[first + 3]]
            tex = new('tex')
            write = [f'{tex} = OpCompositeConstruct %v4float ' + ' '.join(comps),
                     f'OpImageWrite {images[tgt]} {coord} {tex}']
            if tgt in flags:
                yes, after = new('wthen'), new('wdone')
                write = [f'OpSelectionMerge {after} None', f'OpBranchConditional {flags[tgt]} {yes} {after}',
                         f'{yes} = OpLabel'] + write + [f'OpBranch {after}', f'{after} = OpLabel']
            code += write
        code += [f'OpBranch {done}', f'{done} = OpLabel']
    return code

stores = {}
in_main = False
merge_label_seen = False
flushed = False
pad = '               '
block = None
block_cond = {}    # block label -> (condition, polarity) of the selection that enters it
bounds_block = None
for number, line in enumerate(lines):
    s = line.strip()
    m = re.match(r'(%\w+) = OpLabel$', s)
    if m:
        block = m[1]
    m = re.match(r'OpBranchConditional (%\w+) (%\w+) (%\w+)$', s)
    sm = m and re.match(r'\s*OpSelectionMerge (%\w+) None', lines[number - 1])
    if sm:
        if number - 1 == sel_i:
            bounds_block = m[3]
        elif m[3] == sm[1]:
            block_cond[m[2]] = (m[1], True)
        elif m[2] == sm[1]:
            block_cond[m[3]] = (m[1], False)
    if s.startswith('%main = OpFunction'):
        out += [pad + d for d in decl]
        in_main = True
        out.append(line)
        continue
    if in_main and re.match(r'%\w+ = OpLabel$', s) and preamble:
        out.append(line)
        out += [pad + p for p in preamble]
        preamble = []
        continue
    m = re.match(r'OpImageWrite (%\w+) (%\w+) (%\w+)$', s)
    if in_main and m and number > sel_i:
        tgt = target(m[1])
        cond = block_cond.get(block)
        if conds.setdefault(tgt, cond) != cond:
            die(f'stores to one image are under different conditions: {s}')
        coord = re.match(r'OpCompositeConstruct %v2uint (%\w+) (%\w+)$', defs[m[2]])
        if not coord:
            die(f'unexpected coordinate of {s}')
        x, y = coord[1], coord[2]
        texel = defs[m[3]]
        if texel.startswith('OpFConvert %v4float'):
            kind = 'xyzw'
            comps = []
            for c in range(4):
                v = new('r')
                out.append(f'{pad}{v} = OpCompositeExtract %float {m[3]} {c}')
                comps.append(v)
        else:
            kind = 'xyzx'
            t = re.match(r'OpCompositeConstruct %v4float (%\w+) (%\w+) (%\w+) (%\w+)$', texel)
            if not t or t[4] != t[1]:
                die(f'texel is not (x, y, z, x): {texel}')
            comps = [t[1], t[2], t[3]]
        if tgt not in slots:
            used = sum(3 if k == 'xyzx' else 4 for _, k in slots.values())
            slots[tgt] = (used, kind)
        if slots[tgt][1] != kind:
            die(f'stores to one image differ in form: {s}')
        first = slots[tgt][0]
        lx, ly, row, pix, base = new('slx'), new('sly'), new('srow'), new('spix'), new('sbase')
        out += [pad + c for c in [
            f'{lx} = OpISub %uint {x} %bb_x0', f'{ly} = OpISub %uint {y} %bb_y0',
            f'{row} = OpShiftLeftLogical %uint {ly} %bb_u5', f'{pix} = OpIAdd %uint {row} {lx}',
            f'{base} = OpIMul %uint {pix} %bb_u10']]
        for c, v in enumerate(comps):
            e, p = new('se'), new('sp')
            out += [pad + q for q in [
                f'{e} = OpIAdd %uint {base} %bb_c{first + c}',
                f'{p} = OpAccessChain %bb_ptr_f %bb_lds {e}', f'OpStore {p} {v}']]
        stores[tgt] = stores.get(tgt, 0) + 1
        continue
    if in_main and s == f'{merge} = OpLabel':
        merge_label_seen = True
    if in_main and merge_label_seen and s == 'OpReturn':
        out += [pad + f for f in flush()]
        flushed = True
    out.append(line)

kinds = sorted(k for _, k in slots.values())
if kinds != ['xyzw', 'xyzx', 'xyzx'] or sorted(stores.values()) != [4, 4, 4] or not flushed:
    die(f'expected 4 stores to each of three images, found {sorted(stores.values())} {kinds}')
print('\n'.join(out))
