#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# rename_dll.py <in.dll> <out.dll> <old name> <new name>: changes the version name an already patched DLL reports (what OptiScaler
# shows). patch_upscaler_dll.py --name puts a name of more than 7 characters, NUL-terminated, at the end of its .fsr4 section and points
# the one 'lea r64, [rip+disp]' that loads it there; this writes the new name over it (the section grows if the name is longer;
# VirtualSize and SizeOfImage follow) and checks that exactly one instruction loads that address. Nothing else changes: the script
# checks that every other byte (but the PE checksum) is the same. Release dll-2026-10-22's DLLs were patched with a build-time name
# and renamed with it. Keep a version number such as 4.1.1 at the start of the name: OptiScaler reads the FSR version from the name.
import sys, struct
src, out, old, new = sys.argv[1], sys.argv[2], sys.argv[3].encode(), sys.argv[4].encode()
d = bytearray(open(src, 'rb').read()); orig = bytes(d)
pe = struct.unpack_from('<I', d, 0x3c)[0]; nsec = struct.unpack_from('<H', d, pe + 6)[0]; opt = pe + 24; osz = struct.unpack_from('<H', d, pe + 20)[0]
sect_align = struct.unpack_from('<I', d, opt + 32)[0]; st = opt + osz
secs = []
for i in range(nsec):
    o = st + 40 * i; nm = d[o:o + 8].rstrip(b'\0').decode(); vs, va, rs, ro = struct.unpack_from('<IIII', d, o + 8); secs.append((nm, va, vs, ro, rs, o))
f = [s for s in secs if s[0] == '.fsr4']; assert len(f) == 1, 'no .fsr4 section (not a patched DLL?)'
nm, va, vs, ro, rs, ho = f[0]
sec = bytes(d[ro:ro + vs]); k = sec.find(old + b'\0'); assert k >= 0 and sec.find(old + b'\0', k + 1) < 0, f'{old.decode()} not found once in .fsr4'
assert k + len(old) + 1 == vs, 'the name is not the last thing in .fsr4'
target = va + k; text = next(s for s in secs if s[0] == '.text')
refs = [i for i in range(text[3] + 3, text[3] + text[4] - 4) if d[i - 2] == 0x8d and d[i - 3] in (0x48, 0x4c) and d[i - 1] & 0xc7 == 5
        and text[1] + i - text[3] + 4 + struct.unpack_from('<i', d, i)[0] == target]
assert len(refs) == 1, f'expected one instruction loading the name, found {len(refs)}'
nvs = k + len(new) + 1; assert nvs <= rs, 'the new name does not fit in the section\'s raw size'
d[ro + k:ro + max(vs, nvs)] = new + b'\0' + bytes(max(vs, nvs) - nvs)
struct.pack_into('<I', d, ho + 8, nvs)
struct.pack_into('<I', d, opt + 56, -(-(va + nvs) // sect_align) * sect_align)
struct.pack_into('<I', d, opt + 64, 0)
assert struct.unpack_from('<I', d, opt + 56)[0] == struct.unpack_from('<I', orig, opt + 56)[0], 'SizeOfImage changed: check by hand'
diff = [i for i in range(len(d)) if d[i] != orig[i] and not (ro + k <= i < ro + max(vs, nvs)) and not (ho + 8 <= i < ho + 12) and not (opt + 64 <= i < opt + 68)]
assert not diff, f'unexpected changes at {diff[:5]}'
s = 0      # PE checksum, as patch_upscaler_dll.py computes it
for (w,) in struct.iter_unpack('<H', bytes(d) + (b'\0' if len(d) % 2 else b'')):
    s += w; s = (s & 0xffff) + (s >> 16)
struct.pack_into('<I', d, opt + 64, ((s & 0xffff) + (s >> 16) & 0xffff) + len(d))
open(out, 'wb').write(d); print(f'{out}: {old.decode()} -> {new.decode()}')
