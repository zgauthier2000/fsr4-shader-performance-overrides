#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# motionpost.py < postpass.spvasm > out.spvasm     (AMD's postpass; run before skipblend.py)
#
# NOT bit-exact. For use with frameskip.py, whose prepass stores the motion.
# On a skipped frame the model's result belongs to the picture of the frame before. Each output
# pixel takes it from where its content was then: the displacement D (output pixels) that the
# prepass stored for the pixel's 4x4 block (frameskip.py).
#
# The model's result is one packed vector per cell, and each of a thread's four pixels has its own
# last layer (different constants per position in the cell). A pixel at position s whose content
# was at an odd distance needs the vector of another cell and the layer of the other position. So:
#   - the part of the shader that turns the model's tensor into the cell's vector (the "head") runs
#     for the cell at X + floor(D/2), and again for its right, lower and diagonal neighbour where D
#     is odd in x, in y, or in both (in branches: nothing extra where D is even or the frame ran);
#   - the pixel code for position s keeps its constants and gets the vector of the cell that holds
#     position s of the displaced picture, and writes the pixel that this content lands on:
#     x = 2X + (s xor (D & 1)).
import os, re, sys
L = sys.stdin.read().split('\n')
S = next((x for x in (15392, 30752, 61472) if any(f'%uint_{x} = ' in l for l in L)), None) or sys.exit('motionpost: no known row size')
width = S // 16 - 2; REGION = (width * 9 // 16 + 2) * S; WM = (REGION + S + 128) // 4
main = next(n for n, l in enumerate(L) if '= OpFunction' in l)
SSBO = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpVariable %_ptr_StorageBuffer__runtimearr_SSBO StorageBuffer', l)] if m)
GLSL = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpExtInstImport "GLSL.std.450"', l)] if m)
ge = [n for n, l in enumerate(L) if n > main and 'OpUGreaterThanEqual %bool' in l][:2]
X, WC = L[ge[0]].split()[-2:]; Y, HC = L[ge[1]].split()[-2:]
br = next(n for n in range(ge[1], len(L)) if 'OpBranchConditional' in L[n])
lab = L[br].split()[-1]
at = next(n for n, l in enumerate(L) if re.match(rf'\s*{re.escape(lab)} = OpLabel', l))
end = next(n for n, l in enumerate(L) if re.search(rf'= OpShiftLeftLogical %uint {re.escape(X)} %uint_1$', l))
m = re.match(r'\s*(%\w+) = ', L[end]); PX = m[1]
m = re.match(rf'\s*(%\w+) = OpShiftLeftLogical %uint {re.escape(Y)} %uint_1$', L[end + 1]) or sys.exit('motionpost: pixel row not where expected'); PY = m[1]
region = L[at + 1:end]
rdef = [m[1] for l in region for m in [re.match(r'\s*(%\w+) = ', l)] if m]
rlabels = [m[1] for l in region for m in [re.match(r'\s*(%\w+) = OpLabel', l)] if m]
after = '\n'.join(L[end:])
used_after = set(re.findall(r'%\w+', after)); rline = {m[1]: l for l in region for m in [re.match(r'\s*(%\w+) = ', l)] if m}
words = [d for d in rdef if d in used_after and re.match(rf'\s*{re.escape(d)} = OpBitcast %uint ', rline[d])]
if len(words) != 4:
    sys.exit(f'motionpost: {len(words)} words of the cell vector found, expected 4')
# what follows the vector in that part of the shader is per frame, not per cell: it runs once, as it was
cut = max(n for n, l in enumerate(region) if any(re.match(rf'\s*{re.escape(w)} = ', l) for w in words)) + 1
tail = region[cut:]; region = region[:cut]
rdef = [m[1] for l in region for m in [re.match(r'\s*(%\w+) = ', l)] if m]
rlabels = [m[1] for l in region for m in [re.match(r'\s*(%\w+) = OpLabel', l)] if m]
if any('OpLabel' in l for l in tail) or set(rdef) & set(re.findall(r'%\w+', '\n'.join(tail))) or (set(rdef) & used_after) - set(words) - set(rlabels):
    sys.exit('motionpost: the head is not separable from what follows it')
