# inspired by the i2s core in the LiteX project
# original migen version by:
#   Copyright (c) 2020 bunnie <bunnie@kosagi.com>
#   Copyright (c) 2020 Antmicro <www.antmicro.com>
# nMigen version by:
#   Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import math
from enum import Enum

from nmigen import *
from nmigen.build    import Platform
from nmigen.lib.cdc  import FFSynchronizer
from nmigen.lib.fifo import SyncFIFO

from ..stream import StreamInterface, connect_stream_to_fifo, connect_fifo_to_stream
from ..utils  import rising_edge_detected, falling_edge_detected
from ..test   import GatewareTestCase, sync_test_case

class I2S_FORMAT(Enum):
    STANDARD       = 1
    LEFT_JUSTIFIED = 2

class I2STransmitter(Elaboratable):
    """ I2S Transmitter

        Attributes
        ----------
        enable_in: Signal(), input
            enable transmission
        stream_in: StreamInterface(), input
            Stream containing the audio samples to be sent
        word_select_in: Signal(), input
            I2S word select signal (word clock)
        serial_clock_in: Signal(), input
            I2S bit clock
        serial_data_out: Signal(), output
            transmitted I2S serial data
        underflow_out: Signal(), output
            is strobed, when the fifo was empty at the time to transmit a sample
        mismatch_out: Signal(), output
            is strobed, when the first flag set does not match the left channel
                        and when the first flag clear does not match the right channel
        fifo_level_out: Signal()
            reports the current FIFO fill level

        Parameters
        ----------
        sample_width: int
            the width of one audio sample in bits
        frame_format: I2S_FORMAT
            choice of standard and left justified I2S-variant
        fifo_depth: int
            depth of the transmit FIFO

        CODEC Interface
        ---------------

        The interface assumes we have a sysclk domain running around 100MHz, and that our typical
        audio rate is 44.1kHz * 24bits * 2channels = 2.1168MHz audio clock. Thus, the architecture
        treats the audio clock and data as asynchronous inputs that are MultiReg-syncd into the clock
        domain. Probably the slowest sysclk rate this might work with is around 20-25MHz (10x over
        sampling), but at 100MHz things will be quite comfortable.

        The upside of the fully asynchronous implementation is that we can leave the I/O unconstrained,
        giving the place/route more latitude to do its job.

        Here's the timing format targeted by this I2S interface:

            .. wavedrom::
                :caption: Timing format of the I2S interface

                { "signal" : [
                  { "name": "clk",         "wave": "n....|.......|......" },
                  { "name": "sync",        "wave": "1.0..|....1..|....0." },
                  { "name": "tx/rx",       "wave": ".====|==x.===|==x.=x", "data":
                  ["L15", "L14", "...", "L1", "L0", "R15", "R14", "...", "R1", "R0", "L15"] },
                ]}

        - Data is updated on the falling edge
        - Data is sampled on the rising edge
        - Words are MSB-to-LSB,
        - Sync is an input or output based on configure mode,
        - Sync can be longer than the wordlen, extra bits are just ignored
        - Tx is data to the codec (SDI pin on LM49352)
        - Rx is data from the codec (SDO pin on LM49352)
        """
    def __init__(self, *, sample_width: int, frame_format: I2S_FORMAT = I2S_FORMAT.STANDARD, fifo_depth=16):
        self._sample_width = sample_width
        self._frame_format = frame_format
        self._fifo_depth = fifo_depth

        self.enable_in        = Signal()
        self.stream_in        = StreamInterface(payload_width=sample_width)
        self.word_select_in   = Signal()
        self.serial_clock_in  = Signal()
        self.serial_data_out  = Signal()
        self.underflow_out    = Signal()
        self.mismatch_out     = Signal()
        self.fifo_level_out   = Signal(range(fifo_depth + 1))

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        sample_width = self._sample_width
        frame_format = self._frame_format

        fifo_data_width = sample_width
        concatenate_channels = True
        if concatenate_channels:
            if sample_width <= 16:
                fifo_data_width = sample_width * 2
            else:
                concatenate_channels = False
                print("I2S warning: sample width greater than 16 bits. your channels can't be glued")

        tx_buf_width = fifo_data_width + 1 if frame_format == I2S_FORMAT.STANDARD else fifo_data_width
        sample_width = sample_width + 1    if frame_format == I2S_FORMAT.STANDARD else sample_width
        offset       = [0]                 if frame_format == I2S_FORMAT.STANDARD else []

        tx_cnt_width = math.ceil(math.log(fifo_data_width,2))
        tx_cnt = Signal(tx_cnt_width)
        tx_shifter = Signal(tx_buf_width - 1)
        sample_msb = fifo_data_width - 1

        bit_clock  = Signal()
        word_clock = Signal()
        m.submodules.bit_clock_synchronizer  = FFSynchronizer(self.serial_clock_in, bit_clock)
        m.submodules.word_clock_synchronizer = FFSynchronizer(self.word_select_in, word_clock)

        bit_clock_rose  = Signal()
        bit_clock_fell  = Signal()
        m.d.comb += [
            bit_clock_rose .eq(rising_edge_detected(m, bit_clock)),
            bit_clock_fell.eq(falling_edge_detected(m, bit_clock)),
        ]

        left_channel  = Signal()
        right_channel = Signal()
        m.d.comb += [
            left_channel.eq(~word_clock if frame_format == I2S_FORMAT.STANDARD else word_clock),
            right_channel.eq(~left_channel)
        ]

        m.submodules.tx_fifo = tx_fifo = SyncFIFO(width=fifo_data_width + 1, depth=self._fifo_depth)

        # first marks left channel
        first_flag = Signal()
        m.d.comb += [
            connect_stream_to_fifo(self.stream_in, tx_fifo),
            tx_fifo.w_data[-1].eq(self.stream_in.first),
            first_flag.eq(tx_fifo.r_data[-1]),
            tx_fifo.r_en.eq(0),
            self.fifo_level_out.eq(tx_fifo.level),
            self.underflow_out.eq(0),
            self.mismatch_out.eq(0),
        ]

        with m.FSM(reset="IDLE"):
            with m.State("IDLE"):
                with m.If(self.enable_in):
                    with m.If(bit_clock_rose & left_channel):
                        m.next = "WAIT_SYNC"

            with m.State("WAIT_SYNC"):
                with m.If(bit_clock_rose & left_channel):
                    m.next = "LEFT_FALL"
                    m.d.sync += [
                        tx_cnt.eq(sample_width),
                        tx_shifter.eq(Cat(tx_fifo.r_data, offset))
                    ]
                    m.d.comb += tx_fifo.r_en.eq(1),

            # sync should be sampled on rising edge, but data should change on falling edge
            with m.State("LEFT_FALL"):
                with m.If(bit_clock_fell):
                    m.next = "LEFT"

            with m.State("LEFT"):
                with m.If(~self.enable_in):
                    m.next = "IDLE"
                with m.Else():
                    m.d.sync += [
                        self.serial_data_out.eq(tx_shifter[sample_msb]),
                        tx_shifter.eq(Cat(0, tx_shifter[:-1])),
                        tx_cnt.eq(tx_cnt - 1)
                    ]
                    m.next = "LEFT_WAIT"

            if concatenate_channels:
                with m.State("LEFT_WAIT"):
                    with m.If(~self.enable_in):
                        m.next = "IDLE"
                    with m.Else():
                        with m.If(bit_clock_rose):
                            with m.If((tx_cnt == 0)):
                                with m.If(right_channel):
                                    m.d.sync += tx_cnt.eq(sample_width)
                                    m.next = "RIGHT"
                                with m.Else():
                                    m.next = "LEFT_WAIT"
                            with m.Elif(tx_cnt > 0):
                                m.next = "LEFT_FALL"
            else:
                with m.State("LEFT_WAIT"):
                    with m.If(~self.enable_in):
                        m.next = "IDLE"
                    with m.Else():
                        with m.If(bit_clock_rose):
                            with m.If((tx_cnt == 0)):
                                with m.If(right_channel):
                                    m.d.sync += tx_cnt.eq(sample_width),
                                    with m.If(tx_fifo.r_rdy):
                                        # in LEFT_WAIT state, we wait for the
                                        # right channel to start
                                        with m.If(~first_flag):
                                            m.d.sync += tx_shifter.eq(Cat(tx_fifo.r_data, offset))
                                            m.d.comb += tx_fifo.r_en.eq(1)
                                        with m.Else():
                                            m.d.comb += self.mismatch_out.eq(1)
                                    with m.Else():
                                        m.d.comb += self.underflow_out.eq(1)

                                    m.next = "RIGHT_FALL"
                                with m.Else():
                                    m.next = "LEFT_WAIT"
                            with m.Elif(tx_cnt > 0):
                                m.next = "LEFT_FALL"

            # sync should be sampled on rising edge, but data should change on falling edge
            with m.State("RIGHT_FALL"):
                with m.If(bit_clock_fell):
                    m.next = "RIGHT"

            with m.State("RIGHT"):
                with m.If(~self.enable_in):
                    m.next = "IDLE"
                with m.Else():
                    m.d.sync += [
                        self.serial_data_out.eq(tx_shifter[sample_msb]),
                        tx_shifter.eq(Cat(0, tx_shifter[:-1])),
                        tx_cnt.eq(tx_cnt - 1)
                    ]
                    m.next = "RIGHT_WAIT"

            with m.State("RIGHT_WAIT"):
                with m.If(~self.enable_in):
                    m.next = "IDLE"
                with m.Else():
                    with m.If(bit_clock_rose):
                        with m.If((tx_cnt == 0) & left_channel):
                            m.d.sync += tx_cnt.eq(sample_width)
                            with m.If(tx_fifo.r_rdy):
                                # in RIGHT_WAIT, we wait for the left channel to start
                                with m.If(first_flag):
                                    m.d.sync += tx_shifter.eq(Cat(tx_fifo.r_data, offset))
                                    m.d.comb += tx_fifo.r_en.eq(1)
                                with m.Else():
                                    m.d.comb += self.mismatch_out.eq(1)
                            with m.Else():
                                m.d.comb += self.underflow_out.eq(1)
                            m.next = "LEFT_FALL"
                        with m.Elif(tx_cnt > 0):
                            m.next = "RIGHT_FALL"

        return m

