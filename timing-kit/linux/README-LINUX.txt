FSR 4 timing kit for Linux and the Steam Deck

This is the Windows kit's program and test DLLs, run under Proton, so reports from Linux can be set beside those from Windows.
Figures under Proton are not Windows figures: the drivers differ.

To run it, from a terminal in this folder:   bash run.sh
It lists the Protons it finds and asks which to use; Enter takes the first. The report names the one used. To choose without the question: env FSR4_PROTON=/path/to/a/Proton/folder bash run.sh
If you change Proton for a later run, delete the pfx folder first.
CachyOS Proton builds work: testers ran the 2026-11-02 and 2026-11-03 kits with proton-cachyos and Proton-CachyOS (Latest, x86_64_v3). An older CachyOS Proton build ended without running in testing here; if yours does, use Proton Experimental or GE-Proton.
On a Steam Deck use Desktop Mode, plugged in. It takes about 15 minutes on a desktop card, but about 30 to 40 minutes on a Steam Deck (one round of tests takes that long there); `bash run.sh --quick` is a short run. A window asks its questions, then whether to send the result.
It needs Proton from Steam or umu-run. Nothing is installed: its Wine prefix and results stay in this folder, so deleting the folder removes everything.
On a Steam Deck or a laptop, performance mode gives the best results.

du-nopack, du-shipped: DeckyUpscaler
  These slots are FSR 4.1.2 Lite through DeckyUpscaler, a Steam Deck plugin by doodlum (https://github.com/doodlum/DeckyUpscaler, MIT), included with its author's permission.
  du-shipped is its release v0.2.1 FSR 4 Lite drop-in, unchanged, with its shader packs. du-nopack is the same commit built here without shader packs, changed only in the name of the folder it reads (du0).
  They run only under Proton. Both use AMD's unmodified SDK Vulkan DLL. Licenses are in deckyupscaler/: LICENSE, shaders-LICENSE-AMD.md, amd_fidelityfx-LICENSE.md.

du-x-exact, du-x-pmix, du-x-rhu, du-x-pfm, du-x-nodot2, du-x-prepass, du-x-network, du-x-postpass: measuring builds of DeckyUpscaler's shaders, never for a game or a release
  They time parts of its shipped set, to see which part brings its speed on your card, built here from its generators with no other change than which options and shaders are in each (folders du1 to du8).

du-e-notstore, du-e-norecloop, du-e-noq4b, du-e-noring, du-e-nocsan2, du-e-nopdead, du-e-noentry, du-e-base, du-e-prepass, du-e-network, du-e-postpass: more measuring builds of DeckyUpscaler's shaders, never for a game or a release
  They split its same-picture set: one change left out, none of its options, or one step only (folders du10 to du20).

The other DLLs are described in README.txt, which also lists some that this kit leaves out (their questions are answered): lt17-19, lt22, lt31, lt35, lt36, lt41, lt53, lt57, lt58, lt87-98 and the n-exact-*-prev builds.

Music (optional): while the runs go, Space plays / pauses and the Left / Right arrows skip songs. The terminal window must have focus.
