# RX 9000 (RDNA4): finding and measuring the FP8 load stalls

[Back to research](../README.md)

These are the tools behind [`../../windows/rdna4/`](../../windows/rdna4) and issue #56. They let anyone repeat the
measurements on another RX 9000 card or driver.

| File | What it does |
|---|---|
| `scan_isa.py <dir> [co ...]` | Reads RDNA4 ISA text (`gfx1201_co<N>_comp.txt`, as RGA writes it) and simulates the load counters in program order. Reports, per shader, the WMMA count, how many instructions hide each load, and the **serialized waits**: a wait that retires the newest one or two loads less than 24 instructions after they were issued. |
| `isa_offline.sh <shader.dxil> ...` | Compiles shaders for gfx1201 with RGA's DX12 offline compiler (`RGA=<rga.exe>`) and runs `scan_isa.py` on each. RGA offline gave the same ISA as the runtime code objects in an RGP capture for every shader compared. |
| `co_to_dxbc.py <dll> <dir>` | Names the code objects of an RGP capture (exported as `co*.elf`) by the DXBC shader in AMD's DLL they came from. The ELF's `api_shader_hash` is the DXBC digest. |
| `ab.sh <pairs> <dir A> <dir B>` | A/B timing with the Windows timing kit at AMD's stable clocks (`RDP_DIR` = folder of `RadeonDeveloperPanelCLI.exe`). It alternates A B / B A, prints the per-pair ratios, and checks that every picture fingerprint of B equals A's. |
| `compare_pictures.py <results> <tag A> <tag B>` | Compares the picture fingerprints of two kit runs row by row. |
| `pmlog.c` | Logs the driver's PM sensors (ADL) every N ms. `ab.sh` uses it (`PMLOG=pmlog.exe`) to confirm each run's core clock. Build: `cl pmlog.c`. |

## Why stable clocks

In normal clock mode, kit timings of the same DLL on an RX 9070 XT swung by 20–40% between sessions. The sensor log
shows why: for the kit's one-call-then-wait load, the driver picks about 1475 MHz without reaching any power or heat
limit, and an undervolt raises that clock. In stable mode (`RadeonDeveloperPanelCLI -m clocks --clock-mode stable`,
1868 MHz), the same DLL against itself stays within about ±0.3%.

## Example: pass 9 of AMD's 4.1.2, before and after

```
$ RGA=rga.exe ./isa_offline.sh pass9_amd.dxbc pass9_rdna4.dxil
== pass9_amd
co0: 1079 ins, wmma 114
   serialized waits (n=0, <=2 loads, cover<24): 110
== pass9_rdna4
co0: 1075 ins, wmma 114
   serialized waits (n=0, <=2 loads, cover<24): 2
```

Per-pass findings on AMD 4.1.1 (4K, stable clocks, from an RGP capture of all 28 dispatches):

| Pass | µs | VGPRs | WMMA/ns | Serialized waits |
|---|---|---|---|---|
| 1, 2, 12 | 93 each | 167 | 18.0 | 0 |
| 7, 8 | 35 each | 209 | 19.0 | 0 |
| 4, 5, 10 | 50–52 each | 189 | 16.0 | 24 each |
| 6 | 35 | 79 | about 8 | 39 |
| 9 | 114 | 90 | 8.1 | 113 |
| 11 | 123 | 51 | 8.7 | 33 |
