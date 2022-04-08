#!/usr/bin/env python3
#
# Copyright (c) 2022 Rouven Broszeit <roubro1991@gmx.de>
# SPDX-License-Identifier: CERN-OHL-W-2.0

from amaranth import Elaboratable, Module, Signal, Array, Memory, signed, Cat, Mux
from amaranth.sim import Tick
from amlib.stream import StreamInterface
from amlib.test import GatewareTestCase, sync_test_case

import numpy as np
import math
from enum import Enum

class ConvolutionMode(Enum):
    CROSSFEED = 1
    STEREO = 2
    MONO = 3

class StereoConvolutionMAC(Elaboratable):
    """A stereo convolution module which uses the MAC (Multiply-Accumulate) algorithm

        Parameters
        ----------
        taps : int[][]
            A two dimensional numpy array containing the stereo impulse response data: np.zeros((tapcount, 2), dtype=np.int32)

        samplerate : int
            The samplerate of the signal.

        clockfrequency : int
            The frequency of the sync domain. This is needed to evaluate how many parallel multiplications need to
            be done in order to process the data in realtime.

        bitwidth : int
            The bitwidth of the signal.

        convolutionMode : ConvolutionMode
            Either of:
            CROSSFEED (1)
                Applies the IR data as crossfeed
                Channel 1 = Channel 1 * IR-Channel1 + Channel2 * IR-Channel2
                Channel 2 = Channel 2 * IR-Channel1 + Channel1 * IR-Channel2
            STEREO (2)
                Applies each channel of the IR data to each signal channel:
                Channel 1 = Channel 1 * IR-Channel1
                Channel 2 = Channel2 * IR-Channel2
            MONO (3)
                Applies only the first IR channel two both signal channels:
                Channel 1 = Channel 1 * IR-Channel1
                Channel 2 = Channel 2 * IR-Channel1


        Attributes
        ----------
        signal_in : StreamInterface
        signal_out : StreamInterface
    """
    def __init__(self,
                 taps: [],
                 samplerate:     int=48000,
                 clockfrequency:  int=60e6,
                 bitwidth:       int=24,
                 convolutionMode: ConvolutionMode=ConvolutionMode.MONO) -> None:

        self.signal_in  = StreamInterface(name="signal_stream_in", payload_width=bitwidth)
        self.signal_out = StreamInterface(name="signal_stream_out", payload_width=bitwidth)

        self._tapcount = len(taps) #4096 synthesizes
        self._bitwidth = bitwidth
        self._convolutionMode = convolutionMode

        # in order to process more taps than we have clock cycles per sample we will run parallel calculations.
        # The number of parallel calculations per channel is defined by the "slices" variable
        self._slices = math.ceil(self._tapcount / (clockfrequency / samplerate))  # 4
        self._size_of_slizes = self._bitwidth * self._slices #how many bits per slice
        self._samples_per_slice = self._tapcount // self._slices #how many samples per slice

        print(f"Creating {self._slices} slices for {self._tapcount} taps.")

        assert self._tapcount % self._slices == 0, f"Tapcount {self._tapcount} cannot be evenly distributed on {self._slices} slizes."

        taps_fp = taps[:self._tapcount, 0]
        taps2_fp = taps[:self._tapcount, 1]

        self._taps1_memory = Memory(width=self._size_of_slizes, depth=self._samples_per_slice)
        self._taps2_memory = Memory(width=self._size_of_slizes, depth=self._samples_per_slice)
        self._samples1_memory = Memory(width=self._size_of_slizes, depth=self._samples_per_slice)
        self._samples2_memory = Memory(width=self._size_of_slizes, depth=self._samples_per_slice)

        taps_fp_mod = []
        taps2_fp_mod = []
        for i in range(0, self._tapcount, self._slices):
            val1 = 0
            val2 = 0
            for j in range(self._slices):
                val1 += int(taps_fp[i+j]) << (self._slices - j - 1) * self._bitwidth
                val2 += int(taps2_fp[i+j]) << (self._slices - j - 1) * self._bitwidth
            taps_fp_mod.append(val1)
            taps2_fp_mod.append(val2)

        self._taps1_memory.init = taps_fp_mod
        self._taps2_memory.init = taps2_fp_mod

    def elaborate(self, platform) -> Module:
        m = Module()

        taps1_read_port = self._taps1_memory.read_port()
        taps2_read_port = self._taps2_memory.read_port()
        samples1_write_port = self._samples1_memory.write_port()
        samples2_write_port = self._samples2_memory.write_port()
        samples1_read_port = self._samples1_memory.read_port()
        samples2_read_port = self._samples2_memory.read_port()

        m.submodules += [taps1_read_port, taps2_read_port, samples1_write_port, samples2_write_port, samples1_read_port, samples2_read_port]

        set1 = Signal()
        set2 = Signal()
        output_channels = Signal(2)
        ix = Signal(range(self._samples_per_slice + 1))

        previous_sample1 = Signal(self._size_of_slizes)
        previous_sample2 = Signal.like(previous_sample1)
        current_sample1 = Signal.like(previous_sample1)
        current_sample2 = Signal.like(previous_sample1)
        carryover1 = Signal(signed(self._bitwidth))
        carryover1_2 = Signal.like(carryover1)
        carryover2 = Signal.like(carryover1)
        carryover2_2 = Signal.like(carryover1)

        madd_values = Array(Signal(signed(self._bitwidth * 2), name=f"madd_values_{i}") for i in range(self._slices * 2))
        sumSignalL = Signal(signed(self._bitwidth * 2))
        sumSignalR = Signal.like(sumSignalL)

        #debugging
        #left_sample_sig = Array(Signal.like(carryover1, name=f"left_sample_sig_{i}") for i in range(self._slices))
        #right_sample_sig = Array(Signal.like(carryover1, name=f"right_sample_sig_{i}") for i in range(self._slices))
        #main_tap_sig = Array(Signal.like(carryover1, name=f"main_tap_sig_{i}") for i in range(self._slices))
        #bleed_tap_sig = Array(Signal.like(carryover1, name=f"bleed_tap_sig_{i}") for i in range(self._slices))

        m.d.comb += [
            self.signal_in.ready.eq(0),
            taps1_read_port.addr.eq(ix),
            taps2_read_port.addr.eq(ix),
            samples1_read_port.addr.eq(ix),
            samples2_read_port.addr.eq(ix),
        ]

        m.d.sync += [
            self.signal_out.valid.eq(0),
            samples1_write_port.en.eq(0),
            samples2_write_port.en.eq(0),

            previous_sample1.eq(samples1_read_port.data),
            previous_sample2.eq(samples2_read_port.data),

            carryover1.eq(samples1_read_port.data[:self._bitwidth]),
            carryover1_2.eq(carryover1),
            carryover2.eq(samples2_read_port.data[:self._bitwidth]),
            carryover2_2.eq(carryover2),
        ]

        with m.FSM(reset="IDLE"):
            with m.State("IDLE"):
                # store new sample for left channel
                with m.If(self.signal_in.valid & self.signal_in.first & ~set1):
                    sample1_value = Cat(
                        samples1_read_port.data[:-self._bitwidth],
                        self.signal_in.payload.as_signed()
                    )

                    m.d.sync += [
                        samples1_write_port.data.eq(sample1_value),
                        samples1_write_port.addr.eq(0),
                        samples1_write_port.en.eq(1),
                        set1.eq(1),
                    ]

                # store new sample for right channel
                with m.Elif(self.signal_in.valid & self.signal_in.last & ~set2):
                    sample2_value = Cat(
                        samples2_read_port.data[:-self._bitwidth],
                        self.signal_in.payload.as_signed()
                    )
                    m.d.sync += [
                        samples2_write_port.data.eq(sample2_value),
                        samples2_write_port.addr.eq(0),
                        samples2_write_port.en.eq(1),
                        set2.eq(1),
                    ]

                # prepare MAC calculations
                with m.If(set1 & set2):
                    for i in range(self._slices * 2):
                        m.d.sync += [
                            ix.eq(0),
                            madd_values[i].eq(0),
                            previous_sample1.eq(0),
                            previous_sample2.eq(0),
                            current_sample1.eq(0),
                            current_sample2.eq(0),
                            carryover1.eq(0),
                            carryover1_2.eq(0),
                            carryover2.eq(0),
                            carryover2_2.eq(0),
                        ]

                    m.next = "MAC"
                with m.Else():
                    m.d.comb += self.signal_in.ready.eq(1)
            with m.State("MAC"):
                # do the actual MAC calculation
                with m.If(ix <= self._samples_per_slice):
                    with m.If(ix > 0):
                        for i in range(self._slices):
                            left_sample = samples1_read_port.data[i*self._bitwidth:(i + 1) * self._bitwidth].as_signed()
                            right_sample = samples2_read_port.data[i*self._bitwidth:(i + 1) * self._bitwidth].as_signed()
                            main_tap = taps1_read_port.data[i*self._bitwidth:(i + 1) * self._bitwidth].as_signed()
                            bleed_tap = taps2_read_port.data[i*self._bitwidth:(i + 1) * self._bitwidth].as_signed()

                            #debugging
                            #m.d.sync += [
                            #    left_sample_sig[i].eq(left_sample),
                            #    right_sample_sig[i].eq(right_sample),
                            #    main_tap_sig[i].eq(main_tap),
                            #    bleed_tap_sig[i].eq(bleed_tap),
                            #]

                            if self._convolutionMode == ConvolutionMode.CROSSFEED:
                                m.d.sync += [
                                    madd_values[i].eq(madd_values[i] + (left_sample * main_tap)
                                                    + (right_sample * bleed_tap)),
                                    madd_values[i + self._slices].eq(madd_values[i + self._slices] + (right_sample * main_tap)
                                                                     + (left_sample * bleed_tap))
                                ]
                            elif self._convolutionMode == ConvolutionMode.STEREO:
                                m.d.sync += [
                                    madd_values[i].eq(madd_values[i] + (left_sample * main_tap)),
                                    madd_values[i + self._slices].eq(madd_values[i + self._slices] + (right_sample * bleed_tap)),
                                ]
                            elif self._convolutionMode == ConvolutionMode.MONO:
                                m.d.sync += [
                                    madd_values[i].eq(madd_values[i] + (left_sample * main_tap)),
                                    madd_values[i + self._slices].eq(madd_values[i + self._slices] + (right_sample * main_tap)),
                                ]

                # shift the samples buffer by one sample to prepare for the next arriving sample in the IDLE state
                with m.If(ix > 1):
                    m.d.sync += [
                        samples1_write_port.data.eq(Cat((previous_sample1 >> self._bitwidth)[:((self._slices - 1) * self._bitwidth)], carryover1_2)),
                        samples1_write_port.addr.eq(ix - 2),
                        samples1_write_port.en.eq(1),

                        samples2_write_port.data.eq(Cat((previous_sample2 >> self._bitwidth)[:((self._slices - 1) * self._bitwidth)], carryover2_2)),
                        samples2_write_port.addr.eq(ix - 2),
                        samples2_write_port.en.eq(1),
                    ]

                with m.If(ix == self._samples_per_slice + 1):
                    m.next = "SUM"
                with m.Else():
                    m.d.sync += ix.eq(ix+1)

            with m.State("SUM"):
                sumL = 0
                sumR = 0
                for i in range(self._slices):
                    sumL += madd_values[i]
                    sumR += madd_values[i + self._slices]

                m.d.sync += [
                    sumSignalL.eq(sumL),
                    sumSignalR.eq(sumR),
                    output_channels.eq(0),
                ]
                m.next = "OUTPUT"
            with m.State("OUTPUT"):
                m.d.sync += [
                    set1.eq(0),
                    set2.eq(0),
                    ix.eq(0),
                ]

                with m.If(output_channels == 2):
                    m.next = "IDLE"
                with m.Elif(self.signal_out.ready):
                    m.d.sync += [
                        output_channels.eq(output_channels + 1),
                        self.signal_out.payload.eq(Mux(output_channels == 0, sumSignalL >> self._bitwidth, sumSignalR >> self._bitwidth)),
                        self.signal_out.valid.eq(1),
                        self.signal_out.first.eq(~output_channels),
                        self.signal_out.last.eq(output_channels),
                    ]

        return m


