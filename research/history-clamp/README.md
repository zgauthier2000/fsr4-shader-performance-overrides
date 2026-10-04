# A lower bound on the history weight (changes the image)

[Back to the research index](../README.md)

Everything shipped by this repository leaves FSR 4's output unchanged, byte for byte. This is an
experiment that does not: it was asked for by a user who wanted to try it against shimmering in
motion. **It is not part of the normal DLL or the Linux overrides.**

## What it changes

For each output pixel, the postpass blends the reprojected previous output (the history) with the
filtered current frame:

    out = w * history + (1 - w) * current        w = sigmoid(a model output)

`history_clamp_dxil.py [min]` turns `w` into `max(w, min)` (0.8 by default) in all four places the
shader computes it. It works on the disassembled postpass of any of the 48 normal versions; it
finds the weight by its pattern, because the instruction numbers differ from version to version.
Run it on AMD's shader before `windows/dxil/postpass_lds_dxil.py`:

    dxc -dumpbin postpass.dxil > in.ll
    python3 history_clamp_dxil.py 0.8 < in.ll | python3 ../../windows/dxil/postpass_lds_dxil.py > out.ll

## What was measured

Only a still scene: the rig of [`../pruning`](../pruning) (32 jittered frames at 2260x1272 sampled
from a 4K screenshot, no motion, AMD's DLL 4.1.1.2740 under Proton, Radeon RX 7800 XT). PSNR in
sRGB.

| Frames | AMD against the screenshot | Clamp against the screenshot | Clamp against AMD | Largest pixel difference from AMD (of 255) |
|---|---|---|---|---|
| 2 | 41.72 dB | 41.57 dB | 48.9 dB | 98 |
| 8 | 43.52 dB | 43.62 dB | 55.4 dB | 50 |
| 32 | 44.43 dB | 44.43 dB | 63.8 dB | 29 |

On a still scene the clamped version reaches the same quality, slightly later.

## What was not measured

Anything in motion, which is the whole point of the change. The model lowers `w` where the history
is wrong, for example in areas a moving object has just uncovered. Forcing at least 80% history
there can be expected to leave ghosting or trails. Whether shimmering improves, and what it costs,
has to be judged in a game.

## Test builds

Release [`dll-2026-10-04.3`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-04.3):

| File | Contents |
|---|---|
| `test-history-clamp-0.8.zip` | the normal DLL (all 54 shader versions, both rewrites) with the clamp |
| `test-history-clamp-0.8-any-gpu.zip` | the same with AMD's GPU check lifted and the postpass's dot products split, as in `test-rdna2.zip` (see [GPU support](../../docs/gpu-support.md)) |

Both give the same image as each other on an RX 7800 XT. FSR's debug view still uses AMD's
postpass, without the clamp.
