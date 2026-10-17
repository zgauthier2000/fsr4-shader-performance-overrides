# The lossy DLL's rules on a skipped frame

[Back to the README](../README.md) · [Exact and lossy builds compared](exact-vs-lossy.md) · [How the rules were found](../research/frame-skip)

The lossy DLL runs FSR 4's neural network on every other frame. On the frames in between, the last of FSR 4's shaders
has to make a picture without it: from the network's result of the frame before, the previous picture, and the new
frame's samples. The rules it follows grew over many releases, one fault at a time. This page shows them in one chart,
as they are in the current release.

It applies to the lossy DLL (the `lossy` folder of each download) only. The exact files have none of this.

<img src="img/rules-flow-light.svg#gh-light-mode-only" width="760" alt="Flow chart of what the lossy DLL's last shader does with one output pixel on a frame that skips the neural network. 1: start from the network's weight for the new frame, kept from its last run and moved along with the picture, and square it. 2: ask whether the picture is at rest at this pixel. 3, at rest: take nothing from the new frame, unless the content changed without the game reporting motion: the previous picture lies outside the range of the nine new samples, the new frame differs from it by more than a quarter of that range (or by much less, where the previous picture lies at one end of that range), or the network itself had given a middle or a very high weight. 4, in motion: keep the weight and, only beside anything that moves differently from the pixel, limit the previous picture to the range of the nine new samples. 5, at rest and in motion: a spark test takes the new frame where a new sample lies far outside the previous picture around the pixel and has a bright neighbor both sideways and above or below. 6: a pixel that was hidden a frame ago behind something nearer that moves differently, or whose previous picture scrolled in from outside the screen, takes the new frame alone. Then the pixel is mixed from the new frame and the previous picture with the resulting weight. 7, on every frame: a change smaller than two to four steps of the stored number format is dropped."><img src="img/rules-flow-dark.svg#gh-dark-mode-only" width="760" alt="Flow chart of what the lossy DLL's last shader does with one output pixel on a frame that skips the neural network. 1: start from the network's weight for the new frame, kept from its last run and moved along with the picture, and square it. 2: ask whether the picture is at rest at this pixel. 3, at rest: take nothing from the new frame, unless the content changed without the game reporting motion: the previous picture lies outside the range of the nine new samples, the new frame differs from it by more than a quarter of that range (or by much less, where the previous picture lies at one end of that range), or the network itself had given a middle or a very high weight. 4, in motion: keep the weight and, only beside anything that moves differently from the pixel, limit the previous picture to the range of the nine new samples. 5, at rest and in motion: a spark test takes the new frame where a new sample lies far outside the previous picture around the pixel and has a bright neighbor both sideways and above or below. 6: a pixel that was hidden a frame ago behind something nearer that moves differently, or whose previous picture scrolled in from outside the screen, takes the new frame alone. Then the pixel is mixed from the new frame and the previous picture with the resulting weight. 7, on every frame: a change smaller than two to four steps of the stored number format is dropped.">

## The words in the chart

- **Weight:** the share of the new frame in a pixel. AMD's network works it out for every pixel on every frame: near 0
  where the previous picture is still right, near 1 where it has to be given up. On a skipped frame the lossy DLL only
  has the weight of the frame before.
- **History:** the previous picture, moved by the game's motion vectors to where its content is now.
- **The nine samples:** the pixels of the game's frame around the output pixel. The game renders at a lower resolution
  and at a slightly different offset every frame, so these are the only fresh information a skipped frame has.
- **Range:** the span from the darkest to the brightest of the nine samples, per color channel.

## Why each step is there

Each rule answers a fault that was seen in the test rig or reported from a game. The links go to the write-up of how it
was found and measured.