# The vector depends only on the model's output, which a skipped frame leaves as it was. So the frame that runs the model
# keeps every cell's vector, and the skipped frame reads it back instead of working it out again (for up to four cells).
# Where: the half of the working buffer that holds pass 11's output, which nothing reads between pass 12 and the next
# run of the model. The border-clearing shaders still run on a skipped frame and zero some lines of cells there (the
# borders of the tensors that share that memory); the vectors are kept xored with a pattern, so a zero word means
# "cleared", and such a cell is worked out as before.
CBASE = (int(os.environ['MP_CBASE_ROWS']) * S + 16) // 4 if os.environ.get('MP_CBASE_ROWS') else (REGION * 3 // 2 + S + 16) // 4
TAG = 0xA5A5A5A5
rn = lambda l, a, b: re.sub(rf'{re.escape(a)}(?!\w)', b, l)
c = ([f"%mp_jlo = OpConstant %float {float(os.environ['MP_SPOILJ'].split(',')[0])}", f"%mp_jhi = OpConstant %float {float(os.environ['MP_SPOILJ'].split(',')[1])}"] if os.environ.get('MP_SPOILJ') else []) + ([f"%mp_len = OpConstant %uint {int(os.environ['MP_LEN']) // 4}"] if os.environ.get('MP_LEN') else []) + [f'%mp_cbase = OpConstant %uint {CBASE}', f'%mp_tag = OpConstant %uint {TAG}', '%mp_false = OpConstantFalse %bool', '%mp_c2 = OpConstant %uint 2', '%mp_m1 = OpConstant %uint 1511506142', '%mp_m2 = OpConstant %uint 168889943', '%mp_c0 = OpConstant %uint 0', '%mp_c1 = OpConstant %uint 1', '%mp_c16 = OpConstant %uint 16',
     f'%mp_w0 = OpConstant %uint {WM}', f'%mp_w1 = OpConstant %uint {WM + 1}', f'%mp_base = OpConstant %uint {(REGION + S) // 4}', f'%mp_row = OpConstant %uint {S // 4}',
     '%mp_b0 = OpConstant %uint 48', f'%mp_b1 = OpConstant %uint {(2048 if S == 15392 else 4096)}', f'%mp_lo = OpConstant %uint {(-254) & 0xffffffff}', '%mp_hi = OpConstant %uint 254']
if os.environ.get('MP_FORCE'):
    c += [f"%mp_fx = OpConstant %uint {int(os.environ['MP_FORCE'].split(',')[0]) & 0xffffffff}", f"%mp_fy = OpConstant %uint {int(os.environ['MP_FORCE'].split(',')[1]) & 0xffffffff}"]
