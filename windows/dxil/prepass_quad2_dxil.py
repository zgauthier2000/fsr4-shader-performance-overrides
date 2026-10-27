#!/usr/bin/env python3
# prepass_quad2_dxil.py < prepass.ll > out.ll (2026-10-25, user: "add it to the lossy builds too"): prepass_quad_dxil.py (the 4.1.2 RX 6000 driver prepass's LAYOUT on
# AMD's 4.1.1 prepass; see there) generalized for the LOSSY prepasses, which hold a frame-skip header and TWO copies of AMD's prepass (frameskip_dxil.py, FS_BRANCH=1:
# fs.R = frames that run the network, fs.S = skipped frames, named k.*), each with extra per-pixel code (exposure steps, motion code, persistence taps).
#   - the function is first put in named form (numbered values %N -> %vN, numbered blocks -> bN; names in DXIL are free), then every COPY is rearranged on its own:
#     a copy = a block that computes the thread id and ends in AMD's bounds test (br on x < width to the y test, else return);
#   - a copy that STORES the downsampled tensor (lane-0 block with rawBufferStore) gets the full driver layout (as prepass_quad_dxil.py: 4 pixels per thread,
#     features to groupshared memory, barrier, one chain per cell from the bias, zeros outside the image);
#   - a copy WITHOUT that store (the skipped-frame copy: frame skip removes it) gets only its per-pixel work, 4 pixels per thread, no barrier or downsample.
#   Per-pixel code (all blocks reachable from the copy's body down to the block that makes the 7 features) is cloned 4 times with only x, y changed; values and blocks
#   defined in it get per-pixel names. Side effects inside it (history store, motion-code store) are per pixel and come along. 64 threads; wave-ops flag dropped.
import sys, re, os
# PQ_LAYOUT=hybrid (2026-10-25, user: "look into the cheaper layout for the skipped frames"): keep AMD's 256 threads, one pixel per thread (AMD's own per-pixel code and
# mapping, not cloned); a copy that stores the tensor writes each pixel's features to groupshared memory, barrier, then threads 0..63 each sum one cell in the driver's
# order (same features, same chain = the same picture as the 64-thread layout); a copy without the store (skipped frames) stays AMD's code unchanged.
HYB = os.environ.get('PQ_LAYOUT', 'quad') == 'hybrid'
# PQ_ORDER=amd (2026-10-25, user: "check for the exact speedup for lossy3"): keep AMD's OWN summation (4.1.1 and Lite alike): per pixel a chain from 0, then
# (p0 + p1) + (p2 + p3), then + bias, the same adds in the same operand order as AMD's quad ops (lane 0: t = qx + own, sum = t + qy, out = sum + bias)
# = AMD's picture byte for byte in the new layout (an EXACT build). Default 'driver': one chain from the bias (4.1.2 RX 6000 driver's picture).
AMDORDER = os.environ.get('PQ_ORDER', 'driver') == 'amd'
t = sys.stdin.read()
a = t.index('define void @'); b = t.index('\n}\n', a)
head, body, tail = t[:a], t[a:b + 3], t[b + 3:]
PACK4 = 'declare i32 @dx.op.pack4x8.i32(' in t
L = body.split('\n'); defline = L[0]; fl = L[1:-2]; assert L[-2] == '}'
numlabels = {0} | {int(m) for m in re.findall(r'^; <label>:(\d+)', '\n'.join(fl), re.M)}
def norm(s):
    s = re.sub(r'\s+;.*$', '', s) if not s.lstrip().startswith(';') else s
    return re.sub(r'%(\d+)\b', lambda m: ('%b' if int(m[1]) in numlabels else '%v') + m[1], s)
blocks = [['b0', []]]
for l in fl:
    m = re.match(r'; <label>:(\d+)', l); m2 = re.match(r'([A-Za-z_.][\w.]*):(\s|$)', l)
    if m: blocks.append([f'b{m[1]}', []]); continue
    if m2: blocks.append([m2[1], []]); continue
    if l.strip() and not l.lstrip().startswith(';'): blocks[-1][1].append(norm(l))
order = [n for n, _ in blocks]; bmap = {n: ls for n, ls in blocks}; labels = set(order)
DEF = re.compile(r'\s*%([\w.]+) = (.*)')
defs = {}
for n, ls in blocks:
    for i, l in enumerate(ls):
        m = DEF.match(l)
        if m: defs[m[1]] = (n, i, m[2])
