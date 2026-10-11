#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# prepass_route.py < prepass.spvasm > out.spvasm      (AMD's prepass, or one already rewritten by prepass_gather.py)
#
# Bit-exact. The prepass's last step is a 2x2-stride convolution: the four threads of a quad (one
# render pixel each) each work out their share x of 16 output channels, the quad's shares are added
# up with two exchanges per channel (32 in all), and the quad's first thread rounds, packs and
# stores all 16 channels (four words).
#
# Here each thread finishes one of the four words instead. A thread at position p of the quad
# works out the same 16 shares, but grouped by whose word they belong to: its own (B), its
# horizontal neighbor's (A), its vertical neighbor's (D) and the diagonal one's (C). Then
#     word(p) = (swapH(A) + B) + swapV(swapH(C) + D)
# which is 12 exchanges instead of 32, and the rounding, packing and storing are spread over the
# four threads (4 channels each) instead of sitting on one. The sums are the same additions in the
# same grouping as AMD's ((x_h + x_own) + (x_diagonal + x_vertical), up to the order of the two
# operands of an addition), so the result is the same bits.
# The idea is from a community member's shader set (see research/community-lossy-set); this is an
# independent implementation from AMD's shader.
import re, sys
L = sys.stdin.read().split('\n')
die = lambda m: sys.exit(f'prepass_route: {m}')
name = lambda l: (re.match(r'\s*(%\w+) = ', l) or [None, None])[1]
defs = {name(l): l.strip() for l in L if name(l)}
GLSL = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpExtInstImport "GLSL.std.450"', l)] if m)
# the 16 channels: x, swapH(x), x + that, swapV of the sum
sw = []
for n, l in enumerate(L):
    m = re.match(r'\s*(%\w+) = OpGroupNonUniformQuadSwap %float (%\w+) (%\w+) %uint_0$', l)
    if m:
        a = re.match(rf'\s*(%\w+) = OpFAdd %float {re.escape(m[1])} {re.escape(m[3])}$', L[n + 1]) or die('unexpected sum after a horizontal exchange')
        b = re.match(rf'\s*(%\w+) = OpGroupNonUniformQuadSwap %float {re.escape(m[2])} {re.escape(a[1])} %uint_1$', L[n + 2]) or die('unexpected vertical exchange')
        sw.append(dict(n=n, x=m[3], s=a[1], v=b[1], scope=m[2]))
if len(sw) != 16:
    die(f'{len(sw)} channel sums found, expected 16')
SCOPE = sw[0]['scope']


def block(k):
    """lines of channel k's share, from where its weights' offset is formed to its last product"""
    lines = L[sw[k - 1]['n'] + 3:sw[k]['n']]
    sh = next((m for l in lines for m in [re.match(r'\s*%\w+ = OpShiftRightLogical %uint (%\w+) %uint_2$', l)] if m), None) or die('no weight offset in a channel')
    return lines, sh[1]


def norm(lines, off, drop):
    """the block with its own ids numbered in order, its offset called OFF, and the lines that only form the offset left out"""
    ren, out = {off: 'OFF'}, []
    for l in lines:
        if name(l) in drop:
            continue
        if name(l):
            ren[name(l)] = f'T{len(ren)}'
        out.append(re.sub(r'%\w+', lambda t: ren.get(t[0], t[0]), l.strip()))
    return out


lines1, off1 = block(1)
m = re.match(rf'{re.escape(off1)} = OpIAdd %uint (%\w+) %uint_(\d+)$', defs[off1]) or die('unexpected offset of channel 1')
BASE, STEP = m[1], int(m[2])
T = norm(lines1, off1, {off1})
for k in range(2, 16):
    lk, ok = block(k)
    a = re.match(rf'{re.escape(ok)} = OpIAdd %uint {re.escape(BASE)} (%\w+)$', defs[ok]) or re.match(rf'{re.escape(ok)} = OpIAdd %uint (%\w+) {re.escape(BASE)}$', defs[ok]) or die(f'unexpected offset of channel {k}')
    mul = re.match(rf'{re.escape(a[1])} = OpIMul %uint %uint_{STEP} %uint_{k}$', defs.get(a[1], ''))
    if not (mul or a[1] == f'%uint_{STEP * k}'):
        die(f'channel {k} is not at {STEP} x {k}')
    if norm(lk, ok, {ok, a[1]}) != T:
        die(f'channel {k} is not built like channel 1')