class I2SReceiver(Elaboratable):
    """ I2S Receiver

        Attributes
        ----------
        enable_in: Signal(), input
            enable reception
        stream_out: StreamInterface(), input
            Stream containing the audio samples received
        word_select_in: Signal(), input
            I2S word select signal (word clock)
        serial_clock_in: Signal(), input
            I2S bit clock
        serial_data_in: Signal(), input
            transmitted I2S serial data
        fifo_level_out: Signal()
            reports the current FIFO fill level

        Parameters
        ----------
        sample_width: int
            the width of one audio sample in bits
        frame_format: I2S_FORMAT
            choice of standard and left justified I2S-variant
        fifo_depth: int
            depth of the receive FIFO

        CODEC Interface
        ---------------

        The interface assumes we have a sysclk domain running around 100MHz, and that our typical
        audio rate is 44.1kHz * 24bits * 2channels = 2.1168MHz audio clock. Thus, the architecture
        treats the audio clock and data as asynchronous inputs that are MultiReg-syncd into the clock
        domain. Probably the slowest sysclk rate this might work with is around 20-25MHz (10x over
        sampling), but at 100MHz things will be quite comfortable.

        The upside of the fully asynchronous implementation is that we can leave the I/O unconstrained,
        giving the place/route more latitude to do its job.

        Here's the timing format targeted by this I2S interface:

            .. wavedrom::
                :caption: Timing format of the I2S interface

                { "signal" : [
                  { "name": "clk",         "wave": "n....|.......|......" },
                  { "name": "sync",        "wave": "1.0..|....1..|....0." },
                  { "name": "tx/rx",       "wave": ".====|==x.===|==x.=x", "data":
                  ["L15", "L14", "...", "L1", "L0", "R15", "R14", "...", "R1", "R0", "L15"] },
                ]}

        - Data is updated on the falling edge
        - Data is sampled on the rising edge
        - Words are MSB-to-LSB,
        - Sync is an input or output based on configure mode,
        - Sync can be longer than the wordlen, extra bits are just ignored
        - Tx is data to the codec (SDI pin on LM49352)
        - Rx is data from the codec (SDO pin on LM49352)
        """
    def __init__(self, *, sample_width: int, frame_format: I2S_FORMAT = I2S_FORMAT.STANDARD, fifo_depth=16):
        self._sample_width = sample_width
        self._frame_format = frame_format
        self._fifo_depth = fifo_depth

        self.enable_in        = Signal()
        self.stream_out       = StreamInterface(payload_width=sample_width)
        self.word_select_in   = Signal()
        self.serial_clock_in  = Signal()
        self.serial_data_in   = Signal()
        self.fifo_level_out   = Signal(range(fifo_depth + 1))

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        sample_width = self._sample_width
        frame_format = self._frame_format

        fifo_data_width = sample_width
        concatenate_channels = True
        if concatenate_channels:
            if sample_width <= 16:
                fifo_data_width = sample_width * 2
            else:
                concatenate_channels = False
                print("I2S warning: sample width greater than 16 bits. your channels can't be glued")

        rx_cnt_width = math.ceil(math.log(fifo_data_width, 2))
        rx_cnt = Signal(rx_cnt_width)

        bit_clock  = Signal()
        word_clock = Signal()
        m.submodules.bit_clock_synchronizer  = FFSynchronizer(self.serial_clock_in, bit_clock)
        m.submodules.word_clock_synchronizer = FFSynchronizer(self.word_select_in, word_clock)

        bit_clock_rose  = Signal()
        bit_clock_fell  = Signal()
        m.d.comb += [
            bit_clock_rose .eq(rising_edge_detected(m, bit_clock)),
            bit_clock_fell.eq(falling_edge_detected(m, bit_clock)),
        ]

        left_channel  = Signal()
        right_channel = Signal()
        m.d.comb += [
            left_channel.eq(~word_clock if frame_format == I2S_FORMAT.STANDARD else word_clock),
            right_channel.eq(~left_channel)
        ]

        m.submodules.rx_fifo = rx_fifo = SyncFIFO(width=fifo_data_width + 1, depth=self._fifo_depth)

        rx_buf       = Signal(fifo_data_width)
        rx_delay_cnt = Signal()
        rx_delay_val = 1 if frame_format == I2S_FORMAT.STANDARD else 0

        # first marks left channel, last marks right channel
        m.d.comb += [
            connect_fifo_to_stream(rx_fifo, self.stream_out),
            rx_fifo.w_data.eq(Cat(rx_buf, left_channel)),
            # at the time the channel flag is written into the FIFO
            # the word clock has already flipped,
            # so we have to flip the first/last flags here
            self.stream_out.first.eq(~rx_fifo.r_data[-1] & self.stream_out.valid),
            self.stream_out.last.eq(rx_fifo.r_data[-1] & self.stream_out.valid),
            rx_fifo.w_en.eq(0),
            self.fifo_level_out.eq(rx_fifo.level),
        ]

        with m.FSM(reset="IDLE"):
            with m.State("IDLE"):
                m.d.sync += rx_buf.eq(0)
                with m.If(self.enable_in):
                    with m.If(bit_clock_rose & left_channel):
                        m.d.sync += rx_delay_cnt.eq(rx_delay_val)
                        m.next = "WAIT_SYNC"

            with m.State("WAIT_SYNC"):
                with m.If(bit_clock_rose & left_channel):
                    with m.If(rx_delay_cnt > 0):
                        m.d.sync += rx_delay_cnt.eq(rx_delay_cnt - 1)
                        m.next = "WAIT_SYNC"
                    with m.Else():
                        m.d.sync += [
                            rx_delay_cnt.eq(rx_delay_val),
                            rx_cnt.eq(sample_width),
                        ]
                        m.next = "LEFT"

            with m.State("LEFT"):
                with m.If(~self.enable_in):
                    m.next = "IDLE"
                with m.Else():
                    m.d.sync += [
                        rx_buf.eq(Cat(self.serial_data_in, rx_buf[:-1])),
                        rx_cnt.eq(rx_cnt - 1),
                    ]
                    m.next = "LEFT_WAIT"

            if concatenate_channels:
                with m.State("LEFT_WAIT"):
                    with m.If(~self.enable_in):
                        m.next = "IDLE"
                    with m.Else():
                        with m.If(bit_clock_rose):
                            with m.If((rx_cnt == 0)):
                                with m.If(right_channel):
                                    with m.If(rx_delay_cnt == 0):
                                        m.d.sync += [
                                            rx_cnt.eq(sample_width),
                                            rx_delay_cnt.eq(rx_delay_val),
                                        ]
                                        m.next = "RIGHT"
                                    with m.Else():
                                        m.d.sync += rx_delay_cnt.eq(rx_delay_cnt - 1)
                                        m.next = "LEFT_WAIT"
                                with m.Else():
                                    m.next = "LEFT_WAIT"
                            with m.Elif(rx_cnt > 0):
                                m.next = "LEFT"
            else:
                with m.State("LEFT_WAIT"):
                    with m.If(~self.enable_in):
                        m.next = "IDLE"
                    with m.Else():
                        with m.If(bit_clock_rose):
                            with m.If(rx_cnt == 0):
                                with m.If(right_channel):
                                    with m.If(rx_delay_cnt == 0):
                                        # write the current data word
                                        m.d.comb += rx_fifo.w_en.eq(1)
                                        m.d.sync += [
                                                rx_cnt.eq(sample_width),
                                                rx_delay_cnt.eq(rx_delay_val),
                                        ]
                                        m.next = "RIGHT"
                                    with m.Else():
                                        m.d.sync += rx_delay_cnt.eq(rx_delay_cnt - 1)
                                        m.next = "LEFT_WAIT"
                                with m.Else():
                                    m.next = "LEFT_WAIT"
                            with m.Elif(rx_cnt > 0):
                                m.next = "LEFT"

            with m.State("RIGHT"):
                with m.If(~self.enable_in):
                    m.next = "IDLE"
                with m.Else():
                    m.d.sync += [
                        rx_buf.eq(Cat(self.serial_data_in, rx_buf[:-1])),
                        rx_cnt.eq(rx_cnt - 1),
                    ]
                    m.next = "RIGHT_WAIT"

            with m.State("RIGHT_WAIT"):
                with m.If(~self.enable_in):
                    m.next = "IDLE"
                with m.Else():
                    with m.If(bit_clock_rose):
                        with m.If((rx_cnt == 0) & left_channel):
                            with m.If(rx_delay_cnt == 0):
                                # write the current data word
                                m.d.comb += rx_fifo.w_en.eq(1)
                                m.d.sync += [
                                    rx_cnt      .eq(sample_width),
                                    rx_delay_cnt.eq(rx_delay_val),
                                ]
                                m.next = "LEFT"
                            with m.Else():
                                m.d.sync += rx_delay_cnt.eq(rx_delay_cnt - 1)
                                m.next = "RIGHT_WAIT"
                        with m.Elif(rx_cnt > 0):
                            m.next =  "RIGHT"

        return m