head = ['%mp_r1 = OpAccessChain %_ptr_PushConstant_uint %registers %uint_1', '%mp_r = OpLoad %uint %mp_r1', '%mp_bi = OpIAdd %uint %mp_r %uint_11',
        f'%mp_bp = OpAccessChain %_ptr_StorageBuffer_SSBO {SSBO} %mp_bi',
        '%mp_p0 = OpAccessChain %_ptr_StorageBuffer_uint %mp_bp %uint_0 %mp_w0', '%mp_v0 = OpLoad %uint %mp_p0',
        '%mp_p1 = OpAccessChain %_ptr_StorageBuffer_uint %mp_bp %uint_0 %mp_w1', '%mp_v1 = OpLoad %uint %mp_p1',
        '%mp_e1 = OpIEqual %bool %mp_v0 %mp_m1', '%mp_e2 = OpIEqual %bool %mp_v1 %mp_m2', *(['%mp_e3 = OpINotEqual %bool %mp_v0 %mp_m1', '%mp_skip = OpLogicalOr %bool %mp_e1 %mp_e3'] if os.environ.get('MP_FORCE') else ['%mp_skip = OpLogicalAnd %bool %mp_e1 %mp_e2']),
        # one stored entry per 4x4 output pixels (2x2 cells): frameskip.py
        f'%mp_xq = OpShiftRightLogical %uint {X} %mp_c1', f'%mp_yq = OpShiftRightLogical %uint {Y} %mp_c1',
        '%mp_yr = OpShiftRightLogical %uint %mp_yq %mp_c1', '%mp_yo = OpBitwiseAnd %uint %mp_yq %mp_c1', '%mp_yb = OpINotEqual %bool %mp_yo %mp_c0',
        '%mp_blk = OpSelect %uint %mp_yb %mp_b1 %mp_b0', '%mp_rw = OpIMul %uint %mp_yr %mp_row', '%mp_a1 = OpIAdd %uint %mp_base %mp_rw', '%mp_a2 = OpIAdd %uint %mp_a1 %mp_blk',
        '%mp_x2 = OpShiftLeftLogical %uint %mp_xq %mp_c1', '%mp_idx = OpIAdd %uint %mp_a2 %mp_x2', '%mp_pm = OpAccessChain %_ptr_StorageBuffer_uint %mp_bp %uint_0 %mp_idx', '%mp_m = OpLoad %uint %mp_pm',
        '%mp_xs = OpShiftLeftLogical %uint %mp_m %mp_c16', '%mp_dx0 = OpShiftRightArithmetic %uint %mp_xs %mp_c16', '%mp_dy0 = OpShiftRightArithmetic %uint %mp_m %mp_c16',
        *(['%mp_dx1 = OpCopyObject %uint %mp_fx', '%mp_dy1 = OpCopyObject %uint %mp_fy'] if os.environ.get('MP_FORCE') else [f'%mp_dx1 = OpExtInst %uint {GLSL} SClamp %mp_dx0 %mp_lo %mp_hi', f'%mp_dy1 = OpExtInst %uint {GLSL} SClamp %mp_dy0 %mp_lo %mp_hi']),
        '%mp_dx = OpSelect %uint %mp_skip %mp_dx1 %mp_c0', '%mp_dy = OpSelect %uint %mp_skip %mp_dy1 %mp_c0',
        '%mp_mx = OpShiftRightArithmetic %uint %mp_dx %mp_c1', '%mp_my = OpShiftRightArithmetic %uint %mp_dy %mp_c1',
        '%mp_rx = OpBitwiseAnd %uint %mp_dx %mp_c1', '%mp_ry = OpBitwiseAnd %uint %mp_dy %mp_c1',
        '%mp_nrx = OpBitwiseXor %uint %mp_rx %mp_c1', '%mp_nry = OpBitwiseXor %uint %mp_ry %mp_c1',
        '%mp_ox = OpINotEqual %bool %mp_rx %mp_c0', '%mp_oy = OpINotEqual %bool %mp_ry %mp_c0', '%mp_oxy = OpLogicalAnd %bool %mp_ox %mp_oy',
        f'%mp_wm = OpIAdd %uint {WC} %uint_4294967295', f'%mp_hm = OpIAdd %uint {HC} %uint_4294967295',
        f'%mp_xa = OpIAdd %uint {X} %mp_mx', f'%mp_ya = OpIAdd %uint {Y} %mp_my', '%mp_xb = OpIAdd %uint %mp_xa %mp_c1', '%mp_yb2 = OpIAdd %uint %mp_ya %mp_c1',
        f'%mp_X0 = OpExtInst %uint {GLSL} SClamp %mp_xa %mp_c0 %mp_wm', f'%mp_Y0 = OpExtInst %uint {GLSL} SClamp %mp_ya %mp_c0 %mp_hm',
        f'%mp_X1 = OpExtInst %uint {GLSL} SClamp %mp_xb %mp_c0 %mp_wm', f'%mp_Y1 = OpExtInst %uint {GLSL} SClamp %mp_yb2 %mp_c0 %mp_hm']
