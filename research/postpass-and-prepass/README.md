# Postpass, prepass and model-pass probes

What was measured while looking for more speed in FSR 4.1.1 (INT8) after the first postpass
rewrite, including the attempts that did not work. Everything here was run on a Radeon RX 7800 XT
with Mesa 26.2.3 (RADV), at 4K output unless noted.

**A note on the numbers.** Times marked "benchmark" come from a standalone program that runs one
shader repeatedly with pseudo-random inputs. With long bursts (500 dispatches) it agrees with the
game: the 12 model passes add up to 2.03 ms there and to 1.86 ms in Shadow of the Tomb Raider.
With short bursts (20 dispatches) the model passes read about 65% too high, which is how they
were first measured; the model-pass tables below are from long bursts. The postpass and prepass
times do not depend on the burst length.

## Why AMD's stores are slow: the density of the writes

The postpass computes a 2x2 block of pixels per thread and writes each pixel with its own store
instruction, so one instruction writes every other pixel in both directions. Three versions,
all byte-identical in output:

| Postpass | What one store instruction writes | Benchmark | Registers / waves per SIMD |
|---|---|---|---|
| AMD's original | every other pixel, every other row | 2.06 ms | 60 / 24 |
| Lane swap (`postpass_shuffle.py`) | 16 pixels in a row, every other row | 1.44 ms | 72 / 20 |
| Phased (shipped) | solid 32x32 blocks | 0.59 ms | 96 / 16 |
| AMD's original with all stores removed (wrong output) | nothing | 0.49 ms | |

The lane swap was an attempt to keep occupancy high: lanes 16 apart exchange one pixel through a
subgroup shuffle, so each store writes contiguous runs without any workgroup memory or barriers.
It gets more waves than the phased version and is still much slower. Images are stored in 2D
tiles, and what costs time is writing them sparsely in either direction; only whole blocks are
fast. Whole blocks need all four of a thread's pixels at once, so three pixels' values (about 30
numbers per thread) must wait somewhere: in registers, which is the phased version's 16 waves, or
in about 30 KB of workgroup memory, which is far worse. That is why 24 waves per SIMD with dense
writes is out of reach, and why the phased postpass is close to what this pass allows.

### Is it the driver's image layout? Partly, but the rewrite still wins

The driver decides how an image's pixels are arranged in memory (its tiling). To see whether the
sparse-write penalty comes from that choice, Mesa was patched to force a tiling mode for colour
images (`mesa-tiling-override.patch`, Mesa 26.2.3, for this experiment only), and the postpass
benchmark was run against the patched driver. Output was byte-identical in every case.

| Tiling of all images | AMD's postpass | Phased postpass |
|---|---|---|
| `64KB_R_X`, the driver's default | 2.10 ms | 0.60 ms |
| `256KB_R_X` | 2.10 ms | 0.60 ms |
| `64KB_D_X` | 2.44 ms | 0.77 ms |
| Linear (no tiling) | 1.02 ms | 0.85 ms |

The other modes tried were rejected for these images on this GPU.

- **The penalty does depend on the layout:** with linear images AMD's sparse writes cost half as
  much.
- **It is not a fix:** the phased postpass on the default tiling is still far faster than AMD's
  shader on any layout, and linear images make the phased version slower. Linear images are also a
  poor choice for everything else that reads or draws to them, and the driver cannot know which
  images a shader will write sparsely.

Linear tiling applied to some of the images only (the others on the default):

| Linear images | AMD's postpass | Phased postpass |
|---|---|---|
| none | 2.07 ms | 0.60 ms |
| the three written (history, output, recurrent state) | 1.06 ms | 0.66 ms |
| history only | 1.70 ms | 0.61 ms |
| output only | 1.69 ms | 0.61 ms |
| recurrent state only | 1.87 ms | 0.62 ms |
| the two read (input colour, reprojected history) | 1.51 ms | 0.81 ms |
| all five | 0.97 ms | 0.84 ms |

- **The written images carry most of the penalty.** Making only them linear halves AMD's postpass
  (2.07 to 1.06 ms), each of the three contributing 0.2 to 0.4 ms, and costs the phased version
  little (0.60 to 0.66 ms).
- **The read images matter too, in opposite directions.** Linear inputs slow the phased postpass
  (0.60 to 0.81 ms), as expected for texture reads. They speed AMD's up (2.07 to 1.51 ms); see
  below.

Why linear inputs speed AMD's postpass up was narrowed down but not settled:

