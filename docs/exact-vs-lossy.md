# Exact and lossy builds: how they differ

[Back to the README](../README.md)

This project ships two kinds of faster FSR 4.1.1 shaders. They get their speed in different ways,
and only one of them keeps AMD's picture.

- **The exact files** (the main DLL, the prebuilt Linux folder and the test builds for other
  GPUs) do the same arithmetic as AMD's shaders, organised so the GPU gets through it faster.
  The output is AMD's image, byte for byte.
- **The lossy test builds** (`test-lossy…`) start from the exact files and then do less work:
  they leave out part of the model's arithmetic and run the model on every other frame.

> **The lossy builds change the image.** They are opt-in experiments, not the same as the main
> files and not the same as AMD's DLL.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/exact-vs-lossy-dark.svg">
  <img src="img/exact-vs-lossy-light.svg" width="760" alt="How the exact files and the lossy test builds differ from AMD's FSR 4.1.1 shaders, pass by pass. AMD's shaders: all fourteen passes unchanged, 4.16 ms per frame. Exact files: twelve passes rewritten with the same output (model passes 3 and 6 untouched), 3.05 ms, the image is AMD's byte for byte. Lossy build on a frame that runs the model: nine model passes change the output (weights folded in passes 1, 5, 10 and 12, simpler rounding in those and in 2, 4, 7, 8 and 9), about 2.9 ms. Lossy build on a skipped frame: all twelve model passes are skipped and the prepass and postpass show mostly the reprojected history, with three repairs, 1.32 ms. The two kinds of frame alternate, 2.11 ms on average, 49% less than AMD's. Cost of the lossy build in a test scene at 4K Balanced: still picture 43.74 dB against 44.31, flicker on fine detail at rest 0.119 against 0.110 (8% more), areas just uncovered by a moving object 32.04 dB against 34.48. Shadow of the Tomb Raider, 4K Balanced, Radeon RX 7800 XT.">
</picture>

The figure is made by [`img/make_exact_vs_lossy.py`](img/make_exact_vs_lossy.py).

## At a glance

