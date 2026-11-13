#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""thread.py in.ll out.ll: thread the 'motion vector invalid' edges of the prepass past the block that tests them.
Block J merges the motion-vector checks with phis and then branches on a condition that is false whenever the
'invalid' phi is true. Edges into J that carry only constants (invalid = true) are sent straight to J's false
target F; F's phis get the values J would have passed on. Instructions of J that do not depend on J's phis move to
the end of the block that dominates J's predecessors, so they are available on the new edges. Same values on every path.
Input uses named values (%vN) and labels (vN:)."""
import re, sys
L = open(sys.argv[1], encoding='utf-8').read().split('\n')
def blocks():
    fn = next(i for i, l in enumerate(L) if l.startswith('define void @')); end = next(i for i in range(fn, len(L)) if L[i] == '}')
    b = {}; cur = None; order = []
    for i in range(fn + 1, end):
        m = re.match(r'(\w+):', L[i])
        if m: cur = m.group(1); b[cur] = [i, i]; order.append(cur)
        elif cur and L[i].strip(): b[cur][1] = i
    return b, order
PHI = re.compile(r'\s+(%\w+) = phi (\w+) (.*)')
DEF = re.compile(r'\s+(%\w+) = (.*)')
def inc(s): return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r'\[ ([^,\]]+), %(\w+) \]', s)]
done = 0
while True:
    b, order = blocks(); hit = None
    for J in order:
        s, e = b[J]; lines = list(range(s + 1, e + 1))
        phis = [(i, PHI.match(L[i])) for i in lines if PHI.match(L[i])]
        term = next((i for i in lines if re.match(r'\s+br i1 ', L[i])), None)
        if len(phis) < 1 or term is None: continue
        preds = [p for _, p in inc(phis[0][1].group(3))]
        if len(preds) < 3 or not any(m.group(2) == 'float' for _, m in phis): continue
        const = [p for p in preds if all(dict((q, v) for v, q in inc(m.group(3)))[p][0] != '%' for _, m in phis)]
        if not const or len(const) == len(preds): continue
        tm = re.match(r'\s+br i1 (%\w+), label %(\w+), label %(\w+)', L[term]); cond, T, F = tm.groups()
        phiname = {m.group(1) for _, m in phis}
        body = [i for i in lines if i not in [x for x, _ in phis] and i != term and DEF.match(L[i])]
        dep = set(phiname)
        for i in body:
            m = DEF.match(L[i])
            if set(re.findall(r'%\w+', m.group(2).split('  ;')[0])) & dep: dep.add(m.group(1))
        def fold(p):
            env = {m.group(1): dict((q, v) for v, q in inc(m.group(3)))[p] for _, m in phis}
            for i in body:
                m = DEF.match(L[i]); v, rhs = m.group(1), m.group(2).split('  ;')[0].strip()
                if v not in dep: continue
                r = re.sub(r'%\w+', lambda x: env.get(x.group(0), x.group(0)), rhs)
                x = re.match(r'xor i1 (true|false), true$', r)
                if x: env[v] = 'false' if x.group(1) == 'true' else 'true'; continue
                if re.match(r'and i1 .*\bfalse\b', r): env[v] = 'false'; continue
                env[v] = None
            return env
        envs = {p: fold(p) for p in const}
        if any(envs[p].get(cond) != 'false' for p in const): continue
        fphis = [(i, PHI.match(L[i])) for i in range(b[F][0] + 1, b[F][1] + 1) if PHI.match(L[i])]
        ok = True
        for i, m in fphis:
            v = dict((q, v) for v, q in inc(m.group(3))).get(J)
            if v is None or (v in dep and any(envs[p].get(v) is None for p in const)): ok = False
        if not ok: continue
        hit = (J, s, e, phis, term, const, preds, F, body, dep, envs, fphis); break
    if not hit: break
    J, s, e, phis, term, const, preds, F, body, dep, envs, fphis = hit
    # the dominating block: the predecessor that is not reached from another predecessor of J
    b_, _ = blocks()
    def succs(x): return re.findall(r'label %(\w+)', L[b_[x][1]])
    top = next(p for p in preds if not any(p in succs(q) for q in preds if q != p))
    edits = {}
    for i, m in fphis:
        v = dict((q, vv) for vv, q in inc(m.group(3)))[J]
        extra = ''.join(f', [ {envs[p][v] if v in dep else v}, %{p} ]' for p in const)
        edits[i] = L[i].split('  ;')[0].rstrip() + extra
    for i, m in phis:
        keep = [(v, q) for v, q in inc(m.group(3)) if q not in const]
        edits[i] = f'  {m.group(1)} = phi {m.group(2)} ' + ', '.join(f'[ {v}, %{q} ]' for v, q in keep)
    for p in const:
        t = b_[p][1]; edits[t] = re.sub(r'label %' + J + r'\b', 'label %' + F, L[t])
    moved = [i for i in body if DEF.match(L[i]).group(1) not in dep]
    topterm = b_[top][1]
    new = []
    for i, l in enumerate(L):
        if i in moved: continue
        if i == topterm: new += [L[j] for j in moved]
        new.append(edits.get(i, l))
    L = new; done += 1
open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(L))
print('threaded', done)
