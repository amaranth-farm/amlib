#
# This file has been partly adapted from the glasgow project
#
# Copyright (C) 2018 whitequark@whitequark.org
#
# SPDX-License-Identifier: Apache-2.0

import functools

from amaranth import Elaboratable
from amaranth.sim import Simulator
from amaranth.compat import Module as CompatModule, run_simulation as compat_run_simulation

from .utils import GatewareTestCase, sync_test_case

__all__ = ["GatewareTestCase", "sync_test_case", "simulation_test"]

def simulation_test(case=None, **kwargs):
    def configure_wrapper(case):
        @functools.wraps(case)
        def wrapper(self):
            if hasattr(self, "configure"):
                self.configure(self.tb, **kwargs)
            def setup_wrapper():
                if hasattr(self, "simulationSetUp"):
                    yield from self.simulationSetUp(self.tb)
                yield from case(self, self.tb)
            if isinstance(self.tb, CompatModule):
                compat_run_simulation(self.tb, setup_wrapper(), vcd_name="test.vcd")
            if isinstance(self.tb, Elaboratable):
                sim = Simulator(self.tb)
                with sim.write_vcd(vcd_file=open("test.vcd", "w")):
                    sim.add_clock(1e-8)
                    sim.add_sync_process(setup_wrapper)
                    sim.run()
        return wrapper

    if case is None:
        return configure_wrapper
    else:
        return configure_wrapper(case)
