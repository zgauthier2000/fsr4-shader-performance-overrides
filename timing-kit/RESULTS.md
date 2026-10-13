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
  [RDNA2 hybrid test build](../docs/gpu-support.md#test-build-rdna2-hybrid-2026-10-05-withdrawn-2026-10-07) is for.
- **Pass 11: the shipped version is the best of the four on both smaller chips** (Steam Machine
  0.56 ms at 4K against AMD's 0.64, unrolled 0.61, compact rows 0.66; RX 6700M 0.41 against
  0.50, 0.44, 0.52). The compact version is slower than AMD's on both.
- **Room left in the postpass at 4K:** with the stores removed it costs 1.21 ms on the Steam
  Machine and 1.13 ms on the RX 6700M; the shipped rewrite is at 1.42 and 1.32 ms.
- **The arithmetic rewrites** (prepass, model passes) carry over at a few percent everywhere.
- **The lossy version is worth relatively more on the smaller chips:** about 5% of the whole on
  top of the exact files, most of it in pass 12 (-31% on the RX 6700M, -32% on the Steam Machine).

## What the runs of 2026-10-06 added

Three more machines and a second look at the RX 6700M, with kit versions 2026-10-05.9 and
2026-10-06.1, which time the postpass on its own.

**The postpass on RDNA2, by output size** (AMD's, the shipped rewrite, AMD's with its stores
removed; ms):

| GPU | 1080p | 1440p | 4K |
|---|---|---|---|
| RX 6800 XT (Navi 21) | .149, .172 (+15%), .147 | .305, .322 (+6%), .265 | 3.46, 1.44 (-58%), .609 |
| RX 6700M (Navi 22), new run | .428, .344 (-20%), .306 | 1.08, .785 (-28%), .596 | 2.49, 2.12 (-15%), 1.88 |
| RX 7800 XT (Navi 32), for reference | .204, .172 (-16%), .153 | .818, .307 (-62%), .269 | 2.14, .679 (-68%), .588 |

- **On the RX 6800 XT the scattered-store slowdown exists only at 4K.** At 1080p and 1440p AMD's
  postpass already runs at the speed of the no-stores probe, so the rewrite can only cost: 15%
  and 6% slower. At 4K AMD's takes 3.46 ms and the rewrite 1.44 ms. This is the pattern of the
  RX 6800 and 6900 XT reports from games: about 30% of FSR 4's time at 4K, next to nothing below.
- **The RX 6700M's new run disagrees with its earlier ones at 1080p** (rewrite 20% faster here,
  15% slower before) and all its 4K figures are slower than before (no-stores probe 1.88 ms
  against 1.13). The kit changed in between (warm-up runs are no longer counted) and so, it
  seems, did the machine's state. Its figures should be compared within one run only.
- **The two candidates ("direct", "direct trim") do not help.** They compile at 16 waves per SIMD
  on these chips against the shipped version's 12, as intended, and time the same as the shipped
  version on the RX 6800 XT at all three sizes. So the thread count is not what holds the rewrite
  back on RDNA2 either; the cost is the buffer round trip itself. They will be dropped.
- **At 4K on the RX 6800 XT the rewrite is still 0.8 ms above the no-stores probe** (1.44 against
  0.61 ms), a much larger gap than on the RX 7800 XT (0.09 ms). Three 4K images, 166 MB, are
  written every frame whatever the write pattern.

**The two forms of the dot product on RDNA2** (RX 6700M, the same shaders compiled with
`v_dot4c_i32_i8` and with `v_dot4_i32_i8`, ms):

| | 1080p | 4K |
|---|---|---|
| Model pass 1 | .187, .178 (-5%) | .702, .713 (+2%) |
| Model pass 12 | .174, .184 (+6%) | .764, .765 (0%) |
| Postpass, AMD's | .334, .349 (+4%) | 2.41, 2.46 (+2%) |
| Postpass, shipped | .430, .412 (-4%) | 2.09, 2.05 (-2%) |

No consistent difference: within 2% at 4K and plus or minus 6% at 1080p, in both directions. The
three-operand form is not faster on this card.

