#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# FSR 4 timing kit for Linux and the Steam Deck: runs the Windows kit's program under Proton. From a terminal, in this folder:   bash run.sh
# It uses umu-run if installed, otherwise a Proton from Steam. FSR4_PROTON=/path/to/a/Proton/folder picks one. Options after run.sh go to the program (--quick: a short run).
# Nothing is installed: its Wine prefix and results stay in this folder. On a laptop or Steam Deck: plugged in, no power-saving mode.
set -u
KIT=$(cd -- "$(dirname -- "$0")" && pwd); cd "$KIT"
export VKD3D_SHADER_CACHE_PATH=0 WINEDEBUG=-all
find_proton() {
    local r d
    [ -n "${FSR4_PROTON:-}" ] && { echo "$FSR4_PROTON"; return; }
    for r in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.steam/root" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$r" ] || continue
        for d in "$r/steamapps/common/Proton - Experimental" $(ls -d "$r"/steamapps/common/Proton\ [0-9]* 2>/dev/null | sort -rV | sed 's/ /\\ /g') $(ls -d "$r"/compatibilitytools.d/* 2>/dev/null | sort -rV); do
            d=${d//\\/}; [ -x "$d/proton" ] && { echo "$d"; return; }
        done
    done
}
if [ -z "${FSR4_PROTON:-}" ] && command -v umu-run >/dev/null; then
    P=$(find_proton); [ -n "$P" ] && export PROTONPATH=$P
    export WINEPREFIX="$KIT/pfx" GAMEID=umu-fsr4timekit
    echo "Running with umu-run${P:+ and $P}."; exec umu-run "$KIT/fsr4time.exe" "$@"
fi
P=$(find_proton)
if [ -z "$P" ]; then echo "No Proton found. Install Proton in Steam (Library, search for Proton Experimental), or set FSR4_PROTON=/path/to/a/Proton/folder."; exit 1; fi
S=; for r in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.steam/root" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do [ -d "$r" ] && { S=$r; break; }; done
mkdir -p "$KIT/pfx"; export STEAM_COMPAT_DATA_PATH="$KIT/pfx" STEAM_COMPAT_CLIENT_INSTALL_PATH="$S"
echo "Running with $P. The first start sets up a Wine prefix: about a minute."; exec "$P/proton" run "$KIT/fsr4time.exe" "$@"
