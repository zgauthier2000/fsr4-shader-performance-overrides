# Research

[Back to the front page](../README.md)

Measurements, probes and experiments behind this repository, including the ones that did not work.
A summary of each is in [How it works, and what was tried](../docs/how-it-works.md).

| Page | What it covers |
|---|---|
| [`postpass-and-prepass/`](postpass-and-prepass) | why AMD's stores are slow, memory-traffic probes for every pass, the prepass breakdown, occupancy on other GPUs |
| [`wmma/`](wmma) | matrix-multiply instructions (WMMA) for the model passes: built, bit-exact, slower |
| [`pruning/`](pruning) | removing weights from the model: time saved against image error (not bit-exact, not shipped); the still-image and motion test rigs |
| [`community-lossy-set/`](community-lossy-set) | a community shader set for RDNA2 that removes weights for speed: timed pass by pass, image error at rest and in motion, and what would be needed to take it further |
| [`history-clamp/`](history-clamp) | a lower bound on the postpass's history weight, requested against shimmering (changes the image; test builds only) |

Game measurements are in [`../results/`](../results).
