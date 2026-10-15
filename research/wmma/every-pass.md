# WMMA on every model pass, exact and lossy

[Back to the WMMA write-up](README.md) · [The hybrid split for pass 1](hybrid.md) · [Research index](../README.md)

> [!NOTE]
> **Research, not a download.** Nothing on this page is in any release. All timings are from one card
> (Radeon RX 7800 XT, Linux, Mesa 26.2.3 RADV), in the benchmark harness, not in a game. Windows was not measured.

## In short

The [earlier write-up](README.md) built WMMA versions of pass 1 only and probed pass 7; the [hybrid page](hybrid.md)
moved only pass 1's 3x3 layer to WMMA. This page covers the rest: every one of the 12 model passes, in the forms the
exact files ship them (AMD's passes, and our unrolled pass 11) and the lossy files' folded passes 1 and 10.

- **Every WMMA version gives AMD's output byte for byte**, on three data sets (below).
- **None is faster than AMD's pass as RADV runs it**, with 64-wide waves. The closest are passes 4, 5 and 10 (0.149
  against 0.140 ms) and pass 6 (0.055 against 0.052 ms).
- **Why:** on this card WMMA's int8 throughput is at most about 13% above that of the packed dot products AMD's passes use
  in 64-wide waves (measured: 35 against at least 31 trillion multiply-adds per second). Getting values into and out of
  the matrices costs more than that.
