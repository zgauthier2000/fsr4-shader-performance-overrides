# fsr4-shader-overrides

Makes AMD FSR 4.1.1 upscaling cheaper on Radeon RX 7000 (RDNA3) cards under Linux and Proton, by
replacing two of FSR's compute shaders with faster versions that produce the same output.

It is a small set of scripts. You run a game once to dump its shaders, the scripts rewrite the two
FSR shaders they recognise, and vkd3d-proton loads the rewritten ones from then on. Nothing in the
game, in OptiScaler or in AMD's DLLs is modified.

## Results

OptiScaler's upscaler time on a Radeon RX 7800 XT (Mesa 26.2, RADV), 4K output:

| Game | Mode | Before | After | Saved |
|---|---|---|---|---|
| Control Resonant | Performance | 5.4 ms | 3.5 ms | 1.9 ms (35%) |
| Mortal Shell II | Balanced | 4.97 ms | 3.58 ms | 1.39 ms (28%) |
| Shadow of the Tomb Raider | Balanced | 4.2 ms | 3.4 ms | 0.8 ms (19%) |
| Elden Ring (postpass only) | Balanced | 5.33 ms | 4.57 ms | 0.76 ms (14%) |

The saving varies by game. Only this one GPU has been tested.

## What you need

- A D3D12 game running through Proton (vkd3d-proton). DX11 and Vulkan games are not covered.
- FSR 4.1.1 with the INT8 model actually running, for example through
  [OptiScaler](https://github.com/optiscaler/OptiScaler) with `amd_fidelityfx_upscaler_dx12.dll`
  version 4.1.1.2740. Other FSR versions have different shaders; the scripts will tell you if they
  find nothing they recognise.
- An RDNA3 card on the RADV driver. The slow pattern these rewrites remove was measured there.
  Other cards are untested, and RDNA4 runs a different FSR 4 model that this does not touch.
- `python3` and SPIRV-Tools (`spirv-dis`, `spirv-as`, `spirv-val`).

## How to use it

1. **Dump the game's shaders once.** Create an empty folder, then add this to the game's launch
   options in Steam (keep anything already there in front of `%command%`):

   ```
   VKD3D_SHADER_DUMP_PATH='Z:/home/you/fsr4-dump' %command%
   ```

   Start the game with FSR 4 enabled at the output resolution you play at, load into gameplay, and
   quit. The folder fills with a few thousand files. `Z:` is how Proton sees your Linux root, so
   `Z:/home/you/...` is `/home/you/...`.

2. **Build the overrides.**

   ```
   ./build_override.sh /home/you/fsr4-dump
   ```

   It prints the files it wrote into `override/` and the launch option to use. If it finds no FSR
   4.1.1 shaders, FSR 4.1.1 was not running during the dump.

3. **Switch the launch option** from the dump variable to the one the script printed:

   ```
   VKD3D_SHADER_OVERRIDE='Z:/path/to/fsr4-shader-overrides/override' %command%
   ```

   The dump folder can be deleted now.

4. **Check it.** Compare OptiScaler's upscaler time with and without the variable, standing at the
   same spot. In some games that number is only reliable with the frame rate uncapped.

One `override/` folder serves every game. Files are named by shader hash, so if a second game uses
the same shaders it needs only the launch option, and if it uses different ones you repeat steps 1
and 2 and the new files are added alongside.

## When you need to dump again

The overrides match exact shaders. A game silently falls back to AMD's originals, with no error,
when it uses a shader you have not built yet. That happens with:

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

- **No shader files are included, on purpose.** The dumped and rewritten shaders contain AMD's
  code, so you build them from your own copy and should not redistribute them. `.gitignore` keeps
  them out of the repository.
- **Set the variable per game.** With `VKD3D_SHADER_OVERRIDE` set, vkd3d-proton stops using the
  SPIR-V stored in its pipeline caches for that game, which can lengthen the first loads.
- **Online games.** This only sets an environment variable for vkd3d-proton, but it does change
  what the game renders with. Use your own judgement in games with anti-cheat.
- **To undo it,** remove the launch option.

## Example images
Before

<img src="https://github.com/zgauthier2000/fsr4-shader-performance-overrides/blob/main/before.jpg" width="1080" alt="Before">

After

<img src="https://github.com/zgauthier2000/fsr4-shader-performance-overrides/blob/main/after.jpg" width="1080" alt="After">


## Credits and licence

The postpass rewrite is adapted from `tools/fsr4cap/postpass_lds.py` in
[bbport](https://github.com/deadinside28/bloodborne_pc), a native Linux port of Bloodborne whose
author found the slow store pattern and wrote the original rewrite for that project's own FSR 4.1.1
runtime. This repository ports it to the shaders vkd3d-proton generates, so it works in ordinary
games.

Licensed under the GNU GPL v2 or later, like the project it derives from. See [LICENSE](LICENSE).
Not affiliated with AMD.
