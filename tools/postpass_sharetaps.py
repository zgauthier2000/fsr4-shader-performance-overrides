#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# postpass_sharetaps.py in.spvasm out.spvasm : postpass color taps computed once per thread. Bit-exact.
# Used by build_override.sh with SHARE=1 (off by default; unreleased: kept for the next release, user 2026-10-14). On an RX 7800 XT the postpass
# is about 6% faster (4K 0.632 -> 0.595 ms); it needs more registers (7800 XT 16 -> 12 waves, smaller register files 16 -> 8), and whether
# that costs more than it saves on those GPUs is not measured yet: timing kits time it against the shipped postpass.
# Each thread writes a 2x2 block of output pixels; each pixel reads a 3x3 window of the color input around
# its rounded center and converts every sample with max(log2(c*e*150 + 1) * k, 0). At upscale ratio >= 1 the
# four centers differ from pixel 0's by 0 or 1 per axis, so the four windows lie inside one 4x4 window.
# The 16 samples are fetched and converted once (same instructions as before); each tap then selects its
# converted value. The original fetches and conversions are left in place, unused (the compiler drops them).
# ST_CHECK=1: print what was found and stop.
import sys, re, os
L = open(sys.argv[1]).read().split('\n')
defs = {}
for i, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (\S+)(.*)', l)
    if m: defs[m.group(1)] = i
def tok(i): return L[defs[i]].split()
def op(i): return tok(i)[2] if i in defs else None
uses = {}
for i, l in enumerate(L):
    for t in re.findall(r'%[\w.]+', l)[1:] if ' = ' in l else re.findall(r'%[\w.]+', l):
        uses.setdefault(t, []).append(i)

def color_image(img):
    # OpLoad <- AccessChain table (registers[2] + 3)
    t = tok(img)
    if t[2] != 'OpLoad': return False
    ac = tok(t[4]); idx = ac[-1]
    if op(idx) != 'OpIAdd' or tok(idx)[-1] != '%uint_3': return False
    base = tok(idx)[4]
    return op(base) == 'OpLoad' and tok(tok(base)[4])[-1] == '%uint_2' and '%registers' in L[defs[tok(base)[4]]]

def clamp_parts(v):
    # SMin(SMax(c + d, 0), lim) -> (c, d, lim)
    t = tok(v); assert t[2] == 'OpExtInst' and t[5] == 'SMin', L[defs[v]]
    lim = t[7]; s = tok(t[6]); assert s[5] == 'SMax' and s[7] == '%uint_0', L[defs[t[6]]]
    a = s[6]
    if op(a) == 'OpIAdd' and tok(a)[5] in ('%uint_4294967295', '%uint_1'):
        return tok(a)[4], (-1 if tok(a)[5] == '%uint_4294967295' else 1), lim
    return a, 0, lim

PURE = {'OpFMul','OpFAdd','OpFSub','OpFDiv','OpExtInst','OpCompositeExtract','OpCompositeConstruct','OpBitcast','OpIAdd',
        'OpISub','OpIMul','OpSelect','OpFOrdLessThan','OpFOrdGreaterThan','OpFOrdLessThanEqual','OpFOrdGreaterThanEqual',
        'OpFOrdEqual','OpFConvert','OpConvertUToF','OpConvertSToF','OpInBoundsAccessChain','OpAccessChain','OpFNegate',
        'OpShiftLeftLogical','OpShiftRightLogical','OpBitwiseAnd','OpBitwiseOr','OpLogicalAnd','OpLogicalOr','OpLogicalNot'}
_canon = {}
def canon(x, F0):
    # value number of an id outside the slices: same number = same value for all pixels
    if x not in defs or x.startswith('%uint_') or x.startswith('%float_'): return x
    if x in _canon: return _canon[x]
    t = tok(x); o = t[2]
    if o in PURE or (o == 'OpLoad' and ('PhysicalStorageBuffer' in L[defs[t[4]]] or 'PushConstant' in L[defs[t[4]]])):
        r = (o, t[3]) + tuple(canon(y, F0) if y.startswith('%') else y for y in t[4:] if not y.startswith('Aligned') and not y.isdigit() or o == 'OpCompositeExtract')
    else: r = x
    _canon[x] = r; return r
def slice_of(f, F0):
    # forward slice of fetch f (in line order) through pure ops; other operands recorded by value number
    S = {f: ('FETCH',)}; order = [f]
    for i in range(defs[f] + 1, len(L)):
        t = L[i].split()
        if len(t) < 3 or t[1] != '=' or t[2] not in PURE: continue
        if not any(y in S for y in t[4:]): continue
        parts = tuple(S[y] if y in S else ('EXT', canon(y, F0)) if y.startswith('%') else y for y in t[4:])
        S[t[0]] = (t[2], t[3]) + parts; order.append(t[0])
    return S, order
fetches = [i for i, l in enumerate(L) if re.match(r'\s*%\S+ = OpImageFetch %v4float', l) and color_image(l.split()[4])]
assert len(fetches) == 36, len(fetches)
F0 = fetches[0]
secs = []
for s in range(4):
    taps = []
    for i in fetches[9 * s: 9 * s + 9]:
        t = L[i].split(); co = tok(t[5]); assert co[2] == 'OpCompositeConstruct'
        cx, dx, lx = clamp_parts(co[4]); cy, dy, ly = clamp_parts(co[5])
        S, order = slice_of(t[0], F0)
        taps.append(dict(line=i, img=t[4], cx=cx, dx=dx, lx=lx, cy=cy, dy=dy, ly=ly, S=S, order=order))
    for key in ('cx', 'cy', 'lx', 'ly'):
        assert len({canon(t[key], F0) for t in taps}) == 1, (s, key)
    assert sorted((t['dx'], t['dy']) for t in taps) == sorted((a, b) for a in (-1, 0, 1) for b in (-1, 0, 1))
    secs.append(taps)
