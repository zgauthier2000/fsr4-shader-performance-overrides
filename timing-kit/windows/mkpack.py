#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# mkpack.py <dlls dir> <out.pack> : the Windows timing kit's DLL pack, uncompressed (compress with zstd afterwards). Layout (little endian):
#   "FSR4PK1\n", u32 count, then per file: u16 path length, path (UTF-8, '/' separated, relative to dlls\), u64 size, u64 FNV-1a 64 of the data;
#   then the files' data in the same order. The order puts similar DLLs next to each other, so a long match window finds what they share.
import sys, os, struct, multiprocessing
src, out = sys.argv[1], sys.argv[2]
names = sorted(d for d in os.listdir(src) if os.path.isfile(os.path.join(src, d, 'amd_fidelityfx_upscaler_dx12.dll')))
order = sorted(names, key=lambda n: (3 if n.startswith('rdna') else 0 if n.startswith('1') else 1 if 'exact' in n else 2, 'igpu' in n, n))      # AMD's, the exact ones, the lossy ones, the study sets
AFTER = {'vk-exact-r3-test': 'vk-amd-412-reference', 'r4-exact-412-test': 'r4-amd-412-reference', 'lt143-test': 'lt131-test', 'lt144-test': 'lt129-test',
         'lt145-test': 'lt131-test', 'lt146-test': 'lt129-test',
         'lt147-test': 'lt137-test', 'lt148-test': 'lt136-test'}      # (2026-11-14) a test DLL right after
# the DLL it was made from: the decoder's window is 128 MB (fsr4time.c), so relatives further apart share nothing (vk-exact 33 DLLs from vk-amd cost ~25 MB of the Windows pack)
for c, par in AFTER.items():
    if c in order and par in order: order.remove(c); order.insert(order.index(par) + 1, c)
assert len(order) <= 128, 'fsr4time.exe reads at most 128 DLLs from a pack (PACK_MAX)'
def fnv(b):
    h = 0xcbf29ce484222325
    for i in range(0, len(b), 1 << 20):
        for x in b[i:i + (1 << 20)]: h = ((h ^ x) * 0x100000001b3) & 0xffffffffffffffff
    return h
if __name__ == '__main__':
  files = [(n + '/amd_fidelityfx_upscaler_dx12.dll', open(os.path.join(src, n, 'amd_fidelityfx_upscaler_dx12.dll'), 'rb').read()) for n in order]
  with multiprocessing.Pool() as pool: sums = pool.map(fnv, [d for _, d in files], 1)      # one file per core at a time
  with open(out, 'wb') as o:
    o.write(b'FSR4PK1\n' + struct.pack('<I', len(files)))
    for (p, d), h in zip(files, sums):
        pb = p.encode(); o.write(struct.pack('<H', len(pb)) + pb + struct.pack('<QQ', len(d), h))
    for _, d in files: o.write(d)
  print(f'{len(files)} files, {sum(len(d) for _, d in files) / 1e6:.1f} MB:', ' '.join(order))
