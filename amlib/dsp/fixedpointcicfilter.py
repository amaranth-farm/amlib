#!/usr/bin/env python3
#
# Copyright (c) 2021 Kaz Kojima <kkojima@rr.iij4u.or.jp>
# SPDX-License-Identifier: CERN-OHL-W-2.0

from amaranth import *
from amaranth import Signal, Module, Elaboratable
from math import log2, ceil

from ..test   import GatewareTestCase, sync_test_case

class FixedPointCICFilter(Elaboratable):
    """ CIC (cascaded integrator comb) filter

        Attributes
        ----------
        signal_in: Signal(width), input
            Filter input signal, must be +-1 only
        strobe_in: Signal(), input
            Input strobe, must be 1 sys clock period
        strobe_out: Signal(), out
            Output strobe
        signal_out: Signal(width), out
            Filter output signal

        Parameters
        ----------
        bitwidth: int
            width
        filter_stage: int
            number of filter stages
        decimation: int
            decimation factor
        verbose: bool
            verbose flag
    """
    def __init__(self,
                 bitwidth:       int=18,
                 filter_stage:   int=4,
                 decimation:     int=12,
                 verbose:        bool=True) -> None:

        self.strobe_in  = Signal()
        self.strobe_out = Signal()
        self.signal_in  = Signal(signed(bitwidth))
        self.signal_out = Signal(signed(bitwidth))

        self.stage = filter_stage
        self.decimation = decimation
        self.bitwidth = bitwidth
        self.delay_width = max(1 + ceil(filter_stage*log2(decimation)), bitwidth)

        if verbose:
            print(f"{filter_stage}-stage CIC with decimation: {decimation}")

    def elaborate(self, platform) -> Module:
        m = Module()

        n = self.stage
        width = self.delay_width
        integrator_edge = self.strobe_in
        comb_edge = Signal()
        decimate_counter = Signal(range(0, self.decimation))
        # we use the array indices flipped, ascending from zero
        # so x[0] is x_n, x[1] is x_n-
        # 1, x[2] is x_n-2 ...
        # in other words: higher indices are past values, 0 is most recent
        # Integrators
        x = Array(Signal(signed(width), name=f"x{i}") for i in range(n))
        # Combs
        y = Array(Signal(signed(width), name=f"y{i}") for i in range(n))
        dy = Array(Signal(signed(width), name=f"dy{i}") for i in range(n))

        m.d.sync += self.strobe_out.eq(comb_edge)

        with m.If(integrator_edge):
            m.d.sync += x[0].eq(self.signal_in + x[0])
            m.d.sync += [x[i + 1].eq(x[i] + x[i + 1]) for i in range(n - 1)]
            with m.If(decimate_counter < self.decimation - 1):
                m.d.sync += decimate_counter.eq(decimate_counter + 1)

            with m.Else():
                m.d.sync += decimate_counter.eq(0)
                m.d.sync += comb_edge.eq(1)

        with m.If(comb_edge):
            m.d.sync += y[0].eq(x[n - 1] - dy[0])
            m.d.sync += [y[i + 1].eq(y[i] - dy[i + 1]) for i in range(n - 1)]
            m.d.sync += self.signal_out.eq(y[n - 1] >> (width - self.bitwidth))
            m.d.sync += dy[0].eq(x[n - 1])
            m.d.sync += [dy[i + 1].eq(y[i]) for i in range(n - 1)]
            m.d.sync += comb_edge.eq(0)

        return m

class FixedPointCICFilterTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = FixedPointCICFilter
    FRAGMENT_ARGUMENTS = dict()

    @sync_test_case
    def test_cic(self):
        dut = self.dut
        N = 1024
        for i in range(N):
            yield dut.signal_in.eq(1 if ((i//256) & 1) == 0 else -1)
            yield
            yield dut.strobe_in.eq(1)
            yield
            yield dut.strobe_in.eq(0)
            yield
