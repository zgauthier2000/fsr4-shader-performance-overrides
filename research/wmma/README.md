# Can WMMA speed up FSR 4.1.1's model passes on RDNA3?

Short answer: no. A version of model pass 1 that does its convolutions with WMMA was built and is
bit-exact, but it is slower than AMD's shader: 0.41 ms against 0.29 ms. The multiplies themselves
get about twice as fast; everything that has to happen around them costs more than that saves. For
the deepest passes, the best case for WMMA, the matrix products alone already cost as much as
AMD's complete pass.

This is a record of what was tried, how it was measured and why it loses, so that nobody has to
repeat it. The sources are in this folder.

## Background

FSR 4.1.1's INT8 model spends most of its time in 12 "model passes", compute shaders that run a
small convolutional network on int8 tensors. AMD's shaders do the arithmetic with packed dot
products: one instruction multiplies four int8 pairs and adds them up (`v_dot4_i32_iu8` on
RDNA3).

RDNA3 also has WMMA (wave matrix multiply-accumulate): one instruction multiplies two 16x16
matrices and accumulates into a third. Vulkan exposes it as cooperative matrices
(`VK_KHR_cooperative_matrix`). Since a convolution is a matrix product, the question was whether
the model passes would run faster on WMMA.

The Bloodborne port this repository derives from had tried it once and measured 0.49 ms against
0.30 ms for pass 1, without publishing the details.

## Setup

- Radeon RX 7800 XT (Navi 32, RDNA3), Mesa 26.2.3 (RADV), Linux.
- FSR 4.1.1.2740, INT8 model, shaders as vkd3d-proton translates them for 4K output. Pass 1 then
  works on a 1920x1080 tensor with 16 int8 channels per pixel.
- All timings below are from this one GPU.

### What the driver offers

`bench/cmprops.c` lists the cooperative matrix configurations. On this setup every one is 16x16x16:

| A | B | Result | Saturating variant |
|---|---|---|---|
| i8 or u8 | i8 or u8 | i32 or u32 | yes, for i32 |
| f16 | f16 | f16 or f32 | no |

Signed int8 times signed int8 into int32, without saturation, is exactly the model's arithmetic,
so a bit-exact WMMA version is possible in principle. vkd3d-proton also translates WMMA itself, so
the feature is enabled on the device games get.

## How it was measured

`bench/mbench.c` is a small Vulkan program that runs a model pass exactly as vkd3d-proton dumped
it, with the same descriptor layout, on a tensor buffer and weights buffer filled with
pseudo-random bytes.

- **Correctness.** Each variant runs once from the same starting buffer. The whole 83 MB buffer is
  read back and compared with the first variant's, so "identical" means every byte the pass wrote.
- **Timing.** 100 dispatches between two GPU timestamps, repeated nine times; the median is
  reported. Dispatches are separated by barriers, as they are in the game.
- **Two data sets.** Full-range random bytes saturate nearly every value, which would hide rounding
  mistakes. `make_test_data.py` makes a second set with small values and small biases so the
  rounding paths are exercised. Both were used for the bit-exact checks.

Two lessons about the method, learned the hard way:

- **Short bursts mislead.** Timing a pass alone in a burst of a few dispatches overstated its cost
  by 40-70%, apparently because the GPU's clocks had not ramped up. Summed that way the 12 passes
  came to about 3.5 ms; run back to back in sequence they take 2.1 ms, which matches what the game
  shows. Everything here uses sustained runs.
- **The harness can fault the GPU.** A shader given the wrong root-constant layout indexes a
  descriptor that is not there. That caused GPU page faults and ring resets several times during
  this work. `mbench` now reads the layout from the shader, but treat it as research code.

## What pass 1 computes

Read from the dumped shader with `pp.py`, which prints a pass as condensed pseudo-code. Passes 2
and 12 have the same structure.

1. **3x3 convolution, 16 to 16 channels.** Weights are constants inside the shader; biases come
   from the weights buffer. Rescale: `(t + 63 + ((t >> 7) & 1)) >> 7`, clamped to int8. This is
   round-half-to-even of `t / 128`.
2. **1x1 convolution, 16 to 32 channels, then ReLU.** Rescale: `(t + 127 + ((t >> 8) & 1)) >> 8`,
   clamped.
3. **1x1 convolution, 32 to 16 channels.**
4. **Residual.** `roundEven((input / 64 + t / 4096) * 64)` in float, through int16, clamped to
   int8, added back to the input position of the output tensor.

Per pixel that is 832 packed dot products (576 for the 3x3, 128 for each 1x1) and 64 rescaled
values. The compiled shader is almost nothing else: 832 `v_dot4_i32_iu8` out of 1450 instructions,
60 registers, weights loaded once per wave.

