#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# try_tools.py <amd_fidelityfx_upscaler_dx12.dll> <work dir>
#
# What does a new version of AMD's DLL need? A dry run of this project's DXIL tools on every shader of an FSR upscaler DLL of any version.
# For each compute shader that looks like part of the FSR 4 network (int8 dot products, raw buffer stores or AMD's extension calls), each tool is tried on
# its own; the table says how many shaders each tool accepted and changed, by the shader's own name where it has one. Nothing is built or kept but the
# report (<work dir>/report.json holds, per shader, each tool's last error line). The columns say where a tool's pattern occurs, not where the builds use
# it: the z-constant and dot-split patterns, for one, occur in passes the builds leave alone. On AMD's 4.1.1.2740 the counts are: postpass stores 48,
# prepass route 90, frame skip in the prepass 90 and in the model passes 60, motion following 48.
# Needs DXC (set DXC_DIR to the unpacked Linux release, as for windows/dxil/build_dxil_overrides.sh).
import os, re, struct, sys, subprocess, collections, json
from concurrent.futures import ThreadPoolExecutor
dll, work = sys.argv[1], sys.argv[2]; os.makedirs(work + '/c', exist_ok=True)
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); W = R + '/windows/dxil'; F = R + '/research/frame-skip'; L = R + '/research/lossy'
DXC = os.environ.get('DXC_DIR', R + '/windows/toolchain/dxc')
if not os.path.exists(DXC + '/bin/dxc'): sys.exit(f'DXC not found in {DXC} (set DXC_DIR)')
env = dict(os.environ, LD_LIBRARY_PATH=DXC + '/lib', PYTHONPATH=F)
d = open(dll, 'rb').read(); blobs = {}; i = 0
while (i := d.find(b'DXBC', i)) >= 0:
    size = struct.unpack_from('<I', d, i + 24)[0]
    if 32 < size < 5_000_000 and i + size <= len(d): blobs.setdefault(d[i + 4:i + 20].hex(), d[i:i + size])
    i += 4
def run(cmd, inp):
    p = subprocess.run(cmd, input=inp, capture_output=True, env=env, timeout=120)
    return p.returncode == 0 and len(p.stdout) > 100, p.stdout, (p.stderr.decode(errors='replace').strip().split('\n') or [''])[-1][:110]
def one(item):
    h, blob = item; f = f'{work}/c/{h}.dxil'; open(f, 'wb').write(blob)
    ok, ll, err = run([DXC + '/bin/dxc', '-dumpbin', f], None); os.remove(f)
    if not ok: return None
    t = ll.decode(errors='replace')
    feats = dict(i8='dot4AddPacked' in t, raw='rawBufferStore' in t, amd='AmdExt' in t or 'amd' in t.lower() and 'dx.op.callShader' in t, stores=t.count('@dx.op.textureStore'), size=len(blob))
    if not (feats['i8'] or feats['amd'] or (feats['raw'] and 'rawBufferLoad' in t)): return None
    n = re.search(rb'(fsr4_model_v\d+_[a-z0-9_]+?)_(prepass|postpass|pass\d+)\x00', blob)
    name = (n[1].decode() + '_' + n[2].decode()) if n else 'unnamed'; pn = n[2].decode()[4:] if n and n[2].startswith(b'pass') and n[2] != b'pass' and n[2][4:].isdigit() else '1'
    rows = sorted(set(int(x) for x in re.findall(r'i32 (15392|30752|61472)\b', t))); S = str(rows[0]) if rows else '30752'
    res = {}; out = {}
    def tr(key, cmd, src):
        ok, o, e = run(['python3'] + cmd, src); ok = ok and o != src      # accepted AND changed something
        res[key] = (ok, e); out[key] = o if ok else None
    tr('postpass taps', [W + '/postpass_taps_dxil.py'], ll); tr('postpass stores', [W + '/postpass_lds_dxil.py'], out['postpass taps'] or ll)
    tr('postpass dot split', [W + '/dot4_split_dxil.py'], out['postpass stores'] or ll)
    tr('prepass route', [W + '/prepass_route_dxil.py'], ll)
    tr('pass 11 zero', [W + '/zconst_dxil.py'], ll); tr('pass 11 stores', [W + '/pass11_stores_dxil.py', 'rowc'], out['pass 11 zero'] or ll)
    tr('output scaling', [W + '/model_tail_dxil.py'], ll)
    tr('fold', [L + '/wfold_dxil.py', '18'], ll)
    tr('skip: prepass', [F + '/frameskip_dxil.py', 'prepass'], ll); tr('skip: model', [F + '/frameskip_dxil.py', 'model', S, pn], ll)
    tr('skip: motion', [F + '/motionpost_dxil.py'], ll); tr('skip: blend', [F + '/skipblend_dxil.py'], out['skip: motion'] or ll)
    return dict(h=h, name=name, feats=feats, rows=rows, res={k: v for k, v in res.items()})
with ThreadPoolExecutor(10) as ex: rs = [r for r in ex.map(one, blobs.items()) if r]
json.dump(rs, open(work + '/report.json', 'w'))
print(f'{len(blobs)} distinct containers; {len(rs)} look like FSR 4 network shaders (int8: {sum(r["feats"]["i8"] for r in rs)})')
tools = list(rs[0]['res']) if rs else []
names = collections.Counter(r['name'] for r in rs)
key = lambda n: (0, n) if n == 'unnamed' else (1, re.sub(r'pass(\d+)$', lambda m: 'pass%02d' % int(m[1]), n))
print(f'{"shader":44s} {"n":>4s} ' + ' '.join(f'{t[:9]:>9s}' for t in tools))
for n in sorted(names, key=key):
    g = [r for r in rs if r['name'] == n]
    print(f'{n:44s} {len(g):4d} ' + ' '.join(f'{sum(r["res"][t][0] for r in g):9d}' for t in tools))
