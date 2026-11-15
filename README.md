<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/banner-dark.svg">
  <img src="docs/img/banner-light.svg" width="100%" alt="cyboman, FSR4 Performance Overrides: faster AMD FSR 4 upscaling on Windows and Linux">
</picture>
</p>

<div align="center">

Makes AMD FSR 4.1.2 upscaling faster on Radeon graphics cards, on Windows and Linux, by replacing
FSR 4's slowest shaders with faster ones. One file to swap, nothing else in the game changes.

<a href="https://www.buymeacoffee.com/cyboman"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me a Coffee" height="36"></a>

**[Download](#quick-start)** · [What to expect](#what-to-expect) · [New in this release](#new-in-this-release) · [Timing kit](#help-test-it-the-timing-kit) ·
[Recorded game clips, side by side](https://zgauthier2000.github.io/fsr4-upscaler-compare/) · [All pages](#more)

</div>

## Quick start

> [!WARNING]
> **Never use this in online games or in any game with anti-cheat.** These are modified game files. Anti-cheat
> software can treat a changed DLL or changed shaders as tampering, and that can get an account banned. Use it in
> single-player games only.

**1. Download the archive for your graphics card.**

| Your graphics card | Download |
|---|---|
| A Radeon **RX 7000** graphics card: "RX 7" and three more digits, such as RX 7800 XT or RX 7600, including laptops with their own RX 7000 chip (RX 7700S, RX 7600M and the like), and the **Steam Machine** | **[fsr4.1.2-cyboman-rx7000-2026-11-05.7z](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-11-05/fsr4.1.2-cyboman-rx7000-2026-11-05.7z)** (8.9 MB) or [.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-11-05/fsr4.1.2-cyboman-rx7000-2026-11-05.zip) (100 MB) |
| A Radeon **RX 6000** graphics card: "RX 6" and three more digits, such as RX 6700 XT or RX 6600, including laptops with their own RX 6000 chip (RX 6700M and the like) | **[fsr4.1.2-cyboman-rx6000-2026-11-05.7z](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-11-05/fsr4.1.2-cyboman-rx6000-2026-11-05.7z)** (8.9 MB) or [.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-11-05/fsr4.1.2-cyboman-rx6000-2026-11-05.zip) (100 MB) |
| **Newer graphics built into the processor** (Radeon 780M, 760M, 880M, 890M and other RDNA 3 and 3.5 chips), and **any other card**: Nvidia GeForce, Intel Arc, older Radeon | **[fsr4.1.2-igpu-cyboman-rdna3-2026-11-05.7z](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-11-05/fsr4.1.2-igpu-cyboman-rdna3-2026-11-05.7z)** (8.9 MB) or [.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-11-05/fsr4.1.2-igpu-cyboman-rdna3-2026-11-05.zip) (100 MB) |
| **Steam Deck** and **older graphics built into the processor** (Radeon 680M, 660M, 610M, the graphics of Ryzen 7000 and 9000 desktop processors) | **[fsr4.1.2-igpu-cyboman-rdna2-2026-11-05.7z](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-11-05/fsr4.1.2-igpu-cyboman-rdna2-2026-11-05.7z)** (8.9 MB) or [.zip](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/dll-2026-11-05/fsr4.1.2-igpu-cyboman-rdna2-2026-11-05.zip) (100 MB) |
| Radeon RX 9000 | not for these cards: they run a different FSR 4. Do not install it there. |

The `.7z` and the `.zip` hold the same files. Windows 11 (version 23H2 or later) opens a `.7z` itself; on Windows 10 use
[7-Zip](https://www.7-zip.org/) or take the `.zip`.

Not sure which you have? In Windows, open Task Manager, go to Performance and look at the GPU's name; on a
laptop with two, the RX one is the one games use. Every archive works on every card; the one for your card is the fastest there.

**2. Choose a version.** Each archive holds four folders with one file each, and `WHICH-SHOULD-I-CHOOSE.txt`, a short guide:

| Folder | Network | Speed | Picture |
|---|---|---|---|
| `exact` | FSR 4.1.2 | faster than AMD's | **the same as AMD's, byte for byte** (the RX 6000 and Steam Deck / older built-in graphics archives: AMD's FSR 4.1.2 for RX 6000, which in games looks the same as 4.1.1: [why](docs/amd-411-vs-412.md)) |
| `lossy` | FSR 4.1.2, trained | faster again | close to AMD's, not the same. **This is the build earlier releases called `lossy2`, retrained** (the older, untrained lossy build is no longer included). Brightening catches up more slowly than before. Read `WARNING.txt` in that folder first |
| `4.1.2l-exact` | FSR 4.1.2 Lite, AMD's smaller network | a little faster than AMD's Lite | **the same as AMD's Lite, byte for byte** (not the same as full FSR 4) |
| `4.1.2l-lossy` | FSR 4.1.2 Lite | about 13 to 22% faster than AMD's Lite | close to Lite's, not the same; thin wires shimmer less in motion, small bright details are less accurate. Read `WARNING.txt` in that folder first |

If you are not sure, take `exact`.

**3. Put the file in the game's folder.** The game must already run FSR 4.1.1, for example through
[OptiScaler](https://github.com/optiscaler/OptiScaler).

1. Find `amd_fidelityfx_upscaler_dx12.dll` in the game's folder (often next to OptiScaler) and
   rename it to `amd_fidelityfx_upscaler_dx12.dll.orig`. It must be version 4.1.1.2740.
2. Copy the `amd_fidelityfx_upscaler_dx12.dll` from the folder you chose into its place.

This works on Windows and, under Proton, on Linux. Linux users can instead use
[one launch option](#linux-a-launch-option-instead-of-the-dll) and leave the DLL alone.

**4. Check that it worked.** Open OptiScaler's overlay in the game. The FSR version reads `4.1.2-exact-r3-cyboman`
(or `4.1.2-lossy-r3-cyboman`, `4.1.2l-exact-r3-cyboman`, `4.1.2l-lossy-r3-cyboman`; `r3` is the RX 7000 archive, `r2` the RX 6000 one, `igpu-r3` and
`igpu-r2` the two built-in graphics archives), and the upscaler time is lower than before.

**To undo it,** delete the file and rename the `.orig` file back.

## What to expect

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/quickstart-dark.svg">
  <img src="docs/img/quickstart-light.svg" width="760" alt="What to expect at 4K: how much less time FSR 4 takes per frame with this project's builds than with AMD's own, card by card, moving scene, Balanced. RX 7800 XT, Linux (this project): exact 37%, lossy 55% less time than AMD's FSR 4.1.2; 4.1.2l-exact 2%, 4.1.2l-lossy 18% less than AMD's Lite. RX 7900 XTX, Windows (1 report): exact 31%, lossy 44% less time than AMD's FSR 4.1.2; 4.1.2l-exact 7%, 4.1.2l-lossy 16% less than AMD's Lite. RX 7900 XT, Windows (1 report): exact 18%, lossy 34% less time than AMD's FSR 4.1.2; 4.1.2l-exact 6%, 4.1.2l-lossy 5% less than AMD's Lite. RX 7800 XT, Windows (2 reports): exact 9%, lossy 27% less time than AMD's FSR 4.1.2; 4.1.2l-exact 6%, 4.1.2l-lossy 14% less than AMD's Lite. RX 7600, Windows (3 reports): exact 31%, lossy 41% less time than AMD's FSR 4.1.2; 4.1.2l-exact 4%, 4.1.2l-lossy 10% less than AMD's Lite. RX 6900 XT, Windows (1 report): exact 4%, lossy 19% less time than AMD's FSR 4.1.2; 4.1.2l-exact 2%, 4.1.2l-lossy 13% less than AMD's Lite. RX 6800 XT, Windows (1 report): exact 5%, lossy 19% less time than AMD's FSR 4.1.2; 4.1.2l-exact 4%, 4.1.2l-lossy 13% less than AMD's Lite. RX 6800, Windows (2 reports): exact 2%, lossy 16% less time than AMD's FSR 4.1.2; 4.1.2l-exact 7%, 4.1.2l-lossy 11% less than AMD's Lite. RX 6750 XT, Windows (4 reports): exact 2%, lossy 16% less time than AMD's FSR 4.1.2; 4.1.2l-exact 7%, 4.1.2l-lossy 11% less than AMD's Lite. RX 6700 XT, Windows (6 reports): exact 2%, lossy 16% less time than AMD's FSR 4.1.2; 4.1.2l-exact 8%, 4.1.2l-lossy 11% less than AMD's Lite. RX 6700, Windows (2 reports): exact 3%, lossy 16% less time than AMD's FSR 4.1.2; 4.1.2l-exact 7%, 4.1.2l-lossy 12% less than AMD's Lite. RX 6650 XT, Windows (1 report): exact 4%, lossy 18% less time than AMD's FSR 4.1.2; 4.1.2l-exact 6%, 4.1.2l-lossy 12% less than AMD's Lite. RX 6600 XT, Windows (1 report): exact 4%, lossy 18% less time than AMD's FSR 4.1.2; 4.1.2l-exact 6%, 4.1.2l-lossy 12% less than AMD's Lite. RX 6600, Windows (1 report): exact 4%, lossy 18% less time than AMD's FSR 4.1.2; 4.1.2l-exact 6%, 4.1.2l-lossy 12% less than AMD's Lite. RX 6600M, Windows (1 report): exact 3%, lossy 17% less time than AMD's FSR 4.1.2; 4.1.2l-exact 6%, 4.1.2l-lossy 11% less than AMD's Lite. The Windows rows come from testers' timing-kit reports of test builds with this release's shaders. Other resolutions give other numbers.">
</picture>

- **What the chart compares.** Exact and lossy against AMD's own FSR 4.1.2 on the same card, and the Lite builds against AMD's FSR 4.1.2 Lite.
  The right column shows how much less time AMD's Lite itself takes than AMD's FSR 4.1.2: Lite is a smaller network with a different picture
  ([how it compares](docs/upscaler-comparison.md)).
- **It depends on your graphics chip, and on Windows or Linux.** The same DLL saves much more under Linux on most Radeon cards. Full tables per
  card and size, other graphics chips and older builds: **[What to expect in detail](docs/what-to-expect.md)**.
- **It only shows when the graphics card is the limit.** If the processor limits your frame rate, the frame rate does not change.
- **The exact DLL cannot change the picture.** Its output was compared with AMD's byte for byte at 720p, 1080p, 1440p, 4K and 5K, in still and
  moving scenes ([AMD's 4.1.1 and 4.1.2](docs/amd-411-vs-412.md) for RX 6000 cards).
- **The lossy DLLs trade a little accuracy for speed.** They run FSR 4's neural network on every other frame and carry its result along with
  the picture's motion in between: [exact and lossy compared](docs/exact-vs-lossy.md), [frame pacing](docs/frame-pacing.md).
- **None of this project's DLLs work on Radeon RX 5000 (RDNA 1) cards,** on Windows or Linux, nor on RX Vega cards under Windows: FSR 4 gives
  only a black picture there ([issue #43](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/issues/43)).

## New in this release

**[See what this release changes against the previous one, in figures →](docs/releases/dll-2026-11-05.md)**

> [!TIP]
> **Faster Lite builds, most of all at 1440p and on the Steam Deck; the pictures stay as they were.** Only `4.1.2l-exact` and `4.1.2l-lossy` change; `exact` and `lossy` are the files of `dll-2026-11-01`.
>
> | Timing-kit reports, median, moving scene, less time per frame than the same build in `dll-2026-11-01` | `4.1.2l-exact` | `4.1.2l-lossy` |
> |---|---|---|
> | RX 7000, Windows (4 reports), 1080p / 1440p / 4K | 1% / 9% / 1% | 0% / 5% / 0% |
> | RX 6000, Windows (9 reports), 1080p / 1440p / 4K | 2% / 9% / 2% | 2% / 5% / 2% |
> | Steam Deck (2 reports), 800p / 1080p | 10% / 2% | 6% / 3% |
> | Steam Machine (1 report), 1080p / 1440p / 4K | 2% / 11% / 3% | 1% / 7% / 2% |
>
> **What got worse:** nothing slower beyond the spread of single runs (one: `4.1.2l-exact` on a Radeon 780M / Ryzen Z1 at 1080p, 1.7% slower, two reports). **Not measured:** GeForce and Intel Arc.
>
> Against AMD's Lite: `4.1.2l-exact` saves 11 to 16% and `4.1.2l-lossy` 13 to 22% at the sizes reported. [Everything that changed](docs/releases/dll-2026-11-05.md).

Earlier releases: [release pages](docs/releases/README.md), each against the one before it, and the [changelog](docs/changelog.md).

## Help test it: the timing kit

### Windows timing kit
**[Download the Windows timing kit](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/timing-kit-2026-11-14/fsr4-timing-kit-windows-2026-11-14.zip)** (experimental, version 2026-11-14; about 16 MB, and it downloads its tests, about 74 MB, on the first start): unpack, double-click
`fsr4time.exe`, wait about 15 minutes on a desktop graphics card (a Steam Deck: about 30 to 40 minutes; a Radeon 780M handheld: about 15 to 20 minutes). It times FSR 4 with AMD's shaders and with this project's
builds on your graphics card, checks that each gives the picture it should, and offers to send the result. Reports are in from more
than twenty graphics chips so far; every further card helps, including GeForce and Intel Arc.

### Linux timing kit
**[Download the Linux and Steam Deck timing kit](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/timing-kit-2026-11-14/fsr4-timing-kit-linux-2026-11-14.tar.gz)** (experimental, version 2026-11-14; about 54 MB, plus about 66 MB of tests it downloads on the first start): unpack, and in a terminal in that folder run
`bash run.sh`, choose a Proton if it asks, then wait about 15 minutes (on a Steam Deck about 30 to 40 minutes: one round of tests takes that long there). It runs the same tests as the Windows kit under Proton, with Proton from Steam or `umu-run`. On a Steam Deck, use Desktop Mode, plugged in.

Optional: the kit asks for a name or nickname for the [thank-you page](docs/thanks.md).
[What the kits do](timing-kit/README.md#windows-experimental) · [what each kit version added](timing-kit/README.md#what-each-kit-version-added)

## Will it work for me?

| Graphics card | Which archive | Status |
|---|---|---|
| RX 7900, 7800, 7700, 7600 (desktop RDNA3), and the Steam Machine | `fsr4.1.2-cyboman-rx7000-<version>` | measured here on an RX 7800 XT; testers report large gains on Windows; Steam Machine: three timing-kit reports (SteamOS) |
| RX 6000 (RDNA2) | `fsr4.1.2-cyboman-rx6000-<version>` | runs, and includes the fix for the shimmering these cards show with AMD's file; at 4K, reports with the exact DLL range from a few percent to about 30%, and we do not yet know what decides it; a few percent at 1440p and below (tester reports) |
| Radeon 780M, 760M, 880M, 890M and other RDNA 3 / 3.5 graphics built into the processor | `fsr4.1.2-igpu-cyboman-rdna3-<version>` | experimental: few reports, small gains |
| Steam Deck, Radeon 680M, 660M, 610M and other RDNA2 graphics built into the processor | `fsr4.1.2-igpu-cyboman-rdna2-<version>` | experimental: few reports, small gains |
| RX 9000 (RDNA4) | none | no: a different FSR 4 runs there ([open for someone to pick up](docs/rdna4.md)) |
| Any other graphics chip: Nvidia GeForce, Intel Arc and Intel integrated graphics, older Radeon | `fsr4.1.2-igpu-cyboman-rdna3-<version>` | **runs; few reports.** FSR 4.1.1's shaders are ordinary DirectX 12 compute shaders: they need Shader Model 6.6 with 8-bit integer dot products, 16-bit types and wave operations, which current drivers from all three makers provide. Timing-kit reports from GeForce cards (GTX 1650, RTX 3060 Ti, 3090, 5070) and Intel Arc (B580, 140V) show the exact DLL from no gain (GeForce) to 6 to 10% (Arc), and the lossy DLL 24 to 37% faster (see the table above). The rewrites were made for Radeon chips; please run the [timing kit](timing-kit/README.md#windows-experimental) and send the report: it tests this project's experiments on your card, which is how new speedups are found |

You also need a DirectX 12 game in which FSR 4.1.1 already runs, with
`amd_fidelityfx_upscaler_dx12.dll` version 4.1.1.2740.

Every DLL has AMD's graphics-card check lifted (AMD's own file offers this FSR 4 only on desktop
RX 7000 cards), so they start on any card whose driver can run the shaders: DirectX 12 with Shader
Model 6.6. That is also why they must not go on an RX 9000 card, where a different FSR 4 would
then start as well.

If the archive for your card is slower than AMD's file, or a game crashes with it, try another archive: they differ only in how
a few shaders are built (the integrated-graphics ones build network pass 11 smaller). Details: [GPU support](docs/gpu-support.md).

## Linux: a launch option instead of the DLL

On Linux you can leave AMD's DLL in place and give the game the replacement shaders directly.

1. Download or clone this repository.
2. In Steam, add this to the game's launch options (keep anything already there in front of
   `%command%`):

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-performance-overrides/prebuilt' %command%
   ```

   `Z:` is how Proton sees your Linux root, so `Z:/home/you/...` is `/home/you/...`. For the lossy
   version use the folder `prebuilt-lossy2` instead (the lossy2 of `dll-2026-10-22`: this release's retrained `lossy` and the Lite builds are
   DLLs only for now, and the Linux files did not change in this release; `prebuilt-lossy` is the older lossy build), after reading the `WARNING.txt` in it.

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

## Good to know

- **Nothing else changes.** No game files are edited, and the output was compared byte for byte
  with AMD's at 4K, 1440p and 1080p.
- **If a game crashes with the `exact` DLL** from the RX 7000 / RX 6000 archive, try the `exact` DLL from the
  `fsr4.1.2-igpu-cyboman-rdna3` archive instead: the same picture, byte for byte, with one shader built differently. In timing-kit
  reports on Windows it is about 1 to 1.5% slower on RX 6000 cards and no slower on RX 7000 cards (medians).
- **Game and OptiScaler updates** can put the original DLL back; the launch option keeps working.
- **Never in online games or games with anti-cheat.** This changes the shaders the game renders with, and anti-cheat
  software can treat that as tampering. Single-player games only.
- **Linux:** do not set `RADV_PERFTEST=cswave32` for a game that runs FSR 4; it adds about 1.1 ms.
- **Each DLL is AMD's own file** with the rewritten shaders swapped in and the version name changed. How that is done, and how to build it
  yourself: [`dll/`](dll); the lossy build's trained weights and the tools that rebuild it: [`research/lossy2`](research/lossy2/README.md).
  A ReShade add-on does the same without touching the DLL: [`windows/`](windows). The Linux scripts are in [`tools/`](tools).
- **In some games OptiScaler's upscaler time is only reliable with the frame rate uncapped.** If nothing changes at all, check that the game
  really runs FSR 4.1.1 with AMD's DLL version 4.1.1.2740; other versions have different shaders. See [shader variants](docs/variants.md).

> [!NOTE]
> **One setting where you will see little or no gain: FSR's debug view (the debug panels FSR can draw over the
> picture).** The faster shaders do not cover the debug versions of FSR's last pass, so AMD's own slow one runs and most
> of the gain is gone. Switch the debug view off to measure or to play. FSR's version watermark (the white text in the
> top left corner, switched on with the `MLSR-WATERMARK` environment variable) is not the debug view: with it on, every
> DLL keeps its full gain and frame skip works as usual (measured under Proton on an RX 7800 XT). It shows the DLL's
> version name, such as `4.1.2-EXACT-R3-CYBOMAN`, so it also tells you which build is running.

> [!NOTE]
> **Ultra Performance mode (since `dll-2026-10-15`).** The lossy DLL skips frames there too (with the older lossy build's untrained weights), and runs the network
> all the same on one in three of the frames it would skip. **Ultra Performance only, not representative of other
> modes:** at 4K about 3.2 to 2.5 ms per frame on an RX 7800 XT, and its picture costs there are larger than in other
> modes ([details](docs/releases/dll-2026-10-15.md)).

## More

| Page | What is in it |
|---|---|
| [What's moving](docs/whats-moving.md) | what the project is working on now, and which cards are most wanted in the timing kit |
| [Vote for games](https://zgauthier2000.github.io/fsr4-shader-performance-overrides/vote/) | which games the project should record and test with next |
| [Which GPUs use the project](https://zgauthier2000.github.io/fsr4-shader-performance-overrides/gpus/) | which cards send timing kit reports, and which GPU families download the builds |
| [What to expect in detail](docs/what-to-expect.md) | speed per card and size, other graphics chips, older builds, one game as an example |
| [All results](docs/results.md) | every game measured, benchmark pages with screenshots |
| [Linux guide](docs/linux.md) | requirements, building your own files, troubleshooting |
| [Making a shader dump](docs/shader-dump.md) | step by step, for reporting a wrong image or a missing speedup on Linux |
| [Timing kit](timing-kit/README.md) | downloads for Windows, Linux and the Steam Deck that time FSR 4 and this project's builds on your GPU, no game needed |
| [GPU support](docs/gpu-support.md) | which download fits which GPU, integrated GPUs, RX 6000 cards and their shimmering fix |
| [Shader variants](docs/variants.md) | which versions of FSR 4's shaders are covered, and what to do if your game's is not |
| [How it works](docs/how-it-works.md) | what the rewrites do, where the time goes, what else was tried |
| [Exact and lossy compared](docs/exact-vs-lossy.md) | what the older lossy build changes in the picture, with measurements and crops (today's lossy: its `WARNING.txt` and [the lossy2 notes](research/lossy2/README.md)) |
| [Lossy (lossy2) beside FSR 4.1.2 Lite, FSR 3.1, HelixSR and XeSS](docs/upscaler-comparison.md) | six upscalers on the same test scenes and timing, for comparison |
| [DeckyUpscaler](docs/deckyupscaler.md) | a first look at another FSR 4 Lite project, for the Steam Deck: speed and picture on one RX 7800 XT, and what each project could use |
| [Frame pacing with the lossy builds](docs/frame-pacing.md) | what the alternating upscaler time means for frame caps, V-Sync, latency and overlay readings |
| [RDNA4](docs/rdna4.md) | what is known about the FP8 model on RX 9000 cards; open for anyone who can test on one |
| [Release pages](docs/releases/README.md) | each release against the one before it, in pictures and figures |
| [The lossy DLL's rules](docs/lossy-rules.md) | what the last shader does on a skipped frame, and which fault each rule answers |
| [Earlier releases](docs/changelog.md) | what each release changed, newest first |
| [Research](research) | the probes, data and scripts behind all of it |

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

[DeckyUpscaler](https://github.com/doodlum/DeckyUpscaler), by doodlum, runs FSR 4 Lite on the Steam Deck. Its author invited this project to learn from it, fixed a fault this project reported, and allowed its builds in the Linux timing kit; see [what we found](docs/deckyupscaler.md).

Testers who have asked to be named are listed on the [thank-you page](docs/thanks.md).

## Star History

 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=zgauthier2000/fsr4-shader-performance-overrides&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=zgauthier2000/fsr4-shader-performance-overrides&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=zgauthier2000/fsr4-shader-performance-overrides&type=date&legend=top-left" />
 </picture>

[Star history on star-history.com](https://www.star-history.com/?repos=zgauthier2000%2Ffsr4-shader-performance-overrides&type=date&legend=top-left)
