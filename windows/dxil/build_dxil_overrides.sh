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
# Options (environment): PREPASS=hybrid (the prepass in the layout of AMD's FSR 4.1.2 RX 6000 driver prepass: 256
# threads, features through groupshared memory, one thread per cell; PQ_ORDER=amd keeps AMD 4.1.1's summation = its picture,
# PQ_ORDER=driver sums in the driver's order = that driver's picture), POSORDER=driver (the postpass's sample position computed in the order of AMD's
# FSR 4.1.2 RX 6000 driver postpass, which gives that driver's picture), PASS11=rows (compact pass 11, for integrated GPUs), DOT4=split (dot
# products as product + add, for RDNA2), DOT4=swap (the same RDNA2 fix by putting the constant operand
# second instead, as FSR 4.1.2 does; faster than split), INTCONV=direct (model passes without our output-scaling rewrite convert their
# rounded outputs straight to 32-bit integers, as AMD's FSR 4.1.2 RX 7000 driver does; same output), TAPS=0 (keep the branches around the postpass's
# neighborhood reads), PREPASS=0 / MODEL=0 (leave the prepass / the integer output scaling alone),
# POSTPASS_SMALL=amd (keep AMD's postpass code in the versions used at 1080p output and below,
# where the rewrite is slower on RDNA2; DOT4 and TAPS still apply to them), POSTPASS_STORES=amd (the same
# at every output size: AMD's image stores, no workgroup-memory rewrite; tuned for drivers that run the
# postpass 32-wide, where the rewrite gains nothing).
# SDKP11=<the game DLL of AMD's FSR SDK 2.4.0, amd_fidelityfx_upscaler_dx12.dll>: AMD's own pass 11 of its FSR 4.1.2 RX 6000 model,
# from that DLL (MIT license, AMD's notice in NOTICE.md), in the six INT8 pass 11 versions instead of the rewrite (sdk_pass11.py; same
# output as AMD's 4.1.1 pass 11, weights read in wider blocks).
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
built=0; failed=0
for f in "$src"/*.dxil; do
    name=$(strings -n 8 "$f" | grep -m1 -oE 'fsr4_model_v07_fp8_no_scale_(postpass|prepass|pass[0-9]+)$' || true)
    case $name in
        *_postpass) script=postpass_lds_dxil.py ;;
        *_prepass) case ${PREPASS:-1} in 1) script=prepass_route_dxil.py ;; hybrid) script=prepass_quad2_dxil.py ;; *) continue ;; esac ;;
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
    # POSORDER=driver: the postpass's sample position in the order of AMD's FSR 4.1.2 RX 6000 driver postpass (first, so the rewrites below work on it);
    # gives the driver postpass's picture, not 4.1.1's
    if [[ ${POSORDER:-} == driver && $name == *_postpass ]]; then
        python3 "$here/posorder_dxil.py" < "$work/in.ll" > "$work/in2.ll" 2>>"$work/posorder.log" && mv "$work/in2.ll" "$work/in.ll" || { echo "FAILED $(basename "$f"): sample position order"; failed=$((failed + 1)); continue; }
    fi
    # the postpass's last layer: its floating-point output scaling in integers (leaves the text alone where it finds none)
    if [[ $name == *_postpass && ${MODEL:-1} == 1 ]]; then
        python3 "$here/model_tail_dxil.py" < "$work/in.ll" > "$work/in2.ll" 2>/dev/null && mv "$work/in2.ll" "$work/in.ll"
    fi
    # the postpass's nine neighborhood reads without their branches (TAPS=0 keeps the branches)
    if [[ ${TAPS:-1} == 1 && $name == *_postpass ]]; then
        python3 "$here/postpass_taps_dxil.py" < "$work/in.ll" > "$work/in2.ll" && mv "$work/in2.ll" "$work/in.ll"
    fi
    # POSTPASS_SMALL=amd: the small output-size class (tensor rows of 962 pixels, 15392 bytes) keeps AMD's postpass.
    # POSTPASS_STORES=amd: every size class keeps AMD's stores.
    if [[ $name == *_postpass ]] && { [[ ${POSTPASS_STORES:-} == amd ]] || { [[ ${POSTPASS_SMALL:-} == amd ]] && grep -q 'i32 15392' "$work/in.ll"; }; }; then
        [[ ${DOT4:-} == split || ${DOT4:-} == swap || ${TAPS:-1} == 1 || ${MODEL:-1} == 1 || ${SHARE:-1} == 1 ]] || continue          # nothing to change: leave AMD's shader in place
        cp "$work/in.ll" "$work/out.ll"
    elif [[ $script == prepass_quad2_dxil.py ]]; then      # PREPASS=hybrid: this tool alone, then straight to assembly (no DCE: AMD's code is all used)
        if ! PQ_LAYOUT=hybrid PQ_ORDER=${PQ_ORDER:-amd} python3 "$here/$script" < "$work/in.ll" > "$work/out.ll" 2>/dev/null; then
            grep -q 'dot4AddPacked' "$work/in.ll" && { echo "FAILED $(basename "$f"): hybrid prepass"; failed=$((failed + 1)); }
            continue                               # an FP8 prepass (no int8 dot products) is left alone, as prepass_route_dxil.py does
        fi
        hyb=$((${hyb:-0} + 1))
        "$work/dxilasm" "$dxc_dir/lib/libdxcompiler.so" "$work/out.ll" "$out/$hash.dxil" || { echo "FAILED $(basename "$f"): assembly"; failed=$((failed + 1)); continue; }
        echo "$out/$hash.dxil  (prepass, hybrid, ${PQ_ORDER:-amd} order, from $(basename "$f"))"; built=$((built + 1)); continue
    elif ! python3 "$here/$script" $arg < "$work/in.ll" > "$work/out.ll" 2>/dev/null; then
        # INTCONV=direct: a model pass the output-scaling rewrite leaves alone gets its rounded outputs converted straight to 32-bit integers, as AMD's
        # FSR 4.1.2 RX 7000 driver passes do (bit-exact), then straight to assembly
        if [[ ${INTCONV:-} == direct && $script == model_tail_dxil.py ]] && python3 "$here/i32conv_dxil.py" < "$work/in.ll" > "$work/out.ll" 2>/dev/null; then
            "$work/dxilasm" "$dxc_dir/lib/libdxcompiler.so" "$work/out.ll" "$out/$hash.dxil" || { echo "FAILED $(basename "$f"): assembly"; failed=$((failed + 1)); continue; }
            echo "$out/$hash.dxil  (${name##*_}, direct conversions, from $(basename "$f"))"; built=$((built + 1)); icv=$((${icv:-0} + 1)); continue
        fi
        [[ $script == model_tail_dxil.py || $script == prepass_route_dxil.py ]] || echo "skipped $(basename "$f"): not the expected structure"
        continue                                   # a model pass without that code is left alone
    fi
    if [[ ${SHARE:-1} == 1 && $name == *_postpass ]]; then      # SHARE=1 (the default since release dll-2026-10-15; SHARE=0 as before): color taps converted once per thread
        python3 "$here/postpass_sharetaps_dxil.py" < "$work/out.ll" > "$work/out2.ll" || { echo "FAILED $(basename "$f"): shared taps"; failed=$((failed + 1)); continue; }
        mv "$work/out2.ll" "$work/out.ll"
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
    # DOT4=swap: constant operand second in every postpass dot product (bit-exact; RDNA2's Windows driver ghosts on the constant-first form).
    if [[ ${DOT4:-} == swap && $name == *_postpass ]]; then
        python3 "$here/dotswap_dxil.py" < "$work/out.ll" > "$work/out2.ll" 2>/dev/null && mv "$work/out2.ll" "$work/out.ll"
    fi
    # last: take out the code the rewrites replaced but left in place, so the driver need not (DCE=0 leaves it in)
    if [[ ${DCE:-1} == 1 ]]; then
        python3 "$here/dce_dxil.py" < "$work/out.ll" > "$work/out2.ll" 2>/dev/null || { echo "FAILED $(basename "$f"): unused code could not be removed"; failed=$((failed + 1)); continue; }
        mv "$work/out2.ll" "$work/out.ll"
    fi
    "$work/dxilasm" "$dxc_dir/lib/libdxcompiler.so" "$work/out.ll" "$out/$hash.dxil"
    # INTCONV=direct on a rewritten model pass that still converts through 16 bits (passes 4 and 5): the same step on the assembled shader
    if [[ ${INTCONV:-} == direct && $name == *_pass[0-9]* ]]; then
        "$dxc_dir/bin/dxc" -dumpbin "$out/$hash.dxil" > "$work/as.ll"
        if python3 "$here/i32conv_dxil.py" < "$work/as.ll" > "$work/out2.ll" 2>/dev/null; then
            "$work/dxilasm" "$dxc_dir/lib/libdxcompiler.so" "$work/out2.ll" "$out/$hash.dxil" || { echo "FAILED $(basename "$f"): assembly"; failed=$((failed + 1)); continue; }
            icv=$((${icv:-0} + 1))
        fi
    fi
    echo "$out/$hash.dxil  (${name##*_}, from $(basename "$f"))"
    built=$((built + 1))
done
[[ $built -gt 0 ]] || { echo "no FSR 4.1.1 INT8 postpass or pass 11 in $src"; exit 1; }
if [[ -n ${SDKP11:-} ]]; then python3 "$here/sdk_pass11.py" "$SDKP11" "$out" "$dxc_dir" "$work/dxilasm" || { echo "FAILED: AMD FSR SDK pass 11"; exit 1; }; fi
[[ ${PREPASS:-1} == hybrid ]] && echo "hybrid prepasses (${PQ_ORDER:-amd} order): ${hyb:-0}"
[[ ${INTCONV:-} == direct ]] && echo "model passes with direct conversions: ${icv:-0}"
[[ ${POSORDER:-} == driver ]] && echo "sample position order: $(sort "$work/posorder.log" | uniq -c | tr '\n' ' ')"
[[ $failed -eq 0 ]] || { echo "$failed shaders FAILED"; exit 1; }