| Step | Rule | The fault it answers | Since |
|---|---|---|---|
| 1 | The weight, squared | Shimmer on skipped frames: the old weight took too much of a frame whose samples fall elsewhere. [Write-up](../research/frame-skip/README.md#leaning-on-the-history-on-skipped-frames-release-dll-2026-10-065) | `dll-2026-10-06.5` |
| 2, 3 | Nothing from the new frame at rest | Fine detail at rest shimmered more than with AMD's shaders. [Write-up](../research/frame-skip/README.md#nothing-from-the-new-frame-at-rest-release-dll-2026-10-07) | `dll-2026-10-07` |
| 2, 4, 6 | ... with motion per 2x2 pixels | A thin thing fixed on screen in front of a moving scene shared its neighbors' motion and kept a faint copy of itself beside it. [Write-up](../research/frame-skip/README.md#finer-motion-for-the-rules-a-memory-rule-and-two-cleared-diagonals-release-dll-2026-10-13) | `dll-2026-10-13` |
| 3 a, b | Content that changed without motion | Particles, sparks and embers froze on every skipped frame, because games draw them without motion vectors. [Write-up](../research/frame-skip/README.md#content-without-motion-vectors-particles-sparks-embers-release-dll-2026-10-09) | `dll-2026-10-09` |
| 3 b | ... with a lower threshold where the history lies at one end of the new samples | Small dark things that move without motion vectors (leaves falling in front of a dark sky) were shown late on every other frame. [Write-up](../research/frame-skip/README.md#small-dark-things-without-motion-vectors-a-one-sided-test-sb_oneside) | `dll-2026-10-13.2` |
| 3 b | ... or by a little, where it did so in the same direction on the frame before | The same leaves were still shown less fully on skipped frames, and left a longer trace than with AMD's shaders. [Write-up](../research/frame-skip/README.md#a-change-that-lasts-two-frames-sb_persist-fs_persist) | `dll-2026-10-14` |
| 3 c | The network's own verdict, high weights | Large soft particles and slow embers were still too dim. [Write-up](../research/frame-skip/README.md#the-models-own-verdict-particles) | `dll-2026-10-11` |
| 3 c | The network's own verdict, middle weights | Slowly swaying leaves lagged. [Write-up](../research/frame-skip/README.md#foliage-and-the-networks-memory-release-dll-2026-10-12) | `dll-2026-10-12` |
| 4 | Limit the history to the samples' range | Where the picture had changed since the network last ran, an outdated color was mixed in. [Write-up](../research/frame-skip/README.md#history-clamp-on-skipped-frames-release-dll-2026-10-064) | `dll-2026-10-06.4` |
| 4 | ... not at rest, and in motion in proportion to the network's weight | The limit erased thin wires from the history and left white beads along them. [Write-up](../research/frame-skip/README.md#thin-wires-what-the-history-clamp-did-to-them) | `dll-2026-10-11` |
| 4 | ... in full beside anything that moves differently | A still bright object over fast-moving ground left its image on the ground. [Write-up](../research/frame-skip/README.md#a-still-object-over-fast-ground-release-dll-2026-10-112) | `dll-2026-10-11.2` |
| 4 | ... and only there: no longer by the network's weight | A very thin wire was shown at about half its brightness while the camera pans. [Write-up](../research/frame-skip/README.md#a-thin-wire-in-a-pan-the-clamp-only-beside-different-motion-release-dll-2026-10-132) | `dll-2026-10-13.2` |
| 4 | ... to the samples' range itself, no longer widened by half of it | Part of a moving object's old image was still let through beside it. [Write-up](../research/frame-skip/README.md#a-tighter-limit-beside-different-motion-sb_clamp0) | `dll-2026-10-14` |
| 3, 7 | A small drift that repeats the frame before's (a slow fade): the network's own weight, and no dead band | Bright flat areas followed a slow fade up to half a frame later than with AMD's shaders. [Write-up](../research/frame-skip/README.md#slow-fades-sb_fade-fs_persistrun) | `dll-2026-10-14` |
| 5 | Spark test | A spark that arrives on a skipped frame was not shown. [Write-up](../research/frame-skip/README.md#content-without-motion-vectors-particles-sparks-embers-release-dll-2026-10-09) | `dll-2026-10-09` |
| 5 | ... stricter threshold | Sky seen through leaves was shown as bright dots. [Write-up](../research/frame-skip/README.md#bright-dots-in-foliage-release-dll-2026-10-113) | `dll-2026-10-11.3` |
| 5 | ... needs a bright neighbor | Single over-bright pixels on glossy surfaces sparkled. [Write-up](../research/frame-skip/README.md#sparkling-on-glossy-surfaces-and-a-shader-that-held-too-much-release-dll-2026-10-116) | `dll-2026-10-11.6` |
| 5 | ... a neighbor in both directions | Rain was shown as white dashes. [Write-up](../research/frame-skip/README.md#rain-and-other-thin-streaks-release-dll-2026-10-117) | `dll-2026-10-11.7` |
| 6 | Just uncovered | The old image of a moving object stayed beside it for a frame. [Write-up](../research/frame-skip/README.md#following-the-pictures-motion-release-dll-2026-10-066), [the record of who was there](../research/frame-skip/README.md#who-was-here-a-frame-ago-release-dll-2026-10-07) | `dll-2026-10-06.6`, `dll-2026-10-07` |
| 6 | Scrolled in | A dark band at the screen edge when the camera began to turn. [Write-up](../research/frame-skip/README.md#dark-bands-at-the-screen-edge-fixed-in-release-dll-2026-10-063) | `dll-2026-10-06.3` |
| 6 | ... not where the picture is at rest | In Ultra Performance, thin wires and sparks at rest flashed on skipped frames (Ultra Performance only; elsewhere almost no change). [Write-up](../research/frame-skip/README.md#frame-skip-in-ultra-performance-release-dll-2026-10-15) | `dll-2026-10-15` |
| 7 | Dead band | Flat areas at rest flickered by one step of the stored number format. [Write-up](../research/frame-skip/README.md#why-folding-steadied-the-picture-and-what-replaced-it-release-dll-2026-10-114) | `dll-2026-10-11.4` |

## What the chart leaves out

- **Before these rules run,** the network's result of the frame before is moved along with the picture, so that each
  pixel gets the weight that belonged to its content. The motion for that is kept once per block of 4x4 output pixels.
- **The rules' own motion is finer since `dll-2026-10-13`:** one value per 2x2 output pixels, for motion up to 31
  pixels per frame; beyond that they use the block's. The network's result is still moved per block, so a thin edge
  in front of a moving background can keep a faint old image beside it on skipped frames. That is a known limit.
- **One rule is not about the picture at all.** Where a skipped frame finds a place at rest with differently moving
  content around it, it raises one value of the memory the network keeps for its next run, so that the network does
  not hold on to the old picture there. [Write-up](../research/frame-skip/README.md#the-memory-rule-sb_memstill)
- **The numbers are defaults, not laws.** Every threshold in the chart is a setting of the tool that writes these rules
  ([`skipblend.py`](../research/frame-skip/skipblend.py), whose head lists them all), chosen by measuring in the test rig.
- **Frames that run the network** get AMD's mix unchanged, and then step 7.
- **What the rules cost in picture quality** is on the page that [compares exact and lossy](exact-vs-lossy.md).