def uses(s): return [x for x in re.findall(r'%([\w.]+)', s) if x in defs]
def succ(n): return re.findall(r'label %([\w.]+)', bmap[n][-1])
def reach(starts, stop=()):
    seen, st = set(), list(starts)
    while st:
        x = st.pop()
        if x in seen: continue
        seen.add(x)
        if x not in stop: st += succ(x)
    return seen
DOT = re.compile(r'call float @dx\.op\.dot2AddHalf\.f32\(i32 162, float ([^,]+), half ([^,]+), half ([^,]+), half ([^,]+), half ([^)]+)\)')
QXP = re.compile(r'call float @dx\.op\.quadOp\.f32\(i32 123, float %([\w.]+), i8 0\)')
copies = []
for n in order:
    ls = bmap[n]
    tid = [v for v, (bb, i, r) in defs.items() if bb == n and r.startswith('call i32 @dx.op.threadIdInGroup.i32(i32 95, i32 0)')]
    m = re.fullmatch(r'\s*br i1 %([\w.]+), label %([\w.]+), label %([\w.]+)', ls[-1])
    if not tid or not m or m[1] not in defs or defs[m[1]][0] != n: continue
    mx = re.fullmatch(r'icmp ult i32 %([\w.]+), %([\w.]+)', defs[m[1]][2])
    if not mx: continue
    copies.append(dict(CR=n, TID=tid[0], X=mx[1], W=mx[2], B31=m[2], RET=m[3]))
