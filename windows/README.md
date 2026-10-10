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
  slower; see [Integrated GPUs](../docs/gpu-support.md#integrated-gpus-radeon-780m-and-similar).
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

   Expect two lines, one for pass 11 and one for the postpass.
4. Compare OptiScaler's upscaler time with the add-on file present and removed.

To undo it, delete the add-on file and the folder.

## What is prebuilt

`prebuilt/fsr4-overrides/` holds a replacement for every normal version of the two shaders in
AMD's DLL 4.1.1.2740: all 48 versions of the postpass and all 6 of model pass 11, each named after
the hash in the original shader's header. Which one a game uses depends on its output size, the
preset and how it sets up exposure and color space; see [shader variants](../docs/variants.md).

All 183 (54 until 2026-10-05, when the model passes' output-scaling rewrite and then the prepass rewrite were added) were built from the DLL's own copies of the shaders (`../dll/extract_shaders.py`, then
`dxil/build_dxil_overrides.sh`), validated and signed by Microsoft's DXC, and checked under
Proton: in each of the 48 combinations that select a different version, the upscaled image is
byte-for-byte identical to AMD's ([`../dll/test/run_all_variants.sh`](../dll/test/run_all_variants.sh)).
The versions for FSR's debug view are not covered; with the debug view on, AMD's own postpass runs.

## Another FSR 4 version

The replacements only fit DLL version 4.1.1.2740. For another build of the DLL, extract its
shaders and build replacements the same way; the scripts stop if a shader does not have the
structure they expect:

```
python3 ../dll/extract_shaders.py amd_fidelityfx_upscaler_dx12.dll shaders
DXC_DIR=/path/to/dxc dxil/build_dxil_overrides.sh shaders /path/to/fsr4-overrides
```

The add-on can also save the shaders a game creates: make an empty folder `fsr4-overrides\dump`
next to it and run the game with FSR 4 on.

## Building the add-on

`build_addon.sh` cross-compiles it from Linux with MinGW-w64 and ReShade's headers; see the
comments at its top. The build is reproducible: it produces the `prebuilt` file byte for byte.

## How the DXIL versions differ from the Linux ones

- The postpass keeps the values of its two float textures in registers and writes the textures
  one after the other, each through 12,288 bytes of shared memory (D3D12 allows a thread group
  32,768). The half-precision texture is written directly as in AMD's shader: sending it through
  shared memory as well measured no faster under vkd3d-proton.
- Pass 11 has the same two changes as on Linux: the always-zero z coordinate becomes a constant,
  and each row of its output is stored together (`dxil/pass11_stores_dxil.py`).

## Licence

The add-on and scripts are GPL v2 or later (see `../LICENSE`). The add-on follows ReShade's
"shader_replace" example by Patrick Mours (BSD-3-Clause OR MIT). The prebuilt `.dxil` files are
modified AMD shaders; see [`prebuilt/NOTICE.md`](prebuilt/NOTICE.md).
