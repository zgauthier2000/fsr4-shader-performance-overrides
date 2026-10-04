# RDNA4 (RX 9000) and the FP8 model: open for someone to pick up

[Back to the front page](../README.md)

Nothing in this repository applies to RDNA4 cards. They run the FP8 version of FSR 4, which uses
different shaders, and no RDNA4 card was available to work on it. **If you have an RX 9000 card
and want to take this on, or just to help by testing, everything needed to start is below.**

## What is known

From the shaders inside AMD's `amd_fidelityfx_upscaler_dx12.dll` 4.1.1.2740:

- **The FP8 postpass is a different program** from the INT8 one this repository rewrites. It is
  Shader Model 6.4 with thread groups of 32 (the INT8 one: 256), and it calls AMD's driver
  intrinsics about 1,580 times (the hardware matrix instructions). The INT8 postpass rewrite
  refuses it.
- **Its stores are laid out differently.** The INT8 postpass writes a 2x2 block of pixels per
  thread into three images, the every-other-pixel pattern that is slow on RDNA3. The FP8 postpass
  makes 7 stores, several images at one shared coordinate. Whether those land densely or sparsely
  cannot be told from the code alone.
- **The whole FP8 pipeline has been dumped** by running it under emulation (next section), but
  not yet analysed for slow patterns.

## The FP8 version can be run on RDNA3 under Proton

Proton can run the FP8 version on an RDNA3 card by emulating the FP8 matrix operations with FP16:
set `DXIL_SPIRV_CONFIG=wmma_rdna3_workaround` (GE-Proton 11-7, vkd3d-proton). On an RX 7800 XT,
AMD's DLL then picks its FP8 version, runs, and produces an image. The shaders it loads at 4K:

| Shaders | Count | Notes |
|---|---|---|
| Model passes `pass1` to `pass12` | 12 | cooperative-matrix code, thread groups of 32 |
| `pass0_post` to `pass12_post` | 13 | small, no matrix code |
| `prepass` | 1 | 2 image writes, some matrix code |
| `postpass` | 1 | 3 image writes, matrix code |

This makes the FP8 shaders available for study, and a rewrite can be checked for unchanged
output this way, without an RDNA4 card. Two limits:

- **Timings do not transfer.** The emulation is slower than real FP8 hardware (Proton itself
  advises the INT8 version on RDNA3), so nothing measured this way says what RDNA4 gains.
- **Linux override files do not transfer either.** With the emulation on, vkd3d-proton translates
  the shaders differently, so `.spv` overrides must be built from a dump made on an RDNA4 card. A
  rewrite of the DXIL itself (the patched-DLL route) does not have this problem.

## What could carry over

The method, not the files:

- **Sparse image writes.** The penalty this repository removes comes from how images are stored
  in 2D tiles (see
  [why AMD's stores are slow](../research/postpass-and-prepass/README.md#why-amds-stores-are-slow-the-density-of-the-writes)),
  so RDNA4 may have it too. If the FP8 postpass writes sparsely, the same idea applies, as a new
  rewrite for that shader: collect a block and write it out solid, one image at a time.
- **Loops the compiler cannot unroll.** The INT8 pass 11 fix (an always-zero coordinate in loop
  counts) is specific to that pass; the FP8 passes need their own check for the same mistake.
- **A different balance.** With matrix hardware the model part should be much cheaper on RDNA4,
  so the prepass and postpass are a larger share of FSR 4's time, and a gain there matters more.

## How to start

1. **Dump the shaders** with FSR 4 running on the RDNA4 card.
   - Linux: add `VKD3D_SHADER_DUMP_PATH='Z:/home/you/fsr4-dump' %command%` to the game's launch
     options, load into gameplay, quit.
   - Windows: the ReShade add-on in [`../windows`](../windows) saves FSR 4's shaders into a
     `fsr4-overrides\dump` folder.
2. **Find where the time goes.** Replace parts of FSR 4 with empty shaders and read OptiScaler's
   upscaler time, as was done for the breakdown on the front page (`nullify.py` in
   [`../research/postpass-and-prepass`](../research/postpass-and-prepass)). On Linux, a Radeon GPU
   Profiler capture (`MESA_VK_TRACE=rgp`) shows each pass's time directly.
3. **Look at the compiled code** of the expensive passes: `RADV_DEBUG=shaders,shaderstats` prints
   the instructions, registers and waves per SIMD. Look for image stores that write every other
   pixel, loops that were not unrolled, and low occupancy.
4. **Test a rewrite** with `VKD3D_SHADER_OVERRIDE`, and check the output is unchanged before
   measuring.

The shaders can be compiled for RDNA4 without the card (Mesa's `amdgpu` drm-shim, chip
`gfx1201`), which is enough for step 3 but cannot time anything. If you open an issue with a dump
attached or with what you find, help with steps 3 and 4 is on offer.
