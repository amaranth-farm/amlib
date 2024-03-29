#
# This file has been adopted from the LUNA project
#
# Copyright (c) 2020 Great Scott Gadgets <info@greatscottgadgets.com>
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
#
# SPDX-License-Identifier: BSD-3-Clause

""" Stream generators. """
import unittest
from amaranth       import *
from amaranth.utils import bits_for
from .            import StreamInterface
from ..test       import GatewareTestCase, sync_test_case


class ConstantStreamGenerator(Elaboratable):
    """ Gateware that generates stream of constant data.

    Attributes
    ----------
    start: Signal(), input
        Strobe that indicates when the stream should be started.
    done: Signal(), output
        Strobe that pulses high when we're finishing a transmission.

    start_position: Signal(range(len(data)), input
        Specifies the starting position in the constant stream; applied when start() is pulsed.

    max_length: Signal(max_length_width), input
        The maximum length to be sent -in bytes-. Defaults to the length of the stream.
        Only present if the `max_length_width` parameter is provided on creation.
    output_length: Signal(max_length_width), output
        Indicates the actual data length for the stream currently being output.
        Will always be the lesser of our data length and :attr:``max_length``.
        Only present if the `max_length_width` parameter is provided on creation.

    stream: stream_type(), output stream
        The generated stream interface.

    Parameters
    ----------
    constant_data: bytes, or equivalent
        The constant data for the stream to be generated.
        Should be an iterable of integers; or, if data_width is divisible by 8, a bytes-like object.
    domain: string
        The clock domain this generator should belong to. Defaults to 'sync'.
    stream_type: StreamInterface, or subclass
        The type of stream we'll be multiplexing.
    data_width: int, optional
        The width of the constant payload. If not provided; will be taken from the stream's payload width.
    max_length_width: int
        If provided, a `max_length` signal will be present that can limit the total length transmitted.
    data_endianness: little
        If bytes are provided, and our data width is greater
    """

    def __init__(self, constant_data, domain="sync", stream_type=StreamInterface,
            max_length_width=None, data_width=None, data_endianness="little"):

        self._domain           = domain
        self._data             = constant_data
        self._data_length      = len(constant_data)
        self._endianness       = data_endianness
        self._max_length_width = max_length_width

        # I/O port.
        self.start           = Signal()
        self.done            = Signal()

        # If we have a data width, apply it to our stream type; otherwise, use its defaults.
        if data_width:
            self.stream      = stream_type(payload_width=data_width)
            self._data_width = data_width
        else:
            self.stream      = stream_type()
            self._data_width = len(self.stream.data)

        self.start_position = Signal(range(self._data_length))

        # If we have a maximum length width, include it in our I/O port.
        # Otherwise, use a constant.
        if max_length_width:
            self.max_length        = Signal(max_length_width)
            self.output_length     = Signal.like(self.max_length)
        else:
            self.max_length = self._data_length

    def _get_initializer_value(self):
        """ Returns this geneartor's data in a form usable as a ROM initializer.

        Returns
        -------
        initializer_data: interable
            An iterable suitable for use in initializing a ROM.
        valid_bytes_last_word: int
            The number of valid bits that should accompany the last word.

            For example, if we have 32-bit words; and 3 bytes of data, we'd have
            three valid bits on the last word; since the upper 8-bits are meaningless.
        """

        # If we have byte-sized data, Python will implicitly handle things correctly.
        # Return our data unmodified.
        if self._data_width == 8:
            return self._data, len(self.stream.valid)

        # If we don't have a byte-string, return our data without pre-processing.
        if not isinstance(self._data, (bytes, bytearray)):
            return self._data, len(self.stream.valid)

        # If our width isn't evenly divisible by 8, we can't accept bytes.
        if (self._data_width % 8):
            raise ValueError("Can't initialize with bytes unless data_width is divisible by 8!")

        # Figure out how wide each datum will be in bytes.
        datum_width_bytes = self._data_width // 8

        # Otherwise, we'll split it into a list of integers, manually.
        in_data  = bytearray(self._data)
        out_data = []

        while in_data:
            # Extract each datum from our stream...
            datum = in_data[0:datum_width_bytes]
            del in_data[0:datum_width_bytes]

            # ... convert it into an integer ...
            datum = int.from_bytes(datum, byteorder=self._endianness)

            # ... and squish it into our output.
            out_data.append(datum)

        # Figure out how many bytes will be in our last word.
        last_word_bytes = len(self._data) % datum_width_bytes
        if last_word_bytes == 0:
            last_word_bytes = datum_width_bytes

        return out_data, last_word_bytes

    def elaborate(self, platform):
        m = Module()

        # Core ROM.

        # Figure out the shape of our data.
        data_initializer, valid_bits_last_word = self._get_initializer_value()
        data_length = len(data_initializer)

        rom = Memory(width=self._data_width, depth=data_length, init=data_initializer)
        m.submodules.rom_read_port = rom_read_port = rom.read_port(transparent=False)

        # Register that stores our current position in the stream.
        position_in_stream = Signal(range(0, data_length))

        # If we have a maximum length we're enforcing, create a counter for it.
        if self._max_length_width:
            bytes_sent     = Signal(self._max_length_width)
            bytes_per_word = (self._data_width + 7) // 8
        else:
            bytes_sent     = Signal()
            bytes_per_word = 0

        # Track when we're on the first and last packet.
        on_first_packet = position_in_stream == self.start_position
        on_last_packet  = \
            (position_in_stream          == (data_length - 1)) | \
            (bytes_sent + bytes_per_word >= self.max_length)

        #
        # Figure out where we should start in our stream.
        #
        start_position = Signal.like(position_in_stream)

        # If our starting position is greater than our data length, use our data length.
        with m.If(self.start_position >= self._data_length):
            m.d.comb += start_position.eq(data_length - 1)

        # Otherwise, use our starting position.
        with m.Else():
            m.d.comb += start_position.eq(self.start_position)

        if hasattr(self, "output_length"):
            # Output length field.
            # Return our max length of the length of our data, whichever is less.
            with m.If(self.max_length < self._data_length):
                m.d.comb += self.output_length.eq(self.max_length)
            with m.Else():
                m.d.comb += self.output_length.eq(self._data_length)

        # Controller.
        with m.FSM(domain=self._domain) as fsm:
            m.d.comb += self.stream.valid.eq(fsm.ongoing('STREAMING'))

            # IDLE -- we're not actively transmitting.
            with m.State('IDLE'):

                # Keep ourselves at the beginning of the stream, but don't yet count.
                m.d.sync += [
                    position_in_stream  .eq(start_position),
                    bytes_sent          .eq(0)
                ]
                m.d.comb += [
                    rom_read_port.addr  .eq(start_position),
                ]

                # Once the user requests that we start, move to our stream being valid.
                with m.If(self.start & (self.max_length > 0)):
                    m.next = 'STREAMING'

            # STREAMING -- we're actively transmitting data
            with m.State('STREAMING'):
                m.d.comb += [
                    # Always drive the stream from our current memory output...
                    rom_read_port.addr   .eq(position_in_stream),
                    self.stream.payload  .eq(rom_read_port.data),

                    ## ... and base First and Last based on our current position in the stream.
                    self.stream.first    .eq(on_first_packet),
                    self.stream.last     .eq(on_last_packet)
                ]

                # Our ``valid`` flag requires a bunch of special handling, since it could be
                # wider than one bit for streams with multi-byte words; and it could be set
                # by either our max_length limiter or by our data length. This logic is complex,
                # but hopefully actually generates relatively simple hardware.


                # Explicit optimization: if we have a valid length of one, don't bother
                # with all of this logic. This ensures we never degrade speed for trivial cases.
                if len(self.stream.valid) == 1:
                    m.d.comb += self.stream.valid.eq(1)

                # Otherwise, we have more complex logic to deal with.
                else:
                    # If we're on the last packet, we'll apply as many valid bits as we have valid
                    # bytes in our data stream.
                    with m.If(on_last_packet):

                        # If we're not enforcing a max length, always use our leftover bits-per-word.
                        if not self._max_length_width:
                            m.d.comb += self.stream.valid.eq(Repl(Const(1), valid_bits_last_word))

                        # Otherwise, do our complex case.
                        else:
                            # Figure out if we're ending due to the length of data we have, or due to a
                            # maximum-to-send restriction...
                            ending_due_to_data_length = (position_in_stream == (data_length - 1))
                            ending_due_to_max_length  = (bytes_sent + bytes_per_word >= self.max_length)

                            # ... and figure out the valid bits based us running out of data...
                            valid_due_to_data_length  = Repl(Const(1), valid_bits_last_word)

                            # ... and due to our maximum length. Finding this arithmetically creates
                            # difficult-to-optimize code, and bytes_per_word is going to be small, so
                            # we'll figure this out enumeratively.
                            bytes_left_over         = Signal(range(bytes_per_word + 1))
                            valid_due_to_max_length = Signal.like(self.stream.valid)
                            m.d.comb += bytes_left_over.eq(self.max_length - bytes_sent)

                            # Generate a case for every possibly number of bytes left over...
                            with m.Switch(bytes_left_over):
                                for i in range(1, bytes_per_word + 1):

                                    # ... with the appropriate amount of valid bits.
                                    with m.Case(i):
                                        m.d.comb += valid_due_to_max_length.eq(Repl(Const(1), i))

                            # Our most complex logic is when both of our end conditions are met; we'll need
                            # to take the lesser of the two validities. AND'ing these will work to accept the
                            # lesser of the two validities.
                            with m.If(ending_due_to_data_length & ending_due_to_max_length):
                                m.d.comb += self.stream.valid.eq(valid_due_to_data_length & valid_due_to_max_length)

                            # If we're ending due to the length of data we have, use our normal logic.
                            with m.Elif(ending_due_to_data_length):
                                m.d.comb += self.stream.valid.eq(valid_due_to_data_length)

                            # Otherwise, we're endign due to our maximum length requirement. We'll apply the
                            # appropriate valid mask.
                            with m.Else():
                                m.d.comb += self.stream.valid.eq(valid_due_to_max_length)

                    # If we're not on our last word, every valid bit should be set.
                    with m.Else():
                        valid_bits = len(self.stream.valid)
                        m.d.comb += self.stream.valid.eq(Repl(Const(1), valid_bits))

                # If the current data byte is accepted, move past it.
                with m.If(self.stream.ready):

                    # If there's still data left to transmit, move forward.
                    with m.If(~on_last_packet):
                        m.d.sync += position_in_stream.eq(position_in_stream + 1)
                        m.d.comb += rom_read_port.addr.eq(position_in_stream + 1)

                        if self._max_length_width:
                            m.d.sync += bytes_sent.eq(bytes_sent + bytes_per_word)

                    # Otherwise, we've finished streaming. Return to IDLE.
                    with m.Else():
                        m.next = 'DONE'

            # DONE -- report our completion; and then return to idle
            with m.State('DONE'):
                m.d.comb += self.done.eq(1)
                m.next = 'IDLE'

        # Convert our sync domain to the domain requested by the user, if necessary.
        if self._domain != "sync":
            m = DomainRenamer({"sync": self._domain})(m)

        return m


class ConstantStreamGeneratorTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = ConstantStreamGenerator
    FRAGMENT_ARGUMENTS  = {'constant_data': b"HELLO, WORLD", 'domain': "sync", 'max_length_width': 16}

    @sync_test_case
    def test_basic_transmission(self):
        dut = self.dut

        # Establish a very high max length; so it doesn't apply.
        yield dut.max_length.eq(1000)

        # We shouldn't see a transmission before we request a start.
        yield from self.advance_cycles(10)
        self.assertEqual((yield dut.stream.valid), 0)
        self.assertEqual((yield dut.stream.first), 0)
        self.assertEqual((yield dut.stream.last),  0)

        # Once we pulse start, we should see the transmission start,
        # and we should see our first byte of data.
        yield from self.pulse(dut.start)
        self.assertEqual((yield dut.stream.valid),   1)
        self.assertEqual((yield dut.stream.payload), ord('H'))
        self.assertEqual((yield dut.stream.first),   1)

        # That data should remain there until we accept it.
        yield from self.advance_cycles(10)
        self.assertEqual((yield dut.stream.valid),   1)
        self.assertEqual((yield dut.stream.payload), ord('H'))

        # Once we indicate that we're accepting data...
        yield dut.stream.ready.eq(1)
        yield

        # ... we should start seeing the remainder of our transmission.
        for i in 'ELLO':
            yield
            self.assertEqual((yield dut.stream.payload), ord(i))
            self.assertEqual((yield dut.stream.first),   0)


        # If we drop the 'accepted', we should still see the next byte...
        yield dut.stream.ready.eq(0)
        yield
        self.assertEqual((yield dut.stream.payload), ord(','))

        # ... but that byte shouldn't be accepted, so we should remain there.
        yield
        self.assertEqual((yield dut.stream.payload), ord(','))

        # If we start accepting data again...
        yield dut.stream.ready.eq(1)
        yield

        # ... we should see the remainder of the stream.
        for i in ' WORLD':
            yield
            self.assertEqual((yield dut.stream.payload), ord(i))


        # On the last byte of data, we should see last = 1.
        self.assertEqual((yield dut.stream.last),   1)

        # After the last datum, we should see valid drop to '0'.
        yield
        self.assertEqual((yield dut.stream.valid), 0)

    @sync_test_case
    def test_basic_start_position(self):
        dut = self.dut

        # Start at position 2
        yield dut.start_position.eq(2)

        # Establish a very high max length; so it doesn't apply.
        yield dut.max_length.eq(1000)

        # We shouldn't see a transmission before we request a start.
        yield from self.advance_cycles(10)
        self.assertEqual((yield dut.stream.valid), 0)
        self.assertEqual((yield dut.stream.first), 0)
        self.assertEqual((yield dut.stream.last),  0)

        # Once we pulse start, we should see the transmission start,
        # and we should see our first byte of data.
        yield from self.pulse(dut.start)
        self.assertEqual((yield dut.stream.valid),   1)
        self.assertEqual((yield dut.stream.payload), ord('L'))
        self.assertEqual((yield dut.stream.first),   1)

        # That data should remain there until we accept it.
        yield from self.advance_cycles(10)
        self.assertEqual((yield dut.stream.valid),   1)
        self.assertEqual((yield dut.stream.payload), ord('L'))

        # Once we indicate that we're accepting data...
        yield dut.stream.ready.eq(1)
        yield

        # ... we should start seeing the remainder of our transmission.
        for i in 'LO':
            yield
            self.assertEqual((yield dut.stream.payload), ord(i))
            self.assertEqual((yield dut.stream.first),   0)


        # If we drop the 'accepted', we should still see the next byte...
        yield dut.stream.ready.eq(0)
        yield
        self.assertEqual((yield dut.stream.payload), ord(','))

        # ... but that byte shouldn't be accepted, so we should remain there.
        yield
        self.assertEqual((yield dut.stream.payload), ord(','))

        # If we start accepting data again...
        yield dut.stream.ready.eq(1)
        yield

        # ... we should see the remainder of the stream.
        for i in ' WORLD':
            yield
            self.assertEqual((yield dut.stream.payload), ord(i))


        # On the last byte of data, we should see last = 1.
        self.assertEqual((yield dut.stream.last),   1)

        # After the last datum, we should see valid drop to '0'.
        yield
        self.assertEqual((yield dut.stream.valid), 0)

    @sync_test_case
    def test_max_length(self):
        dut = self.dut

        yield dut.stream.ready.eq(1)
        yield dut.max_length.eq(6)

        # Once we pulse start, we should see the transmission start,
        yield from self.pulse(dut.start)

        # ... we should start seeing the remainder of our transmission.
        for i in 'HELLO':
            self.assertEqual((yield dut.stream.payload), ord(i))
            yield


        # On the last byte of data, we should see last = 1.
        self.assertEqual((yield dut.stream.last),   1)

        # After the last datum, we should see valid drop to '0'.
        yield
        self.assertEqual((yield dut.stream.valid), 0)


