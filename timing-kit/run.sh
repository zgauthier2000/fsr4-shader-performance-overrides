#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# FSR 4.1.1 shader timings on this machine's GPU. Run from a terminal:   bash run.sh
# Options:  bash run.sh quick     timings only, one round (about 8 minutes on a desktop card)
#           bash run.sh traffic   also try the memory-traffic capture (needs the bundled driver to load)
# Nothing is installed or changed on the machine; results go into results/<name>-<time>/ next to this file.
set -u
KIT=$(cd -- "$(dirname -- "$0")" && pwd)
MODE=${1:-full}
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=$KIT/results/$(cat /sys/class/dmi/id/product_name 2>/dev/null | tr -c 'A-Za-z0-9\n' '_' | head -c 24)-$STAMP
mkdir -p "$OUT" 2>/dev/null || { OUT=$HOME/fsr4-results-$STAMP; mkdir -p "$OUT"; }
# The stick may be mounted without permission to execute files: run the programs from a copy.
W=$(mktemp -d); cp "$KIT"/bin/* "$W"/; chmod +x "$W"/*
S=$KIT/shaders
say() { echo; echo "=== $*"; }
levels=(0 1 1 2 2 2 3 3 3 3 2 2 1)

{
say "system"
date; uname -a
grep -m1 'model name' /proc/cpuinfo
free -h | head -2
for f in /sys/class/power_supply/A*/online; do [ -e "$f" ] && echo "AC online ($f): $(cat "$f")"; done
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null | sed 's/^/cpu governor: /'
cat /sys/firmware/acpi/platform_profile 2>/dev/null | sed 's/^/platform profile: /'
for d in /sys/class/drm/card?/device; do [ -e "$d/mem_info_vram_total" ] && echo "$d: vram $(( $(cat $d/mem_info_vram_total) >> 20 )) MB, gtt $(( $(cat $d/mem_info_gtt_total) >> 20 )) MB"; done
command -v vulkaninfo >/dev/null && vulkaninfo --summary 2>/dev/null | grep -E 'deviceName|driverInfo|deviceType|apiVersion'
command -v dmidecode >/dev/null && sudo -n dmidecode -t memory 2>/dev/null | grep -E 'Size:|Speed:|Locator:|Type:' | grep -v 'No Module'
} 2>&1 | tee "$OUT/system.txt"

if ! "$W/mbench" 1 "$S/1080p/amd/pass1.spv" > "$OUT/selftest.txt" 2>&1; then
    echo; echo "The benchmark could not start on this GPU. See $OUT/selftest.txt:"; tail -5 "$OUT/selftest.txt"; exit 1
fi

