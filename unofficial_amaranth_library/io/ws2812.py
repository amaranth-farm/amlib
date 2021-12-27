# Copyright (C) 2021 Hans Baier hansfbaier@gmail.com
#
# SPDX-License-Identifier: Apache-2.0
#
from math import log2

from amaranth import *
from amaranth.utils import bits_for
from amaranth.build import Platform

from ..test   import GatewareTestCase, sync_test_case

"""
Timing parameters for the WS2811
The LEDs are reset by driving D0 low for at least 50us.
Data is transmitted using a 800kHz signal.
A '1' is 50% duty cycle, a '0' is 20% duty cycle.
"""
class WS2812(Elaboratable):
    def __init__(self, *, sys_clock_freq, no_leds):
        # parameters
        self.no_leds           = no_leds
        self.full_cycle_length = sys_clock_freq // 800e3
        self.low_cycle_length  = int(0.32 * self.full_cycle_length)
        self.high_cycle_length = int(0.64 * self.full_cycle_length)
        print(f"full cycle: {self.full_cycle_length}")

        self.mem = Memory(width=24, depth=no_leds, name="led_memory")

        # I / O
        self.red_in          = Signal(8)
        self.green_in        = Signal(8)
        self.blue_in         = Signal(8)
        self.led_address_in  = Signal(range(no_leds))
        self.write_enable_in = Signal()

        self.data_out = Signal()

        self.start_in  = Signal()
        self.done_out  = Signal()

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        m.submodules.read_port  = mem_read_port  = self.mem.read_port()
        m.submodules.write_port = mem_write_port = self.mem.write_port()

        grb = Signal(3 * 8)

        led_counter = Signal(bits_for(self.no_leds) + 1)
        bit_counter = Signal(5)
        current_bit = Signal()

        cycle_counter_width  = bits_for(int(self.full_cycle_length)) + 1
        cycle_counter        = Signal(cycle_counter_width)
        current_cycle_length = Signal.like(cycle_counter)

        print(f"cycle counter: {cycle_counter_width}")

        m.d.comb += [
            self.data_out.eq(1),
            current_bit.eq(grb[23]),
            current_cycle_length.eq(Mux(current_bit, self.high_cycle_length, self.low_cycle_length)),
            mem_write_port.addr.eq(self.led_address_in),
            mem_write_port.data.eq(Cat(self.blue_in, self.red_in, self.green_in)),
            mem_write_port.en.eq(self.write_enable_in),
            mem_read_port.addr.eq(led_counter),
        ]

        with m.FSM():
            with m.State("IDLE"):
                with m.If(self.start_in):
                    m.d.sync += led_counter.eq(0)
                    m.next = "RESET"

            with m.State("RESET"):
                m.d.comb += self.data_out.eq(0)
                m.d.sync += cycle_counter.eq(cycle_counter + 1)

                with m.If(cycle_counter >= Const(self.full_cycle_length)):
                    m.d.sync += cycle_counter.eq(0)

                    with m.If(led_counter == 0):
                        m.d.sync += [
                            grb.eq(mem_read_port.data),
                            led_counter.eq(led_counter + 1),
                        ]
                        m.next = "TRANSMIT"

                    with m.Else():
                        m.d.comb += self.done_out.eq(1)
                        m.d.sync += led_counter.eq(0)
                        m.next = "IDLE"

            with m.State("TRANSMIT"):
                m.d.sync += cycle_counter.eq(cycle_counter + 1)

                with m.If(cycle_counter < current_cycle_length):
                    m.d.comb += self.data_out.eq(1)
                with m.Else():
                    m.d.comb += self.data_out.eq(0)

                with m.If(cycle_counter >= Const(self.full_cycle_length)):
                    m.d.sync += cycle_counter.eq(0)

                    last_bit = 23
                    with m.If(bit_counter < last_bit):
                        m.d.sync += [
                            grb.eq(grb << 1),
                            bit_counter.eq(bit_counter + 1),
                        ]
                    with m.Else():
                        m.d.sync += [
                            bit_counter.eq(0),
                            led_counter.eq(led_counter + 1),
                        ]

                        # transmit each LED's data
                        with m.If(led_counter < self.no_leds):
                            m.d.sync += grb.eq(mem_read_port.data),

                        # if all LEDS' data has been transmitted, send another reset
                        with m.Else():
                            m.next = "RESET"

        return m

class WS2812Test(GatewareTestCase):
    FRAGMENT_UNDER_TEST = WS2812
    FRAGMENT_ARGUMENTS = dict(sys_clock_freq=8e6, no_leds=3)

    def write_led_color(self, dut, led_no, red, green, blue):
        yield dut.red_in   .eq(red)
        yield dut.green_in .eq(green)
        yield dut.blue_in  .eq(blue)
        yield dut.led_address_in.eq(led_no)
        yield from self.pulse(dut.write_enable_in)
        yield

    @sync_test_case
    def test_spi_interface(self):
        dut = self.dut
        yield
        yield
        yield
        yield from self.write_led_color(dut, 0, 0xff, 0,    0)
        yield from self.write_led_color(dut, 1, 0,    0xff, 0)
        yield from self.write_led_color(dut, 2, 0,    0,    0xff)

        yield
        yield from self.pulse(dut.start_in)
        yield
        yield from self.advance_cycles(1000)