| | Exact files | Lossy test builds |
|---|---|---|
| Image | AMD's, byte for byte | close to AMD's, not the same |
| How the time is saved | same work, done more efficiently | less work |
| Upscaler time, Shadow of the Tomb Raider, 4K Balanced (AMD's: 4.16 ms) | 3.05 ms | 2.11 ms |
| Upscaler time, Rise of the Tomb Raider, 4K Balanced (AMD's: 4.29 ms) | 2.97 ms | 2.05 ms |
| Frame times | even | alternate between a shorter and a longer frame |
| Checked how | output compared with AMD's, byte for byte | measured against the true image and against AMD's output |
| Tested on | several GPUs and games ([results](results.md)) | one GPU and two games by the author, one tester on RDNA2 |
| Files | main DLL, `prebuilt/`, `test-rdna2…`, `test-igpu.zip` | `test-lossy…` only |

All timings on this page are from a Radeon RX 7800 XT on Linux.

## How the exact files get faster

Nothing is removed. Each rewrite computes exactly the values AMD's shader computes and changes
only how the work is laid out for the GPU.

| Part of FSR 4 | What changes | Why it is faster |
|---|---|---|
| Postpass | each thread's pixels are collected and written out in contiguous blocks, one image at a time | AMD's version writes single pixels scattered over three images, which is slow on these GPUs |
| Model pass 11 | constants made visible to the compiler; each row's results stored together | fewer registers per thread, so more threads run at once; far fewer separate writes |
| Other model passes | the final scaling and clamping done in integers where that gives the same result | fewer instructions per thread |
| Prepass | each thread gathers its neighbours' values once and reuses them | fewer exchanges between threads |

Every rewrite is verified by running the whole upscaler and comparing its output with AMD's, byte
for byte, across output sizes, presets and option combinations. A rewrite that differs in a
single byte is not shipped as exact. Details: [how it works](how-it-works.md).

The limit of this approach is the model itself. Its twelve passes are about 60% of FSR 4's time
and are almost pure arithmetic, already running near what the hardware can do. With the work
unchanged there is little left to gain there.

## How the lossy builds get faster

They contain everything the exact files do, plus two changes that give up exactness.

### 1. Less arithmetic in the model (weight folding)

Six of the model passes carry their weights as constants. In each, an output value is a sum of 36
small dot products. The lossy build drops the ones with the smallest weights and adds their
weights to a neighbouring one that is kept, so the sum changes little. It also simplifies how
intermediate values are rounded.

- **How much is dropped** was tuned pass by pass against a moving test scene: 4 of 36 in pass 1,
  18 in passes 5 and 10, 20 in pass 12. One step further in any of them made something visibly
  less steady, and pass 2 tolerates none.
- **What it saves:** about 0.14 ms (3.05 to 2.91 ms).
- **What it costs:** the still picture is about 0.6 dB less accurate, and fine repeating patterns
  can be less steady in motion, most at 1440p output.

Details: [the lossy track](../research/lossy).

### 2. The model runs on every other frame (frame skip)

On alternate frames the twelve model passes return immediately, and the postpass reuses the
model's result from the frame before, which is still in memory.

- **What it saves:** about 0.8 ms on average (2.91 to 2.09 ms). A skipped frame takes about
  1.3 ms, a normal one about 2.9 ms.
- **What it costs:** the reused result is one frame old. That shows in three ways, described
  below, two of which needed a repair.

Details: [frame skip](../research/frame-skip).

### What a skipped frame does instead, and three repairs

All of this acts on skipped frames only. Frames that run the model are not touched.

A skipped frame leans on the history: it shows the previous picture moved along with the scene,
and takes very little from the new frame (the new frame's weight is squared, so a typical 7%
becomes about 0.5%), except where the model had asked for the new frame. Three repairs keep that
honest:

| Problem with a reused result | Repair in the builds |
|---|---|
| **Shimmer on fine detail.** The reused result was worked out for the previous frame's camera jitter, so it gives too much weight to the new frame in pixels whose nearest sample has moved away. | The previous jitter is carried over to the skipped frame, and the new frame's weight is lowered where its nearest sample is now farther from the pixel. About half of the extra flicker goes. |
| **A dark band at the screen edge** for one frame when the camera starts to turn. The strip that scrolls in has no history, and the reused result still says "mostly history". | Where the history is far darker than the new frame, the new frame is used alone. The band is gone in the test scene. |
| **A smear behind moving objects.** Where something has just been uncovered, the reused result keeps a history that is out of date. | The history is limited to the colour range of the new frame's samples around the pixel. Most of the loss there goes. |

## What the lossy builds cost, measured

Test scene at 4K Balanced. "Lossy" is the release build: folding, frame skip and the three repairs.

| | AMD's (= exact files) | Folding only | Lossy |
|---|---|---|---|
| Still picture against the true image | 44.31 dB | 43.71 dB | 43.74 dB |
| Flicker at rest on fine detail (lower is steadier) | 0.110 | 0.123 | 0.119 |
| Moving scene: background | 49.27 dB | 48.67 dB | 47.68 dB |
| Moving scene: areas a moving object has just uncovered | 34.48 dB | 34.89 dB | 32.04 dB |
| Revealed strip when a pan starts on a skipped frame | 100% of true brightness | no frame skip | 100% |

- **Fine detail shimmers about 8% more than with AMD's shaders** at rest (0.119 against 0.110).
  It was about 55% with the first frame-skip build and about 30% up to release 4.
- **The still picture is about 0.6 dB less accurate,** the same as with folding alone.
- **Just-uncovered areas are about 2.5 dB less accurate** in this scene: the edge behind a moving
  object is one frame behind. Before the history clamp it was about 5 dB.
- **Frame times alternate.** With a frame cap or normal V-Sync the average is what counts. With
  low-latency modes or unbuffered V-Sync the longer frames can miss.

## Speed side by side

| Benchmark, 4K Balanced, RX 7800 XT | AMD's shaders | Exact files | Lossy |
|---|---|---|---|
| Shadow of the Tomb Raider: upscaler time | 4.16 ms | 3.05 ms (−27%) | 2.11 ms (−49%) |
| Shadow of the Tomb Raider: average FPS | 97 | 109 | 122 |
| Rise of the Tomb Raider: upscaler time | 4.29 ms | 2.97 ms (−31%) | 2.05 ms (−52%) |
| Rise of the Tomb Raider: overall score | 97.67 FPS | 109.61 FPS | 122.34 FPS |

On RDNA2 at 1440p output, one tester measured only 1 to 2% from the folding alone; frame skip
has not been timed there.

## Limits of the lossy builds

- **Frame skip depends on the game's camera jitter.** With the usual sequence, frames alternate
  strictly. A game with an unusual sequence may skip unevenly, and a game that passes no jitter
  never skips.
- **Frame skip is off in Ultra Performance** and on frames the game marks as a reset. In Ultra
  Performance the lossy build does very little: that model's own passes are left exact.
- **Frame skip costs more at low real frame rates.** In the moving test scene at a fixed
  on-screen speed, just-uncovered areas are level with AMD's at 120 FPS, about 1 dB below at 60
  and about 5 dB below at 30, and thin structures 1.5 to 2.9 dB below
  ([by frame rate](../research/frame-skip#by-frame-rate)). The shimmer also
  alternates at half the real frame rate, so it is slower and easier to see (that part is
  reasoning, not a measurement). With frame generation on top of a low base rate, the exact
  build is the safer choice.
- **Little testing.** Two games on one RDNA3 card by the author, and one tester on RDNA2. The
  repairs were verified in a test rig; the edge-band fix has not been confirmed in the game it
  was reported in.

## Which to use

- **Use the exact files** if you want AMD's picture, if you use frame generation at a low base
  frame rate, or if you are unsure. They are the main files of this project.
- **Try a lossy build** if you run at a high real frame rate, want the extra speed, and accept
  a picture that is not AMD's. Look at distant fine detail while standing still and at the edges
  of moving objects; if either bothers you, go back to the exact build.

## Where to read more

- [How the exact rewrites work](how-it-works.md) and [all results](results.md)
- [The lossy track](../research/lossy): folding, rounding, what was tried and rejected
- [Frame skip](../research/frame-skip): the mechanism, the shimmer correction and the edge guard
- [GPU support](gpu-support.md): which build is for which GPU
