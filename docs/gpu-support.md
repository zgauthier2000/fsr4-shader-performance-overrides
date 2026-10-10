# GPU and operating system support

[Back to the front page](../README.md)

| GPU | System | Status |
|---|---|---|
| Desktop RDNA3 (RX 7900, 7800, 7700, 7600) | Linux, Proton | measured on an RX 7800 XT: faster |
| Desktop RDNA3 | Windows | testers report large gains |
| RDNA3 integrated (Radeon 780M, 890M) | any | do not use the normal build (pass 11 is reported much slower there); the experimental `test-igpu.zip` is reported 2% faster than fsr4xyz's `4.1.1b` on a 780M |
| RDNA2 (RX 6000, Steam Deck) | any | AMD's DLL does not offer this FSR 4 there; the experimental `test-rdna2.zip` runs on Windows and fixes the shimmering in motion; testers report about 30% less upscaler time at 4K, 19% at 3440x1440 and 1 to 11% at 1440p and below ([below](#rdna2-needs-one-more-change-the-dot-products)) |
| RDNA4 (RX 9000) | any | not covered: it runs a different FSR 4 model; see [RDNA4](rdna4.md) |

## Which download (dll-2026-10-09 and later)

Since release `dll-2026-10-09` there are two downloads instead of a file per GPU family:

| Download | Version name shown | For | What differs |
|---|---|---|---|
| [`fsr4.1.1-cyboman.zip`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/latest/download/fsr4.1.1-cyboman.zip) | `4.1.1-cyboman`, `4.1.1-lossy-cyboman` | RX 7000 and RX 6000 cards, desktop and laptop | pass 11 unrolled (fastest on these cards) |
| [`fsr4.1.1-igpu-cyboman.zip`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/latest/download/fsr4.1.1-igpu-cyboman.zip) | `4.1.1-igpu-cyboman`, `4.1.1-igpu-lossy-cyboman` | integrated Radeon graphics, handhelds, and small RX 6000 chips if the first is slow there | pass 11 with its loops kept (small code) |

