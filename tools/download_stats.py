#!/usr/bin/env python3
# download_stats.py <data dir> [owner/repo]
# download_stats.py <data dir> --report-only      rewrite summary.md and the graphs from the recorded data, without asking GitHub
# Records the download counts of every release file, so that they can be followed over time. GitHub keeps one running count per file and no history,
# and a file that is replaced starts again at zero; this keeps both.
#   downloads.csv   one line whenever a file's count is first seen or has changed: date (UTC), tag, file, GitHub's id of the file, count.
#                   A replaced file has a new id, so the old file's last line stays its final count.
#   runs.csv        one line per run: date, files seen, sum of the counts GitHub shows now, sum including replaced and deleted files
#   summary.md      the total, a table of the downloads per day, and the totals per release and per kind of download; rewritten every run
#   downloads-light.svg, downloads-dark.svg   the graph in summary.md: the total over time and the new downloads per day
# Run daily by .github/workflows/download-stats.yml, which keeps the data on the branch `download-stats`. Needs nothing but Python; a token in
# GITHUB_TOKEN is used if there is one (the counts are public).
import csv, datetime, json, os, sys, urllib.request
REPORT_ONLY = '--report-only' in sys.argv; sys.argv = [a for a in sys.argv if a != '--report-only']
out = sys.argv[1]; repo = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('GITHUB_REPOSITORY', 'zgauthier2000/fsr4-shader-performance-overrides')
os.makedirs(out, exist_ok=True)
rel = []; page = 1
while not REPORT_ONLY:
    rq = urllib.request.Request(f'https://api.github.com/repos/{repo}/releases?per_page=100&page={page}', headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'download-stats'})
    if os.environ.get('GITHUB_TOKEN'):
        rq.add_header('Authorization', 'Bearer ' + os.environ['GITHUB_TOKEN'])
    got = json.load(urllib.request.urlopen(rq, timeout=60))
    rel += got; page += 1
    if len(got) < 100:
        break
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
path = out + '/downloads.csv'; last = {}; first = {}      # by file id: latest and first line
if os.path.exists(path):
    for r in csv.DictReader(open(path, newline='')):
        last[r['id']] = r; first.setdefault(r['id'], r)
new = []; live = set(); shown = 0
for r in rel:
    for a in r['assets']:
        i = str(a['id']); live.add(i); shown += a['download_count']
        if i not in last or int(last[i]['downloads']) != a['download_count']:
            row = {'date': now, 'tag': r['tag_name'], 'file': a['name'], 'id': i, 'downloads': str(a['download_count'])}
            new.append(row); last[i] = row; first.setdefault(i, row)
if REPORT_ONLY:      # every file still counts as present, and the releases are listed in the order of the tags
    live = set(last); shown = sum(int(r['downloads']) for r in last.values())
    now = max((r['date'] for r in last.values()), default=now)
with open(path, 'a', newline='') as f:
    w = csv.DictWriter(f, ['date', 'tag', 'file', 'id', 'downloads'])
    if f.tell() == 0:
        w.writeheader()
    w.writerows(new)
total = sum(int(r['downloads']) for r in last.values())
with open(out + '/runs.csv', 'a', newline='') as f:
    if f.tell() == 0:
        f.write('date,files,downloads shown by GitHub,downloads including replaced files\n')
    if not REPORT_ONLY:
        f.write(f'{now},{len(live)},{shown},{total}\n')

def kind(r):
    if r['tag'].startswith('timing-kit'):
        return 'Timing kit: Windows' if 'windows' in r['file'] else 'Timing kit: Linux' if r['file'].endswith('.tar.gz') else None
    if not r['file'].endswith(('.zip', '.dll')):
        return None
    return 'DLLs: integrated graphics' if 'igpu' in r['file'] else 'DLLs: desktop cards and other'
kinds = {}; tags = {}
for r in last.values():
    t = tags.setdefault(r['tag'], [0, 0]); t[0] += int(r['downloads']); t[1] += int(r['downloads']) if r['id'] in live else 0
    if kind(r):
        k = kinds.setdefault(kind(r), [0, 0]); k[0] += int(r['downloads']); k[1] += int(r['downloads']) if r['id'] in live else 0
