# Shader variants: what is covered and what is not

[Back to the front page](../README.md)

AMD's FSR 4.1.1 DLL does not contain one postpass, but many versions of it. Which one a game
gets depends on how the game sets FSR 4 up. The replacements in this repository match exact
shaders, so **a game that uses a version without a replacement keeps AMD's original shader for
that pass and gets no speedup from it**. Nothing breaks; it just is not faster.

## What AMD's DLL contains (version 4.1.1.2740)

Counted from the DLL itself, for the INT8 version of FSR 4 that runs on RX 7000 cards:

| Shader | Versions in the DLL | Replacements shipped | The rewrite applies to |
|---|---|---|---|
| Postpass, normal | 48 | 48 | all 48 |
| Postpass, with FSR's debug view | 48 | 0 | none (the debug view writes an extra image) |
| Model pass 11 | 6 | 6 | all 6 |

The DLL also holds 24 postpass and 3 pass 11 versions for the FP8 model (RX 9000 cards), which
this repository does not touch; see [RDNA4](rdna4.md).

All INT8 postpass versions use thread groups of 256x1x1. The 32x1x1 groups in the DLL belong to
the FP8 versions.

## What selects a version

Found by running AMD's DLL with each option:

| Choice | Values | Postpass versions | Pass 11 versions |
|---|---|---|---|
| Output size | up to 1080p; above 1080p up to 4K; above 4K | 3 | 3 |
| Model | Ultra Performance; every other preset | 2 | 2 |
| Exposure and color space, as the game sets FSR up | 8 combinations, below | 8 | 1 |
| | | 48 | 6 |

The 8 combinations: automatic exposure on or off, each with the input color declared as linear,
as non-linear without saying which, as sRGB, or as PQ. High dynamic range, the motion-vector and
depth options, dynamic resolution, sharpening and native-resolution anti-aliasing do not change
which postpass or pass 11 runs.

## What this means for you

- **Patched DLL and ReShade add-on (since 2026-10-04):** every normal version is covered, so the
  speedup no longer depends on how the game sets FSR up. Only FSR's debug view falls back to
  AMD's postpass.
- **The prepass (since 2026-10-05):** 90 versions, 30 for each output-size class. Which one a game
  uses depends on five context options (display-resolution motion vectors, jitter cancellation,
  inverted depth, auto exposure, non-linear color space) and the color-space dispatch flags. The
  DLL replaces all 90 and `prebuilt/` has all 90 (collected by running FSR 4 in every combination
  of those options at the three size classes). `build_override.sh` rewrites the one in your dump.
- **The other model passes (since 2026-10-05):** two more exact rewrites apply to model passes
  other than 11. Those passes come in up to six versions each (three output-size classes, two
  models), independent of the option sets. `prebuilt/` has 45 such files and the DLL replaces 39
  (the DLL-format rewrite covers passes 1, 2, 4, 5, 9, 10 and 12; the Linux one 1, 2, 4, 5, 7, 8,
  9, 10 and 12).
- **Linux launch option (since 2026-10-04):** `prebuilt/` has all 54 as well. They were made by
  running AMD's unmodified DLL under Proton in each of the 48 combinations with shader dumping on,
  which gives Proton's own translation of every version, and building the overrides from those
  dumps. Checked the same way: byte-identical output in all 48
  ([`../dll/test/run_all_variants_linux.sh`](../dll/test/run_all_variants_linux.sh)). The three
  files shipped before came out identical this way.

## How the full set was verified

The rewrite was run on the DLL's own copies of all 54 shaders (48 postpass, 6 pass 11). A test
program then ran AMD's DLL and the patched one in each of the 48 combinations that select a
different version (3 output sizes x 2 models x 8 setups), with a shader dump to confirm which
versions ran. In all 48 the output was byte-for-byte identical to AMD's, both shaders were
replaced, and every one of the 54 was exercised at least once.

Thanks to the commenter on Discord who pointed out that the DLL has far more postpass versions
than were covered.
