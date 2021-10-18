from enum import IntEnum
from sys import modules

from nmigen import *
from nmigen.build import Platform
from nmigen.compat.fhdl.structure import Repl

from .spi     import SPIControllerBus, SPIControllerInterface
from ..test   import GatewareTestCase, sync_test_case

seven_segment_hex = [
    0b1111110, # 0
    0b0110000, # 1
    0b1101101, # 2
    0b1111001, # 3
    0b0110011, # 4
    0b1011011, # 5
    0b1011111, # 6
    0b1110000, # 7
    0b1111111, # 8
    0b1110011, # 9
    0b1110111, # A
    0b0011111, # b
    0b1001110, # C
    0b0111101, # d
    0b1001111, # E
    0b1000111, # F
]

class Register(IntEnum):
    DECODE         = 0x09
    INTENSITY      = 0x0a
    SCAN_LIMIT     = 0x0b
    SHUTDOWN       = 0x0c
    DISPLAY_TEST   = 0x0f

class SerialLEDArray(Elaboratable):
    def __init__(self, *, divisor, no_modules=1):
        # parameters
        assert divisor % 2 == 0, "divisor must be even"
        self.divisor       = divisor
        self.no_modules    = no_modules

        # I/O
        self.spi_bus_out  = SPIControllerBus()
        self.digits_in    = Array(Signal(8, name=f"digit{n}") for n in range(8 * no_modules))
        self.valid_in     = Signal()

    def send_command_to_all_modules(self, spi_controller, command_byte, data_byte):
        return spi_controller.word_out.eq(Repl(Cat(Const(command_byte, 8), Const(data_byte, 8)), self.no_modules))

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        current_digits = Array(Signal(8, name=f"current_digit{n}") for n in range(8 * self.no_modules))

        m.submodules.spi_controller = spi_controller = SPIControllerInterface(word_size=16 * self.no_modules, divisor=self.divisor, cs_idles_high=True)

        with m.If(self.valid_in):
            m.d.sync += Cat(current_digits).eq(Cat(self.digits_in))

        m.d.comb += spi_controller.spi.connect(self.spi_bus_out)

        digit_counter = Signal(8)
        next_digit    = Signal()

        with m.If(next_digit):
            m.d.sync += digit_counter.eq(digit_counter + 1)

        step_counter = Signal(range(10))
        next_step    = Signal()

        with m.If(next_step):
            m.d.sync += step_counter.eq(step_counter + 1)

        with m.FSM(name="max7219"):
            with m.State("INIT"):
                with m.Switch(step_counter):
                    with m.Case(0):
                        m.d.sync += self.send_command_to_all_modules(spi_controller, Register.SCAN_LIMIT, 7)
                        m.d.comb += next_step.eq(1)
                    with m.Case(1):
                        m.d.comb += [
                            spi_controller.start_transfer.eq(1),
                            next_step.eq(1)
                        ]

                    with m.Case(2):
                        with m.If(spi_controller.word_complete):
                            m.d.sync += self.send_command_to_all_modules(spi_controller, Register.DECODE, 0),
                            m.d.comb += next_step.eq(1)
                    with m.Case(3):
                        m.d.comb += [
                            spi_controller.start_transfer.eq(1),
                            next_step.eq(1)
                        ]

                    with m.Case(4):
                        with m.If(spi_controller.word_complete):
                            m.d.sync += self.send_command_to_all_modules(spi_controller, Register.SHUTDOWN, 1),
                            m.d.comb += next_step.eq(1)
                    with m.Case(5):
                        m.d.comb += [
                            spi_controller.start_transfer.eq(1),
                            next_step.eq(1)
                        ]

                    with m.Case(6):
                        with m.If(spi_controller.word_complete):
                            m.d.sync += self.send_command_to_all_modules(spi_controller, Register.DISPLAY_TEST, 0),
                            m.d.comb += next_step.eq(1)
                    with m.Case(7):
                        m.d.comb += [
                            spi_controller.start_transfer.eq(1),
                            next_step.eq(1)
                        ]

                    with m.Case(6):
                        with m.If(spi_controller.word_complete):
                            m.d.sync += self.send_command_to_all_modules(spi_controller, Register.INTENSITY, 0xf),
                            m.d.comb += next_step.eq(1)
                    with m.Case(7):
                        m.d.comb += [
                            spi_controller.start_transfer.eq(1),
                            next_step.eq(1)
                        ]
                    with m.Default():
                        m.d.sync += step_counter.eq(0)
                        m.next = "SHOWTIME"

            with m.State('SHOWTIME'):
                with m.Switch(step_counter):
                    with m.Case(0):
                        for module in range(self.no_modules):
                            m.d.sync += [
                                spi_controller.word_out[(0 + module * 16):(8  + module * 16)].eq(current_digits[Const(module * 8, 8) + digit_counter]),
                                spi_controller.word_out[(8 + module * 16):(16 + module * 16)].eq((digit_counter + 1)[0:8]),
                            ]
                            m.d.comb += [
                                next_step.eq(1),
                            ]

                    with m.Case(1):
                        m.d.comb += [
                            spi_controller.start_transfer.eq(1),
                            next_step.eq(1)
                        ]

                    with m.Default():
                        with m.If(spi_controller.word_complete):
                            m.d.sync += step_counter.eq(0)
                            with m.If(digit_counter >= 7):
                                m.d.sync += digit_counter.eq(0)
                            with m.Else():
                                m.d.comb += next_digit.eq(1)

        return m


class SerialLEDArrayTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = SerialLEDArray
    FRAGMENT_ARGUMENTS = dict(divisor=10, no_modules=2)

    def loopback(self, no_cycles):
        for _ in range(no_cycles):
            yield self.dut.spi_bus_out.sdi.eq((yield self.dut.spi_bus_out.sdo))
            yield

    @sync_test_case
    def test_spi_interface(self):
        dut = self.dut
        yield
        yield
        yield from self.loopback(900)
        yield
        yield
        for d in range(16):
            yield dut.digits_in[d].eq(d)
        yield
        yield
        yield from self.pulse(dut.valid_in)
        yield from self.loopback(7200)


"""
TODO: decode seven segment
            if self.seven_segment != None:
                for module in range(self.no_modules):
                    with m.Switch(self.digits_in):
                        for digit in range(8):
                            index = module * 8 + digit
                            with m.Case(digit):
                                m.d.sync += current_digits[index].eq(self.digits_in[index])

"""