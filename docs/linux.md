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
- **Not RDNA2 (RX 6000) for now.** A tester with an RX 6900 XT reports that the launch option
  works there but the image comes out darker than with AMD's shaders (2026-10-05). The cause is
  not known yet; if you have an RDNA2 card and want to help find it, see
  [Making a shader dump](shader-dump.md). On RDNA2, use the DLL (`test-rdna2.zip`) instead, which the same tester runs
  without that problem.
- Only if you build your own files: `python3` and SPIRV-Tools (`spirv-dis`, `spirv-as`,
  `spirv-val`).

## Quick start: the prebuilt files

The [`prebuilt/`](../prebuilt) folder holds overrides for every normal version of the two shaders
in AMD's DLL version 4.1.1.2740: every output size, every preset, and every way a game can set up
exposure and colour space (54 files; see [shader variants](variants.md)).

1. Clone or download this repository.
2. Add this to the game's launch options in Steam (keep anything already there in front of
   `%command%`):

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-performance-overrides/prebuilt' %command%
   ```

   `Z:` is how Proton sees your Linux root, so `Z:/home/you/...` is `/home/you/...`.
3. Compare OptiScaler's upscaler time with and without the variable, standing at the same spot. ***In
   some games, that number is only reliable with the frame rate uncapped.***

If the time does not drop, see [when the prebuilt files are not enough](#when-the-prebuilt-files-are-not-enough).

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
when it uses a shader there is no file for. Since 2026-10-04 `prebuilt/` has a file for every
normal version in AMD's DLL 4.1.1.2740, so that should only happen with:

- a different FSR DLL version;
- a modified DLL: the patched DLL from this repository (it shows as `4.1.1-cyboman-...` in
  OptiScaler), fsr4xyz's `4.1.1b` or any other. Their shaders are not AMD's, so no file matches
  and the launch option does nothing; the DLL's own shaders run. Put AMD's original DLL back to
  use the launch option. Checked with release `dll-2026-10-04.5`: none of its shaders match;
- FSR's debug view (its versions of the postpass are not covered);
- a Proton or vkd3d-proton version that translates the shaders differently from the one the
  files were made with (GE-Proton 11-7). This has not been seen, but it cannot be ruled out.

If the image is wrong, or you were asked for a dump, follow
[Making a shader dump](shader-dump.md).

With a different FSR DLL version or another Proton, dump that game and build your own files as described above.

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