- **Against AMD's passes run 32-wide, about half the WMMA versions win** (the hybrids of passes 1, 2, 4, 5, 10 and 12,
  lossy pass 1, and passes 3 and 6; in 32-wide waves the dot products run at about 19 trillion per second), but none
  beats AMD's 64-wide time. On RDNA2, Windows' driver appears to run these passes
  32-wide already (a tester's RX 6600 in the Windows timing kit); those cards have no WMMA. What Windows does on RDNA3
  is not known.
- **The lossy passes lose their folding.** Folding sets weights to zero so that dot products can be left out; a matrix
  instruction multiplies the zeros anyway.

## Results

4K output, median of sustained runs (300 dispatches per timing), times in ms. "32-wide" means the pipeline was created
with a required subgroup size of 32, as vkd3d-proton does for a DXIL shader with Shader Model 6.6's `WaveSize(32)`.

| Pass | What was built | AMD's, 64-wide | AMD's, 32-wide | WMMA, 64-wide | WMMA, 32-wide |
|---|---|---|---|---|---|
| 1, 2, 12 | hybrid: 3x3 layer on WMMA | 0.293 | 0.458 | 0.338 | 0.364 |
| 1 | all three layers on WMMA | 0.293 | 0.458 | | 0.334 |
| 3 | all WMMA (one layer) | 0.053 | 0.074 | 0.063 | 0.063 |
| 4, 5, 10 | hybrid: 3x3 layer on WMMA | 0.140 | 0.217 | 0.149 | 0.194 |
| 6 | all WMMA (one layer) | 0.052 | 0.071 | 0.056 | 0.055 |
| 7 | all WMMA (three layers) | 0.120 | 0.191 | 0.339 | 0.295 |
| 8 | all WMMA (three layers) | 0.119 | 0.193 | 0.327 | 0.295 |
| 9 | all WMMA (four layers) | 0.177 | 0.282 | 1.086 | 0.728 |
| 11 (exact, unrolled) | hybrid: 3x3 layer on WMMA | 0.201 | 0.296 | 0.231 | 0.296 |
| 1 (lossy, folded) | hybrid: 3x3 layer on WMMA | 0.275 | 0.430 | 0.325 | 0.347 |
| 10 (lossy, folded) | hybrid: 3x3 layer on WMMA | 0.122 | 0.183 | 0.146 | 0.188 |

The rows for passes 1, 2, 12 and 4, 5, 10 show pass 1 and pass 4; the other passes of each group were timed too and are
within 0.004 ms of them.
Pass 11 in the exact files is our unrolled version, not AMD's (0.605 ms in this harness).

### What the passes do

Read from the passes as vkd3d-proton translates them (4K output; "level 1" is the 1920x1080 tensor):

| Pass | Layers | Multiply-adds per pixel of the pass's grid |
|---|---|---|
| 1, 2, 12 | 3x3 16→16, 1x1 16→32, 1x1 32→16, residual | 3,328 |
| 3 | 2x2 stride-2, 16→32 (level 1 to 2) | 2,048 |
| 4, 5, 10 | 3x3 16→16 on half the channels, 1x1 32→64, 1x1 64→32, residual | 6,400 |
| 6 | 2x2 stride-2, 32→64 (level 2 to 3) | 8,192 |
| 7, 8 | grouped 3x3 (two groups of 16), 1x1 64→128, 1x1 128→64, residual | 20,992 |
| 9 | as 7, then a 1x1 64→4x32 layer that writes level 2 (2x upsampling) with a skip input | 29,184 (per level-3 pixel) |
| 11 | 3x3 16→16, 1x1 32→64, 1x1 64→32, 1x1 32→4x16 (2x upsampling) with a skip input | 8,448 (per level-2 pixel) |

Passes 7, 8 and 9 have the same shape but not the same arithmetic: they round with different shifts (7 and 7, 9 and 6,
8 and 7 for the first two layers) and scale the residual differently. Each is built with its own constants.

## Why WMMA does not win here

### Peak rates

Throughput probes ([`peak_dot.comp`](peak_dot.comp), [`peak_wmma.comp`](peak_wmma.comp)), nothing but independent
multiply-adds, the whole 1920x1080 grid:

| | 64-wide waves | 32-wide waves |
|---|---|---|
| Packed dot products (`v_dot4_i32_iu8`), best variant | 30.9 trillion/s | 19.0 trillion/s |
| WMMA (`v_wmma_i32_16x16x16_iu8`) | 35.1–35.7 trillion/s | 35.1–35.7 trillion/s |

The dot-product rate depends on how the probe is written (between 23 and 31 trillion per second for the same work), so
30.9 is a lower bound for the 64-wide peak. The card's nominal int8 rate works out to about 39 trillion multiply-adds per
second for either instruction (256 per clock per compute unit). Measured, WMMA is at most 13% ahead in 64-wide waves and
about 85% ahead in 32-wide waves. AMD's passes run at about 20–24 trillion per second overall, everything included.

This explains the whole table. Only the multiplies can get faster, and in 64-wide waves hardly at all. Everything around
them gets slower: each layer's sums have to be rounded one by one, as before, and in addition moved between lanes or
through shared memory to become the next layer's matrix, and a matrix instruction works on 16 pixels at a time where
AMD's code works on one pixel per lane.

### The single-layer passes

Passes 3 and 6 are the best case for WMMA: one layer, so nothing has to be handed from one layer to the next. Each
invocation receives whole words of consecutive channels of its own pixel (the rows of the weight matrices are permuted
for that) and stores them directly. They still end 6% (pass 6) and 19% (pass 3) above AMD's 64-wide time.

### The deep passes

The full versions of passes 7, 8 and 9 are far slower than the lower bound from [the earlier probe](README.md#the-deeper-passes)
(the multiplies of pass 7 alone, without rounding: 0.097 ms in 32-wide waves, measured again for this page; the earlier
write-up had 0.12–0.13 ms). Two reasons, found with the compiler statistics and one ablation:

- They need all 256 registers, so only 2 waves run per SIMD (AMD's pass 7: 60 registers, 24 waves).
- Each workgroup copies all 82 weight matrices (21 KB) into shared memory with their rows permuted. Leaving the copy
  out (wrong output; timing only) takes pass 7 from 0.296 to 0.242 ms.

Both could be reduced, but not below the lower bound: 0.097 ms for the multiplies plus the rounding of 224 values per
pixel already comes to about AMD's 0.120 ms. They were not tuned further.

## How it was built

### From AMD's passes, through GLSL

Every pass was decompiled with [SPIRV-Cross](https://github.com/KhronosGroup/SPIRV-Cross) and compiled again with
glslang. This round trip gives AMD's output byte for byte for all 12 passes and our pass 11, at the same speed (passes
3 and 6 about 5–17% slower). That made two kinds of WMMA version possible:

- **Spliced hybrids** ([`splice3x3.py`](splice3x3.py), [`splice11.py`](splice11.py)): the 3x3 layer is computed with
  WMMA at the top of AMD's decompiled shader; each lane gets the 16 sums of its own pixel through a lane exchange, and
  they are written over AMD's accumulators after its loops for that layer, which the compiler then removes. Everything
  else is AMD's own code, so its rounding and residual need no reimplementing.
- **All-WMMA passes** written from the layer structure ([`gen_full32.py`](gen_full32.py) for pass 1,
  [`gen_down.py`](gen_down.py) for 3 and 6, [`gen_deep.py`](gen_deep.py) for 7, 8 and 9). The rows of every weight matrix
  are permuted so that each invocation receives consecutive channels of its pixel: 8 in 32-wide waves (channels 8g to
  8g + 7 of lane group g), 4 in 64-wide waves. It rounds them, packs two words, and writes them to shared memory, where
  they form a column of the next layer's B matrix in channel order, or straight to the output. No bytes are shuffled
  between lanes.

### How it was checked

- **Three data sets:** AMD's real model data with a random tensor, the same with a small-value tensor, and small-value
  weights with the small-value tensor. Every version above is identical to AMD's pass on all three.
- **The check catches errors:** a hybrid with 5 of the 9 taps differs from AMD's output on all three.
- **[`bench/mbench.c`](bench/mbench.c)** compares all 83 MB the pass can write.

## Two traps

**`RADV_PERFTEST=cswave32` is not the same as a 32-wide pipeline.** With it, RADV compiled these shaders for an API
subgroup size of 64 but ran them 32-wide: a workgroup barrier became a subgroup-only one, and `gl_SubgroupID` was
always 0. Shaders that rely on either then race between the two waves of a workgroup, and timings come out different
(the pass 1 hybrid: 0.249 ms with the switch, 0.364 ms with a real 32-wide pipeline). Everything on this page uses a required subgroup size per pipeline instead: `mbench` now takes
`file.spv@32` or `WAVE=32`. AMD's own passes give the same time both ways (pass 1: 0.458 and 0.459 ms), and the 32-wide
figures on the [hybrid page](hybrid.md) were not affected: its 32-wide hybrid used workgroups of 32.

**A missing data file was silently replaced.** Given a `WEIGHTS=` path that did not exist, `mbench` fell back to random
weights, under which nearly every value saturates and the comparison cannot see errors. The first round of checks for
this page ran that way; everything was checked again with the right file. `mbench` now stops when a `WEIGHTS=` or
`SCRATCH=` file cannot be opened.

## Not tried

- Windows, and any card but the RX 7800 XT. On Windows, `WaveSize(32)` in a DLL would request 32-wide waves per pass;
  that only matters where a pass is faster 32-wide, which none is here.
- Tuning the deep passes (registers, the weight copy). Their lower bound is already about AMD's time.
- RDNA4: different matrix layout, and AMD's FP8 model rather than these INT8 passes.
- A game. Nothing here was built into an override folder or a DLL.

## Files

| File | What it is |
|---|---|
| [`splice3x3.py`](splice3x3.py) | Hybrid of a decompiled pass 1, 2, 4, 5, 10 or 12 (exact or lossy): its first 3x3 layer by WMMA; second argument 32 or 64 |
| [`splice11.py`](splice11.py) | The same for the exact (unrolled) pass 11 |
| [`gen_full32.py`](gen_full32.py) | Pass 1 with all three layers on WMMA, 32-wide; reads a dumped pass like [`gen_hybrid.py`](gen_hybrid.py) |
| [`gen_down.py`](gen_down.py) | Passes 3 and 6 on WMMA: `gen_down.py 3\|6 32\|64` |
| [`gen_deep.py`](gen_deep.py) | Passes 7, 8 and 9 on WMMA: `gen_deep.py 7\|8\|9 32\|64` |
| [`peak_dot.comp`](peak_dot.comp), [`peak_wmma.comp`](peak_wmma.comp) | Throughput probes (`-DNW= -DNA= -DITERS=`; `-DWAVE= -DNACC= -DITERS=`) |
| [`bench/mbench.c`](bench/mbench.c), [`bench/bench.c`](bench/bench.c) | The benchmark; new: `x.spv@32` / `WAVE=`, and it stops on a missing data file |

To reproduce a hybrid (pass 4 at 4K is level 2; levels are 1 for passes 1, 2, 12; 2 for 3, 4, 5, 10, 11; 3 for 6 to 9):

```
spirv-cross --vulkan-semantics pass4.spv --output pass4.comp
python3 splice3x3.py pass4.comp 64 > h4_64.comp
python3 splice3x3.py pass4.comp 32 > h4_32.comp
glslangValidator -V --target-env vulkan1.3 h4_64.comp -o h4_64.spv
glslangValidator -V --target-env vulkan1.3 h4_32.comp -o h4_32.spv
WEIGHTS=model_data.bin N_DISP=300 ./mbench 2 pass4.spv pass4.spv@32 h4_64.spv h4_32.spv@32
SCRATCH=small_scratch.bin WEIGHTS=model_data.bin N_DISP=1 ./mbench 2 pass4.spv h4_64.spv h4_32.spv@32
```

The passes 3, 6, 7, 8 and 9 generators take no input: their weights are read from the weight buffer when they run, and
the offsets in them are those of FSR 4.1.1.2740 at 4K output.
