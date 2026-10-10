#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# FSR 4.1.1 shader timings on this machine's GPU. Run from a terminal:   bash run.sh
# With no option it runs the full set (about 20 minutes on a desktop card): all 14 passes at 1080p,
# 1440p and 4K (each alone, and the model's 12 in sequence), the lossy build's skipped-frame postpass, the postpass comparison with its candidates, the pass 11 and postpass versions, the
# store probes and compiler statistics.
# Options:  bash run.sh postpass  only the postpass comparison (a minute or two)
#           bash run.sh quick     all 14 passes and the postpass comparison, without the versions and probes (about 12 minutes)
#           bash run.sh traffic   the full set, plus the memory-traffic capture with the bundled driver build
# On a machine with two GPUs the discrete one is used;  KIT_GPU=integrated bash run.sh  uses the integrated one.
# Nothing is installed or changed on the machine; results go into results/<name>-<time>/ next to this file.
set -u
KIT=$(cd -- "$(dirname -- "$0")" && pwd)
MODE=${1:-full}
case $MODE in postpass|quick|full|traffic) ;; *) echo "unknown option: $MODE (use: postpass, quick or traffic, or nothing for the full run)"; exit 1 ;; esac
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
date; uname -sr
grep -m1 'model name' /proc/cpuinfo
free -h | head -2
for f in /sys/class/power_supply/A*/online; do [ -e "$f" ] && echo "AC online ($f): $(cat "$f")"; done
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null | sed 's/^/cpu governor: /'
cat /sys/firmware/acpi/platform_profile 2>/dev/null | sed 's/^/platform profile: /'
for d in /sys/class/drm/card?/device; do [ -e "$d/mem_info_vram_total" ] && echo "$d: vram $(( $(cat $d/mem_info_vram_total) >> 20 )) MB, in use $(( $(cat $d/mem_info_vram_used 2>/dev/null || echo 0) >> 20 )) MB, gtt $(( $(cat $d/mem_info_gtt_total) >> 20 )) MB, in use $(( $(cat $d/mem_info_gtt_used 2>/dev/null || echo 0) >> 20 )) MB"; done
command -v vulkaninfo >/dev/null && vulkaninfo --summary 2>/dev/null | grep -E 'deviceName|driverInfo|deviceType|apiVersion'
for d in /sys/class/drm/card?/device; do [ -e "$d/gpu_busy_percent" ] && echo "$d: PCI $(cat $d/vendor):$(cat $d/device), busy now $(cat $d/gpu_busy_percent)%, power state $(grep -h "\*" $d/pp_dpm_sclk 2>/dev/null | tr -d "\n")"; done
for f in /sys/class/power_supply/BAT*/status; do [ -e "$f" ] && echo "battery: $(cat "$f")"; done
echo "mode: $MODE, GPU choice: ${KIT_GPU:-default}"
command -v dmidecode >/dev/null && sudo -n dmidecode -t memory 2>/dev/null | grep -E 'Size:|Speed:|Locator:|Type:' | grep -v 'No Module'
} 2>&1 | tee "$OUT/system.txt"

# Is something else using the GPU? AMD's postpass in particular reads differently when it is.
gpu_load() {      # average of six readings over about two seconds; nothing if the driver does not report it
    local busy=0 n=0 i f
    for i in 1 2 3 4 5 6; do
        for f in /sys/class/drm/card?/device/gpu_busy_percent; do [ -e "$f" ] && { busy=$((busy + $(cat "$f" 2>/dev/null || echo 0))); n=$((n + 1)); }; done
        sleep 0.4
    done
    [ $n -gt 0 ] && echo $((busy / n))
}
load=$(gpu_load)
if [ -n "$load" ] && [ "$load" -ge 15 ]; then
    echo; echo "NOTE: something is using the GPU ($load% busy). Close games, browsers and video for readings"
    echo "      that can be trusted. Waiting up to 30 seconds for it to settle."
    for i in 1 2 3 4 5 6 7 8 9 10 11 12; do load=$(gpu_load); [ "$load" -lt 15 ] && break; done
    [ "$load" -ge 15 ] && echo "      Still $load% busy: continuing, and the summary will say so."
fi
[ -n "$load" ] && echo "GPU load before the run: $load%" | tee -a "$OUT/system.txt"

if ! "$W/mbench" 1 "$S/1080p/amd/pass1.spv" > "$OUT/selftest.txt" 2>&1; then
    echo; echo "The benchmark could not start on this GPU. See $OUT/selftest.txt:"; tail -5 "$OUT/selftest.txt"; exit 1
fi