alltaps = [t for s in secs for t in s]
shared = set.intersection(*[set(t['S'].values()) for t in alltaps])
outsig = None
for t in alltaps:
    sh = {v for v in t['order'] if t['S'][v] in shared}
    t['sh'] = [v for v in t['order'] if v in sh]
    outs = {}
    for v in t['sh']:
        if any(not (len(L[i].split()) > 2 and L[i].split()[1] == '=' and L[i].split()[0] in sh) for i in uses.get(v, [])):
            outs[t['S'][v]] = v
    t['outs'] = outs
    assert outsig in (None, set(outs)), 'outputs differ between taps'; outsig = set(outs)
t0 = secs[0][0]
nconv = len(t0['sh']) - 1
if os.environ.get('ST_CHECK'):
    print('shared conversion instructions per tap', nconv, 'outputs', len(outsig))
    for v in t0['sh']: print('   ', L[defs[v]].strip())
    for n, s in enumerate(secs): print(n, s[0]['cx'], s[0]['cy'], s[0]['lx'], s[0]['ly'], s[0]['img'])
    sys.exit()

X0, Y0, LX, LY, IMG = t0['cx'], t0['cy'], t0['lx'], t0['ly'], t0['img']
# insertion point: before the first output definition anywhere, after every value the cloned code needs
P = min(defs[v] for t in alltaps for v in t['outs'].values())
need = [X0, Y0, LX, LY, IMG]
for v in t0['sh'][1:]:
    need += [y for y in L[defs[v]].split()[4:] if y.startswith('%') and y in defs and y not in t0['S'] and defs[y] > 50]
need = [y for y in need if not re.match(r'%(uint|float|int|bool)_', y) and y != '%1']
late = [y for y in need if defs[y] >= P]
assert not late, ('needed after insertion point', late)
assert not any('OpLabel' in L[i] for i in range(F0, P)), 'insertion point not in the first block'
ins, after = {}, {}
w = []
off = {-1: '%uint_4294967295', 1: '%uint_1', 2: '%uint_2'}
for c0, lim, nm in [(X0, LX, 'x'), (Y0, LY, 'y')]:
    for d in (-1, 0, 1, 2):
        v = c0
        if d: w.append(f'%st_{nm}a{d + 1} = OpIAdd %uint {c0} {off[d]}'); v = f'%st_{nm}a{d + 1}'
        w.append(f'%st_{nm}b{d + 1} = OpExtInst %uint %1 SMax {v} %uint_0')
        w.append(f'%st_{nm}{d + 1} = OpExtInst %uint %1 SMin %st_{nm}b{d + 1} {lim}')
clone = {}
for i in range(4):
    for j in range(4):
        p = f'%st_{i}{j}'
        m = {t0['sh'][0]: p + '_f'}
        w.append(f'{p}_c = OpCompositeConstruct %v2uint %st_x{i} %st_y{j}')
        w.append(f'{p}_f = OpImageFetch %v4float {IMG} {p}_c Lod %uint_0')
        for v in t0['sh'][1:]:
            m[v] = p + '_' + v[1:]
            t = L[defs[v]].split()
            w.append(' '.join([m[v], '='] + [m.get(y, y) for y in t[2:]]))
        for sig, v in t0['outs'].items(): clone[(i, j, sig)] = m[v]
ins[P] = w
rename = {}
for n, taps in enumerate(secs):
    if n:
        ins.setdefault(taps[0]['line'], []).extend([
            f'%st_ox{n} = OpISub %uint {taps[0]["cx"]} {X0}', f'%st_oy{n} = OpISub %uint {taps[0]["cy"]} {Y0}',
            f'%st_zx{n} = OpIEqual %bool %st_ox{n} %uint_0', f'%st_zy{n} = OpIEqual %bool %st_oy{n} %uint_0'])
    for t in taps:
        i0, j0 = t['dx'] + 1, t['dy'] + 1
        for k, (sig, nid) in enumerate(t['outs'].items()):
            ty = L[defs[nid]].split()[3]
            rename[nid] = nid.replace('%', '%st_dead_')
            if n == 0:
                sel = [f'{nid} = OpCopyObject {ty} {clone[(i0, j0, sig)]}']
            else:
                b = f'%st_s{n}_{i0}{j0}_{k}'
                sel = [f'{b}r0 = OpSelect {ty} %st_zy{n} {clone[(i0, j0, sig)]} {clone[(i0, j0 + 1, sig)]}',
                       f'{b}r1 = OpSelect {ty} %st_zy{n} {clone[(i0 + 1, j0, sig)]} {clone[(i0 + 1, j0 + 1, sig)]}',
                       (f'{nid} = OpSelect {ty} %st_zx{n} {b}r1 {b}r0' if os.environ.get('ST_BREAK') else f'{nid} = OpSelect {ty} %st_zx{n} {b}r0 {b}r1')]
            after[defs[nid]] = sel
out = []
for i, l in enumerate(L):
    if i in ins: out += ['       ' + x for x in ins[i]]
    sp = l.split()
    if len(sp) > 1 and sp[1] == '=' and sp[0] in rename: l = l.replace(sp[0], rename[sp[0]], 1)
    out.append(l)
    if i in after: out += ['       ' + x for x in after[i]]
open(sys.argv[2], 'w').write('\n'.join(out))
print('sections', len(secs), 'conversion instructions per tap', nconv, 'outputs', len(outsig), file=sys.stderr)
