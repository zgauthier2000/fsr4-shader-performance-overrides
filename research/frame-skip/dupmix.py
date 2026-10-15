#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# dupmix.py < skipblend.py output (SB_RANGEPRE=1 SB_RANGEAT=1 SB_ROWS=1 SB_RANGESET=minmax) > out (internal build, unreleased; DM_END=last is the tested form) : for each of the four pixels, the stretch from the first running min / max of the
# nine samples up to the skipped-frame branch is split in two: frames that run the network take the shader's own lines (without the min / max), skipped
# frames a copy with them. Values used later meet in phis. Output unchanged; network frames no longer pay for the min / max.
# DM_HOIST=1: lines of the stretch that depend on nothing in it and are not arithmetic on samples (descriptor loads, image fetches) stay shared, before the split.
import re, sys, os
L = sys.stdin.read().split('\n')
RNG = re.compile(r'^\s*%sb_q[nx]\d(\d)_\d+ = ')
defre = re.compile(r'^\s*(%\w+) = (Op\w+)(?: (%\w+))?')
types = {}
for l in L:
    m = re.match(r'\s*(%\w+) = (OpType\w+)', l)
    if m: types[m[1]] = m[2]
handle = {t for t, k in types.items() if k in ('OpTypeImage', 'OpTypeSampledImage', 'OpTypeSampler', 'OpTypePointer')}
fl = next(t for t, k in types.items() if k == 'OpTypeFloat' and re.search(rf'^\s*{re.escape(t)} = OpTypeFloat 32$', '\n'.join(L), re.M))
HOIST = os.environ.get('DM_HOIST', '0') == '1'
extra_decl = []; undefs = {}
def undef(t):
    if t not in undefs:
        undefs[t] = f'%dm_undef{len(undefs)}'; extra_decl.append(f'{undefs[t]} = OpUndef {t}')
    return undefs[t]
for k in '0123':
    b = next(i for i, l in enumerate(L) if l.strip() == f'OpSelectionMerge %sb_M{k} None')
    s = next(i for i, l in enumerate(L) if RNG.match(l) and RNG.match(l)[1] == k)
    if os.environ.get('DM_END') == 'last':      # copy only up to the last min / max line; the rest of the stretch stays shared, after the paths meet
        b = max(i for i, l in enumerate(L) if i < b and RNG.match(l) and RNG.match(l)[1] == k) + 1
    if any(re.search(r'= OpLabel|^\s*Op(Branch|Return|Selection|Loop)', L[i]) for i in range(s, b)):
        sys.exit(f'dupmix: the stretch of pixel {k} is not one block')
    lab0 = next(re.match(r'\s*(%\w+) = OpLabel', L[i])[1] for i in range(s, -1, -1) if re.match(r'\s*%\w+ = OpLabel', L[i]))
    R = L[s:b]; pre = []
    defs_R = {}
    for l in R:
        m = defre.match(l)
        if m: defs_R[m[1]] = (m[2], m[3])
    # lines that must or may stay shared: handles (no phis of images allowed) and, with DM_HOIST, fetches; only if they need nothing from the stretch
    keep = []; moved = set()
    # handles and everything they need from the stretch (descriptor index arithmetic) stay shared
    need = set(); dl = {defre.match(l)[1]: l for l in R if defre.match(l)}
    todo = [x for x, l in dl.items() if defre.match(l)[3] in handle or (HOIST and defre.match(l)[2] in ('OpImageFetch', 'OpImageSampleExplicitLod', 'OpImageRead'))]
    while todo:
        x = todo.pop()
        if x in need: continue
        need.add(x); todo += [o for o in re.findall(r'%\w+', dl[x].split(' = ', 1)[1]) if o in dl]
    if any(RNG.match(dl[x]) for x in need):
        sys.exit('dupmix: a shared line depends on the min / max')
    for l in R:
        m = defre.match(l)
        if m and m[1] in need:
            pre.append(l); moved.add(m[1])
        else:
            keep.append(l)
    R = keep
    net = [l for l in R if not RNG.match(l)]
    dR = [defre.match(l)[1] for l in R if defre.match(l) and defre.match(l)[1] not in moved]
    ren = {x: f'{x}_ds' for x in dR}
    sub = lambda l, mp: re.sub(r'%\w+', lambda q: mp.get(q[0], q[0]), l)
    skip = [sub(l, ren) for l in R]
    rest = '\n'.join(L[b:])
    used = [x for x in dR if re.search(rf'{re.escape(x)}(?!\w)', rest)]
    rng_ids = {defre.match(l)[1] for l in R if RNG.match(l)}
    phis = []; mrg = {}
    for x in used:
        t = defs_R[x][1]
        nv = undef(t) if x in rng_ids else x
        phis.append(f'{x}_dm = OpPhi {t} {x}_ds %dm_S{k} {nv} %dm_N{k}'); mrg[x] = f'{x}_dm'
    mrg[lab0] = f'%dm_M{k}'
    tail = []
    for l in L[b:]:
        if ' OpPhi ' in l:
            tail.append(sub(l, mrg))
        else:
            tail.append(sub(l, {a: c for a, c in mrg.items() if a != lab0}))
    L = L[:s] + pre + [f'OpSelectionMerge %dm_M{k} None', f'OpBranchConditional %sb_skip %dm_S{k} %dm_N{k}', f'%dm_S{k} = OpLabel'] + skip + [f'OpBranch %dm_M{k}',
         f'%dm_N{k} = OpLabel'] + net + [f'OpBranch %dm_M{k}', f'%dm_M{k} = OpLabel'] + phis + tail
    print(f'dupmix: pixel {k}: {len(R)} lines in the stretch, {len(R) - len(net)} min / max, {len(pre)} kept shared, {len(phis)} phis', file=sys.stderr)
fn = next(i for i, l in enumerate(L) if re.match(r'\s*%\w+ = OpFunction ', l))
L = L[:fn] + extra_decl + L[fn:]
print('\n'.join(L))
