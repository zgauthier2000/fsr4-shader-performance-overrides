#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_lossy_dxil.sh <dir with AMD's original .dxil> <dir with the exact replacement set> <out-dir>
#
# NOT bit-exact. Builds the lossy DXIL set of the test build (see README.md): a copy of the exact
# set (windows/prebuilt/fsr4-overrides, or the output of windows/dxil/build_dxil_overrides.sh) in
# which 27 model-pass shaders are replaced: passes 1, 2, 4, 5, 7, 8, 9, 10 and 12 of the normal
# model, for the three output-size classes. Weights are folded in passes 1 (4 words of 36), 5 (18),
# 10 (18) and 12 (20); the rounding between layers is changed in all nine. The passes that only
# the Ultra Performance model uses are left exact: the settings were not tuned for it.
# AMD's originals come from dll/extract_shaders.py. Needs DXC (set DXC_DIR) and g++.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
[[ $# -eq 3 ]] || { sed -n '3,11p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
src=$(realpath "$1"); exact=$(realpath "$2"); out=$(realpath -m "$3")
dxc_dir=${DXC_DIR:-$here/../../windows/toolchain/dxc}
export LD_LIBRARY_PATH=$dxc_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
[[ -x $dxc_dir/bin/dxc ]] || { echo "DXC not found in $dxc_dir (set DXC_DIR)"; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
g++ -std=c++17 -O1 -I"$dxc_dir/include" "$here/../../windows/tools/dxilasm.cpp" -ldl -o "$work/dxilasm"
mkdir -p "$out"
cp "$exact"/*.dxil "$out"/
declare -A K=([pass1]=4 [pass5]=18 [pass10]=18 [pass12]=20)
# the hash in the container header of each AMD shader to replace, and its pass
while read -r hash pass; do
    "$dxc_dir/bin/dxc" -dumpbin "$src/$hash.dxil" > "$work/a.ll"
    if [[ -n ${K[$pass]:-} ]]; then
        python3 "$here/wfold_dxil.py" "${K[$pass]}" < "$work/a.ll" > "$work/b.ll" 2>/dev/null; mv "$work/b.ll" "$work/a.ll"
    fi
    python3 "$here/wround_dxil.py" < "$work/a.ll" > "$work/b.ll" 2>/dev/null; mv "$work/b.ll" "$work/a.ll"
    # the exact integer form of the output scaling, where the pass has it
    if python3 "$here/../../windows/dxil/model_tail_dxil.py" < "$work/a.ll" > "$work/b.ll" 2>/dev/null; then mv "$work/b.ll" "$work/a.ll"; fi
    "$work/dxilasm" "$dxc_dir/lib/libdxcompiler.so" "$work/a.ll" "$out/$hash.dxil"
    echo "$out/$hash.dxil  ($pass, lossy)"
done <<'LIST'
5b67737eafe17f21b051a0efe30f175e pass1
c7c1e0184dcc4b6a3fca6d6a8b873965 pass1
be6a3617b6dcf44f5fab8f1571652cbb pass1
755ca70ed4e5d1fc8231e6d567c881b7 pass2
f5c7d8b41d4ce7a8f9b65a40f2b959b6 pass2
6433f67788cd97c07342a7bbcfbe0d4a pass2
9520d91584508b33703ce28a8ed5918c pass4
910903c6fe68cdd5c764fcfadd960708 pass4
c8c67dfe3600667f7bf4ba6220841361 pass4
a1b5a3ce6b5aa7fc555e7c90c5622109 pass5
145b4d28de375081586518969e18468c pass5
239f5f5aec7daa0c54457b96b65f4657 pass5
97a2b2f4c0a65db62bd69017f3742b40 pass7
4f022ae31e77e0e3d374c8a539aba9e7 pass7
4c4c4c24f96459c00c1ad1e35e6d68ee pass7
a2e3a7abe4b428b029c2f68c53894577 pass8
e1660f6ab141919f71844987762c129e pass8
442dc6bcfb88e36336388eb37a4d7edb pass8
94594de450011ece269b3da6ecd6ca26 pass9
7f092598701939a238264b0c4f2a4c5f pass9
b8d0133b5170b06588642fb9c32279ca pass9
260cb9f229a3321e97b016bf3c0fad9f pass10
54a1ac719744f69d69c072bce3492e9e pass10
a5ae39a2b7d0348769e6c2a0e1c86f3f pass10
cef018ba31e6e83b17815b93c15d89b0 pass12
938540a6ac6e404d702fd450f5fa76ba pass12
8cc4fd043a8fc43ab3fbf7124f6cc591 pass12
LIST
