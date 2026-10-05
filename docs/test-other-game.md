# One last check: does the problem follow the game or the system?

[Back to the front page](../README.md)

This page is for the tester who gets a frozen frame blended over the picture (it looks darker)
with the prebuilt Linux files in Final Fantasy VII Rebirth. It takes about ten minutes.

**What we know:** on that setup Proton prepares AMD's FSR 4 shaders slightly differently from the
machine the prebuilt files were made on, so the prebuilt files read their textures from the wrong
place. Files built from your own dump work. The DLL, the Proton version, OptiScaler, the mods and
the card generation have all been ruled out as the reason
([details](gpu-support.md#rdna2-needs-one-more-change-the-dot-products)).

**What this check answers:** whether that is something about Final Fantasy VII Rebirth, or
something about your system as a whole.

## Steps

Pick any **other** game where you use FSR 4 through OptiScaler.

1. Make sure that game uses AMD's original `amd_fidelityfx_upscaler_dx12.dll`. OptiScaler should
   show the FSR version as plain `4.1.1`, not `4.1.1-cyboman-...`.

2. Make an empty folder:

   ```
   mkdir ~/fsr4-dump-other
   ```

3. Set that game's launch option to this. Replace `YOURNAME` with your user name, and take out
   `VKD3D_SHADER_OVERRIDE` for this run if it is there:

   ```
   VKD3D_SHADER_DUMP_PATH='Z:/home/YOURNAME/fsr4-dump-other' %command%
   ```

4. Start the game, get into gameplay with FSR 4 on, wait a few seconds, and quit.

5. In a terminal, in the `fsr4-shader-performance-overrides` folder:

   ```
   git pull
   ./check_prebuilt.sh ~/fsr4-dump-other
   ```

6. Send back what it prints, and which game it was.

Afterwards you can delete the folder and remove the launch option.

## What the answer means

| It prints | Meaning |
|---|---|
| `All N shaders match: prebuilt/ fits your setup.` | The problem is specific to Final Fantasy VII Rebirth. The prebuilt files should work in this other game; you can confirm by pointing the launch option at `prebuilt` there and looking at the picture. |
| `N of M shaders are translated differently on your setup.` | It is something system-wide. In that case please also send: your Mesa version (`vulkaninfo --summary \| grep -i driverInfo`), how you launch games (Steam, Heroic, Lutris), and any environment variables you set globally. |
| `None of the shaders prebuilt/ covers is in this dump.` | FSR 4 was not running during the dump, or that game has a different FSR DLL version. Check that OptiScaler shows FSR 4.1.1 and try again. |

## In the meantime

Either of these gives you a correct picture in Final Fantasy VII Rebirth:

- the DLL from the [latest release](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/latest)
  (`test-rdna2.zip` for an RX 6000 card), with no launch option; or
- the launch option pointed at the files you built from your own dump (`~/fsr4-own`).