@unittest.skip("https://github.com/hansfbaier/amaranth-library/issues/1")
class ConstantStreamGeneratorWideTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = ConstantStreamGenerator
    FRAGMENT_ARGUMENTS  = dict(
        domain           = "sync",
        constant_data    = b"HELLO WORLD",
        stream_type      = StreamInterface,
        max_length_width = 16
    )

    @sync_test_case
    def test_basic_transmission(self):
        dut = self.dut

        # Establish a very high max length; so it doesn't apply.
        yield dut.max_length.eq(1000)

        # We shouldn't see a transmission before we request a start.
        yield from self.advance_cycles(10)
        self.assertEqual((yield dut.stream.valid), 0)
        self.assertEqual((yield dut.stream.first), 0)
        self.assertEqual((yield dut.stream.last),  0)

        # Once we pulse start, we should see the transmission start,
        # and we should see our first byte of data.
        yield from self.pulse(dut.start)
        self.assertEqual((yield dut.stream.valid),   0b1111)
        self.assertEqual((yield dut.stream.payload), int.from_bytes(b"HELL", byteorder="little"))
        self.assertEqual((yield dut.stream.first),   1)

        # That data should remain there until we accept it.
        yield from self.advance_cycles(10)
        self.assertEqual((yield dut.stream.valid),   0b1111)
        self.assertEqual((yield dut.stream.payload), int.from_bytes(b"HELL", byteorder="little"))

        # Once we indicate that we're accepting data...
        yield dut.stream.ready.eq(1)
        yield

        # ... we should start seeing the remainder of our transmission.
        yield
        self.assertEqual((yield dut.stream.valid),   0b1111)
        self.assertEqual((yield dut.stream.payload), int.from_bytes(b"O WO", byteorder="little"))
        self.assertEqual((yield dut.stream.first),   0)

        yield
        self.assertEqual((yield dut.stream.valid),   0b111)
        self.assertEqual((yield dut.stream.payload), int.from_bytes(b"RLD", byteorder="little"))
        self.assertEqual((yield dut.stream.first),   0)

        # On the last byte of data, we should see last = 1.
        self.assertEqual((yield dut.stream.last),   1)

        # After the last datum, we should see valid drop to '0'.
        yield
        self.assertEqual((yield dut.stream.valid), 0)

    @sync_test_case
    def test_max_length_transmission(self):
        dut = self.dut

        # Apply a maximum length of six bytes.
        yield dut.max_length.eq(6)
        yield dut.stream.ready.eq(1)

        # Once we pulse start, we should see the transmission start,
        # and we should see our first byte of data.
        yield from self.pulse(dut.start)
        self.assertEqual((yield dut.stream.valid),   0b1111)
        self.assertEqual((yield dut.stream.payload), int.from_bytes(b"HELL", byteorder="little"))
        self.assertEqual((yield dut.stream.first),   1)

        # We should then see only two bytes of our remainder.
        yield
        self.assertEqual((yield dut.stream.valid),   0b0011)
        self.assertEqual((yield dut.stream.payload), int.from_bytes(b"O WO", byteorder="little"))
        self.assertEqual((yield dut.stream.first),   0)
        self.assertEqual((yield dut.stream.last),    1)

    @sync_test_case
    def test_very_short_max_length(self):
        dut = self.dut

        # Apply a maximum length of six bytes.
        yield dut.max_length.eq(2)

        # Once we pulse start, we should see the transmission start,
        # and we should see our first word of data.
        yield from self.pulse(dut.start)
        self.assertEqual((yield dut.stream.valid),   0b0011)
        self.assertEqual((yield dut.stream.payload), int.from_bytes(b"HELL", byteorder="little"))
        self.assertEqual((yield dut.stream.first),   1)
        self.assertEqual((yield dut.stream.last),    1)

        # Our data should remain there until it's accepted.
        yield dut.stream.ready.eq(1)
        yield
        self.assertEqual((yield dut.stream.valid),   0b0011)
        self.assertEqual((yield dut.stream.payload), int.from_bytes(b"HELL", byteorder="little"))
        self.assertEqual((yield dut.stream.first),   1)
        self.assertEqual((yield dut.stream.last),    1)

        # After acceptance, valid should drop back to false.
        yield
        self.assertEqual((yield dut.stream.valid),   0b0000)


