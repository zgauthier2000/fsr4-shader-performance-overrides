# A patched upscaler DLL

`patch_upscaler_dll.py` writes a copy of AMD's `amd_fidelityfx_upscaler_dx12.dll` (FSR 4.1.1,
version 4.1.1.2740) with the faster shaders built in. Drop it in place of the original and FSR 4
uses them, with no launch option, no add-on and no override folder, on Windows and under Proton
alike.

## Download it

Four archives are attached to each release since `dll-2026-10-22` (the newest: [latest release](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/latest)), one per kind of graphics,
each with an exact and a lossy DLL (until `dll-2026-10-22` also a lossy2 DLL; since `dll-2026-10-29` `lossy` is that trained build, and the archives also hold the two Lite builds, `4.1.2l-exact` and `4.1.2l-lossy`: [the Lite builds](../docs/lite-builds.md)), AMD's notice and SHA-256 checksums, and each as a `.zip` and a much smaller `.7z` with the same
files. In `dll-2026-10-29`: [`fsr4.1.2-cyboman-rx7000-2026-10-29.7z`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-10-29/fsr4.1.2-cyboman-rx7000-2026-10-29.7z) for RX 7000 cards,
[`fsr4.1.2-cyboman-rx6000-2026-10-29.7z`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-10-29/fsr4.1.2-cyboman-rx6000-2026-10-29.7z) for RX 6000 cards,
[`fsr4.1.2-igpu-cyboman-rdna3-2026-10-29.7z`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-10-29/fsr4.1.2-igpu-cyboman-rdna3-2026-10-29.7z) for RDNA 3 / 3.5 graphics built into the processor
and for other makers' cards, and [`fsr4.1.2-igpu-cyboman-rdna2-2026-10-29.7z`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-10-29/fsr4.1.2-igpu-cyboman-rdna2-2026-10-29.7z) for the Steam Deck and
other RDNA2 built-in graphics (each also as a `.zip`; [which one](../docs/gpu-support.md#which-download-dll-2026-10-22-and-later)).
The exact DLLs were made by this script from AMD's original (SHA-256
`d0dcccc74a43c44ba435b7a369b456e0970d8a4464e4bd683119b374f2c9fb46`) and the shader sets `../windows/dxil/build_dxil_overrides.sh` builds with
these options (since `dll-2026-10-29`; every flavor also `INTCONV=direct`):

| Flavor | Options | Picture |
|---|---|---|
| RX 7000 (`r3`) | `PREPASS=hybrid PQ_ORDER=amd` | AMD's FSR 4.1.1 |
| RX 6000 (`r2`) | `DOT4=swap POSORDER=driver PREPASS=hybrid PQ_ORDER=driver` | AMD's FSR 4.1.2 for RX 6000 |
| integrated RDNA 3 (`igpu-r3`) | `PASS11=rows PREPASS=hybrid PQ_ORDER=amd` | AMD's FSR 4.1.1 |
| integrated RDNA2 (`igpu-r2`) | `DOT4=swap PASS11=rows POSORDER=driver PREPASS=hybrid PQ_ORDER=driver` | AMD's FSR 4.1.2 for RX 6000 |

(`dll-2026-10-22`: RX 7000 none, RX 6000 `DOT4=split PREPASS=0`, integrated RDNA 3 `PASS11=rows`, integrated RDNA2 `DOT4=split PASS11=rows`.)
They are patched with `--any-gpu --name 4.1.2-exact-<flavor>-build` and then given their release names with [`rename_dll.py`](rename_dll.py)
(`rename_dll.py <in> <out> <old name> <new name>`: it changes only the name and checks that every other byte stays the same). The
`lossy` DLLs (called lossy2 until `dll-2026-10-29`) and the two Lite builds of `dll-2026-10-29` are built with this project's local tools, which
are not in the repository yet; [`research/lossy2`](../research/lossy2/README.md) rebuilds the lossy2 DLLs of `dll-2026-10-22` byte for byte, reading the lossy DLL's
shader set back with `recover_set.py` (the patcher only takes AMD's own DLL). Install as the [front page](../README.md#quick-start) describes.

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
Since release `dll-2026-10-29` the released DLLs use `4.1.2-<exact|lossy>-<r3|r2|igpu-r3|igpu-r2>-cyboman`, for example
`4.1.2-exact-r3-cyboman` (RX 7000) or `4.1.2-lossy-igpu-r2-cyboman` (Steam Deck and other RDNA2 built-in graphics; `lossy` is the trained build
earlier releases called `lossy2`); in `dll-2026-10-22` they were `4.1.1-<exact|lossy|lossy2>-<flavor>-cyboman`; since `dll-2026-10-29` the Lite builds add `4.1.2l-exact-<flavor>-cyboman` and `4.1.2l-lossy-<flavor>-cyboman`; lossy, lossy2 and 4.1.2l-lossy change the image
([exact and lossy compared](../docs/exact-vs-lossy.md)). From `dll-2026-10-09` to `dll-2026-10-19` they were `4.1.1-cyboman`, `4.1.1-igpu-cyboman` and their `-lossy-` / `-lossy2-` forms; up to
release `dll-2026-10-07` there were four flavors with the names `4.1.1-r3-`, `-r2-`, `-r2c-` and `-ig-cyboman` ([earlier releases](../docs/changelog.md)).

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
output size, model, exposure and color-space setup that selects a different shader: 48
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
- **Never in online games or games with anti-cheat.** The DLL is modified code, and anti-cheat software can treat it as
  tampering. Single-player games only.

## When AMD ships a new version

Everything here was built against AMD's DLL version 4.1.1.2740, and the patcher refuses any other file. Two tools give a
first answer to "what would a new version need?":

- `inspect_dll.py <dll> <out dir>` prints the DLL's version, how many shader containers it holds and the FSR 4 network
  shaders by name, and extracts the named ones.
- `try_tools.py <dll> <work dir>` tries every one of this project's DXIL tools on every network shader of the DLL and
  prints, tool by tool, how many shaders it accepted and changed. It needs DXC (`DXC_DIR`). Each tool's reason for refusing
  a shader is kept in `report.json`.

Tried on FSR 4.0.2 (the DLL some games ship), the only other version at hand: frame skip's hook fits model passes 1 to 11,
and none of the speed rewrites fits, because that version lays out its buffers and thread groups differently (the postpass's
group is not 256x1x1, the prepass has no sixteen channel sums, the row sizes the tools know appear in few of its shaders).
Its weights are also different numbers in layers of the same size, so anything tuned against the network's behavior (the fold,
the lossy thresholds) would have to be measured again. A version that keeps 4.1.1's layout may be much closer; none has been
seen yet.

## License

The script is GPL v2 or later (see [`../LICENSE`](../LICENSE)). A DLL it writes is AMD's DLL,
which AMD's FidelityFX SDK license lists under MIT terms, with modified shaders from this
repository; [`../windows/prebuilt/NOTICE.md`](../windows/prebuilt/NOTICE.md) has AMD's notice and
the details. If you share a patched DLL, include that notice.