if '%uint_4294967295' not in '\n'.join(L[:main]):
    c.append('%uint_4294967295 = OpConstant %uint 4294967295')
NOCACHE = os.environ.get('MP_CACHE') == '0'
def addr(p, x, y):
    return [f'{p}ar = OpIMul %uint {y} %mp_row', f'{p}ab = OpIAdd %uint {p}ar %mp_cbase', f'{p}ax = OpShiftLeftLogical %uint {x} %mp_c2', f'{p}a0 = OpIAdd %uint {p}ab {p}ax',
            f'{p}a1 = OpIAdd %uint {p}a0 %mp_c1', f'{p}a2 = OpIAdd %uint {p}a0 %mp_c2', f'{p}a3 = OpIAdd %uint {p}a2 %mp_c1'] + \
           [f'{p}p{i} = OpAccessChain %_ptr_StorageBuffer_uint %mp_bp %uint_0 {p}a{i}' for i in range(4)]
def kept(p, x, y):
    """the vector kept for cell (x, y): {p}d0..3, and {p}ok when no word of it was cleared"""
    o = addr(p, x, y)
    for i in range(4):
        o += [f'{p}l{i} = OpLoad %uint {p}p{i}', f'{p}d{i} = OpBitwiseXor %uint {p}l{i} %mp_tag', f'{p}n{i} = OpINotEqual %bool {p}l{i} %mp_c0']
    if os.environ.get('MP_LEN'):      # probe: is the buffer, as the postpass sees it, at least this many bytes long?
        return o + [f'{p}al = OpArrayLength %uint %mp_bp 0', f'{p}ok = OpUGreaterThanEqual %bool {p}al %mp_len']
    if os.environ.get('MP_CACHE') == 'force':      # timing probe: as if nothing had been cleared
        return o + [f'{p}z0 = OpIEqual %bool {p}l0 %mp_c0', f'{p}ok = OpLogicalOr %bool {p}n0 {p}z0']
    return o + [f'{p}n01 = OpLogicalAnd %bool {p}n0 {p}n1', f'{p}n23 = OpLogicalAnd %bool {p}n2 {p}n3', f'{p}ok = OpLogicalAnd %bool {p}n01 {p}n23' if not NOCACHE else f'{p}ok = OpLogicalAnd %bool {p}n01 %mp_false']
def body(k, xs, ys):
    sub = {d: f'%mp{k}_{d[1:]}' for d in rdef} if k != '00' else {}
    sub[X] = xs; sub[Y] = ys
    o = []
    for l in region:
        if ' OpPhi ' in l:
            l = rn(l, lab, f'%mp_T{k}')
        o.append(re.sub(r'%\w+', lambda m: sub.get(m[0], m[0]), l))
    return o, [sub.get(w, w) for w in words], (sub.get(rlabels[-1], rlabels[-1]) if rlabels else f'%mp_T{k}')
# the postpass declares the working buffer read-only (in Direct3D terms it is bound as a shader resource; under vkd3d-proton
# it is an ordinary storage buffer): the declaration goes, so that the vectors can be kept in it
L = [('' if l.strip() == f'OpDecorate {SSBO} NonWritable' else l) for l in L]
out = L[:main] + c + L[main:at + 1] + head
# the thread's own cell: read back on a skipped frame; worked out and kept on a frame that runs (and where it was cleared)
b, bw, blast = body('00', '%mp_X0', '%mp_Y0')
out += ['OpSelectionMerge %mp_L00 None', 'OpBranchConditional %mp_skip %mp_C00 %mp_L00', '%mp_C00 = OpLabel'] + kept('%mp_k00', '%mp_X0', '%mp_Y0') + ['OpBranch %mp_L00', '%mp_L00 = OpLabel']
out += [f'%mp_h{i} = OpPhi %uint %mp_c0 {lab} %mp_k00d{i} %mp_C00' for i in range(4)] + [f'%mp_have = OpPhi %bool %mp_false {lab} %mp_k00ok %mp_C00']
if os.environ.get('MP_CACHE') == 'map':
    out += ['%mp_have2 = OpLogicalAnd %bool %mp_have %mp_false']
