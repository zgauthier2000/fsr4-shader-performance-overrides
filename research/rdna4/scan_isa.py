#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Scan RDNA4 ISA (rga text) for load latency that is not hidden.
Linear program-order simulation of the vector-memory counters: each load joins its counter's queue; an s_wait_*cnt N
retires the oldest loads until N remain. For each retired load we record how many instructions separated its issue
from the wait that needed it ("cover"). Short cover with few loads in flight = a serialized load.
usage: scan.py isa_dir [co ...]"""
import re, sys, os, glob, collections
d = sys.argv[1]; only = sys.argv[2:]
INS = re.compile(r'^\s+([a-z_0-9]+)(.*?)\s*//\s*([0-9A-F]{12}):')
def counter(op):
    if op.startswith('image_sample') or op.startswith('image_gather'): return 'sample'
    if op.startswith(('buffer_load', 'global_load', 'image_load', 'tbuffer_load', 'scratch_load')): return 'load'
    if op.startswith('ds_') and not op.startswith(('ds_store', 'ds_write')) or op.startswith('ds_bpermute') or op.startswith('ds_swizzle'): return 'ds'
    return None
WAIT = re.compile(r's_wait_(loadcnt|samplecnt|dscnt|loadcnt_dscnt)\b\s*(0x[0-9a-f]+|\d+)?')
for f in sorted(glob.glob(os.path.join(d, 'gfx1201_co*_comp.txt'))):
    co = re.search(r'co(\d+)', f).group(1)
    if only and co not in only: continue
    ins = []
    for l in open(f):
        m = INS.match(l)
        if m: ins.append((m.group(1), m.group(2).strip(), int(m.group(3), 16)))
    addr = {a: i for i, (_, _, a) in enumerate(ins)}
    loops = []
    for i, (op, args, a) in enumerate(ins):
        if op.startswith('s_cbranch') or op == 's_branch':
            m = re.search(r'(\d+)\s*$', args)
    q = {'load': collections.deque(), 'sample': collections.deque(), 'ds': collections.deque()}
    stats = {k: [] for k in q}   # (cover, inflight_at_issue) per retired load
    serial = []   # waits that retire exactly the newest load with cover < 24
    alu_since = 0
    for i, (op, args, a) in enumerate(ins):
        c = counter(op)
        if c:
            q[c].append(i); continue
        m = re.match(r's_wait_(loadcnt|samplecnt|dscnt)$', op)
        if m:
            k = {'loadcnt': 'load', 'samplecnt': 'sample', 'dscnt': 'ds'}[m.group(1)]
            n = int(args, 0) if args else 0
            popped = []
            while len(q[k]) > n: popped.append(q[k].popleft())
            for p in popped: stats[k].append(i - p)
            if popped and n == 0 and len(popped) <= 2 and i - popped[-1] < 24:
                serial.append((a, k, len(popped), i - popped[-1], ins[popped[-1]][0]))
        if op.startswith('s_wait_loadcnt_dscnt'):
            pass
        if op in ('s_cbranch_execz', 's_cbranch_scc0', 's_cbranch_scc1', 's_cbranch_vccz', 's_cbranch_vccnz', 's_branch', 's_cbranch_execnz'):
            pass
    nwm = sum(op.startswith('v_wmma') for op, _, _ in ins)
    print(f'co{co}: {len(ins)} ins, wmma {nwm}')
    for k, v in stats.items():
        if not v: continue
        v.sort(); short = sum(x < 24 for x in v)
        print(f'   {k:6s} retired {len(v):4d}  cover median {v[len(v)//2]:4d}  min {v[0]:3d}  <24 instr: {short}')
    if serial:
        print(f'   serialized waits (n=0, <=2 loads, cover<24): {len(serial)}')
        for s in serial[:12]: print('     @%05x %s retired %d, cover %d (%s)' % s)
    dup = collections.Counter((op, args) for op, args, _ in ins if counter(op) in ('load', 'sample'))
    dd = [(k, n) for k, n in dup.items() if n > 1]
    if dd: print(f'   identical load lines: {sum(n-1 for _, n in dd)} extra ({len(dd)} distinct)')
