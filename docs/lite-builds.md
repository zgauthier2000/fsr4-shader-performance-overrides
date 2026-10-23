# The Lite builds: 4.1.2l-exact and 4.1.2l-lossy

Since release `dll-NEXTVER` every archive also holds two builds based on **FSR 4.1.2 Lite**, the smaller FSR 4 network that AMD's
driver uses for graphics built into the processor:

| Folder | Version name in OptiScaler | Picture | Speed against AMD's Lite (Linux, RX 7800 XT) |
|---|---|---|---|
| `4.1.2l-exact` | `4.1.2l-exact-<flavor>-cyboman` | **AMD's Lite picture, byte for byte** (exact to AMD's Lite, not to full FSR 4) | 1 to 3% faster |
| `4.1.2l-lossy` | `4.1.2l-lossy-<flavor>-cyboman` | close to Lite's, not the same: read its `WARNING.txt` | about 15 to 18% faster |

`<flavor>` is `r3`, `r2`, `igpu-r3` or `igpu-r2`, after the archive. The Lite builds are the same file in all four archives; only
the name differs.

> [!WARNING]
> **4.1.2l-lossy changes the picture.** It is neither AMD's FSR 4.1.1 nor AMD's FSR 4.1.2 Lite. Never use any of these builds in
> online games or games with anti-cheat. Not for Radeon RX 9000 cards.

## Which one?

- **Lite or full FSR 4?** Lite is a smaller network: a little less accurate on a still picture than full FSR 4.1.1 (43.9 against
  44.3 dB on the test scenes), better on some motion (swaying foliage, thin detail), worse on others (old image beside moving objects,
  fades). How it compares with full FSR 4.1.1, lossy (called lossy2 there) and other upscalers: [upscaler comparison](upscaler-comparison.md).
- **4.1.2l-exact** gives Lite's picture unchanged and saves a little time.
- **4.1.2l-lossy** is the faster of the two. It runs the network on every other frame, like `lossy`, with weights retrained
  for that frame loop.

## Speed

FSR 4's time per frame, milliseconds, moving scene, Balanced, **under Linux (Proton) on one Radeon RX 7800 XT**, two runs each.
Windows and other cards are not measured yet; timing-kit reports will follow.

| Output | FSR 4.1.2 Lite (AMD) | 4.1.2l-exact | 4.1.2l-lossy |
|---|---|---|---|
| 1080p | 0.656 | 0.645 (−1.7%) | 0.560 (−14.7%) |
| 1440p | 1.036 | 1.005 (−2.9%) | 0.846 (−18.3%) |
| 4K | 2.016 | 1.988 (−1.4%) | 1.655 (−17.9%) |

- **4.1.2l-exact** saves about the same small amount of time at every size (about 0.01 to 0.03 ms), so its share is largest at the
  smaller sizes. That is the opposite of the 4.1.1 exact DLL, whose saving grows with the output size. Gains this small are close to the
  spread between runs.
- **4.1.2l-lossy** alternates two kinds of frame: at 4K about 2.09 ms on a frame that runs the network and 1.20 ms on one that skips it.
  What an uneven cost means for frame caps and V-Sync: [frame pacing](frame-pacing.md).

## Picture

**4.1.2l-exact:** its output equals the Lite network's byte for byte (test rig: 1080p and 4K, game auto exposure off and on, a still
scene and a particle scene; the last 4 of 40 frames each).

**4.1.2l-lossy:** the test rig's full check. 4K Balanced, synthetic test scenes, Linux (Proton), one run each. Each cell gives the
game's auto exposure off / on. `*` marks scene types not used in training. FSR 4.1.1 and Lite were measured in this project's local test
harness, not in AMD's own runtime.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/rel-lite-wires-dark.svg">
  <img src="img/rel-lite-wires-light.svg" width="760" alt="Shimmer of thin wires while the camera pans, mean change per frame, lower is steadier, auto exposure off then on: FSR 4.1.2 Lite 9.75 and 7.81; 4.1.2l-lossy 5.88 and 3.83; FSR 4.1.1 7.16 and 6.79; lossy (former lossy2) 4.56 and 4.36.">
