# unofficial-amaranth-library
THE unofficial library of utility cores for amaranth HDL.

This library is in active development, therefore beware that things
may break!

This library contains:

**unofficial_amaranth_library.io**
: Basic communication cores:
  * UART
  * I2C
  * I2S (currently transmit only)
  * SPI
  * MAX7219 SPI LED array driver core
  * neopixel (WS2812) RGB led strip driver core

**unofficial_amaranth_library.dsp**
: Building blocks for digital signal processing:
  * fixed point FIR filter
  * fixed point IIR filter
  * fixed point CIC filter
  * fixed point halfband filter
  * filterbank
  * fractional resampler

**unofficial_amaranth_library.soc**
: Building blocks for SOC creation:
  * CPU
  * interrupts
  * memory
  * wishbone
  * CSRs
  * SimpleSOC
  * peripherals

**unofficial_amaranth_library.stream**
* LiteX like streams
* stream generators from ROM
* stream to I2C
* stream to/from FIFO
* stream arbiter
* stream to UART

**unofficial_amaranth_library.debug**
: Internal logic analyzer (ILA)

**unofficial_amaranth_library.test**
: Convenience tools for automated testing of simulations, CRC

**unofficial_amaranth_library.utils**
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
