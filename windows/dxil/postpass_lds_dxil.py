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
# output color) keep their values in registers instead, and after the pass's bounds check the
# group writes the two textures one after the other: the threads put one texture's 32x32 block
# into shared memory (x y z per pixel, alpha repeats x: 12288 bytes), and the group writes it out
# in solid blocks (each wave an aligned 8x8 block of pixels). One texture at a time keeps shared
# memory small enough for several groups to run on a WGP at once.
#
# The stores to the half texture (the recurrent state) stay as they are: sending it through shared
# memory as well (as the floats it is converted from) measured no faster under vkd3d-proton.
# Nothing else changes, so the output is bit-exact.
#
# POSTPASS_DIRECT (default 1; 0 for the files up to release dll-2026-10-07; as ../../postpass_direct.py does on Linux): the first
# of the two float textures goes into shared memory as each of its pixels is computed, instead of
# waiting in registers until the end of the pass, so a thread holds 12 values fewer. Shared memory
# is free at that point: nothing else uses it before the first flush.
import os
import re
import sys

# POSTPASS_HALF (default 1; 0 for the files up to release dll-2026-10-07): the half texture goes through shared memory as well (16384 bytes for a block),
# so that none of the pass's scattered stores are left. Its four channels are kept as the floats
# AMD's code narrows to halves just before each store, and are narrowed just before the store
# here too: narrowing earlier and widening again does not give the same texels under
# vkd3d-proton, where the narrowing is left to the store itself. With POSTPASS_DIRECT=1 it is then the half texture that goes in as it
# is computed, and it is written out first.
DIRECT = os.environ.get('POSTPASS_DIRECT', '1') == '1'
HALF = os.environ.get('POSTPASS_HALF', '1') == '1'
SLOTS = 4 if HALF else 3                       # values per pixel in shared memory

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


# The stores after the bounds check: their values reach the flush as phis in the exit block.
check_block = block_of(check_line)
exit_preds = [b for b in order if exit_block in succ[b]]
if check_block not in exit_preds:
    die('the bounds check does not branch to the exit block directly')
cond_oob = lines[check_line].split()[2].rstrip(',')
held = {}        # key -> list of 4 (x, y, [v0, v1, v2]) in store order
STORE = re.compile(r'\s*call void @dx\.op\.textureStore\.(f16|f32)\(i32 67, %dx\.types\.Handle (%[\w.]+), '
                   r'i32 (%[\w.]+), i32 (%[\w.]+), i32 undef, (\w+) (\S+), \w+ (\S+), \w+ (\S+), \w+ (\S+), i8 15\)')
targets = {}     # (base handle, properties) -> {'kind', 'slot', 'count'}
replace = {}     # line index -> replacement lines
n = [0]


def new(prefix):
    n[0] += 1
    return f'%bb.{prefix}{n[0]}'


F = f'[{1024 * SLOTS} x float], [{1024 * SLOTS} x float] addrspace(3)* @"\\01?bb_ldf@@3PAMA"'
scale = lambda r, v: f'  {r} = shl i32 {v}, 2' if HALF else f'  {r} = mul i32 {v}, 3'      # pixel -> its first value


def widen(code, v, ty):
    """the value as a float: a half widens exactly"""
    if ty == 'float':
        return v
    r = new('w')
    code.append(f'  {r} = fpext half {v} to float')
    return r


