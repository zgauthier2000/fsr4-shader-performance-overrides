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
  (0.60 to 0.81 ms), as expected for texture reads. They speed AMD's up (2.07 to 1.51 ms), which
  is not explained; the two effects add up to the "all five" row.

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

## The prepass

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
| `prepass_quad.py` | the prepass rewrite |
| `mesa-tiling-override.patch` | the experimental Mesa change behind the tiling table (`AC_FORCE_SWIZZLE=<mode>`, `AC_FORCE_SWIZZLE_MASK=<bit per image>`, `AC_PRINT_SWIZZLE=1`) |
| `pbench.c` | the prepass benchmark; the postpass and model-pass ones are in [`../wmma/bench`](../wmma/bench) |

The scripts take `spirv-dis` text of shaders from a vkd3d-proton dump and write text for
`spirv-as`, like the scripts at the top of the repository. They are kept as they were used, as a
record; the shaders they produce are not shipped.