def send_i2s(stream: StreamInterface):
    payload = stream.payload
    valid   = stream.valid
    first   = stream.first

    yield

    yield valid.eq(1)
    yield first.eq(1)
    yield payload.eq(0x111111)
    yield

    yield payload.eq(0x222222)
    yield first.eq(0)
    yield

    yield payload.eq(0x333333)
    yield first.eq(1)
    yield

    yield payload.eq(0x444444)
    yield first.eq(0)
    yield

    yield payload.eq(0x555555)
    yield first.eq(1)
    yield

    yield payload.eq(0x666666)
    yield first.eq(0)
    yield

    yield payload.eq(0xaaaaaa)
    yield first.eq(1)
    yield

    yield payload.eq(0xbbbbbb)
    yield first.eq(0)
    yield

    yield payload.eq(0xcccccc)
    yield first.eq(1)
    yield

    yield payload.eq(0xdddddd)
    yield first.eq(0)
    yield

    yield payload.eq(0xeeeeee)
    yield first.eq(1)
    yield

    yield payload.eq(0xffffff)
    yield first.eq(0)
    yield

    yield valid.eq(0)
    yield


class I2STransmitterTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = I2STransmitter
    FRAGMENT_ARGUMENTS = {'sample_width': 24}

    @sync_test_case
    def test_basic(self):
        dut = self.dut

        yield from send_i2s(dut.stream_in)

        yield dut.enable_in.eq(1)
        yield

        serial_clock = 0
        word_select  = 0
        for i in range(2700):
            if i % 3 == 0:
                yield dut.serial_clock_in.eq(serial_clock)
                serial_clock = ~serial_clock
            if i % (3 * 64) == 0:
                yield dut.word_select_in.eq(word_select)
                word_select = ~word_select
            yield