order = [r['tag_name'] for r in rel] + sorted((t for t in tags if t not in {r['tag_name'] for r in rel}), reverse=True)
since = min((r['date'] for r in first.values()), default=now)
# ---- per day: the last reading of every day (UTC), and what was added since the last reading of the day before, split by kind from downloads.csv
KINDS = ['DLLs: desktop cards and other', 'DLLs: integrated graphics', 'Timing kit: Windows', 'Timing kit: Linux']
runs = [(r[0], int(r[3])) for r in list(csv.reader(open(out + '/runs.csv', newline='')))[1:] if len(r) > 3]
rows = list(csv.DictReader(open(path, newline='')))
days = []      # (day, time of the reading, total, {kind: total})
cur = {}; k = 0
for date, tot in runs:
    while k < len(rows) and rows[k]['date'] <= date:
        cur[rows[k]['id']] = rows[k]; k += 1
    by = {n: sum(int(r['downloads']) for r in cur.values() if kind(r) == n) for n in KINDS}
    if days and days[-1][0] == date[:10]:
        days.pop()
    days.append((date[:10], date[11:], tot, by))
stamp = lambda d: datetime.datetime.strptime(d[0] + ' ' + d[1], '%Y-%m-%d %H:%M')
hours = lambda a, b: (stamp(b) - stamp(a)).total_seconds() / 3600
span = hours(days[0], days[-1]) if len(days) > 1 else 0
per24 = (days[-1][2] - days[0][2]) / span * 24 if span else None