## Mapping it to WMMA

One wave handles 16 pixels per matrix product:

- **A** = weights `[output channel][input channel]`
- **B** = the 16 pixels as columns, 16 channel bytes each, straight from the tensor
- **C** = `[output channel][pixel]`, int32

The 3x3 convolution is nine products (one per tap), each 1x1 layer two. That is 13 WMMA
instructions per 16 pixels in place of 13,312 dot-product lane operations.

A workgroup still covers 64 pixels of a tensor row, because AMD's DLL fixes the dispatch grid, so
the shader loops over four tiles of 16.

### What RADV does with cooperative matrices on RDNA3

Found by reading `radv_nir_lower_cooperative_matrix.c` and confirmed in the compiled code. These
decide whether a WMMA shader is fast or slow:

- **A and B are 16 elements per lane**, with lanes 0-15 replicated across the wave.
- **Layout decides the load cost.** A loaded row-major and B loaded column-major each become one
  16-byte load per lane. Any other combination becomes 16 single-byte loads plus byte shuffling.
  The first probe got this wrong and was twice as slow.
- **The accumulator is spread over the wave.** Invocation `(g = id / 16, p = id % 16)` owns
  `C[g + i * (wave / 16)][p]` as element `i`: 8 elements per lane at wave32, 4 at wave64.
- **Elements can be read and written per lane without memory.** Indexing a matrix (`m[i]`) gives
  the invocation's own elements. This is what makes a register-only version possible.
- **A workgroup of 32 threads gets 32-wide waves** with no pipeline flag, which matters for
  deployment through a shader override.

## Results

All times are sustained medians for the full 1920x1080 tensor.

### Probes: the multiply alone

`probe*.comp` do only the 3x3 convolution's arithmetic and then write truncated bytes. They are
throughput tests, not real passes.

| Probe | Wave | Time |
|---|---|---|
| Wrong layouts (`probe.comp`: both matrices row-major, int8 buffers) | 64 | 0.392 ms |
| Right layouts (`probe2.comp`) | 64 | 0.198 ms |
| Right layouts | 32 | 0.158 ms |
| Output writes only, no products (`-DTAPS=0`) | 64 / 32 | 0.068 / 0.072 ms |
| Nine products, operands loaded once (`probe3.comp -DMODE=1`) | 64 / 32 | 0.155 / 0.153 ms |

Derived:

- The nine products alone cost about 0.085 ms; loading their operands adds about 0.045 ms at
  wave64 and almost nothing at wave32.
- So the 3x3 convolution costs about 0.09 ms with WMMA at wave32. AMD's dot-product version of the
  same convolution is roughly 0.17 ms (its share of the 0.29 ms pass, estimated from the
  instruction count).
- One `v_wmma_i32_16x16x16_iu8` costs about as much as eight packed-dot instructions while doing
  the work of sixteen. **WMMA roughly doubles multiply throughput; it does not do more than that.**

### The whole pass

`gen_pass1.py` and `gen_pass1b.py` generate complete WMMA versions of pass 1 from the dumped
shader, extracting its weights. Both produce output byte-for-byte identical to AMD's on both data
sets.

| Version | Wave | Time | Registers | Waves per SIMD |
|---|---|---|---|---|
| AMD's shader (packed dot products) | 64 | 0.294 ms | 60 | 24 |
| WMMA, layers handed over through shared memory (`gen_pass1.py`) | 32 | 0.512 ms | 144 | 5 |
| same | 64 | 0.549 ms | | |
| WMMA, layers kept in registers (`gen_pass1b.py`) | 32 | 0.414 ms | 192 | 8 |
| same | 64 | 0.510 ms | 108 | 14 |

The first version stores each layer's accumulator to shared memory, rescales it per lane, and
loads the result back as the next layer's matrix. The second uses per-lane element access and
`subgroupShuffleXor(x, 16)` to gather a pixel's bytes from the lanes that hold them, so nothing but
the weights goes through shared memory.

### Where the 0.414 ms goes

Variants of the register version with parts removed (these no longer compute the right result;
they only show what each part costs):

| Variant | Time | So the removed part costs |
|---|---|---|
| Full | 0.414 ms | |
| Without the rescaling arithmetic | 0.326 ms | 0.088 ms |
| Without the cross-lane gathering | 0.391 ms | 0.023 ms |
| Without both | 0.304 ms | |

What is left at 0.304 ms is the 13 products per tile with their loads (about 0.13 ms), plus
packing bytes into words and into matrices, the final store, and loading the weight matrices.
**Even with no rescaling and no gathering, the WMMA pass is already slower than AMD's complete
shader.**

