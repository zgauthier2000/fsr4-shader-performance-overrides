#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""unname.py in.ll out.ll: undo the renaming taphoist.py and dedupe.py write (%vN -> %N, labels vN: -> ; <label>:N,
no v0: entry label), so that the next tool sees dxc -dumpbin style names again."""
import re,sys
t=open(sys.argv[1],encoding='utf-8').read()
t=re.sub(r'(?m)^(define void @[^\n]*\{)\nv0:\n', r'\1\n', t, count=1)
t=re.sub(r'(?m)^v(\d+):', r'; <label>:\1', t)
t=re.sub(r'%v(\d+)\b', r'%\1', t)
open(sys.argv[2],'w',encoding='utf-8').write(t)
