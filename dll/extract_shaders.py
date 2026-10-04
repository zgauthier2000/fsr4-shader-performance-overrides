#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# extract_shaders.py <amd_fidelityfx_upscaler_dx12.dll> <out-dir>
#
# Writes every version of the FSR 4 postpass and model pass 11 that AMD's DLL contains into
# <out-dir> as <hash>.dxil (the hash in the shader's own header), so that
# ../windows/dxil/build_dxil_overrides.sh can build replacements for all of them at once instead
# of only for the versions one game happened to use. The output is AMD's shader code: keep it out
# of the repository.
import os
import re
import struct
import sys

if len(sys.argv) != 3:
    sys.exit('\n'.join(l[2:] for l in open(__file__).read().split('\nimport')[0].split('\n')[2:]))
d = open(sys.argv[1], 'rb').read()
os.makedirs(sys.argv[2], exist_ok=True)
n = 0
i = 0
while (i := d.find(b'DXBC', i)) >= 0:
    size = struct.unpack_from('<I', d, i + 24)[0]
    if 32 < size < 5_000_000 and i + size <= len(d):
        blob = d[i:i + size]
        if re.search(rb'fsr4_model_v07_fp8_no_scale_(postpass|pass11)\x00', blob):
            open(os.path.join(sys.argv[2], blob[4:20].hex() + '.dxil'), 'wb').write(blob)
            n += 1
    i += 4
print(f'{n} shaders written to {sys.argv[2]}')
