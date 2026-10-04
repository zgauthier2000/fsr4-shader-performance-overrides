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

## Benchmark pages

- [Shadow of the Tomb Raider](../results/shadow-of-the-tomb-raider): built-in benchmark, 4K and 1440p
- [Rise of the Tomb Raider](../results/rise-of-the-tomb-raider): built-in benchmark, 4K and 1440p,
  and 4K with the phased postpass
- [The phased postpass](../results/phased-postpass): what changed on 2026-10-03 and its measurements
