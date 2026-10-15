#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# wavesize_dxil.py <32|64> < in.ll > out.ll
# Asks the driver to run a compute shader with waves of the given width: adds Shader Model 6.6's WaveSize
# entry property (tag 11) to the entry point's property list in DXIL text as printed by "dxc -dumpbin",
# replacing one already there. The shader's arithmetic is unchanged. Exits 1 below Shader Model 6.6.
import re
import sys

size = int(sys.argv[1])
if size not in (32, 64):
    sys.exit('wavesize_dxil: size must be 32 or 64')
s = sys.stdin.read()
sm = re.search(r'^!\d+ = !\{!"cs", i32 6, i32 (\d+)\}$', s, re.M)
if not sm or int(sm[1]) < 6:
    sys.exit('wavesize_dxil: not a compute shader of Shader Model 6.6 or later')
entry = re.search(r'^!dx\.entryPoints = !\{!(\d+)\}$', s, re.M)
if not entry:
    sys.exit('wavesize_dxil: no single entry point')
ep = re.search(r'^!%s = !\{(.*), (!\d+|null)\}$' % entry[1], s, re.M)
if not ep:
    sys.exit('wavesize_dxil: entry point metadata not as expected')
n = max(int(x) for x in re.findall(r'^!(\d+) = ', s, re.M)) + 1
s = s.rstrip('\n') + '\n!%d = !{i32 %d}\n' % (n, size)
if ep[2] == 'null':                          # no property list yet
    s = s.replace(ep[0], '!%s = !{%s, !%d}' % (entry[1], ep[1], n + 1), 1)
    s += '!%d = !{i32 11, !%d}\n' % (n + 1, n)
else:
    props = re.search(r'^%s = !\{(.*)\}$' % re.escape(ep[2]), s, re.M)
    items = [x.strip() for x in props[1].split(',')]
    pairs = [(items[i], items[i + 1]) for i in range(0, len(items), 2)]
    pairs = [p for p in pairs if p[0] != 'i32 11'] + [('i32 11', '!%d' % n)]
    s = s.replace(props[0], '%s = !{%s}' % (ep[2], ', '.join(a + ', ' + b for a, b in pairs)), 1)
sys.stdout.write(s)
