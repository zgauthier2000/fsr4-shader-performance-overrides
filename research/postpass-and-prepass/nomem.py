#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Fusion ceiling probe for the FSR 4.1.1 model passes (vkd3d-proton SPIR-V text).
#   nomem.py st|ld|both < passN.spvasm > out.spvasm
# st:   every store to a storage buffer runs only when its value equals 0x9E3779B9, so all the
#       arithmetic stays but (practically) nothing is written.
# ld:   loads from storage buffers whose index depends on the thread ID get their index masked
#       to the first 16384 elements, so the same instructions run but hit the caches.
#       Image versions for the prepass and postpass: image writes are guarded the same way (on
#       the texel's first channel), image fetches get their coordinates masked to a 64x64 tile
#       and samples get theirs scaled into the top-left corner.
# Output is garbage; this measures what the intermediate tensors' memory traffic costs.
import re
import sys

mode = sys.argv[1]
import os
ONLY = os.environ.get('NOMEM_ONLY', '')   # 'img' or 'buf': guard only image writes / only buffer stores
L = sys.stdin.read().split('\n')


def split_headers(L, sbstore):
    """A loop header block that contains a store gets its body moved into a block of its own,
    so the store can be put under a selection. Self-continuing headers get a continue block."""
    out, i, k, fix = [], 0, 0, {}
    while i < len(L):
        m = re.match(r'\s*(%\S+) = OpLabel', L[i])
        if not m:
            out.append(L[i]); i += 1; continue
        j = i + 1
        while not re.match(r'\s*Op(Branch|BranchConditional|Switch|Return|ReturnValue|Unreachable|Kill)\b', L[j]):
            j += 1
        blk = L[i:j + 1]
        lm = [x for x in blk if 'OpLoopMerge' in x]
        if not lm or not any(sbstore(x) for x in blk):
            out += blk; i = j + 1; continue
        H = m[1]; k += 1; B, C2 = f'%nmb{k}', f'%nmc{k}'
        merge, cont, ctrl = re.match(r'\s*OpLoopMerge (%\S+) (%\S+) (.*)', lm[0]).groups()
        selfc = cont == H
        phis = [x for x in blk[1:] if 'OpPhi' in x]
        body = [x for x in blk[1:-1] if 'OpPhi' not in x and 'OpLoopMerge' not in x]
        term = blk[-1]
        if selfc:
            phis = [re.sub(re.escape(H) + r'(?=\s|$)', C2, x) for x in phis]
            term = re.sub(re.escape(H) + r'(?=\s|$)', C2, term)
        out += [blk[0]] + phis + [f'               OpLoopMerge {merge} {C2 if selfc else cont} {ctrl}',
                                  f'               OpBranch {B}', f'{B} = OpLabel'] + body + [term]
        if selfc:
            out += [f'{C2} = OpLabel', f'               OpBranch {H}']
        fix[H] = B
        i = j + 1
    # phis outside the header that named it as predecessor now come from the body block
    res = []
    for x in out:
        if 'OpPhi' in x:
            for h, b in fix.items():
                x = re.sub(re.escape(h) + r'(?=\s|$)', b, x)
        res.append(x)
    return res


# --- storage buffer variables and pointers derived from them
sb = set()
for l in L:
    m = re.match(r'\s*(%\S+) = OpVariable \S+ StorageBuffer', l)
    if m:
        sb.add(m[1])
chains = {}  # pointer id -> (base, indices)
for l in L:
    m = re.match(r'\s*(%\S+) = OpAccessChain \S+ (%\S+)(.*)', l)
    if m and (m[2] in sb or m[2] in chains):
        sb.add(m[1])
        chains[m[1]] = (m[2], m[3].split())

if mode in ('st', 'both'):
    L = split_headers(L, lambda x: 'OpImageWrite' in x or
                      (lambda m: bool(m) and m[1] in sb)(re.match(r'\s*OpStore (%\S+)', x)))
# --- taint: values depending on the thread ID (through SSA and Function variables)
taint = set(re.findall(r'%gl_\w+', '\n'.join(l for l in L if 'OpEntryPoint' in l)))
changed = True
while changed:
    changed = False
    for l in L:
        m = re.match(r'\s*(%\S+) = Op\w+ (.*)', l)
        if m:
            if m[1] not in taint and any(t in taint for t in re.findall(r'%\S+', m[2])):
                taint.add(m[1])
                changed = True
            continue
        m = re.match(r'\s*OpStore (%\S+) (%\S+)', l)
        if m and m[2] in taint:
            # mark the variable behind the pointer
            p = m[1]
            for l2 in L:
                m2 = re.match(r'\s*' + re.escape(p) + r' = OpAccessChain \S+ (%\S+)', l2)
                if m2:
                    p = m2[1]
                    break
            if p not in taint:
                taint.add(p)
                changed = True

# Roots of the thread-dependent load indices: follow "x + constant" back to x, so that the
# per-load constant offsets stay foldable into the load instructions.
defs = {}
for l in L:
    m = re.match(r'\s*(%\S+) = (Op\w+) (\S+) (.*)', l)
    if m:
        defs[m[1]] = (m[2], m[3], m[4].split())
