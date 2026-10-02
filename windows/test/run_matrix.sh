#!/usr/bin/env bash
# Runs AMD's FSR 4.1.1 DLL under Proton for several output sizes and ratios, first plain and then
# with ReShade + the add-on + freshly built DXIL replacements, and compares the output images byte
# for byte. This is how the Windows add-on was verified on Linux.
#
# Put these next to this script first:
#   fsr4cap.exe                        built from tools/fsr4cap of bbport
#                                      (https://github.com/deadinside28/bloodborne_pc)
#   amd_fidelityfx_upscaler_dx12.dll   4.1.1.2740, and amd_fidelityfx_loader_dx12.dll 2.3.0
#   d3d12.dll                          ReShade64.dll with add-on support, renamed
#   fsr4_overrides.addon64             the add-on
# Needs umu-run, a Proton build (PROTONPATH) and DXC (DXC_DIR, see ../dxil/build_dxil_overrides.sh).
set -u
cd -- "$(dirname -- "$0")"
export WINEPREFIX=$PWD/pfx GAMEID=umu-fsr4cap WINEDEBUG=-all
export PROTONPATH=${PROTONPATH:-$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton11-7-x86_64}
frames=${FRAMES:-4}
for cfg in "2560x1440 3840x2160" "2260x1272 3840x2160" "1920x1080 3840x2160" "1280x720 3840x2160" "1706x960 2560x1440" "1280x720 1920x1080" "640x360 1920x1080"; do
    set -- $cfg; render=$1; out=$2; tag=${render}_${out}
    rm -rf "matrix/$tag"; mkdir -p "matrix/$tag/dump" "matrix/$tag/fsr4-overrides"
    # Reference run: ReShade and the add-on are loaded (d3d12.dll next to the exe), but with an empty
    # replacement folder, so AMD's own shaders run and get dumped.
    rm -rf fsr4-overrides; mkdir fsr4-overrides
    VKD3D_SHADER_DUMP_PATH="Z:$PWD/matrix/$tag/dump" timeout 280 umu-run "$PWD/fsr4cap.exe" 4.1.1 $render $out $frames noise > umu.log 2>&1
    mv "output_$out.raw" "matrix/$tag/reference.raw" 2>/dev/null || { echo "$tag: baseline run failed"; continue; }
    built=$(../dxil/build_dxil_overrides.sh "matrix/$tag/dump" "matrix/$tag/fsr4-overrides" 2>&1 | grep -c "\.dxil  (")
    rm -rf fsr4-overrides; cp -r "matrix/$tag/fsr4-overrides" fsr4-overrides; rm -f ReShade.log
    WINEDLLOVERRIDES="d3d12=n,b" timeout 280 umu-run "$PWD/fsr4cap.exe" 4.1.1 $render $out $frames noise > umu.log 2>&1
    replaced=$(grep -c "replacing compute shader" ReShade.log 2>/dev/null)
    if cmp -s "output_$out.raw" "matrix/$tag/reference.raw"; then verdict=IDENTICAL; else verdict=DIFFERS; fi
    [[ $built -eq 2 && $replaced -eq 2 ]] || verdict="$verdict (NOT A VALID TEST: expected 2 built and 2 replaced)"
    printf '%-22s built %s, replaced %s, output %s\n' "$tag" "$built" "$replaced" "$verdict"
    cp ReShade.log "matrix/$tag/ReShade.log" 2>/dev/null
    rm -f "output_$out.raw"; rm -rf "noise_capture_${render}_${out}"
done
