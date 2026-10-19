#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_lossy2.sh <out folder> [<AMD's amd_fidelityfx_upscaler_dx12.dll 4.1.1.2740> <this release's lossy DLL> <desktop|igpu>]
#
# Rebuilds lossy2 from its integer weights (weights_lossy2.npz) and checks the result:
#  Linux:   <out>/linux = ../../prebuilt-lossy with network passes 1, 2, 4, 5, 10, 12 rebuilt for every output-size class (gen_lossy2.py);
#           it must equal ../../prebuilt-lossy2 file for file.
#  Windows: (with the three extra arguments) the same 18 shaders as HLSL -> DXC -> DXIL; the shader set of the release's lossy DLL of that
#           flavor is read back (../../dll/recover_set.py), the 18 shaders replace theirs, and AMD's DLL is patched with the set
#           (../../dll/patch_upscaler_dll.py --any-gpu --name 4.1.1-lossy2-cyboman or 4.1.1-igpu-lossy2-cyboman) -> <out>/<flavor>.dll.
#           Compare its SHA-256 with the release's SHA256SUMS. Needs DXC (DXC_DIR: a folder with bin/dxc and lib/; the release used
#           DXC 1.9.2609.5, Microsoft's Linux build) and Python 3 with numpy, glslangValidator (the release used 16.4.0).
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd); R=$(cd "$H/../.." && pwd); O=$1
[ -e "$O" ] && { echo "$O exists: not overwritten"; exit 1; }
mkdir -p "$O"
python3 -I "$H/gen_lossy2.py" "$H/weights_lossy2.npz" "$R/prebuilt-lossy" "$O/linux" ${2:+--hlsl "$O/hlsl"}
n=0; for f in "$R/prebuilt-lossy2"/*; do cmp -s "$f" "$O/linux/$(basename "$f")" || { n=$((n+1)); echo "differs: $(basename "$f")"; }; done
echo "Linux: $n files differ from prebuilt-lossy2 (0 expected)"
[ -n "${2:-}" ] || exit 0
A=$2; L=$3; F=$4; X=${DXC_DIR:?set DXC_DIR to a DXC folder with bin/dxc}; export LD_LIBRARY_PATH="$X/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
nm=4.1.1-lossy2-cyboman; [ "$F" = igpu ] && nm=4.1.1-igpu-lossy2-cyboman
python3 -I "$R/dll/recover_set.py" "$A" "$L" "$O/set"
for h in "$O/hlsl"/*.hlsl; do b=$(basename "$h" .hlsl)
  [ -f "$O/set/$b.dxil" ] || { echo "the lossy DLL has no shader $b: not this release's lossy DLL?"; exit 1; }
  "$X/bin/dxc" -T cs_6_6 -E main -enable-16bit-types -HV 2021 "$h" -Fo "$O/set/$b.dxil" > /dev/null; done
python3 -I "$R/dll/patch_upscaler_dll.py" --any-gpu --name $nm "$A" "$O/$F.dll" "$O/set" > /dev/null
echo "Windows ($F): $O/$F.dll  SHA-256 $(sha256sum "$O/$F.dll" | cut -c1-64)"
