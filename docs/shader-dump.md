# Making a shader dump (Linux troubleshooting)

[Back to the front page](../README.md)

Use this when the launch option gives a wrong image or no speedup and you have been asked for a
dump. It takes about ten minutes. A dump is a folder of the shaders the game compiled, as
Proton translated them on your machine; it shows whether your game runs the shaders the prebuilt
files were made for, and lets you build files that fit your setup exactly.

You need Linux, Steam with Proton, this repository, and `python3` plus SPIRV-Tools (the package
is usually called `spirv-tools`). Replace `/home/you` with your home folder throughout.

## 1. Use AMD's original DLL

The game must run AMD's unmodified `amd_fidelityfx_upscaler_dx12.dll` (version 4.1.1.2740).
OptiScaler should show FSR as plain `4.1.1`. With a patched DLL (`4.1.1-...-cyboman`, `4.1.1b`)
the dump contains that DLL's shaders, which is not what is being checked.

## 2. Dump

1. Make an empty folder:

   ```
   mkdir ~/fsr4-dump
   ```

2. In Steam, set the game's launch options to this. Remove `VKD3D_SHADER_OVERRIDE` for this run
   and keep any other options you use in front of `%command%`:

   ```
   VKD3D_SHADER_DUMP_PATH='Z:/home/you/fsr4-dump' %command%
   ```

3. Start the game with FSR 4 on, at the output resolution and preset you normally play at, load
   into gameplay, wait a few seconds, and quit. The folder now holds a few thousand files.

## 3. Check it against the prebuilt files

In a terminal, in this repository's folder:

```
./check_prebuilt.sh ~/fsr4-dump
```

It compares the dumped shaders with the ones the prebuilt files were made from and prints one of:

- **"All N shaders match: prebuilt/ fits your setup."** Proton translated AMD's shaders on your
  machine exactly as on the machine the prebuilt files were made on.
- **"N of M shaders are translated differently on your setup."** The prebuilt files do not fit and
  would give a wrong image. Go on to step 4 and use your own build.
- **"None of the shaders prebuilt/ covers is in this dump."** The shaders are not AMD's 4.1.1.2740
  ones (another FSR version or a modified DLL), or FSR 4 was not running during the dump.

Keep the output for your report.

## 4. Build files from your own dump and test them

```
./build_override.sh ~/fsr4-dump ~/fsr4-own
```

It prints the files it wrote and a launch option. Put that launch option in Steam in place of the
dump one, start the game, and compare the image and OptiScaler's upscaler time with AMD's shaders
(no launch option), standing at the same spot.

If it says it found no FSR 4.1.1 shaders, stop here and report that.

## 5. Only if the image is still wrong: find which shader

Build each of the two rewrites alone, into its own folder, and test each the same way:

```
PASS11=0 ./build_override.sh ~/fsr4-dump ~/fsr4-postpass-only
POSTPASS=0 ./build_override.sh ~/fsr4-dump ~/fsr4-pass11-only
```

## 6. What to report

Open an issue on this repository, or reply wherever you were asked, with:

- GPU, Mesa version (`vulkaninfo --summary | grep -i driverInfo`) and Proton version;
- the game, output resolution and FSR preset;
- the output of step 3;
- what the image and the upscaler time were with: AMD's shaders, the `prebuilt` folder, your own
  build (step 4), and, if you did step 5, each single-shader build;
- screenshots of the same spot with AMD's shaders and with the build that looks wrong, if you can;
- if you are willing, the dumped files that step 3 lists as differing, or, if none differ, the
  ones `build_override.sh` names in step 4 (zip them). They are AMD's shaders as Proton
  translated them; nothing from your system is in them.

Afterwards the dump folder can be deleted, and the launch option set back to what you want to use.
