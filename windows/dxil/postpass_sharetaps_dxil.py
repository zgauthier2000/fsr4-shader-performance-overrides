#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# postpass_sharetaps_dxil.py < postpass.ll > out.ll : DXIL twin of tools/postpass_sharetaps.py (build_dxil_overrides.sh SHARE=1, the default since release dll-2026-10-15) (postpass color taps converted once per thread).
# Each thread writes a 2x2 block of output pixels; each pixel reads a 3x3 window of the color input (t3) around its rounded
# center and converts every sample. At upscale ratio >= 1 the four windows lie inside one 4x4 window: its 16 samples are
# loaded and converted once (the same instructions, copied under new names) and every tap's converted values are replaced,
# in the instructions that use them, by a choice among them. The original loads and conversions stay in place unused
# (numbered values are never deleted; dce_dxil.py removes them). ST_CHECK=1: print what was found and stop.
import sys, re, os
L = sys.stdin.read().split('\n')
defs = {}
for i, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = ', l)
    if m: defs[m.group(1)] = i
def ids(s): return re.findall(r'%[\w.]+', s)
uses = {}
for i, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = (.*)', l)
    for t in ids(m.group(2).split(';')[0] if m else l.split(';')[0]):
        uses.setdefault(t, []).append(i)
def body(x): return L[defs[x]].split(' = ', 1)[1].split('  ;')[0].strip()

# the color input: textureLoad.f32 on a Texture2D<3xF32> annotated from the t3 binding
def color_handle(h):
    if h not in defs or 'annotateHandle' not in L[defs[h]] or 'Texture2D<3xF32>' not in L[defs[h]]: return False
    base = re.search(r'%dx\.types\.Handle (%[\w.]+)', body(h)).group(1)
    return 'createHandleFromBinding' in L[defs[base]] and 'i32 3, i32 3, i32 0, i8 0' in L[defs[base]]
fetches = []
for i, l in enumerate(L):
    m = re.match(r'\s*(%[\w.]+) = call %dx\.types\.ResRet\.f32 @dx\.op\.textureLoad\.f32\(i32 66, %dx\.types\.Handle (%[\w.]+), i32 0, i32 (%[\w.]+), i32 (%[\w.]+),', l)
    if m and color_handle(m.group(2)): fetches.append((i, m.group(1), m.group(2), m.group(3), m.group(4)))
assert len(fetches) == 36, len(fetches)
F0 = fetches[0][0]

PURE = re.compile(r'^(fmul|fadd|fsub|fdiv|add|sub|mul|shl|lshr|and|or|xor|select|fcmp|icmp|extractvalue|uitofp|sitofp|fptosi|fptoui|bitcast|'
                  r'call float @dx\.op\.(unary|binary|tertiary)\.f32|call i32 @dx\.op\.(unary|binary|tertiary)\.i32|'
                  r'call %dx\.types\.CBufRet\.\w+ @dx\.op\.cbufferLoadLegacy|call %dx\.types\.Handle @dx\.op\.annotateHandle)')
_canon = {}
def canon(x):
    # value number: same number = same value for every pixel of the thread
    if not x.startswith('%') or x not in defs: return x
    if x in _canon: return _canon[x]
    b = body(x)
    if PURE.match(b): r = (re.sub(r'%[\w.]+', '%', b),) + tuple(canon(y) for y in ids(b))
    else: r = x
    _canon[x] = r; return r
def clamp_parts(v):
    # IMin(IMax(c + d, 0), lim) -> (c, d, lim)
    m = re.match(r'call i32 @dx\.op\.binary\.i32\(i32 38, i32 (%[\w.]+), i32 (%[\w.]+)\)', body(v)); assert m, body(v)
    n = re.match(r'call i32 @dx\.op\.binary\.i32\(i32 37, i32 (%[\w.]+), i32 0\)', body(m.group(1))); assert n, body(m.group(1))
    a = n.group(1); k = re.match(r'add i32 (%[\w.]+), (-?1)$', body(a)) if a in defs else None
    return (k.group(1), int(k.group(2)), m.group(2)) if k else (a, 0, m.group(2))
def slice_of(f):
    S = {f: ('FETCH',)}; order = [f]
    for i in range(defs[f] + 1, len(L)):
        m = re.match(r'\s*(%[\w.]+) = (.*)', L[i])
        if not m: continue
        b = m.group(2).split('  ;')[0].strip()
        if not PURE.match(b) or not any(y in S for y in ids(b)): continue
        S[m.group(1)] = (re.sub(r'%[\w.]+', '%', b),) + tuple(S[y] if y in S else ('EXT', canon(y)) for y in ids(b)); order.append(m.group(1))
    return S, order

secs = []
for s in range(4):
    taps = []
    for i, f, h, xc, yc in fetches[9 * s: 9 * s + 9]:
        cx, dx, lx = clamp_parts(xc); cy, dy, ly = clamp_parts(yc)
        S, order = slice_of(f)
        taps.append(dict(line=i, f=f, h=h, cx=cx, dx=dx, lx=lx, cy=cy, dy=dy, ly=ly, S=S, order=order))
    for key in ('cx', 'cy', 'lx', 'ly'): assert len({canon(t[key]) for t in taps}) == 1, (s, key)
    assert sorted((t['dx'], t['dy']) for t in taps) == sorted((a, b) for a in (-1, 0, 1) for b in (-1, 0, 1))
    secs.append(taps)