timing() {  # timing <class dir> <WxH> <render W H>
    local c=$1 o=$2 nd=100
    [ "$c" = 1080p ] && nd=300        # short passes need a longer burst for a steady reading
    [ "$o" = 2560x1440 ] && nd=200
    say "class $c, output $o: prepass  (AMD, exact)"
    OUT=$o N_DISP=60 "$W/pbench2" "$S/$c/amd/prepass.spv" "$S/$c/exact/prepass.spv" 2>&1 | grep -E 'round 1|differ|DIFFER|IDENTICAL' | sed "s#$S/##"
    for k in 1 2 3 4 5 6 7 8 9 10 11 12; do
        v=("$S/$c/amd/pass$k.spv"); [ -f "$S/$c/exact/pass$k.spv" ] && v+=("$S/$c/exact/pass$k.spv"); [ -f "$S/$c/lossy/pass$k.spv" ] && v+=("$S/$c/lossy/pass$k.spv")
        say "class $c, output $o: pass $k  (AMD$( [ ${#v[@]} -gt 1 ] && echo ', exact')$( [ ${#v[@]} -gt 2 ] && echo ', lossy'))"
        OUT=$o N_DISP=$nd "$W/mbench" "${levels[$k]}" "${v[@]}" 2>&1 | sed "s#$S/##"
    done
    say "class $c, output $o: postpass  (AMD, exact)"
    A="$S/$c/amd/postpass.spv" B="$S/$c/exact/postpass.spv" N_DISP=30 "$W/bench" ${o%x*} ${o#*x} $3 $4 2>&1 | grep -E 'round|differ|DIFFER|IDENTICAL|output' | sed "s#$S/##"
    # the same two the other way round: whichever runs second reads a little differently
    say "class $c, output $o: postpass, other order  (exact, AMD)"
    A="$S/$c/exact/postpass.spv" B="$S/$c/amd/postpass.spv" N_DISP=30 "$W/bench" ${o%x*} ${o#*x} $3 $4 2>&1 | grep -E 'round 1' | sed "s#$S/##"
    # the 12 model passes one after another, as a game runs them (each pass alone can read differently)
    say "class $c, output $o: the 12 model passes in sequence  (AMD, exact)"
    for s_ in amd exact; do
        mkdir -p "$W/seq-$c-$s_"
        for k in 1 2 3 4 5 6 7 8 9 10 11 12; do f="$S/$c/$s_/pass$k.spv"; [ -f "$f" ] || f="$S/$c/amd/pass$k.spv"; cp "$f" "$W/seq-$c-$s_/pass$k.spv"; done
        v=$(OUT=$o "$W/mbench" seq "$W/seq-$c-$s_" 2>/dev/null | grep -o 'median [0-9.]* ms' | head -1)
        echo "sequence $c $o $s_ ${v:-failed}"
    done
    # the lossy build's postpass on a frame that skips the model: a probe that treats every frame as skipped, with the
    # picture at rest and moving 12,6 pixels. The rest of such a frame is the prepass; the model does not run.
    say "class $c, output $o: lossy postpass on a skipped frame, probe  (at rest, moving)"
    A="$S/$c/lossy/postpass_skipped_rest.spv" B="$S/$c/lossy/postpass_skipped_moving.spv" N_DISP=30 "$W/bench" ${o%x*} ${o#*x} $3 $4 2>&1 | grep -E 'round 1' | sed "s#$S/##"
}

# The postpass on its own: AMD's, the shipped rewrite, AMD's with its stores removed (the floor a
# rewrite can reach), and any candidate versions in shaders/<set>/candidates/postpass_*.spv.
postpass_section() {
    for c in "1080p 1920x1080 1280 720" "4k 2560x1440 1707 960" "4k 3840x2160 2560 1440"; do set -- $c
        say "postpass at $2: AMD's against the shipped rewrite, second reading"
        A="$S/$1/amd/postpass.spv" B="$S/$1/exact/postpass.spv" N_DISP=30 "$W/bench" ${2%x*} ${2#*x} $3 $4 2>&1 | grep -E 'round 1|DIFFER' | sed "s#$S/##"
        say "postpass at $2: AMD's against AMD's with its stores removed"
        A="$S/$1/amd/postpass.spv" B="$S/$1/probes/postpass_no_stores.spv" N_DISP=30 "$W/bench" ${2%x*} ${2#*x} $3 $4 2>&1 | grep -E 'round 1' | sed "s#$S/##"
        for f in "$S/$1"/candidates/postpass_*.spv; do
            [ -e "$f" ] || continue
            say "postpass at $2: AMD's against candidate $(basename "$f" .spv)"
            A="$S/$1/amd/postpass.spv" B="$f" N_DISP=30 "$W/bench" ${2%x*} ${2#*x} $3 $4 2>&1 | grep -E 'round 1|bytes differ|DIFFER' | sed "s#$S/##"
        done
    done
    # RDNA2 only: Mesa compiles most int8 dot products there as v_dot4c_i32_i8 (two operands, adds
    # onto its result). The bundled driver build can keep the three-operand v_dot4_i32_i8 instead
    # (AC_NO_DOT4C=1). Same shaders, same driver, both ways; on other GPUs the two are the same code.
    say "dot product form (bundled driver): as compiled, then with AC_NO_DOT4C=1"
    cp -r "$KIT/mesa" "$W/mesa" 2>/dev/null
    for c in "1080p 1920x1080 1280 720 300" "4k 3840x2160 2560 1440 100"; do set -- $c
        for e in dot4c dot4; do
            x=""; [ $e = dot4 ] && x="AC_NO_DOT4C=1"
            for p in 1 12; do
                v=$(env $x VK_DRIVER_FILES="$W/mesa/icd.json" RADV_DEBUG=nocache OUT=$2 N_DISP=$5 "$W/mbench" 1 "$S/$1/exact/pass$p.spv" 2>/dev/null | grep -o 'median [0-9.]* ms' | head -1)
                echo "dotform $1 $2 pass$p $e ${v:-failed}"
            done
            v=$(env $x VK_DRIVER_FILES="$W/mesa/icd.json" RADV_DEBUG=nocache A="$S/$1/amd/postpass.spv" B="$S/$1/exact/postpass.spv" N_DISP=30 "$W/bench" ${2%x*} ${2#*x} $3 $4 2>/dev/null | grep 'round 1' | grep -o 'median [0-9.]* ms' | tr '\n' ' ')
            echo "dotform $1 $2 postpass(AMD,shipped) $e ${v:-failed}"
        done
    done
    say "compiled code of the postpass versions"
    for c in 1080p 4k; do
        for f in "$S/$c/amd/postpass.spv" "$S/$c/exact/postpass.spv" "$S/$c"/candidates/postpass_*.spv; do
            [ -e "$f" ] || continue
            echo "--- $c $(basename "$(dirname "$f")")/$(basename "$f" .spv)"
            RADV_DEBUG=shaderstats,nocache A="$f" B="$f" N_DISP=1 "$W/bench" 1920 1080 1280 720 2>&1 | grep -E '^(VGPRs|Code size|LDS size|Subgroups per SIMD|Instructions|Branches):' | head -6
        done
    done
}
if [ "$MODE" = postpass ]; then
    postpass_section 2>&1 | tee "$OUT/postpass.txt"
    MODE=postpass-only
fi

rounds=2; [ "$MODE" = quick ] && rounds=1
if [ "$MODE" != postpass-only ]; then
# 1440p output uses the same shader versions as 4K (the "4k" set)
{ timing 1080p 1920x1080 1280 720; timing 4k 2560x1440 1707 960; timing 4k 3840x2160 2560 1440; } 2>&1 | tee "$OUT/timing-round1.txt"
# second round at 1080p only, to see how well the readings repeat
[ $rounds = 2 ] && timing 1080p 1920x1080 1280 720 2>&1 | tee "$OUT/timing-round2.txt"
postpass_section 2>&1 | tee "$OUT/postpass.txt"
fi

if [ "$MODE" != quick ] && [ "$MODE" != postpass-only ]; then
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

# One thing the kit cannot measure: what a game shows. It ties these readings to real use.
if [ -t 0 ] && [ "$MODE" != postpass-only ]; then
    echo; echo "Optional: if you have looked at OptiScaler's overlay in a game, what upscaler time (ms) did it show"
    echo "with AMD's file and with this project's? One line, for example:   3.8 2.9 Cyberpunk 2077, 4K Balanced, Windows"
    printf "(Enter to skip) > "; read -r ingame
    [ -n "$ingame" ] && printf '%s\n' "$ingame" | head -c 200 > "$OUT/ingame.txt"
fi

# Summary and a link that opens a pre-filled issue on the project's GitHub page. Nothing is sent
# from here: the issue exists only once you press "Submit new issue" in the browser.
if command -v python3 >/dev/null && python3 "$KIT/submit.py" "$OUT" 2>/dev/null; then
    echo; echo "=== summary (also in $OUT/summary.txt)"; cat "$OUT/summary.txt"
    if [ -t 0 ]; then
        printf '\nSend this summary (and nothing else) to the Discord results channel of the project? [Y/n] '; read -r answer
        case $answer in n*|N*) ;; *) python3 "$KIT/submit.py" "$OUT" --discord ;; esac
    fi
    echo; echo "It can also be sent as a GitHub issue: open this link and press \"Submit new issue\" (needs a GitHub account):"
    echo; cat "$OUT/submit-link.txt"
    echo "The link is also saved in $OUT/submit-link.txt. Only the summary above is in it."
    if [ -t 0 ] && command -v xdg-open >/dev/null && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        printf '\nOpen it in your browser now? [Y/n] '; read -r answer
        case $answer in n*|N*) ;; *) xdg-open "$(cat "$OUT/submit-link.txt")" >/dev/null 2>&1 & ;; esac
    fi
else
    echo "No summary could be made (python3 missing?). Please send the results folder instead."
fi