class I2SLoopbackTestHarness(Elaboratable):
    def __init__(self) -> None:
        self.stream_in  = StreamInterface(payload_width=24)
        self.stream_out = StreamInterface(payload_width=24)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        m.submodules.transmitter   = transmitter = I2STransmitter(sample_width=24)
        m.submodules.receiver      = receiver    = I2SReceiver(sample_width=24)

        # generate synthetic I2S clocks
        word_counter = Signal(8)
        bit_counter  = Signal(2)
        word_clock = Signal()
        bit_clock  = Signal()
        m.d.sync += [
            word_counter.eq(word_counter + 1),
            bit_counter.eq(bit_counter + 1),
        ]

        with m.If(word_counter == 0):
            m.d.sync += word_clock.eq(~word_clock)

        with m.If(bit_counter == 0):
            m.d.sync += bit_clock.eq(~bit_clock)

        m.d.comb += [
            transmitter.stream_in.stream_eq(self.stream_in),
            transmitter.serial_clock_in.eq(bit_clock),
            transmitter.word_select_in.eq(word_clock),
            transmitter.enable_in.eq(1),
            self.stream_out.stream_eq(receiver.stream_out),
            receiver.serial_data_in.eq(transmitter.serial_data_out),
            receiver.serial_clock_in.eq(bit_clock),
            receiver.word_select_in.eq(word_clock),
            receiver.enable_in.eq(1),
            receiver.stream_out.ready.eq(1),
        ]

        return m

class I2SLoopbackTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = I2SLoopbackTestHarness
    FRAGMENT_ARGUMENTS = {}

    @sync_test_case
    def test_basic(self):
        dut = self.dut

        yield from send_i2s(dut.stream_in)

        for _ in range(10000):
            yield