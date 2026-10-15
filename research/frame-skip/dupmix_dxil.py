#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# dupmix_dxil.py < skipblend_dxil.py output (SB_RANGEPRE=1 SB_RANGEAT=1 SB_ROWS=1) > out (internal build, unreleased) : the DXIL form of dupmix.py (DM_END=last). For each of the four pixels the stretch
# from the first to the last running min / max of the nine samples runs twice: frames that run the network take the shader's own lines, skipped frames a copy
# with the min / max; values used later meet in phis. Same output; network frames do not pay for the min / max.
import re, sys
L = sys.stdin.read().split('\n')
RNG = re.compile(r'^\s*%sb\.q[nx]\d(\d)\.\d+ = ')
DEF = re.compile(r'^\s*(%[\w.]+) = (.*)$')
LAB = re.compile(r'^([\w.]+):\s*(;.*)?$|^; <label>:(\d+)')
FLAGS = {'fast', 'nnan', 'ninf', 'nsz', 'arcp', 'contract', 'afn', 'reassoc', 'nuw', 'nsw', 'exact'}
EXT = {'%dx.types.ResRet.f16': ['half'] * 4 + ['i32'], '%dx.types.ResRet.f32': ['float'] * 4 + ['i32'], '%dx.types.ResRet.i32': ['i32'] * 5,
       '%dx.types.CBufRet.f32': ['float'] * 4, '%dx.types.CBufRet.i32': ['i32'] * 4, '%dx.types.CBufRet.f16': ['half'] * 8, '%dx.types.Dimensions': ['i32'] * 4}
def ty(rhs):
    t = rhs.split(); op = t[0]
    if op in ('fadd', 'fsub', 'fmul', 'fdiv', 'frem', 'add', 'sub', 'mul', 'and', 'or', 'xor', 'shl', 'lshr', 'ashr', 'udiv', 'sdiv', 'urem', 'srem'):
        return next(x for x in t[1:] if x not in FLAGS)
    if op in ('icmp', 'fcmp'): return 'i1'
    if op == 'select': return re.match(r'select i1 [^,]+, (\S+) ', rhs)[1]
    if op in ('call', 'phi'): return t[1]
    if op == 'load': return t[1].rstrip(',')
    if op in ('fpext', 'fptrunc', 'sitofp', 'uitofp', 'fptosi', 'fptoui', 'bitcast', 'zext', 'sext', 'trunc'): return re.search(r' to (\S+)', rhs)[1]
    if op == 'extractvalue':
        m = re.match(r'extractvalue (\S+) [^,]+, (\d+)', rhs); return EXT[m[1]][int(m[2])]
    sys.exit(f'dupmix_dxil: type of "{rhs[:80]}" unknown')
def label_of(i):
    for j in range(i, -1, -1):
        m = LAB.match(L[j])
        if m: return '%' + (m[1] or m[3])
    sys.exit('dupmix_dxil: no block label found')
def newname(x, suf):
    return f'%dm.{x[1:]}.{suf}' if x[1].isdigit() else f'{x}.{suf}'
sub = lambda l, mp: re.sub(r'%[\w.]+', lambda q: mp.get(q[0], q[0]), l)
for k in '0123':
    idx = [i for i, l in enumerate(L) if RNG.match(l) and RNG.match(l)[1] == k]
    if not idx: sys.exit(f'dupmix_dxil: no min / max lines for pixel {k}')
    s, b = idx[0], idx[-1] + 1
    if __import__('os').environ.get('DM_END') == 'branch':      # copy up to the skipped-frame branch: the paths meet where the code is split anyway
        b = next(i for i in range(b, len(L)) if L[i].strip() == f'br i1 %sb.skip, label %sb.T{k}, label %sb.M{k}')
    if any(LAB.match(L[i]) or re.match(r'\s*(br|ret|switch) ', L[i]) for i in range(s, b)):
        sys.exit(f'dupmix_dxil: the stretch of pixel {k} is not one block')
    lab0 = label_of(s)
    R = [l for l in L[s:b] if l.strip()]
    dl = {DEF.match(l)[1]: l for l in R if DEF.match(l)}
    need = set(); todo = []      # numbered values must stay in order, so nothing is moved out: handles are copied too (and must not be used after the stretch)
    while todo:
        x = todo.pop()
        if x in need: continue
        need.add(x); todo += [o for o in re.findall(r'%[\w.]+', DEF.match(dl[x])[2]) if o in dl]
    if any(RNG.match(dl[x]) for x in need): sys.exit('dupmix_dxil: a shared line depends on the min / max')
    pre = [l for l in R if DEF.match(l) and DEF.match(l)[1] in need]
    R = [l for l in R if not (DEF.match(l) and DEF.match(l)[1] in need)]
    net = [l for l in R if not RNG.match(l)]
    dR = [DEF.match(l)[1] for l in R if DEF.match(l)]
    ren = {x: newname(x, 'ds') for x in dR}
    skip = [sub(l, ren) for l in R]
    rest = '\n'.join(L[b:])
    used = [x for x in dR if re.search(rf'{re.escape(x)}(?![\w.])', rest)]
    rng = {DEF.match(l)[1] for l in R if RNG.match(l)}
    phis = []; mrg = {}; remade = []
    for x in used:
        t = ty(DEF.match(dl[x])[2])
        if t == '%dx.types.Handle' and all(o not in dl for o in re.findall(r'%[\w.]+', DEF.match(dl[x])[2])):
            m = newname(x, 'dm'); remade.append(f'  {m} = {DEF.match(dl[x])[2]}'); mrg[x] = m; continue      # a handle cannot pass a phi: made again after the paths meet
        if t.startswith('%') or t.endswith('*'): sys.exit(f'dupmix_dxil: an aggregate is used after the stretch: {dl[x].strip()[:80]}')
        m = newname(x, 'dm')
        phis.append(f'  {m} = phi {t} [ {ren[x]}, %dm.S{k} ], [ {"undef" if x in rng else x}, %dm.N{k} ]'); mrg[x] = m
    tail = []
    for l in L[b:]:
        l2 = sub(l, mrg)
        if re.match(r'\s*%[\w.]+ = phi ', l2):
            l2 = re.sub(rf'{re.escape(lab0)} \]', f'%dm.M{k} ]', l2)
        tail.append(l2)
    L = L[:s] + pre + [f'  br i1 %sb.skip, label %dm.S{k}, label %dm.N{k}', '', f'dm.S{k}:'] + skip + [f'  br label %dm.M{k}', '', f'dm.N{k}:'] + net + [
        f'  br label %dm.M{k}', '', f'dm.M{k}:'] + phis + remade + tail
    print(f'dupmix_dxil: pixel {k}: {len(R)} lines, {len(R) - len(net)} min / max, {len(pre)} kept shared, {len(phis)} phis', file=sys.stderr)
print('\n'.join(L))
