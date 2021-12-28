#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0
#
from .fixedpointiirfilter import FixedPointIIRFilter
from .fixedpointfirfilter import FixedPointFIRFilter
from amaranth import *

class Filterbank(Elaboratable):
    def __init__(self, num_instances,
                 samplerate:       int,
                 bitwidth:         int=18,
                 fraction_width:   int=18,
                 cutoff_freq:      int=20000,
                 filter_order:     int=2,
                 filter_structure: str='fir', # or 'iir'
                 filter_type:      str='lowpass',
                 verbose:          bool=True) -> None:

        self.enable_in  = Signal()
        self.signal_in  = Signal(signed(bitwidth))
        self.signal_out = Signal(signed(bitwidth))

        if filter_structure == 'iir':
            self.filters = [FixedPointIIRFilter(samplerate=samplerate,
                                                bitwidth=bitwidth, fraction_width=fraction_width,
                                                cutoff_freq=cutoff_freq, filter_order=filter_order,
                                                filter_type=filter_type, verbose=verbose)
                            for _ in range(num_instances)]
        elif filter_structure == 'fir':
            self.filters = [FixedPointFIRFilter(samplerate=samplerate,
                                                bitwidth=bitwidth, fraction_width=fraction_width,
                                                cutoff_freq=cutoff_freq, filter_order=filter_order,
                                                filter_type=filter_type, verbose=verbose)
                            for _ in range(num_instances)]
        else:
            assert False, f"Unsupported filter structure '{filter_structure}', supported are: 'fir' and 'iir'"

    def elaborate(self, platform) -> Module:
        m = Module()

        last_filter = None

        for f in self.filters:
            m.submodules += f
            m.d.comb += f.enable_in.eq(self.enable_in)

            if last_filter is not None:
                m.d.comb += f.signal_in.eq(last_filter.signal_out)

            last_filter = f

        m.d.comb += [
            self.filters[0].signal_in.eq(self.signal_in),
            self.signal_out.eq(self.filters[-1].signal_out)
        ]

        return m