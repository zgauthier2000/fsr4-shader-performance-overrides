#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_addon.sh [output]
#
# Cross-compiles the ReShade add-on for 64-bit Windows from Linux. Needs:
#   MINGW        a MinGW-w64 C++ compiler (default: x86_64-w64-mingw32-clang++ from llvm-mingw,
#                https://github.com/mstorsjo/llvm-mingw, or x86_64-w64-mingw32-g++ on PATH)
#   RESHADE_SRC  a checkout of https://github.com/crosire/reshade (only its include/ folder is used)
# On Windows, build addon/fsr4_overrides.cpp as a DLL with any C++20 compiler and ReShade's
# include folder on the include path, and name the result fsr4_overrides.addon64.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
out=${1:-$here/fsr4_overrides.addon64}
cxx=${MINGW:-$(command -v x86_64-w64-mingw32-clang++ || command -v x86_64-w64-mingw32-g++ || true)}
[[ -n $cxx ]] || { echo "no MinGW-w64 C++ compiler found (set MINGW)"; exit 1; }
[[ -f ${RESHADE_SRC:-}/include/reshade.hpp ]] || { echo "set RESHADE_SRC to a ReShade source checkout"; exit 1; }
"$cxx" -std=c++20 -O2 -shared -static -Wno-unknown-attributes \
    -I"$here/addon/compat" -I"$RESHADE_SRC/include" \
    "$here/addon/fsr4_overrides.cpp" -o "$out" -lpsapi -Wl,--no-insert-timestamp
echo "$out"
