# Copyright (C) 2021 Hans Baier hansfbaier@gmail.com
#
# SPDX-License-Identifier: Apache-2.0
#
from enum import IntEnum

from amaranth import *
from amaranth.build import Platform

from ..test   import GatewareTestCase, sync_test_case

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
        self.dots_in           = Signal(width // 4)
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
                self.seven_segment_out[(i * 8):(i * 8 + 7)].eq(digit_to_hex.seven_segment_out),
                self.seven_segment_out[(i * 8) + 7].eq(self.dots_in[i])
            ]

        return m

class NumberToBitBar(Elaboratable):
    """
    This converts the range of an unsigned integer into bits representing a bar of
    a bar chart:
    * we map the minimal value and everything below to an empty bar
    * and only the maxvalue to a full bar
    * all values in between should be divided up linearly between one bit and  all
      least significant bits until (all output bits - 1) set
    """
    def __init__(self, minvalue_in, maxvalue_in, bitwidth_out, debug=False) -> None:
        # parameters
        self._debug = debug
        self.minvalue = minvalue_in
        self.maxvalue = maxvalue_in
        self.bitbar   = [Const(int(2**n - 1), bitwidth_out) for n in range(bitwidth_out + 1)]

        # I/O
        self.value_in   = Signal(range(maxvalue_in))
        self.bitbar_out = Signal(bitwidth_out)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        debug = self._debug

        bar_value = Signal(range(self.maxvalue - self.minvalue))

        with m.If(self.value_in >= self.maxvalue):
            m.d.sync += self.bitbar_out.eq(self.bitbar[-1])

        with m.Elif(self.value_in <= self.minvalue):
            m.d.sync += self.bitbar_out.eq(self.bitbar[0])

        with m.Else():
            m.d.comb += bar_value.eq(self.value_in - self.minvalue)

            bar_bits = self.bitbar[1:-1]
            if debug: print("barbits: " + str([bin(b.value) for b in bar_bits]))

            range_max_values = [(self.maxvalue - self.minvalue) // (len(bar_bits) - 1) * i for i in range(1, len(bar_bits))]
            rng_vals = [int(val) for val in range_max_values]
            if debug: print("ranges:  " + str(rng_vals))

            rng_vals_deltas = list(map(lambda x: x[0] - x[1], zip(rng_vals + [self.maxvalue], [0] + rng_vals)))
            if debug: print("deltas:  " + str(rng_vals_deltas))

            with m.If(bar_value < range_max_values[0]):
                m.d.sync += self.bitbar_out.eq(bar_bits[0])

            range_to_value = zip(range_max_values[1:], bar_bits[1:-1])

            for (range_max, bitbar) in list(range_to_value):
                if debug: print(f"range: {str(range_max)}, value: {bitbar}")
                with m.Elif(bar_value < range_max):
                    m.d.sync += self.bitbar_out.eq(bitbar)

            with m.Else():
                m.d.sync += self.bitbar_out.eq(bar_bits[-1])

        return m

class NumberToBitBarTest(GatewareTestCase):
    MIN = 0x10
    MAX = 0x82
    FRAGMENT_UNDER_TEST = NumberToBitBar
    FRAGMENT_ARGUMENTS = dict(minvalue_in=MIN, maxvalue_in=MAX, bitwidth_out=8, debug=False)

    @sync_test_case
    def test_byte_range(self):
        dut = self.dut
        yield

        step = (self.MAX - self.MIN) // (dut.bitbar_out.width - 2)
        if dut._debug: print("step: " + str(step))

        for i in range(self.MAX + 10):
            yield dut.value_in.eq(i)
            yield
            yield
            if True:
                if i <= self.MIN:
                    self.assertEqual((yield dut.bitbar_out), 0)
                elif i < (self.MIN + step):
                    self.assertEqual((yield dut.bitbar_out), 0b1)
                elif i < (self.MIN + 2*step):
                    self.assertEqual((yield dut.bitbar_out), 0b11)
                elif i < (self.MIN + 3*step):
                    self.assertEqual((yield dut.bitbar_out), 0b111)
                elif i < (self.MIN + 4*step):
                    self.assertEqual((yield dut.bitbar_out), 0b1111)
                elif i < (self.MIN + 5*step):
                    self.assertEqual((yield dut.bitbar_out), 0b11111)
                elif i < (self.MIN + 6*step):
                    self.assertEqual((yield dut.bitbar_out), 0b111111)
                elif i < self.MAX:
                    self.assertEqual((yield dut.bitbar_out), 0b1111111)
                elif i >= self.MAX:
                    self.assertEqual((yield dut.bitbar_out), 0b11111111)

        yield
        yield