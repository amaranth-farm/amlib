#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0

from math import ceil
from scipy import signal
from amaranth import *
from pprint import pformat

from ..test   import GatewareTestCase, sync_test_case

class FixedPointIIRFilter(Elaboratable):
    def __init__(self,
                 samplerate:     int,
                 bitwidth:       int=18,
                 fraction_width: int=18,
                 cutoff_freq:    int=20000,
                 filter_order:   int=2,
                 filter_type:    str='lowpass',
                 verbose:        bool=False) -> None:

        self.enable_in  = Signal()
        self.signal_in  = Signal(signed(bitwidth))
        self.signal_out = Signal(signed(bitwidth))

        nyquist_frequency = samplerate * 0.5
        cutoff = cutoff_freq / nyquist_frequency
        allowed_ripple = 1.0 # dB
        b, a = signal.cheby1(filter_order, allowed_ripple, cutoff, btype=filter_type, output='ba')

        # convert to fixed point representation
        self.bitwidth = bitwidth
        self.fraction_width = fraction_width
        assert bitwidth <= fraction_width, f"Bitwidth {bitwidth} must not exceed {fraction_width}"
        self.b = b_fp = [int(x * 2**fraction_width) for x in b]
        self.a = a_fp = [int(x * 2**fraction_width) for x in a]

        if verbose:
            print(f"{filter_order}-order Chebyshev-Filter cutoff: {cutoff * nyquist_frequency}" + \
                f" max ripple: {allowed_ripple}dB\n")
            print(f"b: {pformat(b)}")
            print(f"a: {pformat(a)}")
            print(f"b ({bitwidth}.{fraction_width} fixed point): {b_fp}")
            print(f"a ({bitwidth}.{fraction_width} fixed point): {a_fp}\n")
        assert len(b_fp) == len(a_fp)

        def conversion_error(coeff, fp_coeff):
            val = 2**(bitwidth - 1)
            fp_product = fp_coeff * val
            fp_result  = fp_product >> fraction_width
            fp_error   = fp_result - (coeff * val)
            return fp_error

        num_coefficients = len(b)
        conversion_errors_b = [abs(conversion_error(b[i], b_fp[i])) for i in range(num_coefficients)]
        conversion_errors_a = [abs(conversion_error(a[i], a_fp[i])) for i in range(num_coefficients)]
        if verbose:
            print("b, fixed point conversion errors: {}".format(conversion_errors_a))
            print("a, fixed point conversion errors: {}".format(conversion_errors_b))
        for i in range(num_coefficients):
            assert (conversion_errors_b[i] < 1.0)
            assert (conversion_errors_a[i] < 1.0)

    def elaborate(self, platform) -> Module:
        m = Module()

        # see https://en.wikipedia.org/wiki/Infinite_impulse_response
        # and https://en.wikipedia.org/wiki/Digital_filter
        # b are the input coefficients
        # a are the recursive (output) coefficients
        n = len(self.a)
        width = self.bitwidth + self.fraction_width
        b = [Const(n, signed(width)) for n in self.b]
        # the filter design tool generates a '1.0' coefficient for a_n, which we don't need
        a = [Const(n, signed(width)) for n in self.a[1:]]

        # we use the array indices flipped, ascending from zero
        # so x[0] is x_n, x[1] is x_n-1, x[2] is x_n-2 ...
        # in other words: higher indices are past values, 0 is most recent
        x = Array(Signal(signed(width), name=f"x{i}") for i in range(n))
        # because y[0] would be the output value, the y array is shifted by one:
        # y[0] is y_n-1, y[1] is y_n-2, y[2] is y_n-3
        # but the signals are still named 'right' to be easy to understnad
        # in the waveform viewer
        y = Array(Signal(signed(width), name=f"y{i+1}") for i in range(n - 1))

        m.d.comb += self.signal_out.eq(
              sum([((x[i] * b[i]) >> self.fraction_width) for i in range(n)])
            - sum([((y[i] * a[i]) >> self.fraction_width) for i in range(n - 1)]))

        with m.If(self.enable_in):
            m.d.sync += [x[i + 1].eq(x[i]) for i in range(n - 1)]
            m.d.sync += [y[i + 1].eq(y[i]) for i in range(n - 2)]

            m.d.sync += x[0].eq(self.signal_in)
            m.d.sync += y[0].eq(self.signal_out)

        return m

class FixedPointIIRFilterTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = FixedPointIIRFilter
    FRAGMENT_ARGUMENTS = dict(samplerate=336000)

    @sync_test_case
    def test_iir(self):
        dut = self.dut
        max = int(2**15 - 1)
        min = -max
        yield dut.enable_in.eq(1)
        for _ in range(20): yield
        yield dut.signal_in.eq(max)
        for _ in range(100): yield
        yield dut.signal_in.eq(min)
        for _ in range(5): yield
        yield dut.enable_in.eq(0)
        for _ in range(20): yield
        yield dut.enable_in.eq(1)
        for _ in range(60): yield
        yield dut.signal_in.eq(0)
        for _ in range(100): yield
        for i in range(10):
           yield dut.signal_in.eq(max)
           yield
           yield dut.signal_in.eq(0)
           yield
           for _ in range(6): yield
           yield dut.signal_in.eq(min)
           yield
           yield dut.signal_in.eq(0)
           yield
           for _ in range(6): yield
