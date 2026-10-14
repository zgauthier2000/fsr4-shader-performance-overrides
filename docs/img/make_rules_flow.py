#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Writes rules-flow-light.svg and rules-flow-dark.svg: the flow chart of docs/lossy-rules.md, what the lossy DLL's last
# shader does with one output pixel on a frame that skips the network (research/frame-skip/skipblend.py with its defaults).
# A schematic: the thresholds in it are the tool's defaults, quoted on the page.
from make_explainers import THEMES, W, arrow, frame, line, rect, text

LEFT, RIGHT = 24, W - 24
LH = 16      # line height of the body text


def box(o, t, x, y, w, head, lines, accent=None, tag=None):
    """a step: a bold head line and body lines; returns the y below it"""
    h = 30 + LH * len(lines) + 6
    o.append(rect(x, y, w, h, 'box', t, 6, accent or 'grid'))
    if tag:
        o.append(rect(x + 10, y + 9, 22, 20, accent or 'muted', t, 10))
        o.append(text(x + 21, y + 24, tag, t, 12, 'on', 'middle', 600))
    o.append(text(x + (40 if tag else 12), y + 24, head, t, 13, 'ink', weight=600))
    for i, s in enumerate(lines):
        o.append(text(x + 12, y + 44 + LH * i, s, t, 12))
    return y + h


