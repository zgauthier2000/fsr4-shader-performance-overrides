# WMMA for the 3x3 layer only: the hybrid split

[Back to the WMMA write-up](README.md) · [Research index](../README.md)

> [!NOTE]
> **Research, not a download.** Nothing on this page is in any release. All timings are from one card
> (Radeon RX 7800 XT, Linux, Mesa 26.2.3 RADV), in the benchmark harness, not in a game. Windows was not measured.

## In short

A community member sent three things: a benchmark suggesting that FSR 4.1.1's pass 1 runs 1.56× faster when its
3x3 convolution uses WMMA and its two 1x1 convolutions keep AMD's packed dot products, a test showing that AMD's
Windows driver runs int8 WMMA correctly through D3D12, and a D3D12 version of pass 1 built that way. The
[earlier WMMA work](README.md) had put every layer on WMMA, never only the 3x3 one, so the split was built and measured.

- **On Linux and under Proton it is slower.** Both hybrid versions give AMD's output byte for byte, but the faster one
  takes 0.331 ms against 0.292 ms for AMD's pass 1 (+13%).
- **Why:** RADV runs AMD's pass with 64-wide waves. In that mode the card's packed dot products are about as fast
  as int8 WMMA, so replacing 576 of them with 36 WMMA instructions saves nothing, and moving data between lanes
  costs extra.
- **Where it could still pay off:** forced to 32-wide waves, AMD's pass takes 0.452 ms, and both hybrids beat that
  (0.329 and 0.372 ms). Whether AMD's Windows driver runs these passes with 32-wide waves is unknown. If it does, the
  split could save time on Windows. Simply running AMD's own shader with 64-wide waves might save more, with no
  change to the picture.
- **A flaw in the harness, now fixed:** with random input, nearly every value hits its clamp, so a
  deliberately broken pass still came out "identical". The checks on this page use AMD's real model data, and the
  earlier WMMA results were checked again with it (still identical).

## What the community member measured

Their benchmark (HIP on Windows, RX 7800 XT, a stand-in for pass 1 at the 1080p output size) reported:

| Their build | Time per launch | Compared with their dot-product build |
|---|---|---|
| Dot products only | 393 µs | 1.00× |
| WMMA for every layer | 369 µs | 1.07× |
| WMMA for the 3x3, dot products for the 1x1s | 250 µs | 1.56× |
| WMMA, 3x3 layer alone | 131 µs (dot products: 311 µs) | 2.38× |

They also measured the card's peak rates: 33.5 trillion int8 multiply-adds per second with WMMA and 17.7 with
packed dot products.

Their dot-product build is not AMD's shader, though. Scaled to the 4K output size it would take about 1.6 ms;
AMD's real pass 1 takes 0.29 ms on the same card in our harness. So the question for this project was whether the
split beats **AMD's** shader, not a stand-in.

## The hybrid shader

[`gen_hybrid.py`](gen_hybrid.py) reads the weights out of AMD's dumped pass (the same extraction as
[`gen_pass1b.py`](gen_pass1b.py)) and writes a GLSL compute shader:

1. **3x3 convolution, 16 to 16 channels, with WMMA.** As in the register-only WMMA version: weights as the A matrix,
   16 pixels as the columns of B, nine products per tile of 16 pixels, four tiles per 64-pixel workgroup.
2. **Rescale** each accumulator value to int8 exactly as AMD's shader does.
3. **Hand over.** After the product, each lane holds only some channels of one pixel (every second channel with
   32-wide waves, every fourth with 64-wide). One exchange between lanes gives each lane all 16 channels of its own
   pixels:
   - **32-wide waves:** 2 lanes per pixel; each lane gets two whole pixels, using four `subgroupShuffleXor`.
   - **64-wide waves:** 4 lanes per pixel; each lane gets one whole pixel, using three.
4. **The two 1x1 convolutions, the residual and the store with packed dot products,** one pixel per lane, the same
   arithmetic as AMD's shader.

## Results

Pass 1 at 4K output (1920x1080 tensor), median of sustained runs (500 dispatches per timing):