class StreamSerializer(Elaboratable):
    """ Gateware that serializes a short Array input onto a stream.

    I/O port:
        I: start        -- Strobe that indicates when the stream should be started.
        O: done         -- Strobe that pulses high when we're finishing a transmission.

        I: data[]       -- The data stream to be sent out. Length is set by the data_length initializer argument.
        I: max_length[] -- The maximum length to be sent. Defaults to the length of the stream.
                           Only present if the `max_length_width` parameter is provided on creation.

        *: stream       -- The generated stream interface.

    """

    def __init__(self, data_length, domain="sync", data_width=8, stream_type=StreamInterface, max_length_width=None):
        """
        Parameters:
            constant_data      -- The constant data for the stream to be generated.
                                  Should be an array of integers; or, if data_width=8, a bytes-like object.
            domain             -- The clock domain this generator should belong to. Defaults to 'sync'.
            data_width         -- The width of the constant payload
            stream_type        -- The type of stream we'll be multiplexing. Must be a subclass of StreamInterface.
            max_length_width   -- If provided, a `max_length` signal will be present that can limit the total length
                                  transmitted.
        """

        self.domain      = domain
        self.data_width  = data_width
        self.data_length = data_length

        #
        # I/O port.
        #
        self.start       = Signal()
        self.done        = Signal()

        self.data        = Array(Signal(data_width, name=f"datum_{i}") for i in range(data_length))
        self.stream      = stream_type(payload_width=data_width)


        # If we have a maximum length width, include it in our I/O port.
        # Otherwise, use a constant.
        if max_length_width:
            self.max_length = Signal(max_length_width)
        else:
            self.max_length = self.data_length

    def elaborate(self, platform):
        m = Module()

        # Register that stores our current position in the stream.
        position_in_stream = Signal(range(0, self.data_length))

        # Track when we're on the first and last packet.
        on_first_packet = position_in_stream == 0
        on_last_packet  = \
            (position_in_stream == (self.data_length - 1)) | \
            (position_in_stream == (self.max_length - 1))

        m.d.comb += [
            # Create first and last based on our stream position.
            self.stream.first    .eq(on_first_packet & self.stream.valid),
            self.stream.last     .eq(on_last_packet  & self.stream.valid)
        ]

        #
        # Controller.
        #
        with m.FSM(domain=self.domain) as fsm:
            m.d.comb += self.stream.valid.eq(fsm.ongoing('STREAMING'))

            # IDLE -- we're not actively transmitting.
            with m.State('IDLE'):

                # Keep ourselves at the beginning of the stream, but don't yet count.
                m.d.sync += position_in_stream.eq(0)

                # Once the user requests that we start, move to our stream being valid.
                with m.If(self.start & (self.max_length > 0)):
                    m.next = 'STREAMING'


            # STREAMING -- we're actively transmitting data
            with m.State('STREAMING'):
                m.d.comb += self.stream.payload.eq(self.data[position_in_stream])

                # If the current data byte is accepted, move past it.
                with m.If(self.stream.ready):

                    should_continue = \
                        ((position_in_stream + 1) < self.max_length) & \
                        ((position_in_stream + 1) < self.data_length)

                    # If there's still data left to transmit, move forward.
                    with m.If(should_continue):
                        m.d.sync += position_in_stream.eq(position_in_stream + 1)

                    # Otherwise, we've finished streaming. Return to IDLE.
                    with m.Else():
                        m.next = 'DONE'

            # DONE -- report our completion; and then return to idle
            with m.State('DONE'):
                m.d.comb += self.done.eq(1)
                m.next = 'IDLE'

        # Convert our sync domain to the domain requested by the user, if necessary.
        if self.domain != "sync":
            m = DomainRenamer({"sync": self.domain})(m)

        return m