floats_used = 0
halfs = 0
for i in range(check_line, end):
    m = STORE.match(lines[i])
    if not m:
        if 'dx.op.textureStore' in lines[i]:
            die('unexpected store: ' + lines[i].strip()[:100])
        continue
    kind, handle, x, y = m[1], m[2], m[3], m[4]
    if kind == 'f16' and not HALF:
        halfs = halfs + 1
        continue
    values = [m[6], m[7], m[8], m[9]]
    nc, ty = (4 if kind == 'f16' else 3), 'float'
    if kind == 'f16':
        src = [re.match(r'fptrunc float (%[\w.]+) to half$', re.sub(r'\s*;.*$', '', defs.get(v, (0, ''))[1])) for v in values]
        if not all(src):
            die('a half texel is not narrowed from floats right before its store: ' + lines[i].strip()[:100])
        values = [m_[1] for m_ in src]
    a = re.match(r'call %dx\.types\.Handle @dx\.op\.annotateHandle\(i32 216, %dx\.types\.Handle (%[\w.]+), '
                 r'(%dx\.types\.ResourceProperties \{[^}]*\})\)', defs.get(handle, (0, ''))[1])
    if not a or 'createHandleFromBinding' not in defs.get(a[1], (0, ''))[1] or defs[a[1]][0] > check_line:
        die('unexpected texture handle of a store: ' + lines[i].strip()[:100])
    if reaches_exit_without(block_of(i)):
        die('a store is conditional: ' + lines[i].strip()[:100])
    key = (a[1], a[2])
    if key not in targets:
        targets[key] = {'kind': kind, 'slot': floats_used, 'count': 0, 'nc': nc, 'ty': ty,
                        'direct': DIRECT and (kind == 'f16' if HALF else floats_used == 0)}
        floats_used += 3
    t = targets[key]
    if t['kind'] != kind:
        die('stores to one texture differ in type')
    if kind == 'f32' and values[3] != values[0]:
        die('float texel is not (x, y, z, x): ' + lines[i].strip()[:100])
    t['count'] += 1
    if t['direct']:
        lx, ly, row, pix, base = new('dlx'), new('dly'), new('drow'), new('dpix'), new('dbase')
        code = [f'  {lx} = sub i32 {x}, %bb.x0', f'  {ly} = sub i32 {y}, %bb.y0', f'  {row} = shl i32 {ly}, 5',
                f'  {pix} = add i32 {row}, {lx}', scale(base, pix)]
        for c in range(nc):
            e, p = new('de'), new('dp')
            v = widen(code, values[c], ty)
            code += [f'  {e} = add i32 {base}, {c}', f'  {p} = getelementptr {F}, i32 0, i32 {e}',
                     f'  store float {v}, float addrspace(3)* {p}, align 4']
        replace[i] = code
        continue
    held.setdefault(key, []).append((x, y, values[:nc]))
    replace[i] = []

if len(targets) != (3 if HALF else 2) or any(t['count'] != 4 for t in targets.values()) or halfs != (0 if HALF else 4):
    die(f'expected 4 stores to each of two float textures and one half texture, found '
        f'{[t["count"] for t in targets.values()]} and {halfs}')

# Phis at the top of the exit block: the held values on the path from the body, undef from the
# bounds check (those threads write nothing).
phis = []
phi_of = {}


def phi(v, ty):
    if (v, ty) not in phi_of:
        r = new('phi')
        srcs = ', '.join(f'[ {"undef" if b == check_block else v}, {b} ]' for b in exit_preds)
        phis.append(f'  {r} = phi {ty} {srcs}')
        phi_of[(v, ty)] = r
    return phi_of[(v, ty)]


held_phi = {key: [(phi(x, 'i32'), phi(y, 'i32'), [phi(v, targets[key]['ty']) for v in vs]) for x, y, vs in stores]
            for key, stores in held.items()}

# The flush, in place of the exit block's "ret void".
ok = new('ok')
flush = [f'  {ok} = xor i1 {cond_oob}, true']
handles = {}
for key in targets:
    h = new('h')
    flush.append(f'  {h} = call %dx.types.Handle @dx.op.annotateHandle(i32 216, %dx.types.Handle {key[0]}, {key[1]})')
    handles[key] = h
