#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# sdk_pass11.py <amd_fidelityfx_upscaler_dx12.dll of AMD FSR SDK 2.4.0> <out dir> <dxc dir> <dxilasm>
# (build_dxil_overrides.sh SDKP11=<that DLL>): AMD's own pass 11 of its FSR 4.1.2 RX 6000 model, taken from the game DLL of
# AMD's FSR SDK 2.4.0 (MIT license; AMD's notice ships in NOTICE.md), for the six INT8 pass 11 versions of the 4.1.1 DLL
# (3 output-size classes x normal / Ultra Performance weights). It computes the same output as AMD's 4.1.1 pass 11 and
# reads its weights in wider blocks. This repository carries no AMD code: the tool reads it from the DLL you give it.
# The SDK binds the scratch buffer at u13 and the weights at t21 in 8 x 4 thread groups; the 4.1.1 DLL uses u11, t18 and
# 64 x 1 x 1. Only those numbers are changed (the two handles, the two resource records, numthreads); everything else is
# AMD's code as compiled. Each result is written as <out>/<the 4.1.1 shader's hash>.dxil, replacing the file the builder
# made for that version, and checked against the expected SHA-256. Fails if the DLL is not SDK 2.4.0's or any check fails.
import sys, os, re, hashlib, struct, subprocess, tempfile
SDK_DLL = 'aad4fccccb29084a655f9a4f9f613bd22c8c03fb4a0f8840148cc6543b4ccace'      # Kits/FidelityFX/signedbin/amd_fidelityfx_upscaler_dx12.dll, FSR SDK v2.4.0 (4.1.2.4555)
SIX = [      # (4.1.1 shader hash = output name, SHA-256 of AMD's container in the SDK DLL, SHA-256 of the result)
    ('6cb24f36716688e11890a37b128ff84e', 'f7751856e2220a292ed50d07defdcb99b2609c6c6d0868da6ded7e9f64d04e93', 'bb0369f09204ad62c89b1df3f4df6f088e121b2a4cd845a4b7cb570d9bbb3729'),
    ('1941744520122a74c2a679385d5ad403', '636fbe361ae302c56d5d1b567caf8aff7edc2870cba45c6ea0f54ca1fc9822f7', 'dfa3c3f0a89a715651b5bd8fc7b93073b4a8aab5c47332eeff2c2b823e9d3ee4'),
    ('616f13c1865211ef6f958ae4fb21eb25', 'a6f91f53f128e03ddef345d610cb0e5419b501e9b8e0138750f3f58fa54db7ff', '3c6d3a65ad3a21dd6b65dbffacae73ebd485b5c1c3c8aec670cdd49a20e26c4e'),
    ('f0b3c3c7a787ee896886a310452010b4', 'cacd0edef0d31ea55b0297d1ac1b7c2ccf60a646af0c639b1d71fa078bac04cb', '13f5362a94d78378839e9dd1c9654b15dfb91aeedc2813d53e35069411fba356'),
    ('3b52762c8cfb77508b14680f13d0efae', '817a308c67f4938ecc236d988e7c505f59b6e33219173427bd77d94b21868845', 'b8cbc1b28b5d5fc7cdaa87ef478efc8de24a327e55314a57e6b4a34e3fc97186'),
    ('7fc508cf10455f421457107f36989100', 'f9ae5d42fa5a7a7ba1be06345aaa6a6936c89dd680d56fdf55688051e1be03df', '6ee3197c6115608333f3e65ca24cc36c94775677dcecf3f91dddb3b25e82ca58'),
]
def rebind(s):
    n = {}
    def sub(pat, rep, key):
        nonlocal s; s, k = re.subn(pat, rep, s); n[key] = k
    sub(r'(@dx\.op\.createHandle\(i32 57, i8 1, i32 0, i32 )13(, i1 false\))', r'\g<1>11\2', 'uav handle')
    sub(r'(@dx\.op\.createHandle\(i32 57, i8 0, i32 0, i32 )21(, i1 false\))', r'\g<1>18\2', 'srv handle')
    sub(r'(%struct\.ByteAddressBuffer\* undef, !"", i32 0, i32 )21(, i32 1,)', r'\g<1>18\2', 'srv record')
    sub(r'(%struct\.RWByteAddressBuffer\* undef, !"", i32 0, i32 )13(, i32 1,)', r'\g<1>11\2', 'uav record')
    sub(r'(!\d+ = !\{i32 )8, i32 4, i32 1(\})', r'\g<1>64, i32 1, i32 1\2', 'numthreads')
    bad = {k: v for k, v in n.items() if v != 1}
    if bad: sys.exit(f'sdk_pass11: expected one of each, found {bad}')
    return s
def main():
    if len(sys.argv) != 5: sys.exit(__doc__ or 'usage: sdk_pass11.py <SDK DLL> <out dir> <dxc dir> <dxilasm>')
    dll, out, dxc, asm = sys.argv[1:]
    d = open(dll, 'rb').read()
    if hashlib.sha256(d).hexdigest() != SDK_DLL: sys.exit(f'sdk_pass11: {dll} is not the game DLL of AMD FSR SDK 2.4.0')
    want = {a: (slot, b) for slot, a, b in SIX}; found = {}; i = 0
    for m in re.finditer(b'DXBC', d):
        j = m.start()
        if j < i: continue
        size = struct.unpack_from('<I', d, j + 24)[0]
        if not (64 < size < 8_000_000 and j + size <= len(d)): continue
        c = d[j:j + size]; i = j + size; h = hashlib.sha256(c).hexdigest()
        if h in want: found[h] = c
    if len(found) != 6: sys.exit(f'sdk_pass11: {len(found)} of the 6 pass 11 shaders found in {dll}')
    env = dict(os.environ, LD_LIBRARY_PATH=f'{dxc}/lib' + (':' + os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else ''))
    with tempfile.TemporaryDirectory() as w:
        for h, c in found.items():
            slot, expect = want[h]; dst = f'{out}/{slot}.dxil'
            if not os.path.exists(dst): sys.exit(f'sdk_pass11: {dst} missing (the builder made no pass 11 file for this version)')
            open(f'{w}/in.dxil', 'wb').write(c)
            ll = subprocess.run([f'{dxc}/bin/dxc', '-dumpbin', f'{w}/in.dxil'], capture_output=True, text=True, env=env, check=True).stdout
            open(f'{w}/out.ll', 'w').write(rebind(ll))
            subprocess.run([asm, f'{dxc}/lib/libdxcompiler.so', f'{w}/out.ll', f'{w}/out.dxil'], capture_output=True, env=env, check=True)
            r = open(f'{w}/out.dxil', 'rb').read()
            if hashlib.sha256(r).hexdigest() != expect: sys.exit(f'sdk_pass11: the result for {slot} differs from the expected one')
            open(dst, 'wb').write(r)
    print('AMD FSR SDK 2.4.0 pass 11: 6 versions in place (rebound to u11 / t18, 64 x 1 x 1)')
if __name__ == '__main__': main()