out += ['OpSelectionMerge %mp_M00 None', 'OpBranchConditional ' + ('%mp_have2' if os.environ.get('MP_CACHE') == 'map' else '%mp_have') + ' %mp_M00 %mp_T00', '%mp_T00 = OpLabel'] + b + addr('%mp_s', '%mp_X0', '%mp_Y0')
for i in range(4):
    out += [f'%mp_sv{i} = OpBitwiseXor %uint {bw[i]} %mp_tag'] + ([f'%mp_so{i} = OpLoad %uint %mp_sp{i}', f'%mp_sw{i} = OpSelect %uint %mp_skip %mp_so{i} %mp_sv{i}', f'OpStore %mp_sp{i} %mp_sw{i}'] if os.environ.get('MP_CACHE') == 'map' else [f'OpStore %mp_sp{i} %mp_sv{i}'])
if os.environ.get('MP_TESTSTORE'):      # probe: do the postpass's stores reach the buffer? (spoils the kept jitter)
    out += [f'%mp_tsr = OpIMul %uint {Y} %mp_row', f'%mp_tsx = OpShiftLeftLogical %uint {X} %mp_c2', '%mp_tsa = OpIAdd %uint %mp_tsr %mp_tsx', '%mp_tsp = OpAccessChain %_ptr_StorageBuffer_uint %mp_bp %uint_0 %mp_tsa', 'OpStore %mp_tsp %mp_tag']
out += ['OpBranch %mp_M00', '%mp_M00 = OpLabel']
W = {'00': [f'%mp_W00_{i}' for i in range(4)]}
out += [f'{W["00"][i]} = OpPhi %uint %mp_h{i} %mp_L00 {bw[i]} {blast}' for i in range(4)]
if os.environ.get('MP_CACHE') == 'map':      # probe: spoil the picture exactly where a kept vector came through whole
    out += kept('%mp_q', '%mp_X0', '%mp_Y0') + ([f'%mp_qe{i} = OpIEqual %bool %mp_qd{i} {W["00"][i]}' for i in range(4)] + ['%mp_qe01 = OpLogicalAnd %bool %mp_qe0 %mp_qe1', '%mp_qe23 = OpLogicalAnd %bool %mp_qe2 %mp_qe3', '%mp_qeq = OpLogicalAnd %bool %mp_qe01 %mp_qe23', '%mp_qs = OpLogicalAnd %bool %mp_qeq %mp_skip'] if os.environ.get('MP_MAPEQ') else ['%mp_qs = OpLogicalAnd %bool %mp_qok %mp_skip']) + [f'%mp_Q{i} = OpSelect %uint %mp_qs %mp_c0 {W["00"][i]}' for i in range(4)]
    W['00'] = [f'%mp_Q{i}' for i in range(4)]
if os.environ.get('MP_SPOILJ'):      # probe: on the one frame with this jitter x, spoil the picture where the kept vector had been cleared
    lo, hi = (float(v) for v in os.environ['MP_SPOILJ'].split(','))
    out += ['%mp_jpc = OpAccessChain %_ptr_PushConstant_v2uint %registers %uint_0', '%mp_jad = OpLoad %v2uint %mp_jpc', '%mp_jcb = OpBitcast %_ptr_PhysicalStorageBuffer_PhysicalPointerFloat4NonWriteCBVArray %mp_jad',
            '%mp_jfp = OpInBoundsAccessChain %_ptr_PhysicalStorageBuffer_v4float %mp_jcb %uint_0 %uint_1', '%mp_jf = OpLoad %v4float %mp_jfp Aligned 16', '%mp_jx = OpCompositeExtract %float %mp_jf 2',
            '%mp_j1 = OpFOrdGreaterThan %bool %mp_jx %mp_jlo', '%mp_j2 = OpFOrdLessThan %bool %mp_jx %mp_jhi', '%mp_j3 = OpLogicalAnd %bool %mp_j1 %mp_j2', '%mp_j4 = OpLogicalNot %bool %mp_have',
            '%mp_j5 = OpLogicalAnd %bool %mp_j3 %mp_j4', '%mp_j6 = OpLogicalAnd %bool %mp_j5 %mp_skip'] + [f'%mp_Q{i} = OpSelect %uint %mp_j6 %mp_c0 {W["00"][i]}' for i in range(4)]
    W['00'] = [f'%mp_Q{i}' for i in range(4)]
