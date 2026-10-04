#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_dxil_overrides.sh <dir-with-dxil> <out-dir>
#
# Builds the DXIL replacements the ReShade add-on loads (Windows / native D3D12) from AMD's
# original FSR 4.1.1 shaders: every *.dxil in the input directory that is the INT8 postpass or
# model pass 11 is rewritten, assembled and signed, and written as <hash>.dxil, where <hash> is
# the hash in the original container's header (the name the add-on looks for).
# The input can be a vkd3d-proton shader dump (VKD3D_SHADER_DUMP_PATH writes the DXIL too).
# Needs DXC (dxc and libdxcompiler.so; set DXC_DIR to the unpacked Linux release) and g++.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
[[ $# -eq 2 ]] || { sed -n '3,11p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
src=$(realpath "$1")
out=$(realpath -m "$2")
dxc_dir=${DXC_DIR:-$here/../toolchain/dxc}
export LD_LIBRARY_PATH=$dxc_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
[[ -x $dxc_dir/bin/dxc ]] || { echo "DXC not found in $dxc_dir (set DXC_DIR)"; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
g++ -std=c++17 -O1 -I"$dxc_dir/include" "$here/../tools/dxilasm.cpp" -ldl -o "$work/dxilasm"
mkdir -p "$out"
built=0
for f in "$src"/*.dxil; do
    name=$(strings -n 8 "$f" | grep -m1 -oE 'fsr4_model_v07_fp8_no_scale_(postpass|pass11)$' || true)
    case $name in
        *_postpass) script=postpass_lds_dxil.py ;;
        *_pass11) script=zconst_dxil.py ;;
        *) continue ;;
    esac
    hash=$(xxd -s 4 -l 16 -p "$f")
    "$dxc_dir/bin/dxc" -dumpbin "$f" > "$work/in.ll"
    if ! python3 "$here/$script" < "$work/in.ll" > "$work/out.ll"; then
        echo "skipped $(basename "$f"): not the expected structure"
        continue
    fi
    if [[ $script == zconst_dxil.py ]] && python3 "$here/pass11_stores_dxil.py" < "$work/out.ll" > "$work/out2.ll" 2>/dev/null; then
        mv "$work/out2.ll" "$work/out.ll"      # pass 11, second step: store each row together
    fi
    "$work/dxilasm" "$dxc_dir/lib/libdxcompiler.so" "$work/out.ll" "$out/$hash.dxil"
    echo "$out/$hash.dxil  (${name##*_}, from $(basename "$f"))"
    built=$((built + 1))
done
[[ $built -gt 0 ]] || { echo "no FSR 4.1.1 INT8 postpass or pass 11 in $src"; exit 1; }
