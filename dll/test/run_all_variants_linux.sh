#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Dumps Proton's translation of every postpass / pass 11 version (AMD's DLL), build
# the Linux overrides from the dumps, then run each combination with the overrides and compare.
cd -- "$(dirname -- "$0")"
# Needs fsr4var.exe, AMD's DLL as all_original.dll and the loader next to this script (see
# run_all_variants.sh), umu-run and a Proton build.
export WINEPREFIX=$PWD/pfx GAMEID=umu-fsr4cap WINEDEBUG=-all PROTONPATH=${PROTONPATH:-$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton11-7-x86_64}
BASES=("1280x720 1920x1080" "640x360 1920x1080" "2560x1440 3840x2160" "1280x720 3840x2160" "3413x1920 5120x2880" "1706x960 5120x2880")
COMBOS=(0x21:0 0x121:0 0x121:2 0x121:4 0x0:0 0x100:0 0x100:2 0x100:4)
cp all_original.dll amd_fidelityfx_upscaler_dx12.dll
mkdir -p lall/dump lall/ref lall/override
for base in "${BASES[@]}"; do set -- $base; r=$1; o=$2
    for combo in "${COMBOS[@]}"; do ctx=${combo%%:*}; disp=${combo##*:}; tag=${r}_${o}_${ctx}_${disp}
        rm -rf lall/tmp; mkdir -p lall/tmp; rm -f output_$o.raw
        FSR_CTX_FLAGS=$ctx FSR_DISP_FLAGS=$disp VKD3D_SHADER_DUMP_PATH="Z:$PWD/lall/tmp" timeout 280 umu-run "$PWD/fsr4var.exe" 4.1.1 $r $o 4 noise > umu.log 2>&1
        mv output_$o.raw lall/ref/$tag.raw 2>/dev/null || { echo "$tag: REFERENCE RUN FAILED"; continue; }
        for f in lall/tmp/*.dxil; do
            strings -n 8 "$f" | grep -qE 'no_scale_(postpass|pass11)$' || continue
            cp -n "$f" "${f%.dxil}.spv" lall/dump/
        done
    done
done
echo "dumped $(ls lall/dump/*.spv | wc -l) shaders"
../../build_override.sh "$PWD/lall/dump" "$PWD/lall/override" | grep -c '\.spv ('
for base in "${BASES[@]}"; do set -- $base; r=$1; o=$2
    for combo in "${COMBOS[@]}"; do ctx=${combo%%:*}; disp=${combo##*:}; tag=${r}_${o}_${ctx}_${disp}
        [[ -f lall/ref/$tag.raw ]] || continue
        rm -f output_$o.raw
        FSR_CTX_FLAGS=$ctx FSR_DISP_FLAGS=$disp VKD3D_SHADER_OVERRIDE="Z:$PWD/lall/override" timeout 280 umu-run "$PWD/fsr4var.exe" 4.1.1 $r $o 4 noise > umu.log 2>&1
        if [[ ! -f output_$o.raw ]]; then v="OVERRIDE RUN FAILED"; elif cmp -s output_$o.raw lall/ref/$tag.raw; then v=IDENTICAL; else v=DIFFERS; fi
        echo "$tag: output $v"; rm -f output_$o.raw lall/ref/$tag.raw
    done
done
echo "=== linux_all done"
