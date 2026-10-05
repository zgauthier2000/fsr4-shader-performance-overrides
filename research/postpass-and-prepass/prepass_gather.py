#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Rewrites the FSR 4.1.1 (INT8) prepass as dumped by vkd3d-proton so that each lane of a quad
# computes and stores one of the four words of the model's input tensor on its own.
#
#   spirv-dis <hash>.spv | prepass_gather.py > out.spvasm ; spirv-as --target-env spv1.3
#
# AMD's shader: every lane (pixel of a 2x2 quad) forms 16 channel sums d = dot(its 7 features, its
# weights), 4 dot-product instructions each; two quad swaps and two adds per channel turn them into
# (d_own + d_horizontal) + (d_vertical + d_diagonal), the same in all four lanes; then lane 0 alone
# adds the bias, scales, rounds, clamps and stores all 16 channels as four words.
# Here every lane first fetches the other three pixels' features (12 quad swaps instead of 32) and
# then, for the four channels of "its" word only, computes the four d's itself, with the same
# instructions in the same order, and adds them in the same grouping. That is the same arithmetic
# on the same numbers, so the result is intended to be bit-exact; the lane then finishes and
# stores its word. A pixel's weights sit at 512*y + 16*x + 32*channel, so a neighbour's weights
# are at the lane's own address with bit 4 (x) or bit 9 (y) flipped.
# (prepass_quad.py, the first version, only shared the last step.)
#
# Each quad of lanes (a 2x2 block of pixels) reduces 16 channel sums with quad swaps; then only
# lane 0 of the quad turns them into four words of four int8 values each (add the bias, scale,
# round, clamp, pack) and stores the words, while the other three lanes of the quad idle. The
# reduction leaves the same sums in all four lanes (each lane adds the same two values, and float
# addition is commutative), so here every lane computes one of the four words, with the same
# operations, and stores it. The quantisation runs once per lane instead of four times in a
# quarter of the lanes, and the quad writes its 16 bytes with one store. The output is bit-exact.
import re
import sys

lines = sys.stdin.read().split('\n')


def die(msg):
    sys.exit(f'prepass_gather: {msg}')


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


new_consts = {}
def uconst(v):
    name = f'%uint_{v}'
    if name not in defs and name not in new_consts:
        new_consts[name] = v
    return name


def operands(v, opname):
    t = tokens(v)
    return t[2:] if t and t[0] == opname else None


def is_swap(v, direction, of=None):
    t = tokens(v)
    return bool(t and t[0] == 'OpGroupNonUniformQuadSwap' and t[4] == f'%uint_{direction}' and (of is None or t[3] == of))


def total_parts(v):
    """v = (d + swapH(d)) + swapV(d + swapH(d))  ->  d, or None"""
    o = operands(v, 'OpFAdd')
    if not o:
        return None
    for s1, sv in ((o[0], o[1]), (o[1], o[0])):
        if is_swap(sv, 1, s1):
            p = operands(s1, 'OpFAdd')
            if p:
                for d, sh in ((p[0], p[1]), (p[1], p[0])):
                    if is_swap(sh, 0, d):
                        return d
    return None


def chain_info(d):
    """the dot-product chain ending in d -> (weight buffer, address, [feature vectors], zero)"""
    feats, v, word0 = [], d, None
    while True:
        o = operands(v, 'OpFDot2MixAcc32VALVE')
        if not o:
            die('unexpected dot-product chain')
        feats.insert(0, o[1]); wv = o[0]; acc = o[2]
        if not operands(acc, 'OpFDot2MixAcc32VALVE'):
            zero = acc; break
        v = acc
    h0 = operands(wv, 'OpCompositeConstruct')[0]
    e0 = operands(h0, 'OpBitcast')[0]
    vv = operands(e0, 'OpCompositeExtract')[0]
    word = operands(vv, 'OpBitcast')[0]
    vec = operands(word, 'OpCompositeExtract')[0]
    l0 = operands(vec, 'OpCompositeConstruct')[0]
    ptr = operands(l0, 'OpLoad')[0]
    ac = operands(ptr, 'OpAccessChain')
    addr = operands(ac[2], 'OpShiftRightLogical')[0]
    return ac[0], addr, feats, zero


