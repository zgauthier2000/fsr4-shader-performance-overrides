#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# patch_upscaler_dll.py [--only postpass|pass11|none] [--any-gpu] <amd_fidelityfx_upscaler_dx12.dll> <output.dll> [replacement-dir]
#
# Writes a copy of AMD's FSR 4.1.1 upscaler DLL that carries the faster shaders itself, so no
# launch option, add-on or override folder is needed. The replacements are the DXIL files the
# Windows add-on uses (default: ../windows/prebuilt/fsr4-overrides), each named after the hash in
# the header of the AMD shader it replaces. --only builds in just one of the two rewrites (or none),
# to find out which one helps on a given GPU.
#
# --any-gpu (experimental) also lifts AMD's GPU check on the INT8 version of FSR 4: AMD's DLL only
# offers it on desktop RDNA3 (chip family 0x91), refusing RDNA2, RDNA3 integrated GPUs and others.
# The check (the IsSupported function of ffxProvider_FSR4_Int8, found through its type information)
# is made to always answer yes. Whether FSR 4 then works on a given GPU is up to that GPU and its
# driver. Not for RDNA4: there both versions of FSR 4 would then report support.
#
# The DLL keeps its shaders as plain DXIL containers in .rdata, each described by an entry in
# .data: a 64-bit size followed by a 64-bit pointer. A replacement that fits is written in place;
# a larger one goes into a new section, .fsr4, at the end of the file, and the entry's size and
# pointer are changed to match (a base relocation already covers the pointer). Nothing else in
# the DLL changes.
#
# AMD's Authenticode signature does not survive the change, so it is removed, and the PE checksum
# is recomputed. Only DLLs that contain the expected shaders are patched; anything else (another
# FSR version, an already patched DLL) is refused.
import hashlib
import os
import struct
import sys

args = sys.argv[1:]
only = None
any_gpu = False
while args[:1] in (['--only'], ['--any-gpu']):
    if args[0] == '--any-gpu':
        any_gpu, args = True, args[1:]
        continue
    if len(args) < 2 or args[1] not in ('postpass', 'pass11', 'none'):
        sys.exit('--only takes postpass, pass11 or none')
    only, args = args[1], args[2:]
if only == 'none' and not any_gpu:
    sys.exit('--only none changes nothing without --any-gpu')
if len(args) not in (2, 3):
    sys.exit('\n'.join(l[2:] for l in open(__file__).read().split('\nimport')[0].split('\n')[2:]))
src, dst = args[0], args[1]
here = os.path.dirname(os.path.abspath(__file__))
rdir = args[2] if len(args) == 3 else os.path.join(here, '..', 'windows', 'prebuilt', 'fsr4-overrides')


def die(msg):
    sys.exit(f'patch_upscaler_dll: {msg}')


d = bytearray(open(src, 'rb').read())
repl = {f[:-5]: open(os.path.join(rdir, f), 'rb').read() for f in sorted(os.listdir(rdir)) if f.endswith('.dxil')}
if only:
    repl = {h: b for h, b in repl.items() if f'fsr4_model_v07_fp8_no_scale_{only}'.encode() in b}
if not repl and only != 'none':
    die(f'no replacement .dxil files in {rdir}' + (f' for {only}' if only else ''))
for h, blob in repl.items():
    if blob[:4] != b'DXBC' or struct.unpack_from('<I', blob, 24)[0] != len(blob):
        die(f'{h}.dxil is not a DXIL container')

# --- PE headers
if d[:2] != b'MZ':
    die('not a PE file')
pe = struct.unpack_from('<I', d, 0x3c)[0]
if d[pe:pe + 4] != b'PE\0\0':
    die('not a PE file')
nsec = struct.unpack_from('<H', d, pe + 6)[0]
osz = struct.unpack_from('<H', d, pe + 20)[0]
opt = pe + 24
if struct.unpack_from('<H', d, opt)[0] != 0x20b:
    die('not a 64-bit DLL')
image_base = struct.unpack_from('<Q', d, opt + 24)[0]
sect_align, file_align = struct.unpack_from('<II', d, opt + 32)
size_of_headers = struct.unpack_from('<I', d, opt + 60)[0]
dirs = opt + 112
sec_table = opt + osz
sections = []
for k in range(nsec):
    o = sec_table + 40 * k
    name = bytes(d[o:o + 8]).rstrip(b'\0').decode()
    vsize, va, rsize, roff = struct.unpack_from('<IIII', d, o + 8)
    sections.append((name, va, vsize, roff, rsize))
if any(s[0] == '.fsr4' for s in sections):
    die('this DLL is already patched')


def section_of_file(off):
    return next((s for s in sections if s[3] <= off < s[3] + s[4]), None)


def va_of_file(off):
    s = section_of_file(off)
    return image_base + s[1] + off - s[3]


data = next((s for s in sections if s[0] == '.data'), None)
if not data:
    die('no .data section')
dlo, dhi = data[3], data[3] + data[4]

