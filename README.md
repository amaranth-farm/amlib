# an-amaranth-lib
Assorted library of utility cores for amaranth HDL.

This library is in active development, therefore beware that things
may break!

This library contains:

**an_amaranth_lib.io**
: Basic communication cores:
  * UART
  * I2C
  * I2S (currently transmit only)
  * SPI
  * MAX7219 SPI LED array driver core
  * neopixel (WS2812) RGB led strip driver core

**an_amaranth_lib.dsp**
: Building blocks for digital signal processing:
  * fixed point FIR filter
  * fixed point IIR filter
  * fixed point CIC filter
  * fixed point halfband filter
  * filterbank
  * fractional resampler

**an_amaranth_lib.soc**
: Building blocks for SOC creation:
  * CPU
  * interrupts
  * memory
  * wishbone
  * CSRs
  * SimpleSOC
  * peripherals

**an_amaranth_lib.stream**
* LiteX like streams
* stream generators from ROM
* stream to I2C
* stream to/from FIFO
* stream arbiter
* stream to UART

**an_amaranth_lib.debug**
: Internal logic analyzer (ILA)

**an_amaranth_lib.test**
: Convenience tools for automated testing of simulations, CRC

**an_amaranth_lib.utils**
: basic utility modules:
  * bit manipulation functions
  * one-hot-multiplexer
  * synchronizer
  * strobe stretcher
  * dividing counter
  * edge to pulse
  * edge detectors
  * linear feedback shift register (LFSR)
  * NRZI encoder
  * shift register
