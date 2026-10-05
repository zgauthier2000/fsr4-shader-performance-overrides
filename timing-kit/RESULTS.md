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
| Steam Machine (Navi 33, RDNA3) | 4K | 8.95 ms | 8.54 ms (-5%) | 8.07 ms (-10%) |
| | 1080p | 2.38 ms | 2.25 ms (-5%) | 2.13 ms (-11%) |
| Radeon RX 6700M (Navi 22, RDNA2) | 4K | 7.53 ms | 6.45 ms (-14%) | 6.16 ms (-18%) |
| | 1080p | 1.66 ms | 1.65 ms (-1%) | 1.57 ms (-5%) |

## Where it differs: the passes that were rewritten for their stores

AMD's shader, then the exact rewrite, in ms.

| Pass | RX 7800 XT | Steam Machine (Navi 33) | RX 6700M (RDNA2) |
|---|---|---|---|
| Postpass, 4K | 2.16, 0.67 (-69%) | 1.77, 1.70 (-4%) | 2.37, 1.54 (-35%) |
| Postpass, 1080p | 0.23, 0.17 (-23%) | 0.50, 0.47 (-7%) | 0.33, 0.38 (**+15%, slower**) |
| Model pass 11, 4K | 0.58, 0.20 (-65%) | 0.64, 0.55 (-14%) | 0.50, 0.41 (-18%) |
| Prepass, 4K | 0.49, 0.45 (-10%) | 1.28, 1.19 (-7%) | 1.20, 1.16 (-3%) |
| Model pass 1, 4K (for scale) | 0.30, 0.28 | 0.85, 0.81 | 0.60, 0.57 |

- **The scattered-store slowdown is a 4K effect on big-cache chips.** On the RX 7800 XT AMD's
  postpass takes 9.5 times as long at 4K as at 1080p for 4 times the pixels; on the RX 6700M
  7.2 times; on the Steam Machine 3.5 times, which is no slowdown at all. The rewrite removes
  that excess where it exists: 69%, 35% and 4%.
- **At 1080p the RX 6700M runs the rewritten postpass 15% slower than AMD's.** With no slowdown
  to remove, what is left is the rewrite's cost: it needs more registers (80 against 64 on this
  chip), so fewer threads run at once (12 waves per SIMD against 16). This matches the RX 6000
  reports from games: about 30% at 4K, a few percent at 1440p and 1080p. An RDNA2 build that
  keeps AMD's postpass at small output sizes is the obvious next test.
- **On the RX 6700M the shipped pass 11 is the right one:** 0.41 ms at 4K against 0.50 for AMD's,
  0.44 for the unrolled version without grouped stores and 0.52 for the compact one, which is
  slower than AMD's. So the compact build is not for desktop RDNA2, as its game reports said.
- **The Steam Machine's GPU is about 2.8 times slower than the RX 7800 XT on ordinary passes**
  and the RX 6700M about 2 times, as expected for their size. The arithmetic rewrites (prepass,
  model passes) carry over at about the same few percent everywhere.
- **The lossy version is worth relatively more on the smaller chips:** 5 to 6% of the whole on
  top of the exact files, most of it in pass 12 (-31% on the RX 6700M, -32% on the Steam
  Machine).

## Steam Machine (RADV NAVI33), 2026-10-05

Kit 2026-10-05.3, quick run. Mesa 26.2.0-devel, kernel 7.2.7-valve1 (SteamOS), 15 GB RAM,
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

Not yet known for this GPU: which version of the postpass and of pass 11 suits it best (the full
run, `bash run.sh`, times eight and four of them), and how the gain looks in a game.

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