| Check | Result |
|---|---|
| Which input | only the input colour image (read 9 times per pixel): 2.08 to 1.52 ms. The reprojected history (read once per pixel) makes no difference. |
| Are the reads themselves faster? | No. AMD's postpass with its stores removed takes 0.47 ms on either layout. The gain only exists while the sparse stores are there. |
| With the written images linear too | the gain shrinks to about 0.15 ms (1.06 to 0.91 ms) |
| Where the images sit in memory | no effect: each image shifted by 64 KB, 1 MB and 33 MB, and the linear input by 256 bytes to 32 KB |
| The driver's image compression (DCC) and fast clears | no effect: `RADV_DEBUG=nodcc`, `nofastclears`, `radv_disable_dcc_stores` |
| Other tiled modes for the input | `256KB_R_X` the same as the default, `64KB_D_X` slower (2.20 ms) |

So a linear input removes about a third of the sparse-store penalty without making any read
cheaper.

### The GPU's cache counters: sparse writes make the cache read and rewrite blocks

RADV can record the GPU's performance counters for a single submit (`MESA_VK_TRACE=rgp` with
`MESA_VK_TRACE_PER_SUBMIT=1`), so the benchmark needed no presenting loop. The same Mesa patch
prints each raw counter summed over the capture (`AC_SPM_PRINT=1`). Requests between the GPU's L2
cache and memory, in millions per 5 dispatches of the postpass at 4K (medians of 60 captures;
capturing slows the pass by about 1.4 times, so the times are only for comparing rows):

| Postpass, tiling | Read requests, 64 B | Read requests, 128 B | Write requests | L2 misses | Time while capturing |
|---|---|---|---|---|---|
| AMD's, stores removed, default tiling | 10.2 | 7.5 | 7.0 | 115 | 0.55 ms |
| AMD's, stores removed, linear input | 10.6 | 8.4 | 7.4 | 122 | 0.55 ms |
| Phased, default tiling | 17.8 | 17.3 | 16.1 | 202 | 0.87 ms |
| AMD's, default tiling | 57.9 | 51.2 | 38.7 | 494 | 3.08 ms |
| AMD's, linear input | 45.9 | 49.3 | 34.0 | 410 | 2.22 ms |
| AMD's, linear written images | 31.6 | 36.2 | 26.5 | 288 | 1.43 ms |

(Write requests: the general and the 64-byte write counters added.)

- **This is what the sparse-write penalty is.** With AMD's stores the cache makes five to seven
  times the read requests of the same shader without stores, and 2.4 times the write requests of
  the phased version, for the same pixels. A block that is only partly written has to be fetched
  from memory first, and it is written back more than once because it leaves the cache before the
  other stores have filled it. The phased postpass fills whole blocks, so it stays close to the
  minimum.
- **Why a linear input helps AMD's postpass.** Without stores, the input's layout changes nothing
  (first two rows). With them, a linear input gives 21% fewer 64-byte reads, 12% fewer writes and
  17% fewer L2 misses: the tiled input's reads were pushing partly written output blocks out of
  the cache, and each one pushed out costs a write, and a read when the next store reaches it.
  That confirms the guess above, with the L2 cache as the place where it happens.
- **Linear written images** cut the traffic further, but not to the phased version's level.

Can the phased postpass's remaining traffic be cut the same way? Tried, with no gain in time:

| Phased postpass, pixels one wave writes per store | 64 B reads | 128 B reads | Writes | Benchmark |
|---|---|---|---|---|
| 32x2 (shipped until the pass 11 release) | 17.7 | 17.2 | 16.0 | 0.60 ms |
| 16x4 | 17.0 | 15.3 | 15.2 | 0.60 ms |
| 8x8 (shipped after it) | 16.9 | 15.3 | 15.2 | 0.60 ms |

Letting each wave write a square block instead of two rows removes about a tenth of the traffic
(all three versions byte-identical), but the pass is no faster: once the writes are dense, memory
traffic is no longer what limits it. The reads that remain above the no-store level are the cache
fetching blocks that are about to be overwritten whole, which a shader cannot prevent. The prepass
shows the same thing: its writes add traffic (64 B reads 26 to 38, writes 18 to 35 million), but
removing them saves only 0.02 ms.