assert 1 <= len(copies) <= 2, [c['CR'] for c in copies]
gen = {}; drop = set(); report = []
for ci, c in enumerate(copies):
    CR, TID, X, W, B31, RET = c['CR'], c['TID'], c['X'], c['W'], c['B31'], c['RET']; P = f'q{ci}'
    l31 = bmap[B31]; assert len(l31) == 3, l31
    m1 = DEF.match(l31[0]); H = m1[1]; CB = re.fullmatch(r'extractvalue %dx\.types\.CBufRet\.i32 %([\w.]+), 1', m1[2])[1]
    assert re.fullmatch(rf'extractvalue %dx\.types\.CBufRet\.i32 %{re.escape(CB)}, 0', defs[W][2])
    m2 = DEF.match(l31[1]); Y = re.fullmatch(rf'icmp ult i32 %([\w.]+), %{re.escape(H)}', m2[2])[1]
    BODY = re.fullmatch(rf'\s*br i1 %{re.escape(m2[1])}, label %([\w.]+), label %{re.escape(RET)}', l31[2])[1]
    GX = [v for v, (bb, i, r) in defs.items() if bb == CR and r.startswith('call i32 @dx.op.groupId.i32(i32 94, i32 0)')][0]
    GY = [v for v, (bb, i, r) in defs.items() if bb == CR and r.startswith('call i32 @dx.op.groupId.i32(i32 94, i32 1)')][0]
    tidder = {TID}
    for v, (bb, i, r) in sorted(defs.items(), key=lambda kv: kv[1][1]):
        if bb == CR and any(u in tidder for u in uses(r)): tidder.add(v)
    assert X in tidder and Y in tidder
    allr = reach([BODY])
    qx = sorted((v for v, (bb, i, r) in defs.items() if bb in allr and QXP.fullmatch(r)), key=lambda v: (order.index(defs[v][0]), defs[v][1]))
    assert len(qx) == 16, (CR, len(qx))
    chains = []
    for q in qx:
        s = QXP.fullmatch(defs[q][2])[1]; ds = []
        while True:
            d = DOT.fullmatch(defs[s][2]); assert d, defs[s]
            ds.append(d.groups()[1:]); acc = d[1].strip()
            if acc == '0.000000e+00': break
            s = acc[1:]
        ds.reverse(); chains.append(ds)
    feat = [(d[2], d[3]) for d in chains[0]]
    assert all([(d[2], d[3]) for d in ch] == feat for ch in chains) and len(feat) == 4 and feat[3][1] == '0xH0000', feat
    F = [f[1:] for p in feat for f in p if f != '0xH0000']; assert len(F) == 7 and len(set(F)) == 7
    BEND = defs[F[0]][0]; assert all(defs[f][0] == BEND for f in F)
    cut = max(defs[f][1] for f in F)
    reg = [n for n in order if n in reach([BODY], stop=(BEND,))]
    assert RET not in reg and B31 not in reg and CR not in reg, ('region', CR)
    after = reach(succ(BEND)); SBs = [x for x in succ(BEND) if x != RET]; assert len(SBs) == 1 and after <= {SBs[0], RET}, (CR, after)
    SB = SBs[0]
    rest = bmap[BEND][cut + 1:] + bmap[SB]
    stores = [l for l in rest if re.match(r'\s*call void', l)]
    has_store = any('rawBufferStore.i32(i32 140' in l for l in stores); assert len(stores) == (1 if has_store else 0), (CR, stores)
    for n in reg:
        ls = bmap[n] if n != BEND else bmap[n][:cut + 1]
        for l in ls:
            bad = [u for u in uses(l) if u in tidder and u not in (X, Y)]
            assert not bad, ('per-pixel code uses thread-derived values', CR, l, bad)
            assert f'label %{RET}' not in l and f'label %{SB}' not in l, ('per-pixel code leaves early', l)
            assert 'quadOp' not in l and 'Wave' not in l and 'barrier' not in l, l
    if HYB and not has_store: report.append(f'{CR}: unchanged (no tensor store)'); continue
    drop |= {CR, B31, SB, RET} | set(reg)
    # handles of the weights (any chain's weight loads) and of the output
    def whandle(w):
        r = defs[w][2]; r = defs[re.fullmatch(r'fptrunc float %([\w.]+) to half', r)[1]][2]
        r = defs[re.fullmatch(r'call float @dx\.op\.legacyF16ToF32\(i32 131, i32 %([\w.]+)\)', r)[1]][2]
        m = re.fullmatch(r'(?:and i32 %([\w.]+), 65535|lshr i32 %([\w.]+), 16)', r); r = defs[m[1] or m[2]][2]
        r = defs[re.fullmatch(r'extractvalue %dx\.types\.ResRet\.i32 %([\w.]+), \d', r)[1]][2]
        return defs[re.search(r'rawBufferLoad\.i32\(i32 139, %dx\.types\.Handle %([\w.]+),', r)[1]][2]
    WHL = {whandle(d[0][1:]) for ch in chains for d in ch}; assert len(WHL) == 1; WHL = WHL.pop()
    out = [f'{CR}:'] + bmap[CR][:-1] + [f'  %{H} = extractvalue %dx.types.CBufRet.i32 %{CB}, 1']
    if HYB:
        assert not any(' = phi ' in l for l in bmap[BODY]), 'phi in the body entry'
        K = f'{P}h'
        out += [f'  %{K}_ix = icmp ult i32 %{X}, %{W}', f'  %{K}_iy = icmp ult i32 %{Y}, %{H}', f'  %{K}_in = and i1 %{K}_ix, %{K}_iy', f'  br i1 %{K}_in, label %{BODY}, label %{K}_skip']
        for n in reg:
            out += [f'{n}:'] + (bmap[n] if n != BEND else bmap[n][:cut + 1] + [f'  br label %{K}_join'])
        out += [f'{K}_skip:', f'  br label %{K}_join', f'{K}_join:']
        for j, f in enumerate(F): out.append(f'  %{K}_f{j} = phi half [ %{f}, %{BEND} ], [ 0xH0000, %{K}_skip ]')
        out += [f'  %{K}_xl = and i32 %{X}, 15', f'  %{K}_yl = and i32 %{Y}, 15', f'  %{K}_cx = lshr i32 %{K}_xl, 1', f'  %{K}_cy0 = lshr i32 %{K}_yl, 1', f'  %{K}_cy = shl i32 %{K}_cy0, 3',
                f'  %{K}_c = or i32 %{K}_cx, %{K}_cy', f'  %{K}_c4 = shl i32 %{K}_c, 2', f'  %{K}_sx = and i32 %{K}_xl, 1', f'  %{K}_sy0 = and i32 %{K}_yl, 1', f'  %{K}_sy = shl i32 %{K}_sy0, 1',
                f'  %{K}_sl = or i32 %{K}_sx, %{K}_sy', f'  %{K}_sw = shl i32 %{K}_sl, 8', f'  %{K}_w = add i32 %{K}_c4, %{K}_sw']
        for j in range(4):
            lo = f'%{K}_f{2 * j}'; hi = f'%{K}_f{2 * j + 1}' if 2 * j + 1 < 7 else None
            out += [f'  %{K}_e{j}l = fpext half {lo} to float', f'  %{K}_h{j}l = call i32 @dx.op.legacyF32ToF16(i32 130, float %{K}_e{j}l)']
            out += ([f'  %{K}_e{j}h = fpext half {hi} to float', f'  %{K}_h{j}h = call i32 @dx.op.legacyF32ToF16(i32 130, float %{K}_e{j}h)'] if hi else
                    [f'  %{K}_h{j}h = call i32 @dx.op.legacyF32ToF16(i32 130, float 0.000000e+00)'])
            out += [f'  %{K}_s{j} = shl i32 %{K}_h{j}h, 16', f'  %{K}_v{j} = or i32 %{K}_s{j}, %{K}_h{j}l', f'  %{K}_a{j} = add i32 %{K}_w, {j}',
                    f'  %{K}_g{j} = getelementptr [1024 x i32], [1024 x i32] addrspace(3)* @"\\01?po_lds@@3PAIA", i32 0, i32 %{K}_a{j}',
                    f'  store i32 %{K}_v{j}, i32 addrspace(3)* %{K}_g{j}, align 4']
    if HYB: pass
    else:
     out += [f'  %{P}_x0 = and i32 %{TID}, 1', f'  %{P}_s1 = lshr i32 %{TID}, 1', f'  %{P}_x1 = and i32 %{P}_s1, 6', f'  %{P}_xl = or i32 %{P}_x0, %{P}_x1',
             f'  %{P}_y0 = and i32 %{P}_s1, 1', f'  %{P}_s3 = lshr i32 %{TID}, 3', f'  %{P}_y1 = and i32 %{P}_s3, 6', f'  %{P}_yl = or i32 %{P}_y0, %{P}_y1',
             f'  %{P}_gx = shl i32 %{GX}, 4', f'  %{P}_gy = shl i32 %{GY}, 4', f'  %{P}_x = or i32 %{P}_xl, %{P}_gx', f'  %{P}_y = add i32 %{P}_yl, %{P}_gy',
             f'  %{P}_cell = lshr i32 %{P}_s1, 1', f'  %{P}_cx = and i32 %{P}_cell, 3', f'  %{P}_s4 = lshr i32 %{TID}, 4', f'  %{P}_cy = shl i32 %{P}_s4, 3', f'  %{P}_c = or i32 %{P}_cx, %{P}_cy',
             f'  %{P}_sl = and i32 %{TID}, 3', f'  %{P}_sw = shl i32 %{P}_sl, 8', f'  %{P}_c4 = shl i32 %{P}_c, 2', f'  %{P}_w0 = add i32 %{P}_c4, %{P}_sw']
     rdefs = {v for v, (bb, i, r) in defs.items() if bb in reg and (bb != BEND or i <= cut)}
     for k, (dx, dy) in enumerate([(0, 0), (8, 0), (0, 8), (8, 8)]):
         K = f'{P}k{k}'; xk, yk = (f'{P}_x', f'{P}_y') if k == 0 else (f'{K}_x', f'{K}_y')
         if k: out += [f'  %{K}_x = add i32 %{P}_x, {dx}', f'  %{K}_y = add i32 %{P}_y, {dy}']
         out += [f'  %{K}_ix = icmp ult i32 %{xk}, %{W}', f'  %{K}_iy = icmp ult i32 %{yk}, %{H}', f'  %{K}_in = and i1 %{K}_ix, %{K}_iy',
                 f'  br i1 %{K}_in, label %{K}b_{BODY}, label %{K}_skip']
         def rn(l, K=K, xk=xk, yk=yk):
             def f(m):
                 x = m[1]
                 if x == X: return '%' + xk
                 if x == Y: return '%' + yk
                 if x in rdefs: return f'%{K}v_{x}'
                 if x in reg: return f'%{K}b_{x}'
                 return m[0]
             return re.sub(r'%([\w.]+)', f, l)
         for n in reg:
             out.append(f'{K}b_{n}:')
             out += [rn(l) for l in (bmap[n] if n != BEND else bmap[n][:cut + 1])]
             if n == BEND: out.append(f'  br label %{K}_join')
         out += [f'{K}_skip:', f'  br label %{K}_join', f'{K}_join:']
         if has_store:
             for j, f in enumerate(F): out.append(f'  %{K}_f{j} = phi half [ %{K}v_{f}, %{K}b_{BEND} ], [ 0xH0000, %{K}_skip ]')
             out.append(f'  %{K}_w = add i32 %{P}_w0, {(16 if dx else 0) + (128 if dy else 0)}')
             for j in range(4):
                 lo = f'%{K}_f{2 * j}'; hi = f'%{K}_f{2 * j + 1}' if 2 * j + 1 < 7 else None
                 out += [f'  %{K}_e{j}l = fpext half {lo} to float', f'  %{K}_h{j}l = call i32 @dx.op.legacyF32ToF16(i32 130, float %{K}_e{j}l)']
                 out += ([f'  %{K}_e{j}h = fpext half {hi} to float', f'  %{K}_h{j}h = call i32 @dx.op.legacyF32ToF16(i32 130, float %{K}_e{j}h)'] if hi else
                         [f'  %{K}_h{j}h = call i32 @dx.op.legacyF32ToF16(i32 130, float 0.000000e+00)'])
                 out += [f'  %{K}_s{j} = shl i32 %{K}_h{j}h, 16', f'  %{K}_v{j} = or i32 %{K}_s{j}, %{K}_h{j}l', f'  %{K}_a{j} = add i32 %{K}_w, {j}',
                         f'  %{K}_g{j} = getelementptr [1024 x i32], [1024 x i32] addrspace(3)* @"\\01?po_lds@@3PAIA", i32 0, i32 %{K}_a{j}',
                         f'  store i32 %{K}_v{j}, i32 addrspace(3)* %{K}_g{j}, align 4']
    if not has_store:
        out.append('  ret void'); gen[CR] = out; report.append(f'{CR}: per-pixel only (no tensor store), {len(reg)} blocks x 4'); continue
    m = re.search(r'rawBufferStore\.i32\(i32 140, %dx\.types\.Handle %([\w.]+), i32 %([\w.]+), i32 undef,', [l for l in stores][0])
    OHL = defs[m[1]][2]; ROW = int(re.fullmatch(r'call i32 @dx\.op\.tertiary\.i32\(i32 49, i32 (\d+), i32 %[\w.]+, i32 %[\w.]+\)', defs[m[2]][2])[1])
    BL = [int(x) for x in re.findall(r'rawBufferLoad\.i32\(i32 139, %dx\.types\.Handle %[\w.]+, i32 (\d+), i32 undef, i8 15, i32 4\)', '\n'.join(bmap[SB]))]
    assert BL == [BL[0] + 16 * i for i in range(4)], BL
    sbt = '\n'.join(bmap[SB])
    for pat in (rf'shl i32 %{re.escape(GX)}, 3', rf'shl i32 %{re.escape(GY)}, 3', r'or i32 %[\w.]+, 1', r'add i32 %[\w.]+, 16'): assert re.search(pat, sbt), ('address form', pat)
    out += ['  call void @dx.op.barrier(i32 80, i32 9)']
    if HYB: out += [f'  %{P}_lo = icmp ult i32 %{TID}, 64', f'  br i1 %{P}_lo, label %{P}_conv, label %{P}_end', f'{P}_end:', '  ret void', f'{P}_conv:']
    out += [f'  %{P}c_wh = {WHL}', f'  %{P}c_t4 = shl i32 %{TID}, 2']
    for k in range(4):
        for j in range(4):
            Q = f'{P}c{k}{j}'
            out += [f'  %{Q}a = add i32 %{P}c_t4, {256 * k + j}', f'  %{Q}g = getelementptr [1024 x i32], [1024 x i32] addrspace(3)* @"\\01?po_lds@@3PAIA", i32 0, i32 %{Q}a',
                    f'  %{Q}l = load i32, i32 addrspace(3)* %{Q}g, align 4', f'  %{Q}m = and i32 %{Q}l, 65535', f'  %{Q}n = lshr i32 %{Q}l, 16',
                    f'  %{Q}p = call float @dx.op.legacyF16ToF32(i32 131, i32 %{Q}m)', f'  %{Q}q = call float @dx.op.legacyF16ToF32(i32 131, i32 %{Q}n)',
                    f'  %{Q}x = fptrunc float %{Q}p to half', f'  %{Q}y = fptrunc float %{Q}q to half']
    for i in range(4):
        out.append(f'  %{P}c_bl{i} = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %{P}c_wh, i32 {BL[0] + 16 * i}, i32 undef, i8 15, i32 4)')
        for j in range(4): out.append(f'  %{P}c_be{4 * i + j} = extractvalue %dx.types.ResRet.i32 %{P}c_bl{i}, {j}')
    for ch in range(16):
        out.append(f'  %{P}c_b{ch} = bitcast i32 %{P}c_be{ch} to float'); acc = f'%{P}c_b{ch}'; part = []
        for k, o0 in enumerate([0, 16, 512, 528]):
            if AMDORDER: acc = '0.000000e+00'
            Wn = f'{P}w{ch}_{k}'
            out.append(f'  %{Wn} = call %dx.types.ResRet.i32 @dx.op.rawBufferLoad.i32(i32 139, %dx.types.Handle %{P}c_wh, i32 {32 * ch + o0}, i32 undef, i8 15, i32 4)')
            for j in range(4):
                out += [f'  %{Wn}_{j} = extractvalue %dx.types.ResRet.i32 %{Wn}, {j}', f'  %{Wn}_{j}m = and i32 %{Wn}_{j}, 65535', f'  %{Wn}_{j}n = lshr i32 %{Wn}_{j}, 16',
                        f'  %{Wn}_{j}p = call float @dx.op.legacyF16ToF32(i32 131, i32 %{Wn}_{j}m)', f'  %{Wn}_{j}q = call float @dx.op.legacyF16ToF32(i32 131, i32 %{Wn}_{j}n)',
                        f'  %{Wn}_{j}x = fptrunc float %{Wn}_{j}p to half', f'  %{Wn}_{j}y = fptrunc float %{Wn}_{j}q to half',
                        f'  %{P}d{ch}_{k}_{j} = call float @dx.op.dot2AddHalf.f32(i32 162, float {acc}, half %{Wn}_{j}x, half %{Wn}_{j}y, half %{P}c{k}{j}x, half %{P}c{k}{j}y)']
                acc = f'%{P}d{ch}_{k}_{j}'
            part.append(acc)
        if AMDORDER:
            out += [f'  %{P}t01_{ch} = fadd fast float {part[1]}, {part[0]}', f'  %{P}t23_{ch} = fadd fast float {part[3]}, {part[2]}',
                    f'  %{P}ts_{ch} = fadd fast float %{P}t01_{ch}, %{P}t23_{ch}', f'  %{P}tb_{ch} = fadd fast float %{P}ts_{ch}, %{P}c_b{ch}']
            acc = f'%{P}tb_{ch}'
        out += [f'  %{P}o_m{ch} = fmul fast float {acc}, 6.400000e+01', f'  %{P}o_r{ch} = call float @dx.op.unary.f32(i32 26, float %{P}o_m{ch})', f'  %{P}o_i{ch} = fptosi float %{P}o_r{ch} to i32']
    # pack: AMD 4.1.1 uses pack4x8 (signed saturate); FSR 4.1.2 Lite clamps with IMax / IMin and packs with shifts (2026-10-25): the same bits; use the input's form
    for g in range(4):
        if PACK4: out.append(f'  %{P}o_pk{g} = call i32 @dx.op.pack4x8.i32(i32 220, i8 2, i32 %{P}o_i{4 * g}, i32 %{P}o_i{4 * g + 1}, i32 %{P}o_i{4 * g + 2}, i32 %{P}o_i{4 * g + 3})'); continue
        for b_ in range(4):
            v = f'{P}o_i{4 * g + b_}'; out += [f'  %{v}x = call i32 @dx.op.binary.i32(i32 37, i32 %{v}, i32 -128)', f'  %{v}n = call i32 @dx.op.binary.i32(i32 38, i32 %{v}x, i32 127)']
            out += [f'  %{v}m = and i32 %{v}n, 255'] if b_ == 0 else ([f'  %{v}s = shl i32 %{v}n, {8 * b_}', f'  %{v}m = and i32 %{v}s, {255 << (8 * b_)}'] if b_ < 3 else [f'  %{v}m = shl i32 %{v}n, 24'])
        i0, i1, i2, i3 = (f'%{P}o_i{4 * g + b_}m' for b_ in range(4))
        out += [f'  %{P}o_q{g}a = or i32 {i1}, {i0}', f'  %{P}o_q{g}b = or i32 %{P}o_q{g}a, {i2}', f'  %{P}o_pk{g} = or i32 %{P}o_q{g}b, {i3}']
    out += [f'  %{P}o_cx = and i32 %{TID}, 7', f'  %{P}o_cy = lshr i32 %{TID}, 3', f'  %{P}o_gx = shl i32 %{GX}, 3', f'  %{P}o_gy = shl i32 %{GY}, 3',
            f'  %{P}o_x = or i32 %{P}o_cx, %{P}o_gx', f'  %{P}o_y = add i32 %{P}o_cy, %{P}o_gy', f'  %{P}o_y1 = add i32 %{P}o_y, 1', f'  %{P}o_x16 = shl i32 %{P}o_x, 4', f'  %{P}o_x17 = add i32 %{P}o_x16, 16',
            f'  %{P}o_ad = call i32 @dx.op.tertiary.i32(i32 49, i32 {ROW}, i32 %{P}o_y1, i32 %{P}o_x17)', f'  %{P}o_px = shl i32 %{P}o_x, 1', f'  %{P}o_py = shl i32 %{P}o_y, 1',
            f'  %{P}o_ox = icmp sge i32 %{P}o_px, %{W}', f'  %{P}o_oy = icmp sge i32 %{P}o_py, %{H}', f'  %{P}o_out = or i1 %{P}o_ox, %{P}o_oy']
    for g in range(4): out.append(f'  %{P}o_v{g} = select i1 %{P}o_out, i32 0, i32 %{P}o_pk{g}')
    out += [f'  %{P}o_h = {OHL}', f'  call void @dx.op.rawBufferStore.i32(i32 140, %dx.types.Handle %{P}o_h, i32 %{P}o_ad, i32 undef, i32 %{P}o_v0, i32 %{P}o_v1, i32 %{P}o_v2, i32 %{P}o_v3, i8 15, i32 4)',
            '  ret void']
    gen[CR] = out; report.append(f'{CR}: ' + ('hybrid (256 threads, 64 sum)' if HYB else f'driver layout, {len(reg)} blocks x 4') + (', AMD order' if AMDORDER else ', driver order') + f', bias at {BL[0]}, row bytes {ROW}')