### Was it register pressure?

A related project on another AMD chip found that waves per SIMD mattered more than instruction
count, and the WMMA shader does run at a third of AMD's occupancy. Two tests:

1. **Use fewer registers.** Loading the 13 weight matrices and the biases at the point of use cut
   live registers before scheduling from 123 to 76. The allocator still ended at 168, occupancy
   stayed at 8, and the time did not change (0.416 ms).
2. **Measure the sensitivity.** `occ_w32.comp` is the multiply probe with `K` extra values forced
   to stay in registers. Each row compares it with a build that executes the same added
   instructions without holding the values.

| K | Registers | Waves per SIMD | Held | Not held |
|---|---|---|---|---|
| 72 | 120 | 12 | 0.237 ms | 0.229 ms |
| 104 | 168 | 9 | 0.267 ms | 0.263 ms |

Falling from 16 to 9 waves per SIMD cost 2-3% at wave32. Register pressure is not the reason.
(At wave64 the same test showed 14-28%, but there the extra loads themselves are a confound.)

A trap in this kind of experiment: the compiler sinks buffer loads to their use and folds running
sums, so "held" values must be distinct loads that are combined late with something only known at
the end. The first two attempts changed nothing because of that.

## Why it loses

1. **Only the multiplies get faster, and only twofold.** They are about 60% of AMD's pass, so
   doubling them could save 0.08-0.09 ms at the very best.
2. **The rescaling is unchanged work.** 64 values per pixel still have to be rounded and clamped
   one by one. Matrices offer no elementwise shift, round or clamp, so this runs as ordinary
   per-lane code, 0.09 ms.
3. **Getting data into and out of matrices costs more than the saving.** A lane holds every second
   channel of a pixel, not a contiguous word, so bytes have to be exchanged between lanes and
   repacked for every layer, and again for the output.
4. **A wave handles 16 pixels per product.** The surrounding code runs four times per workgroup
   where AMD's runs once for 64 pixels.

With perfect packing the floor would be about 0.25-0.28 ms, roughly 10% under AMD's shader, for
three of the twelve passes. That is about 0.05 ms per pass, and the two earlier gains predicted by
this benchmark that were that small could not be seen in a game.

## The deeper passes

The analysis above says WMMA can only win where there is much more multiply work for each value
that has to be rounded and repacked afterwards. Counted from the shader code (4K output):

| Pass | Layers | Dot ops per thread | Values rounded per thread | Ratio | Time alone |
|---|---|---|---|---|---|
| 1, 2, 12 | 3x3 16→16, 1x1 16→32, 1x1 32→16 | 832 | 64 | 13 | 0.29 ms each |
| 4, 10 | 3x3 16→16, 1x1 32→64, 1x1 64→32 | 1,600 | 112 | 14 | 0.16 ms each |
| 6 | about 2,048 dot ops | 2,048 | about 190 | about 11 | 0.07 ms |
| 7, 8 | 3x3 16→32, 1x1 64→128, 1x1 128→64 | about 5,200 | 224 | 23 | 0.14 ms each |
| 9 | as 7, plus a 2x upsampling layer | about 7,300 | about 350 | 21 | 0.18 ms |

Passes 4 and 10 have more channels but the same ratio as pass 1. Passes 7, 8 and 9 are the only
ones with clearly more multiply work per value, so pass 7 was tested as the best case.

`probe7.comp` does only the matrix products of pass 7's three layers: 82 WMMA instructions per 16
pixels, with the weight loads a real kernel would need, and none of the rounding or repacking
between layers. That makes it a lower bound for any WMMA version of the pass.

| Pass 7 variant | Time |
|---|---|
| AMD's complete pass (packed dot products, everything included) | 0.142 ms |
| Probe, each layer's result through memory to the next (`-DMODE=0`) | 0.218 ms |
| Probe, no intermediate memory traffic, layer 2/3 operands read from memory (`-DMODE=1`) | 0.12-0.13 ms |
| Probe, the same with layer 2/3 operands cache-resident (`-DMODE=2`) | 0.12 ms |

64-wide waves give the same 0.12-0.13 ms. **The products alone cost about as much as AMD's whole
pass.** Adding the rounding and repacking, which cost pass 1 about as much again as its products,
puts a real WMMA pass 7 well above AMD's. Passes 8 and 9 have the same layer shapes.

That settles it: on RDNA3 there is no FSR 4.1.1 INT8 model pass that WMMA can make faster.

## Comparison with d4r

