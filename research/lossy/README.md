# A lossy track: folding away part of the model's weights

[Back to the research index](../README.md)

Everything this repository ships keeps AMD's image byte for byte. This page is about an
experiment that does not: doing less arithmetic in the model passes, and looking for the settings
that cost the least. **Nothing here is shipped or built into any release.**

It builds on two things: the measurement of a [community shader set](../community-lossy-set), which
showed that some model passes can lose weights without a measurable cost, and the
[motion test](../pruning#motion-test), which gives figures to tune against.

## The tool

`wfold.py <K> < passN.spvasm > out.spvasm` works on a model pass as vkd3d-proton translates it.

- Six of the twelve model passes (1, 2, 4, 5, 10, 12) carry their weights as constants. Each has
  one 3x3 convolution, and in it every output channel is a sum of 36 dot products: 9 taps times
  4 "weight words" (the int8 weights for four input channels).
- The tool drops the K words with the smallest weights from every output channel and adds each
  dropped word's weights to the nearest tap that is kept for the same four input channels
  (*folding*). Neighbouring pixels are similar, so the sum changes little, and the layer's
  response to a flat area is unchanged. One tap is always kept for each group of input channels.
- The compiler then removes the dot products whose weights are zero.

`wfold.py info < passN.spvasm` prints the layers it finds. The folding idea is from VALKKKS's notes;
this is an independent implementation. Folding 23 of 36 words in pass 12 reproduces the behaviour
of that set's pass 12 in the motion test (background change 0.103 against 0.105, 48.7 dB against
48.6 dB from AMD's frames), so the two do the same thing.

## What folding alone saves

Radeon RX 7800 XT, 4K, standalone benchmark, real weights:

| Pass | Words folded of 36 | AMD | Folded | Saved | The community set's version of the pass |
|---|---|---|---|---|---|
| 1 | 4 | 0.295 ms | 0.281 ms | 0.014 ms | 0.241 ms |
| 10 | 18 | 0.141 ms | 0.125 ms | 0.016 ms | 0.107 ms |
| 5 | 18 | 0.141 ms | 0.124 ms | 0.017 ms | 0.111 ms |
| 12 | 23 | 0.296 ms | 0.217 ms | 0.079 ms | 0.173 ms |

Folding accounts for about half of what the community set gains in these passes. The rest comes
from its other changes to the arithmetic (rounding and the integer forms of the output scaling),
which are not reproduced here.

## Pass 12: how much can go

The moving scene; AMD's shaders score 30.53 dB for the whole frame against the true image, and a
frame-to-frame change of 0.079 (background), 0.106 (block texture), 2.04 (fine stripes) and
0.913 (railing bars).

| Words folded of 36 | Saved | Whole frame | Change: background | texture | stripes | railing | Against AMD's frames |
|---|---|---|---|---|---|---|---|
| 8 | 0.025 ms | 30.44 dB | 0.081 | 0.114 | 2.16 | 0.942 | 53.0 dB |
| 12 | 0.040 ms | 30.33 dB | 0.087 | 0.115 | 2.28 | 0.936 | 51.7 dB |
| 16 | 0.055 ms | 30.32 dB | 0.087 | 0.113 | 2.13 | 0.958 | 51.4 dB |
| 20 | 0.067 ms | 30.58 dB | 0.089 | 0.111 | 1.91 | 0.983 | 50.3 dB |
| 23 | 0.077 ms | 30.59 dB | 0.103 | 0.106 | 1.85 | 1.011 | 48.7 dB |

The background gets less stable in steps: slightly up to 20 words, sharply at 23.

## Combinations

| Set | Saved | Whole frame | Change: background | texture | stripes | railing | Against AMD's frames |
|---|---|---|---|---|---|---|---|
| AMD's shaders | | 30.53 dB | 0.079 | 0.106 | 2.04 | 0.913 | |
| Passes 1 (4), 10 (18), 5 (18) | 0.047 ms | 30.84 dB | 0.069 | 0.098 | 1.99 | 0.888 | 49.7 dB |
| the same plus pass 12 (16) | 0.102 ms | 30.63 dB | 0.072 | 0.103 | 1.93 | 0.934 | 49.3 dB |
| the same plus pass 12 (20) | 0.114 ms | 30.70 dB | 0.079 | 0.105 | 1.96 | 0.947 | 47.6 dB |

- With passes 1, 10 and 5 folded, no figure is worse than AMD's.
- Adding pass 12 at 16 or 20 words keeps the background at AMD's level (the other passes offset
  it) and raises the railing's change by 2 to 4%. That is 0.10 to 0.11 ms, about 3.5% of FSR 4's
  time at 4K on this card.

## What these figures do and do not mean

- **The image is not AMD's.** About 48 to 50 dB from it: small, everywhere.
- **"Not worse on these figures" is not "not worse".** A lower frame-to-frame change can simply
  mean a softer image. The whole-frame error against the true image does not show that here, but
  it is one synthetic scene at one speed.
- **Timings are from one RDNA3 card.** The motivation is RDNA2 at 1440p and below, where the exact
  rewrites gain little; the relative saving there is not measured.

## Not done yet

- Sweeps for passes 1, 5, 10 (more than the fractions above) and pass 2; pass 4 looked like a bad
  trade in the community set.
- The other half of the community set's gain: its changes to rounding and output scaling.
- The prepass: a faster, not bit-exact prepass with no measurable effect exists in that set; an
  implementation of its own is needed here.
- Every version of the passes (three output-size classes, two models) and the DLL's shader
  format. The tool has only been run on the versions used at 1440p-to-4K output.
- More scenes, ideally frames captured from a game.
