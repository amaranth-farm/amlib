#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: BSD-3-Clause

from nmigen          import *
from nmigen.lib.fifo import FIFOInterface
from .               import StreamInterface

def connect_fifo_to_stream(fifo: FIFOInterface, stream: StreamInterface) -> None:
    return [
        stream.valid.eq(fifo.r_rdy & fifo.r_en),
        fifo.r_en.eq(stream.ready),
        stream.payload.eq(fifo.r_data),
    ]

def connect_stream_to_fifo(stream: StreamInterface, fifo: FIFOInterface) -> None:
    return [
        fifo.w_en.eq(stream.valid),
        stream.ready.eq(fifo.w_rdy),
        fifo.w_data.eq(stream.payload),
    ]