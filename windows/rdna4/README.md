# RX 9000 (RDNA4): exact FP8 load reorder

Rewrites of the FSR 4 FP8 network shaders in AMD's DLL (4.1.1.2740 or 4.1.2.4555). They make the RX 9000 driver issue
loads earlier. Only the order of loads and integer math changes, plus identical reads being shared, so **the picture
stays AMD's byte for byte**. Background and measurements: issue #56. Research tools for repeating the measurements:
[`../../research/rdna4/`](../../research/rdna4).

RX 9070 XT, stable clocks (1868 MHz), 3 A/B pairs, moving scene, Balanced, against AMD's DLL of the same version:

| Build | 1080p | 1440p | 4K |
|---|---|---|---|
| 4.1.2 | 0.476 → 0.441 ms (−7.2%) | 0.823 → 0.743 ms (−9.6%) | 1.705 → 1.578 ms (−7.5%) |
| 4.1.1 | 0.475 → 0.439 ms (−7.6%) | 0.820 → 0.738 ms (−9.9%) | 1.694 → 1.569 ms (−7.4%) |
| 4.1.2 with `PREPASS_HOIST=1` | −7.8% | −10.1% | −8.1% |
| 4.1.1 with `PREPASS_HOIST=1` | −8.2% | −10.1% | −7.8% |

Pictures: identical to AMD's in all 26 kit rows (Quality, Balanced, Performance and Ultra Performance at 1080p, 1440p and
4K, plus 800p, still and moving), for every build in the table.

**Use the 4.1.2 form on RX 9000.** When a game asks for FSR's automatic version, Adrenalin 32.0.32015.12012 swaps a 4.1.1
DLL for its own FSR 4.1.2 (provider `4.1.2 *`), so a patched 4.1.1 DLL never runs. A 4.1.2 DLL is used as it is.

## Build

You need Python 3, DXC (`dxc` for `-dumpbin`, and its `dxcompiler` library) and `dxilasm`
([`../tools/dxilasm.cpp`](../tools/dxilasm.cpp)). On Windows, the Windows SDK's `dxc.exe` and `dxcompiler.dll` work:

```bash
cl /EHsc /O2 ../tools/dxilasm.cpp /Fe:dxilasm.exe          # or: g++ -std=c++17 -I<dxc>/include ../tools/dxilasm.cpp -ldl -o dxilasm
DXC=/path/to/dxc DXILASM=/path/to/dxilasm DXCOMPILER=/path/to/dxcompiler.dll \
  ./build_rdna4_fp8.sh amd_fidelityfx_upscaler_dx12.dll out/
(cd out && sha256sum -c --quiet ../check/4.1.2.sha256)  # same files as the measured build (4.1.1.sha256 for 4.1.1)
python3 ../../dll/patch_upscaler_dll.py --name 4.1.2-rdna4 amd_fidelityfx_upscaler_dx12.dll patched.dll out/
```

`PREPASS_HOIST=1` adds the two prepass steps that move float math (see below). Their output is listed in
`check/*-prepass-hoist.sha256`.

## Steps

The table shows the measured gain of each step on 4.1.1, in the order they were added, each against the build before it
(stable clocks, 3 pairs; the picture was identical after every step):

| Step | Tool | Shaders | 1080p | 1440p | 4K |
|---|---|---|---|---|---|
| Postpass: group the first pixel's 3×3 color taps; prepass: share repeated depth reads | `taphoist.py`, `dedupe.py` | postpass, prepass | −0.5% | −0.9% | −0.9% |
| Move operand-load groups ahead of the matrix ops, D = 4 | `groupmove.py` | passes 9, 11 | −3.4% | −5.2% | −3.9% |
| The same, D = 2 | `groupmove.py` | passes 4, 5, 10 | −1.2% | −0.9% | −0.5% |
| The same for the postpass, D = 4 | `groupmove_postpass.py` | postpass | −0.5% | −0.5% | −0.5% |
| *Prepass: hoist the second half's reads* (`PREPASS_HOIST=1`) | `xhoist.py` | prepass | −0.5% | −0.2% | −0.2% |
| Remove repeated load groups; forward entry-block array stores (pass 6) | `dedupg.py`, `m2r.py` | passes 4, 5, 6, 10 | −1.5% | −1.1% | −0.9% |
| Issue address math shared by several groups early | `groupmove.py` | passes 4, 5, 6, 9, 10, 11 | −0.8% | −1.0% | −0.6% |
| *Prepass: send "motion vector invalid" edges past their test* (`PREPASS_HOIST=1`) | `thread.py` | prepass | −0.4% | −0.4% | −0.5% |

What each tool does (all work on `dxc -dumpbin` output):

- **`groupmove.py in out D`**: an FP8 operand load is a group of AMD intrinsic calls, all with id byte 0x29:
  - the address `0x50000029`;
  - a placeholder `rawBufferLoad` and its `extractvalue`;
  - the insert `0x5100xx29`;
  - eight read-outs `0x52xxxx29`.

  The driver builds the `buffer_load` where the group sits. The tool moves each complete group, with its integer address
  math, up past at most D runs of matrix-op calls. It never stops a group inside a run, and groups never pass one
  another. Address math shared by several groups is issued as early as its operands allow.
- **`groupmove_postpass.py`**: the earlier `groupmove.py`, without the shared-address step. The postpass is 0.7% slower
  with the newer version, so it uses this one.
- **`dedupg.py`**: removes a load group that repeats an earlier one in the same block (same buffer, same address
  value). Its read-outs take the earlier group's values. Without this the driver merges the copies and places the loads
  itself, ignoring the order.
- **`m2r.py`**: forwards constant-index array stores in the entry block to the loads of the same slot (pass 6).
- **`taphoist.py`**: moves the postpass's ten SRV `textureLoad`s of the first pixel, with their coordinate math, to one
  point. No intrinsic, LDS access or store moves.
- **`dedupe.py`**: shares a prepass texture read with an earlier, dominating read whose coordinates are equal for every
  input (checked by evaluating both expressions in float32/int32 on random inputs; the expressions are not changed).
- **`xhoist.py`** and **`thread.py`** (only with `PREPASS_HOIST=1`): move the prepass's later SRV reads, and the float
  math computing their coordinates, into earlier blocks. They give the same picture on this driver. Another driver could
  contract the moved `fast` float math differently, so they are off by default.
- **`unname.py`**: restores dumpbin-style value names between tools.

Passes 1, 2, 3, 7, 8 and 12 compile to the same code either way and stay AMD's. Only the FP8 versions of the shaders
are rewritten (they use AMD's intrinsics through `atomicCompareExchange`). The INT8 and Lite shaders with the same names
are left alone.

## Checking the picture against AMD's

Run the timing kit once with AMD's DLL and once with the patched one, into the same results file, and compare the
fingerprints:

```bash
export FSR4TIME_800P=1                               # adds the 800p rows
fsr4time.exe --run amd results.txt full all          # in a folder with AMD's DLL
fsr4time.exe --run patched results.txt full all      # in a folder with the patched DLL
python3 ../../research/rdna4/compare_pictures.py results.txt amd patched     # expect "26 of 26 rows identical"
```

`../../research/rdna4/ab.sh` does the timing, with the same picture check.

The output files are AMD's shaders, rewritten; see [`../prebuilt/NOTICE.md`](../prebuilt/NOTICE.md) before sharing
them.
