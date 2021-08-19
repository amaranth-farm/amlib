#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0
#
"""Counter which runs a subcounter which divides the maincounter"""
from nmigen import Elaboratable, Signal, Module
from ..test import GatewareTestCase, sync_test_case

class DividingCounter(Elaboratable):
    """Counter which runs a subcounter which divides the maincounter"""
    def __init__(self, divisor, width):
        self.reset_in            = Signal()
        self.active_in           = Signal()
        self.counter_out         = Signal(width)
        self.divided_counter_out = Signal(width)
        self.dividable_out       = Signal()
        self.divisor = divisor
        self.width = width

        self.ports = [self.reset_in, self.active_in,
                      self.counter_out, self.divided_counter_out, self.dividable_out]

    def elaborate(self, platform) -> Module:
        """build the module"""
        m = Module()

        dividing_cycle_counter = Signal(range(0, self.divisor))

        with m.If(self.reset_in):
            m.d.sync += [
                self.counter_out.eq(0),
                self.divided_counter_out.eq(0),
                dividing_cycle_counter.eq(0)
            ]
        with m.Else():
            with m.If(self.active_in):
                with m.If(dividing_cycle_counter == self.divisor - 1):
                    m.d.sync += [
                        dividing_cycle_counter.eq(0),
                        self.divided_counter_out.eq(self.divided_counter_out + 1),
                        self.dividable_out.eq(1)
                    ]

                with m.Else():
                    m.d.sync += [
                        self.dividable_out.eq(0),
                        dividing_cycle_counter.eq(dividing_cycle_counter + 1)
                    ]

                # when the main counter wraps around to zero, the dividing counter needs reset too
                with m.If(self.counter_out == (2 ** self.counter_out.width) - 1):
                    m.d.sync += dividing_cycle_counter.eq(0)

                m.d.sync += [
                    self.counter_out.eq(self.counter_out + 1),
                ]

        return m


class DividingCounterTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = DividingCounter
    FRAGMENT_ARGUMENTS = {'divisor': 5, 'width': 5}

    @sync_test_case
    def test_basic(self):
        dut = self.dut
        yield dut.active_in.eq(0)
        for _ in range(0, 5):
            yield
            self.assertEqual((yield dut.counter_out), 0)

        count = 0
        divided_count = 1
        yield dut.active_in.eq(1)
        for _ in range(0, 50):
            yield
            self.assertEqual((yield dut.counter_out), count % 32)

            dividable = yield dut.dividable_out
            if dividable:
                self.assertEqual(((count % 32) % 5), 0)
                self.assertEqual((yield dut.divided_counter_out), divided_count)
                divided_count += 1

            count += 1

        yield dut.reset_in.eq(1)
        yield
        yield
        self.assertEqual((yield dut.counter_out), 0)
        yield
        yield
        yield
        yield
        yield
        yield dut.reset_in.eq(0)

        count = 0
        for _ in range(0, 20):
            yield
            self.assertEqual((yield dut.counter_out), count % 32)
            count += 1

        yield dut.active_in.eq(0)
        yield
        yield
        yield
        return
