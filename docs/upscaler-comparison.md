# The lossy DLL beside FSR 3.1, HelixSR and XeSS

[Back to the front page](../README.md) · [Exact and lossy compared](exact-vs-lossy.md)

People compare this project's lossy DLL with other upscalers they can run on the same card. This page puts five of them
through the same test scenes and the same timing, for comparison only. It is not a ranking, and it is not a review of the
other projects.

## In short

- **Picture accuracy:** the lossy DLL stays close to AMD's FSR 4.1.1 and ahead of the other three: within 0.1 dB of FSR 4
  on a still picture, where XeSS, HelixSR and FSR 3.1 are 2 to 4 dB behind.
- **Where the lossy DLL is last of the five:** leaves that sway fast without motion vectors (with slowly swaying leaves it is
  second after FSR 4). A very thin wire in a camera pan it draws dimmer than any of the others, and in a slow pan that wire flickers more than
  with any of them. In film grain it is busier
  than FSR 3.1, HelixSR and XeSS (and steadier than FSR 4).
- **Rain** drawn without motion vectors is where the five differ most to the eye: HelixSR shows the streaks as the game drew
  them, FSR 3.1 shows part of them, and FSR 4, the lossy DLL and XeSS blend faint rain almost entirely into the picture.
- **Speed on this card:** FSR 3.1 is the fastest by a wide margin, then HelixSR, then the lossy DLL, then this project's
  exact DLL, with AMD's FSR 4.1.1 and XeSS the slowest.
- **Everything here is one graphics card, made-up scenes and single runs.** A game can come out differently.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/cmp5-radar-dark.svg">
  <img src="img/cmp5-radar-light.svg" width="760" alt="Five radar charts, one per upscaler, each with nine spokes: still picture, moving background, thin railing, just-uncovered areas, tiny fast sparks, swaying foliage, steadiness at rest, steadiness of a thin wire in a pan, and speed. On every spoke the best of the five reaches the outer ring and the others reach in proportion. FSR 4.1.1 fills the ring on accuracy, sparks and foliage and is short on speed and steadiness at rest. The lossy DLL has nearly FSR 4.1.1's shape on accuracy, is the best on just-uncovered areas, shorter on foliage and sparks, and longer on speed and steadiness at rest. FSR 3.1 is longest on speed and steadiness at rest and shortest on accuracy and sparks. HelixSR is longest on the wire and strong on sparks, short on just-uncovered areas. XeSS is short on speed, on steadiness at rest and on sparks. The figures are in the tables below.">
</picture>

**How to read it.** One shape per upscaler, all on the same nine spokes. On each spoke the best of the five reaches the outer ring; the
others reach in proportion: a spoke at half length means twice the error (or twice the change per frame, or twice the time) of the
best one, and for sparks half as much of them shown. A bigger shape is better and a dent is a weakness. The dashed outline in each
panel is FSR 4.1.1, for comparison. The spokes do not weigh the same to the eye in a game, so the area of a shape is not a score.

The charts and pictures on this page are made by [`img/make_upscaler_comparison.py`](img/make_upscaler_comparison.py); the crops show the piece
of the picture where the five differ most from each other, picked by that script from the data.

## What was compared

| Name here | What it is | Version | Settings |
|---|---|---|---|
| FSR 4.1.1 | AMD's FSR 4 (INT8 model) with AMD's own shaders. This project's exact DLL gives the same picture, byte for byte | 4.1.1 | defaults |
| Lossy | this project's lossy DLL: FSR 4.1.1's network on every other frame | release `dll-2026-10-12` (auto exposure is off on this page) | defaults |
| FSR 3.1 | AMD's FSR 3.1 upscaler, from the same AMD file as FSR 4.1.1 | 3.1.5 | defaults |
| HelixSR | a community upscaler that runs NVIDIA's DLSS "Model E" network as ordinary compute shaders behind FSR 3.1's interface | 1.2.0 | defaults (its main network, sharpening off) |
| XeSS | Intel's XeSS, in the form that runs on any graphics card | 2.0.2 | defaults, no auto exposure |

- **Same inputs for all:** the same rendered frames, camera jitter, motion vectors and depth, from the test rig that the
  rest of this repository uses. Output 3840x2160 from 2260x1272, the size FSR calls "Balanced" (XeSS calls this ratio
  "Quality"). No sharpening anywhere.
- **Same measurements:** the last 8 of 40 frames, against the true 4K image.
- **One card:** a Radeon RX 7800 XT on Linux, through Proton.
- **Checked before measuring:** that each upscaler receives the inputs the way it expects. For XeSS the sign of the jitter and
  of the motion vectors was tested both ways and the better one used, which is also what Intel's guide describes. FSR 3.1
  and HelixSR take the same interface as FSR 4.

