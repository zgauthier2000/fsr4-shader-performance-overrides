# fsr4-shader-performance-overrides

Makes AMD FSR 4.1.1 upscaling cheaper on Radeon RX 7000 (RDNA3) cards under Linux and Proton, by
replacing two of FSR's compute shaders with faster versions that produce the same output.

It is three ready-made shader files plus the small scripts that build them. vkd3d-proton loads the
replacements through one launch option. Nothing in the game, in OptiScaler or in AMD's DLLs is
modified.

**New on 2026-10-03 at 14:40 EDT (UTC−4), commit `896d7f0`: a faster postpass.** The postpass rewrite now writes its three images one
at a time, which lets four times as many waves run at once. Same output, byte for byte. In Shadow
of the Tomb Raider at 4K the upscaler time dropped from 3.42 ms (first rewrite) to 3.09 ms, 26%
below AMD's 4.16 ms, and the frame rate rose from 116.6 to 120.7 FPS. The files in
[`prebuilt/`](prebuilt) are already the new version; if you built your own, run
`build_override.sh` again; anything built or downloaded before that commit is the first
version. Details and measurements:
[`results/phased-postpass`](results/phased-postpass).

**Patched DLL:** [`dll/`](dll) has a script that builds the same shaders straight into AMD's
`amd_fidelityfx_upscaler_dx12.dll`, so a game needs no launch option or add-on: replace the DLL
and you are done. A ready-made patched DLL is attached to the
[release `dll-2026-10-03`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-03). Verified byte for byte under Proton, and run on Windows by
testers (see below).

