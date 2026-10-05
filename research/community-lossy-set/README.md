# Testing a community shader set that trades image quality for speed

[Back to the research index](../README.md)

## TL;DR

- A community member's shader set for RDNA2 replaces **all fourteen main passes** of FSR 4.1.1;
  this repository replaces two. Most of its extra speed comes from **removing part of the model's
  weights, which changes the image**.
- **Speed on an RX 7800 XT:** its twelve model passes take 2.03 ms, the same as this repository's
  set (2.04 ms; AMD's take 2.42 ms). Combined with this repository's pass 11 they would take
  1.70 ms, 0.34 ms less than what is shipped (about 0.4 ms with its pruned postpass as well).
- **Quality at rest:** a small loss, 0.7 dB against the true image.
- **Quality in motion:** less stable than AMD's shaders. Frame-to-frame change is 75% higher on
  the background and 20 to 25% higher on thin detail. This repository's shaders stay identical to
  AMD's, frame for frame.
- **Its bit-exact parts gain nothing on RDNA3.** They may on RDNA2, which could not be measured
  here.
- **Outcome:** nothing from it goes into the main files. The lossy direction is worth pursuing as
  an opt-in extra, but that needs the set's source and per-pass tuning against the motion test;
  see [what would help](#what-would-help-to-take-this-further).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/what-is-replaced-dark.svg">
  <img src="img/what-is-replaced-light.svg" width="760" alt="Diagram of FSR 4.1.1's fourteen main passes (prepass, model passes 1 to 12, postpass) for two shader sets. This repository rewrites model pass 11 and the postpass with unchanged output and leaves the rest as AMD's. The community set replaces all fourteen: passes 3 and 6 with unchanged output; passes 7, 8, 9 and 11 with a changed rounding rule; passes 1, 2, 4, 5, 10, 12 and the postpass with weights removed; the prepass was not measured.">
</picture>

For the community set's postpass, the diagram shows the version that writes exposure, which has
weights removed; its other postpass file only removes branches and gives unchanged output.

## Background

On 2026-10-05 a community member, VALKKKS, shared a fork of this project aimed at RDNA2 under
Linux: a write-up ("v45") and a zip of override files ("v42-b", 17 `.spv` files). Their write-up
reports FSR 4.1.1 going from 3.13 ms to 2.34 ms on a Radeon RX 6700M at 2560x1440. The fork is
not online at the time of writing, so this page records what was tested here, from the files
alone. **None of those files are in this repository,** and nothing from this page is shipped. The figures
are made by [`img/make_figures.py`](img/make_figures.py).

The set replaces the prepass, all twelve model passes and the postpass (this repository replaces
the postpass and model pass 11). It mixes two kinds of change:

- **Bit-exact rewrites:** the always-zero z coordinate folded on every pass, loops unrolled where
  the result stays small, the postpass's nine neighbourhood reads done without branches, and
  integer forms of the rounding code.
- **Changes to the result:** weights removed from six model passes and from the postpass (each
  removed weight is added to a neighbouring one, so sums are preserved), and rounding half up
  instead of half to even.

## Speed and exactness, pass by pass

Radeon RX 7800 XT, standalone benchmark at 4K output, 500 dispatches per pass, the model's real
weights loaded. "Differs" counts output bytes that are not AMD's; it says how widespread the change
is, not how large.

| Pass | AMD | Community set | Output |
|---|---|---|---|
| 1 | 0.292 ms | 0.241 ms | differs (69% of bytes) |
| 2 | 0.292 ms | 0.243 ms | differs (88%) |
| 3 | 0.051 ms | 0.051 ms | identical |
| 4 | 0.140 ms | 0.102 ms | differs (92%) |
| 5 | 0.140 ms | 0.111 ms | differs (89%) |
| 6 | 0.049 ms | 0.045 ms | identical |
| 7 | 0.116 ms | 0.110 ms | differs (3%) |
| 8 | 0.116 ms | 0.109 ms | differs (2%) |
| 9 | 0.177 ms | 0.174 ms | differs (4%) |
| 10 | 0.139 ms | 0.107 ms | differs (85%) |
| 11 | 0.615 ms | 0.565 ms | differs (3%) |
| 12 | 0.293 ms | 0.174 ms | differs (96%) |
| All twelve | 2.42 ms | 2.03 ms | |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/model-pass-time-dark.svg">
  <img src="img/model-pass-time-light.svg" width="760" alt="Bar chart of the time of the twelve model passes at 4K on a Radeon RX 7800 XT: AMD's shaders 2.42 ms; this repository 2.04 ms with unchanged output; community set 2.03 ms with changed output; community set with this repository's pass 11 1.70 ms with changed output.">
</picture>

- Only passes 3 and 6 are bit-exact, and together they save 0.004 ms on this card.
- The small differences (passes 7, 8, 9, 11) are the rounding change; the large ones are the
  removed weights.
- Their pass 11 takes 0.565 ms here; this repository's takes 0.23 ms and is exact. With AMD's other
  eleven passes and this repository's pass 11 the total is 2.04 ms, so on an RX 7800 XT the whole
  community set lands where the shipped files already are.
- Their pruned passes with this repository's pass 11 would total about 1.70 ms.

Postpass, 4K:

| File | Community set | This repository | Output |
|---|---|---|---|
| Basic version (`683038df6272d4db`), branches removed | 0.622 ms | 0.601 ms | identical |
| Exposure-writing version (`4d657fb0eed077d6`), weights removed | 0.603 ms | 0.691 ms | differs (about half the pixels) |

Both are built on this repository's phased postpass. The branch removal was also rebuilt here from
the write-up ([`postpass_taps.py`](../postpass-and-prepass/postpass_taps.py)): bit-exact over a
full 4K frame, and 3% slower on the RX 7800 XT (0.617 to 0.622 ms against 0.600 ms). The write-up
reports it 10% faster on the RX 6700M (581 to 525 microseconds at 1440p), so it may be worth having
on RDNA2; that has not been measured here.

Not tested: the prepass file (it is for a prepass version the benchmark here is not set up for) and
the border shaders, which are in the write-up but not in the zip.

## Image quality: still scene

The rig of [`../pruning`](../pruning): 32 frames, Balanced to 4K, no motion, sharpening off, PSNR in
sRGB.

| Shader set | Against AMD's output | Against the true image | Largest pixel error (of 255) |
|---|---|---|---|
| AMD's | | 44.31 dB | |
| This repository's | identical | 44.31 dB | 0 |
| Community set, all files | 56.1 dB | 43.62 dB | 64 |
| Same, with this repository's pass 11 | 56.1 dB | 43.61 dB | 72 |
| Only the six pruned model passes | 55.7 dB | 43.54 dB | 71 |
| Only the pruned postpass | 61.7 dB | 44.19 dB | 41 |
| Only the passes with the rounding change (7, 8, 9, 11) | 67.8 dB | 44.31 dB | 22 |

At rest the set loses about 0.7 dB against the true image, nearly all of it from the pruned model
passes. Compared with the plain pruning tried in [`../pruning`](../pruning) (10% of weights: 0.07 ms
for 0.47 dB), folding the removed weights into their neighbours buys about five times the time for
similar damage.

## Image quality: motion

The moving scene described in [`../pruning`](../pruning#motion-test): a panning background, a
moving block with fine stripes, and a moving railing of 3-pixel bars. "Change" is how much a point
of the scene changes between two consecutive output frames, in 8-bit steps; 0 would be perfectly
stable, and more means shimmer.

| Shader set | Against AMD's frames | Change: background | Change: railing bars | Change: fine stripes |
|---|---|---|---|---|
| AMD's | | 0.079 | 0.913 | 2.04 |
| This repository's | identical | 0.079 | 0.913 | 2.04 |
| Community set, all files | 45.3 dB | 0.138 | 1.140 | 2.47 |
| Same, with this repository's pass 11 | 45.3 dB | 0.137 | 1.144 | 2.47 |
| Only the six pruned model passes | 46.1 dB | 0.072 | 1.068 | 2.43 |
| Only the pruned postpass | 50.2 dB | 0.201 | 1.028 | 1.94 |
| Only the passes with the rounding change | 55.9 dB | 0.080 | 0.915 | 2.04 |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/motion-stability-dark.svg">
  <img src="img/motion-stability-light.svg" width="760" alt="Bar chart of frame-to-frame change in the moving test scene with the community set, relative to AMD's shaders at 100%: background 175% (0.079 to 0.138), railing bars 125% (0.913 to 1.14), fine stripes 121% (2.04 to 2.47). This repository's shaders equal AMD's.">
</picture>

- In motion the set is much further from AMD's output than at rest (45 dB against 56 dB).
- It is less stable: about 75% more frame-to-frame change on the background and 20 to 25% more on
  the railing and the stripes.
- The two pruned parts fail differently. The pruned model passes hurt thin detail and leave the
  background alone; the pruned postpass is what makes the background unstable (2.5 times AMD's
  figure on its own).
- The rounding change is harmless here.
- The error against the true image hardly moves (whole frame 30.5 to 30.2 dB), so an average
  quality figure would not have shown any of this.

This is one synthetic scene at one speed. It ranks shader sets; it does not say how visible the
difference is in a particular game.

## Where this stands

- **Nothing here goes into the main files.** They keep AMD's image byte for byte; the exact parts
  of the community set do not gain on RDNA3, and the rest changes the image.
- **The lossy direction is real, though.** About 0.4 ms on an RX 7800 XT (roughly 13% of the
  upscaler time that is left) for a loss that is small at rest and measurable in motion.

## What would help to take this further

1. **The source.** Only compiled files were shared. The scripts that fold the weights and choose
   which to remove are what could be reviewed, measured per pass and maintained; they are also
   needed to cover the other 47 postpass versions and the Windows DLL. This repository's scripts
   are GPL, and work derived from them is welcome back under the same terms.
2. **Exact and lossy changes as separate files.** With every pass carrying both, the exact gains
   cannot be measured on their own. An exact-only build of each pass would show what is free.
3. **Per-pass limits set by measurement.** The limits were chosen by eye in one game. The motion
   test gives a number to tune against: raise the removed fraction of one pass at a time and keep
   it while the frame-to-frame change stays within a chosen margin of AMD's. On the figures above,
   the postpass pruning is the first thing to drop.
4. **More scenes, and real ones.** One synthetic scene is thin evidence. The best input would be
   frames captured from a game (colour, motion vectors, depth, jitter), which the test program
   could replay.
5. **Numbers from RDNA2.** Everything here was timed on an RX 7800 XT, where the store rewrites
   already take most of the available gain. The set was made for RDNA2: per-pass timings there,
   exact changes separate from lossy ones, are what would show whether an RDNA2-specific build of
   the exact parts (branch removal, size-limited unrolling) is worth shipping.
6. **A clear label if it is ever offered.** A lossy set would have to be opt-in, in its own
   folder, and visibly different, for example through its own version name in the DLL
   (`dll/patch_upscaler_dll.py --name`), so that nobody takes it for the exact one.
