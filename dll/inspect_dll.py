#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# inspect_dll.py <amd_fidelityfx_upscaler_dx12.dll> <out dir>
#
# A first look at an FSR upscaler DLL of any version: its version, how many shader containers it holds, and the FSR 4 network
# shaders by the names they carry. Writes each named network shader to <out dir>/<hash>.dxil with names.txt (file, shader
# name, bytes). The output is AMD's shader code: keep it out of the repository. See also try_tools.py.
import os, re, struct, sys, collections
d = open(sys.argv[1], 'rb').read(); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
u = d.decode('utf-16-le', 'ignore'); m = re.search(r'FileVersion\x00+([0-9., ]+)', u)
print(f'file: {len(d)} bytes, version {m[1].strip() if m else "?"}; DXBC containers: {d.count(b"DXBC")}')
seen = {}; i = 0; kinds = collections.Counter(); other = collections.Counter()
while (i := d.find(b'DXBC', i)) >= 0:
    size = struct.unpack_from('<I', d, i + 24)[0]
    if 32 < size < 5_000_000 and i + size <= len(d):
        blob = d[i:i + size]; n = re.search(rb'(fsr4_model_v\d+_[a-z0-9_]+?)_(prepass|postpass|pass\d+)\x00', blob)
        if n:
            h = blob[4:20].hex()
            if h not in seen:
                seen[h] = (n[1].decode(), n[2].decode(), size); open(os.path.join(out, h + '.dxil'), 'wb').write(blob)
        else:
            nm = re.search(rb'(ffx_fsr[0-9a-z_]+|fsr[0-9]_[a-z0-9_]+)', blob); other[nm[1].decode()[:40] if nm else '(unnamed)'] += 1
    i += 4
open(os.path.join(out, 'names.txt'), 'w').write(''.join(f'{h}.dxil {a}_{b} {s}\n' for h, (a, b, s) in sorted(seen.items())))
byk = collections.defaultdict(collections.Counter)
for a, b, s in seen.values(): byk[a][b] += 1
order = lambda p: (0, 0) if p == 'prepass' else (2, 0) if p == 'postpass' else (1, int(p[4:]))
for a in sorted(byk):
    print(f'{a}: {sum(byk[a].values())} shaders: ' + '  '.join(f'{p} {byk[a][p]}' for p in sorted(byk[a], key=order)))
print(f'other containers: {sum(other.values())} ({len(other)} kinds)')
