#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""co_to_dxbc.py <amd dll> <dir with co*.elf>: names each code object of an RGP capture (exported as ELF) by the DXBC
shader in the DLL it was compiled from. The ELF's api_shader_hash u64 pair, byte-reversed as b||a, is the DXBC digest."""
import sys, struct, glob, os, re
dll, elfdir = sys.argv[1:3]
d = open(dll, 'rb').read()
for f in sorted(glob.glob(os.path.join(elfdir, 'co*.elf'))):
    e = open(f, 'rb').read(); i = e.find(b'api_shader_hash')
    if i < 0: continue
    j = i + 15 + 1; a = struct.unpack('>Q', e[j+1:j+9])[0]; b = struct.unpack('>Q', e[j+10:j+18])[0]
    found = None
    for dig in (struct.pack('<QQ', b, a),):
        k = d.find(b'DXBC' + dig)
        if k >= 0:
            m = re.search(rb'fsr4_model_\w+', d[k:k + struct.unpack_from('<I', d, k + 24)[0]]); found = (hex(k), m.group(0).decode() if m else '?'); break
    print(os.path.basename(f), found)
