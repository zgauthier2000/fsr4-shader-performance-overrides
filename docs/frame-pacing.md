# Lossy builds: what alternating frame times mean in practice

[Back to the README](../README.md) · [Exact and lossy builds compared](exact-vs-lossy.md)

The lossy DLL runs FSR 4's model, a small neural network, on every other frame. So the upscaler does not take the
same time every frame: it alternates between a long frame and a short one. This page is about
what that does to frame pacing, frame caps, V-Sync, latency and the numbers an overlay shows.

It applies to the lossy DLL (the `lossy` folder of each download) only. The exact files take the same time every frame.

The figures are for release `dll-2026-10-29`'s lossy DLL. FSR 4's times are measured in this project's test rig; what they mean for
whole frames is worked out from them and marked as derived. Before this release the page used Shadow of the Tomb Raider figures of
earlier builds (1.7 ms apart); they are in this file's history. The release's Lite build `4.1.2l-lossy` alternates the same way, with
smaller times (about 2.1 and 1.3 ms at 4K on the same card).

## In short

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/explain-skip-dark.svg">
  <img src="img/explain-skip-light.svg" width="760" alt="How the lossy DLL saves time. AMD's shaders and the exact DLL run FSR 4's neural network on every frame. The lossy DLL runs it on every other frame and reuses the last result on the frames in between: about 3.2 ms on a frame that runs the network and about 1.3 ms on one that skips it, at 4K on a Radeon RX 7800 XT (Linux).">
</picture>

**In plain words:** with the lossy DLL every second frame is cheaper than the one before it. If your frame rate is free to
vary, you simply get the average, and it is higher. If something forces every frame to fit a fixed slot (V-Sync without a
frame queue, some low-latency modes), the expensive frames are the ones that have to fit.

- **Uncapped, the average is what you get.** FPS counters, benchmarks and the gain over the exact
  files are all about the average, and that is real.
- **With a fixed refresh and no frame queue, plan for the long frame, not the average.** A frame
  rate the average reaches can still miss every other refresh.
- **The size of the swing is fixed in milliseconds,** about 2.0 ms on an RX 7800 XT at 4K. It is
  a small share of a frame at 60 FPS and a large one at 240.
- **Almost none of this page is measured frame by frame.** The two upscaler times and the
  averages are measured; the consequences are worked out from them and marked as such.

## The numbers it starts from

FSR 4's time per frame, 4K Balanced, moving scene, Radeon RX 7800 XT under Linux, this project's test rig (one run):

| | FSR 4 time per frame |
|---|---|
| AMD's FSR 4.1.1 file | 4.83 ms every frame |
| Exact | 3.14 ms every frame |
| Lossy, a frame that runs the model | 3.22 ms |
| Lossy, a skipped frame | 1.25 ms |
| Lossy, average | 2.24 ms |

To turn that into whole frames this page takes a real game: in Shadow of the Tomb Raider's benchmark (4K Balanced, the same card, earlier
builds) the rest of a frame, everything that is not FSR 4, is about 6.15 ms with every build. So a lossy frame is about 9.37 ms when the
model runs and 7.40 ms when it is skipped: **2.0 ms apart, 8.39 ms on average (119 FPS)**, against 9.29 ms (108 FPS) for every exact frame.
Those whole-frame figures are derived, not captured; this release's builds have not been run through that benchmark yet.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/frame-pacing-dark.svg">
  <img src="img/frame-pacing-light.svg" width="760" alt="Frame time of eight consecutive frames, in milliseconds, against a frame cap of 116 FPS, 8.62 ms per frame. Exact files: every frame takes 9.29 ms, above the interval. Lossy build: frames alternate between 9.37 ms when the model runs and 7.40 ms when it is skipped; the average, 8.39 ms, is below the cap's frame time, but every other frame is above it. Derived: the rest of a frame from Shadow of the Tomb Raider at 4K Balanced on a Radeon RX 7800 XT, FSR 4's times from the test rig on the same card.">
</picture>

The figure is made by [`img/make_frame_pacing.py`](img/make_frame_pacing.py).

## How big the swing is at different frame rates

The 2.0 ms does not shrink when the frame rate goes up, because it is the model's time and
nothing else. As a share of the frame it grows:

| Average frame rate | Frame time | Each frame is off the average by |
|---|---|---|
| 30 FPS | 33.3 ms | 3.0% |
| 60 FPS | 16.7 ms | 6% |
| 90 FPS | 11.1 ms | 9% |
| 120 FPS | 8.3 ms | 12% |
| 144 FPS | 6.9 ms | 14% |
| 240 FPS | 4.2 ms | 24% |

This is arithmetic on the 2.0 ms measured on an RX 7800 XT at 4K Balanced. Two things change it:

- **A slower GPU or a larger output makes it bigger.** The swing is the time of the twelve model
  passes, about 60% of the exact files' upscaler time on that card. Where FSR 4 takes twice as
  long, expect about twice the swing. Not measured on other cards.
