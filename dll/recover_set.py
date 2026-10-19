#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# recover_set.py <AMD's amd_fidelityfx_upscaler_dx12.dll> <a DLL made by patch_upscaler_dll.py from it> <out-dir>
#
# Writes the replacement shaders a patched DLL carries into <out-dir>, each named after the hash of the AMD shader it
# replaces (the names patch_upscaler_dll.py expects), so a patched DLL can be rebuilt with some shaders changed:
# recover the set, replace files in it, patch AMD's DLL again. The patcher leaves the shader table where it is and only
# writes a new (size, pointer) into each entry, so an entry found through AMD's DLL locates the same shader in the patched
# one. Shaders the patched DLL leaves as AMD's are not written. The output is shader code derived from AMD's: keep it out
# of the repository.
import os
import re
import struct
import sys

if len(sys.argv) != 4:
    sys.exit('\n'.join(l[2:] for l in open(__file__).read().split('\nimport')[0].split('\n')[2:]))
amd, pat = open(sys.argv[1], 'rb').read(), open(sys.argv[2], 'rb').read()
os.makedirs(sys.argv[3], exist_ok=True)


def sections(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    osz = struct.unpack_from('<H', d, pe + 20)[0]
    base = struct.unpack_from('<Q', d, pe + 24 + 24)[0]
    t = pe + 24 + osz
    out = []
    for k in range(nsec):
        o = t + 40 * k
        nm = d[o:o + 8].rstrip(b'\0').decode('latin1')
        vsize, va, rsize, raw = struct.unpack_from('<IIII', d, o + 8)
        out.append((nm, va, vsize, raw, rsize))
    return base, out


abase, asec = sections(amd)
pbase, psec = sections(pat)
adata = next(s for s in asec if s[0] == '.data')
dlo, dhi = adata[3], adata[3] + adata[4]


def va_of(off, base, secs):
    s = next(s for s in secs if s[3] <= off < s[3] + s[4])
    return base + s[1] + off - s[3]


def off_of(va, base, secs):
    rva = va - base
    s = next((s for s in secs if s[1] <= rva < s[1] + max(s[2], s[4])), None)
    if s is None:
        sys.exit(f'pointer {va:#x} is in no section of the patched DLL')
    return s[3] + rva - s[1]


n = same = 0
written = set()
pos = 0
while (pos := amd.find(b'DXBC', pos)) >= 0:
    size = struct.unpack_from('<I', amd, pos + 24)[0]
    if 32 < size < 5_000_000 and pos + size <= len(amd):
        blob = amd[pos:pos + size]
        if re.search(rb'fsr4_model_v07_fp8_no_scale_(postpass|prepass|pass[0-9]+)\x00', blob):
            h = blob[4:20].hex()
            ptr = struct.pack('<Q', va_of(pos, abase, asec))
            refs = []
            r = dlo
            while (r := amd.find(ptr, r, dhi)) >= 0:
                refs.append(r)
                r += 1
            if len(refs) != 1:
                sys.exit(f'shader {h}: expected one table entry in AMD\'s DLL, found {len(refs)}')
            ref = refs[0]
            psize = struct.unpack_from('<Q', pat, ref - 8)[0]
            poff = off_of(struct.unpack_from('<Q', pat, ref)[0], pbase, psec)
            pblob = pat[poff:poff + psize]
            if pblob[:4] != b'DXBC' or struct.unpack_from('<I', pblob, 24)[0] != psize:
                sys.exit(f'shader {h}: the patched DLL\'s entry does not point at a whole DXIL container')
            if pblob == blob:
                same += 1
            else:
                open(os.path.join(sys.argv[3], h + '.dxil'), 'wb').write(pblob)
                written.add(h)
    pos += 4
print(f'{len(written)} replacement shaders written to {sys.argv[3]} (table entries left as AMD\'s: {same})')
