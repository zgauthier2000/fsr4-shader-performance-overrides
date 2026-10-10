FSR 4.1.1 timing kit for Windows (EXPERIMENTAL)
===============================================

Experimental: the first reports from Windows PCs are in, from eight graphics cards. If it fails
or shows something odd on your PC, that is exactly the report the project needs.

Times FSR 4.1.1 the way a game runs it, with AMD's own shaders and with this project's DLLs, on
your graphics card. No game and no OptiScaler are needed, and nothing is installed or changed.
https://github.com/zgauthier2000/fsr4-shader-performance-overrides

How to run it
  1. Unpack the whole folder somewhere (not inside the zip viewer).
  2. Close games, browsers and video players.
  3. Double-click fsr4time.exe. It takes about five minutes. Leave the PC alone while it runs.
  4. At the end it shows a summary, saves it as results-<time>.txt in this folder, and asks
     whether to send it to the project. Only the summary you see is sent.

Windows will warn about an unknown program, because the file is not signed. The source is in
the project's repository (timing-kit/windows/fsr4time.c) with the command that builds it, and the
checksums are on the download page.

What it does
  For every folder in dlls\ it loads that upscaler DLL through AMD's FidelityFX loader, feeds it
  made-up frames at 1080p, 1440p and 4K output (render size as in the Balanced preset), with the
  picture still and with the camera moving, and measures the graphics card's time for each upscale
  call: 200 calls after 40 to warm up. It also takes a fingerprint of the picture each DLL produces
  from the still scene, to show which DLLs give the same picture.

  dlls\1-amd-shaders   AMD's DLL with AMD's shaders (only its graphics-card check is lifted, so
                       that it runs on RX 6000 cards and integrated graphics too): the reference
  dlls\1b-amd-shaders-dots-split
                       the same, with one change to the last shader: its dot products are split
                       into two steps. The result is the same number, but RX 6000 cards under
                       Windows are known to show ghosting with AMD's original form. On those cards
                       this is the picture to compare with, not AMD's.
  dlls\1c-amd-shaders-411b-changes
                       AMD's shaders with all three changes that the community's "4.1.1b" fix for
                       RX 6000 cards makes to the last shader: the split dot products, and two
                       small ones to how pixel positions are limited and halved. Rebuilt by this
                       project from AMD's shaders; it is not that project's file.
  dlls\2-exact         this project's exact DLL for RX 7000 and RX 6000 cards
  dlls\3-lossy         its lossy DLL (faster; the picture is NOT the same as AMD's)
  dlls\4-igpu-exact    the exact DLL for integrated graphics and handhelds
  dlls\5-igpu-lossy    and its lossy one

  To time another FSR 4.1.1 DLL as well, make a folder for it in dlls\ (for example
  dlls\6-other) and put its amd_fidelityfx_upscaler_dx12.dll there.

Reading the summary
  The numbers are milliseconds of graphics-card time per upscaled frame; lower is better. The
  percentage compares with the first DLL. For a lossy DLL the two numbers in brackets are a frame
  that runs FSR 4's model and a frame that skips it.

  After each still run comes the picture's fingerprint. "= 1-amd-shaders" after it means the
  output was the same as that DLL's, byte for byte; "(differs from those above)" means no DLL
  before it gave that picture. A lossy DLL always differs, as it should. On an RX 6000 card the
  exact DLLs are expected to differ from 1-amd-shaders and to match 1b-amd-shaders-dots-split;
  whether 1c gives that picture too is one of the things the kit is there to find out.

  These are made-up frames. A game's numbers will differ somewhat; what OptiScaler's overlay
  shows in a game is the real thing, and the kit asks for it at the end if you have it.

Options (from a command prompt in this folder)
  fsr4time.exe --quick           1080p and 4K only
  fsr4time.exe --no-questions    no questions at the end, nothing is sent

Other graphics cards
  The kit is not limited to Radeon. FSR 4.1.1 should run on any graphics chip whose driver supports
  DirectX 12 with Shader Model 6.6. If you have a GeForce, an Intel Arc or Intel integrated
  graphics, or an older Radeon, please run it too:
  these DLLs were made for Radeon chips, nobody has measured them elsewhere yet, and your result
  shows whether they help there and whether the exact DLL still gives AMD's picture.

Not for Radeon RX 9000 cards: they run a different FSR 4.

The DLLs are modified versions of AMD's; see NOTICE.md. The program is licensed under the GNU
GPL v2 or later.