# the texture already in shared memory is written first, before anything else is put there
for t_i, key in enumerate(sorted(targets, key=lambda k: not targets[k]['direct'])):
    nc, ty = targets[key]['nc'], targets[key]['ty']
    put, putd = f'bb.put{t_i}', f'bb.putdone{t_i}'
    if key not in held_phi:      # already in shared memory (POSTPASS_DIRECT): wait for every thread's pixels, then write
        flush += ['  call void @dx.op.barrier(i32 80, i32 9)  ; GroupMemoryBarrierWithGroupSync',
                  f'  br label %bb.flush{t_i}_0']
    else:
        flush += ['  call void @dx.op.barrier(i32 80, i32 9)  ; GroupMemoryBarrierWithGroupSync',
                  f'  br i1 {ok}, label %{put}, label %{putd}', '', f'{put}:']
        for x, y, vs in held_phi[key]:
            lx, ly, row, pix, base = new('lx'), new('ly'), new('row'), new('pix'), new('base')
            flush += [f'  {lx} = sub i32 {x}, %bb.x0', f'  {ly} = sub i32 {y}, %bb.y0', f'  {row} = shl i32 {ly}, 5',
                      f'  {pix} = add i32 {row}, {lx}', scale(base, pix)]
            for c in range(nc):
                e, p = new('e'), new('p')
                v = widen(flush, vs[c], ty)
                flush += [f'  {e} = add i32 {base}, {c}', f'  {p} = getelementptr {F}, i32 0, i32 {e}',
                          f'  store float {v}, float addrspace(3)* {p}, align 4']
        flush += [f'  br label %{putd}', '', f'{putd}:',
                  '  call void @dx.op.barrier(i32 80, i32 9)  ; GroupMemoryBarrierWithGroupSync',
                  f'  br label %bb.flush{t_i}_0']
    for k in range(4):
        i, lx, ly, px, py, tx, ty, cx, cy, c = (new(p) for p in ('i', 'lx', 'ly', 'px', 'py', 'tx', 'ty', 'cx', 'cy', 'c'))
        wv, ln, a1, a2, a3, b1, b2, b3, pixr, pixi = (new(p) for p in ('wv', 'ln', 'a', 'a', 'a', 'b', 'b', 'b', 'pixr', 'pix'))
        nxt = f'bb.flush{t_i}_{k + 1}' if k < 3 else (f'bb.next{t_i}')
        flush += ['', f'bb.flush{t_i}_{k}:',
                  # each wave (64 lanes) writes an aligned 8x8 block of the 32x32 block
                  f'  {i} = add i32 %bb.tid, {256 * k}', f'  {wv} = lshr i32 {i}, 6', f'  {ln} = and i32 {i}, 63',
                  f'  {a1} = and i32 {wv}, 3', f'  {a2} = shl i32 {a1}, 3', f'  {a3} = and i32 {ln}, 7',
                  f'  {lx} = or i32 {a2}, {a3}',
                  f'  {b1} = lshr i32 {wv}, 2', f'  {b2} = shl i32 {b1}, 3', f'  {b3} = lshr i32 {ln}, 3',
                  f'  {ly} = or i32 {b2}, {b3}', f'  {pixr} = shl i32 {ly}, 5', f'  {pixi} = or i32 {pixr}, {lx}',
                  f'  {px} = add i32 %bb.x0, {lx}', f'  {py} = add i32 %bb.y0, {ly}',
                  f'  {tx} = lshr i32 {px}, 1', f'  {ty} = lshr i32 {py}, 1',
                  f'  {cx} = icmp ult i32 {tx}, {w2}', f'  {cy} = icmp ult i32 {ty}, {h2}', f'  {c} = and i1 {cx}, {cy}',
                  f'  br i1 {c}, label %bb.write{t_i}_{k}, label %{nxt}', '', f'bb.write{t_i}_{k}:']
        fbase = new('fbase')
        flush.append(scale(fbase, pixi))
        vals = []
        for comp in range(nc):
            e, p, v = new('e'), new('p'), new('v')
            flush += [f'  {e} = add i32 {fbase}, {comp}', f'  {p} = getelementptr {F}, i32 0, i32 {e}',
                      f'  {v} = load float, float addrspace(3)* {p}, align 4']
            if targets[key]['kind'] == 'f16':
                flush.append(f'  {v}n = fptrunc float {v} to half')
                v += 'n'
            vals.append(v)
        if targets[key]['kind'] == 'f16':
            flush.append(f'  call void @dx.op.textureStore.f16(i32 67, %dx.types.Handle {handles[key]}, i32 {px}, i32 {py}, '
                         f'i32 undef, half {vals[0]}, half {vals[1]}, half {vals[2]}, half {vals[3]}, i8 15)')
        else:
            flush.append(f'  call void @dx.op.textureStore.f32(i32 67, %dx.types.Handle {handles[key]}, i32 {px}, i32 {py}, '
                         f'i32 undef, float {vals[0]}, float {vals[1]}, float {vals[2]}, float {vals[0]}, i8 15)')
        flush.append(f'  br label %{nxt}')
    flush += ['', f'bb.next{t_i}:']
flush += ['  ret void']

# Attribute group for the barrier, and the declarations.
used = [int(m[1]) for l in lines if (m := re.match(r'attributes #(\d+) = ', l))]
attr = max(used) + 1 if used else 0
out = []
for i, l in enumerate(lines):
    if i == start:
        out += [f'@"\\01?bb_ldf@@3PAMA" = external addrspace(3) global [{1024 * SLOTS} x float], align 4', '', l,
                '  %bb.gx = call i32 @dx.op.groupId.i32(i32 94, i32 0)',
                '  %bb.gy = call i32 @dx.op.groupId.i32(i32 94, i32 1)',
                '  %bb.tid = call i32 @dx.op.threadIdInGroup.i32(i32 95, i32 0)',
                '  %bb.x0 = shl i32 %bb.gx, 5', '  %bb.y0 = shl i32 %bb.gy, 5']
    elif i in replace:
        out += replace[i]
    elif i == blocks[exit_block][0] and i != ret_line:
        out += phis + [l]
    elif i == ret_line:
        out += (phis if i == blocks[exit_block][0] else []) + flush
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
