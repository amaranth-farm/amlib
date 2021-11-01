from math import log2

from nmigen import *
from nmigen.utils import bits_for
from nmigen.build import Platform

from ..test   import GatewareTestCase, sync_test_case

"""
Timing parameters for the WS2811
The LEDs are reset by driving D0 low for at least 50us.
Data is transmitted using a 800kHz signal.
A '1' is 50% duty cycle, a '0' is 20% duty cycle.
"""
class WS2812(Elaboratable):
    def __init__(self, *, sys_clock_freq, num_leds):
        # parameters
        self.num_leds          = num_leds
        self.full_cycle_length = sys_clock_freq // 800e3
        self.low_cycle_length  = int(0.32 * self.full_cycle_length)
        self.high_cycle_length = int(0.64 * self.full_cycle_length)
        print(f"full cycle: {self.full_cycle_length}")

        # I / O
        self.red_in   = Array(Signal(8, name=f"red_{n}")   for n in range(num_leds))
        self.green_in = Array(Signal(8, name=f"green_{n}") for n in range(num_leds))
        self.blue_in  = Array(Signal(8, name=f"blue_{n}")  for n in range(num_leds))
        self.data_out = Signal()

        self.start_in  = Signal()
        self.done_out  = Signal()

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        grb = Signal(3 * 8)

        led_counter = Signal(bits_for(self.num_leds) + 1)
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
                            grb.eq(Cat(self.blue_in[led_counter], self.red_in[led_counter], self.green_in[led_counter])),
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
                    with m.If(bit_counter < 23):
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
                        with m.If(led_counter < self.num_leds):
                            m.d.sync += [
                                grb.eq(Cat(self.blue_in[led_counter], self.red_in[led_counter], self.green_in[led_counter])),
                            ]

                        # if all LEDS' data has been transmitted, send another reset
                        with m.Else():
                            m.next = "RESET"

        return m

class WS2812Test(GatewareTestCase):
    FRAGMENT_UNDER_TEST = WS2812
    FRAGMENT_ARGUMENTS = dict(sys_clock_freq=8e6, num_leds=3)

    @sync_test_case
    def test_spi_interface(self):
        dut = self.dut
        yield
        yield
        yield
        yield dut.red_in[0]   .eq(0xff)
        yield dut.green_in[0] .eq(0x0)
        yield dut.blue_in[0]  .eq(0x0)

        yield dut.red_in[1]   .eq(0x0)
        yield dut.green_in[1] .eq(0xff)
        yield dut.blue_in[1]  .eq(0x0)

        yield dut.red_in[2]   .eq(0x0)
        yield dut.green_in[2] .eq(0x0)
        yield dut.blue_in[2]  .eq(0xff)

        yield
        yield from self.pulse(dut.start_in)
        yield
        yield from self.advance_cycles(1000)