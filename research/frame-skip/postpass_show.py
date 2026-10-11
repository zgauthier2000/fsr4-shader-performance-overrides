#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# postpass_show.py < postpass.spvasm > out.spvasm : AMD's postpass with its DISPLAY output replaced by what the mix is made of (the history it writes for the
# next frame is untouched, so the upscaler runs exactly as before). Per output pixel the postpass computes  new history = a * history + w * cur,  w = 1 - a,
# with a from the network and cur the resampled new frame. Display output becomes:  R = w,  G = mean over the channels of |cur - history|,
# B = w * G (the size of the step the history is asked to take, before it is rounded to the image's 16-bit floats).
import re, sys
L = sys.stdin.read().split('\n'); defs = {}
for l in L:
    m = re.match(r'\s*(%\S+) = (.*)$', l)
    if m: defs[m[1]] = m[2]
glsl = next(m[1] for l in L for m in [re.match(r'\s*(%\w+) = OpExtInstImport "GLSL.std.450"', l)] if m)
out = []; site = None; n_done = 0; third = '%dbg_third'
for n, l in enumerate(L):
    m = re.match(r'\s*(%\w+) = OpFSub %float %float_1 (%\w+)$', l)
    if m and re.match(r'OpFDiv %float %float_1 ', defs.get(m[2], '')):
        site = {'w': m[1], 'a': m[2], 'cur': [], 'hist': [], 'writes': 0}
    if site:
        f = re.match(r'\s*(%\w+) = OpFMul %float (%\w+) (%\w+)$', l)
        if f and site['w'] in (f[2], f[3]) and len(site['cur']) < 3: site['cur'].append(f[3] if f[2] == site['w'] else f[2])
        if f and site['a'] in (f[2], f[3]) and len(site['hist']) < 3: site['hist'].append(f[3] if f[2] == site['a'] else f[2])
        if 'OpImageWrite' in l: site['writes'] += 1
        c = re.match(r'\s*(%\w+) = OpCompositeConstruct %v4float (%\w+) (%\w+) (%\w+) (%\w+)$', l)
        if c and site['writes'] == 1 and len(site['cur']) == 3 and len(site['hist']) == 3:      # the construct of the second write after the mix: the display output
            k = n_done; n_done += 1; code = []
            for i in range(3):
                code += [f'%dbg_d{i}_{k} = OpFSub %float {site["cur"][i]} {site["hist"][i]}', f'%dbg_a{i}_{k} = OpExtInst %float {glsl} FAbs %dbg_d{i}_{k}']
            code += [f'%dbg_s1_{k} = OpFAdd %float %dbg_a0_{k} %dbg_a1_{k}', f'%dbg_s2_{k} = OpFAdd %float %dbg_s1_{k} %dbg_a2_{k}', f'%dbg_m_{k} = OpFMul %float %dbg_s2_{k} {third}',
                     f'%dbg_u_{k} = OpFMul %float %dbg_m_{k} {site["w"]}']
            out += code; out.append(f'{c[1]} = OpCompositeConstruct %v4float {site["w"]} %dbg_m_{k} %dbg_u_{k} {site["w"]}'); site = None; continue
    out.append(l)
at = max(i for i, l in enumerate(out) if re.match(r'\s*%\S+ = OpConstant %float ', l))
out[at] += f'\n{third} = OpConstant %float 0.3333333333'
sys.stderr.write(f'ppdebug: {n_done} pixel sites\n'); sys.stdout.write('\n'.join(out))
