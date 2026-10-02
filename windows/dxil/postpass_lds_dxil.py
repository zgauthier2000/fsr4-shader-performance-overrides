#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Rewrites the FSR 4.1.1 (INT8) postpass in DXIL form (LLVM IR text from "dxc -dumpbin") so that
# its image stores go through thread-group shared memory, as postpass_lds_vkd3d.py does for the
# SPIR-V that vkd3d-proton generates. Derived from tools/fsr4cap/postpass_lds.py of bbport
# (https://github.com/deadinside28/bloodborne_pc, GPL-2.0-or-later).
#
#   dxc -dumpbin <postpass.dxil> | postpass_lds_dxil.py > out.ll      (then dxilasm)
#
# Each thread computes a 2x2 block of output pixels (the thread group: 32x32) and writes it into
# three textures one pixel per store. Here the stores to the two float textures (history and
# output colour) save their value in shared memory instead: 6 floats per pixel, x y z of each
# (alpha repeats x), 24576 bytes of the 32768 that D3D12 allows a thread group. After the pass's
# bounds check the group writes its 32x32 block of both textures in contiguous rows.
#
# The stores to the half texture (the recurrent state) stay as they are. Moving them as well gains
# nothing measurable, the floats they are converted from would not fit in the 32768 bytes, and
# keeping them as halfs in shared memory changes how a driver may round them. Nothing else
# changes, so the output is bit-exact.
import re
import sys

lines = sys.stdin.read().split('\n')


def die(msg):
    sys.exit('postpass_lds_dxil: ' + msg)


start = next((i for i, l in enumerate(lines) if l.startswith('define void @')), None)
if start is None:
    die('no entry function')
end = next(i for i in range(start, len(lines)) if lines[i] == '}')
if not any(re.match(r'!\d+ = !\{i32 256, i32 1, i32 1\}', l) for l in lines):
    die('thread group size is not 256x1x1')

defs = {}        # value -> (line index, text after '=')
for i in range(start, end):
    m = re.match(r'\s*(%[\w.]+) = (.*)$', lines[i])
    if m:
        defs[m[1]] = (i, m[2])

# Basic blocks: label -> (first line, last line); the entry block is '%0'.
blocks = {}
order = []
label = '%0'
first = start + 1
for i in range(start + 1, end):
    m = re.match(r'; <label>:(\d+)', lines[i]) or re.match(r'([\w.]+):', lines[i])
    if m:
        blocks[label] = (first, i - 1)
        order.append(label)
        label, first = '%' + m[1], i + 1
blocks[label] = (first, end - 1)
order.append(label)


def terminator(b):
    lo, hi = blocks[b]
    for i in range(hi, lo - 1, -1):
        s = lines[i].strip()
        if s.startswith(('br ', 'ret ', 'switch ')):
            return i, s
    die(f'block {b} has no terminator')


succ = {b: re.findall(r'label (%[\w.]+)', terminator(b)[1]) for b in order}

# The bounds check: br i1 (x >= W/2 || y >= H/2), label %exit, label %body
check = None
for b in order:
    i, t = terminator(b)
    m = re.match(r'br i1 (%[\w.]+), label (%[\w.]+), label (%[\w.]+)', t)
    cond = m and re.match(r'or i1 (%[\w.]+), (%[\w.]+)', defs.get(m[1], (0, ''))[1])
    if cond:
        cx = re.match(r'icmp uge i32 (%[\w.]+), (%[\w.]+)', defs[cond[1]][1])
        cy = re.match(r'icmp uge i32 (%[\w.]+), (%[\w.]+)', defs[cond[2]][1])
        if cx and cy:
            check = (i, m[2], m[3], cx[2], cy[2])
            break
if not check:
    die('no bounds check found')
check_line, exit_block, body_block, w2, h2 = check
ret_line, ret_text = terminator(exit_block)
if ret_text != 'ret void':
    die('the bounds check does not branch to the returning block')


def reaches_exit_without(skip):
    seen, todo = set(), [body_block]
    while todo:
        b = todo.pop()
        if b == skip or b in seen:
            continue
        if b == exit_block:
            return True
        seen.add(b)
        todo += succ[b]
    return False


def block_of(line):
    return next(b for b in order if blocks[b][0] <= line <= blocks[b][1])


# The stores after the bounds check.
STORE = re.compile(r'\s*call void @dx\.op\.textureStore\.(f16|f32)\(i32 67, %dx\.types\.Handle (%[\w.]+), '
                   r'i32 (%[\w.]+), i32 (%[\w.]+), i32 undef, (\w+) (\S+), \w+ (\S+), \w+ (\S+), \w+ (\S+), i8 15\)')
targets = {}     # (base handle, properties) -> {'kind', 'slot', 'count'}
replace = {}     # line index -> replacement lines
n = [0]


def new(prefix):
    n[0] += 1
    return f'%bb.{prefix}{n[0]}'


