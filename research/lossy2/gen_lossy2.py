#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# gen_lossy2.py <weights_lossy2.npz> <prebuilt-lossy folder> <out folder> [--hlsl <dir>]
#
# Builds the lossy2 Linux folder: the lossy folder with network passes 1, 2, 4, 5, 10 and 12 replaced by shaders written from the integer
# weights in weights_lossy2.npz (trained weights; the other six passes, the prepass, the postpass and Ultra Performance stay lossy's), for all
# three output-size classes (up to 1080p, up to 4K, above 4K). Each pass is written as GLSL in the layout of AMD's 4K-class pass (the
# generator of this project's student-network work, gen_net.py, without its weight readers), with lossy's frame-skip check at entry; the other
# size classes are the same GLSL with the buffer-layout literals rewritten (row bytes, tensor offsets, bounds, the frame-skip mark), only on
# the lines that hold them; then glslangValidator. The result must equal ../../prebuilt-lossy2 file for file (build_lossy2.sh checks it).
# --hlsl <dir>: also writes each of the 18 shaders as HLSL for the Windows DLL (to_hlsl.py), named after the DLL hash of the shader it replaces.
# Needs numpy and glslangValidator; no PyTorch.
import sys, os, re, shutil, subprocess, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
HDR = os.path.join(HERE, 'header.glsl')      # declarations as spirv-cross writes them for AMD's pass 1 under vkd3d-proton
LV = {1: (30752, 0, 1920, 1080), 2: (15392, 8342464, 960, 540), 3: (7712, 2097664, 480, 270)}      # 4K class: row bytes, plane size, width, height
RB = {1: dict(s1=7, s2=8, a=0.015625, b=0.000244140625, c=64.0, inp=0, out=33273664),
      2: dict(s1=8, s2=7, a=0.015625, b=0.000244140625, c=32.0, inp=33273664, out=0),
      12: dict(s1=7, s2=8, a=0.03125, b=0.00048828125, c=16.0, inp=49958592, out=0)}
MID = {4: dict(S1=7, S2=8, IA=(0.015625, 0.015625), B=6.103515625e-05, C=(64.0, 32.0), IN=33273664, OUT=49958592),
       5: dict(S1=8, S2=8, IA=(0.015625, 0.03125), B=0.0001220703125, C=(32.0, 32.0), IN=49958592, OUT=33273664),
       10: dict(S1=8, S2=7, IA=(0.0625, 0.0625), B=0.00048828125, C=(16.0, 16.0), IN=58349248, OUT=33273664)}
def cfg(k):
    if k in (1, 2, 12):
        P = RB[k]
        return dict(lv=1, n=1, G=1, IN=P['inp'], OUT=P['out'], S1=P['s1'], S2=P['s2'], IA=[P['a']] * 16, B=P['b'], C=[P['c']] * 16, vs=k + 1)
    P = MID[k]
    return dict(lv=2, n=2, G=1, IN=P['IN'], OUT=P['OUT'], S1=P['S1'], S2=P['S2'], IA=[P['IA'][0]] * 16 + [P['IA'][1]] * 16, B=P['B'],
                C=[P['C'][0]] * 16 + [P['C'][1]] * 16, vs=k + 1)

def pack(v): v = [int(t) & 255 for t in v]; return f'{v[0] | v[1] << 8 | v[2] << 16 | v[3] << 24}u'
def rsh(e, s): return f'(int(({e}) + {(1 << (s - 1)) - 1}u + ((({e}) >> {s}u) & 1u)) >> {s})'
def dot(acc, ws, rows):
    """acc literal + sum of sdot(word, packed row bytes)"""
    return f'{int(acc) & 0xffffffff}u + ' + ' + '.join(f'spvSDot_uint_uint_uint({w}, {pack(r)}, 0)' for w, r in zip(ws, rows))
def cvt(xe, ia, se, b, c):
    return f'uint(int16_t(uint16_t(int16_t(roundEven(((float({xe}) * {ia!r}) + (float(int({se})) * {b!r})) * {c!r})))))'
