# GPU and operating system support

[Back to the front page](../README.md)

| GPU | System | Status |
|---|---|---|
| Desktop RDNA3 (RX 7900, 7800, 7700, 7600) | Linux, Proton | measured on an RX 7800 XT: faster |
| Desktop RDNA3 | Windows | testers report large gains |
| RDNA3 integrated (Radeon 780M, 890M) | any | do not use the normal build (pass 11 is reported much slower there); the experimental `test-igpu.zip` is reported 2% faster than fsr4xyz's `4.1.1b` on a 780M |
| RDNA2 (RX 6000, Steam Deck) | any | AMD's DLL does not offer this FSR 4 there; the experimental `test-rdna2.zip` runs on Windows and fixes the shimmering in motion; testers report 2 to 3% less upscaler time than fsr4xyz's `4.1.1b` ([below](#rdna2-needs-one-more-change-the-dot-products)) |
| RDNA4 (RX 9000) | any | not covered: it runs a different FSR 4 model; see [RDNA4](rdna4.md) |

## Windows

Several testers on Windows with Radeon RX 7000 graphics cards report large improvements with the
first version of these rewrites, nearly as large as on Linux, so AMD's Windows driver has the
same slow store pattern. The phased version has also been run on Windows with an RX 7800 XT,
with about the same result as the first version there.

Two ways to use them on Windows:

- the [patched DLL](../dll/README.md): replace `amd_fidelityfx_upscaler_dx12.dll`, nothing else;
- a ReShade add-on in [`windows/`](../windows) that swaps the same two shaders when AMD's DLL creates
  them. See [`windows/README.md`](../windows/README.md).

Both were verified byte for byte against AMD's output under Proton. On integrated GPUs, see below.

## Integrated GPUs (Radeon 780M and similar)

**Do not use these rewrites on an integrated GPU for now.** A tester who ran the two rewrites
separately on an RDNA3 integrated GPU (with the 2026-10-03 release) reports:

- **the pass 11 rewrite makes the upscaler much slower;**
- **the postpass rewrite makes no difference:** it behaves like AMD's shader.

So on these GPUs there is nothing to gain and pass 11 costs a lot; AMD's original shaders are the
right choice. This has not been reproduced here (only a Radeon RX 7800 XT was available), and
earlier advice on this page to use pass 11 alone on integrated GPUs was a guess that turned out
wrong.

What is known about why:

- **Pass 11.** The rewrite lets the compiler unroll the pass's loops, which makes it faster on a
  graphics card but five times larger (about 31 KB of code instead of 6 KB, as Mesa compiles it
  for a Radeon 780M). Whether the size is what hurts on an integrated GPU is not known.
- **Postpass.** An integrated GPU's memory system evidently does not suffer from the scattered
  stores the way a graphics card does, so there is nothing for the rewrite to remove.
- **The 2026-10-04 release has a different pass 11** (it also stores its output in whole rows, and
  reads far less memory). It has not been tested on an integrated GPU; the pass 11-only test
  build of that release is the way to find out.

**An experimental build for integrated GPUs is available for testing.** Its pass 11 keeps AMD's
loops, so the pass stays small (6.5 KB as compiled for a Radeon 780M), and only stores each row of
its output together, which cuts the memory the pass reads to about a quarter. It is attached to
the [release `dll-2026-10-04.5`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-04.5)
as `test-igpu.zip` (AMD's GPU check is lifted in it, as in every released DLL). Its output is
byte-identical to AMD's.

**First report (2026-10-04):** Radeon 780M (Ryzen 7 8845HS), Windows 11, Cyberpunk 2077, 1080p
Balanced, OptiScaler 0.9.5-pre4, same spot: fsr4xyz's `4.1.1b` 5.15 ms and 47.8 FPS on average;
the integrated-GPU build 5.04 ms and 48.5 FPS (-2%). So this build is no longer slower on an
integrated GPU, unlike the normal one, but the gain is small. It was compared with `4.1.1b`, which is
treated as equal in speed to AMD's shaders (see [RDNA2](#rdna2-needs-one-more-change-the-dot-products)). More reports are welcome: please compare the upscaler time with the DLL you
used before and report both. On Linux, the same pass 11 can be built with
`PASS11=rows ./build_override.sh <dump>`.

On Windows with Radeon RX 7000 graphics cards (not integrated GPUs), testers report large
improvements with the first version, and one tester with an RX 7800 XT saw no difference between
the first and the phased version. That is expected: the DXIL version that Windows uses was never
limited the same way (it already ran 8 waves per SIMD), and under vkd3d-proton its postpass only
went from 0.72 ms to 0.67 ms.

To test on your own GPU, compare OptiScaler's upscaler time, frame rate uncapped, in four runs. A DLL with
only one of the two rewrites is built with `dll/patch_upscaler_dll.py --only pass11` or
`--only postpass`.

| Run | Linux (launch option) | Patched DLL |
|---|---|---|
| AMD's shaders | no `VKD3D_SHADER_OVERRIDE` | AMD's original DLL |
| Both rewrites | the `prebuilt/` folder | `patch_upscaler_dll.py` |
| Pass 11 only | a copy of `prebuilt/` without `683038df6272d4db.spv` and `4d657fb0eed077d6.spv` | `patch_upscaler_dll.py --only pass11` |
| Postpass only | a copy of `prebuilt/` without `e29847a84b6f746f.spv` | `patch_upscaler_dll.py --only postpass` |

At 1080p output or below, the files in `prebuilt/` do not apply; build your own with
`build_override.sh`, using `PASS11=0` or `POSTPASS=0` to leave one rewrite out.

Please report the results with the GPU, the operating system and driver (Mesa version or AMD
driver), the game, the output resolution and FSR mode.

## RDNA2 and other GPUs that FSR 4 refuses (experimental)

AMD's DLL decides for itself which GPUs get FSR 4. It contains two versions, each with its own
check:

- the FP8 version needs the driver to report FP8 matrix multiplication and a discrete GPU, which in
  practice means RDNA4;
- the INT8 version (the one this repository speeds up) reads the GPU's chip family from AMD's
  driver and only accepts family 0x91, desktop RDNA3 (RX 7900, 7800, 7700, 7600). It refuses RDNA2
  (RX 6000), RDNA3 integrated GPUs (Radeon 780M, 890M) and other vendors.

The INT8 version's shaders themselves are plain Direct3D 12 (Shader Model 6.6; packed int8 and
half-precision dot products) and need no RDNA3-only feature. `patch_upscaler_dll.py --any-gpu`
makes the INT8 version's check always answer yes, so FSR 4 is offered on those GPUs too. Under
Proton on an RX 7800 XT the result is byte-for-byte identical to AMD's DLL, but **it has not been
tried on any GPU the check refuses**: whether FSR 4 then runs correctly, and how fast, is up to
that GPU and its driver. Do not use it on RDNA4, where both versions would then report support.

**Since release `dll-2026-10-04.5` every released DLL has the check lifted**, including the main
one, so there are three builds in all: desktop RDNA3, integrated GPUs and RDNA2. On desktop RDNA3
the lifted check changes nothing.

### RDNA2 needs one more change: the dot products

The [fsr4xyz](https://github.com/the3rdparty1917/fsr4xyz) project, which fixes this version of
FSR 4 for RDNA2 on Windows, found that the postpass ghosts on RDNA2 unless its int8 dot products
are written differently: AMD's shader adds each product onto a running total inside the
instruction, and their version computes each product alone and adds it afterwards. The result is
the same number, so the difference can only matter to the driver, which evidently mishandles the
accumulating form on RDNA2. Their DLL also lifts the same GPU check, which confirms that lifting
it is what RDNA2 needs.

The postpass rewrite in this repository keeps AMD's accumulating form, so the plain `--any-gpu`
builds would be expected to ghost on RDNA2. `windows/dxil/dot4_split_dxil.py` (build option
`DOT4=split`) applies the same idea to the rewritten postpass; it is an independent
implementation on AMD's shaders, with no code from that project. On an RX 7800 XT the output is
byte-identical to AMD's in all 48 shader combinations and the pass is as fast as without it.

**Result on RDNA2 (2026-10-04):** the build with this change, `test-rdna2.zip`, fixes the
shimmering in motion. So the accumulating dot product is the cause, and the rewritten postpass
and pass 11 work on RDNA2 once it is gone. 
**First speed reports from testers (2026-10-04, release `dll-2026-10-04.5`)**, OptiScaler's
upscaler time:

| GPU | Game | Render to output | Before | `4.1.1-cyboman-r2` | Change |
|---|---|---|---|---|---|
| RX 6900 XT | Final Fantasy VII Rebirth | 1920x1080 to 3840x2160 | 3.79 ms, 66.6 FPS (a DLL reporting `4.1.1`) | 2.70 ms, 73.2 FPS | -29% |
| RX 6900 XT (same tester) | Final Fantasy VII Rebirth | 1280x720 to 2560x1440 | 1.38 ms, 93.1 FPS (a DLL reporting `4.1.1`) | 1.23 ms, 92.8 FPS | -11% |
| RX 6800 | Control Resonant | 1707x960 to 2560x1440 | 1.96 ms, 73.7 FPS (fsr4xyz `4.1.1b`) | 1.92 ms, 73.2 FPS | -2% |
| RX 6700 XT | not stated | not stated | 2.46 ms (not stated) | 2.38 ms | -3% |

How to read these:

- **`4.1.1b` is treated as equal in speed to AMD's `4.1.1`.** Its shader changes (the dot-product
  form and a few coordinate clamps) leave the amount of work the same, so a comparison against
  either counts as a comparison against AMD's shaders. This is an assumption from reading the
  shaders, not a measurement.
- On that basis the gain on RDNA2 so far ranges from 2% to 29%: 29% at 4K output, and 2% and 11%
  at 1440p.
- **The gain shrinks faster than the pixel count.** The same RX 6900 XT in the same game saves
  1.09 ms at 4K and 0.15 ms at 1440p. With 44% of the pixels, a proportional saving would be about
  0.48 ms. One explanation that fits, not verified: the rewrites remove a memory penalty from
  sparse image writes, and at 1440p the postpass's images (about 29 MB each) fit in these cards'
  128 MB on-chip cache, where that penalty is small, while at 4K (66 MB each) they do not.
- The two 4K screenshots differ in one sharpening setting (the override was on in the "before"
  one), so treat the 29% as approximate. The 1440p pair has sharpening off in both.
- These are single readings from testers' screenshots, not repeated runs.

**What did not fix it:** a lower bound of 0.8 on the postpass's history weight (the share of the
previous frame in each output pixel), which was suggested as a fix. It looks bad in motion; see
[history clamp](../research/history-clamp).

The builds are attached to the [release `dll-2026-10-04.5`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-04.5):

| File | Contents |
|---|---|
| `test-rdna2.zip` | **for RDNA2, fixes the shimmering:** check lifted, both rewrites, and the postpass's dot products split (see above) |
| `amd_fidelityfx_upscaler_dx12.dll` | the main DLL for desktop RDNA3: check lifted, both rewrites |
| `test-igpu.zip` | for integrated GPUs: check lifted, postpass rewrite and the compact pass 11 ([above](#integrated-gpus-radeon-780m-and-similar)) |

Other combinations (check lifted with AMD's shaders unchanged, or with one rewrite only) are built
with `dll/patch_upscaler_dll.py --any-gpu --only none|pass11|postpass`.

If you try them, please report your GPU, Windows or Linux and driver version, the game, whether FSR
4 starts and looks right, and OptiScaler's upscaler time for each.