alltaps = [t for s in secs for t in s]
shared = set.intersection(*[set(t['S'].values()) for t in alltaps])
outsig = None
for t in alltaps:
    sh = [v for v in t['order'] if t['S'][v] in shared]; shs = set(sh); t['sh'] = sh; outs = {}
    for v in sh:
        cons = [i for i in uses.get(v, []) if not (re.match(r'\s*(%[\w.]+) = ', L[i]) and re.match(r'\s*(%[\w.]+) = ', L[i]).group(1) in shs)]
        if cons: outs[t['S'][v]] = (v, cons)
    t['outs'] = outs
    assert outsig in (None, set(outs)), 'outputs differ between taps'; outsig = set(outs)
t0 = secs[0][0]
if os.environ.get('ST_CHECK'):
    print('conversion instructions per tap', len(t0['sh']) - 1, 'outputs', len(outsig), file=sys.stderr)
    for v in t0['sh']: print('   ', L[defs[v]].strip()[:150], file=sys.stderr)
    sys.exit(0)

X0, Y0, LX, LY, H = t0['cx'], t0['cy'], t0['lx'], t0['ly'], t0['h']
P = min(defs[v] for t in alltaps for v, _ in t['outs'].values())
need = [X0, Y0, LX, LY, H] + [y for v in t0['sh'][1:] for y in ids(body(v)) if y not in t0['S']]
late = [y for y in need if y in defs and defs[y] >= P]
assert not late, ('needed after the insertion point', late)
assert not any(re.match(r'; <label>:|\w+:', L[i]) for i in range(F0, P)), 'insertion point not in the first block'
w = []
for c0, lim, nm in [(X0, LX, 'x'), (Y0, LY, 'y')]:
    for d in (-1, 0, 1, 2):
        v = c0
        if d: w.append(f'%st_{nm}a{d + 1} = add i32 {c0}, {d}'); v = f'%st_{nm}a{d + 1}'
        w.append(f'%st_{nm}b{d + 1} = call i32 @dx.op.binary.i32(i32 37, i32 {v}, i32 0)')
        w.append(f'%st_{nm}{d + 1} = call i32 @dx.op.binary.i32(i32 38, i32 %st_{nm}b{d + 1}, i32 {lim})')
clone = {}
for i in range(4):
    for j in range(4):
        p = f'%st_{i}{j}'; m = {t0['f']: p + '_f'}
        w.append(f'{p}_f = call %dx.types.ResRet.f32 @dx.op.textureLoad.f32(i32 66, %dx.types.Handle {H}, i32 0, i32 %st_x{i}, i32 %st_y{j}, i32 undef, i32 undef, i32 undef, i32 undef)')
        for v in t0['sh'][1:]:
            m[v] = p + '_' + v[1:]
            w.append(m[v] + ' = ' + re.sub(r'%[\w.]+', lambda q: m.get(q.group(0), q.group(0)), body(v)))
        for sig, (v, _) in t0['outs'].items(): clone[(i, j, sig)] = m[v]
ins = {P: w}; after = {}; subst = {}      # subst: line -> {old id: new id}
def tyof(v):
    b = body(v)
    if b.startswith('extractvalue'): return re.search(r'ResRet\.(\w+)', b).group(1).replace('f32', 'float').replace('f16', 'half')
    if b.startswith('call float') or b.split()[0] in ('fmul', 'fadd', 'fsub', 'fdiv') or b.startswith('select'): return 'float' if ' float ' in ' ' + b + ' ' else 'i32'
    if b.split()[0] in ('uitofp', 'sitofp'): return b.split()[-1]
    raise ValueError(b)
for n, taps in enumerate(secs):
    if n:
        ins.setdefault(taps[0]['line'], []).extend([
            f'%st_ox{n} = sub i32 {taps[0]["cx"]}, {X0}', f'%st_oy{n} = sub i32 {taps[0]["cy"]}, {Y0}',
            f'%st_zx{n} = icmp eq i32 %st_ox{n}, 0', f'%st_zy{n} = icmp eq i32 %st_oy{n}, 0'])
    for t in taps:
        i0, j0 = t['dx'] + 1, t['dy'] + 1
        for k, (sig, (nid, cons)) in enumerate(t['outs'].items()):
            ty = tyof(nid); assert ty == 'float', (nid, body(nid))
            if n == 0: new = clone[(i0, j0, sig)]
            else:
                b = f'%st_s{n}_{i0}{j0}_{k}'; new = b
                sel = [f'{b}r0 = select i1 %st_zy{n}, float {clone[(i0, j0, sig)]}, float {clone[(i0, j0 + 1, sig)]}',
                       f'{b}r1 = select i1 %st_zy{n}, float {clone[(i0 + 1, j0, sig)]}, float {clone[(i0 + 1, j0 + 1, sig)]}',
                       f'{b} = select i1 %st_zx{n}, float {b}r0, float {b}r1']
                after.setdefault(defs[nid], []).extend(sel)
            for i in cons:
                assert i > defs[nid] and (n == 0 or i > defs[nid])
                subst.setdefault(i, {})[nid] = new
out = []
for i, l in enumerate(L):
    if i in ins: out += ['  ' + x for x in ins[i]]
    if i in subst:
        m = re.match(r'(\s*%[\w.]+ = )(.*)', l)
        head, rest = (m.group(1), m.group(2)) if m else ('', l)
        code, _, comment = rest.partition('  ;')
        code = re.sub(r'%[\w.]+', lambda q: subst[i].get(q.group(0), q.group(0)), code)
        l = head + code + ('  ;' + comment if comment else '')
    out.append(l)
    if i in after: out += ['  ' + x for x in after[i]]
sys.stdout.write('\n'.join(out))
print(f'sharetaps_dxil: 36 taps, {len(t0["sh"]) - 1} conversion instructions per tap, {len(outsig)} outputs', file=sys.stderr)
