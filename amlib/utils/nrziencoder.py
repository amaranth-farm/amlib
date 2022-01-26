#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0
#
"""Encode a stream of bits to NRZI"""

from amaranth import Elaboratable, Signal, Module, Mux

class NRZIEncoder(Elaboratable):
    """Converts a synchronous stream of bits into a NRZI encoded stream"""

    def __init__(self):
        self.nrzi_out   = Signal()
        self.data_in    = Signal()

    def elaborate(self, platform) -> Module:
        """ build the module """
        m = Module()

        m.d.sync += self.nrzi_out.eq(
                        Mux(self.data_in,
                            ~self.nrzi_out,
                            self.nrzi_out)),

        return m