F = '[6144 x float], [6144 x float] addrspace(3)* @"\\01?bb_ldf@@3PAMA"'
floats_used = 0
halfs = 0
for i in range(check_line, end):
    m = STORE.match(lines[i])
    if not m:
        if 'dx.op.textureStore' in lines[i]:
            die('unexpected store: ' + lines[i].strip()[:100])
        continue
    kind, handle, x, y = m[1], m[2], m[3], m[4]
    if kind == 'f16':
        halfs = halfs + 1
        continue
    values = [m[6], m[7], m[8], m[9]]
    a = re.match(r'call %dx\.types\.Handle @dx\.op\.annotateHandle\(i32 216, %dx\.types\.Handle (%[\w.]+), '
                 r'(%dx\.types\.ResourceProperties \{[^}]*\})\)', defs.get(handle, (0, ''))[1])
    if not a or 'createHandleFromBinding' not in defs.get(a[1], (0, ''))[1] or defs[a[1]][0] > check_line:
        die('unexpected texture handle of a store: ' + lines[i].strip()[:100])
    if reaches_exit_without(block_of(i)):
        die('a store is conditional: ' + lines[i].strip()[:100])
    key = (a[1], a[2])
    if key not in targets:
        targets[key] = {'kind': kind, 'slot': floats_used, 'count': 0}
        floats_used += 3
    t = targets[key]
    if t['kind'] != kind:
        die('stores to one texture differ in type')
    if kind == 'f32' and values[3] != values[0]:
        die('float texel is not (x, y, z, x): ' + lines[i].strip()[:100])
    lx, ly, row, pix, base = new('lx'), new('ly'), new('row'), new('pix'), new('base')
    code = [f'  {lx} = sub i32 {x}, %bb.x0', f'  {ly} = sub i32 {y}, %bb.y0',
            f'  {row} = shl i32 {ly}, 5', f'  {pix} = add i32 {row}, {lx}']
    code.append(f'  {base} = mul i32 {pix}, 6')
    for c in range(3):
        e, p = new('e'), new('p')
        code += [f'  {e} = add i32 {base}, {t["slot"] + c}', f'  {p} = getelementptr {F}, i32 0, i32 {e}',
                 f'  store float {values[c]}, float addrspace(3)* {p}, align 4']
    replace[i] = code
    t['count'] += 1

if len(targets) != 2 or any(t['count'] != 4 for t in targets.values()) or halfs != 4:
    die(f'expected 4 stores to each of two float textures and one half texture, found '
        f'{[t["count"] for t in targets.values()]} and {halfs}')

# The flush, in place of the exit block's "ret void".
flush = ['  call void @dx.op.barrier(i32 80, i32 9)  ; GroupMemoryBarrierWithGroupSync']
handles = {}
for key in targets:
    h = new('h')
    flush.append(f'  {h} = call %dx.types.Handle @dx.op.annotateHandle(i32 216, %dx.types.Handle {key[0]}, {key[1]})')
    handles[key] = h
flush.append('  br label %bb.flush0')
for k in range(4):
    i, lx, ly, px, py, tx, ty, cx, cy, c = (new(p) for p in ('i', 'lx', 'ly', 'px', 'py', 'tx', 'ty', 'cx', 'cy', 'c'))
    flush += ['', f'bb.flush{k}:',
              f'  {i} = add i32 %bb.tid, {256 * k}', f'  {lx} = and i32 {i}, 31', f'  {ly} = lshr i32 {i}, 5',
              f'  {px} = add i32 %bb.x0, {lx}', f'  {py} = add i32 %bb.y0, {ly}',
              f'  {tx} = lshr i32 {px}, 1', f'  {ty} = lshr i32 {py}, 1',
              f'  {cx} = icmp ult i32 {tx}, {w2}', f'  {cy} = icmp ult i32 {ty}, {h2}', f'  {c} = and i1 {cx}, {cy}',
              f'  br i1 {c}, label %bb.write{k}, label %bb.flush{k + 1}', '', f'bb.write{k}:']
    fbase = new('fbase')
    flush.append(f'  {fbase} = mul i32 {i}, 6')
    for key, t in targets.items():
        vals = []
        for comp in range(3):
            e, p, v = new('e'), new('p'), new('v')
            flush += [f'  {e} = add i32 {fbase}, {t["slot"] + comp}', f'  {p} = getelementptr {F}, i32 0, i32 {e}',
                      f'  {v} = load float, float addrspace(3)* {p}, align 4']
            vals.append(v)
        flush.append(f'  call void @dx.op.textureStore.f32(i32 67, %dx.types.Handle {handles[key]}, i32 {px}, i32 {py}, '
                     f'i32 undef, float {vals[0]}, float {vals[1]}, float {vals[2]}, float {vals[0]}, i8 15)')
    flush.append(f'  br label %bb.flush{k + 1}')
flush += ['', 'bb.flush4:', '  ret void']

# Attribute group for the barrier, and the declarations.
used = [int(m[1]) for l in lines if (m := re.match(r'attributes #(\d+) = ', l))]
attr = max(used) + 1 if used else 0
out = []
for i, l in enumerate(lines):
    if i == start:
        out += ['@"\\01?bb_ldf@@3PAMA" = external addrspace(3) global [6144 x float], align 4', '', l,
                '  %bb.gx = call i32 @dx.op.groupId.i32(i32 94, i32 0)',
                '  %bb.gy = call i32 @dx.op.groupId.i32(i32 94, i32 1)',
                '  %bb.tid = call i32 @dx.op.threadIdInGroup.i32(i32 95, i32 0)',
                '  %bb.x0 = shl i32 %bb.gx, 5', '  %bb.y0 = shl i32 %bb.gy, 5']
    elif i in replace:
        out += replace[i]
    elif i == ret_line:
        out += flush
    elif i == end:
        out += [l, '', f'declare void @dx.op.barrier(i32, i32) #{attr}']
        for name, sig in (('groupId', 'declare i32 @dx.op.groupId.i32(i32, i32)'),
                          ('threadIdInGroup', 'declare i32 @dx.op.threadIdInGroup.i32(i32, i32)')):
            if not any(x.startswith(sig) for x in lines):
                out.append(sig + ' #0')
    else:
        out.append(l)
    if used and l.startswith(f'attributes #{max(used)} = '):
        out.append(f'attributes #{attr} = {{ noduplicate nounwind }}')
print('\n'.join(out))