## Accuracy

Against the true image; higher dB is better, lower error is better.

| Scene | FSR 4.1.1 | Lossy | FSR 3.1 | HelixSR | XeSS |
|---|---|---|---|---|---|
| Still picture | 44.33 dB | 44.26 dB | 39.94 dB | 41.99 dB | 42.14 dB |
| Moving scene: background | 49.27 dB | 49.00 dB | 47.95 dB | 46.92 dB | 47.70 dB |
| Moving scene: thin railing | 41.82 dB | 41.34 dB | 38.36 dB | 40.12 dB | 40.86 dB |
| Moving scene: areas a moving object has just uncovered | 34.48 dB | 36.53 dB | 29.22 dB | 27.11 dB | 30.20 dB |
| A still bright object over fast ground at the same depth: error where its old image lands, of 255 | 1.62 | 2.65 | 3.09 | 2.27 | 2.15 |
| Leaves swaying without motion vectors, camera still: error of 255 | 12.1 | 18.7 | 16.8 | 15.5 | 15.5 |
| The same, camera panning | 10.7 | 18.0 | 15.4 | 16.8 | 16.8 |
| Leaves swaying at two thirds of that speed, camera still | 10.8 | 13.2 | 16.7 | 14.1 | 14.2 |
| Leaves swaying at half that speed, camera still | 10.2 | 12.0 | 16.6 | 13.5 | 13.1 |
| Still leaves, camera panning | 6.2 | 7.5 | 7.6 | 8.2 | 7.4 |

- The lossy DLL is the most accurate after FSR 4 in the first four rows, and the best of all five in just-uncovered areas.
- **Behind a still bright object over fast ground it is behind HelixSR and XeSS** and ahead of FSR 3.1; FSR 4 is clearly best there.
  This row came with release `dll-2026-10-11.2`, which fixed a ghost in that case (the release before it scored 6.06).

<img src="img/cmp5-plate.png" width="760" alt="A white object with dark marks at the top and ground moving fast below it, the piece just below the object enlarged two times, as true image and from the five upscalers. FSR 4.1.1 (error 1.6 of 255), HelixSR (2.4) and XeSS (2.0) show the ground clean; the lossy DLL (2.2) shows a faint lighter patch below each dark mark, what is left of the object's old image; FSR 3.1 (3.6) shows a ragged lower edge on the object.">

The lossy DLL is the only one of the five that leaves a visible trace of the object on the ground here, faint as it is. The object
and the ground are at the same depth in this scene; with distinct depths the lossy DLL is at FSR 4's level (1.42 against 1.58).