Both carry what used to be the separate RX 6000 change: the postpass's dot products in the split form
([below](#rdna2-needs-one-more-change-the-dot-products)). On an RX 7800 XT under Proton the split form times the same as AMD's
(0.65 to 0.66 ms at 4K either way, both slot orders), which is expected there: vkd3d-proton translates both forms into the same
code. **On Windows with an RX 7000 card the split form has not been timed.** The former `test-rdna2` build is now the first zip,
the former `test-rdna2-compact` and `test-igpu` builds are the second.

The Windows postpass also changed in this release: all three of its images now go through shared memory, the recurrent one as it is
computed. Compiled with Mesa's driver for other chips (not run), it keeps 16 waves on RDNA2, Navi 33 and the Steam Deck's chip, like
AMD's own; RDNA3 runs it at 16 waves where the previous DLL had 20, and is faster all the same (0.66 against 0.69 to 0.90 ms at 4K
on the RX 7800 XT). The sections below describe the builds up to release `dll-2026-10-07` and the reports gathered with them.

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
the [release `dll-2026-10-07`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-07)
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
**Speed reports from testers (2026-10-04 and 2026-10-05)**, OptiScaler's upscaler time, sorted by
output size. "Before" is the DLL named in brackets; the patched DLL in every row is
`test-rdna2.zip` (`4.1.1-r2-cyboman`), not the compact test build.

| GPU | Game | Render to output | Before | Patched DLL | Change |
|---|---|---|---|---|---|
| RX 6900 XT, Linux | Ready or Not | 2258x1271 to 3840x2160 | 3.79 ms, 134.5 FPS (`4.1.1b`) | 2.57 ms, 153.7 FPS | -32% |
| RX 6900 XT, Linux | Final Fantasy VII Rebirth | 1920x1080 to 3840x2160 | 3.79 ms, 66.6 FPS (`4.1.1`) | 2.70 ms, 73.2 FPS | -29% |
| RX 6900 XT | S.T.A.L.K.E.R. 2 | 2292x960 to 3440x1440 | 2.22 ms, 123.3 FPS (`4.1.1b`) | 1.79 ms, 124.4 FPS | -19% |
| RX 6900 XT, Linux | Final Fantasy VII Rebirth | 1280x720 to 2560x1440 | 1.38 ms, 93.1 FPS (`4.1.1`) | 1.23 ms, 92.8 FPS | -11% |
| RX 6750 XT | Mafia: The Old Country | 2560x1440 to 2560x1440 | 2.31 ms, 38.4 FPS (`4.1.1b`) | 2.22 ms, 43.9 FPS | -4% |
| RX 6750 XT | Mafia: The Old Country | 1707x960 to 2560x1440 | 2.17 ms (`4.1.1b`) | 2.13 ms | -2% |
| RX 6800 | Control Resonant | 1707x960 to 2560x1440 | 1.96 ms, 73.7 FPS (`4.1.1b`) | 1.92 ms, 73.2 FPS | -2% |
| RX 6700 XT | not stated | not stated | 2.46 ms (not stated) | 2.38 ms | -3% |
| RX 6600 | Clair Obscur: Expedition 33 | 1281x721 to 1920x1080 | 2.24 ms, average 2.26 (`4.1.1b`) | 2.18 ms, average 2.22 | -2 to -3% |
| RX 6600 | Code Vein 2 | 1287x724 to 1920x1080 | 2.43 ms, 48.4 FPS (`4.1.1b`) | 2.41 ms, 49.3 FPS | -1% |

Other measurements:

| Setup | Before | After | Change |
|---|---|---|---|
| RX 6900 XT, Linux, Final Fantasy VII Rebirth, 1080p to 4K: the patched DLL against Linux override files built from the tester's own dump | 2.70 ms (DLL) | 2.68 ms (override files) | -1% |
| GPU not shown, Sifu (Direct3D 11 through OptiScaler's Direct3D 12 path), 1920x1080 to 3840x2160 | 9.36 ms, average 9.71 (`4.1.1b`) | 9.48 ms, average 9.23 | none measurable |

How to read these:

- **`4.1.1b` is treated as equal in speed to AMD's `4.1.1`.** Its shader changes (the dot-product
  form and a few coordinate clamps) leave the amount of work the same, so a comparison against
  either counts as a comparison against AMD's shaders. This is an assumption from reading the
  shaders, not a measurement. The reports are consistent with it: on an RX 6900 XT at 4K, one
  tester measured 3.79 ms with `4.1.1b` and another 3.79 ms with `4.1.1`.
- **The gain follows the output size.** About 30% at 4K (two testers, two games, 1.1 to 1.2 ms
  saved), 19% at 3440x1440, 11% and less at 2560x1440, and 1 to 3% at 1080p.
- **At 1440p and below the rewrites do little on RDNA2.** That holds on cards with very different
  amounts of on-chip cache (RX 6600 to RX 6900 XT), so the earlier guess that a large cache hides
  the problem at 1440p does not explain it. Why the saving falls off faster than the pixel count
  is not known.
- Frame rates moved only where the time saved was large (Ready or Not at 4K: 134.5 to 153.7 FPS).
  The Mafia pair at native 1440p differs by more than the upscaler time can account for, so its
  frame rates were probably not taken at the same spot.
- The two Final Fantasy VII Rebirth 4K screenshots differ in one sharpening setting (the override
  was on in the "before" one), so treat that 29% as approximate.
- On an RDNA2 card the Linux override files and the DLL are equally fast. On RDNA3 the override
  route is a little faster.
- The Sifu result is from a much slower setup (8 ms in FSR itself at 4K); nothing can be read
  from it without knowing the GPU.
- These are single readings from testers' screenshots, not repeated runs.

**On Linux with RDNA2, build the override files from your own dump (2026-10-05).** The tester
with the RX 6900 XT gets a darker image with the prebuilt override files, and a correct image with
files built by `build_override.sh` from a dump of their own game, on the same Proton version as the
prebuilt files were made with. The rewrite itself is therefore fine on RDNA2; what does not carry
over is Proton's translation of AMD's shaders, which the prebuilt files (made on an RX 7800 XT)
are tied to. The tester's dump confirms it: all four of their dumped shaders (two postpass
versions, two of pass 11) have different checksums from the same shaders dumped on the RX 7800 XT,
while on the RX 7800 XT the dumps are identical across three different programs.

