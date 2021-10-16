from nmigen import *
from nmigen.build import Platform

class SimpleClockDivider(Elaboratable):
    def __init__(self, divisor, clock_polarity=0):
        # parameters
        self.clock_polarity  = clock_polarity
        assert divisor % 2 == 0, "divisor must be even"
        self._divisor        = divisor // 2

        # I/O
        self.clock_enable_in = Signal()
        self.clock_out       = Signal(reset=clock_polarity)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        clock_counter = Signal(range(self._divisor))

        with m.If(clock_counter >= (self._divisor - 1)):
            with m.If(self.clock_enable_in):
                m.d.sync += self.clock_out.eq(~self.clock_out),
            with m.Else():
                m.d.sync += self.clock_out.eq(self.clock_polarity)

            m.d.sync += clock_counter.eq(0)

        with m.Else():
            m.d.sync += clock_counter.eq(clock_counter + 1)

        return m