# ---- the graph: the total at every day's reading, and the downloads added per day; one file per color scheme
def graph(t):
    W, H, L, R = 760, 440, 64, 24; x0, x1 = L, W - R; n = len(days)
    font = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""
    tx = lambda x, y, s, size=11, fill='ink2', anchor='start', weight='': f'<text x="{x:.1f}" y="{y:.1f}" {font} font-size="{size}"{weight} text-anchor="{anchor}" fill="{t[fill]}">{s}</text>'
    xs = [x0 + 30 + (x1 - x0 - 60) * (i / (n - 1) if n > 1 else 0.5) for i in range(n)]
    new = [days[i][2] - days[i - 1][2] for i in range(1, n)]
    label = (f'Two charts of the downloads of the release files. Total at each day\'s reading: ' + ', '.join(f'{d[0]} {d[2]:,}' for d in days[-14:]) + '. '
             + ('Downloads added per day: ' + ', '.join(f'{days[i + 1][0]} {v:,}' for i, v in list(enumerate(new))[-14:]) + '.' if new else 'One reading so far, so no downloads per day yet.'))
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">', f'<rect width="{W}" height="{H}" fill="{t["surface"]}"/>',
         tx(24, 30, 'Downloads of the release files', 16, 'ink', weight=' font-weight="600"'), tx(24, 48, f'All files of all releases, at each day\'s reading (UTC). Total now: {days[-1][2]:,}.', 12)]

    def axis(top, bot, lo, hi, title):      # round steps (1, 2 or 5 times a power of ten), three to five grid lines
        o.append(tx(24, top - 12, title, 12, 'ink', weight=' font-weight="600"'))
        st = next(m * 10 ** e for e in range(12) for m in (1, 2, 5) if (hi - lo) / (m * 10 ** e) <= 4)
        lo = lo // st * st; hi = -(-hi // st) * st; k = round((hi - lo) / st)
        for j in range(k + 1):
            v = lo + st * j; y = bot - (bot - top) * j / k
            o.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>'); o.append(tx(x0 - 8, y + 4, f'{v:,.0f}', 10, 'muted', 'end'))
        return lambda v: bot - (bot - top) * (v - lo) / (hi - lo)
    step = max(1, -(-n // 12))      # at most about twelve date labels
    shown_x = [i for i in range(n) if (n - 1 - i) % step == 0]
    # total over time
    tots = [d[2] for d in days]
    y = axis(92, 212, min(tots), max(max(tots), min(tots) + 1), 'Total downloads')
    if n > 1:
        o.append(f'<polyline points="{" ".join(f"{xs[i]:.1f},{y(tots[i]):.1f}" for i in range(n))}" fill="none" stroke="{t["line"]}" stroke-width="2" stroke-linejoin="round"/>')
    for i in range(n):
        if n <= 31:
            o.append(f'<circle cx="{xs[i]:.1f}" cy="{y(tots[i]):.1f}" r="4" fill="{t["line"]}" stroke="{t["surface"]}" stroke-width="2"/>')
        if i in (0, n - 1) or n <= 8:
            o.append(tx(xs[i], y(tots[i]) - 10, f'{tots[i]:,}', 11, 'ink', 'middle'))
    # added per day
    top, bot = 272, 392
    if new:
        y = axis(top, bot, 0, max(max(new), 1), 'Downloads added since the reading of the day before')
        bw = min(48, (x1 - x0 - 60) / max(n - 1, 1) * 0.7) if n > 2 else 48
        for i, v in enumerate(new):
            h = max(bot - y(v), 1)
            o.append(f'<path d="M{xs[i + 1] - bw / 2:.1f},{bot} v{-(h - 4) if h > 4 else -h:.1f} q0,-4 4,-4 h{bw - 8:.1f} q4,0 4,4 v{(h - 4) if h > 4 else h:.1f} z" fill="{t["bar"]}"/>' if h > 4 and bw > 8 else
                     f'<rect x="{xs[i + 1] - bw / 2:.1f}" y="{bot - h:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{t["bar"]}"/>')
            if len(new) <= 14 or i == new.index(max(new)):      # with many bars only the tallest is labeled; the table has them all
                o.append(tx(xs[i + 1], bot - h - 6, f'{v:,}', 11, 'ink', 'middle'))
    else:
        o.append(tx(24, top - 12, 'Downloads added per day', 12, 'ink', weight=' font-weight="600"')); o.append(tx(24, top + 12, 'Needs a second day of readings.', 12))
    for i in shown_x:
        for yy in (228, bot + 16):
            o.append(tx(xs[i], yy, days[i][0][5:], 10, 'muted', 'middle'))
    o.append(tx(24, H - 12, 'Readings are not exactly 24 hours apart: the table below gives the hours each one covers.', 11, 'muted'))
    return '\n'.join(o + ['</svg>']) + '\n'


THEMES = {'light': dict(surface='#fcfcfb', ink='#0b0b0b', ink2='#52514e', muted='#898781', grid='#e1e0d9', line='#2a78d6', bar='#2a78d6'),
          'dark': dict(surface='#1a1a19', ink='#ffffff', ink2='#c3c2b7', muted='#898781', grid='#2c2c2a', line='#3987e5', bar='#3987e5')}
for name, th in THEMES.items():
    open(f'{out}/downloads-{name}.svg', 'w').write(graph(th))

md = [f'# Downloads of the release files', '', f'**Total downloads: {total:,}**', '',
      f'Updated {now} UTC; counted since {since} UTC. Files that were replaced before then are not in it.'
      + (f' Since counting began: {days[-1][2] - days[0][2]:,} downloads in {span / 24:.1f} days, {per24:,.0f} per 24 hours on average.' if per24 is not None else ''), '',
      '<picture>', '  <source media="(prefers-color-scheme: dark)" srcset="downloads-dark.svg">',
      '  <img src="downloads-light.svg" width="760" alt="Two charts: the total downloads of the release files at each day\'s reading, and the downloads added per day. The figures are in the table below.">', '</picture>', '',
      '## Per day', '',
      'One line per day (UTC), from that day\'s last reading. "Added" is what came in since the last reading of the day before; the readings are not exactly 24 hours apart, so the hours each one covers are given.', '',
      '| Day | Read at | Total | Added | Hours covered | Added: DLLs, desktop | Added: DLLs, integrated | Added: Windows kit | Added: Linux kit |', '|---|---|---|---|---|---|---|---|---|']
for i in range(len(days) - 1, -1, -1):
    d = days[i]
    if i == 0:
        md.append(f'| {d[0]} | {d[1]} | {d[2]:,} | counting began | | | | | |')
    else:
        p = days[i - 1]; md.append(f'| {d[0]} | {d[1]} | {d[2]:,} | {d[2] - p[2]:,} | {hours(p, d):.1f} | ' + ' | '.join(f'{d[3][n] - p[3][n]:,}' for n in KINDS) + ' |')
md += ['', 'The four columns on the right do not add up to "Added": checksum files and other small files are downloaded too.', '',
       '## By kind and by release', '',
       '| Kind of download | Downloads | Of these, in files since replaced |', '|---|---|---|']
md += [f'| {k} | {v[0]:,} | {v[0] - v[1]:,} |' for k, v in sorted(kinds.items())]
md += ['', '| Release | Downloads | Of these, in files since replaced |', '|---|---|---|'] + [f'| `{t}` | {tags[t][0]:,} | {tags[t][0] - tags[t][1]:,} |' for t in order if t in tags]
md += ['', f'All files: {total:,}. `downloads.csv` has a line for every day a file\'s count changed; `runs.csv` has the totals of every run.', '']
open(out + '/summary.md', 'w').write('\n'.join(md))
print(f'{len(rel)} releases, {len(live)} files, {len(new)} counts new or changed, {shown} downloads shown, {total} including replaced files')