- **A smaller output makes it smaller,** for the same reason.

## What it means, case by case

**Uncapped, GPU-bound, variable refresh (VRR).** Each frame is shown for as long as it took, so
the display alternates between a slightly longer and a slightly shorter frame. The pattern
repeats every two frames, which is 60 times a second at 120 FPS. Whether that is visible has not
been tested here.

**Uncapped, fixed refresh, no V-Sync.** Tearing as usual. The tear line moves in a two-frame
pattern instead of drifting evenly. Not tested.

**A frame cap below what the long frame can do.** Nothing alternates on screen: both kinds of
frame finish in time and the limiter spaces them evenly. The GPU simply idles a little longer
after a skipped frame. In the example above, a cap of 106 FPS or lower is in this case.

**A frame cap, or V-Sync, between the long frame's rate and the average.** This is the case to
understand. In the example the average is 119 FPS, but a frame that runs the model takes
9.37 ms, which is 107 FPS. The chart above shows a cap of 116 FPS, a common setting on a 120 Hz display with
variable refresh.

- **With a frame queue** (V-Sync with normal buffering, most limiters), a short frame finishes
  early and the next, long one starts early and uses the slack. Two frames take 16.8 ms and two
  slots of the 116 FPS cap are 17.2 ms, so 116 FPS holds. The average is what counts.
- **Without a queue** (low-latency modes that start each frame as late as possible, V-Sync with
  no pre-rendered frames), every frame has to make its own slot. The long frames miss by
  0.8 ms and the short ones do not. The result is a missed slot on every other frame, which
  looks worse than a steady lower rate.

**What to do in that case:** cap at or below the long frame's rate (106 FPS in the example),
allow one queued frame, or use the exact files, which need 108 FPS worth of time on every frame
and never alternate.

**A frame cap you cannot reach on average.** The same as with any build: you are GPU-bound, see
the uncapped case.

## What it does to the numbers you read

- **Average FPS and average frame time** are right, and are what the benchmarks on this project
  report.
- **The upscaler time in OptiScaler's overlay flips** between about 1.3 and 3.2 ms from frame to
  frame (4K on an RX 7800 XT); its average sits in between. A reading taken on a still screen, such as a benchmark's
  result page, is not typical of a scene in motion.
- **A frame-time graph shows a fine sawtooth.** That is this alternation, not stutter from
  somewhere else.
- **Lows rose with the average in the one benchmark measured,** with the builds of an earlier release. Shadow of the Tomb Raider reports
  a GPU minimum of 106 FPS and a 95th percentile of 112 with the lossy build (average 127),
  against 96 and 101 with the exact files (average 114). A tool that takes "1% low" from single
  frame times will count the long frames, so expect lows to improve less than the average
  there. That has not been measured.

## Latency

A skipped frame reaches the screen about 2.0 ms sooner after it was started than a frame that
runs the model. So input lag alternates by that much, and averages about 0.9 ms less than with
the exact files. Both are small next to a whole frame, and neither has been measured.

## Frame generation

Not tested. Two things follow from how it works:

- Generated frames are placed between real ones on the assumption that real frames are evenly
  spaced. Here they are not quite, by the percentages in the table above for the **base** frame
  rate.
- Frame skip costs more image quality at a low real frame rate (see
  [the comparison page](exact-vs-lossy.md#limits-of-the-lossy-builds)), and frame generation is
  mostly used on top of a low base rate.

With frame generation on a base rate under about 60 FPS, the exact files are the safer choice.

## Power and heat

With a frame cap, the lossy build does less work per second than the exact files: half the frames
skip about 60% of FSR 4. That should show as lower GPU load at the same frame rate. Not measured.

## When frames do not alternate

- **Ultra Performance (since `dll-2026-10-15`; Ultra Performance only):** frame skip works there too, but one in three of the
  frames that would skip runs the model all the same, so the network runs on about two frames in three instead of every other one.
  A long frame can then follow another long frame. (Before `dll-2026-10-15` frame skip was off there.)
- **Frames the game marks as a reset** (a camera cut) always run the model.
- **Games with an unusual camera jitter sequence** may skip unevenly, because the build picks
  frames by the sign of the jitter. A game that passes no jitter never skips, and then the lossy
  build is only slightly faster than the exact files.

## Why it cannot be evened out

The obvious idea is to spread the model over two frames, half each. It does not work: the
model's input and its output share the same memory, so a frame cannot start a new run and still
have the last result to show. The time of a frame is either all of the model or none of it.

## Short version of the advice

- **Uncapped or VRR at a high frame rate:** use the lossy build if you accept its picture; the
  alternation is small.
- **V-Sync or a cap with low-latency settings:** set the cap for the long frame, or allow one
  queued frame.
- **Low base frame rate, with or without frame generation:** use the exact files.
- **If you see a regular fine stutter that the exact files do not have:** this is the likely
  cause. Lower the cap a little or switch to the exact files.