if T[-1].split(' = ')[0] != f'T{len([t for t in T if " = " in t])}' or not re.match(r'T\d+ = OpFDot2MixAcc32VALVE', T[-1]):
    die('a channel does not end in its last product')
# channel 0 uses the base itself and has no offset line
n0 = sw[0]['n'] - len(T)
if norm(L[n0:sw[0]['n']], BASE, set()) != T:
    die('channel 0 is not built like channel 1')
# the part only the quad's first thread runs: the totals, the biases, rounding, packing, four stores
cn = sw[15]['n'] + 3
pm = re.match(rf'\s*(%\w+) = OpBitwiseAnd %uint (%\w+) %uint_3$', L[cn]) or die('quad position not where expected')
POS = pm[1]
if not (re.match(rf'\s*(%\w+) = OpIEqual %bool {re.escape(POS)} %uint_0$', L[cn + 1]) and 'OpSelectionMerge' in L[cn + 2]):
    die('the first-thread test is not where expected')
MERGE = L[cn + 2].split()[1]
bc = re.match(r'\s*OpBranchConditional %\w+ (%\w+) (%\w+)$', L[cn + 3]) or die('no branch after the first-thread test')
if bc[2] != MERGE:
    die('unexpected shape of the first-thread branch')
t0 = cn + 5
t1 = next(n for n in range(t0, len(L)) if re.match(rf'\s*OpBranch {re.escape(MERGE)}$', L[n]))
tail = L[t0:t1]
tdef = {name(l): n for n, l in enumerate(tail) if name(l)}
stores = [m for l in tail for m in [re.match(r'\s*OpStore (%\w+) (%\w+)$', l)] if m]
if len(stores) != 4:
    die(f'{len(stores)} stores found, expected 4')
p0 = re.match(r'(%\w+) = OpAccessChain (%\w+) (%\w+) %uint_0 (%\w+)$', defs[stores[0][1]]) or die('unexpected store address')
for i in (1, 2, 3):
    pi = re.match(rf'%\w+ = OpAccessChain {re.escape(p0[2])} {re.escape(p0[3])} %uint_0 (%\w+)$', defs[stores[i][1]]) or die('unexpected store address')
    if not re.match(rf'{re.escape(pi[1])} = OpIAdd %uint {re.escape(p0[4])} %uint_{i}$', defs[pi[1]]):
        die('the four words are not stored side by side')
bias = [m for l in tail for m in [re.match(r'\s*(%\w+) = OpAccessChain (%\w+) (%\w+) %uint_0 %uint_(\d+)$', l)] if m and 'v4uint' in m[2]]
if len(bias) != 4 or [int(b[4]) for b in bias] != [int(bias[0][4]) + i for i in range(4)]:
    die('unexpected bias loads')
cl = next((m for l in tail for m in [re.match(rf'\s*%\w+ = OpExtInst %v4int {re.escape(GLSL)} SClamp %\w+ (%\w+) (%\w+)$', l)] if m), None) or die('no clamp in the tail')
# word 0's code must be the usual one: total + bias, times 64, round to even, to int, clamp, pack
if len(re.findall(r'OpFMul %float %\w+ %float_64', '\n'.join(tail))) != 16 or len(re.findall('RoundEven', '\n'.join(tail))) != 16:
    die('unexpected rounding code in the tail')


def needs(ids):
    """the tail's lines that the given ids depend on, in order"""
    want, todo = set(), list(ids)
    while todo:
        i = todo.pop()
        if i in tdef and tdef[i] not in want:
            want.add(tdef[i]); todo += re.findall(r'%\w+', tail[tdef[i]].split(' = ', 1)[1])
    return [tail[n] for n in sorted(want)]


