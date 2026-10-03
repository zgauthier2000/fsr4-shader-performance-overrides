# Windows: a ReShade add-on (experimental)

On Linux the overrides are loaded by vkd3d-proton. On Windows there is no such option, so this
folder does the same job with a [ReShade](https://reshade.me) add-on: when AMD's FSR 4.1.1 DLL
creates its compute pipelines, the add-on swaps two of the shaders for the faster versions. AMD's
DLL stays untouched.

## Status

- **Tested:** AMD's real FSR 4.1.1 DLL, ReShade 6.8.0 and this add-on, run under Proton on Linux
  (GE-Proton 11-7, Radeon RX 7800 XT). The add-on loads and replaces both shaders, and the upscaled
  image is byte-for-byte identical to the run with AMD's own shaders in all seven configurations of
  [`test/run_matrix.sh`](test/run_matrix.sh): 4K, 1440p and 1080p output at ratios from 1.5 to 3.0.
  Translated by vkd3d-proton, the replacement postpass takes 0.67 ms at 4K in a standalone
  benchmark, against 2.1 ms for AMD's (the Linux override: 0.60 ms).
- **On Windows:** testers with Radeon RX 7000 graphics cards report large improvements with the
  first version of these rewrites, nearly as large as on Linux, so AMD's Windows driver has the
  same slow store pattern. The phased version has been run on Windows with an RX 7800 XT, with
  about the same result as the first version. On RDNA3 integrated GPUs both versions are reported
  slower; see [Integrated GPUs](../README.md#integrated-gpus-radeon-780m-and-similar).
- **The add-on itself** (as opposed to the [patched DLL](../dll)) is built with MinGW, not MSVC.
  Measure before and after, and please report what you find.

## What you need

- A D3D12 game where FSR 4.1.1 with the INT8 model is running (for example through OptiScaler with
  `amd_fidelityfx_upscaler_dx12.dll` 4.1.1.2740) on an RDNA3 card.
- ReShade **with full add-on support** installed for that game.

Do not use it in games with anti-cheat: ReShade with add-on support is DLL injection.

## Install

1. Copy `prebuilt/fsr4_overrides.addon64` and the `prebuilt/fsr4-overrides` folder next to
   ReShade's DLL in the game folder (where `ReShade.ini` is).
2. Start the game and enable FSR 4.
3. Open `ReShade.log` in the game folder. A working install shows lines like

   ```
   [FSR 4 shader overrides] fsr4_overrides: replacing compute shader 1941744520122a74c2a679385d5ad403
   ```

   Expect two lines, one for pass 11 and one for the postpass. If only one appears, your game uses
   a postpass variant that is not prebuilt; see below.
4. Compare OptiScaler's upscaler time with the add-on file present and removed.

To undo it, delete the add-on file and the folder.

## What is prebuilt

Replacements are named after the hash in the original shader's container header.

| File in `fsr4-overrides/` | Replaces | Output | Model | Run end to end |
|---|---|---|---|---|
| `1941744520122a74c2a679385d5ad403.dxil` | pass 11 | above 1080p | Native AA to Performance | yes |
| `f0b3c3c7a787ee896886a310452010b4.dxil` | pass 11 | above 1080p | Ultra Performance | yes |
| `6cb24f36716688e11890a37b128ff84e.dxil` | pass 11 | 1080p or below | Native AA to Performance | yes |
| `3b52762c8cfb77508b14680f13d0efae.dxil` | pass 11 | 1080p or below | Ultra Performance | yes |
| `440afc0eb4a57f115596ea2564d3dc6b.dxil` | postpass, reads an auto-exposure texture | above 1080p | Native AA to Performance | yes |
| `53b16ae473cf6c59778672c834cfc8a0.dxil` | postpass, same variant | above 1080p | Ultra Performance | yes |
| `5d195c84c2de56863a0b926747f0bef3.dxil` | postpass, same variant | 1080p or below | Native AA to Performance | yes |
| `f6496a6da2dadbee04a221be9e325c59.dxil` | postpass, same variant | 1080p or below | Ultra Performance | yes |
| `cbe597c540bef208e6ce03232d5ddc8b.dxil` | postpass, plain variant | above 1080p | Native AA to Performance | no |
| `9d85178a424650c483c6ebe7ade7ba19.dxil` | postpass, also stores the exposure value | above 1080p | Native AA to Performance | no |

All ten are validated and signed by Microsoft's DXC. "Run end to end" means the file was exercised
by the Proton test described under Status with a byte-identical result. The last two come from
games' shader dumps (the Linux overrides for the same two variants are in use and verified); in
DXIL form they were only built and validated, because the test program does not trigger those
variants.

Pass 11 does not depend on the game. The postpass does: which variant a game uses depends on how
it sets FSR up, so a game may need a variant that is not listed.

## If your game's variant is not prebuilt

1. Create an empty folder `fsr4-overrides\dump` next to the add-on and run the game with FSR 4 on.
   The add-on saves every FSR 4 compute shader the game creates into it.
2. On Linux or WSL, with Microsoft's [DXC](https://github.com/microsoft/DirectXShaderCompiler/releases)
   Linux release unpacked somewhere:

   ```
   DXC_DIR=/path/to/dxc dxil/build_dxil_overrides.sh /path/to/dump /path/to/fsr4-overrides
   ```

3. Remove the `dump` folder again.

On Linux a vkd3d-proton shader dump works as the input folder too, since it contains the DXIL.

## Building the add-on

`build_addon.sh` cross-compiles it from Linux with MinGW-w64 and ReShade's headers; see the
comments at its top. The build is reproducible: it produces the `prebuilt` file byte for byte.

## How the DXIL versions differ from the Linux ones

- The postpass keeps the values of its two float textures in registers and writes the textures
  one after the other, each through 12,288 bytes of shared memory (D3D12 allows a thread group
  32,768). The half-precision texture is written directly as in AMD's shader: sending it through
  shared memory as well measured no faster under vkd3d-proton.
- Pass 11 is the same change as on Linux: the always-zero z coordinate becomes a constant.

## Licence

The add-on and scripts are GPL v2 or later (see `../LICENSE`). The add-on follows ReShade's
"shader_replace" example by Patrick Mours (BSD-3-Clause OR MIT). The prebuilt `.dxil` files are
modified AMD shaders; see [`prebuilt/NOTICE.md`](prebuilt/NOTICE.md).
