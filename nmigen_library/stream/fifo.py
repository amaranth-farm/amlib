#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0

from nmigen          import *
from nmigen.lib.fifo import FIFOInterface
from .               import StreamInterface

def connect_fifo_to_stream(m: Module, fifo: FIFOInterface, stream: StreamInterface) -> None:
    m.d.comb += [
        stream.valid.eq(fifo.r_rdy & fifo.r_en),
        fifo.r_en.eq(stream.ready),
        stream.payload.eq(fifo.r_data),
    ]

def connect_stream_to_fifo(m: Module, stream: StreamInterface, fifo: FIFOInterface) -> None:
    m.d.comb += [
        fifo.w_en.eq(stream.valid),
        stream.ready.eq(fifo.w_rdy),
        fifo.w_data.eq(stream.payload),
    ]