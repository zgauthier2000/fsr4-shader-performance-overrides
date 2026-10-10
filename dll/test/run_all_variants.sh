#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Runs AMD's FSR 4.1.1 DLL under Proton in every combination that selects a different postpass or
# pass 11 (3 output-size classes x 2 models x 8 exposure and color-space setups = 48), first
# unchanged and then patched by ../patch_upscaler_dll.py, and compares the output images byte for
# byte. A shader dump of each run shows which versions ran and that both were replaced.
#
# Put these next to this script first:
#   fsr4var.exe                        built from ../../research/pruning/fsr4img.c
#   amd_fidelityfx_upscaler_dx12.dll   4.1.1.2740 (AMD's, unchanged), and
#   amd_fidelityfx_loader_dx12.dll     2.3.0
# Needs umu-run and a Proton build (PROTONPATH). REPL_DIR: another replacement folder.
cd -- "$(dirname -- "$0")"
[[ -f all_original.dll ]] || cp amd_fidelityfx_upscaler_dx12.dll all_original.dll
python3 ../patch_upscaler_dll.py all_original.dll all_patched.dll ${REPL_DIR:+"$REPL_DIR"} > /dev/null || exit 1
export WINEPREFIX=$PWD/pfx GAMEID=umu-fsr4cap WINEDEBUG=-all PROTONPATH=${PROTONPATH:-$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton11-7-x86_64}
hashes() {  # hashes <dump dir> -> "postpass pass11"
    local post= p11= f n
    for f in "$1"/*.dxil; do
        n=$(strings -n 8 "$f" | grep -m1 -oE 'no_scale_(postpass|pass11)$') || continue
        [[ $n == *postpass ]] && post=$(xxd -s 4 -l 16 -p "$f"); [[ $n == *pass11 ]] && p11=$(xxd -s 4 -l 16 -p "$f")
    done
    echo "$post $p11"
}
for base in "1280x720 1920x1080" "640x360 1920x1080" "2560x1440 3840x2160" "1280x720 3840x2160" "3413x1920 5120x2880" "1706x960 5120x2880"; do
    set -- $base; r=$1; o=$2
    for combo in 0x21:0 0x121:0 0x121:2 0x121:4 0x0:0 0x100:0 0x100:2 0x100:4; do
        ctx=${combo%%:*}; disp=${combo##*:}
        rm -rf va vb; mkdir -p va vb
        cp all_original.dll amd_fidelityfx_upscaler_dx12.dll; rm -f output_$o.raw
        FSR_CTX_FLAGS=$ctx FSR_DISP_FLAGS=$disp VKD3D_SHADER_DUMP_PATH="Z:$PWD/va" timeout 280 umu-run "$PWD/fsr4var.exe" 4.1.1 $r $o 4 noise > umu.log 2>&1
        mv output_$o.raw va.raw 2>/dev/null || { echo "$r->$o ctx=$ctx disp=$disp: ORIGINAL RUN FAILED"; continue; }
        cp all_patched.dll amd_fidelityfx_upscaler_dx12.dll
        FSR_CTX_FLAGS=$ctx FSR_DISP_FLAGS=$disp VKD3D_SHADER_DUMP_PATH="Z:$PWD/vb" timeout 280 umu-run "$PWD/fsr4var.exe" 4.1.1 $r $o 4 noise > umu.log 2>&1
        ha=$(hashes va); hb=$(hashes vb)
        rep=0; [[ ${ha% *} != "${hb% *}" ]] && rep=$((rep+1)); [[ ${ha#* } != "${hb#* }" ]] && rep=$((rep+1))
        if [[ ! -f output_$o.raw ]]; then v="PATCHED RUN FAILED"; elif cmp -s output_$o.raw va.raw; then v=IDENTICAL; else v=DIFFERS; fi
        echo "$r->$o ctx=$ctx disp=$disp: postpass ${ha% *} pass11 ${ha#* } replaced $rep/2 output $v"
        rm -f output_$o.raw va.raw
    done
done
cp all_original.dll amd_fidelityfx_upscaler_dx12.dll
echo "=== verify_all done"
