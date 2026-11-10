#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# FSR 4 timing kit for Linux and the Steam Deck: runs the Windows kit's program under Proton. From a terminal, in this folder:   bash run.sh
# It lists the Protons it finds and asks which to use; Enter takes the first. FSR4_PROTON=/path/to/a/Proton/folder picks one without asking. Options after run.sh go to the program (--quick: a short run).
# Nothing is installed: its Wine prefix and results stay in this folder. On a laptop or Steam Deck: plugged in, no power-saving mode.
set -u
KIT=$(cd -- "$(dirname -- "$0")" && pwd); cd "$KIT"
export VKD3D_SHADER_CACHE_PATH=0 WINEDEBUG=-all
ROOTS=("$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.steam/root" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam")
list_protons() {
    local r d
    {
        for r in "${ROOTS[@]}"; do
            [ -d "$r" ] || continue
            [ -x "$r/steamapps/common/Proton - Experimental/proton" ] && echo "$r/steamapps/common/Proton - Experimental"
            ls -d "$r"/steamapps/common/Proton\ [0-9]* 2>/dev/null | sort -rV
            ls -d "$r"/compatibilitytools.d/* 2>/dev/null | sort -rV
        done
        ls -d /usr/share/steam/compatibilitytools.d/* 2>/dev/null | sort -rV
    } | while IFS= read -r d; do [ -x "$d/proton" ] && readlink -f "$d"; done | awk '!seen[$0]++' | awk 'tolower($0) ~ /cachyos/ { c[++n] = $0; next } { print } END { for (i = 1; i <= n; i++) print c[i] }'      # CachyOS last: see below
}
P=${FSR4_PROTON:-}
ASK=1; for a in "$@"; do [ "$a" = --no-questions ] && ASK=0; done; [ -t 0 ] || ASK=0
if [ -z "$P" ]; then
    mapfile -t ALL < <(list_protons)
    if [ ${#ALL[@]} -gt 1 ] && [ $ASK = 1 ]; then
        echo "Protons found:"; for i in "${!ALL[@]}"; do n=$(basename "${ALL[$i]}"); case "${n,,}" in *cachyos*) n="$n  (did not start this kit in testing: the program ends without running)";; esac; echo "  $((i + 1))) $n"; done
        read -r -p "Which one? (Enter = 1) " c
        case "${c:-1}" in ''|*[!0-9]*) echo "Not a number on the list: using 1."; c=1;; esac
        [ "${c:-1}" -ge 1 ] && [ "${c:-1}" -le ${#ALL[@]} ] || { echo "Not a number on the list: using 1."; c=1; }
        P=${ALL[$((${c:-1} - 1))]}
    elif [ ${#ALL[@]} -ge 1 ]; then P=${ALL[0]}; fi
fi
if [ -z "$P" ] && ! command -v umu-run >/dev/null; then echo "No Proton found. Install Proton in Steam (Library, search for Proton Experimental), or set FSR4_PROTON=/path/to/a/Proton/folder."; exit 1; fi
[ -z "$P" ] || [ -x "$P/proton" ] || { echo "No proton program in $P."; exit 1; }
# the record of tests already run stays when a new kit replaces this folder (its Wine prefix goes with the folder)
ST="${XDG_DATA_HOME:-$HOME/.local/share}/fsr4-timing-kit"; mkdir -p "$ST" && export FSR4_STATE_DIR="Z:$(printf %s "$ST" | tr / '\\')"
export FSR4_PROTON_NAME="${P:+$(basename "$P")}"; [ -n "$FSR4_PROTON_NAME" ] || FSR4_PROTON_NAME="umu-run default"      # goes in the report
# (2026-11-10) the graphics driver setup, for the report: the Mesa version (from vulkaninfo, which follows VK_DRIVER_FILES, else from the driver library's own text) and the
# settings that change how FSR 4 runs (a descriptor heap costs RDNA 3 cards 6-10% on some Mesa versions)
mesa_version() {
    local v=""
    command -v vulkaninfo >/dev/null && v=$(timeout 20 vulkaninfo --summary 2>/dev/null | grep -m1 -oE 'Mesa [0-9][0-9.]*[^ ,)]*')
    if [ -z "$v" ]; then
        local j f
        for j in ${VK_DRIVER_FILES//:/ } ${VK_ICD_FILENAMES//:/ } /usr/share/vulkan/icd.d/radeon_icd*.json /etc/vulkan/icd.d/radeon_icd*.json; do
            [ -f "$j" ] || continue; f=$(grep -oE '"library_path"[^"]*"[^"]+"' "$j" | sed 's/.*"\([^"]*\)"$/\1/'); [ -n "$f" ] || continue
            [ -f "$f" ] || f=$(ls /usr/lib*/"$(basename "$f")" /usr/lib/*/"$(basename "$f")" 2>/dev/null | head -1)
            [ -n "$f" ] && [ -f "$f" ] && v=$(grep -aom1 -E 'Mesa [0-9]+\.[0-9]+\.[0-9]+[-a-z0-9.]*' "$f") && break
        done
    fi
    echo "${v:-Mesa version not found}"
}
LI="$(mesa_version)"; for e in VKD3D_CONFIG RADV_EXPERIMENTAL RADV_PERFTEST RADV_DEBUG; do [ -n "${!e:-}" ] && LI="$LI; $e=${!e}"; done
[ -n "${VK_DRIVER_FILES:-}${VK_ICD_FILENAMES:-}" ] && LI="$LI; own Vulkan driver file (VK_DRIVER_FILES)"
export FSR4_LINUX_INFO="$LI"      # goes in the report
# (2026-11-10) no screen blanking or sleep while the runs go: a tester's runs stopped when the screen went off (KDE). systemd-inhibit holds the lock as long as the program runs.
# Used only if it works here: without systemd-inhibit, or where it cannot take the lock (no login service, some containers), the kit runs as before.
INH=(); command -v systemd-inhibit >/dev/null && [ -z "${FSR4_NO_INHIBIT:-}" ] && timeout 10 systemd-inhibit --what=idle:sleep --who="FSR 4 timing kit" --why=check true >/dev/null 2>&1 && INH=(systemd-inhibit --what=idle:sleep --who="FSR 4 timing kit" --why="timing runs (a blanked screen or sleep can stop them)" --mode=block)
if command -v umu-run >/dev/null; then
    [ -n "$P" ] && export PROTONPATH=$P
    export WINEPREFIX="$KIT/pfx" GAMEID=umu-fsr4timekit
    echo "Running with umu-run${P:+ and $(basename "$P")}."; exec ${INH[@]+"${INH[@]}"} umu-run "$KIT/fsr4time.exe" "$@"
fi
S=; for r in "${ROOTS[@]}"; do [ -d "$r" ] && { S=$r; break; }; done
mkdir -p "$KIT/pfx"; export STEAM_COMPAT_DATA_PATH="$KIT/pfx" STEAM_COMPAT_CLIENT_INSTALL_PATH="$S"
echo "Running with $(basename "$P"). The first start sets up a Wine prefix: about a minute."; exec ${INH[@]+"${INH[@]}"} "$P/proton" run "$KIT/fsr4time.exe" "$@"