cur = '%mp_M00'
if os.environ.get('MP_PLANE', '1') == '1':
    # the plane the prepass of a skipped frame records "who was here a frame ago" in (frameskip.py): cleared by every frame that runs
    from frameskip_layout import plane_layout
    L_ = plane_layout(S)
    c_extra = [f'%mp_pb0 = OpConstant %uint {L_["pb0"]}', f'%mp_pb1 = OpConstant %uint {L_["pb1"]}']
    out[main:main] = c_extra
    out += [f'%mp_cxy = OpBitwiseOr %uint {X} {Y}', '%mp_cev = OpBitwiseAnd %uint %mp_cxy %mp_c1', '%mp_ce = OpIEqual %bool %mp_cev %mp_c0', '%mp_nsk = OpLogicalNot %bool %mp_skip',
            '%mp_cd = OpLogicalAnd %bool %mp_ce %mp_nsk', 'OpSelectionMerge %mp_CM None', 'OpBranchConditional %mp_cd %mp_CT %mp_CM', '%mp_CT = OpLabel',
            f'%mp_cxq = OpShiftRightLogical %uint {X} %mp_c1', f'%mp_cyq = OpShiftRightLogical %uint {Y} %mp_c1', '%mp_cyr = OpShiftRightLogical %uint %mp_cyq %mp_c1',
            '%mp_cyo = OpBitwiseAnd %uint %mp_cyq %mp_c1', '%mp_cyb = OpINotEqual %bool %mp_cyo %mp_c0', '%mp_cblk = OpSelect %uint %mp_cyb %mp_pb1 %mp_pb0',
            '%mp_crw = OpIMul %uint %mp_cyr %mp_row', '%mp_ca1 = OpIAdd %uint %mp_base %mp_crw', '%mp_ca2 = OpIAdd %uint %mp_ca1 %mp_cblk', '%mp_cidx = OpIAdd %uint %mp_ca2 %mp_cxq',
            '%mp_cp = OpAccessChain %_ptr_StorageBuffer_uint %mp_bp %uint_0 %mp_cidx', 'OpStore %mp_cp %mp_c0', 'OpBranch %mp_CM', '%mp_CM = OpLabel']
    cur = '%mp_CM'
for k, (xs, ys, cond) in (('10', ('%mp_X1', '%mp_Y0', '%mp_ox')), ('01', ('%mp_X0', '%mp_Y1', '%mp_oy')), ('11', ('%mp_X1', '%mp_Y1', '%mp_oxy'))):
    b, bw, blast = body(k, xs, ys)
    out += [f'OpSelectionMerge %mp_M{k} None', f'OpBranchConditional {cond} %mp_C{k} %mp_M{k}', f'%mp_C{k} = OpLabel'] + kept(f'%mp_k{k}', xs, ys)
    out += [f'OpSelectionMerge %mp_J{k} None', f'OpBranchConditional %mp_k{k}ok %mp_J{k} %mp_T{k}', f'%mp_T{k} = OpLabel'] + b + [f'OpBranch %mp_J{k}', f'%mp_J{k} = OpLabel']
    out += [f'%mp_v{k}_{i} = OpPhi %uint %mp_k{k}d{i} %mp_C{k} {bw[i]} {blast}' for i in range(4)] + [f'OpBranch %mp_M{k}', f'%mp_M{k} = OpLabel']
    W[k] = [f'%mp_W{k}_{i}' for i in range(4)]
    out += [f'{W[k][i]} = OpPhi %uint %mp_v{k}_{i} %mp_J{k} {W["00"][i]} {cur}' for i in range(4)]
    cur = f'%mp_M{k}'
