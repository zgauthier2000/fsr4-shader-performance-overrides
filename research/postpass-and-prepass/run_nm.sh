#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# As used: expects the 12 model passes as passN.spvasm/.spv next to it and mbench in ../bench.
# Fusion ceiling probe: each model pass as is, without stores, with cached loads, both.
set -e
cd -- "$(dirname -- "$0")"
for mode in st ld both; do
    mkdir -p exp/nm/$mode
    for k in $(seq 1 12); do
        src=pass$k.spvasm; [[ $k = 11 ]] && src=exp/z/pass11.spvasm
        python3 nomem.py $mode < $src > exp/nm/$mode/pass$k.spvasm 2> exp/nm/$mode/pass$k.log
        spirv-as --target-env spv1.3 exp/nm/$mode/pass$k.spvasm -o exp/nm/$mode/pass$k.spv
        spirv-val --target-env vulkan1.3 exp/nm/$mode/pass$k.spv
    done
done
grep -h . exp/nm/ld/*.log | sort | uniq -c
cd ../bench
levels=(0 1 1 2 2 2 3 3 3 3 2 2 1)
for k in $(seq 1 12); do
    b=../model/pass$k.spv; [[ $k = 11 ]] && b=../model/exp/z/pass11.spv
    ./mbench "${levels[$k]}" $b ../model/exp/nm/{st,ld,both}/pass$k.spv 2>&1 | grep median |
        awk -v k=$k '{printf "%s%s", (NR==1 ? "pass" k : ""), "  " $4} END {print ""}'
done
