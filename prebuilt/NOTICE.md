# Notice for the prebuilt shaders

The `.spv` files in this folder are modified versions of compute shaders from AMD's FSR 4.1.1
upscaler. They are not AMD's originals and are not provided or endorsed by AMD.

## Where they come from

- **Source file:** `amd_fidelityfx_upscaler_dx12.dll`, version 4.1.1.2740, exactly as published in
  AMD FidelityFX SDK 2.3.0 under `Kits/FidelityFX/signedbin/`
  (<https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK>, commit
  `60f4ea81909200d8542eca14dccb2628b763a9a3`; git blob
  `199de3a500a1d153b7e73fa5ca0adbd2a4ac1229`).
- **Translation:** the DLL's shaders as vkd3d-proton translated them to SPIR-V while a game ran
  (`VKD3D_SHADER_DUMP_PATH`).
- **Modification:** rewritten by `postpass_lds_vkd3d.py`, `zconst.py` and `pass11_stores.py` from this
  repository.
  Running `build_override.sh` on a matching dump reproduces these files byte for byte.
- **They fit only where Proton produces the same translation.** They were made on a Radeon
  RX 7800 XT with GE-Proton 11-7; on an RX 6900 XT the translation differs and these files give a
  wrong image. `ORIGINALS.sha256` lists the checksums of the translated shaders they were made
  from, and `../check_prebuilt.sh <dump>` compares a dump against it.

189 files. 90 are the prepass in every version (each lane of a quad finishes one word of the
model's input, with 12 exchanges between lanes instead of 32, `prepass_route.py`; since 2026-10-07, replacing the first prepass rewrite of 2026-10-05). 45 are model passes other than pass 11, in every version (rounding and clamping
between layers with the clamp first, `model_clamp.py`; output scaling in integers, `model_tail.py`;
added 2026-10-05). The other 54 are one for every normal version of the two shaders rewritten first: 48 of the FSR 4.1.1 postpass
(stores written in solid blocks through workgroup memory, one image at a time; since 2026-10-07 also integer rounding and clamping in its small network and its neighbor reads without branches) and 6 of model
pass 11 (always-zero z coordinate replaced by a constant; each row of its output stored
together). They were made from dumps of AMD's DLL running in a test program under Proton
(GE-Proton 11-7) in each combination that selects a different version; see
[`../docs/variants.md`](../docs/variants.md).

## Licenses

AMD's SDK license (`docs/license.md` in the repository above) lists
`Kits\FidelityFX\signedbin\amd_fidelityfx_upscaler_dx12.dll` among the files that are subject to
the following license, reproduced here as it requires:

> Copyright (C) Advanced Micro Devices, Inc.
> 
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
> 
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
> 
> THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

The modifications are made by scripts adapted from bbport
(<https://github.com/deadinside28/bloodborne_pc>, GPL-2.0-or-later). The files in this folder are
therefore distributed under the GNU General Public License, version 2 or later (see `LICENSE` in
the repository root), together with AMD's notice above. The scripts in this repository are the
source of the modifications.