out += tail
base_words = words; words = W['00']
# the vector each position's pixel code gets
sel = {}
for s in (0, 1):
    for t in (0, 1):
        sel[(s, t)] = []
        for i in range(4):
            if s == 0 and t == 0:
                out += [f'%mp_s00a{i} = OpSelect %uint %mp_oy {W["11"][i]} {W["10"][i]}', f'%mp_s00b{i} = OpSelect %uint %mp_oy {W["01"][i]} {words[i]}',
                        f'%mp_s00_{i} = OpSelect %uint %mp_ox %mp_s00a{i} %mp_s00b{i}']
                sel[(s, t)].append(f'%mp_s00_{i}')
            elif s == 1 and t == 0:
                out.append(f'%mp_s10_{i} = OpSelect %uint %mp_oy {W["01"][i]} {words[i]}'); sel[(s, t)].append(f'%mp_s10_{i}')
            elif s == 0 and t == 1:
                out.append(f'%mp_s01_{i} = OpSelect %uint %mp_ox {W["10"][i]} {words[i]}'); sel[(s, t)].append(f'%mp_s01_{i}')
            else:
                sel[(s, t)].append(words[i])
# the pixel each position's code writes
out += [f'%mp_bx = OpShiftLeftLogical %uint {X} %uint_1', f'%mp_by = OpShiftLeftLogical %uint {Y} %uint_1',
        f'{PX} = OpIAdd %uint %mp_bx %mp_rx', f'{PY} = OpIAdd %uint %mp_by %mp_ry']
rest = L[end + 2:]
# blocks of pixel code: three image writes each
blocks, b0, nw = [], 0, 0
for n, l in enumerate(rest):
    if 'OpImageWrite' in l:
        nw += 1
        if nw % 3 == 0 and nw < 12:
            blocks.append((b0, n + 1)); b0 = n + 1
blocks.append((b0, len(rest)))
if len(blocks) != 4:
    sys.exit(f'motionpost: {len(blocks)} blocks of pixel code found, expected 4')
alldefs = {m[1]: m[2] for l in L for m in [re.match(r'\s*(%\w+) = (.*)$', l)] if m}
xor = {}       # ids that mean "pixel column / row + 1"
for n, l in enumerate(rest):
    m = re.match(rf'(\s*)(%\w+) = OpBitwiseOr %uint ({re.escape(PX)}|{re.escape(PY)}) %uint_1$', l)
    if m:
        rest[n] = f'{m[1]}{m[2]} = OpIAdd %uint ' + ('%mp_bx %mp_nrx' if m[3] == PX else '%mp_by %mp_nry'); xor[m[2]] = m[3]
for (a, b) in blocks:
    w = next(l for l in rest[a:b] if 'OpImageWrite' in l).split()
    cc = re.match(r'OpCompositeConstruct %v2uint (%\w+) (%\w+)$', alldefs[w[2]]) or sys.exit('motionpost: pixel coordinates not found')
    s = 0 if cc[1] == PX else 1 if xor.get(cc[1]) == PX else sys.exit('motionpost: unknown pixel column'); t = 0 if cc[2] == PY else 1 if xor.get(cc[2]) == PY else sys.exit('motionpost: unknown pixel row')
    wsub = {base_words[i]: sel[(s, t)][i] for i in range(4)}
    for n in range(a, b):
        rest[n] = re.sub(r'%\w+', lambda m: wsub.get(m[0], m[0]), rest[n])
for n, l in enumerate(rest):
    if ' OpPhi ' in l and cur != (rlabels[-1] if rlabels else lab):
        rest[n] = rn(l, rlabels[-1] if rlabels else lab, cur)
sys.stdout.write('\n'.join(out + rest))