</picture>

| Test (4K Balanced; lower is better unless noted) | FSR 4.1.1 (AMD) | FSR 4.1.2 Lite (AMD) | **4.1.2l-lossy** | lossy (former lossy2) |
|---|---|---|---|---|
| Flat areas at rest: change per frame * | 0.126 / 0.213 | 0.11 / 0.207 | **0.079 / 0.128** | 0.074 / 0.109 |
| Fine detail at rest: change per frame * | 0.11 / 0.125 | 0.094 / 0.117 | **0.092 / 0.107** | 0.089 / 0.1 |
| Thin detail, vertical motion: change per frame * | 0.364 / 0.422 | 0.31 / 0.379 | **0.337 / 0.364** | 0.328 / 0.359 |
| Background in motion: change per frame | 0.079 / 0.072 | 0.08 / 0.071 | **0.08 / 0.071** | 0.027 / 0.034 |
| Light film grain: change per frame | 0.785 / 0.552 | 0.416 / 0.592 | **0.288 / 0.424** | 0.423 / 0.444 |
| Heavy film grain: change per frame | 2.549 / 0.484 | 2.313 / 0.413 | **1.396 / 0.817** | 2.13 / 1.406 |
| Thin wires, still camera: change per frame | 2.91 / 2.82 | 2.64 / 2.54 | **2.6 / 2.43** | 2.77 / 2.54 |
| Thin wires, camera pan: change per frame * | 7.16 / 6.79 | 9.75 / 7.81 | **5.88 / 3.83** | 4.56 / 4.36 |
| Rain: specks brighter than 20 levels * | 0 / 2 | 0 / 254 | **0 / 0** | 0 / 0 |
| Bright rain: specks brighter than 20 levels | 1,314 / 3,764 | 78 / 1,592 | **256 / 297** | 464 / 438 |
| Fireflies (single over-bright pixels) * | 370 / 137 | 259 / 321 | **275 / 62** | 356 / 128 |
| Dim, dense fireflies | 34 / 10 | 37 / 31 | **37 / 9** | 34 / 9 |
| Foliage at rest: flicker * | 0.32 / 0.38 | 0.32 / 0.37 | **0.31 / 0.33** | 0.32 / 0.34 |
| Still picture accuracy, dB (higher is better) * | 44.33 / 44.44 | 43.92 / 44.03 | **43.97 / 44.06** | 43.91 / 43.9 |
| Just-uncovered areas, dB (higher is better) | 34.48 / 34.71 | 34.44 / 34.69 | **34.44 / 34.69** | 37.04 / 37.22 |
| Old image beside a moving object, scene A * | 4.01 / 3.77 | 6.01 / 5.44 | **6.14 / 5.71** | 4.13 / 3.98 |
| Old image beside a moving object, scene B * | 3.11 / 2.9 | 4.35 / 4.35 | **2.57 / 2.63** | 3.64 / 4.6 |
| Large particles: error | 0.66 / 0.66 | 0.71 / 0.71 | **0.92 / 0.92** | 1.2 / 1.17 |
| Small, slow bright details: error | 2.52 / 2.52 | 2.68 / 2.66 | **3.17 / 3.09** | 2.69 / 2.71 |
| Swaying foliage: error | 12.09 / 12.08 | 10.37 / 10.39 | **11.67 / 11.72** | 12.24 / 12.28 |
| Fade: frames behind * | 0.91 / 0.9 | 1.69 / 1.53 | **1.24 / 1.07** | 0.88 / 0.92 |
| Brightening: frames behind * | 0.46 / 0.46 | 1.03 / 0.86 | **1.03 / 1.13** | 1.54 / 1.33 |
| Brightness step: share missed on the first frame * | 0.04 / 0.04 | 0 / 0.01 | **0 / 0.01** | 0.09 / 0.09 |

