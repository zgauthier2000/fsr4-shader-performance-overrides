# Timing kit results

[Back to the timing kit](README.md)

Summaries sent in from the [timing kit](README.md), one section per GPU. Times are milliseconds
per run of one pass on made-up inputs, at 4K output unless stated; they are not game times. "Exact"
is this repository's shipped rewrite (same image as AMD's), "lossy" the
[opt-in test version](../research/lossy) (changed image).

## Whole pipeline (sum of the 14 passes)

| GPU | Output | AMD's shaders | Exact | Lossy |
|---|---|---|---|---|
| Radeon RX 7800 XT (Navi 32, desktop RDNA3) | 4K | 4.77 ms | 3.28 ms (-31%) | 3.13 ms (-34%) |
| | 1080p | 1.01 ms | 0.92 ms (-9%) | 0.88 ms (-12%) |
| Steam Machine (Navi 33, RDNA3), full run | 4K | 9.78 ms | 8.49 ms (-13%) | 8.02 ms (-18%) |
| | 1080p | 2.32 ms | 2.23 ms (-4%) | 2.12 ms (-9%) |
| the same machine, earlier quick run | 4K | 8.95 ms | 8.54 ms (-5%) | 8.07 ms (-10%) |
| Radeon RX 6700M (Navi 22, RDNA2) | 4K | 7.53 ms | 6.45 ms (-14%) | 6.16 ms (-18%) |
| | 1080p | 1.66 ms | 1.65 ms (-1%) | 1.57 ms (-5%) |

## Where it differs: the passes that were rewritten for their stores

> **Correction (2026-10-05).** An earlier version of this page concluded from the Steam Machine's
> first run that AMD's postpass is not slow on that chip (1.77 ms at 4K, so the rewrite gained
> only 4%). A second, full run on the same machine read 2.63 ms for AMD's postpass and 1.67 ms
> for the rewrite (-37%), and 2.57 against 1.42 ms for the other postpass version it times
> (-45%). **AMD's postpass does not give a steady reading at 4K:** the same was seen on the
> RX 7800 XT when something else was using the GPU (0.9 to 2.2 ms across runs, against a steady
> 2.17 ms on an idle machine). The rewritten postpass read the same in both Steam Machine runs
> (1.70 and 1.67 ms). So that conclusion is withdrawn: the Steam Machine has the slow stores too.
> The kit's summary flags unsteady postpass readings since version 2026-10-05.5.

AMD's shader, then the exact rewrite, in ms. Steam Machine figures are from its full run.

| Pass | RX 7800 XT | Steam Machine (Navi 33) | RX 6700M (RDNA2) |
|---|---|---|---|
| Postpass, 4K | 2.16, 0.67 (-69%) | 2.63, 1.67 (-37%) | 2.37, 1.54 (-35%) |
| Postpass, 1080p | 0.23, 0.17 (-23%) | 0.44, 0.46 (+4%, slower) | 0.33, 0.38 (**+15%, slower**) |
| Model pass 11, 4K | 0.58, 0.20 (-65%) | 0.64, 0.56 (-14%) | 0.50, 0.41 (-18%) |
| Prepass, 4K | 0.49, 0.45 (-10%) | 1.26, 1.18 (-6%) | 1.20, 1.16 (-3%) |
| Model pass 1, 4K (for scale) | 0.30, 0.28 | 0.84, 0.81 | 0.60, 0.57 |

- **The Steam Machine's GPU behaves like the RDNA2 card, not like the RX 7800 XT.** The driver
  compiles the shaders for it exactly as for the RX 6700M: 56 registers and 18 waves per SIMD for
  the model passes, and for the rewritten postpass 80 registers and 12 waves against AMD's 64 and
  16. The RX 7800 XT has more registers to give (the rewritten postpass runs 16 waves there).
