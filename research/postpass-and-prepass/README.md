# Postpass, prepass and model-pass probes

What was measured while looking for more speed in FSR 4.1.1 (INT8) after the first postpass
rewrite, including the attempts that did not work. Everything here was run on a Radeon RX 7800 XT
with Mesa 26.2.3 (RADV), at 4K output unless noted.

**A note on the numbers.** Times marked "benchmark" come from a standalone program that runs one
shader in a long burst with pseudo-random inputs. It is good for comparing versions of a shader,
but it overstates what a pass costs in a game: the 12 model passes add up to 3.35 ms there and to
1.86 ms in Shadow of the Tomb Raider, about 1.8 times less.

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

## How much of each pass is memory traffic

`nomem.py` makes probe versions of a shader that keep all the arithmetic but drop memory traffic:
writes happen only if the value equals an impossible constant, and reads have the thread-dependent
part of their address masked into a small window, so they come from cache. The output is wrong;
only the time matters.

| Benchmark, ms | As is | No writes | Cached reads | Both |
|---|---|---|---|---|
| Postpass (first rewrite) | 0.83 | 0.76 | 0.76 | 0.72 |
| Prepass | 0.47 | 0.45 | 0.46 | 0.42 |
| 12 model passes, total | 3.35 | 3.28 | 3.42 | 3.47 |

Per model pass (pass 11 with its rewrite):

| Pass | As is | No writes | Cached reads | Both |
|---|---|---|---|---|
| 1 | 0.441 | 0.426 | 0.442 | 0.448 |
| 2 | 0.443 | 0.427 | 0.455 | 0.447 |
| 3 | 0.096 | 0.098 | 0.098 | 0.095 |
| 4 | 0.256 | 0.253 | 0.276 | 0.257 |
| 5 | 0.257 | 0.254 | 0.275 | 0.264 |
| 6 | 0.094 | 0.088 | 0.098 | 0.094 |
| 7 | 0.225 | 0.218 | 0.241 | 0.230 |
| 8 | 0.220 | 0.216 | 0.236 | 0.245 |
| 9 | 0.297 | 0.293 | 0.322 | 0.315 |
| 10 | 0.258 | 0.247 | 0.265 | 0.270 |
| 11 | 0.339 | 0.328 | 0.355 | 0.356 |
| 12 | 0.426 | 0.430 | 0.455 | 0.451 |

- **Model passes:** removing every write saves about 2%, and cached reads save nothing (the extra
  masking instruction costs slightly more than it gains). The passes are limited by arithmetic, so
  merging passes to keep data on chip could save under 0.1 ms.
- **Postpass and prepass:** about 14% and 10% memory traffic. What stood out instead was the
  first postpass rewrite's occupancy, which led to the phased version.
- **A trap:** masking each read's own index, instead of the shared base it is computed from, stops
  the compiler from merging neighbouring reads and makes the probe slower than the original.

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
| `pbench.c` | the prepass benchmark; the postpass and model-pass ones are in [`../wmma/bench`](../wmma/bench) |

The scripts take `spirv-dis` text of shaders from a vkd3d-proton dump and write text for
`spirv-as`, like the scripts at the top of the repository. They are kept as they were used, as a
record; the shaders they produce are not shipped.