**Better than AMD's Lite:**

- Thin wires while the camera pans shimmer 40 to 50% less (5.9 / 3.8 against 9.8 / 7.8; FSR 4.1.1: 7.2 / 6.8). With the camera still
  the two are level.
- Steadier in film grain (except heavy grain with auto exposure on, below) and in flat areas at rest.
- With auto exposure on: no rain specks where Lite has 254, and far fewer fireflies.
- Old image beside a moving object (scene B): 2.6 against 4.4. Fades catch up sooner (1.2 / 1.1 frames against 1.7 / 1.5).

**Worse than AMD's Lite:**

- **Small, slowly moving bright details** (sparks, distant lights): error 3.2 / 3.1 against Lite's 2.7 / 2.7 and FSR 4.1.1's 2.5. This is
  the one test where it does not meet this project's own quality goal for the build.
- Large particles: error 0.92 against 0.71. Swaying foliage: 11.7 against 10.4 (still better than FSR 4.1.1's 12.1).
- Bright rain with auto exposure off: 256 bright specks against 78 (with it on: 297 against 1,592).
- With auto exposure on: brightening catches up more slowly (1.13 frames against 0.86), and heavy film grain changes more from frame to
  frame (0.82 against 0.41).

## Ultra Performance and above 4K

**Ultra Performance only: not representative of the other modes.** 4.1.2l-lossy skips frames in Ultra Performance too. It uses AMD's own
Lite weights for that mode there (the retrained weights are for the other modes). Test rig, 4K output, auto exposure off / on; speed under Linux
(Proton) on one Radeon RX 7800 XT, two runs:

| | FSR 4.1.2 Lite (AMD) | 4.1.2l-lossy |
|---|---|---|
| FSR 4 time per frame: 1080p / 1440p / 4K | 0.666 / 1.017 / 1.944 ms | 0.585 / 0.873 / 1.678 ms (−12 / −14 / −14%) |
| Thin wires, camera pan: change per frame | 12.6 / 12.8 | 9.4 / 8.7 |
| Bright rain specks | 4,740 / 5,449 | 4,055 / 3,614 |
| Rain specks brighter than 20 levels | 686 / 1,364 | 1,437 / 1,700 |
| Dim, dense fireflies | 1,195 / 1,449 | 1,584 / 1,212 |
| Heavy film grain: change per frame | 0.33 / 0.42 | 0.45 / 1.38 |
| Swaying foliage: error | 17.9 / 17.9 | 19.9 / 20.1 |
| Large particles: error | 1.65 / 1.59 | 2.14 / 2.12 |
| Still picture accuracy, dB (higher is better) | 41.4 / 41.4 | 41.2 / 41.1 |

Above 4K output 4.1.2l-lossy runs the network on every frame with Lite's weights: close to Lite's picture (speed not measured there).
4.1.2l-exact gives Lite's picture byte for byte in every mode and at every size, including Ultra Performance and 5K, and with the flags games set
(inverted depth, display-size motion vectors, jitter cancellation).

## Not checked yet

- Windows: the DLLs only ran under Proton on Linux. Speed on other cards.
- Games: the figures come from synthetic test scenes, not from games.
- Training is not fully repeatable: the same training with other random seeds gave copies that differ somewhat; the best of three is
  shipped.

## How the DLLs were checked

- **4.1.2l-lossy:** the DLL's frames equal those of the Linux build that the full check above measured, byte for byte (1080p and 4K,
  auto exposure off and on, a still scene and a particle scene; the last 4 of 40 frames each).
- **4.1.2l-exact:** the DLL's frames equal those of the Lite network without its changes, byte for byte (the same six inputs).
- Every DLL ran without non-finite values. The four copies of each build differ only in the version name.
