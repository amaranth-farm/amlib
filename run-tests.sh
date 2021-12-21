#!/bin/bash

export GENERATE_VCDS=1

python3 -m unittest amaranth_library.debug.ila.IntegratedLogicAnalyzerBasicTest
python3 -m unittest amaranth_library.debug.ila.IntegratedLogicAnalyzerPretriggerTest

python3 -m unittest amaranth_library.io.spi.SPIControllerInterfaceTest
python3 -m unittest amaranth_library.io.spi.SPIDeviceInterfaceTest
python3 -m unittest amaranth_library.io.spi.SPIRegisterInterfaceTest
python3 -m unittest amaranth_library.io.i2s.I2STransmitterTest
python3 -m unittest amaranth_library.io.i2s.I2SLoopbackTest

python3 -m unittest amaranth_library.dsp.fixedpointfirfilter.FixedPointFIRFilterTest
python3 -m unittest amaranth_library.dsp.fixedpointiirfilter.FixedPointIIRFilterTest
python3 -m unittest amaranth_library.dsp.resampler.ResamplerTestFIR
python3 -m unittest amaranth_library.dsp.resampler.ResamplerTestIIR

python3 -m unittest amaranth_library.stream.i2c.I2CStreamTransmitterTest
python3 -m unittest amaranth_library.stream.uart.UARTTransmitterTest
python3 -m unittest amaranth_library.stream.uart.UARTMultibyteTransmitterTest
python3 -m unittest amaranth_library.stream.generator.ConstantStreamGeneratorTest
python3 -m unittest amaranth_library.stream.generator.ConstantStreamGeneratorWideTest
python3 -m unittest amaranth_library.stream.generator.PacketListStreamerTest

python3 -m unittest amaranth_library.utils.shiftregister.InputShiftRegisterTest
python3 -m unittest amaranth_library.utils.shiftregister.OutputShiftRegisterTest
python3 -m unittest amaranth_library.utils.cdc.StrobeStretcherTest
python3 -m unittest amaranth_library.utils.dividingcounter.DividingCounterTest
python3 -m unittest amaranth_library.utils.edgetopulse.EdgeToPulseTest
python3 -m unittest amaranth_library.utils.timer.TimerTest
python3 -m unittest amaranth_library.utils.fifo.TransactionalizedFIFOTest