gather = {}          # filled on first use: base address, buffer, features of the four pixels
def gathered_total(ds):
    """the channel sum of this lane's word, from the four words' sums ds"""
    infos = [chain_info(d) for d in ds]
    if not gather:
        buf, base, feats, zero = infos[0]
        a = operands(base, 'OpIAdd')
        if a and any(c in defs and defs[c].startswith('OpConstant %uint') for c in a):
            die('the first channel does not use the base address')
        gather.update(buf=buf, base=base, feats=feats, zero=zero)
    offs = []
    for buf, addr, feats, zero in infos:
        if addr == gather['base']:
            offs.append(0)
        else:
            a = operands(addr, 'OpIAdd')
            c = [x for x in a if x != gather['base']] if a and gather['base'] in a else None
            def const_value(v):            # a constant, or a product of two constants
                m = re.match(r'OpConstant %uint (\d+)$', defs.get(v, ''))
                if m:
                    return int(m[1])
                p = operands(v, 'OpIMul')
                if p and const_value(p[0]) is not None and const_value(p[1]) is not None:
                    return const_value(p[0]) * const_value(p[1])
                return None
            val = const_value(c[0]) if c else None
            if val is None:
                die('unexpected weight address')
            offs.append(val)
    off = uconst(offs[0])
    for k in (1, 2, 3):
        s_ = new(); out_code.append(f'{s_} = OpSelect %uint %qd_is{k} {uconst(offs[k])} {off}'); off = s_
    ds_ = []
    for P in range(4):
        addr, idx = new(), new()
        out_code.append(f'{addr} = OpIAdd %uint %gt_base{P} {off}')
        out_code.append(f'{idx} = OpShiftRightLogical %uint {addr} {uconst(2)}')
        acc = gather['zero']
        for w in range(4):
            i2, p_, l_, h_, r_ = new(), new(), new(), new(), new()
            out_code.append(f'{i2} = OpIAdd %uint {idx} {uconst(w)}')
            out_code.append(f'{p_} = OpAccessChain %_ptr_StorageBuffer_uint {gather["buf"]} {uconst(0)} {i2}')
            out_code.append(f'{l_} = OpLoad %uint {p_}')
            out_code.append(f'{h_} = OpBitcast %v2half {l_}')
            out_code.append(f'{r_} = OpFDot2MixAcc32VALVE %float {h_} %gt_f{P}_{w} {acc}')
            acc = r_
        ds_.append(acc)
    a, b, r = new(), new(), new()
    out_code.append(f'{a} = OpFAdd %float {ds_[0]} {ds_[1]}')
    out_code.append(f'{b} = OpFAdd %float {ds_[2]} {ds_[3]}')
    out_code.append(f'{r} = OpFAdd %float {a} {b}')
    return r


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
            ds = [total_parts(o) for o in ops]
            if all(ds):
                args.append(gathered_total(ds))
                continue
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
if not gather:
    die('the channel sums were not found')
# the other three pixels' features and weight addresses, fetched where AMD's first quad swap is
first_swap = next(i for i, l in enumerate(lines) if 'OpGroupNonUniformQuadSwap' in l)
scope = lines[first_swap].split()[4]
gcode = [f'%gt_base0 = OpCopyObject %uint {gather["base"]}',
         f'%gt_base1 = OpBitwiseXor %uint {gather["base"]} {uconst(16)}',
         f'%gt_base2 = OpBitwiseXor %uint {gather["base"]} {uconst(512)}',
         f'%gt_base3 = OpBitwiseXor %uint {gather["base"]} {uconst(528)}']
for w, f in enumerate(gather['feats']):
    gcode.append(f'%gt_f0_{w} = OpCopyObject %v2half {f}')
    gcode.append(f'%gt_p{w} = OpBitcast %uint {f}')
    for P in (1, 2, 3):
        gcode.append(f'%gt_s{P}_{w} = OpGroupNonUniformQuadSwap %uint {scope} %gt_p{w} {uconst(P - 1)}')
        gcode.append(f'%gt_f{P}_{w} = OpBitcast %v2half %gt_s{P}_{w}')
pre = [f'%qd_is{k} = OpIEqual %bool {q} %uint_{k}' for k in (1, 2, 3)]
idx, ptr = new(), new()
store = [f'{idx} = OpIAdd %uint {base} {q}', f'{ptr} = OpAccessChain {ptr_t} {buf} {zero} {idx}',
         f'OpStore {ptr} {word}']

pad = '               '
res = []
for i, l in enumerate(lines):
    if i == first_swap:
        res += [pad + c for c in gcode]
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
if new_consts:
    at = max(i for i, l in enumerate(res) if re.match(r'\s*%\S+ = OpConstant %uint ', l))
    res[at] += ''.join(f'\n{k} = OpConstant %uint {v}' for k, v in new_consts.items())
print('\n'.join(res))
