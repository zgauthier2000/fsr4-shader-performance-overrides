# Results

[Back to the front page](../README.md)

## In short

- **At 4K on a Radeon RX 7800 XT** FSR 4.1.1 takes about 4.2 ms per frame with AMD's shaders, about 3.0 ms with the exact
  files and about 2.15 ms with the lossy ones. In a benchmark that is 97, 109 and 120 frames per second.
- **The gain shrinks with the output resolution.** At 1440p the exact files gain less, and at 1080p almost nothing; the
  lossy files still help there, because they skip work.
- **On RX 6000 cards** testers report about 30% at 4K and a few percent at 1440p and below. On integrated graphics, a
  couple of percent.
- **Most of what is on this page was measured with earlier versions** of the files; each table says which. Only the first
  table below is the current release.

## The current release

Shadow of the Tomb Raider's built-in benchmark, 4K output, FSR 4.1.1 Balanced, Radeon RX 7800 XT, Linux (single runs):

| | FSR 4 time per frame | Frames rendered | Average FPS |
|---|---|---|---|
| AMD's shaders | 4.16 ms | | 97 |
| Exact files | 2.99 ms (−28%) | 16947 | 109 (+12%) |
| Lossy files | 2.15 ms (−48%) | 18565 | 120 (+24%) |

The AMD figure and the exact figure are from earlier runs of the same benchmark; the exact files of this release differ from
those only in the last pass's store path (1 to 2% of that pass in a bench), and that 4K run was not repeated with them.

