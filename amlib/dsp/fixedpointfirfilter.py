#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0

from scipy import signal
from amaranth import *
from pprint import pformat
import numpy as np

from ..test   import GatewareTestCase, sync_test_case

class FixedPointFIRFilter(Elaboratable):
    def __init__(self,
                 samplerate:     int,
                 bitwidth:       int=18,
                 fraction_width: int=18,
                 cutoff_freq:    int=20000,
                 filter_order:   int=24,
                 filter_type:    str='lowpass',
                 weight:         list=None,
                 mac_loop:       bool=False,
                 verbose:        bool=True) -> None:

        self.enable_in  = Signal()
        self.signal_in  = Signal(signed(bitwidth))
        self.signal_out = Signal(signed(bitwidth))

        if type(cutoff_freq) == int:
            cutoff = cutoff_freq / samplerate
            taps = signal.firwin(filter_order, cutoff, fs=samplerate, pass_zero=filter_type, window='hamming')
        elif type(cutoff_freq) == list and len(cutoff_freq) == 2:
            Fs = samplerate
            Fpb = cutoff_freq[0]
            Fsb = cutoff_freq[1]
            bands = np.array([0., Fpb/Fs, Fsb/Fs, .5])
            pass_zero = filter_type == True or filter_type == 'lowpass'
            desired = [1, 0] if pass_zero else [0, 1]
            taps = signal.remez(filter_order, bands, desired, weight)
        else:
            raise TypeError('cutoff_freq parameter must be int or list of start/stop band frequencies')
        # convert to fixed point representation
        self.bitwidth = bitwidth
        self.fraction_width = fraction_width
        assert bitwidth <= fraction_width, f"Bitwidth {bitwidth} must not exceed {fraction_width}"
        self.taps = taps_fp = [int(x * 2**fraction_width) for x in taps]

        self.mac_loop = mac_loop

        if verbose:
            if type(cutoff_freq) == int:
                print(f"{filter_order}-order windowed FIR with cutoff: {cutoff * samplerate}")
            else:
                print(f"{filter_order}-order FIR with start/stop band: {cutoff_freq} weight: {weight}")
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

        # we use the array indices flipped, ascending from zero
        # so x[0] is x_n, x[1] is x_n-
        # 1, x[2] is x_n-2 ...
        # in other words: higher indices are past values, 0 is most recent
        x = Array(Signal(signed(width), name=f"x{i}") for i in range(n))

        if self.mac_loop:
            ix = Signal(range(n + 1))
            madd = Signal(signed(self.bitwidth))
            a = Signal(signed(self.bitwidth))
            b = Signal(signed(self.bitwidth))

            with m.FSM(reset="IDLE"):
                with m.State("IDLE"):
                    with m.If(self.enable_in):
                        m.d.sync += [
                            ix.eq(1),
                            a.eq(x[0]),
                            b.eq(taps[0]),
                            madd.eq(0)
                        ]
                        m.next = "MAC"

                with m.State("MAC"):
                    m.d.sync += madd.eq(madd + ((a * b) >> self.fraction_width))
                    with m.If(ix == n):
                        m.next = "OUTPUT"
                    with m.Else():
                        m.d.sync += [
                            a.eq(x[ix]),
                            b.eq(taps[ix]),
                            ix.eq(ix + 1)
                        ]

                with m.State("OUTPUT"):
                    m.d.sync += self.signal_out.eq(madd)
                    m.next = "IDLE"

        else:
            m.d.comb += self.signal_out.eq(
                sum([((x[i] * taps[i]) >> self.fraction_width) for i in range(n)]))

        with m.If(self.enable_in):
            m.d.sync += [x[i + 1].eq(x[i]) for i in range(n - 1)]

            m.d.sync += x[0].eq(self.signal_in)

        return m


class FixedPointFIRFilterTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = FixedPointFIRFilter
    FRAGMENT_ARGUMENTS = dict(samplerate=336000)

    @sync_test_case
    def test_fir(self):
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

