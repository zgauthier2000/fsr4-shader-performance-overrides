# What's moving

What this project is working on, and how you can help. These are aims, not promises, and nothing here is a release date.

Last updated: 2026-11-04.

<picture><source media="(prefers-color-scheme: dark)" srcset="img/wm-now-dark.svg"><img src="img/wm-now-light.svg" alt="Five parts being worked on, each with what would help."></picture>

**Tiled lossy is an internal experiment,** tested only through the timing kit: it is not in any release, and the released lossy builds do not work this way. It splits each frame into tiles that skip the network at different times, instead of skipping it on the whole frame every other frame.

<picture><source media="(prefers-color-scheme: dark)" srcset="img/wm-cards-dark.svg"><img src="img/wm-cards-light.svg" alt="Timing kit reports most wanted, by kind of card."></picture>

**To send a report:** download [the Windows timing kit](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/timing-kit-2026-11-03/fsr4-timing-kit-windows-2026-11-03.zip), unpack it and run `fsr4time.exe`, or [the Linux and Steam Deck kit](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/download/timing-kit-2026-11-03/fsr4-timing-kit-linux-2026-11-03.tar.gz), which runs under Proton: unpack it and run `bash run.sh`. It tests this project's experiments on your card. Kits from 2026-11-03 on download new tests by themselves when they start, so there is no need to download a new kit for them. [More about the kit](../timing-kit/README.md).

<picture><source media="(prefers-color-scheme: dark)" srcset="img/wm-path-dark.svg"><img src="img/wm-path-light.svg" alt="The path of an improvement, and what limits each step."></picture>