[d4r](https://github.com/countervolts/d4r) runs NVIDIA's DLSS on RDNA3 and gets a real gain from
WMMA, so it is worth asking why it works there and not here. Its documentation and kernel sources
(read, not run) give a consistent answer: the workload is shaped differently.

| | DLSS 4 layers in d4r | FSR 4.1.1 INT8 pass 1 |
|---|---|---|
| Layer type | Transformer blocks over 8x8 token windows: projections, 64x64 attention, an MLP | Small convolutions |
| Channels | 32 per attention head, several heads | 16 |
| Matrix work per value written out | Several products in a row, intermediates kept in shared memory | One 16-deep product per layer |
| Work between products | Float conversion and multiply-add | Integer round and clamp for 64 values per pixel |
| Exactness | Relaxed (f32 accumulation, some 8-bit re-quantization skipped) | Must match AMD's output |

WMMA pays off when there is a lot of matrix work for each value that has to be handled one by one
afterwards. DLSS has that; FSR 4.1.1's 16-channel convolutions are close to the opposite case.

What d4r confirms about the approach used here:

- **The same RDNA3 register layout,** described in its `kernels/common/wmma_layout.h`: 16 K
  values per lane, replicated across the two halves of the wave, accumulator rows spread every
  second row.
- **The same cross-lane exchange.** d4r uses `permlanex16`; the register-only version of pass 1
  compiles its eight exchanges to `v_permlanex16_b32` as well.
- **Occupancy does not help.** d4r lists "occupancy tweaks (VGPR caps, waves-per-EU hints)" under
  what did not help, matching the tests above.
- **Weights in matrix layout are cheap to arrange.** d4r prepares them once in a separate kernel;
  here they are copied from constants per workgroup, which costs about 0.007 ms.

What it adds:

- **On RDNA4 the exchange disappears.** There, the accumulator layout of one product is already the
  operand layout of the next. RDNA4 runs AMD's FP8 FSR 4 model rather than the INT8 one studied here,
  so this does not help the passes in this repository.
- **d4r controls the compiler.** Its kernels are HIP code built with AMD's LLVM toolchain, with
  explicit matrix instructions. FSR's shaders have to pass through D3D12, vkd3d-proton and RADV, so
  that level of control is not available.
- **64-wide waves for float-heavy kernels without matrix work** sped up one of d4r's kernels
  (0.89 to 0.77 ms). RADV already compiles FSR's compute passes as 64-wide.

The deeper passes, the ones with the most matrix work per value, were tested as a result; see
[The deeper passes](#the-deeper-passes).

## Not tried

- **A full WMMA version of a deeper pass.** Not needed: the lower-bound probe for pass 7 already
  costs as much as AMD's complete pass.
- **RDNA4.** Its matrix layout is different (no replication, and a transposing load), and AMD's
  own FSR 4 model for it uses FP8 WMMA. Nothing here was measured on it.
- **Higher occupancy for the WMMA pass itself.** Only the probe was tested, and only downward.

## Files

| File | What it is |
|---|---|
| `probe.comp`, `probe2.comp`, `probe3.comp` | Multiply-only probes. `-DTAPS=n` and `-DMODE=n` select variants; change `local_size_x` to 32 for wave32 |
| `occ_w32.comp` | The occupancy probe; `-DMODE=0 -DK=n` |
| `probe7.comp` | Lower-bound probe for pass 7; `-DMODE=0..2`, `-DWAVE=32` or `64`; run with `mbench 3` |
| `gen_pass1.py` | Generates the shared-memory WMMA version of pass 1, 2 or 12 from a dumped pass |
| `gen_pass1b.py` | Generates the register-only version |
| `pp.py` | Prints a dumped model pass as condensed pseudo-code |
| `make_test_data.py` | The small-value data set |
| `bench/mbench.c`, `bench/bench.c` | The benchmark (`mbench.c` includes `bench.c`) |
| `bench/cmprops.c` | Lists the driver's cooperative matrix configurations |

To reproduce, with a vkd3d-proton shader dump of a game running FSR 4.1.1 at 4K (pass 1 is
`b801eac21966703c` there) and the Vulkan headers:

```
gcc -O2 bench/mbench.c -o mbench -lvulkan
spirv-dis dump/b801eac21966703c.spv -o pass1.spvasm
python3 gen_pass1b.py pass1.spvasm 32 > pass1_wmma.comp
glslangValidator -V --target-env vulkan1.3 pass1_wmma.comp -o pass1_wmma.spv
N_DISP=100 ./mbench 1 dump/b801eac21966703c.spv pass1_wmma.spv
```

`mbench` prints each variant's median time and whether its output is identical to the first one's.
