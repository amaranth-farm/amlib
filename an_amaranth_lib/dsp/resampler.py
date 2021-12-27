#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0

import math
from amaranth import *
from amaranth.lib.fifo import SyncFIFO
from an_amaranth_lib.stream import StreamInterface
from .filterbank import Filterbank

from ..test   import GatewareTestCase, sync_test_case

class FractionalResampler(Elaboratable):
    """Fractional Resampler
        converts a signal to a different samplerate by a
        fractional factor M/N by means of:
        1. upsampling the signal by factor M
        2. low pass filtering the upsampled signal
        3. decimating the filtered signal by factor N

        Currently only fir filtering is supported and recommended.
        IIR filtering has not been tested working yet.
    """
    def __init__(self, *,
                 input_samplerate:  int,
                 upsample_factor:   int,
                 downsample_factor: int,
                 filter_structure:  str  ='fir', # or 'iir'
                 filter_instances:  int  = 1,
                 filter_order:      int  = 24,
                 filter_cutoff:     int  = 20000,
                 bitwidth:          int  = 16,
                 prescale:          int  = None,
                 verbose:           bool = True) -> None:
        self.signal_in  = StreamInterface(payload_width=bitwidth)
        self.signal_out = StreamInterface(payload_width=bitwidth)

        self.input_samplerate = input_samplerate
        self.upsample_factor = upsample_factor
        self.downsample_factor = downsample_factor
        self.filter_structure = filter_structure
        self.filter_order = filter_order
        self.filter_instances = filter_instances
        self.filter_cutoff = filter_cutoff
        self.bitwidth = bitwidth
        self.verbose = verbose
        self.prescale = prescale

    def elaborate(self, platform) -> Module:
        m = Module()

        # FPGA multipliers are multiples of 9 bit wide
        # so add 1 bit of headroom for every 8 bits
        headroom_bitwidth = int(math.ceil(self.bitwidth/8) * 9)

        if self.filter_structure == 'iir':
            prescale = (self.upsample_factor - 1) if self.prescale is None else self.prescale
        else:
            prescale = 4 if self.prescale is None else self.prescale

        m.submodules.antialiasingfilter = antialiasingfilter = \
            Filterbank(self.filter_instances,
                       self.input_samplerate * self.upsample_factor,
                       bitwidth=headroom_bitwidth,
                       filter_structure=self.filter_structure,
                       cutoff_freq=self.filter_cutoff,
                       filter_order=self.filter_order,
                       verbose=self.verbose)

        m.submodules.downsamplefifo = downsamplefifo = \
            SyncFIFO(width=self.bitwidth, depth=self.upsample_factor)

        # upsampling
        upsampled_signal  = Signal(signed(headroom_bitwidth))
        upsample_counter  = Signal(range(self.upsample_factor))
        input_data        = Signal(signed(self.bitwidth))
        input_ready       = Signal()
        input_valid       = Signal()

        m.d.comb += [
            self.signal_in.ready.eq(input_ready),
            input_valid.eq(self.signal_in.valid),
            input_ready.eq((upsample_counter == 0) & (downsamplefifo.w_rdy)),
            input_data.eq(self.signal_in.payload.as_signed()),
            antialiasingfilter.signal_in.eq(upsampled_signal),
            antialiasingfilter.enable_in.eq(upsample_counter > 0),
            downsamplefifo.w_en.eq(downsamplefifo.w_rdy & antialiasingfilter.enable_in),
        ]

        with m.If(input_valid & input_ready):
            m.d.comb += [
                upsampled_signal.eq(input_data * Const(prescale)),
                antialiasingfilter.enable_in.eq(1),
            ]
            m.d.sync += upsample_counter.eq(self.upsample_factor - 1)
        with m.Elif(upsample_counter > 0):
            m.d.comb += upsampled_signal.eq(0)
            m.d.sync += upsample_counter.eq(upsample_counter - 1)

        # downsampling and output
        downsample_counter = Signal(range(self.downsample_factor))

        m.d.comb += [
            downsamplefifo.w_data.eq(antialiasingfilter.signal_out),
            self.signal_out.valid.eq(downsamplefifo.r_rdy),
        ]

        with m.If(downsamplefifo.r_rdy & self.signal_out.ready):
            m.d.comb += downsamplefifo.r_en.eq(1)

            with m.If(downsample_counter == 0):
                m.d.sync += downsample_counter.eq(self.downsample_factor - 1)
                m.d.comb += [
                    self.signal_out.payload.eq(downsamplefifo.r_data),
                    self.signal_out.valid.eq(1),
                ]
            with m.Else():
                m.d.sync += downsample_counter.eq(downsample_counter - 1)
                m.d.comb += self.signal_out.valid.eq(0)

        with m.Else():
            m.d.comb += [
                downsamplefifo.r_en.eq(0),
                self.signal_out.valid.eq(0),
            ]

        return m

class ResamplerTestFIR(GatewareTestCase):
    FRAGMENT_UNDER_TEST = FractionalResampler
    FRAGMENT_ARGUMENTS = dict(
        filter_structure='fir', filter_instances=1, filter_order=24, \
        input_samplerate=56000, upsample_factor=6, downsample_factor=7, \
        filter_cutoff=20000, prescale=4)

    @sync_test_case
    def test_fir(self):
        dut = self.dut
        max = int(2**15 - 1)
        min = -max
        for _ in range(10): yield
        yield dut.signal_out.ready.eq(1)
        for i in range(600):
            yield
            if i < 250:
                if i % 6 == 0:
                    yield dut.signal_in.valid.eq(1)
                    yield dut.signal_in.payload.eq(max)
                else:
                    yield dut.signal_in.valid.eq(0)
            elif i == 500:
                yield dut.signal_out.ready.eq(0)
            else:
                if i % 6 == 0:
                    yield dut.signal_in.valid.eq(1)
                    yield dut.signal_in.payload.eq(min)
                else:
                    yield dut.signal_in.valid.eq(0)

class ResamplerTestIIR(GatewareTestCase):
    FRAGMENT_UNDER_TEST = FractionalResampler
    FRAGMENT_ARGUMENTS = dict(
        filter_structure='iir', input_samplerate=56000, \
        upsample_factor=6, downsample_factor=7, filter_cutoff=20000, prescale=4)

    @sync_test_case
    def test_iir(self):
        dut = self.dut
        max = int(2**15 - 1)
        min = -max
        for _ in range(10): yield
        yield dut.signal_out.ready.eq(1)
        for i in range(600):
            yield
            if i < 250:
                if i % 6 == 0:
                    yield dut.signal_in.valid.eq(1)
                    yield dut.signal_in.payload.eq(max)
                else:
                    yield dut.signal_in.valid.eq(0)
            elif i == 500:
                yield dut.signal_out.ready.eq(0)
            else:
                if i % 6 == 0:
                    yield dut.signal_in.valid.eq(1)
                    yield dut.signal_in.payload.eq(min)
                else:
                    yield dut.signal_in.valid.eq(0)