def flow(t):
    H = 1112
    o = frame(H, "Flow chart: what the lossy DLL's last shader does with one output pixel on a frame that skips the neural network. "
              "It starts from the network's weight for the new frame, kept from the network's last run and moved along with the picture, and squares it. "
              "Then it asks whether the picture is at rest at this pixel. At rest the weight becomes zero, so nothing is taken from the new frame, unless one of three things says the content "
              "changed without the game reporting motion: the previous picture lies outside the range of the nine new samples around the pixel, the new frame differs from it by more than a "
              "quarter of that range (or by much less, where the previous picture lies at one end of that range, or by a little, where it did so in the same direction on the frame before), or the network itself had given the pixel a middle or a very high weight. In motion the weight is kept and, beside anything that moves differently from the pixel, the previous picture is limited to the range "
              "of the nine new samples. Next, at rest and in motion, a spark test: a new sample far outside the previous picture around the pixel is taken, as far as it has a bright neighbor "
              "both sideways and above or below. Two cases then take the new frame alone: a pixel that was hidden a frame ago behind something nearer that moves differently, and one whose "
              "previous picture scrolled in from outside the screen. The pixel is mixed from the new frame and the previous picture with the resulting weight. Last, on every frame, "
              "a change smaller than two to four steps of the stored number format is dropped.",
              "The last shader's rules on a skipped frame", 'What happens to one output pixel when the network did not run. A frame that runs the network goes straight to step 7.', t)
    cx = W / 2
    y = 72
    y = box(o, t, LEFT, y, RIGHT - LEFT, 'What the shader has for this pixel', [
        "the network's weight for the new frame: from its last run, one frame old, moved along with the picture's motion",
        'the previous picture, moved to where its content is now (the "history")',
        'the nine samples of the new frame around the pixel, and the color they give when blended'], 'grid')
    o.append(arrow(cx, y, cx, y + 20, t)); y += 20
    y = box(o, t, LEFT, y, RIGHT - LEFT, 'Start from the weight, squared', [
        'Where the network kept the old picture (weight 0.1), the new frame now counts for very little (0.01).',
        'Where it had given the old picture up (weight near 1), nothing changes.'], 'lossy', '1')
    o.append(arrow(cx, y, cx, y + 20, t)); y += 20
    y = box(o, t, LEFT, y, RIGHT - LEFT, 'Is the picture at rest here?', [
        'At rest = the motion kept for these 2x2 pixels is zero, and nothing looked at around them (3 and 8 cells to each',
        'side) moves differently.'], 'lossy', '2')
    # the two branches
    half = (RIGHT - LEFT - 16) / 2
    xl, xr = LEFT, LEFT + half + 16
    o += [arrow(xl + half / 2, y, xl + half / 2, y + 30, t), arrow(xr + half / 2, y, xr + half / 2, y + 30, t),
          text(xl + half / 2 + 8, y + 19, 'yes, at rest', t, 11, 'muted'), text(xr + half / 2 + 8, y + 19, 'no, it moves', t, 11, 'muted')]
    y += 30
    yl = box(o, t, xl, y, half, 'Take nothing from the new frame', [
        'The weight becomes 0. Fine detail then shimmers no more',
        "than with AMD's shaders. Unless the content changed",
        'without the game reporting motion:',
        '',
        '  a  the history lies outside the range of the nine new',
        '      samples (by a quarter of that range), or',
        '  b  the blended new frame differs from the history by',
        '      more than a quarter of that range (far less where',
        '      the history lies at one end of the range, and by a',
        '      little where it did so the frame before too), or',
        '  c  the network itself had given a middle weight, about',
        '      0.2 to 0.7 (slowly swaying leaves), or one above',
        '      0.95 (particles, embers).',
        '',
        'Then the weight is kept (in case c: the network\'s own).'], 'lossy', '3')
    yr = box(o, t, xr, y, half, 'Keep the weight, limit the history', [
        'Beside anything that moves differently from this pixel',
        '(edges of moving things), the history is held inside the',
        'range of the nine new samples. Where the picture',
        'changed, a plausible color is mixed in instead of an',
        'outdated one.',
        '',
        'Elsewhere the history is left as it is. The nine samples',
        'miss a thing far thinner than a rendered pixel (a distant',
        'wire) on most frames, and the limit would take it away.',
        '',
        '',
        '',
        '',
        '',
        'Not applied at rest.'], 'lossy', '4')
    y = max(yl, yr)
    o += [line(xl + half / 2, y, xl + half / 2, y + 12, t, 'muted', 1.5), line(xr + half / 2, y, xr + half / 2, y + 12, t, 'muted', 1.5),
          line(xl + half / 2, y + 12, xr + half / 2, y + 12, t, 'muted', 1.5), arrow(cx, y + 12, cx, y + 32, t)]
    y += 32
    y = box(o, t, LEFT, y, RIGHT - LEFT, 'Spark test, at rest and in motion', [
        'If the nearest new sample lies far outside the 3x3 history pixels around this pixel, take the new frame, the more the',
        'further outside it is. The sample counts only as far as it has a bright neighbor both sideways and above or below:',
        'a spark is a spot, while a single over-bright pixel (reflection noise) or a one-pixel line (rain, a wire) is not.'], 'lossy', '5')
    o.append(arrow(cx, y, cx, y + 20, t)); y += 20
    y = box(o, t, LEFT, y, RIGHT - LEFT, 'Two cases take the new frame alone', [
        'Just uncovered: what was at this place a frame ago was nearer to the camera and moves differently, so the history',
        'here still shows the thing that was in front.',
        'Scrolled in: the history is far darker than the new frame in every color channel, because it came from outside the',
        'screen when the camera began to turn.'], 'lossy', '6')
    o.append(arrow(cx, y, cx, y + 20, t)); y += 20
    y = box(o, t, LEFT, y, RIGHT - LEFT, 'Mix:   weight x new frame  +  (1 - weight) x history', [], 'grid')
    o.append(arrow(cx, y, cx, y + 20, t)); y += 20
    y = box(o, t, LEFT, y, RIGHT - LEFT, 'Dead band, on every frame (also those that run the network)', [
        'If no color channel would change by more than two to four steps of the number format the history is stored in,',
        'the history is kept exactly. This is what keeps flat areas at rest steady.'], 'exact', '7')
    o.append(arrow(cx, y, cx, y + 20, t)); y += 20
    y = box(o, t, LEFT, y, RIGHT - LEFT, 'Shown on screen, and stored as the history for the next frame', [], 'grid')
    o.append(text(LEFT, y + 22, 'Orange: only on frames that skip the network. Blue: on every frame. The thresholds are the defaults of the tool that writes these rules.', t, 11, 'muted'))
    assert y + 34 <= H, y
    return o


for name in ('light', 'dark'):
    with open(f'rules-flow-{name}.svg', 'w') as f:
        f.write('\n'.join(flow(THEMES[name]) + ['</svg>']) + '\n')
    print(f'rules-flow-{name}.svg')