In a game the square-block flush makes no difference either. Shadow of the Tomb Raider's
benchmark at 4K, one run each: 108 FPS, 16,736 frames and 3.12 ms of upscaler time with the
shipped 32x2 flush; 108 FPS, 16,778 frames and 3.09 ms with the 8x8 flush. That is 0.25% apart,
within run-to-run variation. The 8x8 flush is shipped all the same, for the traffic it saves.

The counter names are Mesa's (`GL2C_EA_RDREQ_64B`, `GL2C_EA_RDREQ_128B`, `GL2C_EA_WRREQ`,
`GL2C_EA_WRREQ_64B`, `GL2C_MISS`); they are used here to compare rows, not as exact byte counts.

So the shader rewrite is the right place for this fix: even with the written images linear, AMD's
shader takes 1.06 ms against 0.60 ms for the phased one on the default layout, and the driver
cannot know which images a shader will write sparsely.

## How much of each pass is memory traffic

`nomem.py` makes probe versions of a shader that keep all the arithmetic but drop memory traffic:
writes happen only if the value equals an impossible constant, and reads have the thread-dependent
part of their address masked into a small window, so they come from cache. The output is wrong;
only the time matters.

| Benchmark, ms | As is | No writes | Cached reads | Both |
|---|---|---|---|---|
| Postpass (first rewrite) | 0.83 | 0.76 | 0.76 | 0.72 |
| Prepass | 0.47 | 0.45 | 0.46 | 0.42 |
| 12 model passes, total | 2.03 | 1.95 | 2.34 | 2.32 |

Per model pass (pass 11 with its rewrite):

| Pass | As is | No writes | Cached reads | Both |
|---|---|---|---|---|
| 1 | 0.291 | 0.280 | 0.331 | 0.328 |
| 2 | 0.291 | 0.280 | 0.330 | 0.327 |
| 3 | 0.050 | 0.050 | 0.049 | 0.048 |
| 4 | 0.139 | 0.136 | 0.181 | 0.182 |
| 5 | 0.139 | 0.136 | 0.181 | 0.181 |
| 6 | 0.048 | 0.052 | 0.055 | 0.053 |
| 7 | 0.115 | 0.112 | 0.117 | 0.116 |
| 8 | 0.115 | 0.115 | 0.115 | 0.114 |
| 9 | 0.176 | 0.171 | 0.217 | 0.216 |
| 10 | 0.139 | 0.138 | 0.181 | 0.178 |
| 11 | 0.229 | 0.203 | 0.252 | 0.250 |
| 12 | 0.293 | 0.280 | 0.330 | 0.327 |

- **Model passes:** removing every write saves about 4% (0.07 ms). The cached-reads probe runs
  slower than the original in most passes, so it is not a valid lower bound and says nothing
  about what the reads cost: masking the addresses changes the code the compiler produces. What
  the compiled code shows is that the passes are almost all arithmetic: pass 1 is 832 int8 dot
  products and 13 memory instructions out of 1,450. So merging passes to keep data on chip has
  little to gain.
- **Other things tried on the model passes:** the constant-z change that takes pass 11 from 0.60
  to 0.23 ms does nothing for the other 11 passes (each within 0.004 ms). Running them as wave32
  (`RADV_PERFTEST=cswave32`) makes every pass 40 to 65% slower, 2.03 to 3.13 ms in total.
- **Postpass and prepass:** about 14% and 10% memory traffic. What stood out instead was the
  first postpass rewrite's occupancy, which led to the phased version.
- **A trap:** masking each read's own index, instead of the shared base it is computed from, stops
  the compiler from merging neighbouring reads and makes the probe slower still.

One caveat: the benchmark repeats one pass, so its inputs may stay in the GPU's 64 MB cache. In a
game the previous pass has just written them, so they are likely cached there too.

## Memory traffic of every pass, and pass 11's stores

The cache counters (see the tiling section above) for each pass at 4K, per run of the pass. About
200 MB of every figure is a floor of the measurement, present even for the smallest passes.

| Pass | Read from memory | Write requests | Data it writes |
|---|---|---|---|
| Postpass, AMD's | 2,295 MB | 7.8 million | 166 MB |
| Prepass | 1,712 MB | 7.0 million | 99 MB |
| Postpass, phased | 792 MB | 3.2 million | 166 MB |
| Model pass 11, AMD's | 1,018 MB | 3.9 million | 33 MB |
| Model pass 11 with only the constant-z change | 739 MB | 2.6 million | 33 MB |
| Model passes 1, 2, 12 | about 270 MB each | 0.24 million each | 33 MB each |
| The other eight model passes | 208 to 265 MB each | about 0.1 million each | 8 to 16 MB each |