# --- find each shader and its entry
found = []
pos = 0
while (pos := d.find(b'DXBC', pos)) >= 0:
    size = struct.unpack_from('<I', d, pos + 24)[0]
    h = bytes(d[pos + 4:pos + 20]).hex()
    if h in repl and pos + size <= len(d):
        ptr = struct.pack('<Q', va_of_file(pos))
        refs = []
        r = dlo
        while (r := d.find(ptr, r, dhi)) >= 0:
            refs.append(r)
            r += 1
        if len(refs) != 1 or struct.unpack_from('<Q', d, refs[0] - 8)[0] != size:
            die(f'shader {h}: expected one (size, pointer) entry, found {len(refs)}')
        found.append((h, pos, size, refs[0]))
    pos += 4
missing = sorted(set(repl) - {f[0] for f in found})
if missing:
    die('shaders not found in this DLL (another FSR version, or already patched?): ' + ', '.join(missing))

# --- the INT8 provider's GPU check (--any-gpu)
INT8_ISSUPPORTED = bytes.fromhex('4883ec48488bc24885d27454488d5424')   # AMD's 4.1.1.2740
unlock_at = None
if any_gpu:
    name = d.find(b'.?AVffxProvider_FSR4_Int8@@\0')
    if name < 0:
        die('no ffxProvider_FSR4_Int8 in this DLL')
    td_rva = va_of_file(name - 16) - image_base                     # RTTI type descriptor
    col, i = None, 0
    while (i := d.find(struct.pack('<I', td_rva), i + 1)) >= 0:     # complete object locator
        if i >= 12 and struct.unpack_from('<II', d, i - 12) == (1, 0):
            col = i - 12
            break
    vt = col is not None and d.find(struct.pack('<Q', va_of_file(col)))
    if not vt or vt < 0:
        die('the INT8 provider\'s vtable was not found')
    fn = struct.unpack_from('<Q', d, vt + 8 + 2 * 8)[0] - image_base   # slot 2: IsSupported
    s_ = next(s for s in sections if s[1] <= fn < s[1] + s[2])
    unlock_at = s_[3] + fn - s_[1]
    if bytes(d[unlock_at:unlock_at + 16]) != INT8_ISSUPPORTED:
        die('the INT8 provider\'s GPU check is not the expected code (another DLL version?)')

# --- patch
if unlock_at is not None:
    d[unlock_at:unlock_at + 3] = bytes.fromhex('b001c3')            # mov al, 1 ; ret
    print('INT8 provider: GPU check lifted (--any-gpu)')
appended = bytearray()
moved = []
for h, pos, size, ref in found:
    blob = repl[h]
    if len(blob) <= size:
        d[pos:pos + size] = blob + bytes(size - len(blob))
        struct.pack_into('<Q', d, ref - 8, len(blob))
        print(f'{h}: replaced in place ({size} -> {len(blob)} bytes)')
    else:
        while len(appended) % 16:
            appended.append(0)
        moved.append((h, ref, len(appended), len(blob), size))
        appended += blob

# Remove the signature (the certificate table sits at the end of the file and is not mapped).
sec_off, sec_size = struct.unpack_from('<II', d, dirs + 8 * 4)
if sec_off:
    if sec_off + sec_size != len(d):
        die('the signature is not at the end of the file')
    del d[sec_off:]
    struct.pack_into('<II', d, dirs + 8 * 4, 0, 0)

if moved:
    if sec_table + 40 * (nsec + 1) > size_of_headers:
        die('no room for another section header')
    last = max(sections, key=lambda s: s[1])
    va = -(-(last[1] + last[2]) // sect_align) * sect_align
    raw_end = max(s[3] + s[4] for s in sections)
    roff = -(-max(raw_end, len(d)) // file_align) * file_align
    rsize = -(-len(appended) // file_align) * file_align
    d += bytes(roff - len(d)) + appended + bytes(rsize - len(appended))
    o = sec_table + 40 * nsec
    d[o:o + 40] = struct.pack('<8sIIIIIIHHI', b'.fsr4', len(appended), va, rsize, roff, 0, 0, 0, 0, 0x40000040)
    struct.pack_into('<H', d, pe + 6, nsec + 1)
    struct.pack_into('<I', d, opt + 56, -(-(va + len(appended)) // sect_align) * sect_align)   # SizeOfImage
    struct.pack_into('<I', d, opt + 8, struct.unpack_from('<I', d, opt + 8)[0] + rsize)        # SizeOfInitializedData
    for h, ref, off, n, old in moved:
        struct.pack_into('<Q', d, ref - 8, n)
        struct.pack_into('<Q', d, ref, image_base + va + off)
        print(f'{h}: moved to .fsr4 ({old} -> {n} bytes)')

# PE checksum
struct.pack_into('<I', d, opt + 64, 0)
s = 0
for (w,) in struct.iter_unpack('<H', bytes(d) + (b'\0' if len(d) % 2 else b'')):
    s += w
    s = (s & 0xffff) + (s >> 16)
struct.pack_into('<I', d, opt + 64, ((s & 0xffff) + (s >> 16) & 0xffff) + len(d))

open(dst, 'wb').write(d)
print(f'wrote {dst} ({len(d)} bytes, sha256 {hashlib.sha256(d).hexdigest()[:16]}...)')
