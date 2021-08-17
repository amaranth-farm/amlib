# Copyright (C) 2021 Hans Baier hansfbaier@gmail.com
#
# SPDX-License-Identifier: Apache-2.0

import sys
sys.path.append('.')

from nmigen import *
from nmigen.sim import Simulator, Tick
from nmigen_library.stream.i2c import I2CStreamTransmitter
from nmigen_library.io.i2c import I2CTestbench

def testbench():
    pads = I2CTestbench()
    dut = I2CStreamTransmitter(pads, 4, clk_stretch=False)

    sim = Simulator(dut)
    sim.add_clock(1.0/100e6, domain="sync")

    def sync_process():
        yield
        yield
        yield dut.stream_in.valid.eq(1)
        yield dut.stream_in.payload.eq(0x55)
        yield dut.stream_in.first.eq(1)
        yield
        yield dut.stream_in.valid.eq(1)
        yield dut.stream_in.payload.eq(0xaa)
        yield dut.stream_in.first.eq(1)
        yield
        yield dut.stream_in.first.eq(0)
        yield dut.stream_in.payload.eq(0xbb)
        yield
        yield dut.stream_in.last.eq(1)
        yield dut.stream_in.payload.eq(0xcc)
        yield
        yield dut.stream_in.valid.eq(0)
        yield dut.stream_in.last.eq(0)
        yield
        yield dut.i2c.bus.sda_o.eq(0)
        yield
        yield
        for _ in range(330): yield

    sim.add_sync_process(sync_process)

    with sim.write_vcd("i2c_stream_transmitter.vcd"):
        sim.run()

if __name__ == "__main__":
    testbench()
