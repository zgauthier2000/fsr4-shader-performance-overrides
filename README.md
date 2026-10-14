# fsr4-shader-performance-overrides

Makes AMD FSR 4.1.1 upscaling faster on Radeon graphics cards, on Windows and Linux, by replacing
FSR 4's slowest shaders with faster ones. One file to swap, nothing else in the game changes.

## Quick start

> [!WARNING]
> **Never use this in online games or in any game with anti-cheat.** These are modified game files. Anti-cheat
> software can treat a changed DLL or changed shaders as tampering, and that can get an account banned. Use it in
> single-player games only.

**1. Download the zip for your graphics card.**

| Your graphics card | Download |
|---|---|
| A Radeon **RX 7000 or RX 6000** graphics card: the name has "RX" and a four-digit number, such as RX 7800 XT or RX 6700 XT. This includes gaming laptops with their own RX chip (RX 7700S, RX 6700M and the like) | **[fsr4.1.1-cyboman.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/latest/download/fsr4.1.1-cyboman.zip)** |
| **Graphics built into the processor:** most laptops, mini PCs and handhelds. The name is "Radeon Graphics" or "Radeon" with a three-digit number, such as Radeon 780M or 890M; also the Steam Deck | **[fsr4.1.1-igpu-cyboman.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/latest/download/fsr4.1.1-igpu-cyboman.zip)** |
| Radeon RX 9000 | not for these cards: they run a different FSR 4. Do not install it there. |

Not sure which you have? In Windows, open Task Manager, go to Performance and look at the GPU's name; on a
laptop with two, the RX one is the one games use.

**2. Choose a version.** Each zip holds two folders with one file each:

| Folder | Speed | Picture |
|---|---|---|
| `exact` | faster than AMD's | **the same as AMD's, byte for byte** |
| `lossy` | faster again | very close to AMD's, but not the same. Read `WARNING.txt` in that folder first |

If you are not sure, take `exact`.

