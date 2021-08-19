#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0
#
"""
    synchronous shift register: bits appear in the output at the next
                                clock cycle
"""
from nmigen import Elaboratable, Signal, Module, Cat
from ..test     import GatewareTestCase, sync_test_case

# pylint: disable=too-few-public-methods
class InputShiftRegister(Elaboratable):
    """shift register with given depth in bits"""
    def __init__(self, depth):
        self.enable_in = Signal()
        self.bit_in    = Signal()
        self.clear_in  = Signal()
        self.value_out = Signal(depth)

    def elaborate(self, platform) -> Module:
        """build the module"""
        m = Module()

        with m.If(self.clear_in):
            m.d.sync += self.value_out.eq(0)
        with m.Elif(self.enable_in):
            m.d.sync += self.value_out.eq((self.value_out << 1) | self.bit_in)

        return m

# pylint: disable=too-few-public-methods
class OutputShiftRegister(Elaboratable):
    """shift register with given depth in bits"""
    def __init__(self, depth, rotate=False):
        self.enable_in = Signal()
        self.we_in     = Signal()
        self.bit_out   = Signal()
        self.value_in  = Signal(depth)
        self.rotate    = rotate

    def elaborate(self, platform) -> Module:
        """build the module"""
        m = Module()

        value = Signal.like(self.value_in)
        m.d.comb += self.bit_out.eq(value[0])

        with m.If(self.we_in):
            m.d.sync += value.eq(self.value_in)
        with m.Elif(self.enable_in):
            m.d.sync += value.eq(Cat(value[1:], value[0])) if self.rotate else value.eq((value >> 1))

        return m

class InputShiftRegisterTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = InputShiftRegister
    FRAGMENT_ARGUMENTS = {'depth': 8}

    @sync_test_case
    def test_basic(self):
        dut = self.dut
        yield dut.enable_in.eq(0)
        yield
        self.assertEqual((yield dut.value_out), 0)
        yield dut.bit_in.eq(1)
        yield
        self.assertEqual((yield dut.value_out), 0)
        yield dut.bit_in.eq(0)
        yield
        self.assertEqual((yield dut.value_out), 0)
        yield dut.bit_in.eq(1)
        yield
        self.assertEqual((yield dut.value_out), 0)
        yield dut.bit_in.eq(1)
        yield
        yield dut.bit_in.eq(0)
        yield
        self.assertEqual((yield dut.value_out), 0)
        yield dut.bit_in.eq(1)
        yield dut.enable_in.eq(1)
        yield
        yield dut.enable_in.eq(0)
        yield
        self.assertEqual((yield dut.value_out), 1)
        yield dut.enable_in.eq(1)
        yield
        self.assertEqual((yield dut.value_out), 0b1)
        yield dut.bit_in.eq(0)
        yield
        self.assertEqual((yield dut.value_out), 0b11)
        yield dut.bit_in.eq(1)
        yield
        self.assertEqual((yield dut.value_out), 0b110)
        yield dut.bit_in.eq(1)
        yield
        self.assertEqual((yield dut.value_out), 0b1101)
        yield dut.bit_in.eq(0)
        yield
        self.assertEqual((yield dut.value_out), 0b11011)
        yield dut.bit_in.eq(1)
        yield
        self.assertEqual((yield dut.value_out), 0b110110)
        yield dut.enable_in.eq(0)
        yield
        self.assertEqual((yield dut.value_out), 0b110110)
        yield
        self.assertEqual((yield dut.value_out), 0b110110)
        yield
        self.assertEqual((yield dut.value_out), 0b110110)
        yield dut.enable_in.eq(1)
        for _ in range(13):
            yield dut.bit_in.eq(1)
            yield
            yield dut.bit_in.eq(0)
            yield
            yield dut.bit_in.eq(1)
            yield
            yield dut.bit_in.eq(0)
            yield

class OutputShiftRegisterTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = OutputShiftRegister
    FRAGMENT_ARGUMENTS = {'depth': 8, 'rotate': True}

    # Function to right
    # rotate n by d bits
    @staticmethod
    def rightRotate(n, d):
        # In n>>d, first d bits are 0.
        # To put last 3 bits of at
        # first, do bitwise or of n>>d
        # with n <<(8 - d)
        return (n >> d)|(n << (8 - d)) & 0xFF

    @sync_test_case
    def test_basic(self):
        dut = self.dut
        yield dut.enable_in.eq(0)
        value = 0xaa
        yield dut.value_in.eq(value)
        yield dut.we_in.eq(1)
        yield
        self.assertEqual((yield dut.bit_out), 0)

        yield dut.we_in.eq(0)
        yield
        self.assertEqual((yield dut.bit_out), 0)

        yield
        self.assertEqual((yield dut.bit_out), 0)

        yield dut.enable_in.eq(1)
        yield
        self.assertEqual((yield dut.bit_out), value & 0x1)
        value = self.rightRotate(value, 1)

        yield
        self.assertEqual((yield dut.bit_out), value & 0x1)
        value = self.rightRotate(value, 1)

        yield
        self.assertEqual((yield dut.bit_out), value & 0x1)
        value = self.rightRotate(value, 1)

        yield
        self.assertEqual((yield dut.bit_out), value & 0x1)
        value = self.rightRotate(value, 1)

        yield
        self.assertEqual((yield dut.bit_out), value & 0x1)
        value = self.rightRotate(value, 1)

        yield dut.enable_in.eq(0)
        yield
        yield
        yield
        yield dut.enable_in.eq(1)
        yield
        yield
        yield dut.value_in.eq(0x55)
        yield dut.we_in.eq(1)
        yield
        yield dut.we_in.eq(0)
        yield
        yield
        yield

        yield dut.we_in.eq(1)
        value = 0b10000000
        yield dut.value_in.eq(value)
        yield

        yield dut.we_in.eq(0)

        for _ in range(13):
            yield
            self.assertEqual((yield dut.bit_out), value & 0x1)
            value = self.rightRotate(value, 1)

        yield dut.we_in.eq(1)
        yield dut.value_in.eq(0)
        yield
        yield dut.we_in.eq(0)
        self.assertEqual((yield dut.bit_out), 0)

        yield
        self.assertEqual((yield dut.bit_out), 0)

        yield
        self.assertEqual((yield dut.bit_out), 0)

        yield
        self.assertEqual((yield dut.bit_out), 0)
