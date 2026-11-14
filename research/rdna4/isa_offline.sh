#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# isa_offline.sh <shader.dxil> [more.dxil ...]: compiles each shader for gfx1201 (RX 9070 / 9070 XT) with RGA's DX12
# offline compiler and runs scan_isa.py on the result. RGA offline gave the same ISA as the runtime code objects in an
# RGP capture for every shader checked. Set RGA to the rga executable of the Radeon Developer Tool Suite.
set -u
here=$(cd "$(dirname "$0")" && pwd)
[[ -n ${RGA:-} ]] || { echo "set RGA to rga(.exe)"; exit 1; }
py=${PYTHON:-python3}
for f in "$@"; do
    t=$(mktemp -d); n=$(basename "$f"); n=${n%.*}
    "$RGA" -s dx12 -c gfx1201 --cs-blob "$f" --isa "$t/$n.isa" > "$t/rga.log" 2>&1
    isa=$(ls "$t"/gfx1201_*_comp.isa 2>/dev/null | head -1)
    [[ -n $isa ]] || { echo "$n: RGA failed, see $t/rga.log"; continue; }
    cp "$isa" "$t/gfx1201_co0_comp.txt"
    echo "== $n"; PYTHONIOENCODING=utf-8 "$py" -I "$here/scan_isa.py" "$t" 0
    rm -rf "$t"
done