timing() {  # timing <class dir> <WxH> <render W H>
    local c=$1 o=$2 nd=100
    [ "$c" = 1080p ] && nd=300        # short passes need a longer burst for a steady reading
    say "class $c, output $o: prepass  (AMD, exact)"
    OUT=$o N_DISP=60 "$W/pbench2" "$S/$c/amd/prepass.spv" "$S/$c/exact/prepass.spv" 2>&1 | grep -E 'round 1|differ|DIFFER|IDENTICAL' | sed "s#$S/##"
    for k in 1 2 3 4 5 6 7 8 9 10 11 12; do
        v=("$S/$c/amd/pass$k.spv"); [ -f "$S/$c/exact/pass$k.spv" ] && v+=("$S/$c/exact/pass$k.spv"); [ -f "$S/$c/lossy/pass$k.spv" ] && v+=("$S/$c/lossy/pass$k.spv")
        say "class $c, output $o: pass $k  (AMD$( [ ${#v[@]} -gt 1 ] && echo ', exact')$( [ ${#v[@]} -gt 2 ] && echo ', lossy'))"
        OUT=$o N_DISP=$nd "$W/mbench" "${levels[$k]}" "${v[@]}" 2>&1 | sed "s#$S/##"
    done
    say "class $c, output $o: postpass  (AMD, exact)"
    A="$S/$c/amd/postpass.spv" B="$S/$c/exact/postpass.spv" N_DISP=30 "$W/bench" ${o%x*} ${o#*x} $3 $4 2>&1 | grep -E 'round|differ|DIFFER|IDENTICAL|output' | sed "s#$S/##"
}

rounds=2; [ "$MODE" = quick ] && rounds=1
{ timing 1080p 1920x1080 1280 720; timing 4k 3840x2160 2560 1440; } 2>&1 | tee "$OUT/timing-round1.txt"
# second round at 1080p only, to see how well the readings repeat
[ $rounds = 2 ] && timing 1080p 1920x1080 1280 720 2>&1 | tee "$OUT/timing-round2.txt"

if [ "$MODE" != quick ]; then
{
    for c in "1080p 1920x1080" "4k 3840x2160"; do set -- $c
        say "pass 11 versions, class $1"
        OUT=$2 N_DISP=100 "$W/mbench" 2 "$S/$1"/pass11/*.spv 2>&1 | sed "s#$S/##"
    done
    say "postpass versions (Elden Ring's 4K version), each against AMD's"
    for f in "$S"/postpass-4k/[b-h]_*.spv; do
        A="$S/postpass-4k/a_amd.spv" B="$f" N_DISP=30 "$W/bench" 2>&1 | grep -E 'round 1|DIFFER|IDENTICAL' | sed "s#$S/##"
    done
    say "probes at 4K: the same shader with its stores removed (how much of the time is writing)"
    P=$S/probes-4k
    OUT=3840x2160 N_DISP=60 "$W/pbench2" "$P/prepass_amd.spv" "$P/prepass_amd_no_stores.spv" 2>&1 | grep 'round 1' | sed "s#$S/##"
    A="$P/postpass_amd.spv" B="$P/postpass_amd_no_stores.spv" N_DISP=30 "$W/bench" 2>&1 | grep 'round 1' | sed "s#$S/##"
    for k in 1 4 7 11 12; do N_DISP=100 "$W/mbench" "${levels[$k]}" "$P/pass${k}_amd.spv" "$P/pass${k}_amd_no_stores.spv" 2>&1 | sed "s#$S/##"; done
} 2>&1 | tee "$OUT/variants.txt"
{
    say "compiled code (instructions, registers, waves) for AMD's and the exact 1080p shaders"
    for s in amd exact; do for p in prepass pass1 pass11 pass12 postpass; do
        echo "--- $s $p"
        case $p in
            prepass) RADV_DEBUG=shaderstats,nocache OUT=1920x1080 N_DISP=1 "$W/pbench2" "$S/1080p/$s/$p.spv" 2>&1 ;;
            postpass) RADV_DEBUG=shaderstats,nocache A="$S/1080p/$s/$p.spv" B="$S/1080p/$s/$p.spv" N_DISP=1 "$W/bench" 1920 1080 1280 720 2>&1 ;;
            *) RADV_DEBUG=shaderstats,nocache OUT=1920x1080 N_DISP=1 "$W/mbench" 1 "$S/1080p/$s/$p.spv" 2>&1 ;;
        esac | grep -E '^(VGPRs|SGPRs|Spilled VGPRs|Code size|LDS size|Scratch size|Subgroups per SIMD|Instructions|Branches|VALU|VMEM):'
    done; done
} > "$OUT/compiled.txt" 2>&1
fi

if [ "$MODE" = traffic ]; then
{
    say "memory traffic (bundled driver build)"
    cp -r "$KIT/mesa" "$W/mesa"
    T="env VK_DRIVER_FILES=$W/mesa/icd.json MESA_VK_TRACE=rgp MESA_VK_TRACE_PER_SUBMIT=1 RADV_THREAD_TRACE_INSTRUCTION_TIMING=false RADV_THREAD_TRACE_QUEUE_EVENTS=false AC_SPM_PRINT=1 N_DISP=5"
    for s in amd exact; do
        echo "$s prepass:  $(OUT=1920x1080 $T "$W/pbench2" "$S/1080p/$s/prepass.spv" 2>&1 | python3 "$KIT/mesa/spmbytes.py" 5 2>&1 | tail -1)"
        for k in 1 4 7 11 12; do echo "$s pass $k:  $(OUT=1920x1080 $T "$W/mbench" "${levels[$k]}" "$S/1080p/$s/pass$k.spv" 2>&1 | python3 "$KIT/mesa/spmbytes.py" 5 2>&1 | tail -1)"; done
        echo "$s postpass: $(A="$S/1080p/$s/postpass.spv" B="$S/1080p/$s/postpass.spv" $T "$W/bench" 1920 1080 1280 720 2>&1 | python3 "$KIT/mesa/spmbytes.py" 5 2>&1 | tail -1)"
        rm -f /tmp/*.rgp
    done
} 2>&1 | tee "$OUT/traffic.txt"
fi
rm -rf "$W"
echo; echo "Done. Results are in: $OUT"
