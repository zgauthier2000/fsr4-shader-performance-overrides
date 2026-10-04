# GPU and operating system support

[Back to the front page](../README.md)

| GPU | System | Status |
|---|---|---|
| Desktop RDNA3 (RX 7900, 7800, 7700, 7600) | Linux, Proton | measured on an RX 7800 XT: faster |
| Desktop RDNA3 | Windows | testers report large gains |
| RDNA3 integrated (Radeon 780M, 890M) | any | reported slower: do not use, or try pass 11 only |
| RDNA2 (RX 6000, Steam Deck) | any | AMD's DLL does not offer this FSR 4 there; experimental unlock, untested |
| RDNA4 (RX 9000) | any | not applicable: it runs a different FSR 4 model |

## Windows

Several testers on Windows with Radeon RX 7000 graphics cards report large improvements with the
first version of these rewrites, nearly as large as on Linux, so AMD's Windows driver has the
same slow store pattern. The phased version has also been run on Windows with an RX 7800 XT,
with about the same result as the first version there.

Two ways to use them on Windows:

- the [patched DLL](../dll/README.md): replace `amd_fidelityfx_upscaler_dx12.dll`, nothing else;
- a ReShade add-on in [`windows/`](../windows) that swaps the same two shaders when AMD's DLL creates
  them. See [`windows/README.md`](../windows/README.md).

Both were verified byte for byte against AMD's output under Proton. On integrated GPUs, see below.

## Integrated GPUs (Radeon 780M and similar)

People testing on RDNA3 integrated GPUs have reported that FSR 4 gets slower, not faster, with
the first version of the postpass rewrite and with the phased version too. This has not been
reproduced here (only a Radeon RX 7800 XT was available), and it is not yet known which of the
two rewrites is responsible. The likely one is the postpass: an integrated GPU's memory system
may not suffer from the scattered stores at all, so rewriting them only adds work. Pass 11 only
lets the driver unroll loops, which is unlikely to cost anything. Until the runs below show
otherwise, **on an integrated GPU, use pass 11 only, or nothing**.

The two possibilities the reports have narrowed down:

- **Low occupancy** in the first postpass rewrite (4 waves per SIMD to hide memory latency) was the
  first suspect, but the phased postpass (16 waves per SIMD) is reported slower too.
- **No store penalty to remove:** if the integrated GPU's memory system handles the scattered
  stores well, the postpass rewrite only adds barriers and workgroup-memory traffic, and bunches
  the writes at the end of each workgroup. This is the current suspect.

On Windows with Radeon RX 7000 graphics cards (not integrated GPUs), testers report large
improvements with the first version, and one tester with an RX 7800 XT saw no difference between
the first and the phased version. That is expected: the DXIL version that Windows uses was never
limited the same way (it already ran 8 waves per SIMD), and under vkd3d-proton its postpass only
went from 0.72 ms to 0.67 ms.

To find out, compare OptiScaler's upscaler time, frame rate uncapped, in four runs. Ready-made
pass 11-only and postpass-only DLLs are attached to the
[release `dll-2026-10-03`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-03)
as `test-pass11-only.zip` and `test-postpass-only.zip`.

| Run | Linux (launch option) | Patched DLL |
|---|---|---|
| AMD's shaders | no `VKD3D_SHADER_OVERRIDE` | AMD's original DLL |
| Both rewrites | the `prebuilt/` folder | `patch_upscaler_dll.py` |
| Pass 11 only | a copy of `prebuilt/` without `683038df6272d4db.spv` and `4d657fb0eed077d6.spv` | `patch_upscaler_dll.py --only pass11` |
| Postpass only | a copy of `prebuilt/` without `e29847a84b6f746f.spv` | `patch_upscaler_dll.py --only postpass` |

At 1080p output or below, the files in `prebuilt/` do not apply; build your own with
`build_override.sh`, using `PASS11=0` or `POSTPASS=0` to leave one rewrite out. Until there is
more data, use whichever run is fastest on your GPU.

Please report the results with the GPU, the operating system and driver (Mesa version or AMD
driver), the game, the output resolution and FSR mode.

## RDNA2 and other GPUs that FSR 4 refuses (experimental)

AMD's DLL decides for itself which GPUs get FSR 4. It contains two versions, each with its own
check:

- the FP8 version needs the driver to report FP8 matrix multiplication and a discrete GPU, which in
  practice means RDNA4;
- the INT8 version (the one this repository speeds up) reads the GPU's chip family from AMD's
  driver and only accepts family 0x91, desktop RDNA3 (RX 7900, 7800, 7700, 7600). It refuses RDNA2
  (RX 6000), RDNA3 integrated GPUs (Radeon 780M, 890M) and other vendors.

The INT8 version's shaders themselves are plain Direct3D 12 (Shader Model 6.6; packed int8 and
half-precision dot products) and need no RDNA3-only feature. `patch_upscaler_dll.py --any-gpu`
makes the INT8 version's check always answer yes, so FSR 4 is offered on those GPUs too. Under
Proton on an RX 7800 XT the result is byte-for-byte identical to AMD's DLL, but **it has not been
tried on any GPU the check refuses**: whether FSR 4 then runs correctly, and how fast, is up to
that GPU and its driver. Do not use it on RDNA4, where both versions would then report support.

Ready-made test builds are attached to the [release `dll-2026-10-03`](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-10-03):

| File | Contents |
|---|---|
| `test-any-gpu-amd-shaders.zip` | check lifted, AMD's shaders unchanged: does FSR 4 run at all? |
| `test-any-gpu.zip` | check lifted, both rewrites |
| `test-any-gpu-pass11-only.zip` | check lifted, pass 11 rewrite only (for integrated GPUs) |

If you try them, please report your GPU, Windows or Linux and driver version, the game, whether FSR
4 starts and looks right, and OptiScaler's upscaler time for each.
