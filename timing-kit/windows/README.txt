FSR 4.1.1 timing kit for Windows (EXPERIMENTAL)
===============================================

Experimental: reports from Windows PCs are in from eleven graphics chips so far. If it fails
or shows something odd on your PC, that is exactly the report the project needs.

Times FSR 4.1.1 the way a game runs it, with AMD's own shaders and with this project's DLLs, on
your graphics card. No game and no OptiScaler are needed, and nothing is installed or changed.
https://github.com/zgauthier2000/fsr4-shader-performance-overrides

How to run it
  1. Unpack the whole folder somewhere (not inside the zip viewer). The DLLs come packed in
     dlls.pack.zst: the program takes out each one when it times it and replaces it with the next,
     so only one DLL (about 40 MB) is on disk at a time, and none when it has finished.
  2. Close games, browsers and video players.
  3. Double-click fsr4time.exe. It takes about 15 minutes (a slow or integrated graphics chip up to about
     20). Leave the PC alone while it runs: the header at the top of the window says so the whole time.
  4. At the end it shows a summary, saves it as results-<time>.txt in this folder, and asks
     whether to send it to the project. Only the summary you see is sent. If you send it,
     you can also type a name or nickname for the project's thank-you page; that is
     optional, and it is published there only if you type one.

Windows will warn about an unknown program, because the file is not signed. The source is in
the project's repository (timing-kit/windows/fsr4time.c) with the command that builds it, and the
checksums are on the download page.

What it does
  For every folder in dlls\ it loads that upscaler DLL through AMD's FidelityFX loader, feeds it
  made-up frames at 1080p, 1440p and 4K output, with two render sizes: the Balanced preset's, and
  Ultra Performance's (a third of the output, marked "UP" in the summary; the UP lines are for that
  mode only and do not describe the lossy DLL in other modes). Each with the picture
  still and with the camera moving. It measures the graphics card's time for each upscale call:
  200 calls after 40 to warm up.

  It does this in rounds: all DLLs in name order, then all in reverse order, and so on, for about
  15 minutes. A fast card gets up to eight rounds, a slow one two (one, if a single round takes
  more than ten minutes). More rounds make the figures steadier, and a reading disturbed by
  something else on the PC shows up as a spread between a DLL's runs. It also takes a fingerprint
  of the picture each DLL produces (its last frame), to show which DLLs give the same picture.

  dlls\1-amd-shaders   AMD's DLL with AMD's shaders (only its graphics-card check is lifted, so
                       that it runs on RX 6000 cards and integrated graphics too): the reference
  dlls\2-exact         this project's exact DLL of release dll-2026-10-15, for desktop cards
  dlls\2w-exact-without-shared-taps
                       the same without one of its changes (the exact DLL of dll-2026-10-14): in
                       2-exact the last shader reads and converts the colors it needs once instead
                       of up to four times. Faster on an RX 7800 XT; it needs more of the card's
                       registers, and whether that makes it slower on RX 6000 cards, the RX 7600
                       or integrated graphics is what your result shows. Both give AMD's picture.
  dlls\3-lossy         the lossy DLL of release dll-2026-10-15 (faster; the picture is NOT the
                       same as AMD's). Since this release it also skips frames in Ultra
                       Performance (the "UP" lines; figures for that mode only).
  dlls\3w-lossy-without-register-cut
                       the same without one of its changes: in 3-lossy the last shader needs fewer
                       registers, so that cards with a smaller register file (RX 6000, RX 7600,
                       integrated graphics) can run more of it at once. Whether that is faster on
                       those cards is what your result shows. Both give the same picture.
  dlls\2v-exact-wave64 2-exact with every FSR 4 shader asking the driver for 64-wide waves
                       (Shader Model 6.6's WaveSize); nothing else changed, AMD's picture.
                       Linux's driver runs these shaders 64-wide, and there they are much faster
                       than 32-wide. Whether Windows' driver already does is what this shows.
  dlls\2x-exact-wave32-control
                       2-exact asking for 32-wide waves: a control. If it takes about as long as
                       2-exact, your driver was running them 32-wide; if it is much slower, 64-wide.
  dlls\4-igpu-exact, 4w-igpu-exact-without-shared-taps, 4v-igpu-exact-wave64, 5-igpu-lossy,
  5w-igpu-lossy-without-register-cut
                       the same for integrated graphics and handhelds

  To time another FSR 4.1.1 DLL as well, and to see whether it gives the same picture as one of
  these, make a folder dlls\ next to fsr4time.exe, a folder for the DLL in it, and put its amd_fidelityfx_upscaler_dx12.dll there. For
  example, if you have the community's 4.1.1b file itself (the kit does not include it), put it
  in dlls\6-411b. The summary then has a line for it at every size, with its time and with
  which of the DLLs above, if any, gives the same picture.

  The DLL does not have to be FSR 4.1.1: any upscaler DLL that offers an FSR 4 version on your
  card is timed, and one that offers several (variants of the model for different kinds of
  graphics chip, for instance) gets a block of lines for each of them.

Reading the summary
  The numbers are milliseconds of graphics-card time per upscaled frame; lower is better. Each
  is the mean of that DLL's runs (one per round), and where they spread by more than 3% the
  smallest and largest are given in square brackets: treat such a line with caution. The percentage compares with the first DLL. For a lossy DLL the two numbers in brackets are a frame
  that runs FSR 4's model and a frame that skips it.

  After each run comes the picture's fingerprint. "= 1-amd-shaders" after it means the
  output was the same as that DLL's, byte for byte; "(differs from those above)" means no DLL
  before it gave that picture. A lossy DLL always differs, as it should. On an RX 6000 card under
  Windows the exact DLLs may differ from 1-amd-shaders (earlier kits found that); that is worth
  sending too.

  A DLL should give the same picture in all of its runs. Where it does not, the line says
  "NOT the same picture in all its runs" and, since kit 2026-10-12.3, how different: how many
  16x16-pixel blocks of the picture differ, the area they lie in, and the largest shift of a
  block's mean value. That is a finding worth sending.

  These are made-up frames. A game's numbers will differ somewhat; what OptiScaler's overlay
  shows in a game is the real thing, and the kit asks for it at the end if you have it.

Options (from a command prompt in this folder)
  fsr4time.exe --quick           1080p and 4K only
  fsr4time.exe --once            one round only (a few minutes)
  fsr4time.exe --minutes 8       let the rounds take about 8 minutes instead of 15
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
