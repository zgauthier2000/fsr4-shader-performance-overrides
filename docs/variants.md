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
| Postpass, normal | 48 | 6 | all 48 |
| Postpass, with FSR's debug view | 48 | 0 | none (the debug view writes an extra image) |
| Model pass 11 | 6 | 4 | all 6 |

The DLL also holds 24 postpass and 3 pass 11 versions for the FP8 model (RX 9000 cards), which
this repository does not touch; see [RDNA4](rdna4.md).

All INT8 postpass versions use thread groups of 256x1x1. The 32x1x1 groups in the DLL belong to
the FP8 versions.

## Why only some are shipped

The shipped replacements are the versions that turned up in practice: in the test program used
to check the output, and in the games measured for this repository. The 48 normal versions look
like 2 output-size classes (above 1080p, and 1080p or below) x 2 models (Ultra Performance, and
all other presets) x 12 combinations of how the game hands FSR its colour and exposure.

## What this means for you

- **Linux launch option:** if the upscaler time does not drop, your game uses a version that is
  not in `prebuilt/`. Build your own files from a dump of that game
  ([Linux guide](linux.md#building-your-own)); the scripts handle any normal version.
- **Patched DLL and ReShade add-on:** same symptom, no speedup for the postpass. Building the
  replacement for your game's version is described in the
  [Windows page](../windows/README.md#if-your-games-variant-is-not-prebuilt).

## Work in progress

Running the rewrite directly on the DLL's own copies of all 54 normal shaders (48 postpass, 6
pass 11) works: every one builds and passes Microsoft's validator, and the 10 already shipped
come out byte for byte the same that way. What is missing is proof that the other 44 produce
output identical to AMD's, because the test program only triggers the 10. The test program is
being extended to set more of FSR's options; versions that pass will be added to the patched DLL
and the add-on, so that Windows users are covered whatever their game does. Linux override files
cannot be prebuilt this way, because they are named after Proton's translation of each shader.

Thanks to the commenter on Discord who pointed out that the DLL has far more postpass versions
than were covered.