class PacketListStreamer(Elaboratable):
    """ Gateware that takes a list of lists of bytes and sends them onto a stream,
        where the first and last signals of the stream delineate the individual packets

    Parameters
    ----------
    packets : List[List[int]]
        the list of packet contents that will be transmitted

    data_width : int
        determines, how wide the payload signal of the output stream is

    Attributes
    ----------
        start : Signal, in
            Strobe that indicates when the stream should be started.
        done : Signal, out
            Strobe that pulses high when we're finishing a transmission.

        stream : StreamInterface or custom, out
            The generated stream interface.

    """
    def __init__(self, packets, data_width=None, stream_type=StreamInterface):
        self.start      = Signal()
        self.done       = Signal()
        self.packets    = packets

        # If we have a data width, apply it to our stream type; otherwise, use its defaults.
        if data_width:
            self.stream  = stream_type(payload_width=data_width)
            self._data_width = data_width
        else:
            self.stream  = stream_type()
            self._data_width = len(self.stream.data)

    def elaborate(self, platform) -> Module:
        m = Module()
        packet_lengths = [len(p) for p in self.packets]
        no_packets = len(packet_lengths)

        max_length_width = bits_for(max(packet_lengths))
        packets_flattened = [words for packet in self.packets for words in packet]

        m.submodules.generator = generator = \
            ConstantStreamGenerator(packets_flattened, max_length_width=max_length_width)

        rom = Memory(width=max_length_width, depth=no_packets, init=packet_lengths)
        m.submodules.packet_lengths_rom = packet_lengths_rom = rom.read_port(transparent=False)

        total_no_bytes = len(packets_flattened)

        position           = Signal(range(total_no_bytes))
        next_position      = Signal.like(position)
        current_packet     = Signal(range(no_packets))
        current_packet_len = Signal(max_length_width)

        m.d.comb += [
            self.stream.stream_eq(generator.stream),
            generator.start.eq(0),
            generator.start_position.eq(position),
            packet_lengths_rom.addr.eq(current_packet),
            current_packet_len.eq(packet_lengths_rom.data),
            generator.max_length.eq(current_packet_len),
            next_position.eq(position + current_packet_len),
            self.done.eq(0)
        ]

        with m.FSM():
            with m.State("INIT"):
                with m.If(self.start):
                    m.d.comb += generator.start.eq(1)
                    m.next = "WAIT"

            with m.State("SEND"):
                m.d.comb += generator.start.eq(1)
                m.next = "WAIT"

            with m.State("WAIT"):
                with m.If(generator.done):
                    with m.If(next_position >= total_no_bytes):
                        m.d.comb += self.done.eq(1)
                        m.d.sync += [
                            position.eq(0),
                            current_packet.eq(0),
                        ]
                        m.next = "INIT"
                    with m.Else():
                        m.d.sync += [
                            position.eq(next_position),
                            current_packet.eq(current_packet + 1),
                        ]
                        m.next = "SEND"

        return m

class PacketListStreamerTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = PacketListStreamer
    FRAGMENT_ARGUMENTS = { 'packets': [b"Hi, ", b"dear", b" ", b"nMigen-", b"-", b"users!"] }

    def traces_of_interest(self):
        dut = self.dut
        return [self.dut.stream.valid,
                self.dut.stream.ready,
                self.dut.stream.payload,
                self.dut.stream.first,
                self.dut.stream.last,
                self.dut.start,
                self.dut.done]

    def wait_for_next_packet(self):
        yield
        self.assertEqual((yield self.dut.stream.valid), 0)
        yield
        self.assertEqual((yield self.dut.stream.valid), 0)

    @sync_test_case
    def test_basic_transmission(self):
        dut = self.dut

        # We shouldn't see a transmission before we request a start.
        yield from self.advance_cycles(10)
        self.assertEqual((yield dut.stream.valid), 0)
        self.assertEqual((yield dut.stream.first), 0)
        self.assertEqual((yield dut.stream.last),  0)

        # Once we pulse start, we should see the transmission start,
        # and we should see our first byte of data.
        yield from self.pulse(dut.start)
        yield # needs one cycle to start
        self.assertEqual((yield dut.stream.valid),   1)
        self.assertEqual((yield dut.stream.payload), ord('H'))
        self.assertEqual((yield dut.stream.first),   1)

        # That data should remain there until we accept it.
        yield from self.advance_cycles(10)
        self.assertEqual((yield dut.stream.valid),   1)
        self.assertEqual((yield dut.stream.payload), ord('H'))

        # Once we indicate that we're accepting data...
        yield dut.stream.ready.eq(1)
        yield

        # ... we should start seeing the remainder of our transmission.
        for i in 'i,':
            yield
            self.assertEqual((yield dut.stream.payload), ord(i))
            self.assertEqual((yield dut.stream.first),   0)

        # end of the first packet has to be marked by the 'last' signal
        yield
        self.assertEqual((yield dut.stream.payload), ord(' '))
        self.assertEqual((yield dut.stream.first),   0)
        self.assertEqual((yield dut.stream.last),    1)

        # first packet done, takes two cycles to load the next
        yield from self.wait_for_next_packet()

        # If we drop the 'accepted', we should still see the next byte...
        yield dut.stream.ready.eq(0)
        yield
        self.assertEqual((yield dut.stream.payload), ord('d'))

        # ... but that byte shouldn't be accepted, so we should remain there.
        yield
        self.assertEqual((yield dut.stream.payload), ord('d'))

        # If we start accepting data again...
        yield dut.stream.ready.eq(1)
        yield

        # ... we should see the second packet
        for i in 'ear':
            yield
            self.assertEqual((yield dut.stream.payload), ord(i))
            if i == 'd':
                self.assertEqual((yield dut.stream.first), 1)
                self.assertEqual((yield dut.stream.last),  0)
            if i == 'r':
                self.assertEqual((yield dut.stream.first), 0)
                self.assertEqual((yield dut.stream.last),  1)

        # two cycles to load the next packet
        yield from self.wait_for_next_packet()

        # the third packet contains a single space, so it should
        # have both first and last flags set
        yield
        self.assertEqual((yield dut.stream.payload), ord(' '))
        self.assertEqual((yield dut.stream.first), 1)
        self.assertEqual((yield dut.stream.last),  1)

        # two cycles to load the next packet
        yield from self.wait_for_next_packet()

        # now we should see the fourth packet
        for i in 'nMigen-':
            yield
            self.assertEqual((yield dut.stream.payload), ord(i))
            if i == 'd':
                self.assertEqual((yield dut.stream.first), 1)
                self.assertEqual((yield dut.stream.last),  0)
            if i == '-':
                self.assertEqual((yield dut.stream.first), 0)
                self.assertEqual((yield dut.stream.last),  1)


        # two cycles to load the next packet
        yield from self.wait_for_next_packet()

        # the fifth packet contains a single dash, so it should
        # have both first and last flags set
        yield
        self.assertEqual((yield dut.stream.payload), ord('-'))
        self.assertEqual((yield dut.stream.first), 1)
        self.assertEqual((yield dut.stream.last),  1)

        # two cycles to load the next packet
        yield from self.wait_for_next_packet()

        # now we should see the sixth packet
        for i in 'users!':
            yield
            self.assertEqual((yield dut.stream.payload), ord(i))
            if i == 'u':
                self.assertEqual((yield dut.stream.first), 1)
                self.assertEqual((yield dut.stream.last),  0)
            if i == '!':
                self.assertEqual((yield dut.stream.first), 0)
                self.assertEqual((yield dut.stream.last),  1)

        # After the last datum, we should see valid drop to '0'.
        yield
        self.assertEqual((yield dut.stream.valid), 0)
        self.assertEqual((yield dut.done),         1)
        yield from self.pulse(dut.start)
        self.assertEqual((yield dut.stream.valid),   1)
        self.assertEqual((yield dut.stream.payload), ord('H'))
        self.assertEqual((yield dut.stream.first),   1)
        yield
        yield