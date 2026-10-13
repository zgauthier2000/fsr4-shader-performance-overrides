# SPDX-License-Identifier: GPL-2.0-or-later
# Layout shared by frameskip.py, motionpost.py and skipblend.py (and their DXIL forms).

def plane_layout(S):
    """Where the "who was here a frame ago" plane sits and how its words are packed (shared by frameskip, motionpost, skipblend).
    One word per 4x4 output pixels, in the same rows of the second region as the motion entries, in word ranges those leave free.
    A word is (nearness << IDB) | (block row << XB) | block column, 0 = nobody; the nearest surface wins (atomic maximum)."""
    width = S // 16 - 2; nx, ny = width // 2, (width * 9 // 16) // 2
    xb, yb = (nx - 1).bit_length(), (ny - 1).bit_length()
    pb0, pb1 = {15392: (1040, 3040), 30752: (2048, 6144), 61472: (8192, 10240)}[S]
    return dict(nx=nx, ny=ny, xb=xb, idb=xb + yb, kb=32 - xb - yb, m=32 - xb - yb - 5, pb0=pb0, pb1=pb1)


# The cleared diagonals (since release dll-2026-10-13; FS_HOLE=0 = as before).
# A half-width tensor of row stride S/2 + 16 bytes shares the second region, and the shader that clears its left border runs on skipped
# frames too. In buffer row r that zeroes the 8 words from 4 + 8r and the 8 words from S/8 + 8 + 8r: two diagonals through the motion
# entries and the plane. Every in-row word offset is therefore stepped past them: + 8 from the first diagonal on, + 8 again from the
# second. The map keeps the order of the words, so the ranges stay apart (each has at least 16 spare words after it).
import os
import re
HOLE = os.environ.get('FS_HOLE', '1') == '1'


def holes_spv(lines, pre, S, sites):
    """SPIR-V text lines: every  <a2> = base + row * rowsize + block  followed by  <idx> = <a2> + x  becomes  <idx> = base + row * rowsize + step(block + x).
    Returns (lines, constants to declare). `sites` = how many such addresses the caller expects at least."""
    if not HOLE:
        return lines, []
    defs = {m[1]: m[2] for l in lines for m in [re.match(r'\s*(%\w+) = (.*)$', l)] if m}
    out, n = [], 0
    for l in lines:
        m = re.match(r'(\s*)(%\w+) = OpIAdd %uint (%\w+)a2 (%\w+)$', l)
        a2 = m and re.match(r'OpIAdd %uint (%\w+)a1 (%\w+)$', defs.get(m[3] + 'a2', ''))
        rw = a2 and a2[1] == m[3] and re.match(r'OpIMul %uint (%\w+) %\w+row$', defs.get(m[3] + 'rw', ''))
        if not rw:
            out.append(l); continue
        p = f'{m[3]}zh'; n += 1
        out += [m[1] + x for x in (
            f'{p}f = OpIAdd %uint {a2[2]} {m[4]}', f'{p}s = OpShiftLeftLogical %uint {rw[1]} %{pre}_zh3', f'{p}d1 = OpIAdd %uint {p}s %{pre}_zh4',
            f'{p}c1 = OpUGreaterThanEqual %bool {p}f {p}d1', f'{p}s1 = OpSelect %uint {p}c1 %{pre}_zh8 %{pre}_zh0', f'{p}o1 = OpIAdd %uint {p}f {p}s1',
            f'{p}d2 = OpIAdd %uint {p}d1 %{pre}_zhd', f'{p}c2 = OpUGreaterThanEqual %bool {p}o1 {p}d2', f'{p}s2 = OpSelect %uint {p}c2 %{pre}_zh8 %{pre}_zh0',
            f'{p}o = OpIAdd %uint {p}o1 {p}s2', f'{m[2]} = OpIAdd %uint {m[3]}a1 {p}o')]
    # no address may be left that still adds to an <a2> of a row product
    left = [k[:-2] for k, v in defs.items() if k.endswith('rw') and re.match(r'OpIMul %uint %\w+ %\w+row$', v)
            and any(re.search(rf'{re.escape(k[:-2])}a2(?!\w)', l) and not re.match(rf'\s*{re.escape(k[:-2])}a2 = ', l) for l in out)]
    if left or n < sites:
        raise SystemExit(f'holes_spv ({pre}): {n} addresses rewritten, at least {sites} expected; not rewritten: {left}')
    return out, [f'%{pre}_zh0 = OpConstant %uint 0', f'%{pre}_zh3 = OpConstant %uint 3', f'%{pre}_zh4 = OpConstant %uint 4', f'%{pre}_zh8 = OpConstant %uint 8',
                 f'%{pre}_zhd = OpConstant %uint {S // 8 + 4}']


def holes_dxil(lines, S, sites):
    """The same for DXIL text lines, where the offsets are bytes:  <a2> = add <a1>, block ;  <idx> = add <a2>, x."""
    if not HOLE:
        return lines
    defs = {m[1]: m[2] for l in lines for m in [re.match(r'\s*(%[\w.]+) = (.*)$', l)] if m}
    out, n = [], 0
    for l in lines:
        m = re.match(r'(\s*)(%[\w.]+) = add i32 (%[\w.]+)a2, (%[\w.]+)$', l)
        a2 = m and re.match(r'add i32 (%[\w.]+)a1, (%[\w.]+)$', defs.get(m[3] + 'a2', ''))
        rw = a2 and a2[1] == m[3] and re.match(rf'mul i32 (%[\w.]+), {S}$', defs.get(m[3] + 'rw', ''))
        if not rw:
            out.append(l); continue
        p = f'{m[3]}zh'; n += 1
        out += [m[1] + x for x in (
            f'{p}f = add i32 {a2[2]}, {m[4]}', f'{p}s = shl i32 {rw[1]}, 5', f'{p}d1 = add i32 {p}s, 16',
            f'{p}c1 = icmp uge i32 {p}f, {p}d1', f'{p}s1 = select i1 {p}c1, i32 32, i32 0', f'{p}o1 = add i32 {p}f, {p}s1',
            f'{p}d2 = add i32 {p}d1, {S // 2 + 16}', f'{p}c2 = icmp uge i32 {p}o1, {p}d2', f'{p}s2 = select i1 {p}c2, i32 32, i32 0',
            f'{p}o = add i32 {p}o1, {p}s2', f'{m[2]} = add i32 {m[3]}a1, {p}o')]
    left = [k[:-2] for k, v in defs.items() if k.endswith('rw') and re.match(rf'mul i32 %[\w.]+, {S}$', v)
            and any(re.search(rf'{re.escape(k[:-2])}a2(?![\w.])', l) and not re.match(rf'\s*{re.escape(k[:-2])}a2 = ', l) for l in out)]
    if left or n < sites:
        raise SystemExit(f'holes_dxil: {n} addresses rewritten, at least {sites} expected; not rewritten: {left}')
    return out


def holes_spv_module(lines, pre, S, sites):
    """holes_spv on a whole module's lines; the constants go in front of the first function."""
    lines, consts = holes_spv(lines, pre, S, sites)
    if consts:
        k = next(i for i, l in enumerate(lines) if '= OpFunction ' in l)
        lines[k:k] = consts
    return lines