fo = [defline]
for n in order:
    if n in gen: fo += gen[n]
    elif n not in drop: fo += [f'{n}:'] + bmap[n]
fo += ['}', '']
lds = '@"\\01?po_lds@@3PAIA" = external addrspace(3) global [1024 x i32], align 4\n\n'
head = head.rstrip('\n') + '\n\n' + lds
quadleft = 'quadOp' in '\n'.join(fo)
assert HYB or not quadleft, 'quad ops left'
tail2 = tail if quadleft else re.sub(r'; Function Attrs: nounwind\ndeclare float @dx\.op\.quadOp\.f32\(i32, float, i8\) #2\n\n?', '', tail)
need = {'@dx.op.barrier': '; Function Attrs: noduplicate nounwind\ndeclare void @dx.op.barrier(i32, i32) #3\n',
        '@dx.op.legacyF32ToF16': '; Function Attrs: nounwind readnone\ndeclare i32 @dx.op.legacyF32ToF16(i32, float) #0\n'}
for k, d in need.items():
    if (k + '(') not in tail2: tail2 = d + '\n' + tail2
if 'attributes #3' not in tail2: tail2 = re.sub(r'(attributes #2 = \{[^}]*\}\n)', r'\1attributes #3 = { noduplicate nounwind }\n', tail2)
assert re.search(r'attributes #3 = \{ noduplicate nounwind \}', tail2), 'attribute #3 is something else'
assert len(re.findall(r'!\{i32 256, i32 1, i32 1\}', tail2)) == 1
if not HYB: tail2 = tail2.replace('!{i32 256, i32 1, i32 1}', '!{i32 64, i32 1, i32 1}')
mf = re.search(r'!\{i32 0, i64 (\d+), i32 4, ', tail2); fl_ = int(mf[1])
if fl_ & 0x80000 and not quadleft: tail2 = tail2.replace(f'!{{i32 0, i64 {fl_}, i32 4, ', f'!{{i32 0, i64 {fl_ & ~0x80000}, i32 4, ', 1)
sys.stdout.write(head + '\n'.join(fo) + tail2)
print('prepass_quad2_dxil: ' + '; '.join(report) + f'; flags {fl_:#x} -> {fl_ & ~0x80000:#x}', file=sys.stderr)
