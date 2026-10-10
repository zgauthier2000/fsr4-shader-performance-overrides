# fsr4-shader-performance-overrides

Makes AMD FSR 4.1.1 upscaling faster on Radeon graphics cards, on Windows and Linux, by replacing
FSR 4's slowest shaders with faster ones. One file to swap, nothing else in the game changes.

## Quick start

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

## New in this release

> ### Help test it: the timing kit
> **[Download the Windows timing kit](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/timing-kit-2026-10-05/fsr4-timing-kit-windows.zip)** (experimental, 110 MB): unpack, double-click
> `fsr4time.exe`, wait about five minutes. It times FSR 4 with AMD's shaders and with these DLLs on
> your graphics card, checks that the exact DLL gives AMD's picture on your machine, and offers to
> send the result. **Nobody has measured these DLLs on Windows yet; your run would be among the
> first.** It also runs on GeForce and Intel Arc graphics: people use these DLLs there, nothing has
> been measured, and a result from such a card would be the first. On Linux and the Steam Deck:
> [the Linux kit](timing-kit).
> [What the kits do](timing-kit#windows-experimental)

### The lossy DLL shows particles properly, and is closer to AMD's picture

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/lossy-improved-dark.svg">
  <img src="docs/img/lossy-improved-light.svg" width="760" alt="What changed in the lossy DLL, measured in the test rig at 4K. Share of a particle drawn without motion vectors that is shown where it truly is, on the frames that skip the model: tiny fast sparks, 16 percent in the previous release, 77 percent now, 83 percent with AMD's shaders; tiny slow embers, 67, 77 and 81 percent; larger particles, 70, 98 and 98 percent. How far a still picture is from AMD's: 0.71 dB in the previous release, 0.25 dB now.">
</picture>

- **Particles, sparks and embers no longer flicker or move at half the frame rate.** Games draw
  them without telling FSR that they move, and the previous lossy DLL kept them where they had
  been, or dimmed them, on every other frame. Seen and fixed in Elden Ring and in the menu of
  Mafia: The Old Country.
- **The still picture is closer to AMD's.** The lossy DLL no longer simplifies the neural
  network's arithmetic; it only skips it on every other frame.
- **It costs about 2% of the previous lossy DLL's speed** (Shadow of the Tomb Raider, 4K: 120 FPS
  against 122; the exact DLL gives 109, AMD's shaders 97).

The same skipped frame with the previous release and with this one, enlarged five times:

<img src="docs/img/cmp-particles.png" width="760" alt="Particles drawn without motion vectors on a frame that skips the model, camera still, pieces of the 4K output enlarged five times, each shown as the true image, the exact files, the lossy build of the previous release and this release's lossy build. Tiny fast sparks: the previous release shows one displaced and one nearly gone; this release shows all three in place, slightly blocky. Larger particles: the previous release shows them displaced and broken up; this release shows them in place with thin seams across them.">

Enlarged like this, this release's particles are a little blocky and have thin seams; at normal
size and in motion that was not visible in the games it was checked in. More comparisons, and
what the lossy DLL still does worse than AMD's: [exact and lossy compared](docs/exact-vs-lossy.md).

### A possible speed-up on Windows, and how to help find out

Two things changed inside both DLLs, with the same picture as before:

- **The last pass writes all three of its images in ordered rows.** The previous DLL did that for
  two of them and left the third to AMD's scattered writes, the slow part of AMD's own shader.
- **The code our rewrites replaced is gone from the file.** The previous DLL left it in for the
  graphics driver to discard.

Both can make the DLLs faster on Windows, where AMD's own driver compiles these shaders. How much
depends on what that driver did with the leftover code and the scattered writes, and nobody has
measured it yet. **That is what the [Windows timing kit](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/timing-kit-2026-10-05/fsr4-timing-kit-windows.zip) is for:** it times the DLLs on
your graphics card, and the previous release's too if you put its file into a folder of its own
under `dlls`.

What is known so far, from one RX 7800 XT on Linux with Proton:

| | Result |
|---|---|
| The last pass, timed alone | faster: 0.42 → 0.30 ms at 1440p; at 4K steady at 0.66 ms where it varied between 0.69 and 0.90 |
| The whole upscaler through the DLL, as a game runs it | the same as the previous DLL: 3.16 ms at 4K, 1.46 against 1.43 ms at 1440p |
| On Windows, any graphics card | not measured yet |

Proton's driver was already discarding the leftover code, so that machine cannot show what
Windows will do.

**Two downloads instead of eight.** One zip for Radeon RX 7000 and RX 6000 graphics cards, one for
graphics built into the processor; each holds the exact and the lossy DLL. The separate RX 6000
builds are gone: their fix is in both DLLs now. It cost nothing measurable here; on Windows with
an RX 7000 card that has not been measured either.

Earlier releases: [changelog](docs/changelog.md).

## What to expect

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/quickstart-dark.svg">
  <img src="docs/img/quickstart-light.svg" width="760" alt="What to expect at 4K on a Radeon RX 7800 XT in Shadow of the Tomb Raider, FSR 4.1.1 Balanced. AMD's shaders: 4.16 milliseconds of upscaling per frame, 97 frames per second. Exact DLL: 2.99 milliseconds, 109 frames per second, same picture byte for byte. Lossy DLL: 2.15 milliseconds, 120 frames per second, very close picture, opt-in. Lower output resolutions and slower cards gain less.">
</picture>

- **The gain depends on the output resolution.** It is largest at 4K. At 1440p and 1080p the exact
  DLL gains little, sometimes nothing you can measure; the lossy DLL still helps there, because it
  skips work instead of only doing the same work faster.
- **It only shows when the graphics card is the limit.** If the processor limits your frame rate,
  the frame rate does not change.
- **The exact DLL cannot change the picture.** Its output was compared with AMD's byte for byte at
  720p, 1080p, 1440p, 4K and 5K, in still and moving scenes.
- **The lossy DLL trades a little accuracy for speed.** It runs FSR 4's neural network on every
  other frame and carries its result along with the picture's motion in between. Measured
  differences and comparison crops: [exact and lossy compared](docs/exact-vs-lossy.md). What the
  alternating cost means for frame caps and V-Sync: [frame pacing](docs/frame-pacing.md).

Measured on a Radeon RX 7800 XT, Shadow of the Tomb Raider's benchmark, 4K output, FSR 4.1.1 Balanced:

| | FSR 4 time per frame | Frame rate | Picture |
|---|---|---|---|
| AMD's shaders | 4.16 ms | 97 FPS | the reference |
| Exact | 2.99 ms (−28%) | 109 FPS (+12%) | identical |
| Lossy | 2.15 ms (−48%) | 120 FPS (+24%) | still picture within 0.2 dB of AMD's |

More games and resolutions: [all results](docs/results.md).

## Will it work for me?

| Graphics card | Which zip | Status |
|---|---|---|
| RX 7900, 7800, 7700, 7600 (desktop RDNA3) | `fsr4.1.1-cyboman.zip` | measured here on an RX 7800 XT; testers report large gains on Windows |
| RX 6000 (RDNA2) | `fsr4.1.1-cyboman.zip` | runs, and includes the fix for the shimmering these cards show with AMD's file; about 30% at 4K, a few percent at 1440p and below (tester reports) |
| Radeon 780M, 890M and other integrated graphics, Steam Deck | `fsr4.1.1-igpu-cyboman.zip` | experimental: few reports, small gains |
| RX 9000 (RDNA4) | none | no: a different FSR 4 runs there ([open for someone to pick up](docs/rdna4.md)) |
| Nvidia GeForce, Intel Arc | `fsr4.1.1-cyboman.zip` | **untested.** Users report that the DLLs run on a GeForce laptop and on an Arc A770. The rewrites were made for Radeon chips, so they may or may not be faster than AMD's shaders there, and "same picture" has only been verified on Radeon. A [timing-kit](timing-kit#windows-experimental) result tells both |

You also need a DirectX 12 game in which FSR 4.1.1 already runs, with
`amd_fidelityfx_upscaler_dx12.dll` version 4.1.1.2740.

Both DLLs have AMD's graphics-card check lifted (AMD's own file offers this FSR 4 only on desktop
RX 7000 cards), so they start on any card. That is why they must not go on an RX 9000 card.

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
  [Linux guide](docs/linux.md#building-your-own). `./check_prebuilt.sh <dump folder>` tells you
  whether the prebuilt files fit.

If it does not get faster: [Linux guide](docs/linux.md).

## More about the files

Each DLL is AMD's own file with the rewritten shaders swapped in and the version name changed.
How that is done, and how to build it yourself: [`dll/`](dll). There is also a ReShade add-on
that does the same without touching the DLL: [`windows/`](windows).

**In some games OptiScaler's upscaler time is only reliable with the frame rate uncapped.** If
nothing changes at all, check that the game really runs FSR 4.1.1 with AMD's DLL version
4.1.1.2740; other versions have different shaders. See [shader variants](docs/variants.md).

## Good to know

- **Nothing else changes.** No game files are edited, and the output was compared byte for byte
  with AMD's at 4K, 1440p and 1080p.
- **Game and OptiScaler updates** can put the original DLL back; the launch option keeps working.
- **Online games:** this changes the shaders the game renders with. Use your own judgment in
  games with anti-cheat.
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

This repository is maintained independently. If this project has provided value to you, and you want to help support the author, consider formalizing your support with a voluntary micro-donation:

<a href="https://www.buymeacoffee.com/cyboman" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>
