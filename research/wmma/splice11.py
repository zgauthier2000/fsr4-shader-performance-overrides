#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Hybrid of the exact pass 11 (decompiled with spirv-cross): its first layer (3x3, 16 -> 16, weights in the buffer as
# [tap][oc][ic] at byte 113920, biases as words at 29056) by WMMA at the top of main(); after AMD's loop of that layer
# its four packed output words are overwritten with the same rounding of bias + WMMA sums. Rest unchanged.
# usage: splice11.py <e11.comp> <wave 32|64> > out.comp
import re, sys
src = open(sys.argv[1]).read(); wave = int(sys.argv[2])
for needle in ('113920u', '29056u', '(15392u * gl_GlobalInvocationID.y)', '33273664u'):
    assert needle in src, needle
ext = """#extension GL_KHR_cooperative_matrix : require
#extension GL_KHR_memory_scope_semantics : require
#extension GL_KHR_shader_subgroup_basic : require
#extension GL_KHR_shader_subgroup_shuffle : require
#extension GL_EXT_shader_explicit_arithmetic_types : require
#extension GL_EXT_control_flow_attributes : require
"""
out = src.replace('#version 450\n', '#version 460\n' + ext, 1)
wb = re.search(r'uvec4\((_\d+)\[_\d+\]\._m0\[_\d+\], \1\[_\d+\]\._m0\[_\d+ \+ 1u\].*\n.*\n.*\n.*\n.*\n.*registers\._m1 \+ 11u', out)
wbuf = re.search(r'uint _\d+ = _\d+ \+ 29056u;\n\s*uvec4 _\d+ = uvec4\((_\d+)\[', out)[1]
tens = re.search(r'uvec2 _\d+ = uvec2\((_\d+)\[_\d+\]\._m0\[_\d+\], \1\[_\d+\]\._m0\[_\d+ \+ 1u\]\);\n\s*uint _\d+ = _\d+\.x;', out)[1]
nt = 4 if wave == 64 else 2; ne = 16 // (wave // 16)
glob = """
#define HACC coopmat<int32_t, gl_ScopeSubgroup, 16, 16, gl_MatrixUseAccumulator>
#define HMATA coopmat<int8_t, gl_ScopeSubgroup, 16, 16, gl_MatrixUseA>
#define HMATB coopmat<int8_t, gl_ScopeSubgroup, 16, 16, gl_MatrixUseB>
"""
top = f"""    // ---- hybrid: layer 1 (3x3, 16 -> 16) by WMMA (splice11.py, wave {wave})
    int h_sum[16];
    {{
        const uint lane = gl_SubgroupInvocationID, p = lane & 15u, g = lane >> 4;
        const uint y = gl_WorkGroupID.y, x0 = gl_WorkGroupID.x * 64u + gl_SubgroupID * {wave}u;
        HMATA ha[9];
        [[unroll]] for (uint m = 0u; m < 9u; m++)
            coopMatLoad(ha[m], {wbuf}[registers._m2 + 18u]._m0, (113920u + 256u * m) >> 2u, 4u, gl_CooperativeMatrixLayoutRowMajor);
        int hv[{nt}][{ne}];
        [[unroll]] for (uint t = 0u; t < {nt}u; t++) {{
            HACC hacc = HACC(0);
            [[unroll]] for (uint tap = 0u; tap < 9u; tap++) {{
                HMATB hb;
                coopMatLoad(hb, {tens}[registers._m1 + 11u]._m0, (33273664u + 15392u * (y + tap / 3u) + (x0 + t * 16u + tap % 3u) * 16u) >> 2u, 4u, gl_CooperativeMatrixLayoutColumnMajor);
                hacc = coopMatMulAdd(ha[tap], hb, hacc);
            }}
            [[unroll]] for (uint i = 0u; i < {ne}u; i++) hv[t][i] = hacc[i];
        }}
"""
if wave == 64:
    top += """        [[unroll]] for (uint i = 0u; i < 4u; i++) {
            int own = hv[0][i];
            [[unroll]] for (uint t = 1u; t < 4u; t++) if (g == t) own = hv[t][i];
            h_sum[g + 4u * i] = own;
        }
        [[unroll]] for (uint d = 1u; d < 4u; d++)
            [[unroll]] for (uint i = 0u; i < 4u; i++) {
                int send = hv[0][i];
                [[unroll]] for (uint t = 1u; t < 4u; t++) if ((g ^ d) == t) send = hv[t][i];
                h_sum[(g ^ d) + 4u * i] = subgroupShuffleXor(send, 16u * d);
            }
    }
"""
else:
    top += """        [[unroll]] for (uint i = 0u; i < 8u; i++) {
            const int own = g == 0u ? hv[0][i] : hv[1][i];
            const int send = g == 0u ? hv[1][i] : hv[0][i];
            h_sum[g + 2u * i] = own;
            h_sum[(g ^ 1u) + 2u * i] = subgroupShuffleXor(send, 16u);
        }
    }
"""
out = out.replace('void main()\n{\n', glob + 'void main()\n{\n' + top, 1)
# the first loop is layer 1; find its end
b = out.index('void main()'); first = out.index('for (;;)', b)
i = out.index('{', first); depth = 0
while True:
    if out[i] == '{': depth += 1
    elif out[i] == '}':
        depth -= 1
        if depth == 0: break
    i += 1
seg = out[first:i]
dst = re.search(r'(_\d+)\[\(_\d+ & 1073741823u\) \+ 0u\] = pack32', seg)[1]
assert '>> 8u) & 1u)' in seg
ind = re.search(r'\n(\s*)for \(;;\)', out[first - 200:first + 10])[1]
put = f"""
{ind}[[unroll]] for (uint w = 0u; w < 4u; w++) {{
{ind}    uint pk = 0u;
{ind}    [[unroll]] for (uint j = 0u; j < 4u; j++) {{
{ind}        const int t = int({wbuf}[registers._m2 + 18u]._m0[29056u + 4u * w + j]) + h_sum[4u * w + j];
{ind}        const int q = clamp((t + 127 + ((t >> 8) & 1)) >> 8, -128, 127);
{ind}        pk |= uint(q & 0xff) << (8u * j);
{ind}    }}
{ind}    {dst}[w] = pk;
{ind}}}"""
out = out[:i + 1] + put + out[i + 1:]
sys.stderr.write(f'splice11: weights {wbuf}, tensor {tens}, dst {dst}\n')
print(out)
