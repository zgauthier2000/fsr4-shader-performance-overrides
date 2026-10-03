# fsr4-shader-performance-overrides

Makes AMD FSR 4.1.1 upscaling cheaper on Radeon RX 7000 (RDNA3) cards under Linux and Proton, by
replacing two of FSR's compute shaders with faster versions that produce the same output.

It is three ready-made shader files plus the small scripts that build them. vkd3d-proton loads the
replacements through one launch option. Nothing in the game, in OptiScaler or in AMD's DLLs is
modified.

**Windows:** there is an experimental ReShade add-on for Windows in [`windows/`](windows). It has
been verified under Proton on Linux but not yet on Windows itself, and it is not known whether
Windows has this slowdown to begin with. See [`windows/README.md`](windows/README.md).

## Results

OptiScaler's upscaler time on a Radeon RX 7800 XT (Mesa 26.2, RADV), 4K output:

| Game | Mode | Before | After | Saved |
|---|---|---|---|---|
| Control Resonant | Performance | 5.4 ms | 3.5 ms | 1.9 ms (35%) |
| Mortal Shell II | Balanced | 4.97 ms | 3.58 ms | 1.39 ms (28%) |
| Shadow of the Tomb Raider | Balanced | 4.16 ms | 3.47 ms | 0.69 ms (17%) |
| Shadow of the Tomb Raider, 1440p output | Balanced | 1.76 ms | 1.55 ms | 0.21 ms (12%) |
| Elden Ring (postpass only) | Balanced | 5.33 ms | 4.57 ms | 0.76 ms (14%) |

The saving varies by game. Only this one GPU has been tested.

In Shadow of the Tomb Raider's built-in benchmark at 4K the average frame rate went from 97 to
104 FPS, and the frame time saved matches the upscaler time saved; see
[the full results](results/shadow-of-the-tomb-raider) with screenshots.

## What you need

- Linux, and a D3D12 game running through Proton (vkd3d-proton). DX11 and Vulkan games are not
  covered. For Windows see the [Windows](#windows) section.
- FSR 4.1.1 with the INT8 model actually running, for example through
  [OptiScaler](https://github.com/optiscaler/OptiScaler) with `amd_fidelityfx_upscaler_dx12.dll`
  version 4.1.1.2740. Other FSR versions have different shaders; the scripts will tell you if they
  find nothing they recognise.
- An RDNA3 card on the RADV driver. The slow pattern these rewrites remove was measured there.
  Other cards are untested, and RDNA4 runs a different FSR 4 model that this does not touch.
- Only if you build your own files: `python3` and SPIRV-Tools (`spirv-dis`, `spirv-as`,
  `spirv-val`).

## Quick start: the prebuilt files

The [`prebuilt/`](prebuilt) folder holds the overrides for the common case: AMD's DLL version
4.1.1.2740, output above 1080p, and any preset except Ultra Performance.

1. Clone or download this repository.
2. Add this to the game's launch options in Steam (keep anything already there in front of
   `%command%`):

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-performance-overrides/prebuilt' %command%
   ```

   `Z:` is how Proton sees your Linux root, so `Z:/home/you/...` is `/home/you/...`.
3. Compare OptiScaler's upscaler time with and without the variable, standing at the same spot. ***In
   some games, that number is only reliable with the frame rate uncapped.***

If the time does not drop, your game uses a shader variant that is not in `prebuilt/`. Build your
own as described next.

## Building your own

1. **Dump the game's shaders once.** Create an empty folder, then add this to the game's launch
   options in Steam (keep anything already there in front of `%command%`):

   ```
   VKD3D_SHADER_DUMP_PATH='Z:/home/you/fsr4-dump' %command%
   ```

   Start the game with FSR 4 enabled at the output resolution you play at, load into gameplay, and
   quit. The folder fills with a few thousand files.

2. **Build the overrides.**

   ```
   ./build_override.sh /home/you/fsr4-dump
   ```

   It prints the files it wrote into `override/` and the launch option to use. If it finds no FSR
   4.1.1 shaders, FSR 4.1.1 was not running during the dump.

3. **Switch the launch option** from the dump variable to the one the script printed:

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-performance-overrides/override' %command%
   ```

   The dump folder can be deleted now.

4. **Check it** the same way as in the quick start.

One `override/` folder serves every game. Files are named by shader hash, so if a second game uses
the same shaders it needs only the launch option, and if it uses different ones you repeat steps 1
and 2 and the new files are added alongside. To have everything in one place, copy the files from
`prebuilt/` into `override/` as well.

## Windows

There is an experimental route for Windows in [`windows/`](windows): a ReShade add-on that swaps
the same two shaders when AMD's DLL creates them. It has been verified under Proton on Linux but
**not on Windows itself**, and it is not known whether Windows has the slowdown to begin with. See
[`windows/README.md`](windows/README.md).

## When the prebuilt files are not enough

The overrides match exact shaders. A game silently falls back to AMD's originals, with no error,
when it uses a shader you do not have a file for. That happens with:

- a different FSR DLL version;
- output at 1080p or below versus above 1080p (two different shader sets);
- Ultra Performance mode (its own model). Quality, Balanced and Performance share one;
- a game whose FSR setup differs, for example in how exposure is handled.

If the upscaler time does not drop, dump that game and run the script again.

## What the two rewrites do

- **Postpass** (`postpass_lds_vkd3d.py`). FSR 4's last pass computes a 2x2 block of pixels per
  thread and writes each pixel separately into three images, so every store instruction writes
  every other pixel. That scattered pattern is slow on RDNA3. The rewrite collects each 32x32 block
  in workgroup memory and writes it out in solid rows. In a standalone benchmark at 4K the pass
  went from about 2.1 ms to 0.8-0.9 ms.
- **Model pass 11** (`zconst.py`). The pass uses a coordinate that is always zero in its loop
  counts, which stops the driver from unrolling the loops. Replacing it with a constant saves about
  0.1 ms.

Both rewrites leave the arithmetic untouched. In a standalone benchmark on the same GPU, the
rewritten shaders produced output byte-for-byte identical to AMD's.

## Things to know

- **The prebuilt files are modified AMD shaders.** They come from AMD's
  `amd_fidelityfx_upscaler_dx12.dll` 4.1.1.2740, which AMD's FidelityFX SDK licence lists under MIT
  terms. [`prebuilt/NOTICE.md`](prebuilt/NOTICE.md) says exactly where they come from and carries
  AMD's notice. Running `build_override.sh` on a matching dump reproduces them byte for byte.
- **Dumps stay out of the repository.** A raw dump contains every shader of the game you ran, so
  `.gitignore` excludes dumps and your own `override/` folder.
- **Set the variable per game.** With `VKD3D_SHADER_OVERRIDE` set, vkd3d-proton stops using the
  SPIR-V stored in its pipeline caches for that game, which can lengthen the first loads.
- **Online games.** This only sets an environment variable for vkd3d-proton, but it does change
  what the game renders with. Use your own judgement in games with anti-cheat.
- **To undo it,** remove the launch option.

## What else was tried

- **WMMA (matrix multiply instructions) for the model passes.** A bit-exact WMMA version of model
  pass 1 was built and measured: 0.41 ms against 0.29 ms for AMD's shader, so it is not used. The
  full write-up, data and sources are in [`research/wmma/`](research/wmma).
- **The other model passes and the prepass.** Benchmarked individually; apart from pass 11 they
  compile to little more than the arithmetic itself, and nothing worth rewriting was found.

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
