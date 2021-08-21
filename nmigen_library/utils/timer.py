from nmigen       import *
from nmigen.build import Platform
from ..test       import GatewareTestCase, sync_test_case

class Timer(Elaboratable):
    def __init__(self, *, width=32, load=None, reload=None, allow_restart=True):
        self._width = width
        self._allow_restart = allow_restart
        self.load_in     = Signal(width, name="load")   if load   == None else load
        self.reload_in   = Signal(width, name="reload") if reload == None else reload
        self.counter_out = Signal(width)
        self.start       = Signal()
        self.done        = Signal()

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        counter = self.counter_out

        with m.FSM() as fsm:
            m.d.comb += self.done.eq(fsm.ongoing("DONE"))

            with m.State("IDLE"):
                # if load is nonzero, it takes precedence
                with m.If(self.load_in > 0):
                    m.d.sync += counter.eq(self.load_in)
                with m.Else():
                    m.d.sync += counter.eq(self.reload_in)

                with m.If(self.start & (counter > 0)):
                    # done should appear exactly 'load' cycles
                    # load is one-based, but we stop at zero
                    m.d.sync += counter.eq(counter - 1)
                    m.next = "RUNNING"

            with m.State("RUNNING"):
                m.d.sync += counter.eq(counter - 1)
                with m.If(counter == 1):
                    m.next = "DONE"

            with m.State("DONE"):
                with m.If(self.reload_in > 0):
                    # we want the next done to appear
                    # exactly 'reload_in' cycles later
                    m.d.sync += counter.eq(self.reload_in - 1)
                    m.next = "RUNNING"
                if self._allow_restart:
                    with m.Else():
                        m.next = "IDLE"

        return m

class TimerTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = Timer
    FRAGMENT_ARGUMENTS = {'width': 32}

    @sync_test_case
    def test_oneshot(self):
        dut = self.dut
        yield

        # load initial value
        yield dut.load_in.eq(10)
        yield
        yield from self.shouldBeLow(dut.done)
        yield from self.shouldBeZero(dut.counter_out)

        # start timer
        yield dut.load_in.eq(0)
        yield from self.pulse(dut.start, step_after=True)
        self.assertEqual((yield dut.counter_out), 9)
        yield from self.shouldBeLow(dut.done)

        yield from self.advance_cycles(8)
        self.assertEqual((yield dut.counter_out), 1)
        yield from self.shouldBeLow(dut.done)

        # counter is zero, transition to DONE
        yield
        yield from self.shouldBeHigh(dut.done)
        yield from self.shouldBeZero(dut.counter_out)

        for _ in range(5):
            yield
            yield from self.shouldBeLow(dut.done)
            yield from self.shouldBeZero(dut.counter_out)

        yield from self.shouldBeZero(dut.counter_out)

    @sync_test_case
    def test_periodic(self):
        dut = self.dut
        yield

        # load initial value
        yield dut.reload_in.eq(3)
        yield
        yield from self.shouldBeLow(dut.done)
        yield from self.shouldBeZero(dut.counter_out)

        yield
        yield

        # start timer
        yield dut.load_in.eq(0)
        yield from self.pulse(dut.start, step_after=True)
        self.assertEqual((yield dut.counter_out), 2)
        yield from self.shouldBeLow(dut.done)

        yield from self.advance_cycles(1)
        self.assertEquals((yield dut.counter_out), 1)
        yield from self.shouldBeLow(dut.done)

        # counter is zero, transition to DONE
        yield
        yield from self.shouldBeHigh(dut.done)
        yield from self.shouldBeZero(dut.counter_out)

        for _ in range(4):
            for _ in range(2):
                yield
                yield from self.shouldBeLow(dut.done)
                yield from self.shouldBeNonZero(dut.counter_out)

            yield
            yield from self.shouldBeZero(dut.counter_out)
            yield from self.shouldBeHigh(dut.done)

class TimerConstReloadTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = Timer
    FRAGMENT_ARGUMENTS = {'width': 32, 'load': 10, 'reload': 0}

    @sync_test_case
    def test_oneshot(self):
        dut = self.dut
        # load initial value
        yield
        yield from self.shouldBeLow(dut.done)
        self.assertEqual((yield dut.counter_out), 10)

        # start timer
        yield from self.pulse(dut.start, step_after=True)
        self.assertEqual((yield dut.counter_out), 9)
        yield from self.shouldBeLow(dut.done)

        yield from self.advance_cycles(8)
        self.assertEqual((yield dut.counter_out), 1)
        yield from self.shouldBeLow(dut.done)

        # counter is zero, transition to DONE
        yield
        yield from self.shouldBeHigh(dut.done)
        yield from self.shouldBeZero(dut.counter_out)

        yield
        yield from self.shouldBeZero(dut.counter_out)

        for _ in range(5):
            yield
            yield from self.shouldBeLow(dut.done)
            self.assertEqual((yield dut.counter_out), 10)

class TimerConstLoadTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = Timer
    FRAGMENT_ARGUMENTS = {'width': 32, 'load': 5}

    @sync_test_case
    def test_periodic(self):
        dut = self.dut
        yield
        # constant load is automatic
        self.assertEqual((yield dut.counter_out), 5)

        # load initial value
        yield dut.reload_in.eq(3)
        yield
        yield from self.shouldBeLow(dut.done)
        self.assertEqual((yield dut.counter_out), 5)
        yield
        yield

        # start timer
        yield from self.pulse(dut.start, step_after=True)
        self.assertEqual((yield dut.counter_out), 4)
        yield from self.shouldBeLow(dut.done)

        yield from self.advance_cycles(3)
        self.assertEquals((yield dut.counter_out), 1)
        yield from self.shouldBeLow(dut.done)

        # counter is zero, transition to DONE
        yield
        yield from self.shouldBeHigh(dut.done)
        yield from self.shouldBeZero(dut.counter_out)

        for _ in range(4):
            for _ in range(2):
                yield
                yield from self.shouldBeLow(dut.done)
                yield from self.shouldBeNonZero(dut.counter_out)

            yield
            yield from self.shouldBeZero(dut.counter_out)
            yield from self.shouldBeHigh(dut.done)