P = '        '
out = L[:n0]
out += [f'{P}%rt_p = OpBitwiseAnd %uint {pm[2]} %uint_3', f'{P}%rt_c1 = OpBitwiseXor %uint %rt_p %uint_1', f'{P}%rt_c2 = OpBitwiseXor %uint %rt_p %uint_2', f'{P}%rt_c3 = OpBitwiseXor %uint %rt_p %uint_3']
consts = [f'%rt_k{STEP * 4} = OpConstant %uint {STEP * 4}'] + [f'%rt_j{STEP * j} = OpConstant %uint {STEP * j}' for j in range(1, 4)]
X = {}
for r, wid in (('B', '%rt_p'), ('A', '%rt_c1'), ('D', '%rt_c2'), ('C', '%rt_c3')):
    out += [f'{P}%rt_w{r} = OpIMul %uint {wid} %rt_k{STEP * 4}', f'{P}%rt_o{r}0 = OpIAdd %uint {BASE} %rt_w{r}'] + [f'{P}%rt_o{r}{j} = OpIAdd %uint %rt_o{r}0 %rt_j{STEP * j}' for j in range(1, 4)]
    for j in range(4):
        sub = lambda t: f'%rt_o{r}{j}' if t[0] == 'OFF' else f'%rt_{r}{j}_{t[0][1:]}'
        code = [re.sub(r'\b(OFF|T\d+)\b', sub, l) for l in T]
        out += [P + c for c in code]; X[r, j] = code[-1].split(' = ')[0]
tot = []
for j in range(4):
    out += [f'{P}%rt_ha{j} = OpGroupNonUniformQuadSwap %float {SCOPE} {X["A", j]} %uint_0', f'{P}%rt_s1{j} = OpFAdd %float %rt_ha{j} {X["B", j]}',
            f'{P}%rt_hc{j} = OpGroupNonUniformQuadSwap %float {SCOPE} {X["C", j]} %uint_0', f'{P}%rt_s2{j} = OpFAdd %float %rt_hc{j} {X["D", j]}']
for j in range(4):
    out += [f'{P}%rt_v{j} = OpGroupNonUniformQuadSwap %float {SCOPE} %rt_s2{j} %uint_1', f'{P}%rt_t{j} = OpFAdd %float %rt_s1{j} %rt_v{j}']
    tot.append(f'%rt_t{j}')
# every thread finishes its own word
out += [f'{P}OpBranch {bc[1]}', L[cn + 4]] + needs([bias[0][3], p0[3], p0[4]])
out += [f'{P}%rt_bi = OpIAdd %uint %uint_{bias[0][4]} %rt_p', f'{P}%rt_bp = OpAccessChain {bias[0][2]} {bias[0][3]} %uint_0 %rt_bi', f'{P}%rt_bv = OpLoad %v4uint %rt_bp']
for j in range(4):
    out += [f'{P}%rt_bu{j} = OpCompositeExtract %uint %rt_bv {j}', f'{P}%rt_bf{j} = OpBitcast %float %rt_bu{j}', f'{P}%rt_a{j} = OpFAdd %float {tot[j]} %rt_bf{j}',
            f'{P}%rt_m{j} = OpFMul %float %rt_a{j} %float_64', f'{P}%rt_r{j} = OpExtInst %float {GLSL} RoundEven %rt_m{j}', f'{P}%rt_i{j} = OpConvertFToS %uint %rt_r{j}']
out += [f'{P}%rt_vec = OpCompositeConstruct %v4uint %rt_i0 %rt_i1 %rt_i2 %rt_i3', f'{P}%rt_cl = OpExtInst %v4int {GLSL} SClamp %rt_vec {cl[1]} {cl[2]}', f'{P}%rt_uc = OpUConvert %v4uchar %rt_cl',
        f'{P}%rt_word = OpBitcast %uint %rt_uc', f'{P}%rt_sa = OpIAdd %uint {p0[4]} %rt_p', f'{P}%rt_sp = OpAccessChain {p0[2]} {p0[3]} %uint_0 %rt_sa', f'{P}OpStore %rt_sp %rt_word']
out += L[t1:]
# channel order inside a word: AMD's word 0 holds channels 0..3 in that order
first = re.search(r'OpCompositeConstruct %v4uint (%\w+) (%\w+) (%\w+) (%\w+)', '\n'.join(tail))
main = next(n for n, l in enumerate(out) if '= OpFunction' in l)
out[main:main] = [c for c in consts if c.split(' = ')[0] not in defs]
for c in ('%uint_1', '%uint_2', '%uint_3', '%float_64', f'%uint_{bias[0][4]}'):
    if c not in defs:
        die(f'{c} is not a constant of this shader')
sys.stdout.write('\n'.join(out))
