#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_rdna4_fp8.sh <amd_fidelityfx_upscaler_dx12.dll> <out dir> [work dir]
#
# Rewrites every FP8 network shader of AMD's FSR 4.1.1.2740 or 4.1.2.4555 DLL so that the RDNA4 driver issues its loads
# earlier, and writes the results as <out dir>/<hash>.dxil for ../../../dll/patch_upscaler_dll.py. The picture stays
# AMD's byte for byte (checked with the timing kit on RX 9070 XT in all 26 rows, both versions). Per pass:
#   pass 9, 11       groupmove D=4
#   pass 4, 5, 10    dedupg, groupmove D=2
#   pass 6           m2r, dedupg, groupmove D=4
#   postpass         taphoist, unname, groupmove_postpass D=4
#   prepass          dedupe, unname, xhoist, thread
# Passes 1, 2, 3, 7, 8 and 12 compile to the same code either way and stay AMD's. Only the FP8 versions are touched
# (they use AMD's intrinsics through atomicCompareExchange); the INT8 and Lite shaders, which share the names, are not.
#
# Needs: DXC (path to dxc, for -dumpbin), DXILASM (the dxilasm tool from ../../tools/dxilasm.cpp) and DXCOMPILER (the
# dxcompiler library dxilasm loads), and Python 3 (PYTHON, default python3).
set -u
here=$(cd "$(dirname "$0")" && pwd)
[[ $# -ge 2 ]] || { sed -n '3,17p' "$0" | cut -c3-; exit 1; }
dll=$1; out=$2; work=${3:-$(mktemp -d)}
py=${PYTHON:-python3}
for v in DXC DXILASM DXCOMPILER; do [[ -n ${!v:-} ]] || { echo "set $v"; exit 1; }; done
mkdir -p "$out" "$work/src"
"$py" -I - "$dll" "$work/src" <<'PY'
import re, struct, sys
d = open(sys.argv[1], 'rb').read(); i = 0; seen = set()
while (i := d.find(b'DXBC', i)) >= 0:
    n = struct.unpack_from('<I', d, i + 24)[0]
    if 32 < n < 8_000_000 and b'DXIL' in d[i:i + n]:
        b = d[i:i + n]; m = re.search(rb'fsr4_model_v07_fp8_no_scale_(postpass|prepass|pass[0-9]+)\x00', b)
        if m and (h := d[i + 4:i + 20].hex()) not in seen:
            seen.add(h); open(f'{sys.argv[2]}/{m.group(1).decode()}.{h}.dxbc', 'wb').write(b)
        i += n; continue
    i += 4
print(len(seen), 'network shaders in the DLL')
PY
built=0; failed=0
for f in "$work"/src/*.dxbc; do
    b=$(basename "$f" .dxbc); p=${b%%.*}; h=${b#*.}; L=$work/$b
    case $p in
        pass9|pass11) steps="groupmove:4";;
        pass4|pass5|pass10) steps="dedupg groupmove:2";;
        pass6) steps="m2r dedupg groupmove:4";;
        postpass) steps="taphoist unname groupmove_postpass:4";;
        prepass) steps="dedupe unname xhoist thread";;
        *) continue;;
    esac
    "$DXC" -dumpbin "$f" > "$L.0.ll" 2>/dev/null
    grep -q '@dx.op.atomicCompareExchange' "$L.0.ll" || continue      # not the FP8 version
    cur=$L.0.ll; k=0; ok=1
    for s in $steps; do
        k=$((k + 1)); tool=${s%%:*}; arg=; [[ $s == *:* ]] && arg=${s#*:}
        "$py" -I "$here/$tool.py" "$cur" "$L.$k.ll" $arg > /dev/null 2>> "$work/errors.log" || { echo "FAILED $p $h: $tool"; ok=0; break; }
        cur=$L.$k.ll
    done
    [[ $ok == 1 ]] && "$DXILASM" "$DXCOMPILER" "$cur" "$out/$h.dxil" > /dev/null 2>> "$work/errors.log" || { [[ $ok == 1 ]] && echo "FAILED $p $h: assembly"; failed=$((failed + 1)); continue; }
    built=$((built + 1))
done
echo "$built shaders written to $out, $failed failed"
[[ $failed == 0 ]]
