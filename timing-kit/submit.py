#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# submit.py <results folder> [--print] [--discord]
# Makes a short summary of a timing-kit run (summary.txt in the results folder) and a link that
# opens a pre-filled issue on the project's GitHub page with that summary. Nothing is sent by this
# script by default: the issue is only created when you press "Submit new issue" in the browser.
# With --discord the summary is posted to the project's Discord results channel (run.sh asks first).
import glob
import os
import re
import sys
import urllib.parse
import urllib.request

REPO = 'zgauthier2000/fsr4-shader-performance-overrides'
# Posts to one results channel only; it cannot read anything. If it stops working, use the link.
WEBHOOK = 'https://discord.com/api/webhooks/1556797078259114065/Qz3Yjjv1fXHvWxGr3X5jT2wK3YyKF3x565PGMiQiREETxRvlGS1qycIM4H6_cs2ioIAK'
d = sys.argv[1].rstrip('/')
kit = os.path.dirname(os.path.abspath(__file__))


def read(name):
    try:
        return open(os.path.join(d, name), errors='replace').read()
    except OSError:
        return ''


def f(x):                      # milliseconds, short: .116  2.02  12.4
    s = f'{x:.3f}' if x < 1 else f'{x:.2f}' if x < 10 else f'{x:.1f}'
    return s[1:] if s.startswith('0.') else s


sysinfo = read('system.txt')
get = lambda pat: (re.search(pat, sysinfo, re.M) or [None, '?'])[1].strip()
gpu = (re.search(r'^GPU: (.+)$', read('selftest.txt'), re.M) or [None, get(r'deviceName\s*=\s*(.+)')])[1].strip()   # the GPU the benchmark used
if gpu == '?':
    gpu = (re.search(r'^(.+), output \d+x\d+, render', read('timing-round1.txt'), re.M) or [None, '?'])[1]
lines = [f'kit {open(os.path.join(kit, "VERSION")).read().strip() if os.path.exists(os.path.join(kit, "VERSION")) else "?"}',
         f'GPU: {gpu}', f'driver: {get(r"driverInfo\s*=\s*(.+)")}', f'kernel: {get(r"^Linux (?:\S+ )?(\d\S+)")}',
         f'CPU: {get(r"model name\s*:\s*(.+)")}', f'RAM: {get(r"Mem:\s+(\S+)")}']
for label, pat in (('RAM modules', None), ('on AC', r'AC online[^:]*:\s*(\d)'), ('governor', r'cpu governor:\s*(\S+)'), ('profile', r'platform profile:\s*(\S+)')):
    if pat is None:
        mods = re.findall(r'^\s*(?:Size|Speed):\s*(.+)$', sysinfo, re.M)
        if mods:
            lines.append('RAM modules: ' + ' / '.join(mods[:8]))
    elif re.search(pat, sysinfo):
        lines.append(f'{label}: {get(pat)}')

ORDER = ['prepass'] + [f'pass{k}' for k in range(1, 13)] + ['postpass']
SHORT = {'prepass': 'pre', 'postpass': 'post', **{f'pass{k}': f'p{k}' for k in range(1, 13)}}


SIZES = {'1920x1080': '1080p', '2560x1440': '1440p', '3840x2160': '4k'}


def timings(text):
    t, size = {}, None
    for l in text.split('\n'):
        h = re.match(r'=== class \S+ output (\d+x\d+):', l.replace(',', ''))
        if h:
            size = SIZES.get(h[1], h[1])
        if l.startswith('round 0'):
            continue
        m = re.search(r'(1080p|4k)/(amd|exact|lossy)/(\w+)\.spv .*median ([\d.]+) ms', l)
        if m:
            t[(size or m[1], m[3], m[2])] = float(m[4])
    return t


t1, t2 = timings(read('timing-round1.txt')), timings(read('timing-round2.txt'))
lines.append('')
lines.append('ms per pass: AMD / exact / lossy')
for cls in ('1080p', '1440p', '4k'):
    row, tot = [], {'amd': 0.0, 'exact': 0.0, 'lossy': 0.0}
    for p in ORDER:
        if (cls, p, 'amd') not in t1:
            continue
        a = t1[(cls, p, 'amd')]
        e = t1.get((cls, p, 'exact'), a)
        lo = t1.get((cls, p, 'lossy'), e)
        tot['amd'] += a; tot['exact'] += e; tot['lossy'] += lo
        v = [a] + ([t1[(cls, p, 'exact')]] if (cls, p, 'exact') in t1 else []) + ([t1[(cls, p, 'lossy')]] if (cls, p, 'lossy') in t1 else [])
        row.append(SHORT[p] + ' ' + '/'.join(f(x) for x in v))
    if row:
        lines.append(f'{cls}: ' + '  '.join(row))
        lines.append(f'{cls} sum: {f(tot["amd"])} / {f(tot["exact"])} / {f(tot["lossy"])}')
# postpass readings whose individual runs spread widely (AMD's postpass does this on some machines)
size, spread = None, []
for l in read('timing-round1.txt').split('\n'):
    h = re.match(r'=== class \S+ output (\d+x\d+):', l.replace(',', ''))
    if h:
        size = SIZES.get(h[1], h[1])
    m = re.match(r'round 1\s+\S+/(amd|exact)/postpass\.spv .*min ([\d.]+) ms\s+median ([\d.]+) ms\s+max ([\d.]+) ms', l)
    if m and float(m[4]) > 1.25 * float(m[2]):
        spread.append(f'{size} post {m[1]} {f(float(m[2]))} to {f(float(m[4]))} (median {f(float(m[3]))})')
