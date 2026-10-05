# Removing weights from the model (not bit-exact)

[Back to the research index](../README.md)

Everything else in this repository leaves FSR 4's output unchanged, byte for byte. This experiment
asks what it would buy to give that up: remove part of the model's arithmetic and accept a
different image. The answer is: little time, for a loss that starts immediately. **Nothing from
this page is shipped.**

## Why pruning is the only lever left

The model passes are almost pure arithmetic, running at about one instruction per lane per clock
cycle. Pass 1, per thread:

| Part | Instructions | Share |
|---|---|---|
| Int8 dot products (4 multiply-adds each, weight as a constant) | 832 | 57% |
| Rounding, clamping and packing 48 intermediate values to int8 | about 240 | 17% |
| Output scaling and rounding (16 values) and the rest | about 380 | 26% |

Exact replacements were looked for and not found: none of the 4-byte weight words is zero (1.5 to
3.7% of single weights are), the clamps cannot be proven unnecessary (the worst-case sum overflows
int8 about 20 times over), the rounding has no shorter exact form, and exact fast-convolution
schemes need operands wider than 8 bits, which loses the 4-per-instruction dot product. So the only
way to run fewer instructions is to change the result.

## The test

- **Ground truth:** a 3840x2160 game screenshot.
- **Inputs:** 32 frames at 2260x1272 (Balanced), each point-sampled from the screenshot at a
  jittered position (`gen_inputs.py`), as a renderer would produce them. No motion, constant depth.
- **Pipeline:** AMD's real `amd_fidelityfx_upscaler_dx12.dll` 4.1.1.2740, run under Proton by
  `fsr4img.c` (the test program of bbport with an image-input mode), sharpening off.
- **Pruned shaders:** `wprune.py` sets the smallest weight words to zero (a word is the 4 int8
  weights one output channel applies to 4 input channels at one tap, one dot-product instruction;
  smallest by the sum of absolute values). The compiler then drops those instructions. Applied to
  the six passes whose weights are constants in the shader (1, 2, 4, 5, 10, 12), loaded with
  `VKD3D_SHADER_OVERRIDE`.
- **Error:** `metric.py`, PSNR in sRGB, against AMD's unpruned output and against the screenshot.
- **Time:** the six passes in the standalone benchmark, 500 dispatches each, Radeon RX 7800 XT.

With 0% pruned the output is byte-identical to AMD's, so the rig adds no error of its own.

## Result

| Pruned | Six passes | Saved | PSNR against AMD's output | PSNR against the screenshot | Largest pixel error (of 255) |
|---|---|---|---|---|---|
| 0% | 1.289 ms | | identical | 44.43 dB | 0 |
| 5% | 1.252 ms | 0.04 ms | 59.9 dB | 44.37 dB | 36 |
| 10% | 1.222 ms | 0.07 ms | 56.8 dB | 43.96 dB | 39 |
| 20% | 1.145 ms | 0.14 ms | 49.2 dB | 42.98 dB | 111 |
| 30% | 1.069 ms | 0.22 ms | 46.7 dB | 41.69 dB | 147 |
| 50% | 0.915 ms | 0.37 ms | 47.2 dB | 41.78 dB | 137 |

About 0.007 ms is saved per 1% pruned. At 5% the average image is nearly unchanged but single
pixels are already far off; at 20% the result is 1.5 dB further from the true image, for less
time than the phased postpass saved at no cost in quality.

## What this test does not show

- **Motion.** A static scene is the easiest case: accumulation over frames hides the model's
  errors, and the model's real work is motion and disocclusion. That 50% scores no worse than 30%
  shows the test is not sensitive enough to rank heavy pruning. The [motion test](#motion-test)
  below was added afterwards for this; the pruning sweep above has not been rerun with it.
- **Other content.** One image.
- **Retraining.** Pruned networks are normally retrained to recover quality. That needs AMD's
  training data and setup.

## Motion test

Added 2026-10-05, to measure what the still scene cannot: stability in motion.

- **Scene** (`motion_scene.py`): the screenshot, mirror-padded, pans by 4 x 2 output pixels per
  frame. In front of it two objects move the other way, by -5 x 3 pixels per frame: a solid block
  (one half texture, one half 2-pixel diagonal stripes) and a railing of 3-pixel bars 24 pixels
  apart with see-through gaps. Every speed is a whole number of output pixels, so a point of the
  scene falls on a pixel centre in every frame and frames can be compared exactly.
- **Inputs** (`gen_motion.py`): per frame, jittered colour at 2260x1272, motion vectors (from each
  pixel to where it was in the previous frame, in render pixels), depth (background 0.9, objects
  0.3) and jitter; and the true 4K image of the last frames.
- **Run** (`fsr4img.c` with `FSR_IMG_DIR` and `FSR_KEEP=8`): 40 frames through AMD's DLL, the last
  8 output frames kept.
- **Figures** (`metric_motion.py`): PSNR against the true image per region (background, block
  texture, stripes, railing, pixels uncovered in the last four frames), and **frame-to-frame
  change**: the mean absolute difference, in 8-bit steps, between a scene point in one output frame
  and the same point in the next. A perfect upscaler scores 0; more means flicker or shimmer.

Checks: with the motion vectors' sign flipped the background drops from 49.3 dB to 43.5 dB and its
frame-to-frame change rises from 0.08 to 0.33, so the convention is right; and this repository's
shipped shaders give exactly AMD's frames in this scene too.

AMD's shaders in this scene:

| Region | PSNR against the true image | Frame-to-frame change |
|---|---|---|
| Background | 49.3 dB | 0.079 |
| Block, texture half | 43.1 dB | 0.106 |
| Block, fine stripes | 15.6 dB | 2.04 |
| Railing (bars and gaps) | 41.8 dB | 0.913 (bars) |
| Just uncovered | 34.5 dB | |

The stripes are deliberately beyond what any upscaler resolves at this ratio. The first use of the
test is in [a community lossy shader set](../community-lossy-set): it showed a loss of stability
that the still scene and the average error both miss.

    python3 gen_motion.py img/truth.npy imgm 40 8
    FSR_IMG_DIR=imgm FSR_KEEP=8 FSR_CTX_FLAGS=0x0 FSR_DISP_FLAGS=0 umu-run fsr4img.exe 4.1.1 2260x1272 3840x2160 40 image
    python3 metric_motion.py imgm <folder with the output frames> [<folder with reference frames>]

Other output sizes: set `SCENE="<output width> <output height> <render width> <render height>"`
for all four scripts (for example `SCENE="2560 1440 1506 847"`) and pass the same sizes to the
test program. The picture is resized and the scene's objects are scaled with it, so a lower
output size has finer detail per pixel, as in a game. Without `SCENE` everything is as above.

## Files

| File | What it is |
|---|---|
| `wprune.py` | zeroes a fraction of a model pass's weight words (`spirv-dis` text in and out) |
| `gen_inputs.py` | jittered render-resolution frames and `jitter.txt` from a 4K image; jitter signs `-1 -1` match FSR's convention (44.1 dB against the image; the other three sign pairs give 37.8 to 40.3 dB) |
| `fsr4img.c` | the test program: feeds those frames to AMD's DLL and writes the output image (the last N frames with `FSR_KEEP=N`) |
| `metric.py` | PSNR and pixel-error statistics between two outputs, or an output and the ground truth |
| `motion_scene.py`, `gen_motion.py` | the moving scene and its inputs (colour, motion vectors, depth, jitter, true frames) |
| `metric_motion.py` | per-region error and frame-to-frame change for the moving scene |
