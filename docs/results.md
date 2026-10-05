# Results

[Back to the front page](../README.md)

OptiScaler's upscaler time on a Radeon RX 7800 XT (Mesa 26.2, RADV), 4K output:

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

The table was measured with the first version of the postpass rewrite. The current, phased
version is faster again; in Shadow of the Tomb Raider at 4K it brings the upscaler time to
3.09 ms, 1.07 ms (26%) below AMD's, and in Rise of the Tomb Raider's benchmark at 4K to 3.02 ms,
1.28 ms (30%) below AMD's (see [`results/phased-postpass`](../results/phased-postpass)). The other
games have not been re-measured yet.

Both Tomb Raider games were also run through their built-in benchmarks, where the frame time
saved matches the upscaler time saved:

- [Shadow of the Tomb Raider](../results/shadow-of-the-tomb-raider): 97 → 104 FPS at 4K (+7%,
  upscaler −16.6%), 171 → 176 FPS at 1440p (+3%, upscaler −11.9%).
- [Rise of the Tomb Raider](../results/rise-of-the-tomb-raider): 97.6 → 107.9 FPS at 4K (+11%,
  upscaler −22.6%), 186.6 → 199.6 FPS at 1440p (+7%, upscaler −16.8%).

Each links to the full numbers and the results screenshots.

## By GPU type

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/gpu-gain-dark.svg">
  <img src="img/gpu-gain-light.svg" width="760" alt="Bar chart of the average reduction in FSR 4's time per frame. Desktop RX 7000: 29 percent at 4K output, 14 percent at 1440p. Desktop RX 6000: 30 percent at 4K, 5 percent at 1440p, 2 percent at 1080p. Integrated Radeon 780M: 2 percent at 1080p.">
</picture>

The chart averages the reports below. The RX 7800 XT rows are this repository's own measurements
on Linux; the others are single readings from testers' screenshots.

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
  measured with the first version of the rewrite; the current one saves more.
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
