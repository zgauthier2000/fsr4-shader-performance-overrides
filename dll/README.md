# A patched upscaler DLL

`patch_upscaler_dll.py` writes a copy of AMD's `amd_fidelityfx_upscaler_dx12.dll` (FSR 4.1.1,
version 4.1.1.2740) with the faster shaders built in. Drop it in place of the original and FSR 4
uses them, with no launch option, no add-on and no override folder, on Windows and under Proton
alike.

## Download it

A patched DLL is attached to the [release `dll-2026-10-06`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-06), with AMD's notice and
SHA-256 checksums. It was made by this script from AMD's original (SHA-256
`d0dcccc74a43c44ba435b7a369b456e0970d8a4464e4bd683119b374f2c9fb46`), and running the script on that
file with `--any-gpu --name 4.1.1-r3-cyboman` reproduces it exactly. Install it as described below, from step 1 under "Then, in the game
folder".

## Make the DLL

You need Python 3 and AMD's DLL, version 4.1.1.2740 (for example the one that ships with
OptiScaler, or AMD's from the FidelityFX SDK 2.3.0). On Windows, run it from a command prompt in
this folder; on Linux, from a terminal:

```
python3 patch_upscaler_dll.py amd_fidelityfx_upscaler_dx12.dll amd_fidelityfx_upscaler_dx12.patched.dll
```

It prints each shader it replaced. `--only pass11` or `--only postpass` (before the file names)
builds in just one of the two rewrites, to find out which one helps on your GPU; see
[Integrated GPUs](../docs/gpu-support.md#integrated-gpus-radeon-780m-and-similar).

`--any-gpu` (experimental) also lifts the GPU check AMD's DLL applies to the INT8 version of
FSR 4, which otherwise only runs on desktop RDNA3; `--only none` with it leaves the shaders as
AMD's. See [RDNA2 and other GPUs](../docs/gpu-support.md#rdna2-and-other-gpus-that-fsr-4-refuses-experimental).
Not for RDNA4. **All released DLLs are built with it** since release `dll-2026-10-04.5`.

`--name <text>` changes the version name the DLL reports ("4.1.1" in AMD's), which is what
OptiScaler displays, so that a patched DLL can be told from AMD's and the builds from each other.
The released DLLs use `4.1.1-r3-cyboman` (desktop RDNA3), `4.1.1-ig-cyboman` (integrated GPUs)
`4.1.1-r2-cyboman` (RDNA2), `4.1.1-r2c-cyboman` (RDNA2 with the compact pass 11, a test
build), `4.1.1-r2h-cyboman` (RDNA2 with AMD's postpass at 1080p output and below, a test build) and `4.1.1-r3-lossy-cyboman` (the opt-in build that changes the image; `4.1.1-r2-lossy-cyboman`,
`4.1.1-r2c-lossy-cyboman` and `4.1.1-ig-lossy-cyboman` for the other GPUs; see
[`research/lossy`](../research/lossy)). The GPU tag comes before `cyboman` since release
`dll-2026-10-05.4`, so that it stays visible in OptiScaler's closed dropdown; earlier releases
have it last (`4.1.1-cyboman-r3`). Keep `4.1.1` at the start
in case a front end reads the name as a number. The file version in the DLL's properties stays
4.1.1.2740.

Then, in the game folder (wherever
`amd_fidelityfx_upscaler_dx12.dll` is, often next to OptiScaler):

1. Rename the original to `amd_fidelityfx_upscaler_dx12.dll.orig` and keep it.
2. Copy the patched DLL there as `amd_fidelityfx_upscaler_dx12.dll`.
3. Compare OptiScaler's upscaler time with the original and the patched DLL. In some games that
   number is only reliable with the frame rate uncapped.

To undo it, put the original back.

The script refuses any other DLL (another FSR version, or one it has already patched), and leaves
the input file untouched.

## What it changes

The replacement shaders are the DXIL files of the Windows add-on,
[`../windows/prebuilt/fsr4-overrides`](../windows/prebuilt/fsr4-overrides): the phased postpass
and model pass 11, in every normal version the DLL contains (48 and 6; see
[shader variants](../docs/variants.md)), so the speedup does not depend on how a game sets FSR up. Inside the DLL the shaders
are plain DXIL containers, each described by a size and a pointer:

- A replacement that is no larger than AMD's shader is written in place.
- A larger one (nearly all 183, in the current version) goes into a new section, `.fsr4`, at the end of
  the file, and its size and pointer are updated.

Nothing else in the DLL changes. AMD's digital signature does not survive the change, so the
script removes it (and recomputes the PE checksum). Neither the DLL nor AMD's FidelityFX loader
checks the signature, so it loads like the original.

## How it was tested

[`test/run_dll_matrix.sh`](test/run_dll_matrix.sh) runs AMD's real DLL under Proton in a small
FSR 4 test program, first unchanged and then patched, for seven output sizes and ratios, and
compares the upscaled images byte for byte. A shader dump of each patched run confirms that the
patched postpass actually ran.

Result (GE-Proton 11-7, Radeon RX 7800 XT, Mesa 26.2.3): identical in all seven configurations,
with the patched postpass running in each.

| Render size | Output size | Patched DLL against AMD's |
|---|---|---|
| 2560x1440 | 3840x2160 | identical |
| 2260x1272 | 3840x2160 | identical |
| 1920x1080 | 3840x2160 | identical |
| 1280x720 | 3840x2160 | identical |
| 1706x960 | 2560x1440 | identical |
| 1280x720 | 1920x1080 | identical |
| 640x360 | 1920x1080 | identical |

[`test/run_all_variants.sh`](test/run_all_variants.sh) does the same for every combination of
output size, model, exposure and colour-space setup that selects a different shader: 48
combinations, all identical, with both replaced shaders confirmed running in each.

## Things to know

- **On Windows,** testers with Radeon RX 7000 graphics cards report large improvements with the
  first version of these rewrites, and the phased version (what this DLL contains) has been run on
  Windows with an RX 7800 XT with about the same result. Measure before and after on your setup.
- **Integrated GPUs:** on RDNA3 integrated GPUs both versions are reported slower than AMD's; see
  [Integrated GPUs](../docs/gpu-support.md#integrated-gpus-radeon-780m-and-similar) before using it there.
- **On Linux, the launch option is slightly faster.** vkd3d-proton translates these DXIL shaders
  into slightly slower code than the hand-written SPIR-V overrides: the postpass takes 0.67 ms at
  4K against 0.60 ms. The patched DLL is simpler to set up; the
  [launch option](../docs/linux.md#quick-start-the-prebuilt-files) is the faster choice. Using both
  does no harm: the override files only match AMD's original shaders, so they are ignored.
- **Game and OptiScaler updates** may put the original DLL back.
- **Online games.** The DLL is modified code; use your own judgement in games with anti-cheat.

## Licence

The script is GPL v2 or later (see [`../LICENSE`](../LICENSE)). A DLL it writes is AMD's DLL,
which AMD's FidelityFX SDK licence lists under MIT terms, with modified shaders from this
repository; [`../windows/prebuilt/NOTICE.md`](../windows/prebuilt/NOTICE.md) has AMD's notice and
the details. If you share a patched DLL, include that notice.