isconst = lambda v: defs.get(v, ('',))[0] == 'OpConstant'
roots = set()
for l in L:
    m = re.match(r'\s*%\S+ = OpAccessChain \S+ (%\S+) (.*)', l)
    if m and m[1] in chains:
        v = m[2].split()[-1]
        if v not in taint:
            continue
        while defs.get(v, ('',))[0] == 'OpIAdd' and any(isconst(a) for a in defs[v][2]):
            v = next(a for a in defs[v][2] if not isconst(a))
        if defs.get(v, ('', ''))[1] == '%uint' and defs[v][0] not in ('OpPhi', 'OpLoad'):
            roots.add(v)
out = []
n = [0]


def new():
    n[0] += 1
    return f'%nm{n[0]}'


masked = stores = 0
func_started = False
const_added = False
block = None
pending_phi_fix = {}   # old block label -> new label (the one ending the old block)
for i, l in enumerate(L):
    s = l.strip()
    if not const_added and re.match(r'\s*%\S+ = OpFunction ', l):
        out += ['%nm_mask = OpConstant %uint 16383', '%nm_magic = OpConstant %uint 2654435769']
        if any('OpImage' in x for x in L):
            out += ['%nm_fmagic = OpConstant %float 1234567.25', '%nm_m63 = OpConstant %uint 63',
                    '%nm_mask2 = OpConstantComposite %v2uint %nm_m63 %nm_m63']
        if any(re.match(r'\s*%v2float = OpTypeVector', x) for x in L):
            out += ['%nm_f = OpConstant %float 0.015625', '%nm_scale2 = OpConstantComposite %v2float %nm_f %nm_f']
        const_added = True
    m = re.match(r'(%\S+) = OpLabel', s)
    if m:
        block = m[1]
    if mode in ('ld', 'both'):
        m = re.match(r'(\s*)(%\S+) = (Op\w+) (%uint) (.*)', l)
        if m and m[2] in roots:
            # rename the original, then define the root as its masked value
            o = m[2] + '_o'
            out.append(f'{m[1]}{o} = {m[3]} {m[4]} {m[5]}')
            out.append(f'{m[1]}{m[2]} = OpBitwiseAnd %uint {o} %nm_mask')
            masked += 1
            continue
        m = re.match(r'(\s*)(%\S+) = (OpImageFetch|OpImageSampleExplicitLod) (\S+) (%\S+) (%\S+) (.*)', l)
        if m:
            t = new()
            op = 'OpBitwiseAnd %v2uint' if m[3] == 'OpImageFetch' else 'OpFMul %v2float'
            k = '%nm_mask2' if m[3] == 'OpImageFetch' else '%nm_scale2'
            out += [f'{m[1]}{t} = {op} {m[6]} {k}', f'{m[1]}{m[2]} = {m[3]} {m[4]} {m[5]} {t} {m[7]}']
            masked += 1
            continue
    if mode in ('st', 'both'):
        m = re.match(r'(\s*)OpImageWrite (%\S+) (%\S+) (%\S+)(.*)', l)
        if m and ONLY != 'buf':
            x, c, T, M = new(), new(), new(), new()
            out += [f'{m[1]}{x} = OpCompositeExtract %float {m[4]} 0',
                    f'{m[1]}{c} = OpFOrdEqual %bool {x} %nm_fmagic',
                    f'{m[1]}OpSelectionMerge {M} None',
                    f'{m[1]}OpBranchConditional {c} {T} {M}',
                    f'{T} = OpLabel', l, f'{m[1]}OpBranch {M}', f'{M} = OpLabel']
            pending_phi_fix[block] = M
            block = M
            stores += 1
            continue
        m = re.match(r'(\s*)OpStore (%\S+) (%\S+)(.*)', l)
        if m and m[2] in sb and ONLY != 'img':
            # value must be a uint scalar; compare it with the magic constant
            c, T, M = new(), new(), new()
            out += [f'{m[1]}{c} = OpIEqual %bool {m[3]} %nm_magic',
                    f'{m[1]}OpSelectionMerge {M} None',
                    f'{m[1]}OpBranchConditional {c} {T} {M}',
                    f'{T} = OpLabel', l, f'{m[1]}OpBranch {M}', f'{M} = OpLabel']
            pending_phi_fix[block] = M
            block = M
            stores += 1
            continue
    out.append(l)

# The rest of a split block now ends in the new label: fix phis naming the old block.
if pending_phi_fix:
    res = []
    for l in out:
        if 'OpPhi' in l:
            for old, new_ in pending_phi_fix.items():
                l = re.sub(re.escape(old) + r'(?=\s|$)', new_, l)
        res.append(l)
    out = res
if not any(re.match(r'\s*%bool = OpTypeBool', l) for l in out):
    out = [('%bool = OpTypeBool\n' + l) if l.strip().startswith('%nm_mask =') else l for l in out]
print('\n'.join(out))
print(f'nomem: masked {masked} loads, guarded {stores} stores', file=sys.stderr)