**Windows:** the patched DLL above works on Windows too, and there is also a ReShade add-on in
[`windows/`](windows). Testers on Windows with Radeon RX 7000 graphics cards report large
improvements, nearly as large as on Linux. See [Windows](#windows).

## Results

OptiScaler's upscaler time on a Radeon RX 7800 XT (Mesa 26.2, RADV), 4K output:

| Game | Mode | Before | After | Saved |
|---|---|---|---|---|
| Control Resonant | Performance | 5.4 ms | 3.5 ms | 1.9 ms (35%) |
| Mortal Shell II | Balanced | 4.97 ms | 3.58 ms | 1.39 ms (28%) |
| Shadow of the Tomb Raider | Balanced | 4.16 ms | 3.47 ms | 0.69 ms (17%) |
| Shadow of the Tomb Raider, 1440p output | Balanced | 1.76 ms | 1.55 ms | 0.21 ms (12%) |
| Rise of the Tomb Raider | Balanced | 4.30 ms | 3.33 ms | 0.97 ms (23%) |
| Rise of the Tomb Raider, 1440p output | Balanced | 1.79 ms | 1.49 ms | 0.30 ms (17%) |
| Elden Ring (postpass only)* | Balanced | 5.33 ms | 4.57 ms | 0.76 ms (14%) |

The saving varies by game. Only this one GPU has been tested.

\* Measured with the game's 60 FPS cap in place, which makes OptiScaler's upscaler time unreliable
in some games; treat this row as approximate.

The table was measured with the first version of the postpass rewrite. The current, phased
version is faster again; in Shadow of the Tomb Raider at 4K it brings the upscaler time to
3.09 ms, 1.07 ms (26%) below AMD's, and in Rise of the Tomb Raider's benchmark at 4K to 3.02 ms,
1.28 ms (30%) below AMD's (see [`results/phased-postpass`](results/phased-postpass)). The other
games have not been re-measured yet.

Both Tomb Raider games were also run through their built-in benchmarks, where the frame time
saved matches the upscaler time saved:

- [Shadow of the Tomb Raider](results/shadow-of-the-tomb-raider): 97 → 104 FPS at 4K (+7%,
  upscaler −16.6%), 171 → 176 FPS at 1440p (+3%, upscaler −11.9%).
- [Rise of the Tomb Raider](results/rise-of-the-tomb-raider): 97.6 → 107.9 FPS at 4K (+11%,
  upscaler −22.6%), 186.6 → 199.6 FPS at 1440p (+7%, upscaler −16.8%).

Each links to the full numbers and the results screenshots.

## Where FSR 4's time goes now

Shadow of the Tomb Raider, 4K output, Balanced, frame rate uncapped, Radeon RX 7800 XT, with the
phased postpass and the pass 11 rewrite: **3.09 ms in total** (AMD's shaders: 4.16 ms).

| Part | Time | Share | Room left |
|---|---|---|---|
| Model passes (12) | 1.86 ms | 60% | none found: limited by arithmetic; WMMA and pass fusion ruled out |
| Postpass (phased) | 0.63 ms | 20% | 0.05 ms at most |
| Prepass | 0.44 ms | 14% | a few hundredths of a millisecond |
| OptiScaler and dispatch overhead | 0.12 ms | 4% | outside the shaders |
| Two small shaders and gaps between passes | 0.04 ms | 1% | |

The model passes, split by each pass's share in a standalone benchmark (an estimate; single
passes cannot be timed in the game):

| Tensor size | Passes | Estimated time |
|---|---|---|
| 1920x1080 | 1, 2, 12 | about 0.73 ms (about 0.24 ms each) |
| 960x540 | 3, 4, 5, 10, 11 | about 0.67 ms (pass 11 the largest, about 0.19 ms) |
| 480x270 | 6, 7, 8, 9 | about 0.46 ms |

How it was measured: parts of FSR 4 were replaced with empty shaders, one run each, and
OptiScaler's upscaler time was read at the same spot. With everything emptied the reading is
0.12 ms, and with only the phased postpass running 0.75 ms, so the postpass costs 0.63 ms (the
first rewrite: 1.08 ms, so 0.96 ms). That matches the drop in the total from 3.42 ms to 3.09 ms. The
other parts were measured while the first rewrite was in place; they did not change. The
attempts behind the "room left" column are under [What else was tried](#what-else-was-tried).

Standalone benchmark times quoted elsewhere in this repository compare versions of one shader
fairly, but overstate its cost in a game: the model passes total 3.35 ms in the benchmark against
1.86 ms here.

## What you need

- Linux, and a D3D12 game running through Proton (vkd3d-proton). DX11 and Vulkan games are not
  covered. For Windows see the [Windows](#windows) section.
- FSR 4.1.1 with the INT8 model actually running, for example through
  [OptiScaler](https://github.com/optiscaler/OptiScaler) with `amd_fidelityfx_upscaler_dx12.dll`
  version 4.1.1.2740. Other FSR versions have different shaders; the scripts will tell you if they
  find nothing they recognise.
- An RDNA3 card on the RADV driver. The slow pattern these rewrites remove was measured there.
  Other cards are untested, and RDNA4 runs a different FSR 4 model that this does not touch.
- Only if you build your own files: `python3` and SPIRV-Tools (`spirv-dis`, `spirv-as`,
  `spirv-val`).

## Quick start: the prebuilt files

The [`prebuilt/`](prebuilt) folder holds the overrides for the common case: AMD's DLL version
4.1.1.2740, output above 1080p, and any preset except Ultra Performance.

1. Clone or download this repository.
2. Add this to the game's launch options in Steam (keep anything already there in front of
   `%command%`):

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-performance-overrides/prebuilt' %command%
   ```

   `Z:` is how Proton sees your Linux root, so `Z:/home/you/...` is `/home/you/...`.
3. Compare OptiScaler's upscaler time with and without the variable, standing at the same spot. ***In
   some games, that number is only reliable with the frame rate uncapped.***

If the time does not drop, your game uses a shader variant that is not in `prebuilt/`. Build your
own as described next.

## Building your own

1. **Dump the game's shaders once.** Create an empty folder, then add this to the game's launch
   options in Steam (keep anything already there in front of `%command%`):

   ```
   VKD3D_SHADER_DUMP_PATH='Z:/home/you/fsr4-dump' %command%
   ```

   Start the game with FSR 4 enabled at the output resolution you play at, load into gameplay, and
   quit. The folder fills with a few thousand files.

2. **Build the overrides.**

   ```
   ./build_override.sh /home/you/fsr4-dump
   ```

   It prints the files it wrote into `override/` and the launch option to use. If it finds no FSR
   4.1.1 shaders, FSR 4.1.1 was not running during the dump.

3. **Switch the launch option** from the dump variable to the one the script printed:

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-performance-overrides/override' %command%
   ```

   The dump folder can be deleted now.

4. **Check it** the same way as in the quick start.

One `override/` folder serves every game. Files are named by shader hash, so if a second game uses
the same shaders it needs only the launch option, and if it uses different ones you repeat steps 1
and 2 and the new files are added alongside. To have everything in one place, copy the files from
`prebuilt/` into `override/` as well.

## Windows

Several testers on Windows with Radeon RX 7000 graphics cards report large improvements with the
first version of these rewrites, nearly as large as on Linux, so AMD's Windows driver has the
same slow store pattern. The phased version has also been run on Windows with an RX 7800 XT,
with about the same result as the first version there.

Two ways to use them on Windows:

- the [patched DLL](#patched-dll): replace `amd_fidelityfx_upscaler_dx12.dll`, nothing else;
- a ReShade add-on in [`windows/`](windows) that swaps the same two shaders when AMD's DLL creates
  them. See [`windows/README.md`](windows/README.md).

Both were verified byte for byte against AMD's output under Proton. On integrated GPUs, see the
next section.

### Why the phased version gains more on Linux than on Windows

Mostly because the two first versions were different; the phased change itself does the same
thing on both.

- **The Linux first version started from a worse place.** It moved all three of the postpass's
  images through workgroup memory at once: 10 values per pixel for a 32x32 block, 40 KB per
  workgroup. Only a few such workgroups fit in a WGP's 128 KB, so the shader ran just 4 waves per
  SIMD. The postpass waits a lot on memory (about 40 texture reads per thread, plus the model's
  output), and with 4 waves there is little other work to run meanwhile.
- **The Windows first version was forced into a better design.** D3D12 allows a workgroup only
  32 KB, so the DXIL version moved just the two float images (24 KB) and wrote the
  half-precision one directly. That already ran 8 waves per SIMD (measured under vkd3d-proton).
- **Both phased versions end at 16 waves per SIMD**, so Linux had much more to gain:

  | Postpass at 4K, standalone benchmark | First version | Phased |
  |---|---|---|
  | Linux (SPIR-V) | 40 KB, 4 waves, 0.83 ms | 16 KB, 16 waves, 0.60 ms |
  | Windows (DXIL, run under vkd3d-proton) | 24 KB, 8 waves, 0.72 ms | 12 KB, 16 waves, 0.67 ms |

- **On Windows itself, AMD's own shader compiler** decides the wave size (it often runs compute
  shaders as wave32), the registers and the occupancy. If it already ran the first version at good
  occupancy, phasing had almost nothing left to fix, which fits the RX 7800 XT tester seeing no
  change.
- **The DXIL version is slightly slower even on Linux** (0.67 ms against 0.60 ms phased), because
  vkd3d-proton's translation of DXIL gives slightly worse code than the hand-written SPIR-V. That
  is not a Windows effect, but it means the Windows file was never quite as fast as the Linux one.

On both systems the big gain comes from the first version, which fixed the scattered stores (AMD's
postpass: 2.06 ms in the same benchmark). The phased version mostly repairs the Linux first
version's low occupancy, a problem the Windows version had largely avoided. A Radeon GPU Profiler
capture on Windows would show what AMD's Windows compiler actually does with each version.

## Patched DLL

Instead of a launch option or the add-on, [`dll/patch_upscaler_dll.py`](dll) writes a copy of
AMD's `amd_fidelityfx_upscaler_dx12.dll` (4.1.1.2740) with the faster shaders built in; it works
on Windows and under Proton alike. On Linux the launch option is still slightly faster (the
postpass: 0.60 ms against 0.67 ms at 4K), because vkd3d-proton translates the DLL's DXIL into
slightly slower code than the hand-written SPIR-V. A ready-made patched DLL is attached to the
[release `dll-2026-10-03`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-03). See [`dll/README.md`](dll/README.md).

## Integrated GPUs (Radeon 780M and similar)

People testing on RDNA3 integrated GPUs have reported that FSR 4 gets slower, not faster, with
the first version of the postpass rewrite and with the phased version too. This has not been
reproduced here (only a Radeon RX 7800 XT was available), and it is not yet known which of the
two rewrites is responsible. The likely one is the postpass: an integrated GPU's memory system
may not suffer from the scattered stores at all, so rewriting them only adds work. Pass 11 only
lets the driver unroll loops, which is unlikely to cost anything. Until the runs below show
otherwise, **on an integrated GPU, use pass 11 only, or nothing**.

The two possibilities the reports have narrowed down:

- **Low occupancy** in the first postpass rewrite (4 waves per SIMD to hide memory latency) was the
  first suspect, but the phased postpass (16 waves per SIMD) is reported slower too.
- **No store penalty to remove:** if the integrated GPU's memory system handles the scattered
  stores well, the postpass rewrite only adds barriers and workgroup-memory traffic, and bunches
  the writes at the end of each workgroup. This is the current suspect.

On Windows with Radeon RX 7000 graphics cards (not integrated GPUs), testers report large
improvements with the first version, and one tester with an RX 7800 XT saw no difference between
the first and the phased version. That is expected: the DXIL version that Windows uses was never
limited the same way (it already ran 8 waves per SIMD), and under vkd3d-proton its postpass only
went from 0.72 ms to 0.67 ms.

To find out, compare OptiScaler's upscaler time, frame rate uncapped, in four runs. Ready-made
pass 11-only and postpass-only DLLs are attached to the
[release `dll-2026-10-03`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-03)
as `test-pass11-only.zip` and `test-postpass-only.zip`.

| Run | Linux (launch option) | Patched DLL |
|---|---|---|
| AMD's shaders | no `VKD3D_SHADER_OVERRIDE` | AMD's original DLL |
| Both rewrites | the `prebuilt/` folder | `patch_upscaler_dll.py` |
| Pass 11 only | a copy of `prebuilt/` without `683038df6272d4db.spv` and `4d657fb0eed077d6.spv` | `patch_upscaler_dll.py --only pass11` |
| Postpass only | a copy of `prebuilt/` without `e29847a84b6f746f.spv` | `patch_upscaler_dll.py --only postpass` |

At 1080p output or below, the files in `prebuilt/` do not apply; build your own with
`build_override.sh`, using `PASS11=0` or `POSTPASS=0` to leave one rewrite out. Until there is
more data, use whichever run is fastest on your GPU.

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

Ready-made test builds are attached to the [release `dll-2026-10-03`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-03):

| File | Contents |
|---|---|
| `test-any-gpu-amd-shaders.zip` | check lifted, AMD's shaders unchanged: does FSR 4 run at all? |
| `test-any-gpu.zip` | check lifted, both rewrites |
| `test-any-gpu-pass11-only.zip` | check lifted, pass 11 rewrite only (for integrated GPUs) |

If you try them, please report your GPU, Windows or Linux and driver version, the game, whether FSR
4 starts and looks right, and OptiScaler's upscaler time for each.

## When the prebuilt files are not enough

The overrides match exact shaders. A game silently falls back to AMD's originals, with no error,
when it uses a shader you do not have a file for. That happens with:

- a different FSR DLL version;
- output at 1080p or below versus above 1080p (two different shader sets);
- Ultra Performance mode (its own model). Quality, Balanced and Performance share one;
- a game whose FSR setup differs, for example in how exposure is handled.

If the upscaler time does not drop, dump that game and run the script again.

## What the two rewrites do

- **Postpass** (`postpass_lds_vkd3d.py`). FSR 4's last pass computes a 2x2 block of pixels per
  thread and writes each pixel separately into three images, so every store instruction writes
  every other pixel. That scattered pattern is slow on RDNA3. The rewrite keeps the values in
  registers and writes the images one at a time: each image's 32x32 block goes through workgroup
  memory and out in solid rows. Passing one image at a time needs 16 KB of workgroup memory
  instead of 40 KB, so four times as many waves run at once. In a standalone benchmark at 4K the
  pass went from about 2.1 ms to 0.6 ms (0.83 ms with the first version, which moved all three
  images at once).
- **Model pass 11** (`zconst.py`). The pass uses a coordinate that is always zero in its loop
  counts, which stops the driver from unrolling the loops. Replacing it with a constant saves about
  0.1 ms.

Both rewrites leave the arithmetic untouched. In a standalone benchmark on the same GPU, the
rewritten shaders produced output byte-for-byte identical to AMD's.

## Things to know

- **The prebuilt files are modified AMD shaders.** They come from AMD's
  `amd_fidelityfx_upscaler_dx12.dll` 4.1.1.2740, which AMD's FidelityFX SDK licence lists under MIT
  terms. [`prebuilt/NOTICE.md`](prebuilt/NOTICE.md) says exactly where they come from and carries
  AMD's notice. Running `build_override.sh` on a matching dump reproduces them byte for byte.
- **Dumps stay out of the repository.** A raw dump contains every shader of the game you ran, so
  `.gitignore` excludes dumps and your own `override/` folder.
- **Set the variable per game.** With `VKD3D_SHADER_OVERRIDE` set, vkd3d-proton stops using the
  SPIR-V stored in its pipeline caches for that game, which can lengthen the first loads.
- **Online games.** This only sets an environment variable for vkd3d-proton, but it does change
  what the game renders with. Use your own judgement in games with anti-cheat.
- **Do not set `RADV_PERFTEST=cswave32`** for a game that runs FSR 4. In a standalone benchmark it
  made 11 of the 12 model passes about 40% slower (pass 1: 0.43 to 0.61 ms), roughly 1 ms of FSR 4
  per frame.
- **To undo it,** remove the launch option.

## What else was tried

- **WMMA (matrix multiply instructions) for the model passes.** A bit-exact WMMA version of model
  pass 1 was built and measured: 0.41 ms against 0.29 ms for AMD's shader, so it is not used. The
  full write-up, data and sources are in [`research/wmma/`](research/wmma).
- **The other model passes and the prepass.** Benchmarked individually; apart from pass 11 they
  compile to little more than the arithmetic itself, and nothing worth rewriting was found. A
  byte-identical prepass rewrite gained about 1.5% and is not shipped.
- **Keeping the postpass at 24 waves per SIMD.** A version that swaps pixels between lanes instead
  of using workgroup memory was byte-identical but took 1.44 ms against 0.59 ms: it still wrote
  only every other row, and sparse writes in either direction are what is slow.

  The probes, data and scripts for these two points, the fusion test above and the occupancy on
  other GPUs are in [`research/postpass-and-prepass/`](research/postpass-and-prepass).
- **Fusing the model passes.** Versions of the 12 passes that write nothing and read from cache
  saved 0.07 ms of 3.35 ms in total, so merging passes to keep data on chip is not worth it: the
  passes are limited by arithmetic, not memory.
- **Further workgroup-memory (LDS) tuning of the phased postpass.** Measured in a standalone
  benchmark at 4K, where the phased postpass takes 0.59 ms and AMD's original with all its stores
  removed (no write cost at all, full occupancy) 0.49 ms, so at most 0.1 ms is left:
  - Removing the barriers (a probe with wrong output) made it slower, not faster (0.63 ms): they
    cost nothing.
  - The LDS work is small, about 70 instructions per thread out of about 2,700, already merged
    into 16-byte stores and 8-byte loads. Smaller buffers (8 KB or 4 KB, half or a quarter of the
    block at a time) were no faster.
  - What is left is occupancy: the shader computes its four pixels one after another, so the
    finished pixels' values wait in registers until the flush, which takes it from 60 to 96
    registers per lane and from 24 to 16 waves per SIMD. Holding the recurrent-state values as
    half-precision numbers to save registers was neither bit-exact nor faster. Flushing each pixel
    as soon as it is done would need barriers inside the pass's bounds check, a large rewrite
    for an expected 0.05 ms at most.

## Example images
Before

<img src="before.jpg" width="800" alt="Before">

After

<img src="after.jpg" width="800" alt="After">


## Credits and licence

The postpass rewrite is adapted from `tools/fsr4cap/postpass_lds.py` in
[bbport](https://github.com/deadinside28/bloodborne_pc), a native Linux port of Bloodborne whose
author found the slow store pattern and wrote the original rewrite for that project's own FSR 4.1.1
runtime. This repository ports it to the shaders vkd3d-proton generates, so it works in ordinary
games.

The scripts are licensed under the GNU GPL v2 or later, like the project they derive from. See
[LICENSE](LICENSE). The prebuilt shaders are modified versions of AMD's, distributed under the same
licence together with AMD's notice; see [`prebuilt/NOTICE.md`](prebuilt/NOTICE.md). Not affiliated
with or endorsed by AMD.
