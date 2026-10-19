#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes lossy2-inside-light.svg and lossy2-inside-dark.svg: how lossy2 differs from the lossy DLL inside (docs/releases/dll-2026-10-19.md).
# A schematic: the same steps and frame skip in both, AMD's weights in the network's layers (passes 1 and 10 lightly folded in lossy),
# and the six layers lossy2 trained (passes 1, 2, 4, 5, 10 and 12, as research/lossy2/gen_lossy2.py writes them).
from make_explainers import THEMES, W, arrow, frame, line, rect, text

TRAINED = {1, 2, 4, 5, 10, 12}
FOLDED = {1, 10}
X0 = 112                     # left edge of the pipeline (row names to its left)
PRE, NET, POST = 74, 30, 86  # box widths: prepass, one network layer, last shader
GAP, ARR = 4, 18


def row(o, t, y, name, sub, kind):
    o += [text(24, y + 17, name, t, 13, 'ink', weight=600), text(24, y + 33, sub, t, 11, 'ink2')]
    x = X0
    o.append(rect(x, y, PRE, 40, 'box', t, stroke='grid')); o.append(text(x + PRE / 2, y + 24, 'prepass', t, 11, 'ink2', 'middle'))
    x += PRE; o.append(arrow(x + 2, y + 20, x + ARR - 2, y + 20, t)); x += ARR
    for k in range(1, 13):
        if kind == 'lossy2' and k in TRAINED:
            o.append(rect(x, y, NET, 40, 'lossy', t)); o.append(text(x + NET / 2, y + 25, str(k), t, 12, 'on', 'middle', 600))
        else:
            o.append(rect(x, y, NET, 40, 'amd', t, stroke='lossy' if (kind == 'lossy' and k in FOLDED) else None,
                          dash=kind == 'lossy' and k in FOLDED))
            o.append(text(x + NET / 2, y + 25, str(k), t, 12, 'on', 'middle', 600))
        x += NET + (GAP if k < 12 else 0)
    o.append(arrow(x + 2, y + 20, x + ARR - 2, y + 20, t)); x += ARR
    o.append(rect(x, y, POST, 40, 'box', t, stroke='grid')); o.append(text(x + POST / 2, y + 24, 'last shader', t, 11, 'ink2', 'middle'))
    return x + POST


def diagram(t):
    H = 506
    o = frame(H, "How lossy2 differs from the lossy DLL inside. Both run the same steps: the prepass, FSR 4's neural network of twelve layers, and the last shader, "
              "with the same frame skip: the network runs on every other frame, and on the frames in between the last shader moves its last result along with the picture. "
              "In lossy the network's layers carry AMD's weights, with layers 1 and 10 lightly folded. In lossy2 layers 1, 2, 4, 5, 10 and 12 carry new weights, trained "
              "from lossy's weights so that lossy's whole frame loop, skipped frames included, comes closer to AMD's picture; the other six layers, the prepass, the last "
              "shader and Ultra Performance are lossy's. Same shapes and sizes, so the same speed. The training tools are those of Durandal, the project's unreleased smaller network.",
              'What lossy2 changes inside the lossy DLL', 'The same steps and the same frame skip. Only the numbers in six of the network\'s twelve layers differ.', t)
    xs = X0 + PRE + ARR
    xe = xs + 12 * NET + 11 * GAP
    o += [line(xs, 84, xe, 84, t, 'muted'), line(xs, 84, xs, 90, t, 'muted'), line(xe, 84, xe, 90, t, 'muted'),
          text((xs + xe) / 2, 78, "FSR 4's neural network: twelve layers (shader passes 1 to 12)", t, 11, 'muted', 'middle')]
    row(o, t, 98, 'lossy', 'AMD\'s weights', 'lossy')
    row(o, t, 156, 'lossy2', '6 layers trained', 'lossy2')
    # legend
    y = 220; x = X0
    for kind, label in (('amd', "AMD's weights"), ('fold', "AMD's, lightly folded"), ('lossy', 'trained for lossy2'), ('box', "lossy's own shader")):
        if kind == 'fold':
            o.append(rect(x, y, 14, 14, 'amd', t, 2, 'lossy', True))
        else:
            o.append(rect(x, y, 14, 14, kind, t, 2, 'grid' if kind == 'box' else None))
        o.append(text(x + 20, y + 11, label, t, 11, 'ink2')); x += 44 + 6 * len(label)
    o.append(line(24, 252, W - 24, 252, t))
    # shared frame skip
    o += [text(24, 280, 'Both: the same frame skip', t, 13, 'ink', weight=600),
          text(24, 298, 'The network runs on every other frame; on the frames between, the last shader moves its last result along with the picture.', t, 11, 'ink2')]
    for i in range(8):
        x = 24 + i * 89; run = i % 2 == 0
        o.append(rect(x, 310, 83, 26, 'amd' if run else 'box', t, 3, None if run else 'grid'))
        o.append(text(x + 41.5, 327, 'network runs' if run else 'skipped', t, 11, 'on' if run else 'muted', 'middle', 600 if run else None))
    o.append(line(24, 352, W - 24, 352, t))
    # how the weights were made
    o += [text(24, 380, "How lossy2's six layers were trained", t, 13, 'ink', weight=600)]
    steps = (("start from", "lossy's weights"), ("run lossy's whole frame loop on", "test scenes, skipped frames too"),
             ("compare with", "AMD's picture"), ("adjust the", "six layers"))
    ws = (150, 236, 140, 130); x = 24
    for i, ((a, b), w) in enumerate(zip(steps, ws)):
        o.append(rect(x, 392, w, 42, 'box', t, 4, 'lossy' if i == 3 else 'grid'))
        o += [text(x + w / 2, 409, a, t, 11, 'ink2', 'middle'), text(x + w / 2, 424, b, t, 11, 'ink2', 'middle')]
        x += w
        if i < 3:
            o.append(arrow(x + 2, 413, x + 16, 413, t)); x += 18
    o += [text(24, 456, "Some scenes start fresh, as after a cut in a game, so that rain and fireflies do not turn into lasting specks.", t, 11, 'muted'),
          text(24, 472, "In Ultra Performance lossy2 runs lossy's layers. The training tools are those of Durandal, the project's unreleased", t, 11, 'muted'),
          text(24, 488, "smaller network: lossy2 is a step on that longer path.", t, 11, 'muted')]
    assert x <= W - 24, x
    return o


for name in ('light', 'dark'):
    with open(f'lossy2-inside-{name}.svg', 'w') as f:
        f.write('\n'.join(diagram(THEMES[name]) + ['</svg>']) + '\n')
    print(f'lossy2-inside-{name}.svg')
