# Notice for the prebuilt Windows files

## `fsr4-overrides/*.dxil`

These are modified versions of compute shaders from AMD's FSR 4.1.1 upscaler, in DXIL form. They
are not AMD's originals and are not provided or endorsed by AMD.

- **Source file:** `amd_fidelityfx_upscaler_dx12.dll`, version 4.1.1.2740, exactly as published in
  AMD FidelityFX SDK 2.3.0 under `Kits/FidelityFX/signedbin/`
  (<https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK>, commit
  `60f4ea81909200d8542eca14dccb2628b763a9a3`; git blob
  `199de3a500a1d153b7e73fa5ca0adbd2a4ac1229`).
- **Modification:** the DLL's shaders, disassembled with Microsoft's DXC, rewritten by
  `dxil/postpass_lds_dxil.py`, `dxil/zconst_dxil.py` and `dxil/pass11_stores_dxil.py`, and assembled and signed with DXC again
  (`dxil/build_dxil_overrides.sh`).

AMD's SDK licence (`docs/license.md` in the repository above) lists
`Kits\FidelityFX\signedbin\amd_fidelityfx_upscaler_dx12.dll` among the files that are subject to
the following licence, reproduced here as it requires:

> Copyright (C) Advanced Micro Devices, Inc.
> 
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
> 
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
> 
> THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

The modifications are made by scripts adapted from bbport
(<https://github.com/deadinside28/bloodborne_pc>, GPL-2.0-or-later). The `.dxil` files are therefore
distributed under the GNU General Public License, version 2 or later (see `LICENSE` in the
repository root), together with AMD's notice above. The scripts are the source of the
modifications.

## `fsr4_overrides.addon64`

Built from `addon/fsr4_overrides.cpp` (GPL-2.0-or-later) by `build_addon.sh`, with:

- ReShade's add-on API headers, copyright Patrick Mours, BSD-3-Clause
  (<https://github.com/crosire/reshade>);
- the llvm-mingw toolchain's runtime libraries, linked statically: libc++, libunwind and
  compiler-rt (Apache-2.0 with LLVM exceptions) and the mingw-w64 runtime (Zope Public License 2.1
  and public domain) (<https://github.com/mstorsjo/llvm-mingw>).
