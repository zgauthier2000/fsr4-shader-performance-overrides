# fsr4-shader-performance-overrides

Makes AMD FSR 4.1.1 upscaling about 25 to 30% cheaper on Radeon RX 7000 graphics cards, on Linux
and Windows, by replacing two of FSR 4's compute shaders with faster ones. **The image is
unchanged, byte for byte.** Nothing in the game or in OptiScaler is modified.

**Latest version: 2026-10-03, 14:40 EDT (commit `896d7f0`), the faster "phased" postpass.** If you
downloaded or built the files before that, get them again.
[What changed](results/phased-postpass).

## What to expect

At 4K, FSR 4 takes about 1 ms less GPU time per frame. When the GPU is the limit, that is:

| Your frame rate at 4K | Gain |
|---|---|
| around 60 FPS | up to about +6% |
| around 100 FPS | up to about +11% |
| around 120 FPS | up to about +14% |

At 1440p output the saving is 0.2 to 0.3 ms per frame, a few percent. If the CPU is the limit,
the frame rate does not change.

Measured on a Radeon RX 7800 XT, 4K output, FSR 4.1.1 Balanced:

| Game | FSR 4 time per frame | Frame rate |
|---|---|---|
| Rise of the Tomb Raider (built-in benchmark) | 4.30 → 3.02 ms (−30%) | 97.6 → 108.6 FPS (+11%) |
| Shadow of the Tomb Raider | 4.16 → 3.09 ms (−26%) | 97 → 104 FPS (+7%) in the benchmark with the first version; the current version adds about 3% more |

More games, 1440p and screenshots: [all results](docs/results.md).

### Where FSR 4's time goes now

Shadow of the Tomb Raider, 4K, Balanced, RX 7800 XT: **3.09 ms in total, down from 4.16 ms.**

| Part of FSR 4 | Time | Share | Room left |
|---|---|---|---|
| Model passes (12) | 1.86 ms | 60% | none found |
| Postpass (rewritten) | 0.63 ms | 20% | 0.05 ms at most |
| Prepass | 0.44 ms | 14% | a few hundredths of a millisecond |
| OptiScaler and dispatch overhead | 0.12 ms | 4% | outside the shaders |
| Two small shaders and gaps between passes | 0.04 ms | 1% | |

How this was measured, and everything that was tried on each part:
[How it works](docs/how-it-works.md).

## Will it work for me?

| GPU | Linux (Proton) | Windows |
|---|---|---|
| RX 7900, 7800, 7700, 7600 (desktop RDNA3) | yes, measured on an RX 7800 XT | yes, testers report large gains |
| Radeon 780M, 890M and other RDNA3 integrated GPUs | no: reported slower | no: reported slower |
| RX 6000, Steam Deck (RDNA2) | experimental, untested | experimental, untested |
| RX 9000 (RDNA4) | not needed: it runs a different FSR 4 | not needed |

You also need:

- a DirectX 12 game;
- FSR 4.1.1 with the INT8 model already running in it, for example through
  [OptiScaler](https://github.com/optiscaler/OptiScaler), with
  `amd_fidelityfx_upscaler_dx12.dll` version 4.1.1.2740.

Details for integrated GPUs and RDNA2: [GPU support](docs/gpu-support.md).

## Install

### Linux: one launch option

1. Download or clone this repository.
2. In Steam, add this to the game's launch options (keep anything already there in front of
   `%command%`):

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-performance-overrides/prebuilt' %command%
   ```

   `Z:` is how Proton sees your Linux root, so `Z:/home/you/...` is `/home/you/...`.

This covers output above 1080p in every mode except Ultra Performance. For anything else, or if it
does not get faster: [Linux guide](docs/linux.md).

### Windows (or Linux, if you prefer): replace one DLL

1. Download `amd_fidelityfx_upscaler_dx12.dll` from the
   [release](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-03).
2. In the game folder, rename the existing `amd_fidelityfx_upscaler_dx12.dll` (often next to
   OptiScaler) to `amd_fidelityfx_upscaler_dx12.dll.orig`. It must be version 4.1.1.2740.
3. Put the downloaded DLL in its place.

It is AMD's DLL with the two shaders swapped. Details, and how to build it yourself:
[`dll/`](dll). There is also a ReShade add-on that does the same without touching the DLL:
[`windows/`](windows).

### Check that it worked

Open OptiScaler's overlay and compare the upscaler time with and without the change, standing at
the same spot. **In some games that number is only reliable with the frame rate uncapped.** At 4K
it should drop by roughly 1 ms.

### Undo

Remove the launch option, or put the original DLL back.

## Good to know

- **Nothing else changes.** No game files are edited, and the output was compared byte for byte
  with AMD's at 4K, 1440p and 1080p.
- **Game and OptiScaler updates** can put the original DLL back; the launch option keeps working.
- **Online games:** this changes the shaders the game renders with. Use your own judgement in
  games with anti-cheat.
- **Linux:** do not set `RADV_PERFTEST=cswave32` for a game that runs FSR 4; it adds about 1.1 ms.

## More

| Page | What is in it |
|---|---|
| [All results](docs/results.md) | every game measured, benchmark pages with screenshots |
| [Linux guide](docs/linux.md) | requirements, building your own files, troubleshooting |
| [GPU support](docs/gpu-support.md) | Windows, integrated GPUs, the experimental RDNA2 unlock |
| [How it works](docs/how-it-works.md) | what the two rewrites do, where the time goes, what else was tried |
| [Research](research) | the probes, data and scripts behind all of it |

## Example images

Before

<img src="before.jpg" width="800" alt="Before">

After

<img src="after.jpg" width="800" alt="After">

## Credits and licence

The postpass rewrite is adapted from `tools/fsr4cap/postpass_lds.py` in
[bbport](https://github.com/deadinside28/bloodborne_pc), a native Linux port of Bloodborne whose
author found the slow store pattern and wrote the original rewrite for that project's own FSR 4.1.1
runtime. This repository ports it to the shaders vkd3d-proton generates, so it works in ordinary
games.

The scripts are licensed under the GNU GPL v2 or later, like the project they derive from. See
[LICENSE](LICENSE). The prebuilt shaders are modified versions of AMD's, distributed under the same
licence together with AMD's notice; see [`prebuilt/NOTICE.md`](prebuilt/NOTICE.md). Not affiliated
with or endorsed by AMD.
