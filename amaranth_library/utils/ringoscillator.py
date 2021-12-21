from amaranth import *
from amaranth.build import Platform

class RingOscillator(Elaboratable):
    """
        DO NOT USE:
        currently not synthesizable, because it contains a combinational loop
    """
    def __init__(self, no_gates=11):
        assert(no_gates % 2 == 1, "number of gates must be odd, otherwise the ring oscillator will not oscillate")

        # parameters
        self.no_gates = no_gates

        # I/O
        self.enable_in        = Signal()
        self.gates_enable_in  = Signal(no_gates)

        self.oscillator_out   = Signal()

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        taps = Array(Signal(name=f"tap{n}") for n in range(self.no_gates + 1))

        m.d.comb += [
            taps[0].eq(taps[-1] & self.enable_in),
            self.oscillator_out.eq(taps[-1]),
        ]

        for n in range(self.no_gates):
            m.d.comb += taps[n + 1].eq(taps[n] ^ self.gates_enable_in[n])

        return m