Pass 11, the model's upsampling step, stands out among the model passes: ten times the write
requests of passes that write the same amount. It computes a 2x2 block of outputs per thread, four
words each, and stores every word as soon as it is computed, with the next word's arithmetic in
between, so one store instruction writes 4 bytes in every 32. That is the postpass's sparse-write
pattern again, in a buffer.

`pass11_stores.py` at the top of the repository (applied after `zconst.py`) keeps each row's eight
words in registers and stores them together. The output is byte-identical.

| Pass 11 | Benchmark | Read from memory | Write requests | Registers / waves per SIMD |
|---|---|---|---|---|
| AMD's | 0.60 ms | 1,018 MB | 3.92 million | 48 / 32 |
| Constant-z change only (`zconst.py`) | 0.23 to 0.32 ms, varying between runs | 739 MB | 2.61 million | 60 / 24 |
| With the stores together as well (shipped) | 0.216 ms, steady | 234 MB | 0.15 million | 48 / 32 |

In a game it makes no measurable difference: Shadow of the Tomb Raider's benchmark at 4K gave
108 FPS, 16,780 frames and 3.12 ms of upscaler time with it, against 108 FPS, 16,736 frames and
3.12 ms without it. It removes traffic that does not limit speed on this card. It is shipped since
2026-10-04 all the same: it is never slower, the pass runs at higher occupancy, and the traffic it
removes may matter on GPUs that are short of memory bandwidth, where it has not been tested.

### The prepass's traffic: attributed, but not reducible from the shader

The prepass is the largest remaining source of traffic. Probes that remove one thing at a time
(wrong output; `nomem.py`, with `NOMEM_ONLY=img` or `buf` to pick the stores):

| Prepass probe | Read from memory | Benchmark |
|---|---|---|
| As is | 1,716 MB | 0.482 ms |
| No image write (66 MB of data) | 1,247 MB | 0.463 ms |
| No tensor stores (33 MB of data) | 1,380 MB | 0.468 ms |
| No stores at all | 950 MB | 0.448 ms |
| All reads from cache, stores kept | 911 MB | 0.457 ms |
| Neither | 252 MB (the floor) | 0.420 ms |

Its stores cause about 700 MB of reads for 99 MB written, seven times the data, and its reads
about 700 MB for roughly 125 MB of inputs. Four byte-identical rewrites were tried against that:

| Rewrite | Read from memory | Benchmark |
|---|---|---|
| AMD's prepass | 1,716 MB | 0.482 ms |
| Each quad lane stores one word of the tensor (`prepass_quad.py`) | 1,705 MB | 0.475 ms |
| All stores moved to the end of the shader (`prepass_sync.py late`) | 1,709 MB | 0.479 ms |
| The same, after a workgroup barrier (`prepass_sync.py sync`) | 1,707 MB | 0.480 ms |
| Each wave covers an 8x8 block of pixels instead of 16x4 | 1,783 MB | 0.474 ms |

None of them moves the traffic. It does not come from when the stores happen or how the lanes are
arranged, so it appears to follow from the pass's shape: a thread group covers 16x16 pixels, so
one group can write only 128 bytes of any row of the image or the tensor, and the rest of each
cache block belongs to other groups that run at other times. A replacement shader cannot change
how the pass is dispatched. The time at stake is small in any case: removing every store saves
0.03 ms.

### The sharpening pass (RCAS): at the memory bandwidth limit

FSR 4's sharpening pass only runs when sharpening is enabled. In the benchmark it takes 0.258 ms
at 4K, reads 1,123 MB and makes 4.7 million write requests. Each thread sharpens four pixels,
8 apart, so every store instruction of a wave writes a solid 8x8 block: the writes are dense.

| Sharpening pass | Benchmark |
|---|---|
| AMD's | 0.258 ms |
| Stores removed (wrong output) | 0.074 ms |
| All reads from cache, stores kept (wrong output) | 0.084 ms |
| Neither | 0.064 ms |
| The four stores moved to the end of the shader (byte-identical) | 0.250 ms |

The arithmetic is only about 0.06 ms; the rest appears only when the pass both reads its 66 MB
input and writes its 66 MB output. Moving that much data takes about 0.21 ms at this card's memory
bandwidth (624 GB/s), close to what is measured, and the two images together do not fit in the
GPU's 64 MB cache. So the pass looks limited by memory bandwidth, not by its code, and nothing in
the shader can change how much it must read and write. Moving the stores to the end, which lets
the compiler group the reads, gains 3%. Not shipped.

