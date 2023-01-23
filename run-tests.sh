#!/bin/bash

export GENERATE_VCDS=1

python3 -m unittest amlib.debug.ila.IntegratedLogicAnalyzerBasicTest
python3 -m unittest amlib.debug.ila.IntegratedLogicAnalyzerPretriggerTest
python3 -m unittest amlib.debug.ila.StreamILATest

python3 -m unittest amlib.io.spi.SPIControllerInterfaceTest
python3 -m unittest amlib.io.spi.SPIDeviceInterfaceTest
python3 -m unittest amlib.io.spi.SPIRegisterInterfaceTest
python3 -m unittest amlib.io.i2s.I2STransmitterTest
python3 -m unittest amlib.io.i2s.I2SLoopbackTest
python3 -m unittest amlib.io.max7219.SerialLEDArrayTest
python3 -m unittest amlib.io.led.NumberToBitBarTest

python3 -m unittest amlib.dsp.fixedpointfirfilter.FixedPointFIRFilterTest
python3 -m unittest amlib.dsp.fixedpointiirfilter.FixedPointIIRFilterTest
python3 -m unittest amlib.dsp.fixedpointhbfilter.FixedPointHBFilterTest
python3 -m unittest amlib.dsp.fixedpointcicfilter.FixedPointCICFilterTest
python3 -m unittest amlib.dsp.fixedpointfft.FixedPointFFTTest
python3 -m unittest amlib.dsp.resampler.ResamplerTestFIR
python3 -m unittest amlib.dsp.resampler.ResamplerTestIIR

python3 -m unittest amlib.stream.i2c.I2CStreamTransmitterTest
python3 -m unittest amlib.stream.uart.UARTTransmitterTest
python3 -m unittest amlib.stream.uart.UARTMultibyteTransmitterTest
python3 -m unittest amlib.stream.generator.ConstantStreamGeneratorTest
python3 -m unittest amlib.stream.generator.ConstantStreamGeneratorWideTest
python3 -m unittest amlib.stream.generator.PacketListStreamerTest

python3 -m unittest amlib.utils.shiftregister.InputShiftRegisterTest
python3 -m unittest amlib.utils.shiftregister.OutputShiftRegisterTest
python3 -m unittest amlib.utils.cdc.StrobeStretcherTest
python3 -m unittest amlib.utils.dividingcounter.DividingCounterTest
python3 -m unittest amlib.utils.edgetopulse.EdgeToPulseTest
python3 -m unittest amlib.utils.timer.TimerTest
python3 -m unittest amlib.utils.fifo.TransactionalizedFIFOTest

