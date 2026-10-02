#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Test data for bench/mbench: a tensor buffer of small values and a weights buffer with small
# biases at the offsets pass 1 reads, so that most values stay inside the clamps and the rounding
# paths are exercised (full-range random data saturates almost everything).
#   make_test_data.py    writes small_scratch.bin (83 MB) and small_weights.bin
import numpy as np

rng = np.random.default_rng(1)
rng.integers(-9, 10, size=83232256, dtype=np.int8).tofile('small_scratch.bin')
w = rng.integers(0, 256, size=131072, dtype=np.uint8).view(np.int32).copy()
w[864:880] = rng.integers(-3000, 3000, 16)        # biases of the 3x3 convolution
w[1024:1056] = rng.integers(-30000, 30000, 32)    # biases of the 1x1 16 -> 32 layer
w[1184:1200] = rng.integers(-60000, 60000, 16)    # biases of the 1x1 32 -> 16 layer
w.tofile('small_weights.bin')
