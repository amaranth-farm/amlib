from amaranth import Signal, Elaboratable, Module

class Debouncer(Elaboratable):
	"""A debouncer for buttons or other unstable signals.
		Obtained from:
		https://github.com/lawrie/blackicemx_nmigen_examples

		Attributes
		----------
		btn_in: Signal()
			The signal to be debounced.

        btn_state_out:  ignal()
        	The current state of the button.

        btn_down_out: Signal()
        	Strobed when the button is pressed.

        btn_up_out    = Signal()
        	Strobed when the button is released.


		Usage example
		-------------
		led  = platform.request("led", 0)
		btn = platform.request("button", 0)
		m = Module()
		m.submodules.debouncer = debouncer = Debouncer()
		m.d.comb += debouncer.btn_in.eq(btn)

		with m.If(debouncer.btn_up_out):
			m.d.sync += led.eq(~led) # toggle led
    """
	def __init__(self):
		self.btn_in       = Signal()
		self.btn_state_out = Signal(reset=0)
		self.btn_down_out  = Signal()
		self.btn_up_out    = Signal()

	def elaborate(self, platform):
		cnt      = Signal(15, reset=0)
		btn_sync = Signal(2,  reset=0)
		idle     = Signal()
		cnt_max  = Signal()

		m = Module()

		m.d.comb += [
			idle.eq(self.btn_state_out == btn_sync[1]),
			cnt_max.eq(cnt.all()),
			self.btn_down_out.eq(~idle & cnt_max & ~self.btn_state_out),
			self.btn_up_out.eq(~idle & cnt_max & self.btn_state_out)
		]

		m.d.sync += [
			btn_sync[0].eq(~self.btn_in),
			btn_sync[1].eq(btn_sync[0])
		]

		with m.If(idle):
			m.d.sync += cnt.eq(0)
		with m.Else():
			m.d.sync += cnt.eq(cnt + 1);
			with m.If(cnt_max):
				m.d.sync += self.btn_state_out.eq(~self.btn_state_out)

		return m