**3. Put the file in the game's folder.** The game must already run FSR 4.1.1, for example through
[OptiScaler](https://github.com/optiscaler/OptiScaler).

1. Find `amd_fidelityfx_upscaler_dx12.dll` in the game's folder (often next to OptiScaler) and
   rename it to `amd_fidelityfx_upscaler_dx12.dll.orig`. It must be version 4.1.1.2740.
2. Copy the `amd_fidelityfx_upscaler_dx12.dll` from the folder you chose into its place.

This works on Windows and, under Proton, on Linux. Linux users can instead use
[one launch option](#linux-a-launch-option-instead-of-the-dll) and leave the DLL alone.

**4. Check that it worked.** Open OptiScaler's overlay in the game. The FSR version reads
`4.1.1-cyboman` (or `4.1.1-lossy-cyboman`; with the other zip `4.1.1-igpu-cyboman` or
`4.1.1-igpu-lossy-cyboman`), and the upscaler time is lower than before.

**To undo it,** delete the file and rename the `.orig` file back.

## What to expect

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/quickstart-dark.svg">
  <img src="docs/img/quickstart-light.svg" width="760" alt="What to expect at 4K on a Radeon RX 7800 XT in Shadow of the Tomb Raider, FSR 4.1.1 Balanced. AMD's shaders: 4.16 milliseconds of upscaling per frame, 97 frames per second. Exact DLL: 2.99 milliseconds, 109 frames per second, same picture byte for byte. Lossy DLL: 2.01 milliseconds, 122 frames per second, very close picture, opt-in. Other resolutions and other cards give other numbers.">
</picture>

- **The gain depends on the output resolution.** It is largest at 4K. At 1440p and 1080p the exact
  DLL's gain depends on the card: some keep most of it (an RX 7900 XT 30% at 1440p, an RX 6600 XT 24% at 1080p),
  others show little or nothing (the RX 7800 XT and an RX 7900 XTX at 1080p). The lossy DLL helps at every size,
  because it skips work instead of only doing the same work faster.
- **It depends on your graphics chip, too.** FSR 4 time saved at 4K, from testers' timing-kit runs and game reports
  so far:

  | Graphics chip | Exact DLL | Lossy DLL |
  |---|---|---|
  | Radeon RX 7000 | 15 to 35% in most reports; about 2% in two RX 7800 XT reports | 29 to 49% |
  | Radeon RX 6000 | from nothing to about 30% | 23 to 48% |
  | Integrated graphics and handhelds | from a few percent slower to 6% faster | 23 to 35% |
  | Intel Arc B580 (one report) | 6 to 8% | 31% |
  | GeForce RTX 3060 Ti (one report) | none | 34% |

  We do not yet know what decides where a card falls in its range. Most rows rest on a handful of single runs.
  [Results by graphics chip](docs/results.md#by-gpu-type), [timing kit results](timing-kit/RESULTS.md).
- **It only shows when the graphics card is the limit.** If the processor limits your frame rate,
  the frame rate does not change.
- **The exact DLL cannot change the picture.** Its output was compared with AMD's byte for byte at
  720p, 1080p, 1440p, 4K and 5K, in still and moving scenes. One intended exception: on RX 6000 cards under
  Windows, AMD's own file shows ghosting, and the exact DLL carries the fix, so its picture differs from AMD's there.
- **The lossy DLL trades a little accuracy for speed.** It runs FSR 4's neural network on every
  other frame and carries its result along with the picture's motion in between. Measured
  differences and comparison crops: [exact and lossy compared](docs/exact-vs-lossy.md). What the
  alternating cost means for frame caps and V-Sync: [frame pacing](docs/frame-pacing.md).

One card, one game, as an example of the best case: a Radeon RX 7800 XT, Shadow of the Tomb Raider's benchmark, 4K
output, FSR 4.1.1 Balanced. Your card and your game will give other numbers:

| | FSR 4 time per frame | Frame rate | Picture |
|---|---|---|---|
| AMD's shaders | 4.16 ms | 97 FPS | the reference |
| Exact | 2.99 ms (−28%) | 109 FPS (+12%) | identical |
| Lossy | 2.01 ms (−52%) | 122 FPS (+26%) | still picture within 0.2 dB of AMD's |

More games and resolutions: [all results](docs/results.md).

> [!NOTE]
> **Two settings where you will see little or no gain:**
> - **FSR's debug view (the overlay that draws FSR's watermark and debug panels).** The faster shaders do not cover the
>   debug versions of FSR's last pass, so AMD's own slow one runs and most of the gain is gone. Switch the debug view off
>   to measure or to play.
> - **Ultra Performance mode.** The lossy DLL does not skip frames there, so it is no faster than the exact DLL. The
>   exact DLL's own gain still applies.

## New in this release

> [!TIP]
> **The lossy DLL: slow fades keep up better, small dark things pulse less, and less of an old image is left beside moving objects.**
> - **Slow fades** (a scene growing lighter or darker with nothing moving): bright flat areas followed them up to half a frame later than with
>   AMD's shaders. Now brightening is 0.64 frames behind where it was 0.88 (AMD's 0.46), darkening 0.68 where it was 0.82 (AMD's 0.62).
>   [Details below](#a-change-that-lasts-two-frames-a-tighter-limit-beside-moving-objects-and-slow-fades-release-dll-2026-10-14).
> - **Small dark things that move without motion vectors** (dark leaves falling in front of a dark sky): with the camera
>   still they are shown more fully on the frames that skip the network (75.5% to 77.5% of the leaf; AMD's shaders 79.1%), and the
>   trace they leave is a little shorter (8.4% to 7.9%; AMD's 5.4%). A change now counts where it lasts two frames, which film grain
>   rarely does. While the camera pans nothing changes.
> - **Beside moving objects** the last shader keeps less of their old image: the outline of an object moving in front of a
>   still camera 1.30 to 1.15 (AMD's 1.07), a still object over fast ground 2.64 to 2.25 (1.62), thin bars fixed on screen in
>   front of a pan 0.91 to 0.86 (0.82).
> - **The price:** flat areas at rest change about a third more per frame and a moving background about a fifth more (both still
>   steadier than with AMD's shaders); the railing of the panning test scene flickers up to 3% more and strong film grain is about 5% less
>   steady with auto exposure off.
> - **Speed:** up to 0.02 ms more per frame at 4K (under 1%). The exact DLL is unchanged.
> - **Not run in a game yet.** Tested on a Radeon RX 7800 XT under Linux: the Linux files in the test rig, the DLLs under
>   Proton in the test rig and the timing kit.
> - **[The lossy DLL beside FSR 3.1, HelixSR and XeSS](docs/upscaler-comparison.md):** the same test scenes and the same
>   timing for all five, with one chart per upscaler and side-by-side crops. It shows where the
>   lossy DLL leads (accuracy close to FSR 4, areas a moving object has just uncovered, slowly swaying foliage, where it
>   is second only to FSR 4) and where it is weakest (fast-moving foliage, the brightness of a thin wire in a camera pan).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/release-radar-dark.svg">
  <img src="docs/img/release-radar-light.svg" width="760" alt="Two radar charts with ten spokes each. Left: this release's lossy DLL, with the previous release's as a dashed outline. Right: AMD's FSR 4.1.1, with this release's lossy DLL as a dashed outline. The spokes have the scale of the upscaler comparison's chart: the outer ring is the best of the five upscalers compared there (FSR 4.1.1, the lossy DLL, FSR 3.1, HelixSR, XeSS), and for film grain the best of these three. A larger shape is better. Still picture and moving background, mean: accuracy (dB): FSR 4.1.1 46.80 dB, the lossy DLL of dll-2026-10-13.2 46.62 dB, the lossy DLL of dll-2026-10-14 46.62 dB. Areas a moving object has just uncovered, mean of a panning and a still camera: accuracy (dB): FSR 4.1.1 33.55 dB, the lossy DLL of dll-2026-10-13.2 33.85 dB, the lossy DLL of dll-2026-10-14 33.94 dB. Old image beside a moving object, mean of seven scenes: error (of 255): FSR 4.1.1 1.92, the lossy DLL of dll-2026-10-13.2 2.31, the lossy DLL of dll-2026-10-14 2.27. Thin bars fixed on screen in front of a panning background, mean of four pans: error where their old image lands (of 255): FSR 4.1.1 0.82, the lossy DLL of dll-2026-10-13.2 0.91, the lossy DLL of dll-2026-10-14 0.86. Tiny fast sparks: share of their brightness shown (%): FSR 4.1.1 83%, the lossy DLL of dll-2026-10-13.2 74%, the lossy DLL of dll-2026-10-14 74%. Leaves swaying without motion vectors, mean of three sway speeds: error (of 255): FSR 4.1.1 11.0, the lossy DLL of dll-2026-10-13.2 14.5, the lossy DLL of dll-2026-10-14 14.6. Still picture with grain of 6, 10 and 15 of 255, mean: change per frame (of 255): FSR 4.1.1 1.69, the lossy DLL of dll-2026-10-13.2 1.06, the lossy DLL of dll-2026-10-14 1.09. Thin wire under a slow pan: how close its brightness is to the true one (%): FSR 4.1.1 90.5%, the lossy DLL of dll-2026-10-13.2 69.3%, the lossy DLL of dll-2026-10-14 69.3%. Still picture: change per frame (of 255): FSR 4.1.1 0.037, the lossy DLL of dll-2026-10-13.2 0.024, the lossy DLL of dll-2026-10-14 0.024. Time per upscale call, mean of 1080p, 1440p and 4K output (ms): FSR 4.1.1 2.69 ms, the lossy DLL of dll-2026-10-13.2 1.29 ms, the lossy DLL of dll-2026-10-14 1.29 ms.">
</picture>

Made-up test scenes on one graphics card, single runs; the speed spoke is the mean over 1080p, 1440p and 4K output from the comparison page's timing of the previous release plus this release's difference in the Windows timing kit (at 4K: 2.21 and 2.24 ms on the still scene). [The comparison page](docs/upscaler-comparison.md) sets this release's lossy DLL beside FSR 3.1, HelixSR and XeSS, with the figures and the scenes it does worst in.

> ### Help test it: the timing kit
> **[Download the Windows timing kit](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/timing-kit-2026-10-13.2/fsr4-timing-kit-windows.zip)** (experimental, 190 MB, version 2026-10-13.2): unpack, double-click
> `fsr4time.exe`, wait 15 to 20 minutes. It times FSR 4 with AMD's shaders and with these DLLs on
> your graphics card, shows which DLLs give the same picture on your machine, and offers to send
> the result. **Reports from Windows are in from eleven graphics chips so far; every further
> card helps.**
> - **Both kits were updated on 2026-10-13; if you ran an earlier one, please download and run again.**
>   - **Both kits (2026-10-13.2) carry the lossy build of `dll-2026-10-13.2`,** the release before this one. Nothing else changed in them. On Windows the lossy
>     DLL uses an image channel in a way that is only checked under Proton so far, so a run there is worth a lot: the
>     kit shows whether the lossy DLL gives the same picture in both of its runs on your card.
>   - **Since 2026-10-12.6 the Linux kit also times the lossy build's first shader on a skipped frame,** which
>     `dll-2026-10-12.2` made cheaper; before, its skipped-frame figure used the exact build's time for that shader.
>   - **Since the Windows kit 2026-10-12.3:** every DLL should give the same picture in both of its runs. Where one does
>     not, the summary now says how different the two are: how many 16x16-pixel blocks, where, and by how much. Two
>     reports from one RX 7800 XT showed such a difference for the lossy DLL at 4K, and this is there to find out what it is.
>   - **The Windows kit (2026-10-12.2) now shows which part of the exact DLL saves time on your card.** It carries two more
>     DLLs: AMD's shaders with only the rewritten last shader, and AMD's shaders with every other rewrite. On some cards
>     under Windows the exact DLL gains a lot and on others almost nothing, and this is how we find out why.
>   - **It times every DLL twice,** in opposite order, and shows both figures where they disagree, so a disturbed
>     reading can be told from a real difference. That makes the run longer than before (seven minutes); the 15 to
>     20 minutes are an estimate. `fsr4time.exe --once` gives the short run.
>   - **It times any FSR 4 DLL you put into a new folder under `dlls`,** not only 4.1.1, and every FSR 4 version that
>     DLL offers.
>   - **Linux kit 2026-10-12.5:** its time for the lossy build's postpass on a skipped frame was too high and is corrected
>     (details in the kit's README). Earlier Linux kit results overstate that one figure and the lossy average.
>   - **The Linux kit (2026-10-13.2; shorter since 2026-10-12.1):** 16 minutes for the full run on an RX 7800 XT, since three tests whose
>     question is settled are gone. It also reports how the card is connected (PCIe link), and when the card is busy
>     it asks you to close what is using it before it starts.
> - The Windows kit compares the moving picture as well as the still one.
> - **New: be named on the [thank-you page](docs/thanks.md).** When you send your result, the kit asks for a name or nickname to list. It is optional.
> - **RX 6000 owners:** AMD's own shaders show ghosting on these cards under Windows. The kit has two
>   extra reference DLLs and prints a fingerprint of each picture, so your run tells us whether the
>   exact DLL gives the corrected picture there.
> - **Not only Radeon:** the DLLs should run on any graphics chip whose driver supports DirectX 12 with
>   Shader Model 6.6, which includes GeForce and Intel Arc.
> - **Linux and the Steam Deck:** [the Linux kit](timing-kit), updated the same day. It now times the lossy
>   build's one changed model pass, and its check that the model passes give AMD's output, blind in kits before
>   2026-10-10, is fixed.
>
> [What the kits do](timing-kit/README.md#windows-experimental)

**The technical pages behind this release:**

- [A change that lasts two frames, a tighter limit beside different motion, and slow fades](research/frame-skip/README.md#a-change-that-lasts-two-frames-a-tighter-limit-beside-different-motion-and-slow-fades-release-dll-2026-10-14): how a skipped frame tells a small thing that has moved in from film grain by asking for the same change on two frames, why the note travels through the first shader, what a tighter limit beside moving objects costs, and which three rules held slow fades back
- [Small dark things without motion vectors: a one-sided test](research/frame-skip/README.md#small-dark-things-without-motion-vectors-a-one-sided-test-sb_oneside): why dark leaves falling in front of a dark sky pulsed, what does not tell them from film grain, and what does
- [A thin wire in a pan: the clamp only beside different motion](research/frame-skip/README.md#a-thin-wire-in-a-pan-the-clamp-only-beside-different-motion-release-dll-2026-10-132): which rule of a skipped frame dimmed a wire far thinner than a rendered pixel, and why it could go
- [Finer motion for the rules, a memory rule, and two cleared diagonals](research/frame-skip/README.md#finer-motion-for-the-rules-a-memory-rule-and-two-cleared-diagonals-release-dll-2026-10-13): how an old image beside thin things fixed on screen was traced to the network's memory, a spare image channel for finer motion, and a storage fault
- [A prepass in two copies, and a fold in the last shader](research/frame-skip/README.md#a-prepass-in-two-copies-and-a-fold-in-the-last-shader-release-dll-2026-10-122): where a skipped frame's time went, a rounding difference found on the way, and why three weight words
- [Foliage and the network's memory](research/frame-skip/README.md#foliage-and-the-networks-memory-release-dll-2026-10-12): why moving leaves lag when the network runs on every other frame, what was tried, and the rule for the slow case
- [Rain and other thin streaks](research/frame-skip/README.md#rain-and-other-thin-streaks-release-dll-2026-10-117): why a line passed the rule against single bright pixels, the rule that replaced it, and what it costs thin wires
- [Sparkling on glossy surfaces, and a shader that held too much](research/frame-skip/README.md#sparkling-on-glossy-surfaces-and-a-shader-that-held-too-much-release-dll-2026-10-116): single over-bright pixels taken for sparks, the test scene, and why a rule that cost nothing in the timing kit cost frames in a game
- [Shimmer with auto exposure on](research/frame-skip/README.md#shimmer-with-auto-exposure-on-the-history-store-release-dll-2026-10-115): the exposure value's wobble, the store that drops bits, why rounding everything was the wrong fix, and the narrow one that shipped
- [The exact files beside a "steady" test build](docs/steady-test.md): an unreleased experiment with the dead band of release `dll-2026-10-11.4` on the exact files, without frame skip
- [Why folding steadied the picture, and what replaced it](research/frame-skip/README.md#why-folding-steadied-the-picture-and-what-replaced-it-release-dll-2026-10-114): the network's weight for the new frame, the one-step flicker, the price in lag, and the dead band
- [Bright dots in foliage](research/frame-skip/README.md#bright-dots-in-foliage-release-dll-2026-10-113): why sky seen through leaves was shown as sparks, and the settings that were compared
- [A still object over fast ground](research/frame-skip/README.md#a-still-object-over-fast-ground-release-dll-2026-10-112): why release `dll-2026-10-11` left a ghost there, and the two fixes that were tried
- [Thin wires, particles and light folds](research/frame-skip/README.md#thin-wires-particles-and-light-folds-release-dll-2026-10-11): what erased the wires, the network's own verdict as a signal, and which further layers were folded
- [The lossy DLL's rules on a skipped frame](docs/lossy-rules.md): one flow chart of what the last shader does when the network did not run, and which fault each rule answers
- [The lossy DLL beside FSR 3.1, HelixSR and XeSS](docs/upscaler-comparison.md): five upscalers on the same scenes and the same timing, with charts and crops
- [Exact and lossy compared](docs/exact-vs-lossy.md): every measurement of the lossy DLL against AMD's, with comparison pictures, and its limits (moving foliage, thin wires in a camera pan)
- [Weight folding](research/lossy): the earlier experiment the light folds come from
- [The timing kits](timing-kit): what the Linux and Windows kits measure, and how to read their summaries

### A change that lasts two frames, a tighter limit beside moving objects, and slow fades (release `dll-2026-10-14`)

Three changes to the lossy DLL's rules. **The exact DLL is unchanged.**

**1. Small dark things that move without motion vectors.** `dll-2026-10-13.2` halved the pulse of dark leaves falling in front of a dark
sky with the camera still, but its test still cannot tell the edge of a leaf from film grain in a single frame.

- **The change.** Every frame now notes, per pixel, whether the new frame lies above or below the old picture by more than a small amount.
  A skipped frame counts the content as changed where its own difference passes that amount in the same direction as the note of the frame
  before. Grain differs in a new place on every frame; a leaf that has moved in, or the sky where a leaf has just been, differs on two frames
  in a row.
- **The note travels through the first shader.** It is kept in a spare channel of FSR 4's history image, and the first shader of a skipped
  frame, which reads that image anyway, passes it on, moved with the picture. Reading it back in the last shader directly cost 0.06 ms per
  skipped frame at 4K; this way it costs nothing measurable.

| Dark leaves falling in front of a dark sky, 4K output, skipped frames; auto exposure off / on | AMD's shaders | `dll-2026-10-13.2` | This release |
|---|---|---|---|
| Camera still: share of the leaf's darkness shown | 79.1% / 80.9% | 75.5% / 75.9% | 77.5% / 77.4% |
| Camera still: left where a leaf was up to 3 frames ago | 5.4% / 5.1% | 8.4% / 9.0% | 7.9% / 8.3% |
| Slow pan: shown | 69.3% / 70.1% | 70.1% / 71.8% | 70.0% / 71.6% |
| Fast pan: shown | 72.9% / 74.6% | 60.8% / 62.1% | 60.6% / 62.0% |
| Tiny slow particles, camera still: left behind | 10.5% / 10.5% | 12.8% / 13.4% | 11.5% / 11.7% |

On the frames that run the network the leaf is shown as before (81%). While the camera pans nothing changes: the at-rest tests do not
apply there.

**2. A tighter limit beside moving objects.** On a skipped frame, beside anything that moves differently from the pixel, the last shader
limits the old picture to the range of the nine new samples around the pixel. That range used to be widened by half of itself; since
`dll-2026-10-13.2` the limit applies only beside different motion, which made the tight form affordable. Less of an object's old image is
left beside it:

| Error where a thing's old image would land, skipped frames (of 255); auto exposure off / on | AMD's shaders | `dll-2026-10-13.2` | This release |
|---|---|---|---|
| An object moving in front of a still camera (8,0): its outline | 1.07 / 1.07 | 1.30 / 1.33 | 1.15 / 1.17 |
| A still bright object over fast ground at the same depth | 1.62 / 1.61 | 2.64 / 2.43 | 2.25 / 2.09 |
| Thin bars fixed on screen in front of a pan, mean of four pans (auto exposure off) | 0.82 | 0.91 | 0.86 |
| Areas a moving object has just uncovered, panning scene at 5K output: accuracy | 39.90 / 40.51 dB | 39.90 / 40.65 dB | 40.55 / 41.17 dB |

**3. Slow fades.** When a scene grows lighter or darker with nothing moving, bright flat areas followed up to half a frame later than with
AMD's shaders, more so when brightening.

- **The cause.** The lag sat on the frames that skip the network. Three of their rules, all there to keep the picture steady at rest, hold a
  pixel back: a change too small to matter is dropped, nothing is taken from the new frame where nothing moves, and the new frame's share is
  squared. AMD's network reacts faster to brightening than to darkening, and these rules threw that away.
- **The change.** The note of the first change also records whether the green channel has drifted up or down by a small amount, and it now
  reaches every frame. Where the same small drift repeats, a change too small to matter is no longer dropped, and on a frame that skips the
  network the pixel takes the network's own weight. Only small drifts count (up to 1% of the brightness), which keeps film grain and fine
  texture out.

| Bright flat areas during a slow fade, 4K: frames behind; auto exposure off / on | AMD's shaders | `dll-2026-10-13.2` | This release |
|---|---|---|---|
| Brightening | 0.46 / 0.46 | 0.88 / 0.90 | 0.64 / 0.71 |
| Darkening | 0.62 / 0.72 | 0.82 / 1.09 | 0.68 / 0.81 |
| Mid-bright flat areas, brightening | 0.89 / 0.77 | 1.21 / 1.08 | 0.91 / 0.82 |

**What the three changes cost and leave open:**

- **What got worse:**
  - Flat areas at rest change more per frame (from the third change): the worst piece of the still scene 0.057 to 0.078 (AMD's 0.126), with
    auto exposure on 0.096 to 0.118 (AMD's 0.213). A moving background changes a little more too: 0.022 to 0.028 at 4K (auto exposure on 0.030
    to 0.036).
  - The railing of the panning test scene changes a little more per frame, at every output size: 1.414 to 1.462 at 1440p (AMD's 1.419), 1.349 to
    1.367 at 1080p (1.276), 0.961 to 0.969 at 4K; with auto exposure on 1.503 to 1.545 at 1440p (1.483).
  - Strong film grain is a little less steady with auto exposure off: change per frame of a still picture with grain of 15 of 255 1.773 to 1.860
    (AMD's 2.549); grain of 6 and 10 are level (0.320 to 0.325, 1.081 to 1.100). With auto exposure on all three are level.
  - Isolated bright dots in foliage seen against the sky, camera still: 0.97 to 1.01 per thousand dark pixels with auto exposure off (AMD's 0.57).
- **What got better besides:** large particles with the camera still, 1.25 to 1.21 of 255 (AMD's 0.66); just-uncovered areas at 4K, 35.90 to
  36.00 dB (AMD's 34.48).
- **Unchanged or within 2%:** fine detail at rest, the still picture, the moving scene's accuracy at every size and from 30 to 120 FPS, the other
  ghost and plate scenes, wires, fast sparks, rain, fireflies, glints and swaying foliage.
- **Speed:** the first two changes cost nothing measurable; the third adds up to 0.02 ms per frame at 4K. Whole upscaler in the Windows timing
  kit under Proton on a Radeon RX 7800 XT, one quick run each: `dll-2026-10-13.2` 2.21 ms at 4K, this release without its third change 2.21 ms, and
  with it 2.24 ms on the still scene and 2.23 ms on the moving one (AMD's shaders 4.87). At 1440p 1.07 ms, at 1080p 0.68 ms. The last shader still
  fits the same number of registers.
- **Not run in a game yet.** Tested on a Radeon RX 7800 XT under Linux: the Linux files in the test rig, the DLLs under Proton in the test rig and
  the timing kit.
- **Not checked:**
  - The leaf and fade scenes at other output sizes than 4K (the scenes of the full check were run at every size).
  - The quality checks with the HDR option set (the DLLs were compared with the Linux files with it).
- These are single runs on made-up scenes.
  [A change that lasts two frames, a tighter limit beside different motion, and slow fades](research/frame-skip/README.md#a-change-that-lasts-two-frames-a-tighter-limit-beside-different-motion-and-slow-fades-release-dll-2026-10-14).

Earlier releases, including `dll-2026-10-13.2` (a thin wire in a camera pan brighter, dark falling leaves pulse less), `dll-2026-10-13` (less of an old image beside thin things fixed on screen), `dll-2026-10-12.2` (cheaper skipped frames, steadier film grain), `dll-2026-10-12` (slowly swaying foliage closer to AMD's), `dll-2026-10-11.7` (rain no longer shown as white dashes), `dll-2026-10-11.6` (no sparkling on glossy surfaces, a speed loss stopped), `dll-2026-10-11.5` (shimmer in bright flat areas with auto exposure on), `dll-2026-10-11.3` (fewer bright dots in foliage), `dll-2026-10-11.2` (a ghost behind bright objects over fast ground), `dll-2026-10-11` (white beads on thin wires, particles closer to AMD's), `dll-2026-10-10` (less shimmer on grain and flat areas) and `dll-2026-10-09` (particles on skipped frames, two downloads instead of eight): [changelog](docs/changelog.md).

## Will it work for me?

| Graphics card | Which zip | Status |
|---|---|---|
| RX 7900, 7800, 7700, 7600 (desktop RDNA3) | `fsr4.1.1-cyboman.zip` | measured here on an RX 7800 XT; testers report large gains on Windows |
| RX 6000 (RDNA2) | `fsr4.1.1-cyboman.zip` | runs, and includes the fix for the shimmering these cards show with AMD's file; at 4K, reports with the exact DLL range from a few percent to about 30%, and we do not yet know what decides it; a few percent at 1440p and below (tester reports) |
| Radeon 780M, 890M and other integrated graphics, Steam Deck | `fsr4.1.1-igpu-cyboman.zip` | experimental: few reports, small gains |
| RX 9000 (RDNA4) | none | no: a different FSR 4 runs there ([open for someone to pick up](docs/rdna4.md)) |
| Any other graphics chip: Nvidia GeForce, Intel Arc and Intel integrated graphics, older Radeon | `fsr4.1.1-cyboman.zip`; for a chip built into the processor try `fsr4.1.1-igpu-cyboman.zip` first | **should run, untested.** FSR 4.1.1's shaders are ordinary DirectX 12 compute shaders: they need Shader Model 6.6 with 8-bit integer dot products, 16-bit types and wave operations, which current drivers from all three makers provide. Users report the DLLs running on a GeForce laptop and on an Arc A770. Nothing has been measured there: the rewrites were made for Radeon chips, so they may or may not be faster than AMD's shaders, and "same picture" has only been verified on Radeon. A [timing-kit](timing-kit/README.md#windows-experimental) result tells both |

You also need a DirectX 12 game in which FSR 4.1.1 already runs, with
`amd_fidelityfx_upscaler_dx12.dll` version 4.1.1.2740.

Both DLLs have AMD's graphics-card check lifted (AMD's own file offers this FSR 4 only on desktop
RX 7000 cards), so they start on any card whose driver can run the shaders: DirectX 12 with Shader
Model 6.6. That is also why they must not go on an RX 9000 card, where a different FSR 4 would
then start as well.

If the first zip is slower than AMD's file on a small RX 6000 card, try the second one: it differs
only in one shader that is built smaller. Details: [GPU support](docs/gpu-support.md).

## Linux: a launch option instead of the DLL

On Linux you can leave AMD's DLL in place and give the game the replacement shaders directly.

1. Download or clone this repository.
2. In Steam, add this to the game's launch options (keep anything already there in front of
   `%command%`):

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-performance-overrides/prebuilt' %command%
   ```

   `Z:` is how Proton sees your Linux root, so `Z:/home/you/...` is `/home/you/...`. For the lossy
   version use the folder `prebuilt-lossy` instead, after reading the `WARNING.txt` in it.

- **The game must be using AMD's original DLL.** The launch option does nothing while a DLL from
  this project is installed, because the files are matched to AMD's shaders.
- **The version name does not change** with the launch option; OptiScaler shows plain `4.1.1`.
  The upscaler time is how you tell it applied.
- **The prebuilt files do not fit every setup.** They were made on an RX 7000 desktop card. On
  one tester's RX 6900 XT, Proton laid the same shaders out differently and the picture came out
  darker. If the picture looks wrong, build your own files:
  [Linux guide](docs/linux.md#building-your-own). `./tools/check_prebuilt.sh <dump folder>` tells you
  whether the prebuilt files fit.

If it does not get faster: [Linux guide](docs/linux.md).

## More about the files

Each DLL is AMD's own file with the rewritten shaders swapped in and the version name changed.
How that is done, and how to build it yourself: [`dll/`](dll). There is also a ReShade add-on
that does the same without touching the DLL: [`windows/`](windows).

The scripts that rewrite the Linux shaders and build the files in `prebuilt/` are in [`tools/`](tools)
(they were in the top folder until release `dll-2026-10-11.3`; commands in older posts need `tools/` in front).

**In some games OptiScaler's upscaler time is only reliable with the frame rate uncapped.** If
nothing changes at all, check that the game really runs FSR 4.1.1 with AMD's DLL version
4.1.1.2740; other versions have different shaders. See [shader variants](docs/variants.md).

## Good to know

- **Nothing else changes.** No game files are edited, and the output was compared byte for byte
  with AMD's at 4K, 1440p and 1080p.
- **Game and OptiScaler updates** can put the original DLL back; the launch option keeps working.
- **Never in online games or games with anti-cheat.** This changes the shaders the game renders with, and anti-cheat
  software can treat that as tampering. Single-player games only.
- **Linux:** do not set `RADV_PERFTEST=cswave32` for a game that runs FSR 4; it adds about 1.1 ms.

## More

| Page | What is in it |
|---|---|
| [All results](docs/results.md) | every game measured, benchmark pages with screenshots |
| [Linux guide](docs/linux.md) | requirements, building your own files, troubleshooting |
| [Making a shader dump](docs/shader-dump.md) | step by step, for reporting a wrong image or a missing speedup on Linux |
| [Timing kit](timing-kit) | a download for Linux and the Steam Deck that times every FSR 4 pass on your GPU, no game needed (new; five GPUs so far) |
| [GPU support](docs/gpu-support.md) | which download fits which GPU, integrated GPUs, RX 6000 cards and their shimmering fix |
| [Shader variants](docs/variants.md) | which versions of FSR 4's shaders are covered, and what to do if your game's is not |
| [How it works](docs/how-it-works.md) | what the rewrites do, where the time goes, what else was tried |
| [Exact and lossy compared](docs/exact-vs-lossy.md) | what the lossy DLL changes in the picture, with measurements and crops |
| [Lossy beside FSR 3.1, HelixSR and XeSS](docs/upscaler-comparison.md) | five upscalers on the same test scenes and timing, for comparison |
| [Frame pacing with the lossy builds](docs/frame-pacing.md) | what the alternating upscaler time means for frame caps, V-Sync, latency and overlay readings |
| [RDNA4](docs/rdna4.md) | what is known about the FP8 model on RX 9000 cards; open for anyone who can test on one |
| [Earlier releases](docs/changelog.md) | what each release changed, newest first |
| [Research](research) | the probes, data and scripts behind all of it |


## Star History

<a href="https://www.star-history.com/?repos=zgauthier2000%2Ffsr4-shader-performance-overrides&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=zgauthier2000/fsr4-shader-performance-overrides&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=zgauthier2000/fsr4-shader-performance-overrides&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=zgauthier2000/fsr4-shader-performance-overrides&type=date&legend=top-left" />
 </picture>
</a>

## Credits and license

The postpass rewrite is adapted from `tools/fsr4cap/postpass_lds.py` in
[bbport](https://github.com/deadinside28/bloodborne_pc), a native Linux port of Bloodborne whose
author found the slow store pattern and wrote the original rewrite for that project's own FSR 4.1.1
runtime. This repository ports it to the shaders vkd3d-proton generates, so it works in ordinary
games.

The scripts are licensed under the GNU GPL v2 or later, like the project they derive from. See
[LICENSE](LICENSE). The prebuilt shaders are modified versions of AMD's, distributed under the same
license together with AMD's notice; see [`prebuilt/NOTICE.md`](prebuilt/NOTICE.md). Not affiliated
with or endorsed by AMD.

Testers who have asked to be named are listed on the [thank-you page](docs/thanks.md).

This repository is maintained independently. If this project has provided value to you, and you want to help support the author, consider formalizing your support with a voluntary micro-donation:

<a href="https://www.buymeacoffee.com/cyboman" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>
