#!/bin/bash

export GENERATE_VCDS=1

python3 -m unittest an_amaranth_lib.debug.ila.IntegratedLogicAnalyzerBasicTest
python3 -m unittest an_amaranth_lib.debug.ila.IntegratedLogicAnalyzerPretriggerTest

python3 -m unittest an_amaranth_lib.io.spi.SPIControllerInterfaceTest
python3 -m unittest an_amaranth_lib.io.spi.SPIDeviceInterfaceTest
python3 -m unittest an_amaranth_lib.io.spi.SPIRegisterInterfaceTest
python3 -m unittest an_amaranth_lib.io.i2s.I2STransmitterTest
python3 -m unittest an_amaranth_lib.io.i2s.I2SLoopbackTest

python3 -m unittest an_amaranth_lib.dsp.fixedpointfirfilter.FixedPointFIRFilterTest
python3 -m unittest an_amaranth_lib.dsp.fixedpointiirfilter.FixedPointIIRFilterTest
python3 -m unittest an_amaranth_lib.dsp.resampler.ResamplerTestFIR
python3 -m unittest an_amaranth_lib.dsp.resampler.ResamplerTestIIR

python3 -m unittest an_amaranth_lib.stream.i2c.I2CStreamTransmitterTest
python3 -m unittest an_amaranth_lib.stream.uart.UARTTransmitterTest
python3 -m unittest an_amaranth_lib.stream.uart.UARTMultibyteTransmitterTest
python3 -m unittest an_amaranth_lib.stream.generator.ConstantStreamGeneratorTest
python3 -m unittest an_amaranth_lib.stream.generator.ConstantStreamGeneratorWideTest
python3 -m unittest an_amaranth_lib.stream.generator.PacketListStreamerTest

python3 -m unittest an_amaranth_lib.utils.shiftregister.InputShiftRegisterTest
python3 -m unittest an_amaranth_lib.utils.shiftregister.OutputShiftRegisterTest
python3 -m unittest an_amaranth_lib.utils.cdc.StrobeStretcherTest
python3 -m unittest an_amaranth_lib.utils.dividingcounter.DividingCounterTest
python3 -m unittest an_amaranth_lib.utils.edgetopulse.EdgeToPulseTest
python3 -m unittest an_amaranth_lib.utils.timer.TimerTest
python3 -m unittest an_amaranth_lib.utils.fifo.TransactionalizedFIFOTest

