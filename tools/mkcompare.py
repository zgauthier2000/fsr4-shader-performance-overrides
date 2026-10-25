#!/usr/bin/env python3
"""mkcompare.py <set name> "Label=path" "Label=path" ... [--title T] [--note N] [--crop x,y,w,h] [--a N] [--b N] [--frames N] [--fps F] [--png] [--out DIR]
    [--label-note "Label=text" ...] [--same "NewLabel=Label" ...] [--intro HTML] [--about HTMLFILE]

Makes a picture set for the slider page docs/compare/index.html: DIR/sets/<set name>/ (default DIR = docs/compare next to this
script's repo) with one lossless WebP (or PNG with --png) per picture and set.json, and adds the set to DIR/sets/index.json.

A path may be a test-harness output frame named output_<W>x<H>_fNNN.raw (float16 RGBA, linear light), a folder of them (its last frame, or with
--frames N its last N frames, which the page plays in step on both sides; a folder of truth_NNN.npy works the same), several files joined by commas (one
frame each),
a .npy array (float16 / float32 RGB, linear light: a true picture), or an ordinary .png / .jpg / .webp (used as it is). Linear pictures
get the same display mapping, x / (1 + x) then gamma 1/2.2, so they compare fairly with each other; it is not any game's tone mapping.
--fps sets the playing speed the page opens with (default 8). --crop cuts the same region from every picture and frame: keep sets small (a 1280x720 crop is ~1-3 MB per picture); full 4K pictures make the
repository large. --a / --b: which pictures (1-based) start on the left / right.
--label-note "Label=text": a short note shown with that picture's name (its timing, for example). --same "NewLabel=Label": one more entry, right after Label, that
shows Label's own files (a build that makes the same picture byte for byte; no second copy). --intro: a line of HTML under the header; --about: a file of HTML for the
collapsible "About these pictures" panel (closed when the page opens).

Only put pictures in the repository that may be published: synthetic test scenes and upscaled game pictures are fine (say which game, which settings,
and that the display mapping is not the game's); raw game captures (input dumps) and other people's files are not.
"""
import sys, os, re, glob, json, numpy as np
from PIL import Image

def disp(x):
    x = np.clip(np.nan_to_num(x.astype(np.float32)), 0, None); return ((x / (1 + x)) ** (1 / 2.2) * 255 + 0.5).clip(0, 255).astype(np.uint8)

def load(p):
    p = os.path.expanduser(p)
    if p.endswith('.raw'):
        m = re.search(r'_(\d+)x(\d+)_', os.path.basename(p))
        if not m: sys.exit(f'mkcompare: cannot read the size from {p} (expects output_<W>x<H>_fNNN.raw)')
        W, H = int(m[1]), int(m[2]); return disp(np.fromfile(p, np.float16)[:W * H * 4].reshape(H, W, 4)[..., :3])
    if p.endswith('.npy'):
        a = np.load(p); return a[..., :3] if a.dtype == np.uint8 else disp(a[..., :3])
    return np.asarray(Image.open(p).convert('RGB'))

def sources(p, n):
    """the files one picture is made of: the n last frames of a folder, a comma-separated list, or the one file"""
    if ',' in p: return [os.path.expanduser(x) for x in p.split(',')]
    p = os.path.expanduser(p)
    if os.path.isdir(p):
        fs = sorted(glob.glob(f'{p}/output_*x*_f*.raw')) or sorted(glob.glob(f'{p}/truth_*.npy'))
        if not fs: sys.exit(f'mkcompare: no output_<W>x<H>_fNNN.raw or truth_NNN.npy in {p}')
        return fs[-n:]
    return [p]

def main():
    args = sys.argv[1:]; opt = {}
    lnotes, same = {}, []
    while '--label-note' in args: i = args.index('--label-note'); k_, _, v_ = args[i + 1].partition('='); lnotes[k_] = v_; del args[i:i + 2]
    while '--same' in args: i = args.index('--same'); k_, _, v_ = args[i + 1].partition('='); same.append((k_, v_)); del args[i:i + 2]
    for k in ('--title', '--note', '--crop', '--a', '--b', '--out', '--frames', '--fps', '--intro', '--about'):
        if k in args: i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    png = '--png' in args; args = [x for x in args if x != '--png']
    if len(args) < 3: sys.exit(__doc__)
    name, items = args[0], args[1:]
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', name): sys.exit('mkcompare: set names use a-z, 0-9, - and _')
    root = opt.get('--out') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'compare')
    out = os.path.join(root, 'sets', name); os.makedirs(out, exist_ok=True)
    crop = tuple(map(int, opt['--crop'].split(','))) if '--crop' in opt else None
    L, total, shape = [], 0, None
    nf = int(opt.get('--frames', 1))
    for n, it in enumerate(items):
        label, _, path = it.partition('=')
        if not path: sys.exit(f'mkcompare: "{it}" is not Label=path')
        files = []
        for k, src in enumerate(sources(path, nf)):
            a = load(src)
            if crop: x, y, w, h = crop; a = a[y:y + h, x:x + w]
            if shape and a.shape != shape: print(f'note: {label} is {a.shape[1]}x{a.shape[0]}, the first picture {shape[1]}x{shape[0]}: the page scales it to fit')
            shape = shape or a.shape
            f = f'{n + 1:02d}' + (f'_{k + 1:02d}' if nf > 1 or ',' in path else '') + ('.png' if png else '.webp')
            Image.fromarray(np.ascontiguousarray(a)).save(f'{out}/{f}', **({'optimize': True} if png else {'lossless': True, 'method': 6}))
            total += os.path.getsize(f'{out}/{f}'); files.append(f)
        L.append([label, files if len(files) > 1 else files[0]] + ([lnotes[label]] if label in lnotes else [])); print(f'{label}: {a.shape[1]}x{a.shape[0]}, {len(files)} frame(s)')
    for new, old in same:
        j = next((i for i, e in enumerate(L) if e[0] == old), None)
        if j is None: sys.exit(f'mkcompare: --same {new}={old}: no picture labeled {old}')
        L.insert(j + 1, [new, L[j][1]] + ([lnotes[new]] if new in lnotes else []))
    bad = [k for k in lnotes if k not in {e[0] for e in L}]
    if bad: sys.exit(f'mkcompare: --label-note for labels not given: {bad}')
    s = {'title': opt.get('--title', name), 'note': opt.get('--note', ''), 'images': L, 'a': int(opt.get('--a', 1)), 'b': int(opt.get('--b', 2)), 'fps': int(opt.get('--fps', 8))}
    if '--intro' in opt: s['intro'] = opt['--intro']
    if '--about' in opt: s['about'] = open(os.path.expanduser(opt['--about'])).read()
    json.dump(s, open(f'{out}/set.json', 'w'), indent=1)
    ix = os.path.join(root, 'sets', 'index.json'); sets = json.load(open(ix)) if os.path.exists(ix) else []
    sets = [x for x in sets if x['name'] != name] + [{'name': name, 'title': s['title']}]
    json.dump(sets, open(ix, 'w'), indent=1)
    print(f'set "{name}": {len(L)} pictures, {total / 1e6:.1f} MB' + ('  (large: consider --crop)' if total > 15e6 else ''))

if __name__ == '__main__': main()