- **In foliage it depends on how fast the leaves move.** At the rig's usual sway speed the lossy DLL is the least accurate of
  the five: FSR 4's network needs its memory of the frame before to recognize motion without vectors, and with the network
  running on every other frame that memory is too old ([why](../research/frame-skip#foliage-and-the-networks-memory-release-dll-2026-10-12)).
  At two thirds and at half of that speed it is second only to FSR 4, ahead of XeSS, HelixSR and FSR 3.1. The two slower rows came
  with release `dll-2026-10-12`, which made skipped frames use the network's verdict there (the release before scored 15.0 and 13.5).
  The figures are for the frames that skip the network; on the others the lossy DLL reads 12.2 and 11.1.

The three pictures below are of the scenes in the first rows of the table and of the foliage rows.

<img src="img/cmp5-still.png" width="760" alt="Still picture, a 150 by 90 pixel piece of the 4K output enlarged four times, where the five upscalers differ most: a water tank with a thin ladder and railing. True image, then FSR 4.1.1 (error 2.3 of 255), the lossy DLL (2.4), FSR 3.1 (2.8), HelixSR (1.8) and XeSS (2.2). The ladder's thin rungs are clearest in HelixSR and FSR 4.1.1 and softest in FSR 3.1.">

<img src="img/cmp5-motion.png" width="760" alt="Moving scene, camera panning, a piece of the fine diagonal stripes on a moving object enlarged four times. True image: thin sharp white stripes. FSR 4.1.1 (error 23.7 of 255) and the lossy DLL (23.5) show them thin and even; FSR 3.1 (34.4) thicker and softer; HelixSR and XeSS (29.9 each) in between.">

<img src="img/cmp5-foliage.png" width="760" alt="Leaves swaying without motion vectors, camera still, a piece enlarged four times. True image: sharp small dark and light green leaves against a pale sky. FSR 4.1.1 (error 13.9 of 255) is the closest; the lossy DLL (22.4) shows the leaves softer and fatter; FSR 3.1 (19.7), HelixSR (18.4) and XeSS (19.7) are between the two.">

## Things a game draws without motion vectors

Bright dots drawn into the picture only, as games draw sparks and embers. For the lossy DLL the figures are for the frames
that skip the network; the same alternate frames are measured for the others.

| Scene | FSR 4.1.1 | Lossy | FSR 3.1 | HelixSR | XeSS |
|---|---|---|---|---|---|
| Large glowing particles: error of 255 | 0.66 | 1.40 | 3.21 | 0.77 | 1.01 |
| Tiny fast sparks: share of their brightness shown | 83% | 74% | 40% | 79% | 50% |
| Tiny slow embers: share shown | 81% | 81% | 53% | 79% | 69% |

FSR 4 and HelixSR handle these best. The lossy DLL is close on embers and behind on large particles and fast sparks. FSR 3.1
loses more than half of the small ones.

<img src="img/cmp5-big.png" width="760" alt="Large glowing particles drawn without motion vectors, camera still, a piece with two of them enlarged four times, as true image and from the five upscalers. FSR 4.1.1 (error 0.4 of 255) and HelixSR (0.7) show both round and smooth; the lossy DLL (0.7) shows them in place with a slightly rough edge on the smaller one; FSR 3.1 (1.5) shows faint arcs across them; XeSS (4.9) shows both dimmed with a fine checkered pattern.">

The piece is the one where the five differ most, so it flatters nobody: over the whole scene XeSS scores 1.01 and the lossy DLL 1.40 (the table above).

<img src="img/cmp5-sparks.png" width="760" alt="Tiny fast sparks drawn without motion vectors, camera still, a piece enlarged five times with five sparks in it. True image, then FSR 4.1.1 (error 0.6 of 255) and HelixSR (0.7) show all five round and bright; the lossy DLL (0.7) shows all five, slightly blocky; FSR 3.1 (1.4) shows them small, dim and one smeared into a streak; XeSS (1.6) shows them faint.">

### Rain

Thin bright streaks falling fast, drawn into the picture without motion vectors, over a dark surface with the camera still. The
streaks are faint (about a third of full brightness) and in a new place every frame. There is no fair "true image" to score
this against, so the table counts what is shown: output pixels more than 20 of 255 brighter than the surface, per million, over
eight frames. As the game draws it, about 5,900 per million of its own pixels carry a streak.

| | FSR 4.1.1 | Lossy | FSR 3.1 | HelixSR | XeSS |
|---|---|---|---|---|---|
| Pixels standing out, per million | 0 | 0 | 1,220 to 1,280 | 8,410 | 90 to 150 |
| The brightest of them, above the surface (of 255) | 7 | 8 | 44 to 45 | 84 | 18 to 20 |

<img src="img/cmp5-rain.png" width="760" alt="Rain drawn without motion vectors over a dark surface, a 200 by 130 pixel piece enlarged three times: the game's own frame and the five upscalers. The game's frame shows nine sharp gray vertical streaks (309 pixels more than 20 of 255 brighter than the surface). FSR 4.1.1 (0) and the lossy DLL (0) show an even dark surface with barely visible vertical traces. FSR 3.1 (191) shows some of the streaks thin and broken, with scattered specks. HelixSR (522) shows all the streaks, smooth and slightly wider than drawn. XeSS (17) shows faint traces.">

- **HelixSR shows the rain as the game drew it;** FSR 3.1 shows part of it, broken into specks. FSR 4, the lossy DLL and XeSS
  treat streaks this faint and fast as noise and blend them into the surface.
- **Which is right depends on the game.** Rain is meant to be seen; noise of the same shape is not. With brighter, slower streaks
  FSR 4 shows them (about 1,300 per million in that variant, the lossy DLL about 470); the other three were not run on it.
- The lossy DLL follows FSR 4 here only since release `dll-2026-10-11.7`. Before, it showed each streak at full strength and kept
  old ones on screen: about 20,000 pixels per million, more than three times what the game drew
  ([what was wrong](exact-vs-lossy.md#what-the-difference-looks-like)).

## Steadiness

How much the picture changes from one frame to the next where it should not, in steps of 255. Lower is steadier.

| Scene | FSR 4.1.1 | Lossy | FSR 3.1 | HelixSR | XeSS |
|---|---|---|---|---|---|
| Still picture, whole frame | 0.037 | 0.024 | 0.014 | 0.020 | 0.084 |
| Moving scene: background | 0.079 | 0.024 | 0.077 | 0.193 | 0.085 |
| A wire half a pixel wide, camera still | 2.9 | 2.8 | 2.3 | 2.4 | 4.2 |
| The same wire under a slow pan | 7.2 | 10.3 | 8.2 | 5.6 | 10.1 |
| Still picture with grain of 6 of 255 | 0.785 | 0.460 | 0.162 | 0.213 | 0.182 |
| Still picture with grain of 10 of 255 | 1.724 | 1.291 | 0.308 | 0.300 | 0.228 |

- The lossy DLL has the steadiest moving background of the five.
- **A thin wire under a slow pan is its weakest steadiness case:** over 40% more flicker than FSR 4, and more than any of the
  others (XeSS is close behind it). Release `dll-2026-10-12`'s fold of the network's first layer added to it (9.6 before). It also draws that wire dimmer than any of them: 53 of 255 against a true 111, where FSR 4 shows 100, XeSS 90,
  FSR 3.1 121 and HelixSR 135.
- **Grain:** FSR 4 passes grain on almost unchanged. The lossy DLL holds some of it back on the frames it skips, but FSR 3.1, HelixSR
  and XeSS all hold it back much further. Release `dll-2026-10-12` gave up steadiness here for the slow-foliage rows above (the
  release before read 0.342 and 1.056) and won a little of it back with a light fold in the network's first layer.
- Steadier is not always more accurate. FSR 3.1 has the steadiest still picture and the least accurate one. The wire also
  shows this with the camera still: HelixSR draws it brighter than the true image (143 of 255 against a true 111), FSR 4 and the lossy DLL
  dimmer (67 and 66), XeSS and FSR 3.1 in between (96 and 91).

<img src="img/cmp5-wires.png" width="760" alt="A wire far thinner than a rendered pixel, camera still, a piece with three wires enlarged four times. True image: thin continuous gray lines. FSR 4.1.1 (error 2.5 of 255) and the lossy DLL (2.6) show continuous dim lines; FSR 3.1 (1.6) and XeSS (1.7) brighter, slightly dotted lines; HelixSR (3.9) thicker lines brighter than the true image.">

## Speed

Graphics-card time for one upscale call, in milliseconds, at the same render ratio. Lower is faster.

| Output | FSR 4.1.1 | This project's exact DLL | Lossy | FSR 3.1 | HelixSR | XeSS |
|---|---|---|---|---|---|---|
| 1920x1080 | 1.05 | 0.89 | 0.68 | 0.41 | 0.75 | 1.42 |
| 2560x1440 | 2.18 | 1.44 | 1.11 | 0.58 | 1.01 | 2.28 |
| 3840x2160 | 4.76 | 3.17 | 2.36 | 1.16 | 1.99 | 4.98 |

- FSR 4.1.1, the two DLLs of this project, FSR 3.1 and HelixSR were timed by the same program, 200 calls after 40 to warm
  up. XeSS has another interface and was timed by a second program over 32 calls, so its column is not measured in quite
  the same way.
- The lossy figure is an average over the two kinds of frame: at 4K, 3.24 ms when the network runs and 1.44 ms when it is skipped.
  It was timed with the build of release `dll-2026-10-11.4`; the releases since changed only the last shader, and with
  `dll-2026-10-11.6` the whole upscaler timed 2.37 ms in the same program. Release `dll-2026-10-12`'s last shader takes 0.01 to
  0.02 ms more per frame when timed alone, and its fold in the network's first layer changes weights, not the amount of work; the
  whole upscaler was not timed again.
- XeSS runs a different, slower network on cards that are not Intel's than on Intel Arc. These figures say nothing about XeSS on Arc.
- All of this is under Proton on Linux. On Windows the same card's FSR 4.1.1 timings differ
  ([what is known](results.md)).

## What this page does not show

- **Games.** These are made-up scenes built to isolate one thing each. They are useful for telling upscalers apart, not for
  predicting how a particular game will look.
- **Other cards and systems.** HelixSR's author develops on different hardware; XeSS and FSR 3.1 behave differently across
  vendors. One RX 7800 XT on Linux is one data point.
- **Other settings.** Each upscaler was run at its defaults. HelixSR can use another network and optional sharpening; XeSS has
  auto exposure, which raised its still-picture score here from 42.1 to 42.7 dB when tried; none of that was explored.
- **Other render ratios.** Only the 1.7 ratio was measured.
- **Run-to-run spread.** Single runs.

## How to reproduce it

The scenes and measures are in [`research/pruning`](../research/pruning): `gen_inputs.py` and `gen_motion.py` write the
input frames, `metric_motion.py`, `particles.py`, `wires.py` and `foliage.py` measure the output; `rain.py` writes and measures the rain scene. `fsr4img.c` drives anything
that speaks AMD's FidelityFX interface and selects the upscaler by version name (`4.1.1`, `3.1`); HelixSR is run by putting its
DLL in the upscaler's place. [`xessmot.c`](../research/pruning/xessmot.c) is the same program for XeSS and needs Intel's
XeSS SDK headers to build and `libxess.dll` to run. None of the other projects' files are in this repository; get them from
their own sources.

Corrections are welcome, most of all from the other projects' authors: if a setting here is unfair to one of them, an issue
on this repository will get it rerun.
