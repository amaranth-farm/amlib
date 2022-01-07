#!/usr/bin/env python3
#
# Copyright (c) 2021 Kaz Kojima <kkojima@rr.iij4u.or.jp>
# SPDX-License-Identifier: CERN-OHL-W-2.0

from scipy import signal
from amaranth import *
from pprint import pformat
import numpy as np

from ..test   import GatewareTestCase, sync_test_case

class FixedPointHBFilter(Elaboratable):
    def __init__(self,
                 bitwidth:       int=18,
                 fraction_width: int=18,
                 filter_order:   int=19,
                 mac_loop:       bool = False,
                 verbose:        bool=True) -> None:

        self.strobe_in  = Signal()
        self.strobe_out = Signal()
        self.signal_in  = Signal(signed(bitwidth))
        self.signal_out = Signal(signed(bitwidth))

        assert (filter_order & 1) and (filter_order//2 & 1), f"Supported only 4m+3 filter_order {filter_order}"
        # firwin might give lower attenuation/ripple but slower transition band
        # use remez now for the transition band
        # taps = signal.firwin(filter_order, 0.5)
        bands = np.array([0.0, 0.22, 0.28, 0.5])
        taps = signal.remez(filter_order, bands, [1, 0], [1, 1])

        # convert to fixed point representation
        self.bitwidth = bitwidth
        self.fraction_width = fraction_width
        assert bitwidth <= fraction_width, f"Bitwidth {bitwidth} must not exceed {fraction_width}"
        self.taps = taps_fp = [int(x * 2**fraction_width) for x in taps]

        self.mac_loop = mac_loop

        if verbose:
            print(f"{filter_order}-order windowed Half Band")
            print(f"taps: {pformat(taps)}")
            print(f"taps ({bitwidth}.{fraction_width} fixed point): {taps_fp}\n")

        def conversion_error(coeff, fp_coeff):
            val = 2**(bitwidth - 1)
            fp_product = fp_coeff * val
            fp_result  = fp_product >> fraction_width
            fp_error   = fp_result - (coeff * val)
            return fp_error

        num_coefficients = len(taps_fp)
        conversion_errors = [abs(conversion_error(taps[i], taps_fp[i])) for i in range(num_coefficients)]
        if verbose:
            print("a, fixed point conversion errors: {}".format(conversion_errors))
        for i in range(num_coefficients):
            assert (conversion_errors[i] < 1.0)

    def elaborate(self, platform) -> Module:
        m = Module()

        n = len(self.taps)
        width = self.bitwidth + self.fraction_width
        taps = Array(Const(n, signed(width)) for n in self.taps)
        decimate_counter = Signal(range(0, 2))

        # we use the array indices flipped, ascending from zero
        # so x[0] is x_n, x[1] is x_n-
        # 1, x[2] is x_n-2 ...
        # in other words: higher indices are past values, 0 is most recent
        x = Array(Signal(signed(width), name=f"x{i}") for i in range(n))

        if self.mac_loop:
            ix = Signal(range(n + 2))
            madd = Signal(signed(self.bitwidth + 1))
            a = Signal(signed(self.bitwidth + 1))
            b = Signal(signed(self.bitwidth))

            with m.FSM(reset="IDLE"):
                with m.State("IDLE"):
                    with m.If(self.strobe_in):
                        m.d.sync += [
                            ix.eq(2),
                            a.eq(x[0] + x[n - 1]),
                            b.eq(taps[0]),
                            madd.eq(0)
                        ]
                        m.next = "MAC"

                with m.State("MAC"):
                    m.d.sync += madd.eq(madd + ((a * b) >> self.fraction_width))
                    with m.If(ix > n//2):
                        m.next = "OUTPUT"
                    with m.Else():
                        m.d.sync += [
                            a.eq(x[ix] + x[n - 1 - ix]),
                            b.eq(taps[ix]),
                            ix.eq(ix + 2)
                        ]

                with m.State("OUTPUT"):
                    m.d.sync += self.signal_out.eq(madd + (x[n//2] >> 1))
                    m.next = "IDLE"

        else:
            m.d.comb += self.signal_out.eq(
                sum([(((x[2*i] + x[n - 1 - 2*i]) * taps[2*i]) >> self.fraction_width) for i in range(n//4 + 1)], (x[n//2] >> 1)))

        with m.If(self.strobe_in):
            m.d.sync += x[0].eq(self.signal_in)
            m.d.sync += [x[i + 1].eq(x[i]) for i in range(n - 1)]
            with m.If(decimate_counter < 1):
                m.d.sync += decimate_counter.eq(decimate_counter + 1)
            with m.Else():
                m.d.sync += decimate_counter.eq(0)
                m.d.sync += self.strobe_out.eq(1)

        with m.If(self.strobe_out):
            m.d.sync += self.strobe_out.eq(0)

        return m


class FixedPointHBFilterTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = FixedPointHBFilter
    FRAGMENT_ARGUMENTS = dict()

    @sync_test_case
    def test_hb(self):
        dut = self.dut
        max = int(2**15 - 1)
        min = -max
        for i in range(8192):
            yield dut.signal_in.eq(min if ((i//64) & 1) else max)
            yield
            yield dut.strobe_in.eq(1)
            yield
            yield dut.strobe_in.eq(0)
            yield
            for _ in range(58): yield
