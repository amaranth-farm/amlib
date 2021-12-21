#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0
#
"""converts a rising edge to a single clock pulse"""
from amaranth     import Elaboratable, Signal, Module
from ..test     import GatewareTestCase, sync_test_case

class EdgeToPulse(Elaboratable):
    """
        each rising edge of the signal edge_in will be
        converted to a single clock pulse on pulse_out
    """
    def __init__(self):
        self.edge_in          = Signal()
        self.pulse_out        = Signal()

    def elaborate(self, platform) -> Module:
        m = Module()

        edge_last = Signal()

        m.d.sync += edge_last.eq(self.edge_in)
        with m.If(self.edge_in & ~edge_last):
            m.d.comb += self.pulse_out.eq(1)
        with m.Else():
            m.d.comb += self.pulse_out.eq(0)

        return m


class EdgeToPulseTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = EdgeToPulse
    FRAGMENT_ARGUMENTS = {}

    @sync_test_case
    def test_basic(self):
        dut = self.dut
        yield dut.edge_in.eq(0)
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield
        yield
        yield dut.edge_in.eq(1)
        yield
        self.assertEqual((yield dut.pulse_out), 1)
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield
        yield
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield dut.edge_in.eq(0)
        yield
        yield
        yield
        yield
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield dut.edge_in.eq(1)
        yield
        self.assertEqual((yield dut.pulse_out), 1)
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield dut.edge_in.eq(0)
        yield
        yield
        yield
        yield
        yield dut.edge_in.eq(1)
        yield
        self.assertEqual((yield dut.pulse_out), 1)
        yield dut.edge_in.eq(0)
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield dut.edge_in.eq(1)
        yield
        self.assertEqual((yield dut.pulse_out), 1)
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield
        yield dut.edge_in.eq(1)
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield dut.edge_in.eq(0)
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield
        yield dut.edge_in.eq(1)
        yield
        self.assertEqual((yield dut.pulse_out), 1)
        yield dut.edge_in.eq(0)
        yield
        self.assertEqual((yield dut.pulse_out), 0)
        yield
        yield
