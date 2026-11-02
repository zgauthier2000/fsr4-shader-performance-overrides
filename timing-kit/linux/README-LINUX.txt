FSR 4 timing kit for Linux and the Steam Deck

This is the Windows kit's program and test DLLs, run under Proton, so reports from Linux can be set beside those from Windows.
Figures under Proton are not Windows figures: the drivers differ.

To run it, from a terminal in this folder:   bash run.sh
On a Steam Deck use Desktop Mode, plugged in. It takes about 15 minutes; `bash run.sh --quick` is a short run. A window asks its questions, then whether to send the result.
It needs Proton from Steam or umu-run. Nothing is installed: its Wine prefix and results stay in this folder, so deleting the folder removes everything.
On a Steam Deck or a laptop, performance mode gives the best results.

du-nopack, du-shipped: DeckyUpscaler
  These slots are FSR 4.1.2 Lite through DeckyUpscaler, a Steam Deck plugin by doodlum (https://github.com/doodlum/DeckyUpscaler, MIT), included with its author's permission.
  du-shipped is its release v0.2.1 FSR 4 Lite drop-in, unchanged, with its shader packs. du-nopack is the same commit built here without shader packs, changed only in the name of the folder it reads (du0).
  They run only under Proton. Both use AMD's unmodified SDK Vulkan DLL. Licenses are in deckyupscaler/: LICENSE, shaders-LICENSE-AMD.md, amd_fidelityfx-LICENSE.md.

The other DLLs are described in README.txt.