| Version | Waves | Time | vs AMD's | Registers | Waves per SIMD | Instructions |
|---|---|---|---|---|---|---|
| AMD's shader | 64-wide | 0.292 ms | | 60 | 24 | 1,450 |
| Hybrid | 64-wide | 0.331 ms | +13% | 72 | 20 | 1,248 |
| Hybrid | 32-wide | 0.372 ms | +27% | 120 | 11 | 2,034 |
| Every layer on WMMA ([earlier](README.md#the-whole-pass)) | 32-wide | 0.409 ms | +40% | 192 | 8 | |

All of them give AMD's output byte for byte (checks below).

The 64-wide hybrid has fewer instructions than AMD's shader (256 dot products and 36 WMMA instead of 832 dot
products) and is still slower.

### Where the time goes

Variants of the 64-wide hybrid with parts removed (their output is wrong; they only show what each part costs):

| Variant | Time |
|---|---|
| Full: 9 taps per tile | 0.331 ms |
| 5 taps per tile | 0.263 ms |
| 1 tap per tile | 0.199 ms |
| 9 products per tile, but their input loaded only once | 0.314 ms |

Derived:

- One WMMA instruction with its input load costs about 0.0041 ms over the whole tensor, or about 0.0036 ms without the
  load. The 36 per workgroup cost about 0.13 ms, plus about 0.017 ms for loading their inputs.
- The 576 dot products they replace are 40% of the instructions in AMD's 0.292 ms pass, about 0.12 ms if every
  instruction costs the same (an estimate). The [earlier write-up](README.md#probes-the-multiply-alone) put the 3x3
  layer at about 0.17 ms from a different split. **Either way, the WMMA layer costs about as much as the dot products
  it replaces.** The lane exchange and lower occupancy then make the hybrid slower.

### Why WMMA does not win here

AMD's pass 1 does 3,328 multiply-adds per pixel. Over the 1920x1080 tensor in 0.292 ms, that is about 23.6 trillion
per second, including everything else the pass does. That is above the 17.7 trillion the community member measured
as the dot-product peak, which therefore cannot be the peak for AMD's shader as RADV runs it.

Our reading (not measured directly): their dot-product peak was measured with 32-wide waves (HIP's default on
RDNA3), and with 64-wide waves the card's dot products run at about twice that rate, close to WMMA's 33.5. Two
measurements support it:

- AMD's own pass slows from 0.292 to 0.452 ms (+55%) when RADV is made to use 32-wide waves
  (`RADV_PERFTEST=cswave32`).
- The hybrid's dot-product part is faster with 64-wide waves too (0.331 against 0.372 ms).

So WMMA's 2× advantage holds only against dot products in 32-wide waves. RADV already runs AMD's passes 64-wide,
so on Linux and under Proton nothing is left to gain.

## The 32-wide case

| Pass 1, 4K output | Time |
|---|---|
| AMD's shader, 64-wide (as RADV runs it) | 0.292 ms |
| AMD's shader, forced 32-wide | 0.452 ms |
| Hybrid, 64-wide | 0.329 ms |
| Hybrid, 32-wide | 0.372 ms |

If a driver runs AMD's INT8 model passes with 32-wide waves, the hybrid is 18-27% faster than AMD's pass 1. Passes 2
and 12 have the same structure, so roughly 0.25-0.37 ms per 4K frame in this harness (an estimate from these
numbers; passes 2 and 12 were not built here. Built since, on [WMMA on every model pass](every-pass.md): with 32-wide
waves requested per pipeline they take 0.362 and 0.364 ms against 0.458 ms for AMD's passes run 32-wide).

**Whether AMD's Windows driver does that is not known.** This project measures DLLs only under Proton, where RADV
picks the wave size. One reading points that way but does not show it: on a Windows RX 7800 XT, a tester measured
3.90 ms for the exact DLL at 4K, against 3.18 ms under Proton on the same card model. That gap could have other
causes.

If Windows does run these passes 32-wide, there is a simpler experiment than the hybrid: ask for 64-wide waves for
AMD's own model passes (Shader Model 6.6's `WaveSize` attribute). In this harness that would be worth 0.16 ms per
pass, more than the hybrid's 0.12 ms, and the output would stay AMD's byte for byte.

**Tried since** (Windows timing kit 2026-10-15.2: DLLs that ask for 64-wide waves on every INT8 pass, and a 32-wide
control). Under Proton the request reaches the driver: the 32-wide control takes 4.50 ms at 4K against 3.15 ms. On
Windows, a tester's RX 6600 (RDNA2) gave the same times with the 32-wide control as without it, and up to 5% more with
64-wide waves, so there the driver appears to run these passes 32-wide already; RDNA2 has no WMMA. A tester's RX 7800 XT
saw no change with 64-wide waves; whether its 32-wide control was run is not known. So for RDNA3 on Windows the
question stays open.

## The D3D12 test and port

The community member's D3D12 test is useful for any Windows WMMA experiment. On their RX 7800 XT (driver
32.0.32015.2008), AMD's driver extension lowered signed int8 16x16x16 WMMA correctly, with these constraints:

- **The shader must be compiled with validation on** (unvalidated DXIL is rejected).
- **The shader must not branch around the matrix instructions** (a run-time switch around them crashed the driver's
  shader compiler).
- **The root signature must include AMD's extension slot** (a UAV in register space 2147420894). Whether
  FSR 4.1.1's INT8 passes already have it is not known.

We did not run their D3D12 pass 1 (it needs Windows), but reading it, three things matter for anyone building on it:

- **Final scale:** it scales the last layer by 1.1875 × 2⁻¹². AMD's shader (the same file, read from the DLL) uses
  2⁻¹². Built into our harness with that one constant changed, the pass differs from AMD's in 27 of 33 million
  bytes.
- **Wave size:** it assumes 32-wide waves (it picks its tiles from the thread index divided by 32). With 64-wide
  waves, one wave would take two paths around the matrix instructions, the case the D3D12 test saw crash the
  driver's compiler. A `WaveSize(32)` attribute would make that assumption explicit.
- **Handoff:** it passes the 3x3 result through 4 KB of shared memory and a barrier. The hybrid here keeps it in
  registers; the [earlier write-up](README.md#the-whole-pass) found the shared-memory handoff slower.

## How it was checked

- **Byte for byte.** [`bench/mbench.c`](bench/mbench.c) runs each version once from the same buffer and compares
  all 83 MB it can write.
- **Real model data.** The weights buffer is AMD's real data (the timing kit's `shaders/model_data.bin`), loaded
  with `WEIGHTS=`.
- **Two inputs.** The tensor is random bytes, and separately the small values from
  [`make_test_data.py`](make_test_data.py), loaded with the new `SCRATCH=` option.
- **The check catches errors.** With this data, the 5-tap variant differs from AMD's output in 25 to 30 million
  bytes, and the wrong-scale variant in 27 million.

**A correction to the earlier write-up.** It says both data sets were used for the bit-exact checks, but the
published `mbench.c` could only load the weights file, not the small-value tensor. With random data, a 5-tap
variant came out "identical" here. All four earlier WMMA versions of pass 1 (`gen_pass1.py` and `gen_pass1b.py`,
32- and 64-wide) were checked again with the real model data on both inputs: all give AMD's output byte for byte, so
the earlier results stand.

## Not tried

- Windows, and any card but the RX 7800 XT. RX 6000 cards have no WMMA. RX 9000 cards use AMD's FP8 model, not
  these INT8 shaders.
- ~~Passes 2 and 12 as hybrids~~: done since, with every other pass, on [WMMA on every model pass](every-pass.md).
- A game. Nothing here was built into an override folder or a DLL.
- ~~AMD's own passes with 64-wide waves on Windows~~: in the Windows timing kit since 2026-10-15.2 (above).

## Files

| File | What it is |
|---|---|
| [`gen_hybrid.py`](gen_hybrid.py) | Generates the hybrid version of pass 1, 2 or 12 from a dumped pass; second argument 32 or 64 |
| [`bench/mbench.c`](bench/mbench.c) | The benchmark; `SCRATCH=<file>` (new) and `WEIGHTS=<file>` load the two buffers |
| [`make_test_data.py`](make_test_data.py) | The small-value data set |

To reproduce (pass 1 at 4K is `b801eac21966703c` in a vkd3d-proton dump; see the [main write-up](README.md#files)):

```
spirv-dis dump/b801eac21966703c.spv -o pass1.spvasm
python3 gen_hybrid.py pass1.spvasm 64 > hybrid64.comp
glslangValidator -V --target-env vulkan1.3 hybrid64.comp -o hybrid64.spv
WEIGHTS=model_data.bin N_DISP=500 ./mbench 1 dump/b801eac21966703c.spv hybrid64.spv
SCRATCH=small_scratch.bin WEIGHTS=model_data.bin N_DISP=20 ./mbench 1 dump/b801eac21966703c.spv hybrid64.spv
RADV_PERFTEST=cswave32 N_DISP=500 ./mbench 1 dump/b801eac21966703c.spv hybrid64.spv     # AMD's pass forced 32-wide
```
