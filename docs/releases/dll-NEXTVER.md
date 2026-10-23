# Release `dll-NEXTVER` against `dll-2026-10-22`

## What's new

- **Two builds based on AMD's FSR 4.1.2 Lite** in every archive, beside the 4.1.1 builds:
  - **`4.1.2l-lossy`: faster than Lite, and thin wires shimmer about half as much when the camera moves** (40 to 50% less in the test
    scene). About 15 to 18% faster than AMD's Lite network (Linux, RX 7800 XT). It changes the picture: read its `WARNING.txt`.
  - **`4.1.2l-exact`**: AMD's Lite picture byte for byte, 1 to 3% faster than AMD's Lite.
- **What got worse:** 4.1.2l-lossy draws small, slowly moving bright details (sparks, distant lights) less accurately than Lite (error
  3.2 against 2.7), large particles a little less accurately (0.92 against 0.71) and swaying foliage a little less (11.7 against 10.4);
  with auto exposure off it shows more bright rain specks than Lite (256 against 78). Details: [the Lite builds](../lite-builds.md).
- **The 4.1.1 builds are unchanged:** `exact`, `lossy` and `lossy2` are the files of `dll-2026-10-22`, byte for byte.
- **New in every archive:** `WHICH-SHOULD-I-CHOOSE.txt`, a short guide to the five folders.
- **Linux:** the launch-option files are unchanged; the Lite builds are DLLs only (they run under Proton).

## Downloads

| Archive | For | Download |
|---|---|---|
| RX 7000 | Radeon RX 7000 cards, including laptops with their own RX 7000 chip | [fsr4.1.1-cyboman-rx7000-NEXTVER.7z](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-NEXTVER/fsr4.1.1-cyboman-rx7000-NEXTVER.7z) (8.5 MB) or [.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-NEXTVER/fsr4.1.1-cyboman-rx7000-NEXTVER.zip) (122 MB) |
| RX 6000 | Radeon RX 6000 cards, including laptops with their own RX 6000 chip | [fsr4.1.1-cyboman-rx6000-NEXTVER.7z](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-NEXTVER/fsr4.1.1-cyboman-rx6000-NEXTVER.7z) (8.5 MB) or [.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-NEXTVER/fsr4.1.1-cyboman-rx6000-NEXTVER.zip) (120 MB) |
| Integrated RDNA 3 | Radeon 780M, 760M, 880M, 890M and other RDNA 3 / 3.5 graphics built into the processor; GeForce, Intel Arc and any other card | [fsr4.1.1-igpu-cyboman-rdna3-NEXTVER.7z](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-NEXTVER/fsr4.1.1-igpu-cyboman-rdna3-NEXTVER.7z) (8.5 MB) or [.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-NEXTVER/fsr4.1.1-igpu-cyboman-rdna3-NEXTVER.zip) (122 MB) |
| Integrated RDNA2 | Steam Deck, Radeon 680M, 660M, 610M and the graphics of Ryzen 7000 and 9000 desktop processors | [fsr4.1.1-igpu-cyboman-rdna2-NEXTVER.7z](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-NEXTVER/fsr4.1.1-igpu-cyboman-rdna2-NEXTVER.7z) (8.7 MB) or [.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-NEXTVER/fsr4.1.1-igpu-cyboman-rdna2-NEXTVER.zip) (124 MB) |

All files and checksums: [release `dll-NEXTVER`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-NEXTVER).
The previous release, `dll-2026-10-22`, stays available: [its page](dll-2026-10-22.md).

Each archive now holds five folders: `exact`, `lossy`, `lossy2` (as before), `4.1.2l-exact` and `4.1.2l-lossy` (new). The two Lite
builds are the same in all four archives. The `.7z` and the `.zip` hold the same files; Windows 11 (23H2 or later) opens a `.7z`
itself, on Windows 10 use [7-Zip](https://www.7-zip.org/) or take the `.zip`. Never use any of them in online games or games with
anti-cheat. Not for Radeon RX 9000 cards.

## Speed

FSR 4's time per frame, ms, Balanced, moving scene, **Linux (Proton), one Radeon RX 7800 XT**, two runs each. Windows timing-kit
figures are not in yet.

| Output | FSR 4.1.2 Lite (AMD) | 4.1.2l-exact | 4.1.2l-lossy |
|---|---|---|---|
| 1080p | 0.656 | 0.645 (−1.7%) | 0.560 (−14.7%) |
| 1440p | 1.036 | 1.005 (−2.9%) | 0.846 (−18.3%) |
| 4K | 2.016 | 1.988 (−1.4%) | 1.655 (−17.9%) |

The 4.1.1 builds' speed is unchanged from `dll-2026-10-22`.

## Picture

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../img/rel-lite-wires-dark.svg">
  <img src="../img/rel-lite-wires-light.svg" width="760" alt="Shimmer of thin wires while the camera pans, mean change per frame, lower is steadier, auto exposure off then on: FSR 4.1.2 Lite 9.75 and 7.81; 4.1.2l-lossy 5.88 and 3.83; FSR 4.1.1 7.16 and 6.79; lossy2 4.56 and 4.36.">
</picture>

4.1.2l-lossy against AMD's Lite, test rig, 4K Balanced, auto exposure off / on (lower is better):

| Test | FSR 4.1.2 Lite (AMD) | 4.1.2l-lossy | 4.1.2l-lossy against Lite |
|---|---|---|---|
| Thin wires, camera pan: change per frame | 9.75 / 7.81 | 5.88 / 3.83 | better |
| Rain specks brighter than 20 levels | 0 / 254 | 0 / 0 | better with auto exposure on |
| Fireflies | 259 / 321 | 275 / 62 | better with auto exposure on |
| Old image beside a moving object (scene B) | 4.35 / 4.35 | 2.57 / 2.63 | better |
| Fade: frames behind | 1.69 / 1.53 | 1.24 / 1.07 | better |
| Heavy film grain: change per frame | 2.31 / 0.41 | 1.40 / 0.82 | better off, worse on |
| Bright rain specks brighter than 20 levels | 78 / 1,592 | 256 / 297 | worse off, better on |
| Brightening: frames behind | 1.03 / 0.86 | 1.03 / 1.13 | worse with auto exposure on |
| Small, slow bright details: error | 2.68 / 2.66 | 3.17 / 3.09 | **worse** |
| Large particles: error | 0.71 / 0.71 | 0.92 / 0.92 | **worse** |
| Swaying foliage: error | 10.37 / 10.39 | 11.67 / 11.72 | **worse** |

All 23 tests, with FSR 4.1.1 and lossy2 beside them: [the Lite builds](../lite-builds.md#picture). Synthetic test scenes on Linux,
one run each; FSR 4.1.1 and Lite measured in this project's local test harness, not in AMD's own runtime.

## Not checked

Windows (the DLLs ran under Proton only); other cards; games. Ultra Performance and above 4K: [the Lite builds](../lite-builds.md#ultra-performance-and-above-4k).

## How it was checked

- 4.1.2l-lossy's DLL gives the frames of the Linux build the full check measured, byte for byte; 4.1.2l-exact's DLL gives the Lite
  network's frames byte for byte (1080p and 4K, auto exposure off and on, a still scene and a particle scene).
- The `exact`, `lossy` and `lossy2` DLLs are those of `dll-2026-10-22` (same checksums).
