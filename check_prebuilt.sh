#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# check_prebuilt.sh <dump-dir>
#
# Tells you whether the files in prebuilt/ fit your setup. They were made from AMD's FSR 4.1.1
# shaders as Proton (vkd3d-proton) translated them on a Radeon RX 7800 XT, and they only work where
# Proton translates those shaders to exactly the same code: on other setups it can differ (seen on
# an RX 6900 XT), and then the prebuilt files give a wrong image, with no error message.
#
# Make a dump first (docs/shader-dump.md, steps 1 and 2), then run this on the dump folder. It
# compares the dumped shaders with the checksums of the ones prebuilt/ was made from
# (prebuilt/ORIGINALS.sha256).
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
[[ $# -eq 1 && -d $1 ]] || { sed -n '3,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
same=0; differ=0
while read -r sum name; do
    [[ -e $1/$name ]] || continue
    if [[ $(sha256sum "$1/$name" | cut -d' ' -f1) == "$sum" ]]; then same=$((same + 1)); else differ=$((differ + 1)); echo "differs: $name"; fi
done < "$here/prebuilt/ORIGINALS.sha256"
if (( same + differ == 0 )); then
    echo "None of the shaders prebuilt/ covers is in this dump: FSR 4.1.1 with AMD's original DLL"
    echo "(4.1.1.2740) was not running, or this is another FSR version."
    exit 2
elif (( differ )); then
    echo "$differ of $((same + differ)) shaders are translated differently on your setup."
    echo "Do NOT use prebuilt/ here. Build your own files instead:"
    echo "    ./build_override.sh $1"
    exit 1
fi
echo "All $same shaders match: prebuilt/ fits your setup."
