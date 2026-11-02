# DeckyUpscaler: what we found, and what each project could use

[DeckyUpscaler](https://github.com/doodlum/DeckyUpscaler) is a Decky Loader plugin by another developer. It runs AMD's FSR 4.1.2 Lite on the Steam Deck under Proton, through AMD's FSR SDK 2.4.0 Vulkan DLL, with its own faster shaders. Its author invited this project to look at the work and use what helps. This page is a first look, written to be useful to both projects. It is not a contest, and nothing here is a verdict on the Steam Deck.

Last updated: 2026-11-02. Timing kit and picture tables: DeckyUpscaler release v0.2.1, except the RX 7800 XT speed table (commit `0137747`).

**In short:** on the first Steam Deck report, under Proton, DeckyUpscaler's shipped set is the fastest build at 1080p, faster than this project's frame-skipping `4.1.2l-lossy`, and with a picture much closer to AMD's. RDNA 2 reports show the same. Above 1080p, where its shaders do not apply, `4.1.2l-lossy` is clearly faster. On RDNA 3 this project's builds are faster at every size tested.

**The limit:** these are one report per chip and one local card. Its shaders run only under Proton, so none of this says anything about Windows.

## The two projects at a glance

| | DeckyUpscaler | This project |
|---|---|---|
| Aim | Lite on the Steam Deck, picture changes kept small | Faster FSR 4 and Lite builds for many graphics cards |
| Networks | Lite | Full FSR 4 and Lite |
| Frame skipping | Ruled out on purpose | Used in the lossy builds |
| How it runs | AMD's SDK Vulkan DLL on the game's own Vulkan device; Proton only | Patched DirectX 12 DLLs through OptiScaler; Windows and Proton |
| Replacing shaders | SPIR-V modules swapped by hash | DXIL shaders patched into the DLL |
| Sizes its shaders cover | Up to 1080p output | Every size class |

DeckyUpscaler's sets tested here:

| Set | What it is |
|---|---|
| No pack | AMD's Lite through the SDK Vulkan DLL, with DeckyUpscaler's memory fix |
| Exact set | Rewritten shaders; same picture as no pack (`repl_exact`) |
| Shipped | `fsr4_shaders.bin` + `fsr4_shaders_dot2.bin`: more rewrites, small picture changes. Picture figures are from release v0.2.1 |

## Speed on a Steam Deck

From the [Linux and Steam Deck timing kit](../timing-kit/README.md#linux-and-steam-deck-experimental), one report, under Proton, moving scene, ms. "AMD Lite" here is AMD's FSR 4.1.2 Lite network and DirectX 12 shaders, run in this project's local test harness, not AMD's own runtime. Lower is faster.

| Build | 1080p | 1440p | 4K |
|---|---|---|---|
| AMD Lite | 6.775 | 12.458 | 26.074 |
| DeckyUpscaler, no pack | 7.135 | 12.327 | 27.695 |
| DeckyUpscaler, its same-picture changes | 5.917 | 12.154 | 28.113 |
| **DeckyUpscaler, shipped** | **5.521** | 11.967 | 27.692 |
| This project, `lt30-test` (`4.1.2l-exact`) | 6.282 | 11.431 | 23.925 |
| This project, `lt34-test` (`4.1.2l-lossy`) | 5.992 | **10.249** | **21.968** |

- **At 1080p** the shipped set is 19% faster than AMD Lite and 8% faster than `4.1.2l-lossy`, without skipping frames.
- **Its same-picture changes alone** are 6% faster than `4.1.2l-exact` at 1080p, and level with `4.1.2l-lossy`.
- **At 1440p and 4K** `4.1.2l-lossy` is 14% and 21% faster than the shipped set, because the shaders only apply up to 1080p.

Where its 1080p gain comes from on this Deck, % against no pack:

| Set | 1080p |
|---|---|
| Network pass changes only | -6.2 |
| Prepass changes only | -5.8 |
| Postpass changes only | -5.6 |
| All same-picture changes | -17.1 |
| Shipped without the `dot2` option | -20.3 |
| Shipped | -22.6 |

The gain is spread over the three parts and adds up, and the RX 6700 XT under Proton shows the same split. Left out one at a time from the same-picture set, the three that cost most are `q4b` (prepass layout, 2.6% slower without it), `csan2` (1.9%) and the options entry (1.5%). The others are within noise.

## Speed on RDNA 2 and on a Radeon 780M

From the [Linux and Steam Deck timing kit](../timing-kit/README.md#linux-and-steam-deck-experimental), one report per chip, under Proton, moving scene, ms at 1080p / 1440p / 4K. "AMD Lite" here is AMD's FSR 4.1.2 Lite network and DirectX 12 shaders, run in this project's local test harness, not AMD's own runtime. Lower is faster.

| Build | RX 6800 family (RDNA 2) | Radeon 780M (RDNA 3) |
|---|---|---|
| AMD Lite | 0.467 / 0.899 / 2.170 | 2.948 / 5.646 / 12.042 |
| DeckyUpscaler, no pack | 0.471 / 0.887 / 2.184 | 3.787 / 6.798 / 15.332 |
| **DeckyUpscaler, shipped** | **0.366** / 0.863 / 2.121 | 3.226 / 6.479 / 14.849 |
| This project, `lt30-test` (`4.1.2l-exact`) | 0.442 / 0.844 / 2.077 | 2.807 / 5.378 / 11.359 |
| This project, `lt34-test` (`4.1.2l-lossy`) | 0.420 / 0.761 / 1.834 | 2.640 / 4.901 / 10.777 |

- **RDNA 2, up to 1080p:** the shipped set is 22% faster than AMD Lite, and about 13% faster than `4.1.2l-lossy`, without skipping frames.
- **The no-pack route is not slow on RDNA 2:** it matches AMD Lite there. The slowdown below shows up on the two RDNA 3 chips, about 20-30%.
- **Above 1080p** the shipped set is about the same as no pack, and `4.1.2l-lossy` is the fastest here.

## Speed on the RX 7800 XT

Timing kit under Proton, moving scene, mean of 5 rounds, one session. "AMD Lite" here is AMD's FSR 4.1.2 Lite network and DirectX 12 shaders, run in this project's local test harness, not AMD's own runtime. Lower is faster.

| Build | 1080p ms | 1440p ms | 4K ms | 1080p vs AMD Lite |
|---|---|---|---|---|
| AMD Lite | 0.623 | 1.019 | 2.024 | baseline |
| DeckyUpscaler, no pack | 0.817 | 1.279 | 2.768 | +31% |
| DeckyUpscaler, exact set | 0.743 | 1.278 | 2.770 | +19% |
| DeckyUpscaler, shipped | 0.689 | 1.261 | 2.734 | +11% |
| This project, `4.1.2l-exact-r3` | 0.586 | 0.949 | 1.922 | -6% |
| This project, `4.1.2l-lossy-r3` | 0.532 | 0.827 | 1.658 | -15% |

- The shipped set in this table is from before the fix described below. One short run of release v0.2.1 gave about the same: 0.689 ms at 1080p, 2.728 ms at 4K.
- On this card DeckyUpscaler's shipped set saves 16% at 1080p against its own no-pack route. The no-pack route starts 31% slower than the DirectX 12 shaders. Why is not known; it does not happen on the RDNA 2 report above.
- `4.1.2l-lossy` gets its speed by skipping frames, and pays for it in picture (below). The fair comparison for DeckyUpscaler's shipped set depends on how much picture change you accept.

DeckyUpscaler's own figures on a Steam Deck, not checked here: at 1280x785 on Vulkan, AMD's shaders 3.00 ms, its exact set 2.56 ms, its shipped set about 2.25 ms. For scale only: this project's `4.1.2l-exact` was 16% faster than plain Lite on one Steam Deck report at 1080p, on Windows. Different system, size and scene, so these cannot be set side by side.

## Picture

DeckyUpscaler's shaders only apply up to 1080p, so these are four game clips reduced locally to 1080p output: render size halved, about 1130x635 (armor 1280x720). A halved clip approximates a game rendering at that size. Scored on the last 8 frames, using this project's display mapping `x / (1 + x)`, not a game's tone mapping.

Clips: Stellar Blade demo (armor), a foliage clip, Black Myth: Wukong Benchmark Tool, Shadow of the Tomb Raider.

**Distance from AMD Lite**, dB (higher is closer), with the share of pixels off by more than 8 of 255 in brackets:

| Build | Armor | Foliage | Wukong | Tomb Raider |
|---|---|---|---|---|
| `4.1.2l-exact` | identical | identical | identical | identical |
| DeckyUpscaler, no pack and exact set | 56.2 (0.03%) | 53.6 (0.02%) | 53.6 (0.02%) | 57.2 (0.02%) |
| DeckyUpscaler, shipped | 56.2 (0.03%) | 53.6 (0.02%) | 53.6 (0.01%) | 57.1 (0.03%) |
| `4.1.2l-lossy` | 45.2 (0.73%) | 43.5 (1.00%) | 42.0 (1.49%) | 50.6 (0.23%) |

**Distance from AMD's full FSR 4.1.1**, dB:

| Build | Armor | Foliage | Wukong | Tomb Raider |
|---|---|---|---|---|
| AMD Lite | 47.1 | 44.8 | 43.8 | 51.6 |
| DeckyUpscaler, shipped | 47.1 | 44.7 | 43.8 | 51.7 |
| `4.1.2l-lossy` | 43.6 | 41.7 | 40.5 | 48.4 |

- DeckyUpscaler's shipped set stays closer to AMD Lite than `4.1.2l-lossy` on all four clips, about as close as with no pack. That is expected: it does not skip frames.
- These figures measure closeness to AMD's picture, not which picture looks better. They do not cover flicker or how a build looks in motion.
- The scores are not comparable with DeckyUpscaler's published 70-72 dB, which uses another scene set and scoring method.

![The left edge of a Shadow of the Tomb Raider frame at 3x: AMD Lite, DeckyUpscaler's shipped set, DeckyUpscaler with no pack and 4.1.2l-lossy](img/deckyupscaler-sottr.png)

*Shadow of the Tomb Raider, last frame of the clip, left edge at 3x, with DeckyUpscaler's release v0.2.1. 1080p output from a clip halved here to 1129x635 render size, RX 7800 XT under Proton. The display mapping is this project's, not the game's tone mapping; no UI or post-processing.*

## Findings that may help DeckyUpscaler

Mostly measured on one RX 7800 XT, offered in case they are useful:

- **Fixed by its author:** a first test here found a dark strip at the frame's left edge at 1080p with the shipped set, and pictures that differed between runs. The author traced both to the prepass writing past the end of each row at 1920-wide output, reproduced them on a Deck and fixed them the same day. On release v0.2.1 both are gone here: two runs are identical on all four clips.
- **The Vulkan route's picture differs a little from the DirectX 12 route's** at 51-57 dB on the 4K clips, about the same distance from full FSR 4.1.1.
- **The packs change nothing above 1080p:** the larger size classes use other shader modules. This matters for a Deck on an external display or for other chips.
- **Its route is slower on RDNA 3 only, so far:** no pack is 20-31% slower than the DirectX 12 shaders on the RX 7800 XT and a Radeon 780M, and level on RDNA 2. A chip it was not tuned for may be worth a look if it ever targets them.
- **An independent test bed:** DeckyUpscaler's drop-in DLL runs in this project's [Linux and Steam Deck timing kit](../timing-kit/README.md#linux-and-steam-deck-experimental), included with its author's permission, so a run on a Deck times both projects on the same scene.

## What this project may try from DeckyUpscaler

Results so far, on a test build of `4.1.2l-lossy`, % against the same build unchanged at 1080p / 1440p / 4K, one report per card. Picture figures are distance from AMD Lite on four 4K clips.

| Idea from its notes | RX 6800 XT (Windows) | RX 6900 XT (Windows) | Radeon 780M (Proton) | Picture |
|---|---|---|---|---|
| Halves round up in the network | -0.6 / -0.3 / -0.5 | -0.2 / -0.1 / -0.3 | -0.2 / +0.0 / -0.1 | no measurable change |
| One bilinear history fetch instead of 9 | -2.4 / -2.5 / -1.0 | -2.1 / -1.6 / +0.3 | -1.8 / -2.1 / -1.7 | 0.2-2.6 dB further, softer |

Neither is in a release. Other ideas from its notes:

| Idea | Status here |
|---|---|
| Convolution weights held per wave in scalar registers | Largely here already: a test build of the first network pass gains about 0.5% on RX 6000, and the prepass already loads its weights from fixed addresses |
| A constant loop count in the last network pass | Already here |
| Prepass with 64-lane groups and 8x4 pixel blocks (`q4b`) | DXIL version being tested. DirectX 12 has no barrier limited to one wave, so this form keeps a workgroup barrier |
| Color clean-up folded into the readers (`csan2`) | Does not apply: it removes a clean-up pass in DeckyUpscaler's own proxy, and this project's route has no such pass |
| Options entry: skip the clean-up, drop some small border dispatches | The clean-up part does not apply. Whether the border part can save anything here is being checked, since this project's Lite builds already handle borders differently |
| f16 products summed in f32 in the prepass | Not tried; changes the picture slightly |

Which of its changes bring its gain is now partly answered: see the split under [Speed on a Steam Deck](#speed-on-a-steam-deck). Nothing from that split is in a release here.

Two cautions from its notes also apply here:

- **Uncached memory:** AMD's SDK Vulkan DLL takes its weights and tensors from uncached memory on RADV, which took Lite from 3.0 to 7.3 ms on a Deck. Any Vulkan build from this project needs that fix.
- **Timing builds that write garbage:** garbage output compresses worse, and the extra memory traffic can hide what was saved. This project's own timing kit builds with nonsense pictures should be read with that in mind.

## What would settle more

- **More Steam Deck runs** of the [Linux and Steam Deck timing kit](../timing-kit/README.md#linux-and-steam-deck-experimental): the comparison above rests on one report.
- **Looking at the pictures in motion,** on clips where both projects' builds apply.
- **More RDNA 2 reports under Proton,** since the result above rests on one.

## Ways this project can help

Open offers to DeckyUpscaler's author.

| Offer | What you would get |
|---|---|
| **Test new shader sets on an RX 7800 XT** | Speed, picture and run-to-run results for a new set, against AMD Lite and earlier sets. A run takes about half an hour. |
| **Send the evidence behind a finding** | Output frames, slider pages and the steps to reproduce the left-edge strip or anything else on this page. Output pictures only: raw game captures stay local. |
| **Run more picture checks** | Game clips, plus this project's synthetic scenes for flicker, rain specks, fine detail and ghosting, at sizes where the shaders apply. |
| **Share what did not work** | Which ideas were already tried here, on which cards, and what they measured, to save you repeating them. This project's documents are public, and questions about them are welcome. |

## What would help this project

DeckyUpscaler's author has a Steam Deck and tools this project lacks, and a few measurements from them could replace whole rounds of timing kits. None of this is expected, and any part of it helps. Figures from a Deck carry most weight.

| Data | How | What it would save or settle |
|---|---|---|
| **More [Linux timing kit](../timing-kit/README.md#linux-and-steam-deck-experimental) runs on a Deck** | `bash run.sh`, plugged in, Desktop Mode | One Deck report exists; a second would show how far it can be trusted. |
| **Per-pass times on a Deck for no pack, its exact set and its shipped set** | `DU_FSR4_VK_PROFILE`, at 1280x800 and 1920x1080 | Per-pass times to check the split measured by the kit. This project times its own passes only indirectly, by running each twice |
| **Gain of each option alone on a Deck, for the current sets** | Its generators with `DU_GEN_OPTS` | Which ideas are worth porting to DirectX 12, so fewer test builds go into kits. Its notes record this across rounds; a single current table would be easiest to compare |
| **Compiler figures for its passes on Van Gogh** | `RADV_DEBUG=shaders,shaderstats` | Registers, waves and instruction counts on RDNA 2 under RADV, to set beside AMD's Windows compiler figures this project already has. Windows and RADV appear to differ here, and this could show why |
| **Which of its changes depend on the RADV compiler** | Its judgment | Which ones are unlikely to carry over to Windows, so they can be skipped without a test |
| **This project's `4.1.2l-lossy` on its replay and motion tests** | Its replay and pan tests, using the DLL from a release | A second picture measure on its captured frames, with the same scoring as its published figures, since the figures on this page use different scenes and scoring |
| **How it keeps Deck timings steady** | Clock settings, windows, what it discards | Lower noise in this project's handheld figures, so fewer reports are needed to see a small change |

Results can go wherever is easiest. This project's raw game captures stay local, but it can run the same steps on its side if the steps are shared.

## Licenses

DeckyUpscaler is MIT, and its shaders derive from AMD's SDK under the license in its `shaders/LICENSE-AMD.md`. This project's scripts are GPL v2 or later. DeckyUpscaler's notes say it uses only this project's written documents and has read none of its code. This page shares results and ideas, not code.
