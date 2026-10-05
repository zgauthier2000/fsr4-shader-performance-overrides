# How it works, and what was tried

[Back to the front page](../README.md)

## What the two rewrites do

(Two smaller rewrites were added on 2026-10-05 for the other model passes; they are described at
the end of this section.)

- **Postpass** (`postpass_lds_vkd3d.py`). FSR 4's last pass computes a 2x2 block of pixels per
  thread and writes each pixel separately into three images, so every store instruction writes
  every other pixel. That scattered pattern is slow on RDNA3. The rewrite keeps the values in
  registers and writes the images one at a time: each image's 32x32 block goes through workgroup
  memory and out in solid 8x8 blocks. Passing one image at a time needs 16 KB of workgroup memory
  instead of 40 KB, so four times as many waves run at once. In a standalone benchmark at 4K the
  pass went from about 2.1 ms to 0.6 ms (0.83 ms with the first version, which moved all three
  images at once).
- **Model pass 11** (`zconst.py`). The pass uses a coordinate that is always zero in its loop
  counts, which stops the driver from unrolling the loops. Replacing it with a constant takes the
  pass from 0.60 ms to 0.23 ms in a standalone benchmark. The same change does nothing for the
  other 11 passes.
- **Model pass 11's stores** (`pass11_stores.py`, since 2026-10-04). The pass is the model's
  upsampling step: each thread computes a 2x2 block of outputs and stored every word the moment it
  was computed, 4 bytes in every 32, the same sparse pattern as the postpass. Now each row's
  eight words are stored together. The pass reads about 233 MB from memory instead of about 1,000 MB and
  makes 26 times fewer write requests. On an RX 7800 XT this does not change the frame rate (the
  traffic was not what limited the pass there); it is shipped because it is never slower and may
  help GPUs with less memory bandwidth.

Both rewrites leave the arithmetic untouched. In a standalone benchmark on the same GPU, the
rewritten shaders produced output byte-for-byte identical to AMD's.

**The other model passes (added 2026-10-05).** Two small rewrites that give exactly the same
numbers as AMD's code:

- *Clamp first* (`model_clamp.py`, Linux files). Between layers a pass turns each sum into an
  int8: round, shift right, then clamp to -128..127. Clamping before the shift gives the same
  number, and when the shift is by 8 bits the result is simply one byte of the clamped value, so
  the shift is not needed.
- *Output scaling in integers* (`model_tail.py`, and `model_tail_dxil.py` for the DLL). Several
  passes end by combining two integers in floating point and rounding. The numbers are small
  integers scaled by powers of two, so every floating-point step is exact and the same value can
  be computed with a few integer instructions.

Together they save 0.05 ms at 4K on an RX 7800 XT with the Linux files, 1.6% of FSR 4's time.

**The prepass (added 2026-10-05).** The part that prepares the model's input works on blocks of
four pixels (quads). In AMD's shader every lane forms 16 channel sums from its own pixel's seven
features; two quad swaps and two additions per channel combine the four pixels' sums; then one
lane rounds and stores all 16 channels while three wait. In the rewrite (`prepass_gather.py`,
`prepass_gather_dxil.py`) each lane first fetches the other three pixels' features and then
computes all four pixels' sums itself for the four channels of one output word, with the same
instructions in the same order and the additions grouped the same way, and stores that word. The
same arithmetic on the same numbers gives the same bits. The prepass takes 10% less time.
One detail matters for the DLL's format: the features are exchanged as half-precision values,
because converting them to float for the exchange makes vkd3d-proton translate the whole shader
with different floating-point rules, and the image then no longer matches.
They were found while measuring a [community shader set](../research/community-lossy-set), whose
write-up pointed at both spots.

## Where FSR 4's time goes

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
| 1920x1080 | 1, 2, 12 | about 0.80 ms (about 0.27 ms each) |
| 960x540 | 3, 4, 5, 10, 11 | about 0.64 ms (pass 11 the largest, about 0.21 ms) |
| 480x270 | 6, 7, 8, 9 | about 0.42 ms |

How it was measured: parts of FSR 4 were replaced with empty shaders, one run each, and
OptiScaler's upscaler time was read at the same spot. With everything emptied the reading is
0.12 ms, and with only the phased postpass running 0.75 ms, so the postpass costs 0.63 ms (the
first rewrite: 1.08 ms, so 0.96 ms). That matches the drop in the total from 3.42 ms to 3.09 ms. The
other parts were measured while the first rewrite was in place; they did not change. The
attempts behind the "room left" column are under [What else was tried](how-it-works.md#what-else-was-tried).

The standalone benchmark agrees with the game when it runs each pass in a long burst (500
dispatches): the 12 model passes total 2.03 ms there against 1.86 ms here, the postpass 0.59 ms
against 0.63 ms, the prepass 0.48 ms against 0.44 ms. With short bursts (20 dispatches) the model
passes read about 65% too high (3.35 ms), which is how they were first measured; the model-pass
figures in this repository have been re-measured with long bursts.

## Why the phased version gains more on Linux than on Windows

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

## What else was tried

- **WMMA (matrix multiply instructions) for the model passes.** A bit-exact WMMA version of model
  pass 1 was built and measured: 0.41 ms against 0.29 ms for AMD's shader, so it is not used. The
  full write-up, data and sources are in [`research/wmma/`](../research/wmma).
- **The other model passes and the prepass.** Benchmarked individually; apart from pass 11 they
  compile to little more than the arithmetic itself, and nothing worth rewriting was found. A
  byte-identical prepass rewrite gained about 1.5% and is not shipped.
- **Keeping the postpass at 24 waves per SIMD.** A version that swaps pixels between lanes instead
  of using workgroup memory was byte-identical but took 1.44 ms against 0.59 ms: it still wrote
  only every other row, and sparse writes in either direction are what is slow.

  The probes, data and scripts for these two points, the fusion test above and the occupancy on
  other GPUs are in [`research/postpass-and-prepass/`](../research/postpass-and-prepass).
- **Changing the driver's image layout instead of the shader.** With Mesa patched to store images
  linearly, AMD's postpass takes 1.02 ms instead of 2.10 ms, so the penalty does depend on the
  layout; but the phased postpass on the default layout takes 0.60 ms, and linear images slow it
  (and other uses of those images) down. Details in
  [`research/postpass-and-prepass/`](../research/postpass-and-prepass).
- **Fusing the model passes.** Versions of the 12 passes that write nothing saved 0.07 ms of
  2.03 ms in total, and the compiled passes are almost all arithmetic (pass 1: 832 int8 dot
  products and 13 memory instructions out of 1,450). Merging passes to keep data on chip is not
  worth it.
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
- **Removing small weights from the model (not bit-exact).** Zeroing the smallest weight groups
  in six of the model passes saves about 0.007 ms per 1% removed, and the image changes from the
  first step: at 5% some pixels are already off by 36 of 255, and at 20% the result is 1.5 dB
  further from the true image for 0.14 ms. Not used. Data and the test rig:
  [`research/pruning/`](../research/pruning).
- **Replacing the model's arithmetic with cheaper exact math.** The passes are 57% int8 dot
  products with the weights as constants, already one instruction per four multiply-adds; none of
  the weight words is zero, the clamps cannot be proven unnecessary, and exact fast-convolution
  schemes need operands wider than 8 bits. Nothing found.

All research write-ups are listed in [`research/`](../research).
