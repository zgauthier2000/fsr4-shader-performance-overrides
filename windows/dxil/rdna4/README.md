# RDNA4 FP8 load reorder

Exact rewrites of the FSR 4 FP8 network shaders. The RX 9000 driver then issues the matrix-operand and texture loads
earlier. The picture stays AMD's byte for byte. Details and measurements are in issue #56.

On an RX 9070 XT at stable clocks, the patched DLL is faster than AMD's (1080p / 1440p / 4K):
- 4.1.1.2740: −8.2% / −10.1% / −7.8%
- 4.1.2.4555: −7.8% / −10.1% / −8.1%

All 26 kit rows give identical pictures for both versions.

```bash
DXC=/path/to/dxc DXILASM=/path/to/dxilasm DXCOMPILER=/path/to/dxcompiler \
  ./build_rdna4_fp8.sh amd_fidelityfx_upscaler_dx12.dll out/
python3 ../../../dll/patch_upscaler_dll.py --name 4.1.2-g1 amd_fidelityfx_upscaler_dx12.dll patched.dll out/
```

The build script runs these tools on `dxc -dumpbin` output:

| Tool | What it does |
|---|---|
| `groupmove.py` | Moves each complete operand-load group (intrinsic id byte 0x29) up past at most D runs of matrix-op calls. Pure address math shared by several groups is issued as early as its operands allow. |
| `groupmove_postpass.py` | The earlier `groupmove.py`, which doesn't move shared address math early. The postpass is faster with it. |
| `dedupg.py` | Removes a load group that repeats an earlier one in the same block (same buffer and address). Its read-outs take the earlier group's values. |
| `m2r.py` | Forwards constant-index array stores in the entry block to the loads that read them (pass 6). |
| `taphoist.py` | Postpass: moves the first pixel's 3×3 color `textureLoad`s, with their coordinate math, to one point. |
| `dedupe.py` | Prepass: shares depth reads whose coordinates are equal for every input. |
| `xhoist.py` | Prepass: hoists the second half's SRV reads into the loop's first block. |
| `thread.py` | Prepass: sends the "motion vector invalid" edges straight past the merge block that tests them. |
| `unname.py` | Restores dumpbin-style value names after `taphoist.py` and `dedupe.py`. |

Only the FP8 versions are rewritten. The INT8 and Lite shaders with the same names stay AMD's. The output is derived
from AMD's shaders; see `../../prebuilt/NOTICE.md` before sharing it.
