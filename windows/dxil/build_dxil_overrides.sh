#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_dxil_overrides.sh <dir-with-dxil> <out-dir>
#
# Builds the DXIL replacements the ReShade add-on loads (Windows / native D3D12) from AMD's
# original FSR 4.1.1 shaders: every *.dxil in the input directory that is the INT8 postpass or a
# model pass with something to rewrite (pass 11: the store and loop rewrites; passes 1, 2, 9, 10, 11
# and 12: the floating-point output scaling in integers, model_tail_dxil.py; MODEL=0 skips that) is rewritten, assembled and signed, and written as <hash>.dxil, where <hash> is
# the hash in the original container's header (the name the add-on looks for).
# The input can be a vkd3d-proton shader dump (VKD3D_SHADER_DUMP_PATH writes the DXIL too).
# Options (environment): PASS11=rows (compact pass 11, for integrated GPUs), DOT4=split (dot
# products as product + add, for RDNA2), TAPS=0 (keep the branches around the postpass's
# neighbourhood reads), PREPASS=0 / MODEL=0 (leave the prepass / the integer output scaling alone),
# POSTPASS_SMALL=amd (keep AMD's postpass code in the versions used at 1080p output and below,
# where the rewrite is slower on RDNA2; DOT4 and TAPS still apply to them).
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
    name=$(strings -n 8 "$f" | grep -m1 -oE 'fsr4_model_v07_fp8_no_scale_(postpass|prepass|pass[0-9]+)$' || true)
    case $name in
        *_postpass) script=postpass_lds_dxil.py ;;
        *_prepass) [[ ${PREPASS:-1} == 1 ]] || continue; script=prepass_route_dxil.py ;;
        *_pass11) script=zconst_dxil.py; [[ ${PASS11:-1} == rows ]] && script=pass11_stores_dxil.py ;;
        *_pass[0-9]*) [[ ${MODEL:-1} == 1 ]] || continue; script=model_tail_dxil.py ;;
        *) continue ;;
    esac
    hash=$(xxd -s 4 -l 16 -p "$f")
    "$dxc_dir/bin/dxc" -dumpbin "$f" > "$work/in.ll"
    # Only the INT8 model's shaders (packed int8 dot products), and not the debug-view versions.
    [[ $name == *_prepass ]] || grep -q 'dot4AddPacked' "$work/in.ll" || continue
    grep -q 'rw_debug_visualization' "$work/in.ll" && continue
    arg=; [[ $script == pass11_stores_dxil.py ]] && arg=rowc
    # the postpass's last layer: its floating-point output scaling in integers (leaves the text alone where it finds none)
    if [[ $name == *_postpass && ${MODEL:-1} == 1 ]]; then
        python3 "$here/model_tail_dxil.py" < "$work/in.ll" > "$work/in2.ll" 2>/dev/null && mv "$work/in2.ll" "$work/in.ll"
    fi
    # the postpass's nine neighbourhood reads without their branches (TAPS=0 keeps the branches)
    if [[ ${TAPS:-1} == 1 && $name == *_postpass ]]; then
        python3 "$here/postpass_taps_dxil.py" < "$work/in.ll" > "$work/in2.ll" && mv "$work/in2.ll" "$work/in.ll"
    fi
    # POSTPASS_SMALL=amd: the small output-size class (tensor rows of 962 pixels, 15392 bytes) keeps AMD's postpass.
    if [[ ${POSTPASS_SMALL:-} == amd && $name == *_postpass ]] && grep -q 'i32 15392' "$work/in.ll"; then
        [[ ${DOT4:-} == split || ${TAPS:-1} == 1 || ${MODEL:-1} == 1 ]] || continue          # nothing to change: leave AMD's shader in place
        cp "$work/in.ll" "$work/out.ll"
    elif ! python3 "$here/$script" $arg < "$work/in.ll" > "$work/out.ll" 2>/dev/null; then
        [[ $script == model_tail_dxil.py || $script == prepass_route_dxil.py ]] || echo "skipped $(basename "$f"): not the expected structure"
        continue                                   # a model pass without that code is left alone
    fi
    if [[ $script == zconst_dxil.py ]] && python3 "$here/pass11_stores_dxil.py" < "$work/out.ll" > "$work/out2.ll" 2>/dev/null; then
        mv "$work/out2.ll" "$work/out.ll"      # pass 11, second step: store each row together
    fi
    # pass 11, last step: its output scaling in integers
    if [[ $name == *_pass11 && ${MODEL:-1} == 1 ]]; then
        python3 "$here/model_tail_dxil.py" < "$work/out.ll" > "$work/out2.ll" 2>/dev/null && mv "$work/out2.ll" "$work/out.ll"
    fi
    # DOT4=split: the postpass's accumulating int8 dot products become dot + add (for RDNA2).
    if [[ ${DOT4:-} == split && $name == *_postpass ]]; then
        python3 "$here/dot4_split_dxil.py" < "$work/out.ll" > "$work/out2.ll" 2>/dev/null && mv "$work/out2.ll" "$work/out.ll"
    fi
    "$work/dxilasm" "$dxc_dir/lib/libdxcompiler.so" "$work/out.ll" "$out/$hash.dxil"
    echo "$out/$hash.dxil  (${name##*_}, from $(basename "$f"))"
    built=$((built + 1))
done
[[ $built -gt 0 ]] || { echo "no FSR 4.1.1 INT8 postpass or pass 11 in $src"; exit 1; }
