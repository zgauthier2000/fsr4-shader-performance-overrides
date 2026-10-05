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

## Where it differs: the passes that were rewritten for their stores

| Pass, 4K | RX 7800 XT: AMD's | exact | Steam Machine: AMD's | exact |
|---|---|---|---|---|
| Postpass | 2.16 ms | 0.67 ms (-69%) | 1.77 ms | 1.70 ms (-4%) |
| Model pass 11 | 0.58 ms | 0.20 ms (-65%) | 0.64 ms | 0.55 ms (-14%) |
| Prepass | 0.49 ms | 0.45 ms (-10%) | 1.28 ms | 1.19 ms (-7%) |
| Model pass 1 (for scale) | 0.30 ms | 0.28 ms | 0.85 ms | 0.81 ms |

- **The Steam Machine's GPU is about 2.8 times slower than the RX 7800 XT on ordinary passes**
  (pass 1, the prepass), as expected for its size.
- **But it runs AMD's postpass faster than the RX 7800 XT does** (1.77 ms against 2.16 ms), and
  AMD's pass 11 nearly as fast. The slow scattered stores that these two rewrites remove on the
  RX 7800 XT are not slow on this chip, so the rewrites have little to remove: 4% and 14% instead
  of 69% and 65%.
- **That is why the exact files gain 5% there instead of 31%.** What is left is the arithmetic
  rewrites (prepass, model passes), which carry over at about the same percentage.
- **The lossy version matters relatively more on this chip:** another 5.5% on top, most of it in
  pass 12 (0.84 ms down to 0.58 ms).

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
