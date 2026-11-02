# DeckyUpscaler: what we found, and what each project could use

[DeckyUpscaler](https://github.com/doodlum/DeckyUpscaler) is a Decky Loader plugin by another developer. It runs AMD's FSR 4.1.2 Lite on the Steam Deck under Proton, through AMD's FSR SDK 2.4.0 Vulkan DLL, with its own faster shaders. Its author invited this project to look at the work and use what helps. This page is a first look, written to be useful to both projects. It is not a contest, and nothing here is a verdict on the Steam Deck.

Last updated: 2026-11-02. Speed table: DeckyUpscaler commit `0137747`; picture tables: its release v0.2.1.

**The biggest limit:** everything below was measured on one RX 7800 XT under Proton, not on a Steam Deck. DeckyUpscaler is tuned for the Deck's RDNA 2 chip, so its results on this card say little about how it runs on a Deck. **No Deck comparison of the two projects exists yet.**

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
- On this card DeckyUpscaler's shipped set saves 16% at 1080p against its own no-pack route, which is a real gain. The no-pack route starts 31% slower than the DirectX 12 shaders. Why is not known, and it may not apply on a Deck.
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

Measured on this card only, offered in case they are useful:

- **Fixed by its author:** a first test here found a dark strip at the frame's left edge at 1080p with the shipped set, and pictures that differed between runs. The author traced both to the prepass writing past the end of each row at 1920-wide output, reproduced them on a Deck and fixed them the same day. On release v0.2.1 both are gone here: two runs are identical on all four clips.
- **The Vulkan route's picture differs a little from the DirectX 12 route's** at 51-57 dB on the 4K clips, about the same distance from full FSR 4.1.1.
- **The packs change nothing above 1080p:** the larger size classes use other shader modules. This matters for a Deck on an external display or for other chips.
- **An independent test bed:** DeckyUpscaler's drop-in DLL runs in this project's [Linux and Steam Deck timing kit](../timing-kit/README.md#linux-and-steam-deck-experimental), included with its author's permission, so a run on a Deck times both projects on the same scene.

## What this project may try from DeckyUpscaler

None of this has been tried here yet. Exact builds would keep AMD's picture byte for byte, as always.

| Idea from its notes | Could suit | Note |
|---|---|---|
| Convolution weights held per wave in scalar registers | Exact | About 10% on its prepass, on a Deck |
| Prepass with 2x2 pixels per lane in 64-lane groups, no barrier | Exact | Needs a DXIL twin of a SPIR-V idea |
| Dropping tensor border-clear dispatches | Exact | This project's Lite builds already handle the border separately: compare |
| One bilinear history fetch instead of 9 taps | Lossy | 78 µs on a Deck; its motion test found little change, though it chose not to ship it |
| f16 products summed in f32 in the prepass | Lossy | Changes the picture slightly |

Two cautions from its notes also apply here:

- **Uncached memory:** AMD's SDK Vulkan DLL takes its weights and tensors from uncached memory on RADV, which took Lite from 3.0 to 7.3 ms on a Deck. Any Vulkan build from this project needs that fix.
- **Timing builds that write garbage:** garbage output compresses worse, and the extra memory traffic can hide what was saved. This project's own timing kit builds with nonsense pictures should be read with that in mind.

## What would settle more

- **A Steam Deck run** of the [Linux and Steam Deck timing kit](../timing-kit/README.md#linux-and-steam-deck-experimental), which times `4.1.2l-exact`, `4.1.2l-lossy` and DeckyUpscaler's shipped set together. This is the comparison that matters most.
- **Looking at the pictures in motion,** on clips where both projects' builds apply.
- **An RDNA 2 desktop card under Proton,** to see whether the slower no-pack route appears on the chip family the shaders were written for.

## Ways this project can help

Open offers to DeckyUpscaler's author.

| Offer | What you would get |
|---|---|
| **Test new shader sets on an RX 7800 XT** | Speed, picture and run-to-run results for a new set, against AMD Lite and earlier sets. A run takes about half an hour. |
| **Send the evidence behind a finding** | Output frames, slider pages and the steps to reproduce the left-edge strip or anything else on this page. Output pictures only: raw game captures stay local. |
| **Run more picture checks** | Game clips, plus this project's synthetic scenes for flicker, rain specks, fine detail and ghosting, at sizes where the shaders apply. |
| **Share what did not work** | Which ideas were already tried here, on which cards, and what they measured, to save you repeating them. This project's documents are public, and questions about them are welcome. |

## Licenses

DeckyUpscaler is MIT, and its shaders derive from AMD's SDK under the license in its `shaders/LICENSE-AMD.md`. This project's scripts are GPL v2 or later. DeckyUpscaler's notes say it uses only this project's written documents and has read none of its code. This page shares results and ideas, not code.