## The prepass

**A caution about the prepass benchmark (2026-10-05).** `pbench.c` feeds the prepass constant
colour, depth and motion. A rewrite that regroups floating-point sums or shares reciprocals gives
identical output on such inputs and different output on real ones: a community prepass that this
benchmark calls identical differs in 93% of pixels when run in AMD's pipeline on a moving scene
(see [community shader set](../community-lossy-set)). "Bit-exact" for the prepass rewrites below
therefore means "identical in this benchmark"; none of them was shipped. Anything for the prepass
has to be checked in the full pipeline with varied inputs, as the shipped postpass and pass 11
were.

**The prepass on RDNA2 (2026-10-05).** Compiled for an RX 6800, AMD's prepass is the same code as
on RDNA3: the same dot-product instructions and about 660 instructions per thread. It needs 56
registers there against 48 on RDNA3, so fewer threads run at once, but on RDNA3 the prepass was
not sensitive to that. There is no RDNA2-specific flaw in it to fix.

AMD's prepass takes 0.47 ms in the benchmark (0.44 ms in the game), runs 32 waves per SIMD with 48
registers, and has about 506 arithmetic instructions per thread.

| Probe | Benchmark | What it shows |
|---|---|---|
| AMD's prepass | 0.47 ms | |
| Model input stored as constants (wrong output) | 0.37 ms | the part that builds the model's input costs about 0.10 ms |
| All lanes share one set of weights (wrong output) | 0.435 ms | of that, fetching per-lane weights is about 0.035 ms |
| `prepass_quad.py` (byte-identical) | 0.475 ms | 9% fewer arithmetic instructions, about 1.5% faster |

`prepass_quad.py` is a correct rewrite: in each 2x2 quad only one lane quantised and stored all 16
channels while the other three idled, and the rewrite gives each lane a quarter of that work. It
is not shipped, because 0.007 ms is not worth one more override file per game. The rest of the
prepass is reprojection arithmetic at full occupancy, with nothing found to remove.

## Occupancy on other GPUs

Compiled, not run: Mesa's `amdgpu` drm-shim lets RADV compile for a GPU that is not installed.
Registers per lane / waves per SIMD:

| | RX 7900, 7800, 7700 | RDNA2 (RX 6000, Steam Deck, 680M), RX 7600, 780M, 890M |
|---|---|---|
| Postpass, AMD's | 60 / 24 | 64 / 16 |
| Postpass, first rewrite | 256 / 4 | 240 to 256 / 4 |
| Postpass, phased | 96 / 16 | 80 / 12 |
| Pass 11, AMD's | 48 / 32 | 56 / 18 |
| Pass 11, rewrite | 60 / 24 | 64 / 16 |

Only the larger RDNA3 chips have the bigger register file. On every chip the phased postpass gives
up a similar share of occupancy (25 to 33%), so occupancy does not explain why integrated GPUs are
reported slower with the rewrites; their memory system is the more likely reason. Timings on those
GPUs have not been measured here.

## Files

| File | What it is |
|---|---|
| `nomem.py`, `run_nm.sh` | the no-memory probes and the script that ran them over the model passes |
| `nullify.py` | replaces a shader's body with an empty one (used for the in-game breakdown of FSR 4's time) |
| `postpass_shuffle.py` | the lane-swap postpass |
| `postpass_taps.py` | the postpass's nine neighbourhood reads without their branches (idea from a [community set](../community-lossy-set)): bit-exact, 3% slower on an RX 7800 XT, reported faster on RDNA2 |
| `prepass_quad.py` | the prepass rewrite |
| `prepass_sync.py` | the prepass with its stores moved to the end (`late`) and synchronised (`sync`) |
| `mesa-tiling-override.patch` | the experimental Mesa changes behind the tiling and counter tables (`AC_FORCE_SWIZZLE=<mode>`, `AC_FORCE_SWIZZLE_MASK=<bit per image>`, `AC_PRINT_SWIZZLE=1`, `AC_SPM_PRINT=1`) |
| `pbench.c` | the prepass benchmark; the postpass and model-pass ones are in [`../wmma/bench`](../wmma/bench) |

The scripts take `spirv-dis` text of shaders from a vkd3d-proton dump and write text for
`spirv-as`, like the scripts at the top of the repository. They are kept as they were used, as a
record; the shaders they produce are not shipped.
