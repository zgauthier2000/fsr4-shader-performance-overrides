#!/usr/bin/env python3
"""mkcompare.py <set name> "Label=path" "Label=path" ... [--title T] [--note N] [--crop x,y,w,h] [--a N] [--b N] [--png] [--out DIR]

Makes a picture set for the slider page docs/compare/index.html: DIR/sets/<set name>/ (default DIR = docs/compare next to this
script's repo) with one lossless WebP (or PNG with --png) per picture and set.json, and adds the set to DIR/sets/index.json.

A path may be a test-harness output frame named output_<W>x<H>_fNNN.raw (float16 RGBA, linear light), a folder of them (its last frame),
a .npy array (float16 / float32 RGB, linear light: a true picture), or an ordinary .png / .jpg / .webp (used as it is). Linear pictures
get the same display mapping, x / (1 + x) then gamma 1/2.2, so they compare fairly with each other; it is not any game's tone mapping.
--crop cuts the same region from every picture: keep sets small (a 1280x720 crop is ~1-3 MB per picture); full 4K pictures make the
repository large. --a / --b: which pictures (1-based) start on the left / right.

Only put pictures in the repository that may be published: synthetic test scenes are fine; game frames and other people's files are not.
"""
import sys, os, re, glob, json, numpy as np
from PIL import Image

def disp(x):
    x = np.clip(np.nan_to_num(x.astype(np.float32)), 0, None); return ((x / (1 + x)) ** (1 / 2.2) * 255 + 0.5).clip(0, 255).astype(np.uint8)

def load(p):
    p = os.path.expanduser(p)
    if os.path.isdir(p):
        fs = sorted(glob.glob(f'{p}/output_*x*_f*.raw'))
        if not fs: sys.exit(f'mkcompare: no output_<W>x<H>_fNNN.raw in {p}')
        p = fs[-1]
    if p.endswith('.raw'):
        m = re.search(r'_(\d+)x(\d+)_', os.path.basename(p))
        if not m: sys.exit(f'mkcompare: cannot read the size from {p} (expects output_<W>x<H>_fNNN.raw)')
        W, H = int(m[1]), int(m[2]); return disp(np.fromfile(p, np.float16)[:W * H * 4].reshape(H, W, 4)[..., :3])
    if p.endswith('.npy'):
        a = np.load(p); return a[..., :3] if a.dtype == np.uint8 else disp(a[..., :3])
    return np.asarray(Image.open(p).convert('RGB'))

def main():
    args = sys.argv[1:]; opt = {}
    for k in ('--title', '--note', '--crop', '--a', '--b', '--out'):
        if k in args: i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    png = '--png' in args; args = [x for x in args if x != '--png']
    if len(args) < 3: sys.exit(__doc__)
    name, items = args[0], args[1:]
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', name): sys.exit('mkcompare: set names use a-z, 0-9, - and _')
    root = opt.get('--out') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'compare')
    out = os.path.join(root, 'sets', name); os.makedirs(out, exist_ok=True)
    crop = tuple(map(int, opt['--crop'].split(','))) if '--crop' in opt else None
    L, total, shape = [], 0, None
    for n, it in enumerate(items):
        label, _, path = it.partition('=')
        if not path: sys.exit(f'mkcompare: "{it}" is not Label=path')
        a = load(path)
        if crop: x, y, w, h = crop; a = a[y:y + h, x:x + w]
        if shape and a.shape != shape: print(f'note: {label} is {a.shape[1]}x{a.shape[0]}, the first picture {shape[1]}x{shape[0]}: the page scales it to fit')
        shape = shape or a.shape
        f = f'{n + 1:02d}.{"png" if png else "webp"}'
        im = Image.fromarray(np.ascontiguousarray(a))
        im.save(f'{out}/{f}', **({'optimize': True} if png else {'lossless': True, 'method': 6}))
        sz = os.path.getsize(f'{out}/{f}'); total += sz; L.append([label, f]); print(f'{label}: {a.shape[1]}x{a.shape[0]} -> {f} ({sz / 1e6:.2f} MB)')
    s = {'title': opt.get('--title', name), 'note': opt.get('--note', ''), 'images': L, 'a': int(opt.get('--a', 1)), 'b': int(opt.get('--b', 2))}
    json.dump(s, open(f'{out}/set.json', 'w'), indent=1)
    ix = os.path.join(root, 'sets', 'index.json'); sets = json.load(open(ix)) if os.path.exists(ix) else []
    sets = [x for x in sets if x['name'] != name] + [{'name': name, 'title': s['title']}]
    json.dump(sets, open(ix, 'w'), indent=1)
    print(f'set "{name}": {len(L)} pictures, {total / 1e6:.1f} MB' + ('  (large: consider --crop)' if total > 15e6 else ''))

if __name__ == '__main__': main()
