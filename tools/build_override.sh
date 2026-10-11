#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_override.sh <dump-dir> [override-dir]
#
# Builds faster replacements for two FSR 4.1.1 (INT8 model) shaders from a vkd3d-proton shader
# dump (VKD3D_SHADER_DUMP_PATH) and writes them as <hash>.spv into the override directory
# (default: override/ next to this script), ready for VKD3D_SHADER_OVERRIDE.
#
#   postpass       image stores go through workgroup memory and are written in contiguous rows
#                  (postpass_direct.py: the first image goes there as it is computed, which keeps
#                  the register count low enough for 16 waves on RDNA2); before that, its small network gets the model passes'
#                  integer rounding and clamping (model_tail.py, model_clamp.py) and reads its
#                  nine neighbor cells without branches (postpass_taps.py). POSTPASS=0 skips it.
#   prepass        each thread of a quad finishes one of the four words of the model's input:
#                  12 exchanges between threads instead of 32 (prepass_route.py). PREPASS=0 skips it.
#   model passes   every model pass: the int8 rounding-and-clamping between layers is done with the
#                  clamp first (model_clamp.py) and the floating-point output scaling in integers
#                  (model_tail.py). MODEL=0 skips them.
#   model pass 11  the always-zero z coordinate becomes a constant, so the driver can unroll the
#                  pass's loops (zconst.py), and each row of its output is stored together
#                  (pass11_stores.py). PASS11=0 skips it; PASS11=rows changes only the stores and
#                  keeps the loops, which keeps the pass small (a version for integrated GPUs).
#
# The override directory can be shared by every game: files are named by shader hash, so variants
# from several games sit side by side and a game only picks up the ones it actually uses.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
if [[ $# -lt 1 || $1 == -h || $1 == --help ]]; then
    sed -n '3,17p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi
dump=$(realpath "$1")
out=$(realpath -m "${2:-$here/override}")
for tool in python3 spirv-dis spirv-as spirv-val; do
    command -v "$tool" >/dev/null || { echo "missing $tool (install python3 and SPIRV-Tools)"; exit 1; }
done
[[ -d $dump ]] || { echo "no such dump directory: $dump"; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Find the passes by their shape: compute shaders with packed int8 dot products.
DUMP_DIR=$dump python3 - <<'PY' > "$work/candidates"
import glob, os, struct
for f in sorted(glob.glob(os.environ['DUMP_DIR'] + '/*.spv')):
    d = open(f, 'rb').read()
    w = struct.unpack('<%dI' % (len(d) // 4), d[:len(d) // 4 * 4])
    if len(w) < 5 or w[0] != 0x07230203:
        continue
    i, compute, local, writes, dots, loops, swaps = 5, False, None, 0, 0, 0, 0
    while i < len(w) and w[i] >> 16:
        op, n = w[i] & 0xffff, w[i] >> 16
        if op == 15: compute = w[i + 1] == 5                      # OpEntryPoint GLCompute
        elif op == 16 and w[i + 2] == 17: local = w[i + 3:i + 6]  # OpExecutionMode LocalSize
        elif op == 99: writes += 1                                # OpImageWrite
        elif 4450 <= op <= 4455: dots += 1                        # OpSDot ... OpSUDotAccSat
        elif op == 246: loops += 1                                # OpLoopMerge
        elif op == 366: swaps += 1                                # OpGroupNonUniformQuadSwap
        i += n
    name = os.path.basename(f)[:-4]
    # 12 image writes, or 13 in the variants that also store the exposure value
    if os.environ.get('POSTPASS', '1') == '1' and compute and local == (256, 1, 1) and writes in (12, 13) and dots == 960:
        print('postpass', name)
    if os.environ.get('PREPASS', '1') == '1' and compute and local == (256, 1, 1) and writes == 1 and swaps == 32:
        print('prepass', name)
    is11 = compute and local == (64, 1, 1) and writes == 0 and dots == 272 and loops == 6
    if os.environ.get('PASS11', '1') != '0' and is11:
        print('pass11', name)
    elif os.environ.get('MODEL', '1') == '1' and compute and local == (64, 1, 1) and writes == 0 and dots > 0 and not is11:
        print('model', name)
PY
if [[ ! -s $work/candidates ]]; then
    echo "No FSR 4.1.1 INT8 shaders found in $dump."
    echo "Either FSR 4.1.1 (INT8) was not running during the dump, or this is another FSR version."
    exit 1
fi

mkdir -p "$out"
built=0
while read -r kind hash; do
    spirv-dis "$dump/$hash.spv" -o "$work/$hash.spvasm"
    if [[ $kind == model ]]; then
        # a model pass other than 11: the two exact rewrites, where the pass has what they look for
        python3 "$here/model_clamp.py" < "$work/$hash.spvasm" 2>/dev/null | python3 "$here/model_tail.py" > "$work/$hash.new.spvasm" 2>/dev/null
        cmp -s "$work/$hash.spvasm" "$work/$hash.new.spvasm" && continue      # nothing to rewrite in this pass
        spirv-as --target-env spv1.3 "$work/$hash.new.spvasm" -o "$work/$hash.spv"
        spirv-val --target-env vulkan1.3 "$work/$hash.spv"
        cp "$work/$hash.spv" "$out/$hash.spv"
        echo "$out/$hash.spv ($kind)"
        built=$((built + 1))
        continue
    fi
    if [[ $kind == postpass ]]; then
        script=postpass_direct.py; [[ ${POSTPASS_DIRECT:-1} == 0 ]] && script=postpass_lds_vkd3d.py      # 0: the store rewrite of the files up to release dll-2026-10-07
        # first the exact rewrites of the postpass's own small network (each leaves the text alone where it finds nothing)
        python3 "$here/model_tail.py" < "$work/$hash.spvasm" 2>/dev/null | python3 "$here/model_clamp.py" 2>/dev/null | python3 "$here/postpass_taps.py" > "$work/$hash.pre.spvasm" 2>/dev/null \
            && mv "$work/$hash.pre.spvasm" "$work/$hash.spvasm"
    elif [[ $kind == prepass ]]; then
        script=prepass_route.py
    elif [[ ${PASS11:-1} == rows ]]; then
        script=pass11_stores.py      # loops kept: only the stores change (for integrated GPUs)
    else
        script=zconst.py
    fi
    arg=; [[ $script == pass11_stores.py ]] && arg=rowc
    if ! python3 "$here/$script" $arg < "$work/$hash.spvasm" > "$work/$hash.new.spvasm"; then
        echo "skipped $hash ($kind): the shader does not have the expected structure"
        continue
    fi
    if [[ $kind == pass11 && ${PASS11:-1} != rows ]]; then
        # second step for pass 11: store each row of its output together (pass11_stores.py)
        if python3 "$here/pass11_stores.py" < "$work/$hash.new.spvasm" > "$work/$hash.new2.spvasm" 2>/dev/null; then
            mv "$work/$hash.new2.spvasm" "$work/$hash.new.spvasm"
        else
            echo "note: $hash (pass11): stores left as they are"
        fi
        if [[ ${MODEL:-1} == 1 ]]; then
            python3 "$here/model_clamp.py" < "$work/$hash.new.spvasm" 2>/dev/null | python3 "$here/model_tail.py" > "$work/$hash.new2.spvasm" 2>/dev/null \
                && mv "$work/$hash.new2.spvasm" "$work/$hash.new.spvasm"
        fi
    fi
    spirv-as --target-env spv1.3 "$work/$hash.new.spvasm" -o "$work/$hash.spv"
    spirv-val --target-env vulkan1.3 "$work/$hash.spv"
    cp "$work/$hash.spv" "$out/$hash.spv"
    echo "$out/$hash.spv ($kind)"
    built=$((built + 1))
done < "$work/candidates"
[[ $built -gt 0 ]] || exit 1
echo
echo "Launch option:  VKD3D_SHADER_OVERRIDE='Z:$out' %command%"
