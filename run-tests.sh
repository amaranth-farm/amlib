#!/bin/bash

export GENERATE_VCDS=1

python3 -m unittest nmigen_library.debug.ila.IntegratedLogicAnalyzerTest

python3 -m unittest nmigen_library.io.spi.SPIGatewareTestCase
python3 -m unittest nmigen_library.io.i2s.I2STransmitterTest
python3 -m unittest nmigen_library.io.i2s.I2SLoopbackTest

python3 -m unittest nmigen_library.stream.i2c.I2CStreamTransmitterTest
python3 -m unittest nmigen_library.stream.uart.UARTTransmitterTest
python3 -m unittest nmigen_library.stream.uart.UARTMultibyteTransmitterTest
python3 -m unittest nmigen_library.stream.generator.ConstantStreamGeneratorTest
python3 -m unittest nmigen_library.stream.generator.ConstantStreamGeneratorWideTest
python3 -m unittest nmigen_library.stream.generator.PacketListStreamerTest

python3 -m unittest nmigen_library.utils.shiftregister.InputShiftRegisterTest
python3 -m unittest nmigen_library.utils.shiftregister.OutputShiftRegisterTest
python3 -m unittest nmigen_library.utils.cdc.StrobeStretcherTest
python3 -m unittest nmigen_library.utils.dividingcounter.DividingCounterTest
python3 -m unittest nmigen_library.utils.edgetopulse.EdgeToPulseTest
python3 -m unittest nmigen_library.utils.timer.TimerTest

