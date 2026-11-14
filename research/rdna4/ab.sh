#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# ab.sh <pairs> <dir A> <dir B>: A/B timing on an RX 9000 card at AMD's stable clocks, with a picture check.
# Each dir holds fsr4time.exe (the Windows timing kit), amd_fidelityfx_loader_dx12.dll and amd_fidelityfx_upscaler_dx12.dll.
# Runs A B, B A, A B ... (one kit run each), logs the core clock of every run, and prints the per-pair ratio B/A
# (moving scene, Balanced) and whether every picture fingerprint of B equals A's.
#
# env: RDP_DIR   folder of RadeonDeveloperPanelCLI.exe (Radeon Developer Tool Suite), for the clock mode
#      FULL=1    every size (default: 1080p and 4K)
#      KEEPCLK=1 leave the clock mode alone (normal-clock runs)
#      PMLOG     pmlog.exe built from pmlog.c, for the clock log (optional)
#
# Normal-clock timings on RX 9000 swing by 20-40% between sessions (the driver picks the clock for this load), so use
# the stable mode (1868 MHz on a 9070 XT) for anything below a few percent. The same DLL against itself stays within
# about +-0.3% this way.
#
# When the kit lists two versions for a run (a 4.1.1 DLL also shows the driver's own '4.1.2 *'), only the DLL's own
# version is used.
set -u
pairs=${1:?pairs}; A=$(cd "${2:?dir A}" && pwd); B=$(cd "${3:?dir B}" && pwd)
mode=quick; [[ -n ${FULL:-} ]] && mode=full
py=${PYTHON:-python3}
OUT=$PWD/ab-$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"

if [[ -z ${KEEPCLK:-} ]]; then
    [[ -n ${RDP_DIR:-} ]] || { echo "set RDP_DIR (or KEEPCLK=1)"; exit 1; }
    GI=$(cd "$RDP_DIR" && ./RadeonDeveloperPanelCLI.exe -m clocks --clock-mode normal --gpu-index 0 2>&1 | tr -d '\r' |
         sed -n 's/^ *\[\([0-9]\)\] AMD Radeon RX 9[0-9]*.*/\1/p' | head -1)
    [[ -n $GI ]] || { echo "no RX 9000 card in the Developer Panel's GPU list"; exit 1; }
    setclk() { (cd "$RDP_DIR" && ./RadeonDeveloperPanelCLI.exe -m clocks --clock-mode "$1" --gpu-index "$GI" 2>&1) | tr -d '\r' |
               grep -q "Clock mode set to: ${1^}" && echo "clock mode: $1 (GPU $GI)" || { echo "could not set clock mode $1"; return 1; }; }
    trap 'setclk normal' EXIT; trap 'exit 130' INT TERM
    setclk stable || exit 1
fi

one() {   # one <tag> <dir>
    local P=
    [[ -n ${PMLOG:-} ]] && { "$PMLOG" 50 4000 > "$OUT/$1.clk" & P=$!; sleep 1; }
    (cd "$2" && ./fsr4time.exe --run "$1" "$OUT/results.txt" $mode > "$OUT/$1.out" 2>&1)
    [[ -n $P ]] && { kill $P 2>/dev/null; wait $P 2>/dev/null; }
    grep -q "^R|$1" "$OUT/results.txt" 2>/dev/null || echo "!! run $1 wrote no results, see $OUT/$1.out"
}
for i in $(seq 1 "$pairs"); do
    if (( i % 2 )); then one A$i "$A"; one B$i "$B"; else one B$i "$B"; one A$i "$A"; fi
done
"$py" -I - "$OUT" <<'PY'
import collections, glob, os, sys
out = sys.argv[1]
t = collections.defaultdict(dict); fp = collections.defaultdict(set)
for l in open(os.path.join(out, 'results.txt'), encoding='utf-8', errors='replace'):
    p = l.rstrip('\n').split('|')
    if len(p) < 12 or p[0] != 'R' or '*' in p[2]: continue        # skip the driver's own provider
    tag = p[1].split(',')[0]
    fp[(tag[0], p[3], p[4], p[5])].add(p[11])
    if p[5] == 'moving' and ' ' not in p[3]: t[tag][p[3]] = float(p[7])
for f in sorted(glob.glob(os.path.join(out, '*.clk'))):      # sensor 1 = core clock, 19 = GPU busy
    c = [int(d['1']) for d in (dict(x.split('=') for x in l.split()[2:]) for l in open(f)) if int(d.get('19', 0)) >= 90]
    if c: print('%s: %d MHz' % (os.path.basename(f)[:-4], sum(c) / len(c)))
n = len([k for k in t if k[0] == 'A'])
print('B/A per pair (moving, Balanced; below 1 = B faster):')
for s in sorted({s for r in t.values() for s in r}):
    r = [t['B%d' % i][s] / t['A%d' % i][s] for i in range(1, n + 1) if s in t.get('A%d' % i, {}) and s in t.get('B%d' % i, {})]
    if r: print('  %-10s %s  mean %+.2f%%' % (s, ' '.join('%.4f' % x for x in r), 100 * (sum(r) / len(r) - 1)))
keys = sorted({k[1:] for k in fp})
diff = [k for k in keys if fp[('A',) + k] != fp[('B',) + k]]
print('pictures: %d rows, %s' % (len(keys), 'all identical' if not diff else 'differing: %s' % diff))
PY
echo "output: $OUT"