The same three, timed without a game by the [Windows timing kit](../timing-kit#windows-experimental) through the DLLs
(under Proton on the same card; whole upscaler, made-up frames, mean of 200 calls):

| Output (render size as in Balanced) | AMD's shaders | Exact DLL | Lossy DLL (frame that runs the model / skipped frame) |
|---|---|---|---|
| 1080p | 1.05 ms | 0.89 ms (−15%) | 0.66 ms (0.91 / 0.34), −37% |
| 1440p | 2.18 ms | 1.46 ms (−33%) | 1.10 ms (1.51 / 0.66), −50% |
| 4K | 4.93 ms | 3.16 ms (−36%) | 2.36 ms (3.28 / 1.44), −52% |

- **The kit reads higher gains at low resolutions than a game shows.** In Shadow of the Tomb Raider at 1080p output the
  exact files measured 0.79 ms against AMD's 0.80 ms: no gain worth the name, where the kit says 15%. A game's numbers are
  the ones to believe; the kit is for comparing builds and graphics chips.
- Nothing here has been measured on Windows. That is what the kit is for.

## Earlier measurements, by game

OptiScaler's upscaler time on a Radeon RX 7800 XT (Mesa 26.2, RADV), 4K output, **with the first version of the files
(2026-10-02)**:

| Game | Mode | Before | After | Saved |
|---|---|---|---|---|
| Control Resonant | Performance | 5.4 ms | 3.5 ms | 1.9 ms (35%) |
| Mortal Shell II | Balanced | 4.97 ms | 3.58 ms | 1.39 ms (28%) |
| Shadow of the Tomb Raider | Balanced | 4.16 ms | 3.47 ms | 0.69 ms (17%) |
| Shadow of the Tomb Raider, 1440p output | Balanced | 1.76 ms | 1.55 ms | 0.21 ms (12%) |
| Rise of the Tomb Raider | Balanced | 4.30 ms | 3.33 ms | 0.97 ms (23%) |
| Rise of the Tomb Raider, 1440p output | Balanced | 1.79 ms | 1.49 ms | 0.30 ms (17%) |
| Elden Ring (postpass only)* | Balanced | 5.33 ms | 4.57 ms | 0.76 ms (14%) |

The saving varies by game. Only this one GPU has been tested.

\* Measured with the game's 60 FPS cap in place, which makes OptiScaler's upscaler time unreliable
in some games; treat this row as approximate.

Later versions are faster again. The phased last pass (2026-10-03) brought Shadow of the Tomb Raider at 4K to
3.09 ms, 1.07 ms (26%) below AMD's (2.99 ms with the current files), and in Rise of the Tomb Raider's benchmark at 4K to 3.02 ms,
1.28 ms (30%) below AMD's (see [`results/phased-postpass`](../results/phased-postpass)). The other
games have not been re-measured yet.

Both Tomb Raider games were also run through their built-in benchmarks, where the frame time
saved matches the upscaler time saved:

- [Shadow of the Tomb Raider](../results/shadow-of-the-tomb-raider): 97 → 104 FPS at 4K (+7%,
  upscaler −16.6%), 171 → 176 FPS at 1440p (+3%, upscaler −11.9%).
- [Rise of the Tomb Raider](../results/rise-of-the-tomb-raider): 97.6 → 107.9 FPS at 4K (+11%,
  upscaler −22.6%), 186.6 → 199.6 FPS at 1440p (+7%, upscaler −16.8%). Re-run on 2026-10-06 with the
  files of that day: 97.7 → 109.6 FPS at 4K (+12%, upscaler 4.29 → 2.97 ms, −31%).

Each links to the full numbers and the results screenshots.

## By GPU type

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/gpu-gain-dark.svg">
  <img src="img/gpu-gain-light.svg" width="760" alt="Bar chart of the average reduction in FSR 4's time per frame. Desktop RX 7000: 29 percent at 4K output, 14 percent at 1440p. Desktop RX 6000: 30 percent at 4K, 5 percent at 1440p, 2 percent at 1080p. Integrated Radeon 780M: 2 percent at 1080p.">
</picture>

The chart averages the reports below. The RX 7800 XT rows are this repository's own measurements
on Linux; the others are single readings from testers' screenshots. All of them are for the exact
files, and all were taken with builds from before this release (the RX 6000 rows with the former `test-rdna2` build, which
is now the main download). Nobody has reported a lossy result on these cards yet.

| Card | Game | Output | FSR 4 time before | After | Saved |
|---|---|---|---|---|---|
| RX 7800 XT | Rise of the Tomb Raider | 4K | 4.30 ms | 3.02 ms | 30% |
| RX 7800 XT | Shadow of the Tomb Raider | 4K | 4.16 ms | 3.12 ms | 25% |
| RX 7800 XT | Control Resonant | 4K | 5.40 ms | 3.50 ms | 35% |
| RX 7800 XT | Mortal Shell II | 4K | 4.97 ms | 3.58 ms | 28% |
| RX 7800 XT | Rise of the Tomb Raider | 1440p | 1.79 ms | 1.49 ms | 17% |
| RX 7800 XT | Shadow of the Tomb Raider | 1440p | 1.76 ms | 1.55 ms | 12% |
| RX 6900 XT | Ready or Not | 4K | 3.79 ms | 2.57 ms | 32% |
| RX 6900 XT | Final Fantasy VII Rebirth | 4K | 3.79 ms | 2.70 ms | 29% |
| RX 6900 XT | Final Fantasy VII Rebirth | 1440p | 1.38 ms | 1.23 ms | 11% |
| RX 6750 XT | Mafia: The Old Country, native | 1440p | 2.31 ms | 2.22 ms | 4% |
| RX 6750 XT | Mafia: The Old Country | 1440p | 2.17 ms | 2.13 ms | 2% |
| RX 6800 | Control Resonant | 1440p | 1.96 ms | 1.92 ms | 2% |
| RX 6600 | Clair Obscur: Expedition 33 | 1080p | 2.24 ms | 2.18 ms | 3% |
| RX 6600 | Code Vein 2 | 1080p | 2.43 ms | 2.41 ms | 1% |
| Radeon 780M | Cyberpunk 2077 | 1080p | 5.15 ms | 5.04 ms | 2% |

Not in the chart: an RX 6900 XT at 3440x1440 in S.T.A.L.K.E.R. 2 (2.22 ms to 1.79 ms, 19%), which
sits between the 4K and 1440p figures as its pixel count does.

Keep in mind:

- The RX 7800 XT rows for Control Resonant and Mortal Shell II, and both of its 1440p rows, were
  measured with the first version of the rewrite; later ones save more at 4K.
- The 1440p and 1080p figures are small on every card, and on the RX 7800 XT a 1080p run with the current files showed
  none. The gain comes from removing writes that are only expensive when the picture is large.
- On RX 6000 cards "before" is fsr4xyz's `4.1.1b` in most reports. It is treated as equal in
  speed to AMD's shaders, which is an assumption (see [GPU support](gpu-support.md)).
- Some bars rest on one or two reports.
- No RX 9000 results: those cards run a different FSR 4 model that this project does not touch.
- The chart is made by [`img/make_gpu_gain_charts.py`](img/make_gpu_gain_charts.py).

## Benchmark pages

- [Shadow of the Tomb Raider](../results/shadow-of-the-tomb-raider): built-in benchmark, 4K and 1440p
- [Rise of the Tomb Raider](../results/rise-of-the-tomb-raider): built-in benchmark, 4K and 1440p,
  and 4K with the phased postpass
- [The phased postpass](../results/phased-postpass): what changed on 2026-10-03 and its measurements