class StereoConvolutionMACTest(GatewareTestCase):
    FRAGMENT_UNDER_TEST = StereoConvolutionMAC
    testSamplecount = 120
    tapcount = 32
    bitwidth = 24
    samplerate = 48000
    clockfrequency = samplerate * tapcount / 4 # we want to test for 4 slices

    #some test IR-data
    #tapdata1 = [5033163, 4194303, 2097151,  838859] # [0.6, 0.5, 0.25, 0.1] * 2 ** (bitwidth-1)-1
    #tapdata2 = [419429, 209714,  83885, 167771] #[0.05, 0.025, 0.01, 0.02] * 2 ** (bitwidth-1)-1
    tapdata1 = [
        8388607, 8388607, -8388608, 7805659, -777420, -2651895, 1181562, -3751702,
        2024355, -1085865, 1194588, -341596, -138844, -133784, -204981, 33373,
        -636104, -988353, -1313180, -851631, -160023, 370339, 391865, 22927,
        -288476, -281780, 6684, 241364, 174375, -151480, -496185, -655125
    ]
    tapdata2 = [
        7881750, 7461102, -1293164, 2060193, 2268606, 1214028, 225034, -1235788,
        486778, 501926, 466836, -94304, 191358, 533261, 402351, 185156,
        111725, 264777, 243255, 136264, 111589, 216495, 296642, 274774,
        243960, 263830, 298115, 283377, 232100, 182950, 140385, 87647
    ]

    taps = np.zeros((tapcount, 2), dtype=np.int32)
    for i in range(len(tapdata1)):
        taps[i, 0] = int(tapdata1[i])
        taps[i, 1] = int(tapdata2[i])

    convolutionMode = ConvolutionMode.CROSSFEED
    FRAGMENT_ARGUMENTS = dict(taps=taps, samplerate=48000, clockfrequency=clockfrequency, bitwidth=bitwidth, convolutionMode=convolutionMode)

    def wait(self, n_cycles: int):
        for _ in range(n_cycles):
            yield Tick()

    def wait_ready(self, dut):
        yield dut.signal_in.valid.eq(0)
        while (yield dut.signal_in.ready == 0):
            yield from self.wait(1)

    def get_output(self, dut, out_signal):
        while (yield dut.signal_out.valid == 0):
            yield from self.wait(1)

        payload = yield dut.signal_out.payload
        out_signal.append(int.from_bytes(payload.to_bytes(3, 'little', signed=False), 'little', signed=True))  # parse 24bit signed
        yield Tick()
        payload = yield dut.signal_out.payload
        out_signal.append(int.from_bytes(payload.to_bytes(3, 'little', signed=False), 'little', signed=True))  # parse 24bit signed


    def calculate_expected_result(self, taps, testdata, convolutionMode):
        output = np.zeros((len(testdata),2), dtype=np.int32)
        for sample in range(len(testdata)):
            sumL = 0
            sumR = 0
            for tap in range(len(taps)):
                if tap > sample:
                    break
                if convolutionMode == ConvolutionMode.CROSSFEED:
                    sumL += int(testdata[sample - tap, 0]) * int(taps[tap, 0]) + int(testdata[sample - tap, 1]) * int(taps[tap, 1])
                    sumR += int(testdata[sample - tap, 1]) * int(taps[tap, 0]) + int(testdata[sample - tap, 0]) * int(taps[tap, 1])
                elif convolutionMode == ConvolutionMode.STEREO:
                    sumL += int(testdata[sample - tap, 0]) * int(taps[tap, 0])
                    sumR += int(testdata[sample - tap, 1]) * int(taps[tap, 1])
                elif convolutionMode == ConvolutionMode.MONO:
                    sumL += int(testdata[sample - tap, 0]) * int(taps[tap, 0])
                    sumR += int(testdata[sample - tap, 1]) * int(taps[tap, 0])

            output[sample, 0] = sumL >> self.bitwidth
            output[sample, 1] = sumR >> self.bitwidth

        return output

    @sync_test_case
    def test_fir(self):
        dut = self.dut
        max = int(2**(self.bitwidth-1) - 1)
        min = -max

        testdata_raw = [[812420, 187705], [800807, 152271], [788403, 109422], [789994, 65769], [773819, 12803],
                    [747336, -40589], [744825, -84371], [729641, -141286], [706089, -190230], [687227, -238741],
                    [674577, -293106], [679382, -354421], [673939, -404084], [670470, -448995], [698245, -493213],
                    [727041, -527915], [749620, -566963], [777583, -578647], [793651, -596892], [807524, -608824],
                    [819352, -600195], [813153, -594125], [811380, -574884], [804773, -549522], [803946, -519619],
                    [798627, -484158], [795990, -457567], [784727, -441965], [781253, -423321], [772247, -406696],
                    [737346, -396969], [727344, -397146], [709987, -398310], [691059, -397030], [657034, -408094],
                    [626680, -421474], [602569, -440591], [568337, -465274], [542343, -489621], [503093, -522351],
                    [449579, -560565], [379701, -601463], [310374, -645896], [224866, -689011], [131545, -735663],
                    [16957, -783650], [-111726, -827044], [-241836, -883122], [-370953, -935652], [-485623, -981734],
                    [-583078, -1036719], [-654543, -1084068], [-710559, -1134423], [-733894, -1178457],
                    [-741472, -1222978], [-730563, -1261715], [-713004, -1283693], [-695040, -1300765],
                    [-669049, -1313577], [-656220, -1333732], [-651277, -1349524], [-657046, -1361661],
                    [-666656, -1369770], [-663344, -1368362], [-667356, -1376221], [-675844, -1380697],
                    [-675575, -1378351], [-670833, -1370430], [-663705, -1343927], [-654934, -1325950],
                    [-630174, -1292244], [-601587, -1244248], [-586781, -1199700], [-577894, -1134632],
                    [-576851, -1061743], [-593347, -977451], [-603222, -883179], [-606804, -777615], [-602340, -671055],
                    [-602439, -575690], [-581846, -480232], [-563534, -413668], [-547941, -360161], [-519823, -314832],
                    [-491941, -277750], [-458161, -247667], [-421273, -221640], [-391277, -193937], [-373996, -167258],
                    [-369452, -141699], [-398689, -124104], [-429195, -104058], [-483597, -90449], [-534715, -76876],
                    [-580318, -75685], [-629828, -68031], [-662375, -69266], [-688125, -77877],
                    [-696417, -84852], [-706783, -99115], [-709124, -115825], [-694132, -152064], [-670392, -183572],
                    [-650166, -220606], [-600539, -254463], [-557703, -287120], [-512840, -317225], [-459318, -333891],
                    [-435701, -348684], [-404251, -355299], [-390665, -352357], [-376465, -343641], [-378383, -344794],
                    [-369697, -338782], [-362845, -332500], [-351513, -319435], [-321284, -298249], [-301254, -274747],
                    [-256613, -242747], [-208538, -203862]]

        testdata = np.zeros((self.testSamplecount, 2))
        for i in range(len(testdata_raw)):
            testdata[i, 0] = testdata_raw[i][0]
            testdata[i, 1] = testdata_raw[i][1]

        yield dut.signal_out.ready.eq(1)

        out_signal = []

        for i in range(len(testdata)):
            yield Tick()
            yield dut.signal_in.first.eq(1)
            yield dut.signal_in.last.eq(0)
            yield dut.signal_in.payload.eq(int(testdata[i, 0]))
            yield dut.signal_in.valid.eq(1)
            yield Tick()
            yield dut.signal_in.valid.eq(1)
            yield dut.signal_in.first.eq(0)
            yield dut.signal_in.last.eq(1)
            yield dut.signal_in.payload.eq(int(testdata[i, 1]))
            yield Tick()
            yield from self.wait_ready(dut)
            yield from self.get_output(dut, out_signal)

        expected_result = self.calculate_expected_result(self.taps, testdata, self.convolutionMode)
        print(f"Length of expected data: {len(expected_result)}")
        print(f"Expected data: {expected_result}")

        print(f"Length of received data: {len(out_signal)/2}")
        print(f"Received data: {out_signal}")

        for i in range(len(expected_result)):
            assert out_signal[i*2] - 2 <= expected_result[i, 0] <= out_signal[i*2] + 2, f"counter was: {i}"
            assert out_signal[i * 2+1] - 2 <= expected_result[i, 1] <= out_signal[i * 2+1] + 2, f"counter was: {i}"
