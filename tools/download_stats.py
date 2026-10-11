#!/usr/bin/env python3
# download_stats.py <data dir> [owner/repo]
# Records the download counts of every release file, so that they can be followed over time. GitHub keeps one running count per file and no history,
# and a file that is replaced starts again at zero; this keeps both.
#   downloads.csv   one line whenever a file's count is first seen or has changed: date (UTC), tag, file, GitHub's id of the file, count.
#                   A replaced file has a new id, so the old file's last line stays its final count.
#   runs.csv        one line per run: date, files seen, sum of the counts GitHub shows now, sum including replaced and deleted files
#   summary.md      the totals per release and per kind of download, rewritten every run
# Run daily by .github/workflows/download-stats.yml, which keeps the data on the branch `download-stats`. Needs nothing but Python; a token in
# GITHUB_TOKEN is used if there is one (the counts are public).
import csv, datetime, json, os, sys, urllib.request
out = sys.argv[1]; repo = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('GITHUB_REPOSITORY', 'zgauthier2000/fsr4-shader-performance-overrides')
os.makedirs(out, exist_ok=True)
rel = []; page = 1
while True:
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
with open(path, 'a', newline='') as f:
    w = csv.DictWriter(f, ['date', 'tag', 'file', 'id', 'downloads'])
    if f.tell() == 0:
        w.writeheader()
    w.writerows(new)
total = sum(int(r['downloads']) for r in last.values())
with open(out + '/runs.csv', 'a', newline='') as f:
    if f.tell() == 0:
        f.write('date,files,downloads shown by GitHub,downloads including replaced files\n')
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
order = [r['tag_name'] for r in rel] + sorted(t for t in tags if t not in {r['tag_name'] for r in rel})
since = min((r['date'] for r in first.values()), default=now)
md = [f'# Downloads of the release files', '', f'Updated {now} UTC; counted since {since} UTC. Files that were replaced before then are not in it.', '',
      '| Kind of download | Downloads | Of these, in files since replaced |', '|---|---|---|']
md += [f'| {k} | {v[0]:,} | {v[0] - v[1]:,} |' for k, v in sorted(kinds.items())]
md += ['', '| Release | Downloads | Of these, in files since replaced |', '|---|---|---|'] + [f'| `{t}` | {tags[t][0]:,} | {tags[t][0] - tags[t][1]:,} |' for t in order if t in tags]
md += ['', f'All files: {total:,}. `downloads.csv` has a line for every day a file\'s count changed; `runs.csv` has the totals of every run.', '']
open(out + '/summary.md', 'w').write('\n'.join(md))
print(f'{len(rel)} releases, {len(live)} files, {len(new)} counts new or changed, {shown} downloads shown, {total} including replaced files')
