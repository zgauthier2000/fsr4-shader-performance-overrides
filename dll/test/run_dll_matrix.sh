#!/usr/bin/env bash
# Runs AMD's FSR 4.1.1 DLL under Proton for several output sizes and ratios, first unchanged and
# then patched by ../patch_upscaler_dll.py, and compares the output images byte for byte. A shader
# dump of the patched run confirms that the patched shaders ran (vkd3d-proton translates the
# phased postpass with a 3072-float workgroup array, which AMD's original does not have).
#
# Put these next to this script first:
#   fsr4cap.exe                        built from tools/fsr4cap of bbport
#                                      (https://github.com/deadinside28/bloodborne_pc)
#   amd_fidelityfx_upscaler_dx12.dll   4.1.1.2740 (AMD's, unchanged), and
#   amd_fidelityfx_loader_dx12.dll     2.3.0
# Needs umu-run and a Proton build (PROTONPATH).
set -u
cd -- "$(dirname -- "$0")"
export WINEPREFIX=$PWD/pfx GAMEID=umu-fsr4cap WINEDEBUG=-all
export PROTONPATH=${PROTONPATH:-$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton11-7-x86_64}
frames=${FRAMES:-4}
mkdir -p dll
[[ -f dll/original.dll ]] || cp amd_fidelityfx_upscaler_dx12.dll dll/original.dll
# REPL_DIR: a replacement folder other than ../../windows/prebuilt/fsr4-overrides
python3 ../patch_upscaler_dll.py dll/original.dll dll/patched.dll ${REPL_DIR:+"$REPL_DIR"} > /dev/null || exit 1
run() {  # run <dll> <render> <out> <dump-dir or ''>
    cp "$1" amd_fidelityfx_upscaler_dx12.dll
    VKD3D_SHADER_DUMP_PATH=${4:+Z:$PWD/$4} timeout 280 umu-run "$PWD/fsr4cap.exe" 4.1.1 "$2" "$3" "$frames" noise > umu.log 2>&1
}
for cfg in "2560x1440 3840x2160" "2260x1272 3840x2160" "1920x1080 3840x2160" "1280x720 3840x2160" "1706x960 2560x1440" "1280x720 1920x1080" "640x360 1920x1080"; do
    set -- $cfg; render=$1; out=$2; tag=${render}_${out}
    rm -rf "dll/$tag"; mkdir -p "dll/$tag/dump"
    run dll/original.dll "$render" "$out" ''
    mv "output_$out.raw" "dll/$tag/original.raw" 2>/dev/null || { echo "$tag: original run failed"; continue; }
    run dll/patched.dll "$render" "$out" "dll/$tag/dump"
    mv "output_$out.raw" "dll/$tag/patched.raw" 2>/dev/null || { echo "$tag: patched run failed"; continue; }
    phased=$(for f in "dll/$tag/dump"/*.spv; do spirv-dis "$f" 2>/dev/null | grep -q 'OpConstant %uint 3072' && echo x; done | wc -l)
    if cmp -s "dll/$tag/original.raw" "dll/$tag/patched.raw"; then verdict=IDENTICAL; else verdict=DIFFERS; fi
    [[ $phased -ge 1 ]] || verdict="$verdict (NOT A VALID TEST: the patched postpass did not run)"
    printf '%-22s output %s\n' "$tag" "$verdict"
    rm -rf "noise_capture_${render}_${out}" "dll/$tag/dump" "dll/$tag"/*.raw
done
cp dll/original.dll amd_fidelityfx_upscaler_dx12.dll
