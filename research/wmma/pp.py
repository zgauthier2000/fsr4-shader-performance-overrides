# SPDX-License-Identifier: GPL-2.0-or-later
# Condensed pseudo-code of a model pass (spirv-dis text), for reading: one line per instruction,
# constants inlined, buffer/array accesses named.
import re,sys
L=open(sys.argv[1]).read().split('\n'); defs={}
for l in L:
    m=re.match(r'\s*(%\w+) = (.*)$',l)
    if m: defs[m[1]]=m[2]
nonw={m[1] for l in L if (m:=re.match(r'\s*OpDecorate (%\w+) NonWritable',l))}
names={}
def c(v):
    d=defs.get(v,'')
    if d.startswith('OpConstant '):
        t,val=d.split()[1],d.split()[2]
        if t=='%uint' and val.isdigit():
            n=int(val); return str(n) if n<1<<31 else f'{n-(1<<32)}' if n>=0xff000000 or n>0xfffffff0 else hex(n)
        return val
    if d.startswith('OpConstantComposite'): return '{'+','.join(c(x) for x in d.split()[2:])+'}'
    return names.get(v,v)
OPS={'OpIAdd':'+','OpISub':'-','OpIMul':'*','OpShiftLeftLogical':'<<','OpShiftRightLogical':'>>u','OpShiftRightArithmetic':'>>s','OpBitwiseAnd':'&','OpBitwiseOr':'|','OpFAdd':'+f','OpFMul':'*f','OpFSub':'-f','OpIEqual':'==','OpULessThan':'<u','OpUGreaterThan':'>u','OpLogicalOr':'||','OpLogicalAnd':'&&','OpSLessThan':'<s','OpSGreaterThan':'>s','OpBitwiseXor':'^'}
start=[i for i,l in enumerate(L) if '%main = OpFunction' in l][0]
for i,l in enumerate(L[start:],start):
    s=l.strip(); m=re.match(r'(%\w+) = (\w+)(?: (%\w+))?(.*)$',s)
    if not m:
        p=s.split()
        if not p: continue
        if p[0]=='OpStore': print(f'{i+1}: {c(p[1])} = {c(p[2])}')
        elif p[0] in('OpBranch','OpBranchConditional','OpLoopMerge','OpSelectionMerge','OpReturn'): print(f'{i+1}:    {p[0][2:]} '+' '.join(c(x) for x in p[1:]))
        continue
    r,op,ty,rest=m[1],m[2],m[3],m[4].split()
    if op=='OpLabel': print(f'{i+1}: {r}:'); continue
    if op=='OpAccessChain':
        base=rest[0]; idx=rest[1:]
        if base in('%registers',): names[r]=f'reg[{c(idx[0])}]'; continue
        if base=='%gl_GlobalInvocationID': names[r]=f'gid.{"xyz"[int(c(idx[0]))]}'; continue
        if defs.get(base,'').startswith('OpVariable') and 'Function' in defs[base]: names[r]=f'L{base[1:]}[{c(idx[0])}]'; continue
        if defs.get(base,'').startswith('OpVariable'): names[r]=('W' if base in nonw else 'T')+base[1:]; continue
        names[r]=f'{c(base)}[{c(idx[-1])}]'; continue
    if op=='OpInBoundsAccessChain': names[r]=f'cbv[{c(rest[-1])}]'; continue
    if op=='OpLoad':
        src=c(rest[0])
        if src.startswith(('reg[','gid.','cbv[')): names[r]=src; continue
        print(f'{i+1}: {r} = {src}'); continue
    if op=='OpCompositeExtract': 
        if defs.get(rest[0],'').startswith('OpCompositeConstruct'):
            names[r]=c(defs[rest[0]].split()[2+int(rest[1])]); continue
        print(f'{i+1}: {r} = {c(rest[0])}.{rest[1]}'); continue
    if op=='OpCompositeConstruct': names[r]='{'+','.join(c(x) for x in rest)+'}'; continue
    if op in('OpBitcast','OpCopyObject'): 
        print(f'{i+1}: {r} = ({ty[1:]}){c(rest[0])}'); continue
    if op in OPS: print(f'{i+1}: {r} = {c(rest[0])} {OPS[op]} {c(rest[1])}'); continue
    if op=='OpSDot': print(f'{i+1}: {r} = sdot({c(rest[0])}, {c(rest[1])})'); continue
    if op=='OpPhi': print(f'{i+1}: {r} = phi('+', '.join(f'{c(rest[k])}@{rest[k+1]}' for k in range(0,len(rest),2))+')'); continue
    if op=='OpExtInst': print(f'{i+1}: {r} = {rest[1]}('+', '.join(c(x) for x in rest[2:])+f') :{ty[1:]}'); continue
    print(f'{i+1}: {r} = {op[2:]}:{ty[1:] if ty else ""}('+', '.join(c(x) for x in rest)+')')
