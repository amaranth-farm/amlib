
# Copyright (C) 2021 Hans Baier hansfbaier@gmail.com
#
# SPDX-License-Identifier: Apache-2.0

from nmigen import *
from nmigen.build import Platform
from nmigen.lib.fifo import SyncFIFO

from . import StreamInterface
from .fifo import connect_stream_to_fifo
from ..io.i2c import I2CInitiator

class I2CStreamTransmitter(Elaboratable):
    def __init__(self, pads, period_cyc, clk_stretch=True, fifo_depth=16):
        self.pads      = pads
        self.stream_in = StreamInterface()

        self._period_cyc  = period_cyc
        self._clk_stretch = clk_stretch
        self._fifo_depth  = fifo_depth

        self.i2c = I2CInitiator(self.pads, self._period_cyc, self._clk_stretch)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.i2c = i2c = self.i2c
        m.submodules.input_fifo = in_fifo = SyncFIFO(width=8 + 2, depth=self._fifo_depth)
        m.d.comb += [
            connect_stream_to_fifo(self.stream_in, in_fifo),
            in_fifo.w_data[8].eq(self.stream_in.first),
            in_fifo.w_data[9].eq(self.stream_in.last),
        ]

        payload = in_fifo.r_data[:8]
        first   = in_fifo.r_data[8]
        last    = in_fifo.r_data[9]

        # strobes are low by default
        m.d.comb += [
            i2c.start.eq(0),
            i2c.stop.eq(0),
            i2c.read.eq(0),
            i2c.write.eq(0),
            in_fifo.r_en.eq(0),
        ]

        with m.FSM():
            with m.State("IDLE"):
                with m.If(~i2c.busy & in_fifo.r_rdy & first):
                    m.d.comb += i2c.start.eq(1)
                    m.next = "STREAMING"

            with m.State("STREAMING"):
                with m.If(~i2c.busy):
                    m.d.comb += [
                        i2c.data_i.eq(payload),
                        i2c.write.eq(1),
                    ]

                    with m.If(in_fifo.r_rdy):
                        m.d.comb += in_fifo.r_en.eq(1)

                    with m.If(last):
                        m.next = "STOP"

            with m.State("STOP"):
                with m.If(~i2c.busy):
                    m.d.comb += i2c.stop.eq(1)
                    m.next = "IDLE"

        return m