# Linux: setup, building your own files, troubleshooting

[Back to the front page](../README.md)

## What you need

- Linux, and a D3D12 game running through Proton (vkd3d-proton). DX11 and Vulkan games are not
  covered. For Windows see the [Windows](gpu-support.md#windows) section.
- FSR 4.1.1 with the INT8 model actually running, for example through
  [OptiScaler](https://github.com/optiscaler/OptiScaler) with `amd_fidelityfx_upscaler_dx12.dll`
  version 4.1.1.2740. Other FSR versions have different shaders; the scripts will tell you if they
  find nothing they recognise.
- An RDNA3 card on the RADV driver. The slow pattern these rewrites remove was measured there.
  Other cards are untested, and RDNA4 runs a different FSR 4 model that this does not touch.
- Only if you build your own files: `python3` and SPIRV-Tools (`spirv-dis`, `spirv-as`,
  `spirv-val`).

## Quick start: the prebuilt files

The [`prebuilt/`](../prebuilt) folder holds the overrides for the common case: AMD's DLL version
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

## When the prebuilt files are not enough

The overrides match exact shaders. A game silently falls back to AMD's originals, with no error,
when it uses a shader you do not have a file for. That happens with:

- a different FSR DLL version;
- output at 1080p or below versus above 1080p (two different shader sets);
- Ultra Performance mode (its own model). Quality, Balanced and Performance share one;
- a game whose FSR setup differs, for example in how exposure is handled.

If the upscaler time does not drop, dump that game and run the script again.

## Things to know

- **The prebuilt files are modified AMD shaders.** They come from AMD's
  `amd_fidelityfx_upscaler_dx12.dll` 4.1.1.2740, which AMD's FidelityFX SDK licence lists under MIT
  terms. [`prebuilt/NOTICE.md`](../prebuilt/NOTICE.md) says exactly where they come from and carries
  AMD's notice. Running `build_override.sh` on a matching dump reproduces them byte for byte.
- **Dumps stay out of the repository.** A raw dump contains every shader of the game you ran, so
  `.gitignore` excludes dumps and your own `override/` folder.
- **Set the variable per game.** With `VKD3D_SHADER_OVERRIDE` set, vkd3d-proton stops using the
  SPIR-V stored in its pipeline caches for that game, which can lengthen the first loads.
- **Online games.** This only sets an environment variable for vkd3d-proton, but it does change
  what the game renders with. Use your own judgement in games with anti-cheat.
- **Do not set `RADV_PERFTEST=cswave32`** for a game that runs FSR 4. In a standalone benchmark it
  made every model pass 40 to 65% slower (pass 1: 0.29 to 0.45 ms; all 12: 2.03 to 3.13 ms), about
  1.1 ms of FSR 4 per frame.
- **To undo it,** remove the launch option.