def loop(o, name, ins, rows, bias, post, gs=4):
    """o += a loop over groups of 4 outputs: acc = bias + sum sdot(ins[w], rows[oc][w]); post(g, accs) -> statements using the 4 sums"""
    n, nw = len(rows), len(ins); assert n % gs == 0
    o.append(f'    uint W{name}[{n * nw}] = uint[](' + ', '.join(pack(r[w]) for r in rows for w in range(nw)) + ');')
    o.append(f'    uint B{name}[{n}] = uint[](' + ', '.join(f'{int(b) & 0xffffffff}u' for b in bias) + ');')
    o.append(f'    for (uint g = 0u; g < {n // gs}u + gl_WorkGroupID.z; g++)\n    {{')
    for j in range(gs):
        o.append(f'        uint v{j} = B{name}[{gs}u * g + {j}u] + ' + ' + '.join(f'spvSDot_uint_uint_uint({x}, W{name}[({gs}u * g + {j}u) * {nw}u + {w}u], 0)' for w, x in enumerate(ins)) + ';')
    o += ['        ' + t for t in post('g', [f'v{j}' for j in range(gs)])]
    o.append('    }')
def gen(k, Wt):
    Q = cfg(k); n, G = Q['n'], Q['G']; R, PL, WD, HT = LV[Q['lv']]
    A, bA, Bw, bB, Cw, bC = (np.asarray(Wt[m]).astype(np.int64) for m in ('A', 'bA', 'Bw', 'bB', 'Cw', 'bC'))
    c1, h = A.shape[0] // G, Bw.shape[0]
    assert c1 % 4 == 0 and h % 4 == 0 and A.shape[1] == 16 and Bw.shape[1] == G * c1 + 16 * (n - G) and Cw.shape == (16 * n, h)
    U = '_26[registers._m1 + 11u]._m0'; X = 'xyzw'; U4 = '_27[registers._m1 + 11u]._m0'
    LP = os.environ.get('LOOP', 'BC' if k in (7, 8, 9) else '')
    o = [open(HDR).read().split('void main()')[0].replace('} _26[];\n', '} _26[];\n\nlayout(set = 2, binding = 0, std430) buffer SSBO4w\n{\n    uvec4 _m0[];\n} _27[];\n', 1) + 'void main()\n{', '    uint x = gl_GlobalInvocationID.x, y = gl_GlobalInvocationID.y;',
         f'    if (x > {WD - 1}u || y > {HT - 1}u) return;', f'    uint ib = {Q["IN"]}u + {R}u * y + 16u * x;']
    for g in range(G):
        for t in range(9):
            o.append(f'    uvec4 t{g}_{t} = uvec4(' + ', '.join(f'{U}[(ib + {PL * g + R * (t // 3) + 16 * (t % 3) + 4 * w}u) >> 2u]' for w in range(4)) + ');')
    ctr = lambda p: f't{p}_4' if p < G else f'p{p}'
    for p in range(G, n):
        o.append(f'    uvec4 p{p} = uvec4(' + ', '.join(f'{U}[(ib + {PL * p + R + 16 + 4 * w}u) >> 2u]' for w in range(4)) + ');')
    xw = []
    for g in range(G):
        tin = [f't{g}_{t}.{X[w]}' for t in range(9) for w in range(4)]
        rows = [[A[g * c1 + c, 4 * w:4 * w + 4, t // 3, t % 3] for t in range(9) for w in range(4)] for c in range(c1)]
        if 'A' in LP:
            o.append(f'    uint qa{g}[{c1 // 4}];')
            loop(o, f'A{g}', tin, rows, bA[g * c1:(g + 1) * c1],
                 lambda gi, v: [f'qa{g}[{gi}] = pack32(u8vec4(clamp(ivec4(' + ', '.join(rsh(e, Q['S1']) for e in v) + '), ivec4(-128), ivec4(127))));'])
            xw += [f'qa{g}[{q}]' for q in range(c1 // 4)]; continue
        for c in range(c1):
            o.append(f'    uint a{g * c1 + c} = ' + dot(bA[g * c1 + c], tin, rows[c]) + ';')
        for q in range(c1 // 4):
            o.append(f'    uint q{g}_{q} = pack32(u8vec4(clamp(ivec4(' + ', '.join(rsh(f'a{g * c1 + 4 * q + j}', Q['S1']) for j in range(4)) +
                     '), ivec4(-128), ivec4(127))));'); xw.append(f'q{g}_{q}')
    xw += [f'p{p}.{X[w]}' for p in range(G, n) for w in range(4)]
    if 'B' in LP:
        o.append(f'    uint ra[{h // 4}];')
        loop(o, 'B', xw, [[Bw[c, 4 * g:4 * g + 4] for g in range(len(xw))] for c in range(h)], bB,
             lambda gi, v: [f'ra[{gi}] = pack32(u8vec4(min(ivec4(' + ', '.join(rsh(f'uint(max(int({e}), 0))', Q['S2']) for e in v) + '), ivec4(127))));'])
        rw = [f'ra[{g}]' for g in range(h // 4)]
    else:
        for c in range(h):
            o.append(f'    uint b{c} = uint(max(int(' + dot(bB[c], xw, [Bw[c, 4 * g:4 * g + 4] for g in range(len(xw))]) + '), 0));')
        for g in range(h // 4):
            o.append(f'    uint r{g} = pack32(u8vec4(min(ivec4(' + ', '.join(rsh(f'b{4 * g + j}', Q['S2']) for j in range(4)) + '), ivec4(127))));')
        rw = [f'r{g}' for g in range(h // 4)]
    if 'C' in LP:
        o.append(f'    uint sa[{16 * n}];')
        loop(o, 'C', rw, [[Cw[c, 4 * g:4 * g + 4] for g in range(h // 4)] for c in range(16 * n)], bC,
             lambda gi, v: [f'sa[4u * {gi} + {j}u] = {e};' for j, e in enumerate(v)])
        sv = lambda c: f'sa[{c}]'
    else:
        for c in range(16 * n):
            o.append(f'    uint s{c} = ' + dot(bC[c], rw, [Cw[c, 4 * g:4 * g + 4] for g in range(h // 4)]) + ';')
        sv = lambda c: f's{c}'
    for p in range(n):
        for w in range(4):
            o.append(f'    ivec4 c{p}{w} = ivec4(i8vec4(unpack8({ctr(p)}.{X[w]})));')
    blk = lambda c: cvt(f'c{c // 16}{c % 16 // 4}.{X[c % 4]}', Q['IA'][c], sv(c), Q['B'], Q['C'][c])
    if 'up' not in Q:      # store the block output
        if Q['vs'] is None: o.append(f'    bool ok = (x < {WD}u) && (y < {HT}u);')
        else: o += [f'    uvec4 vs = PhysicalPointerUint4NonWriteCBVArray(registers._m0).value[{Q["vs"]}u];', '    bool ok = (x < vs.x) && (y < vs.y);']
        o.append(f'    uint ob = {Q["OUT"]}u + {R}u * (y + 1u) + 16u * (x + 1u);')
        o.append('    if (!ok) return;')
        for p in range(n):
            ws = [f'pack32(u8vec4(clamp(ivec4(uvec4(' + ', '.join(blk(16 * p + 4 * w + j) for j in range(4)) + ')), ivec4(-128), ivec4(127))))' for w in range(4)]
            o.append(f'    {U4}[(ob + {PL * p}u) >> 4u] = uvec4({", ".join(ws)});')
        return '\n'.join(o) + '\n}\n'
    u = Q['up']; Uw, bU = np.asarray(Wt['U']).astype(np.int64), np.asarray(Wt['bU']).astype(np.int64); on = u['on']
    R2, PL2, WD2, HT2 = LV[Q['lv'] - 1]; assert Uw.shape == (2, 2, 16 * on, 16 * n)
    for c4 in range(4 * n):
        o.append(f'    uint k{c4} = pack32(u8vec4(clamp(ivec4(uvec4(' + ', '.join(blk(4 * c4 + j) for j in range(4)) + ')), ivec4(-128), ivec4(127))));')
    o += [f'    uvec4 vs = PhysicalPointerUint4NonWriteCBVArray(registers._m0).value[{u["vs"]}u];', '    if (x >= vs.x || y >= vs.y) return;']
    kw = [f'k{q}' for q in range(4 * n)]
    for sy in range(2):
        for sx in range(2):
            o.append(f'    {{ uint X2 = 2u * x + {sx}u, Y2 = 2u * y + {sy}u; bool ok = (Y2 < {HT2}u) && (X2 < {WD2}u);')
            o.append(f'      uint sb = {R2}u * (Y2 + 1u) + 16u * (X2 + 1u);')
            if 'U' in LP:
                def post(gi, v, sy=sy, sx=sx):
                    st = [f'uvec4 ev = {U4}[({u["SKIP"]}u + {PL2}u * {gi} + sb) >> 4u];']
                    ws = []
                    for w in range(4):
                        st.append(f'ivec4 e{w} = ivec4(i8vec4(unpack8(ev.{X[w]})));')
                        ws.append('pack32(u8vec4(clamp(ivec4(uvec4(' + ', '.join(cvt(f"e{w}.{X[j]}", u["KS"], v[4 * w + j], u["SB"], u["SC"]) for j in range(4)) + ')), ivec4(-128), ivec4(127))))')
                    return st + [f'if (ok) {U4}[({u["OUT"]}u + {PL2}u * {gi} + sb) >> 4u] = uvec4({", ".join(ws)});']
                loop(o, f'U{sy}{sx}', kw, [[Uw[sy, sx, c, 4 * q:4 * q + 4] for q in range(4 * n)] for c in range(16 * on)], bU, post, gs=16)
                o.append('    }'); continue
            for p in range(on):
                o.append(f'      uvec4 ev{p} = {U4}[({u["SKIP"]}u + {PL2 * p}u + sb) >> 4u];')
                ws = []
                for w in range(4):
                    o.append(f'      ivec4 e{4 * p + w} = ivec4(i8vec4(unpack8(ev{p}.{X[w]})));')
                    v = []
                    for j in range(4):
                        c = 16 * p + 4 * w + j
                        se = '(' + dot(bU[c], kw, [Uw[sy, sx, c, 4 * q:4 * q + 4] for q in range(4 * n)]) + ')'
                        v.append(cvt(f"e{4 * p + w}.{X[j]}", u["KS"], se, u["SB"], u["SC"]))
                    ws.append(f'pack32(u8vec4(clamp(ivec4(uvec4({", ".join(v)})), ivec4(-128), ivec4(127))))')
                o.append(f'      if (ok) {U4}[({u["OUT"]}u + {PL2 * p}u + sb) >> 4u] = uvec4({", ".join(ws)});')
            o.append('    }')
    return '\n'.join(o) + '\n}\n'

SKIP = ('    if ((_26[registers._m1 + 11u]._m0[8326136u] == 1511506142u) && (_26[registers._m1 + 11u]._m0[8326137u] == 168889943u))\n'
        '    {\n        return;\n    }\n')

MAP = {'1080': {1919: 959, 1079: 539, 959: 479, 539: 269, 30752: 15392, 15392: 7712, 8326136: 2089496, 8326137: 2089497,
                33273664: 8342464, 8342464: 2097664, 41616128: 10440128, 49958592: 12537792, 58349248: 14659648},
       '5k': {1919: 3839, 1079: 2159, 959: 1919, 539: 1079, 30752: 61472, 15392: 30752, 8326136: 33241016, 8326137: 33241017,
              33273664: 132902464, 8342464: 33273664, 41616128: 166176128, 49958592: 199449792, 58349248: 232819648}}
LAYOUT = [re.compile(p) for p in (r'_m0\[\d+u\] == 1511506142u', r'_m0\[\d+u\] == 168889943u', r'^\s*if \(x > \d+u \|\| y > \d+u\) return;',
                                   r'^\s*uint ib = \d+u \+ \d+u \* y', r'\(ib \+ \d+u\)', r'^\s*uint ob = \d+u \+ \d+u \* \(y \+ 1u\)', r'\(ob \+ \d+u\)')]
# address offsets (ib + N), (ob + N): N = rows x row bytes + planes x plane size + tap offset (0..44 bytes); 4K class row bytes / plane size per level,
# and each class's (level 1: passes 1, 2, 12; level 2: passes 4, 5, 10, which also address a second plane)
LVL = {1: 1, 2: 1, 12: 1, 4: 2, 5: 2, 10: 2}
GEOM = {'4k': {1: (30752, None), 2: (15392, 8342464)}, '1080': {1: (15392, None), 2: (7712, 2097664)}, '5k': {1: (61472, None), 2: (30752, 33273664)}}
def offset(n, k, cls):
    rb, pl = GEOM['4k'][LVL[k]]; rbc, plc = GEOM[cls][LVL[k]]
    b = n // pl if pl and n >= pl else 0; r = n - b * (pl or 0); a = r // rb; d = r - a * rb
    assert d < 48 and a <= 3 and b <= 1, f'pass {k}: offset {n} does not decompose ({a} rows, {b} planes, {d} bytes)'
    return a * rbc + b * (plc or 0) + d
def classify(src, m, k, cls):
    out, hit = [], [0] * len(LAYOUT)
    for line in src.split('\n'):
        if any(p.search(line) for p in LAYOUT):
            for i, p in enumerate(LAYOUT): hit[i] += bool(p.search(line))
            line = re.sub(r'\((ib|ob) \+ (\d+)u\)', lambda t: f'({t.group(1)} + {offset(int(t.group(2)), k, cls)}u)', line)      # offsets first
            parts = re.split(r'(\((?:ib|ob) \+ \d+u\))', line)      # then the other literals (bases, row bytes, bounds, marks), not inside offsets
            line = ''.join(x if x.startswith('(ib +') or x.startswith('(ob +') else re.sub(r'\b(\d+)u\b', lambda t: f'{m.get(int(t.group(1)), int(t.group(1)))}u', x) for x in parts)
        out.append(line)
    return '\n'.join(out), hit

# the SPIR-V names (Linux) and DLL hashes (Windows) of the 18 shaders: pass -> (<=1080p, 4K, >4K)
SPV = {1: ('e0d8ce49e87ed7c3', 'b801eac21966703c', '1b5366424fd62c4b'), 2: ('e7c288d8ff89d888', 'ed73a54c062b6761', 'cb88eec183418365'),
       4: ('fdfc534367db7623', '0b774df860126a12', '7b5321a3d5ca0065'), 5: ('f7ea511744202f66', '27b4daeecbd6e6f7', 'dff9e56040c7e96e'),
       10: ('9c405b28b4266d13', '160fae4d0458e948', '65d51e63f9cec64a'), 12: ('c620021443a811fc', '856778db9cb96753', 'b4e989434eb54e49')}
DLL = {1: ('be6a3617b6dcf44f5fab8f1571652cbb', 'c7c1e0184dcc4b6a3fca6d6a8b873965', '5b67737eafe17f21b051a0efe30f175e'),
       2: ('f5c7d8b41d4ce7a8f9b65a40f2b959b6', '6433f67788cd97c07342a7bbcfbe0d4a', '755ca70ed4e5d1fc8231e6d567c881b7'),
       4: ('c8c67dfe3600667f7bf4ba6220841361', '9520d91584508b33703ce28a8ed5918c', '910903c6fe68cdd5c764fcfadd960708'),
       5: ('239f5f5aec7daa0c54457b96b65f4657', 'a1b5a3ce6b5aa7fc555e7c90c5622109', '145b4d28de375081586518969e18468c'),
       10: ('a5ae39a2b7d0348769e6c2a0e1c86f3f', '260cb9f229a3321e97b016bf3c0fad9f', '54a1ac719744f69d69c072bce3492e9e'),
       12: ('8cc4fd043a8fc43ab3fbf7124f6cc591', 'cef018ba31e6e83b17815b93c15d89b0', '938540a6ac6e404d702fd450f5fa76ba')}
if __name__ == '__main__':
    a = sys.argv[1:]; hl = None
    if '--hlsl' in a: i = a.index('--hlsl'); hl = a[i + 1]; del a[i:i + 2]
    if len(a) != 3: sys.exit(__doc__ if __doc__ else open(__file__).read().split('\nimport')[0])
    wz, base, out = a; Z = np.load(wz)
    if os.path.exists(out): sys.exit(f'{out} exists: not overwritten')
    shutil.copytree(base, out); W = os.path.join(out, '.work'); os.makedirs(W)
    if hl: os.makedirs(hl, exist_ok=True); sys.path.insert(0, HERE); import to_hlsl
    for k in (1, 2, 4, 5, 10, 12):
        I = {n: Z[f'p{k}_{n}'] for n in ('A', 'bA', 'Bw', 'bB', 'Cw', 'bC')}
        src = gen(k, I); assert src.count('void main()\n{\n') == 1
        src = src.replace('void main()\n{\n', 'void main()\n{\n' + SKIP, 1)
        for ci, cls in enumerate(('1080', '4k', '5k')):
            s = src
            if cls != '4k':
                s, hit = classify(src, MAP[cls], k, cls); assert all(hit[i] > 0 for i in range(6)), f'pass {k} {cls}: layout lines not all found {hit}'
            f = os.path.join(W, f'p{k}_{cls}.comp'); open(f, 'w').write(s)
            subprocess.run(['glslangValidator', '-V', '--target-env', 'vulkan1.3', f, '-o', os.path.join(out, SPV[k][ci] + '.spv')], check=True, capture_output=True)
            if hl: open(os.path.join(hl, DLL[k][ci] + '.hlsl'), 'w').write(to_hlsl.convert(s, f'p{k}_{cls}'))
    shutil.rmtree(W); shutil.copy(os.path.join(HERE, 'WARNING.txt'), os.path.join(out, 'WARNING.txt'))      # lossy2's own warning
    print(f'{out}: 18 shaders written over {base}' + (f'; HLSL in {hl}' if hl else ''))
