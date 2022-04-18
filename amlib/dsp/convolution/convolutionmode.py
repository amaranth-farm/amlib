#!/usr/bin/env python3
#
# Copyright (c) 2022 Rouven Broszeit <roubro1991@gmx.de>
# SPDX-License-Identifier: CERN-OHL-W-2.0

from enum import Enum

class ConvolutionMode(Enum):
    CROSSFEED = 1
    STEREO = 2
    MONO = 3

