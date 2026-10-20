# lossy2: how it is built

lossy2 is the lossy version with new weights in six of the network's twelve layers (passes 1, 2, 4, 5, 10 and 12).
The weights were trained to match AMD's picture through the whole lossy frame loop, starting from lossy's own weights.
Everything else, including frame skip, the other six layers and Ultra Performance, is lossy's.
**lossy2 does not support Ultra Performance yet:** that mode has no trained weights and runs lossy's network unchanged.
What it changes in the picture is in [`WARNING.txt`](WARNING.txt).

This folder rebuilds lossy2 from its integer weights. The training tools, those of Durandal (the project's unreleased work on a
smaller network that runs on every frame), are not part of the repository; lossy2 is one step on that longer path.

| File | What it is |
|---|---|
| `weights_lossy2.npz` | the trained integer weights of the six passes (numpy) |
| `gen_lossy2.py` | writes the six passes as shaders from those weights, for every output-size class, into a copy of `prebuilt-lossy` |
| `header.glsl` | the shader declarations the passes start with |
| `to_hlsl.py` | the same passes as HLSL, for the Windows DLL |
| `build_lossy2.sh` | runs all of it and checks the result |
| `WARNING.txt` | lossy2's warning, copied into the built folder |

## Rebuilding

Linux folder (needs Python 3 with numpy and `glslangValidator`):

```
./build_lossy2.sh /tmp/lossy2
```

It must report 0 files differing from `prebuilt-lossy2`.

Windows DLL (also needs DXC; set `DXC_DIR` to a folder holding `bin/dxc` and `lib/`):

```
DXC_DIR=/path/to/dxc ./build_lossy2.sh /tmp/lossy2 <AMD's amd_fidelityfx_upscaler_dx12.dll> <this release's lossy DLL> desktop
```

Use `igpu` and the igpu lossy DLL for the other flavor. The script reads the shader set back out of the release's lossy DLL
(`dll/recover_set.py`), puts the 18 lossy2 shaders in, and patches AMD's DLL with the set. Compare the printed SHA-256 with the release's `SHA256SUMS`.
The release was built with DXC 1.9.2609.5 and glslang 16.4.0; other versions may give other bytes.
