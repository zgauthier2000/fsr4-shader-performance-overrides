#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Diagnostic only: the same shader interface with an empty main(). spirv-dis text in, text out.
import re
import sys
lines = sys.stdin.read().split('\n')
i = next(k for k, l in enumerate(lines) if l.strip().startswith('%main = OpFunction'))
gone = {m[1] for l in lines[i + 1:] if (m := re.match(r'\s*(%\w+) = ', l))}
head = [l for l in lines[:i + 1]
        if not ((m := re.match(r'\s*Op(Name|Decorate|MemberDecorate) (%\w+)', l)) and m[2] in gone)]
print('\n'.join(head + ['       %bb_entry = OpLabel', '               OpReturn', '               OpFunctionEnd']))
