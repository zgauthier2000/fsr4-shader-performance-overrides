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
| [`frame-skip/`](frame-skip) | running the model on every other frame and reusing its last output in between: half of AMD's upscaler time at 4K with the lossy set; what it costs in motion and in frame pacing (changes the image; in the lossy test builds) |
| [`lossy/`](lossy) | an experiment that gives up bit-exactness: folding away part of the model's weights, tuned against the motion test; available as an opt-in test build that changes the image |
| [`history-clamp/`](history-clamp) | a lower bound on the postpass's history weight, requested against shimmering (changes the image; test builds only) |

Game measurements are in [`../results/`](../results).
