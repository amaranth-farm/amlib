# amlib
Assorted library of utility cores for amaranth HDL.

This library is in active development, therefore beware that things
may break!

This library contains:

**amlib.io**
: Basic communication cores:
  * UART
  * I2C
  * I2S (currently transmit only)
  * SPI
  * MAX7219 SPI LED array driver core
  * seven segment driver, value to bitbar driver
  * neopixel (WS2812) RGB led strip driver core
  * Debouncer for debouncing button inputs

**amlib.dsp**
: Building blocks for digital signal processing:
  * fixed point FIR filter
  * fixed point IIR filter
  * fixed point CIC filter
  * fixed point halfband filter
  * fixed point FFT
  * filterbank
  * fractional resampler

**amlib.dsp.convolution**
: Convolution cores:
  * mac: A convolution core which uses parallel multiply-accumulate (MAC) calculation. 
    This introduces a latency of only one sample. For longer impulse responses it will consume several hardware
    multipliers for calculations.

**amlib.soc**
: Building blocks for SOC creation:
  * CPU
  * interrupts
  * memory
  * wishbone
  * CSRs
  * SimpleSOC
  * peripherals

**amlib.stream**
* LiteX like streams
* stream generators from ROM
* stream to I2C
* stream to/from FIFO
* stream arbiter
* stream to UART

**amlib.debug**
: Internal logic analyzer (ILA)

**amlib.test**
: Convenience tools for automated testing of simulations, CRC

**amlib.utils**
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