**A tester's own postpass versions.** The RX 6700M's run included candidates the tester had
added (names as given: `arbol2`, `arbol4`, `arbol6`, `sinlds`, `v57b`). Three of them beat the
shipped rewrite at 1440p (0.65 to 0.69 ms against 0.79 ms, with the no-stores probe at 0.60) and
all by 5 to 8% at 4K; one uses no workgroup memory at all and compiles at 16 waves per SIMD. The
kit reported output mismatches against AMD's for that run, which may mean they change the image
or only that they were built from a different version of the postpass. Not yet looked into.

**RX 6600 (Navi 23): not usable as it stands.** Every pass that writes an image, and every pass
on the largest tensors at 4K, read 10 to 30 times slower than on the RX 6700M (postpass at 1080p
11.6 ms for AMD's, 5.7 ms for the rewrite, 0.39 ms with the stores removed; model pass 1 at 4K
4.97 ms against 0.38 ms at 1440p), while the small passes are normal. The throughput of the slow
passes is about what a PCIe 3.0 x8 link carries, which would fit memory that is not on the card,
but that is a guess. In games the same card runs all of FSR 4 in a few milliseconds, so this is
about the benchmark on that machine, not the shaders. The relative results there: the rewrite
halves the postpass at all three sizes; the candidates equal the shipped version.

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

### RX 6700M, second (quick) run

The same machine, kit 2026-10-05.3, `quick`. It repeats the full run closely, including the
slower rewritten postpass at 1080p:

| | Full run | Quick run |
|---|---|---|
| 4K sum (AMD's / exact / lossy) | 7.53 / 6.45 / 6.16 ms | 7.48 / 6.46 / 6.18 ms |
| 1080p sum | 1.66 / 1.65 / 1.57 ms | 1.66 / 1.64 / 1.56 ms |
| Postpass, 4K (AMD's / exact) | 2.37 / 1.54 ms | 2.31 / 1.53 ms |
| Postpass, 1080p | .328 / .376 ms | .327 / .374 ms |
| Pass 11, 4K | .498 / .407 ms | .496 / .409 ms |

So on this card AMD's postpass reads steadily (unlike on the Steam Machine), and the 1080p result
is not noise: the rewritten postpass is 14 to 15% slower there in both runs. Two single readings
differ between the runs (pass 4 lossy .243 against .267, pass 5 AMD's .245 against .264).

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

## Radeon RX 7900 GRE (RADV NAVI31), 2026-10-11, postpass run

Kit 2026-10-06.2, its short postpass test only, on Linux (Mesa 26.2.4, GPU 1% busy before the
run). The "rewrite" here is the postpass shipped at the time of that kit, not the current one, and
the run has no whole-frame or lossy figures. One run.

**The postpass by output size** (ms):

| | 1080p | 1440p | 4K |
|---|---|---|---|
| AMD's | .204 | 1.33 | 2.75 |
| Rewrite | .147 (-28%) | .302 (-77%) | .645 (-77%) |
| AMD's with its stores removed | .122 | .214 | .479 |
| RX 7800 XT for reference (AMD's, rewrite) | .204, .172 | .818, .307 | 2.14, .679 |

- **AMD's postpass gets 6.5 times slower from 1080p to 1440p output, for 1.78 times the
  pixels.** The rewrite grows with the pixel count. So on this card the gain is large from 1440p
  up, not only at 4K, and AMD's postpass costs more here than on the RX 7800 XT at both sizes.
- **The same tester's game reading** (Ready Or Not, 1080p rendered to 4K, the exact DLL's
  shaders through OptiScaler; one screenshot each, the same scene not shown): 5.56 ms for the
  whole upscaler with AMD's shaders, 2.54 ms with the exact files. The postpass accounts for 2.1
  of those 3.0 ms.
- **Compiled postpass** (registers / waves per SIMD / workgroup memory): AMD's 60 / 24 / none,
  the rewrite 96 / 16 / 16 KB, at both 1080p and 4K.
- **AMD's postpass with only its neighborhood reads made branch-free** is 13% slower at 4K
  (3.11 ms) and no faster below; the same change on top of the rewrite makes no difference.
- **The two forms of the dot product** (`v_dot4c_i32_i8` against `v_dot4_i32_i8`): no difference
  on this card (within 5% either way in model passes 1 and 12 and the postpass, at 1080p and 4K).
- **Output check:** every version gave AMD's output.

## Radeon RX 7900 XTX (RADV NAVI31), 2026-10-11, full run

Linux kit 2026-10-11.1, full run (Mesa 26.2.4, GPU 2% busy before the run). One run. The lossy
figures are for the lossy build of that kit (release `dll-2026-10-11`), which skips the model on
every second frame; they are an estimate from the kit's skipped-frame probes, not a game
measurement.

**A whole frame** (prepass, the 12 model passes in sequence, postpass; ms):

| Output | AMD's shaders | Exact | Lossy, average of the two kinds of frame |
|---|---|---|---|
| 1080p | 0.589 | 0.553 (-6%) | about 0.354 (-40%) |
| 1440p | 0.953 | 0.900 (-6%) | about 0.628 (-34%) |
| 4K | 2.46 | 2.01 (-18%) | about 1.43 (-42%) |

**Per pass at 4K** (AMD's / exact, ms): prepass .338 / .291, pass 1 .186 / .178, pass 2 .185 /
.181, pass 4 .094 / .092, pass 5 .092 / .091, pass 7 .081 / .080, pass 8 .082 / .080, pass 9
.121 / .119, pass 10 .092 / .089, pass 11 .150 / .124, pass 12 .187 / .179, postpass .779 / .462.
Passes 3 and 6 are AMD's in both (.051 and .053).

**The postpass by output size** (AMD's, the shipped rewrite, AMD's with its stores removed; ms):

| 1080p | 1440p | 4K |
|---|---|---|
| .105, .105 (0%), .096 | .194, .184 (-5%), .161 | .807, .462 (-43%), .398 |

- **Nearly all of the gain at 4K is the postpass** (0.32 of the 0.45 ms), then the prepass (0.05)
  and pass 11 (0.03). At 1080p and 1440p AMD's postpass already runs close to its no-stores
  floor on this card, so there is little to take.
- **The postpass readings at 1080p and 1440p were unsteady** for both versions (AMD's .098 to
  .173 ms and the rewrite's .098 to .176 ms over 15 runs at 1080p); the medians are given above.
- **Pass 11** (ms at 1080p / 4K): AMD's .073 / .148, the shipped version .061 / .123, unrolled
  .067 / .137, compact rows .075 / .148.
- **Compiled postpass** (registers / waves per SIMD / workgroup memory): AMD's 60 / 24 / none,
  the rewrite 96 / 16 / 16 KB.
- **The two forms of the dot product:** no difference (within 5% in model passes 1 and 12 and
  the postpass, at 1080p and 4K).
- **Output check:** every exact version gave AMD's output; the lossy passes differ, as they
  should.

## Radeon RX 7900 XT (RADV NAVI31), 2026-10-08, full run

Linux kit 2026-10-06.3, full run (Mesa 26.2.4, GPU 2% busy before the run; the tester notes that
a screen-capture layer was enabled system-wide). One run. "Exact" and "lossy" are the versions of
that kit: the postpass shipped at the time, not the current one, and the earlier lossy build
without frame skip.

**Sum of the 14 passes** (ms):

| Output | AMD's shaders | Exact | Lossy |
|---|---|---|---|
| 1080p | 0.690 | 0.641 (-7%) | 0.612 (-11%) |
| 1440p | 1.62 | 1.14 (-30%) | 1.10 (-32%) |
| 4K | 3.73 | 2.48 (-34%) | 2.36 (-37%) |

**Per pass at 4K** (AMD's / exact, ms): prepass .410 / .383, pass 1 .215 / .208, pass 2 .217 /
.210, pass 4 .111 / .109, pass 5 .109 / .110, pass 7 .096 / .095, pass 8 .097 / .096, pass 9
.140 / .134, pass 10 .109 / .106, pass 11 .200 / .145, pass 12 .218 / .210, postpass 1.71 / .573.
Passes 3 and 6 are AMD's in both (.053 and .045).

**The postpass by output size** (AMD's, the rewrite, AMD's with its stores removed; ms):

| 1080p | 1440p | 4K |
|---|---|---|
| .134, .126 (-6%), .113 | .665, .264 (-60%), .195 | 1.76, .573 (-67%), .487 |

- **AMD's postpass is already slow at 1440p on this card:** five times its 1080p time for 1.78
  times the pixels, as on the RX 7900 GRE and unlike the RX 7900 XTX above, where it stays near
  its no-stores floor up to 1440p. So the exact files gain 30% here at 1440p, not only at 4K.
- **The postpass is nearly all of the gain:** 1.14 of the 1.25 ms at 4K, then pass 11 (0.06)
  and the prepass (0.03).
- **AMD's postpass readings at 1080p were unsteady** (.105 to .188 ms over 15 runs, median .129).
- **Pass 11** (ms at 1080p / 4K): AMD's .051 / .193, the shipped version .060 / .147, unrolled
  .068 / .173, compact rows .052 / .175. At 1080p AMD's own was the fastest in this run.
- **AMD's postpass with only its neighborhood reads made branch-free:** 22% faster at 1440p
  (.521 ms), 13% slower at 4K (2.00 ms).
- **Compiled postpass** (registers / waves per SIMD / workgroup memory): AMD's 60 / 24 / none,
  the rewrite 96 / 16 / 16 KB.
- **The two forms of the dot product:** no difference in model passes 1 and 12 (within 2%).
- **Output check:** every version gave AMD's output.

## Radeon RX 7700S, laptop (RADV NAVI33), 2026-10-09, full run

Linux kit 2026-10-06.3, full run (Mesa 26.2.4, on mains power, power profile "balanced"). **The
GPU was 56% busy before the run,** so the times may be higher than on an idle machine, and how much
that changes the comparison between versions is not known. One run. "Exact" and "lossy" as in the section above.

**Sum of the 14 passes** (ms):

| Output | AMD's shaders | Exact | Lossy |
|---|---|---|---|
| 1080p | 3.15 | 2.10 (-33%) | 1.99 (-37%) |
| 1440p | 5.51 | 3.62 (-34%) | 3.44 (-38%) |
| 4K | 12.4 | 8.26 (-33%) | 7.85 (-37%) |

**Per pass at 4K** (AMD's / exact, ms): prepass 1.29 / 1.21, pass 1 .778 / .747, pass 2 .778 /
.753, pass 4 .380 / .373, pass 5 .378 / .373, pass 7 .316 / .309, pass 8 .314 / .309, pass 9
.474 / .464, pass 10 .379 / .367, pass 11 .618 / .519, pass 12 .779 / .742, postpass 5.60 / 1.77.
Passes 3 and 6 are AMD's in both (.208 and .113).

**The postpass by output size** (AMD's, the rewrite, AMD's with its stores removed; ms):

| 1080p | 1440p | 4K |
|---|---|---|
| 1.36, .417 (-69%), .361 | 2.48, .762 (-69%), .614 | 5.60, 1.80 (-68%), 1.48 |

- **The same third off at every output size, 1080p included.** AMD's postpass costs about 3.8
  times its no-stores floor at all three sizes in this run, so there is no size below which the
  rewrite stops paying.
- **This is not what the Steam Machine above showed,** which has the same chip family: there
  AMD's postpass read .500 ms at 1080p and 2.17 ms at 4K, against 1.36 and 5.60 ms here, while
  the rewrite reads about the same on both (1.70 and 1.80 ms at 4K). Why AMD's postpass is so
  much slower on this laptop is not known; the busy GPU is one possible reason, and a second run
  on an idle machine would tell.
- **The postpass is nearly all of it:** 3.8 of the 4.1 ms saved at 4K.
- **The rewrite's postpass readings were unsteady** at every size (4K: 1.50 to 1.90 ms over 15
  runs, median 1.77), which fits a GPU that was busy with something else.
- **Pass 11** (ms at 1080p / 4K): AMD's .167 / .623, the shipped version .140 / .523, unrolled
  .153 / .579, compact rows .169 / .625.
- **AMD's postpass with only its neighborhood reads made branch-free** is 8 to 10% slower at
  every size.
- **Compiled postpass** (registers / waves per SIMD / workgroup memory): AMD's 64 / 16 / none,
  the rewrite of that kit 80 / 12 / 16 KB; the candidate that became the current postpass
  compiles to 64 / 16 / 16 KB and read .689 ms at 1440p against the rewrite's .762.
- **The two forms of the dot product:** no difference (within 2%).
- **Output check:** every version gave AMD's output.

## Ryzen 5 5600G integrated graphics (RADV RENOIR), 2026-10-09, full run

Linux kit 2026-10-06.3, full run on the integrated GPU (Mesa 26.3.0-devel, dual-channel DDR4,
GPU idle before the run). One run. This chip is older than the RDNA generations the project
targets (the tester gives it as GCN 5.1 with 7 compute units), and the times are far from
anything playable; the report shows that the shaders run there and what the rewrites do.
"Exact" and "lossy" as in the two sections above.

**Sum of the passes** (ms):

| Output | AMD's shaders | Exact | Lossy |
|---|---|---|---|
| 1080p | 44.8 | 43.0 (-4%) | 38.2 (-15%) |
| 1440p | 76.9 | 73.7 (-4%) | 65.5 (-15%) |
| 4K, without pass 2 | 153.5 | 146.2 (-5%) | 128.7 (-16%) |

The 4K run has no reading for pass 2, so its sum is of 13 passes; at the smaller sizes pass 2
costs about as much as pass 1.

**Per pass at 1080p** (AMD's / exact, ms): prepass 2.89 / 2.76, pass 1 4.95 / 4.86, pass 2 5.13 /
5.13, pass 4 3.70 / 3.71, pass 5 3.70 / 3.69, pass 7 1.42 / 1.41, pass 8 1.42 / 1.41, pass 9
2.03 / 2.01, pass 10 3.56 / 3.56, pass 11 2.36 / 2.33, pass 12 4.36 / 4.33, postpass 7.63 / 6.10.
Passes 3 and 6 are AMD's in both (.548 and 1.12).

**The postpass by output size** (AMD's, the rewrite, AMD's with its stores removed; ms):

| 1080p | 1440p | 4K |
|---|---|---|
| 7.60, 6.10 (-20%), 5.18 | 13.6, 10.9 (-19%), 9.06 | 30.4, 24.7 (-19%), 20.4 |

- **The model passes are where the time goes here, and the exact files do not change them:**
  the 12 passes are 34 of the 45 ms at 1080p. The whole gain is the postpass (1.5 ms) and a
  little from the prepass.
- **Why the model is so slow on this chip:** passes 1 and 12 compile to 256 registers with one
  wave per SIMD (5,100 to 5,400 instructions, against about 1,400 on RDNA chips), the postpass
  to 128 registers with two.
- **The readings were very steady:** a second round at 1080p differed by less than 1%.
- **Pass 11** at 1080p / 4K: all four versions within 2% (2.33 to 2.38 ms / 8.62 to 8.81 ms).
- **Output check:** every version gave AMD's output.

## Windows kit: Radeon RX 7900 XTX and Intel Arc B580, 2026-10-12

These two come from the [Windows kit](README.md), which measures something else than the sections
above: the whole FSR 4.1.1 upscaler as a game runs it, through AMD's DLL, with AMD's shaders and
with this project's DLLs. Kit version 2026-10-11.4, so the lossy DLL is that of release
`dll-2026-10-11.3`. Milliseconds per upscaled frame with the camera moving; one run per card.

| Card (driver) | Output | AMD's shaders | Exact | Lossy |
|---|---|---|---|---|
| Radeon RX 7900 XTX (32.0.32015) | 1080p | 0.670 | 0.674 (+1%) | 0.469 (-30%) |
| | 1440p | 1.383 | 1.088 (-21%) | 0.778 (-44%) |
| | 4K | 3.305 | 2.341 (-29%) | 1.675 (-49%) |
| Intel Arc B580 (32.0.101.9033) | 1080p | 1.775 | 1.637 (-8%) | 1.220 (-31%) |
| | 1440p | 3.092 | 2.907 (-6%) | 2.155 (-30%) |
| | 4K | 7.002 | 6.528 (-7%) | 4.865 (-31%) |

- **The exact DLL gives AMD's picture on both cards**, byte for byte, at all three sizes (the
  kit's fingerprint of the still scene). The lossy DLL differs, as it should.
- **RX 7900 XTX:** nothing to gain at 1080p, a fifth at 1440p, nearly a third at 4K.
- **Intel Arc B580: the first Intel result.** FSR 4.1.1 runs there with AMD's graphics-card check
  lifted, and the exact DLL is 6 to 8% faster at every size. Some of this card's still-scene
  readings were unsteady (one read 4% slower where the moving one read 6% faster), which is why
  the table uses the moving scene.
