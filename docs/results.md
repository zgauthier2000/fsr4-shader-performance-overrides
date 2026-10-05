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

Every before/after report collected so far, from this repository's own measurements (RX 7800 XT,
Linux) and from testers (RX 6000 cards and the Radeon 780M, single readings from their
screenshots; details in [GPU support](gpu-support.md)).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/gpu-gain-dark.svg">
  <img src="img/gpu-gain-light.svg" width="760" alt="Chart of upscaling time saved by GPU type and output size, one mark per report. Desktop RX 7000: 25 to 35 percent at 4K output (4 reports), 12 to 17 percent at 2560x1440 (2 reports). Desktop RX 6000: 29 to 32 percent at 4K (2 reports), 19 percent at 3440x1440 (1 report), 2 to 11 percent at 2560x1440 (4 reports), 1 to 3 percent at 1080p (2 reports). Integrated Radeon 780M: 2 percent at 1080p (1 report).">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/gpu-times-dark.svg">
  <img src="img/gpu-times-light.svg" width="760" alt="Chart of FSR 4 time per frame before and after for sixteen reports, grouped by GPU type. RX 7800 XT at 4K: 4.30 to 3.02, 4.16 to 3.12, 5.40 to 3.50 and 4.97 to 3.58 ms; at 2560x1440: 1.79 to 1.49 and 1.76 to 1.55 ms. RX 6900 XT at 4K: 3.79 to 2.57 and 3.79 to 2.70 ms; at 3440x1440: 2.22 to 1.79 ms; at 2560x1440: 1.38 to 1.23 ms. RX 6750 XT at 2560x1440: 2.31 to 2.22 and 2.17 to 2.13 ms. RX 6800 at 2560x1440: 1.96 to 1.92 ms. RX 6600 at 1080p: 2.24 to 2.18 and 2.43 to 2.41 ms. Radeon 780M at 1080p: 5.15 to 5.04 ms.">
</picture>

What the charts show:

- **4K output:** about 25 to 35% less upscaling time on both desktop generations, roughly 1 ms per
  frame.
- **Below 4K the gain falls off, faster on RX 6000 than on RX 7000.** At 2560x1440 an RX 7800 XT
  still saves 12 to 17%; RX 6000 cards save 2 to 11%, and 1 to 3% at 1080p.
- **Integrated graphics:** one report, 2%, with the integrated-GPU build.

What to keep in mind:

- The RX 7800 XT rows for Control Resonant and Mortal Shell II, and both of its 1440p rows, were
  measured with the first version of the rewrite; the current one saves more.
- On RX 6000 cards "before" is fsr4xyz's `4.1.1b` in most reports. It is treated as equal in
  speed to AMD's shaders, which is an assumption (see [GPU support](gpu-support.md)).
- Left out: one RX 6700 XT report without a stated resolution, a Sifu report without a stated
  GPU, and Elden Ring on the RX 7800 XT, which was measured with a frame-rate cap.
- No RX 9000 results: those cards run a different FSR 4 model that this project does not touch.
- The charts are made by [`img/make_gpu_gain_charts.py`](img/make_gpu_gain_charts.py).

## Benchmark pages

- [Shadow of the Tomb Raider](../results/shadow-of-the-tomb-raider): built-in benchmark, 4K and 1440p
- [Rise of the Tomb Raider](../results/rise-of-the-tomb-raider): built-in benchmark, 4K and 1440p,
  and 4K with the phased postpass
- [The phased postpass](../results/phased-postpass): what changed on 2026-10-03 and its measurements
