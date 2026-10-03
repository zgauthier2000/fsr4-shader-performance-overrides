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
- **Modification:** rewritten by `postpass_lds_vkd3d.py` and `zconst.py` from this repository.
  Running `build_override.sh` on a matching dump reproduces these files byte for byte.

| File | Shader | Change |
|---|---|---|
| `683038df6272d4db.spv` | FSR 4.1.1 postpass | stores written in rows through workgroup memory, one image at a time |
| `4d657fb0eed077d6.spv` | FSR 4.1.1 postpass, variant that also stores the exposure value | stores written in rows through workgroup memory, one image at a time |
| `e29847a84b6f746f.spv` | FSR 4.1.1 model pass 11 | always-zero z coordinate replaced by a constant |

## Licences

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
(<https://github.com/deadinside28/bloodborne_pc>, GPL-2.0-or-later). The files in this folder are
therefore distributed under the GNU General Public License, version 2 or later (see `LICENSE` in
the repository root), together with AMD's notice above. The scripts in this repository are the
source of the modifications.
