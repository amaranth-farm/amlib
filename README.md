# nmigen-library
standard library of utility cores for nmigen
This library is in active development, therefore beware that things
may break!

This library contains:

**nmigen_library.io**
: Basic communication cores:
  * UART
  * I2C
  * SPI

**nmigen_library.soc**
: Building blocks for SOC creation:
  * CPU
  * interrupts
  * memory
  * wishbone
  * CSRs
  * SimpleSOC
  * peripherals

**nmigen_library.stream**
* LiteX like streams
* stream generators from ROM
* stream to I2C
* stream to/from FIFO
* stream arbiter
* stream to UART

**nmigen_library.debug**
: Internal logic analyzer (ILA)

**nmigen_library.test**
: Convenience tools for automated testing of simulations, CRC

**nmigen_library.utils**
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
