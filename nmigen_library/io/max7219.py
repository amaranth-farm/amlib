from enum import IntEnum

from nmigen import *
from nmigen.build import Platform
from nmigen.compat.fhdl.structure import Repl

from .spi     import SPIControllerBus, SPIControllerInterface
from ..test   import GatewareTestCase, sync_test_case
from ..utils  import Timer

seven_segment_font = [
  ['A', 0b1110111], ['B', 0b1111111], ['C', 0b1001110], ['D', 0b1111110], ['E', 0b1001111], ['F',  0b1000111],
  ['G', 0b1011110], ['H', 0b0110111], ['I', 0b0110000], ['J', 0b0111100], ['L', 0b0001110], ['N',  0b1110110],
  ['O', 0b1111110], ['P', 0b1100111], ['R', 0b0000101], ['S', 0b1011011], ['T', 0b0001111], ['U',  0b0111110],
  ['Y', 0b0100111], ['[', 0b1001110], [']', 0b1111000], ['_', 0b0001000], ['a', 0b1110111], ['b',  0b0011111],
  ['c', 0b0001101], ['d', 0b0111101], ['e', 0b1001111], ['f', 0b1000111], ['g', 0b1011110], ['h',  0b0010111],
  ['i', 0b0010000], ['j', 0b0111100], ['l', 0b0001110], ['n', 0b0010101], ['o', 0b1111110], ['p',  0b1100111],
  ['r', 0b0000101], ['s', 0b1011011], ['t', 0b0001111], ['u', 0b0011100], ['y', 0b0100111], ['-',  0b0000001],
  [' ', 0b0000000], ['0', 0b1111110], ['1', 0b0110000], ['2', 0b1101101], ['3', 0b1111001], ['4',  0b0110011],
  ['5', 0b1011011], ['6', 0b1011111], ['7', 0b1110000], ['8', 0b1111111], ['9', 0b1111011], ['/0', 0b0000000],
]

seven_segment_hex_numbers = [
  ['0', 0b1111110], ['1', 0b0110000], ['2', 0b1101101], ['3', 0b1111001], ['4', 0b0110011],
  ['5', 0b1011011], ['6', 0b1011111], ['7', 0b1110000], ['8', 0b1111111], ['9', 0b1111011],
  ['A', 0b1110111], ['b', 0b0011111], ['C', 0b1001110], ['D', 0b1111110], ['E', 0b1001111], ['F', 0b1000111],
]

class MAX7219Register(IntEnum):
    DECODE         = 0x09
    INTENSITY      = 0x0a
    SCAN_LIMIT     = 0x0b
    SHUTDOWN       = 0x0c
    DISPLAY_TEST   = 0x0f

default_init_sequence = [
    [MAX7219Register.DISPLAY_TEST,   0],
    [MAX7219Register.DECODE,         0],
    [MAX7219Register.INTENSITY,    0xf],
    [MAX7219Register.SCAN_LIMIT,     7],
    [MAX7219Register.SHUTDOWN,       1],
]

class SerialLEDArray(Elaboratable):
    def __init__(self, *, divisor, init_delay=16e6, init_sequence=default_init_sequence, no_modules=1):
        # parameters
        assert divisor % 2 == 0, "divisor must be even"
        self.divisor       = divisor
        self.no_modules    = no_modules
        self.init_delay    = init_delay
        self.init_sequence = init_sequence

        # I/O
        self.spi_bus_out  = SPIControllerBus()
        self.digits_in    = Array(Signal(8, name=f"digit{n}") for n in range(8 * no_modules))
        self.valid_in     = Signal()

    def send_command_to_all_modules(self, spi_controller, command_byte, data_byte):
        return spi_controller.word_out.eq(Repl(Cat(Const(data_byte, 8), Const(command_byte, 8)), self.no_modules))

    def connect_to_resource(self, spi_resource):
        return [
            spi_resource.copi .eq(self.spi_bus_out.sdo),
            spi_resource.clk  .eq(self.spi_bus_out.sck),
            spi_resource.cs   .eq(~self.spi_bus_out.cs),
        ]

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        current_digits = Array(Signal(8, name=f"current_digit{n}") for n in range(8 * self.no_modules))

        m.submodules.init_delay = init_delay = \
            Timer(width=24, load=int(self.init_delay), reload=0, allow_restart=False)

        m.submodules.spi_controller = spi_controller = SPIControllerInterface(word_size=16 * self.no_modules, divisor=self.divisor, cs_idles_high=True)

        with m.If(self.valid_in):
            m.d.sync += Cat(current_digits).eq(Cat(self.digits_in))

        m.d.comb += [
            spi_controller.spi.connect(self.spi_bus_out),
            init_delay.start.eq(1),
        ]

        digit_counter = Signal(8)
        next_digit    = Signal()

        with m.If(next_digit):
            m.d.sync += digit_counter.eq(digit_counter + 1)

        step_counter = Signal(range(10))
        next_step    = Signal()

        with m.If(next_step):
            m.d.sync += step_counter.eq(step_counter + 1)

        with m.FSM(name="max7219"):
            with m.State("WAIT"):
                with m.If(init_delay.done):
                    m.next = "INIT"

            with m.State("INIT"):
                with m.Switch(step_counter):
                    with m.Case(0):
                        item = self.init_sequence[0]
                        m.d.sync += self.send_command_to_all_modules(spi_controller, item[0], item[1]),
                        m.d.comb += next_step.eq(1)
                    with m.Case(1):
                        m.d.comb += [
                            spi_controller.start_transfer.eq(1),
                            next_step.eq(1)
                        ]

                    i = 1
                    for item in self.init_sequence[1:]:
                        with m.Case(2 * i):
                            with m.If(spi_controller.word_complete):
                                m.d.sync += self.send_command_to_all_modules(spi_controller, item[0], item[1]),
                                m.d.comb += next_step.eq(1)
                        with m.Case(2 * i + 1):
                            m.d.comb += [
                                spi_controller.start_transfer.eq(1),
                                next_step.eq(1)
                            ]
                        i += 1

                    with m.Case(2 * i):
                        with m.If(spi_controller.word_complete):
                            m.d.comb += next_step.eq(1)

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
    FRAGMENT_ARGUMENTS = dict(divisor=10, init_delay=20, no_modules=2)

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


class NibbleToSevenSegmentHex(Elaboratable):
    def __init__(self):
        self.nibble_in         = Signal(4)
        self.seven_segment_out = Signal(8)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        with m.Switch(self.nibble_in):
            for digit in seven_segment_hex_numbers:
                with m.Case(int(f"0x{digit[0]}", 0)):
                    m.d.comb += self.seven_segment_out.eq(digit[1])

        return m

class NumberToSevenSegmentHex(Elaboratable):
    def __init__(self, width=32, register = False):
        # parameters
        assert width % 4 == 0, "width must be a multiple of four"
        self.width    = width
        self.register = register

        # I/O
        self.number_in         = Signal(width)
        self.seven_segment_out = Signal(width * 2)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        no_nibbles = self.width // 4

        for i in range(no_nibbles):
            digit_to_hex = NibbleToSevenSegmentHex()
            m.submodules += digit_to_hex
            domain = m.d.sync if self.register else m.d.comb
            domain += [
                digit_to_hex.nibble_in.eq(self.number_in[(i * 4):(i * 4 + 4)]),
                self.seven_segment_out[(i * 8):(i * 8 + 8)].eq(digit_to_hex.seven_segment_out),
            ]

        return m