**What differs is one thing** (from the tester's dumped postpass, compared instruction by
instruction with the RX 7800 XT's): where the shader finds two values in its root constants, the
offsets of its two descriptor tables. In the RX 7800 XT's translation they are at bytes 8 and 12;
in the tester's, at bytes 108 and 112, after 25 more words. Everything else is identical: the same
6,129 instructions. A prebuilt file dropped into the tester's setup therefore reads its table
offsets from the wrong place and fetches the wrong textures, which explains the darker image.

**Why the layout differs is not established.** Ruled out so far:

- the DLL: the tester's is AMD's unmodified 4.1.1.2740 (same SHA-256 as the one used here);
- the Proton version: GE-Proton 11-7 on both machines;
- the game, at least on the RX 7800 XT: three different programs give identical dumps there;
- seven vkd3d-proton options (`VKD3D_CONFIG`: `mutable_single_set`, `force_raw_va_cbv`,
  `force_static_cbv`, `skip_driver_workarounds`, `skip_application_workarounds`,
  `enable_experimental_features`, `descriptor_qa_checks`): none changes the layout on the
  RX 7800 XT.

- OptiScaler v10: the nightly of 2026-10-05 on the RX 7800 XT (Shadow of the Tomb Raider, INT8
  forced with `Fsr4ForceModel = 2`) gives the same layout as before, and `check_prebuilt.sh`
  reports that the prebuilt files fit;
- AMD's driver-side FSR DLL (`amdxcffx64.dll`, which contains the same shaders) taking over: in
  that same run OptiScaler's log shows it loaded and its provider update for upscaling succeeding,
  and the layout was still the usual one;
- three Vulkan extensions hidden from vkd3d-proton one at a time (`VK_EXT_descriptor_buffer`,
  `VK_EXT_mutable_descriptor_type`, `VK_EXT_inline_uniform_block`): no change.

- vkd3d-proton's built-in profile for the game: the test program run under the name
  `ff7rebirth_.exe` on the RX 7800 XT keeps the usual layout;
- two mods the tester had in that game (a shader injector and an asynchronous-shader fix): with
  both removed, the result is the same;
- RDNA2 as such, most likely: override files a community member made from their own dumps on an
  RX 6700M in another game (see [community shader set](../research/community-lossy-set)) use the
  usual layout and are reported to work there.

What is left: the game itself (Final Fantasy VII Rebirth), or something particular to that
tester's system. A dump from the same machine in another game would decide it. Until then,
treat it as one setup where the prebuilt files do not fit, not as a property of RDNA2.

The other layout can be produced from the usual one: a converter reproduces all four of the
tester's dumped shaders byte for byte from the RX 7800 XT's. A second set of prebuilt files for
that layout has been built that way and is not published yet.
`check_prebuilt.sh` compares a dump with the shaders the prebuilt files were made from. The DLL build does not have this problem,
because its shaders are translated on the machine that runs them. See
[Making a shader dump](linux.md#building-your-own).

**What did not fix it:** a lower bound of 0.8 on the postpass's history weight (the share of the
previous frame in each output pixel), which was suggested as a fix. It looks bad in motion; see
[history clamp](../research/history-clamp).

The builds are attached to the [release `dll-2026-10-07`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-07):

| File | Contents |
|---|---|
| `test-rdna2.zip` | **for RDNA2, fixes the shimmering:** check lifted, both rewrites, and the postpass's dot products split (see above) |
| `test-rdna2-compact.zip` | **test build for RDNA2 and the Steam Deck:** as `test-rdna2.zip`, with the compact pass 11 of the integrated-GPU build (see below) |
| `amd_fidelityfx_upscaler_dx12.dll` | the main DLL for desktop RDNA3: check lifted, both rewrites |
| `test-igpu.zip` | for integrated GPUs: check lifted, postpass rewrite and the compact pass 11 ([above](#integrated-gpus-radeon-780m-and-similar)) |

Other combinations (check lifted with AMD's shaders unchanged, or with one rewrite only) are built
with `dll/patch_upscaler_dll.py --any-gpu --only none|pass11|postpass`.

### Test build: RDNA2 with the compact pass 11 (2026-10-05)

`test-rdna2-compact.zip` (shows as `4.1.1-r2c-cyboman`) is `test-rdna2.zip` with one change: model
pass 11 is the compact version from the integrated-GPU build, which keeps AMD's loops and only
stores each row of its output together. Compiled for an RX 6000 card or the Steam Deck, that pass
is 4.7 KB of code, against 21.4 KB for the unrolled version in `test-rdna2.zip` and 4.4 KB for
AMD's. On an RX 7800 XT the two versions are almost equally fast (0.24 ms and 0.22 to 0.23 ms,
AMD's 0.60 ms), so little is given up if the large one is fine on RDNA2 too.

Why try it:

- **Steam Deck.** Its chip is RDNA2 and integrated. On RDNA3 integrated GPUs the unrolled pass 11
  was what made FSR 4 slower, for a reason that was never pinned down (code size or the shared
  memory). The Deck shares the memory system, so the compact pass may suit it better.
- **Desktop RDNA2 at 1440p.** The reports above show smaller gains at 1440p than the pass 11
  rewrite alone gives on RDNA3. If the unrolled pass costs time on RDNA2, this build would show it.

Output is byte-for-byte identical to AMD's DLL at four sizes (4K, 1440p, 1080p and 1280x720
output) on an RX 7800 XT. It has not been run on RDNA2 or a Steam Deck. The useful report is
OptiScaler's upscaler time with `test-rdna2.zip` and with this build, at the same spot: on desktop
at 1440p and at 4K, on the Deck at its own resolution.

**First report (2026-10-05), RX 6750 XT at 1440p output (Performance, XeSS inputs):**
`test-rdna2.zip` 2.10 ms, `test-rdna2-compact.zip` 2.14 ms. The compact build is 0.04 ms (2%)
slower. So on a desktop RDNA2 card the unrolled pass 11 is not what holds the gain back at 1440p,
and `test-rdna2.zip` stays the build for RX 6000 cards. The compact build remains a candidate for
the Steam Deck only, where it has not been tried yet.

**Second report (2026-10-05), RX 6750 XT, Windows 11, Wuthering Waves (Unreal Engine 4), 1707x961
to 2560x1440 (Quality), four builds at the same spot, one reading each:**

| Build | Upscaler time | Frame rate |
|---|---|---|
| `test-rdna2.zip` | 2.51 ms | 106.6 FPS |
| `test-rdna2-compact.zip` | 2.52 ms | 106.1 FPS |
| `test-lossy-rdna2.zip` (changes the image) | 2.45 ms | 104.2 FPS |
| `test-lossy-rdna2-compact.zip` (changes the image) | 2.50 ms | 106.9 FPS |

- The compact build again equals the normal one (0.01 ms apart), as in the first report.
- The lossy builds are 0.02 to 0.06 ms (1 to 2%) below their exact builds, which is about the
  spread of the readings, and the frame rate does not follow. On this card at 1440p the lossy
  build is not worth its image change. See [`research/lossy`](../research/lossy).

### Test build: RDNA2 hybrid (2026-10-05; withdrawn 2026-10-07)

**No longer built.** It did not prove useful (see the report below), and release
`dll-2026-10-07` does not contain it. What follows is kept as a record.

`test-rdna2-hybrid.zip` (shows as `4.1.1-r2h-cyboman`) is `test-rdna2.zip` with one change: at
1080p output and below it keeps AMD's own postpass, with only the dot-product split that fixes
the shimmering, and it uses the rewritten postpass at 1440p output and above.

It follows from the first [timing-kit result on an RDNA2 card](../timing-kit/RESULTS.md), an
RX 6700M on Linux:

| Postpass on the RX 6700M | AMD's | Rewritten |
|---|---|---|
| 4K output | 2.37 ms | 1.54 ms (35% faster) |
| 1080p output | 0.33 ms | 0.38 ms (15% slower) |

The stores the rewrite speeds up are only slow at large sizes. At 1080p there is nothing to
remove, and the rewrite's extra registers (80 against 64 on that chip, so 12 waves per SIMD
against 16) are a net cost. That fits the RX 6000 game reports above: about 30% at 4K, a few
percent at 1440p and 1080p.

- **Who it is for:** RX 6000 owners at 1080p output. Compare it with `test-rdna2.zip` at the same
  spot; the hybrid should be the faster of the two there, by a few percent of FSR 4's time.
- **At 1440p and 4K it is identical to `test-rdna2.zip`.** FSR 4 uses one set of shader versions
  for 1440p and 4K output and another for 1080p and below, so a DLL can choose per set but cannot
  treat 1440p differently from 4K. Whether the rewrite helps or hurts at 1440p on RDNA2 is not
  known yet; the timing kit measures it since version 2026-10-05.4.
- **Not known on Windows.** The measurement is from the Linux driver; AMD's Windows driver
  compiles the shaders differently. This build is how to find out.
- Output is byte-for-byte AMD's at six sizes from 720p to 4K (Proton, RX 7800 XT). Built with
  `DOT4=split POSTPASS_SMALL=amd` in `windows/dxil/build_dxil_overrides.sh`.

**First report (2026-10-06), Windows, Clair Obscur: Expedition 33, 1080p output, one reading
each. The tester's GPU model was not given.**

| Session | Build | Render size | Upscaler time | Frame rate (average) |
|---|---|---|---|---|
| A (DLSS inputs) | a release 3 build (name cut off in the picture) | 1279x720 | 1.98 ms | 85.1 FPS |
| A | fsr4xyz `4.1.1b` | 1279x720 | 2.01 ms | 84.3 FPS |
| B (XeSS inputs) | hybrid (`4.1.1-r2h-cyboman`) | 1280x720 | 1.89 ms | 87.4 FPS |
| B | fsr4xyz `4.1.1b` | 1280x720 | 1.85 ms | 88.2 FPS |
| B | hybrid | 1130x636 | 1.90 ms | 94.0 FPS |
| B | fsr4xyz `4.1.1b` | 1130x636 | 1.87 ms | 95.2 FPS |

- **The hybrid build is not faster than `4.1.1b` here: it is 0.03 to 0.04 ms (2%) slower** at both
  render sizes, and the frame rate agrees.
- In the other session an earlier build of this project was 0.03 ms (1.5%) faster than `4.1.1b`.
  The two sessions cannot be compared with each other (`4.1.1b` itself reads 2.01 ms in one and
  1.85 ms in the other), so this does not show that the hybrid is slower than `test-rdna2.zip`,
  only that it did not deliver the gain the Linux measurement suggested.
- At 1080p the hybrid's postpass is AMD's with the dot products split, which is also what
  `4.1.1b` has. So the 2% it loses to `4.1.1b` would come from the other rewrites it carries
  (pass 11, the prepass, the model passes) under AMD's Windows compiler at this size. That is an
  inference from one report, not a measurement.
- **What would settle it:** `test-rdna2.zip`, the hybrid and `4.1.1b` in one session at the same
  spot, and the GPU model.

### Withdrawn: RDNA2 with the postpass's reads unbranched (2026-10-05)

**Result: testers saw no improvement on RDNA2, and the build has been removed from the release.**
Since the 2026-10-07 release every DLL carries this change again (`TAPS=0` in
`windows/dxil/build_dxil_overrides.sh` leaves it out): together with the integer rounding in
the postpass it is a small gain on RDNA3 with the Linux driver. On RDNA2 under Windows the
testers' finding stands: no difference was seen.

`test-rdna2-taps.zip` (showed as `4.1.1-cyboman-r2t`) was `test-rdna2.zip` with one more change to
the postpass. For each pixel the postpass reads a 3x3 neighbourhood of the model's output; each of
the nine reads sits behind a branch that skips it at the picture's edge. Here the reads always
happen, at a valid address, and their values are replaced by zero at the edge, which gives the
same sums. Without the branches the reads can overlap instead of being waited on one after
another.

The idea and the measurement are a community member's (VALKKKS): on an RX 6700M the postpass got
about 10% faster, roughly 2% of FSR 4's whole time at 1440p. On an RX 7800 XT the same change is 3%
slower, so it was built only into that RDNA2 test build.

Output was byte-for-byte identical to AMD's DLL in eight configurations (720p to 4K output, four
ratios) on an RX 7800 XT.

If you try them, please report your GPU, Windows or Linux and driver version, the game, whether FSR
4 starts and looks right, and OptiScaler's upscaler time for each.
