#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""compare_pictures.py <results.txt> <tag A> <tag B>: compares the picture fingerprints (last column) of two timing-kit
runs row by row (size, render size, still/moving). Run the kit once per DLL with the same results file, e.g.
    fsr4time.exe --run amd results.txt full all      (and the same with the patched DLL as 'patched')
with FSR4TIME_800P=1 for the 800p rows. Rows of the driver's own provider ('4.1.2 *') are skipped.
Exit status 0 when every shared row is identical."""
import sys

if len(sys.argv) != 4:
    sys.exit(__doc__)
rows = {}
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    p = line.rstrip('\n').split('|')
    if len(p) < 12 or p[0] != 'R' or '*' in p[2]:
        continue
    rows.setdefault(p[1].split(',')[0], {})[(p[3], p[4], p[5])] = p[11]
a, b = rows.get(sys.argv[2], {}), rows.get(sys.argv[3], {})
keys = sorted(set(a) & set(b))
diff = [k for k in keys if a[k] != b[k]]
for k in diff:
    print('differs:', ' '.join(k), a[k], b[k])
print(f'{len(keys) - len(diff)} of {len(keys)} rows identical')
sys.exit(1 if diff or not keys else 0)