- **So on both smaller chips the rewritten postpass gains about a third at 4K and nothing at
  1080p:** 4% slower on the Steam Machine, 15% slower on the RX 6700M. The scattered stores it
  removes cost most at large sizes; at 1080p its extra registers are what is left. This matches
  the RX 6000 reports from games (about 30% at 4K, a few percent below), and it is what the
  [RDNA2 hybrid test build](../docs/gpu-support.md#test-build-rdna2-hybrid-2026-10-05) is for.
- **Pass 11: the shipped version is the best of the four on both smaller chips** (Steam Machine
  0.56 ms at 4K against AMD's 0.64, unrolled 0.61, compact rows 0.66; RX 6700M 0.41 against
  0.50, 0.44, 0.52). The compact version is slower than AMD's on both.
- **Room left in the postpass at 4K:** with the stores removed it costs 1.21 ms on the Steam
  Machine and 1.13 ms on the RX 6700M; the shipped rewrite is at 1.42 and 1.32 ms.
- **The arithmetic rewrites** (prepass, model passes) carry over at a few percent everywhere.
- **The lossy version is worth relatively more on the smaller chips:** about 5% of the whole on
  top of the exact files, most of it in pass 12 (-31% on the RX 6700M, -32% on the Steam Machine).

## Steam Machine (RADV NAVI33), 2026-10-05, first (quick) run

Kit 2026-10-05.3, quick run. Its 4K postpass reading for AMD's shader (1.77 ms) was low; see the correction above and the full run below. Mesa 26.2.0-devel, kernel 7.2.7-valve1 (SteamOS), 15 GB RAM,
governor powersave, platform profile balanced. All versions matched AMD's output.

Each cell: AMD's / exact / lossy, in ms.

| Pass | 1080p | 4K |
|---|---|---|
| Prepass | .348 / .316 | 1.28 / 1.19 |
| 1 | .213 / .204 / .189 | .845 / .805 / .736 |
| 2 | .214 / .209 / .195 | .851 / .819 / .793 |
| 3 | .036 | .209 |
| 4 | .109 / .106 / .104 | .404 / .396 / .386 |
| 5 | .108 / .107 / .091 | .407 / .399 / .334 |
| 6 | .035 | .120 |
| 7 | .093 / .092 / .091 | .337 / .329 / .328 |
| 8 | .092 / .091 / .091 | .334 / .328 / .326 |
| 9 | .136 / .133 / .135 | .504 / .492 / .493 |
| 10 | .109 / .105 / .089 | .406 / .394 / .333 |
| 11 | .176 / .149 | .644 / .554 |
| 12 | .214 / .204 / .146 | .842 / .812 / .575 |
| Postpass | .500 / .466 | 1.77 / 1.70 |
| **Sum** | **2.38 / 2.25 / 2.13** | **8.95 / 8.54 / 8.07** |

The full run from the same machine follows the RX 6700M's below.

## Radeon RX 6700M (RADV NAVI22), 2026-10-05

Kit 2026-10-05.3, full run. A laptop: Ryzen 7 5800H, 14 GB RAM, on AC power, governor
performance, Mesa 26.3.0-devel, kernel 7.2.9 (CachyOS). All versions matched AMD's output. The
second round at 1080p repeated within 3% (typically 0%).

Each cell: AMD's / exact / lossy, in ms.

| Pass | 1080p | 4K |
|---|---|---|
| Prepass | .296 / .289 | 1.20 / 1.16 |
| 1 | .150 / .143 / .133 | .598 / .572 / .531 |
| 2 | .149 / .144 / .140 | .595 / .575 / .559 |
| 3 | .025 | .085 |
| 4 | .065 / .063 / .062 | .247 / .240 / .243 |
| 5 | .065 / .062 / .054 | .245 / .241 / .202 |
| 6 | .026 | .079 |
| 7 | .059 / .058 / .058 | .209 / .197 / .197 |
| 8 | .059 / .058 / .058 | .207 / .200 / .200 |
| 9 | .097 / .094 / .094 | .353 / .344 / .344 |
| 10 | .065 / .062 / .053 | .245 / .246 / .200 |
| 11 | .132 / .105 | .498 / .407 |
| 12 | .148 / .141 / .098 | .595 / .564 / .411 |
| Postpass | .328 / .376 | 2.37 / 1.54 |
| **Sum** | **1.66 / 1.65 / 1.57** | **7.53 / 6.45 / 6.16** |

| Versions at 4K | ms |
|---|---|
| Pass 11: AMD's, unrolled, compact rows, shipped | .497, .442, .520, .409 |
| Pass 11 at 1080p: the same four | .115, .102, .116, .094 |
| Postpass (Elden Ring's version): AMD's | 2.13 |
| all stores at once (the first rewrite) | 1.59 |
| phased, 8 / 16 / 32 threads; square blocks, 16 / 32; shipped | 1.33 / 1.31 / 1.32; 1.33 / 1.32; 1.32 |

| With the stores removed, 4K | With | Without |
|---|---|---|
| Postpass | 2.12 | 1.13 |
| Prepass | 1.12 | 1.05 |
| Pass 11 | .500 | .403 |
| Pass 1 | .612 | .590 |
| Pass 12 | .596 | .573 |

So on this chip the shipped postpass (1.32) is within 0.2 ms of what the shader costs with no
stores at all (1.13), and the shipped pass 11 (0.41) is at that floor (0.40).

Compiled code at 1080p (registers / waves per SIMD / instructions): AMD's prepass 56/18/765,
pass 1 56/18/1350, pass 11 56/18/899, pass 12 56/18/1351, postpass 64/16/2977; exact prepass
48/20/739, pass 1 56/18/1282, pass 11 56/18/4014, pass 12 56/18/1283, postpass 80/12/3269.

## Steam Machine (RADV NAVI33), 2026-10-05, full run with memory traffic

Kit 2026-10-05.3, `bash run.sh traffic`. Same machine and software as the quick run above. All
versions matched AMD's output. The second round at 1080p repeated within 1% typically, with one
reading 37% off.

Each cell: AMD's / exact / lossy, in ms.

| Pass | 1080p | 4K |
|---|---|---|
| Prepass | .348 / .315 | 1.26 / 1.18 |
| 1 | .211 / .201 / .187 | .842 / .805 / .742 |
| 2 | .213 / .205 / .197 | .852 / .818 / .790 |
| 3 | .036 | .208 |
| 4 | .108 / .103 / .103 | .404 / .395 / .383 |
| 5 | .109 / .106 / .089 | .404 / .394 / .325 |
| 6 | .035 | .121 |
| 7 | .092 / .091 / .090 | .333 / .330 / .326 |
| 8 | .092 / .090 / .090 | .332 / .327 / .325 |
| 9 | .137 / .135 / .135 | .504 / .492 / .490 |
| 10 | .109 / .105 / .089 | .403 / .390 / .332 |
| 11 | .175 / .149 | .642 / .555 |
| 12 | .214 / .204 / .146 | .848 / .810 / .577 |
| Postpass | .441 / .458 | 2.63 / 1.67 |
| **Sum** | **2.32 / 2.23 / 2.12** | **9.78 / 8.49 / 8.02** |

| Versions at 4K | ms |
|---|---|
| Pass 11: AMD's, unrolled, compact rows, shipped | .643, .608, .657, .555 |
| Pass 11 at 1080p: the same four | .174, .162, .178, .148 |
| Postpass (Elden Ring's version): AMD's | 2.57 |
| all stores at once (the first rewrite) | 1.97 |
| phased, 8 / 16 / 32 threads; square blocks, 16 / 32; shipped | 1.47 / 1.43 / 1.42; 1.42 / 1.42; 1.42 |

| With the stores removed, 4K | With | Without |
|---|---|---|
| Postpass | 2.57 | 1.21 |
| Prepass | 1.22 | 1.12 |
| Pass 11 | .649 | .606 |
| Pass 1 | .845 | .835 |
| Pass 12 | .849 | .836 |

Memory traffic at 1080p (MB read per run, million write requests; about 350 MB of each figure is
the measurement's floor on this machine):

| Pass | AMD's | Exact |
|---|---|---|
| Postpass | 388 MB, 2.54 M | 170 MB, 0.99 M |
| Pass 11 | 370 MB, 0.18 M | 363 MB, 0.08 M |
| Prepass | 408 MB, 0.30 M | 406 MB, 0.30 M |
| Passes 1, 4, 7, 12 | 364, 355, 352, 364 MB | 366, 365, 350, 364 MB |

Compiled code at 1080p (registers / waves per SIMD / instructions): AMD's prepass 56/18/855,
pass 1 56/18/1446, pass 11 56/18/1065, pass 12 56/18/1446, postpass 64/16/3180; exact prepass
48/20/829, pass 1 56/18/1359, pass 11 56/18/4389, pass 12 56/18/1359, postpass 80/12/3506.