if spread:
    lines.append('unsteady postpass readings (min to max of 15 runs): ' + '  '.join(spread))
if t2:
    dev = [abs(t2[k] / t1[k] - 1) for k in t2 if k in t1 and t1[k] > 0]
    if dev:
        lines.append(f'second round at 1080p: readings differ by up to {100 * max(dev):.0f}% (typical {100 * sorted(dev)[len(dev) // 2]:.0f}%)')

var = read('variants.txt')
main_part = var.split('=== probes')[0]
for cls in ('1080p', '4k'):
    v = re.findall(rf'{cls}/pass11/[a-d]_(\w+)\.spv .*median ([\d.]+) ms', var)
    if v:
        lines.append(f'pass 11, {cls}: ' + '  '.join(f'{n} {f(float(x))}' for n, x in v))
v = {}
for n, x in re.findall(r'round 1\s+postpass-4k/[a-h]_(\w+)\.spv .*median ([\d.]+) ms', var):
    v.setdefault(n, []).append(float(x))
if v:
    lines.append('postpass versions, 4K: ' + '  '.join(f'{n} {f(sum(x) / len(x))}' for n, x in v.items()))
v = re.findall(r'probes-4k/(\w+)\.spv.*?median ([\d.]+) ms', var)
if v:
    lines.append('store probes, 4K: ' + '  '.join(f'{n.replace("_amd", "").replace("_no_stores", "-nostore")} {f(float(x))}' for n, x in v))

comp = read('compiled.txt')
c = []
for s, p, body in re.findall(r'--- (amd|exact) (\w+)\n((?:[A-Za-z ]+: \d+\n)+)', comp):
    g = dict(re.findall(r'([A-Za-z ]+): (\d+)', body))
    c.append(f'{s} {SHORT.get(p, p)} {g.get("VGPRs", "?")}r/{g.get("Subgroups per SIMD", "?")}w/{g.get("Instructions", "?")}i')
if c:
    lines.append('compiled at 1080p (registers/waves/instructions): ' + '  '.join(c))
tr = re.findall(r'^(amd|exact) (\w+ ?\d*):\s+read\s+([\d.]+) MB\s+write-requests\s+([\d.]+)', read('traffic.txt'), re.M)
if tr:
    lines.append('traffic at 1080p (MB read/M write requests): ' + '  '.join(f'{s} {n.replace("pass ", "p")} {float(a):.0f}/{b}' for s, n, a, b in tr))

# anything that did not match AMD's output where it should
bad = []
for name in ('timing-round1.txt', 'timing-round2.txt'):
    txt = read(name)
    for l in txt.split('\n'):
        if 'DIFFERS' in l or re.search(r'^\s*[1-9]\d* (pixels differ|of \d+ bytes differ)', l) or re.search(r': [1-9]\d* of \d+ bytes differ', l):
            bad.append(l.strip()[:90])
for l in main_part.split('\n'):
    if 'DIFFERS' in l:
        bad.append(l.strip()[:90])
blank = sum(1 for n in ('timing-round1.txt', 'variants.txt') for l in read(n).split('\n') if '(0 nonzero in the original)' in l and 'heap+6' in l)
if blank:
    bad.append(f'{blank} postpass runs wrote an empty image (inputs not bound?)')
lines.append('')
lines.append('output check: all versions matched AMD\'s' if not bad else f'OUTPUT MISMATCHES ({len(bad)}): ' + ' ; '.join(bad[:6]))
missing = [n for n in ('timing-round1.txt',) if not read(n)]
if missing or not t1:
    lines.append('INCOMPLETE RUN: no timings found. selftest: ' + read('selftest.txt').strip()[-300:])

summary = '\n'.join(lines)
open(os.path.join(d, 'summary.txt'), 'w').write(summary + '\n')
body = ('Results from the timing kit. Anything to add (game settings you normally use, anything odd during the run):\n\n\n'
        '```\n' + summary + '\n```\n')
url = f'https://github.com/{REPO}/issues/new?' + urllib.parse.urlencode({'title': f'Timing kit results: {gpu}', 'labels': 'timing-kit', 'body': body})
if len(url) > 7500:            # keep under what GitHub accepts in a link
    body = 'Results from the timing kit (summary too long for a link: please paste summary.txt here).\n'
    url = f'https://github.com/{REPO}/issues/new?' + urllib.parse.urlencode({'title': f'Timing kit results: {gpu}', 'labels': 'timing-kit', 'body': body})
open(os.path.join(d, 'submit-link.txt'), 'w').write(url + '\n')
if '--print' in sys.argv:
    print(summary)
if '--discord' in sys.argv:
    import json
    b = 'kitboundary7f3a'
    note = os.environ.get('KIT_NOTE', '')
    payload = json.dumps({'content': (f'Timing kit results: **{gpu}**' + (f' ({note})' if note else ''))[:1900], 'allowed_mentions': {'parse': []}})
    data = (f'--{b}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n{payload}\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="files[0]"; filename="summary.txt"\r\nContent-Type: text/plain\r\n\r\n{summary}\n\r\n--{b}--\r\n').encode()
    req = urllib.request.Request(WEBHOOK, data=data, headers={'Content-Type': f'multipart/form-data; boundary={b}', 'User-Agent': 'fsr4-timing-kit'})
    try:
        urllib.request.urlopen(req, timeout=20).read()
        print('Sent to the project\'s Discord. Thank you!')
    except Exception as e:                     # no network, webhook removed, ...
        print(f'Could not send to Discord ({e}). Please use the link or send summary.txt yourself.')
        sys.exit(2)
