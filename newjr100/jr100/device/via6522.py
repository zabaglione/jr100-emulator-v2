"""JR-100 specific VIA (R6522) device (JR-100 oriented port)."""

from __future__ import annotations

from typing import Callable, Dict, Optional

FontCallback = Callable[[bool], None]
BuzzerCallback = Callable[[bool, float], None]

# Register offsets (matching the Java implementation)
REG_IORB = 0x00
REG_IORA = 0x01
REG_DDRB = 0x02
REG_DDRA = 0x03
REG_T1CL = 0x04
REG_T1CH = 0x05
REG_T1LL = 0x06
REG_T1LH = 0x07
REG_T2CL = 0x08
REG_T2CH = 0x09
REG_SR = 0x0A
REG_ACR = 0x0B
REG_PCR = 0x0C
REG_IFR = 0x0D
REG_IER = 0x0E
REG_IORANH = 0x0F

# Interrupt flag bits
IFR_BIT_CA2 = 0x01
IFR_BIT_CA1 = 0x02
IFR_BIT_SR = 0x04
IFR_BIT_CB2 = 0x08
IFR_BIT_CB1 = 0x10
IFR_BIT_T2 = 0x20
IFR_BIT_T1 = 0x40
IFR_BIT_IRQ = 0x80

# Port bit masks
PB5_MASK = 0x20
PB6_MASK = 0x40
PB7_MASK = 0x80
KEY_INPUT_MASK = 0x1F

DEFAULT_ORB = KEY_INPUT_MASK | PB5_MASK  # inputs idle high, CMODE asserted
DEFAULT_IRB = DEFAULT_ORB


class Via6522:
    """Python port of JR-100R6522 with a reduced but faithful feature set."""

    def __init__(
        self,
        start: int,
        keyboard,
        cpu,
        *,
        clock_hz: float = 894_886.25,
        buzzer_callback: Optional[BuzzerCallback] = None,
        font_callback: Optional[FontCallback] = None,
    ) -> None:
        self._start = start
        self._end = start + 0x0F
        self._keyboard = keyboard
        self._cpu = cpu
        self._clock_hz = clock_hz
        self._buzzer_callback = buzzer_callback
        self._font_callback = font_callback

        self._keyboard.add_listener(self._handle_keyboard_event)

        self._reset_state()
        self._update_port_b_cache()

    # ------------------------------------------------------------------
    # Public helpers

    def get_start_address(self) -> int:
        return self._start

    def get_end_address(self) -> int:
        return self._end

    def tick(self, cycles: int) -> None:
        for _ in range(max(cycles, 0)):
            self._step_cycle()

    def debug_snapshot(self) -> Dict[str, int]:
        return {
            "ORB": self._ORB,
            "IRB": self._IRB,
            "DDRB": self._DDRB,
            "ACR": self._ACR,
            "PCR": self._PCR,
            "IFR": self._IFR,
            "IER": self._IER,
            "PB6": 1 if (self._port_b_cache & PB6_MASK) else 0,
            "PB7": 1 if (self._port_b_cache & PB7_MASK) else 0,
            "CA1": self._ca1_in,
            "CB1_IN": self._cb1_in,
            "CB2_IN": self._cb2_in,
            "CB2_OUT": self._cb2_out,
            "CA2": self._ca2_out,
            "timer1": self._timer1 & 0xFFFF,
            "timer2": self._timer2 & 0xFFFF,
        }

    # ------------------------------------------------------------------
    # Memory mapped interface

    def load8(self, address: int) -> int:
        offset = address - self._start

        if offset == REG_IORB:
            if (self._ACR & 0x02) == 0:
                value = self._read_port_b()
            else:
                value = self._IRB
            self._clear_interrupt(IFR_BIT_CB1 | (0x00 if (self._PCR & 0xA0) == 0x20 else IFR_BIT_CB2))
            return value
        if offset == REG_IORA:
            value = self._IRA if (self._ACR & 0x01) else self._read_port_a()
            self._clear_interrupt(IFR_BIT_CA1 | (0x00 if (self._PCR & 0x0A) == 0x02 else IFR_BIT_CA2))
            if (self._ca2_out == 1) and (((self._PCR & 0x0E) == 0x0A) or ((self._PCR & 0x0E) == 0x08)):
                self._set_ca2_output(0)
                self._ca2_timer = 1
            return value
        if offset == REG_DDRB:
            return self._DDRB
        if offset == REG_DDRA:
            return self._DDRA
        if offset == REG_T1CL:
            self._clear_interrupt(IFR_BIT_T1)
            return self._timer1 & 0xFF
        if offset == REG_T1CH:
            return (self._timer1 >> 8) & 0xFF
        if offset == REG_T1LL:
            return self._latch1 & 0xFF
        if offset == REG_T1LH:
            return (self._latch1 >> 8) & 0xFF
        if offset == REG_T2CL:
            self._clear_interrupt(IFR_BIT_T2)
            return self._timer2 & 0xFF
        if offset == REG_T2CH:
            return (self._timer2 >> 8) & 0xFF
        if offset == REG_SR:
            return self._SR
        if offset == REG_ACR:
            return self._ACR
        if offset == REG_PCR:
            return self._PCR
        if offset == REG_IFR:
            return self._IFR
        if offset == REG_IER:
            return self._IER | 0x80
        if offset == REG_IORANH:
            return self._IRA if (self._ACR & 0x01) else self._read_port_a()
        return 0x00

    def store8(self, address: int, value: int) -> None:
        offset = address - self._start
        value &= 0xFF

        if offset == REG_IORB:
            self._ORB = value
            self._output_port_b()
            self._clear_interrupt(IFR_BIT_CB1 | (0x00 if (self._PCR & 0xA0) == 0x20 else IFR_BIT_CB2))
            if (self._cb2_out == 1) and ((self._PCR & 0xC0) == 0x80):
                self._set_cb2_output(0)
            self._handle_store_orb()
        elif offset == REG_IORA:
            self._ORA = value
            if self._DDRA != 0:
                self._output_port_a()
            self._clear_interrupt(IFR_BIT_CA1 | (0x00 if (self._PCR & 0x0A) == 0x02 else IFR_BIT_CA2))
            if (self._ca2_out == 1) and (((self._PCR & 0x0E) == 0x0A) or ((self._PCR & 0x0C) == 0x08)):
                self._set_ca2_output(0)
            if (self._PCR & 0x0E) in (0x0A, 0x08):
                self._ca2_timer = 1
            self._handle_store_iora()
        elif offset == REG_DDRB:
            self._DDRB = value
            self._update_port_b_cache()
            self._handle_store_ddrb()
        elif offset == REG_DDRA:
            self._DDRA = value
            self._handle_store_ddra()
        elif offset == REG_T1CL:
            self._latch1 = (self._latch1 & 0xFF00) | value
        elif offset == REG_T1CH:
            self._latch1 = (self._latch1 & 0x00FF) | (value << 8)
            self._timer1 = self._latch1
            self._timer1_initialized = True
            self._timer1_enable = True
            self._set_port_b_bit(7, 0)
            self._handle_store_t1ch()
        elif offset == REG_T1LL:
            self._latch1 = (self._latch1 & 0xFF00) | value
        elif offset == REG_T1LH:
            self._latch1 = (self._latch1 & 0x00FF) | (value << 8)
        elif offset == REG_T2CL:
            self._latch2 = (self._latch2 & 0xFF00) | value
        elif offset == REG_T2CH:
            self._latch2 = (self._latch2 & 0x00FF) | (value << 8)
            self._timer2 = self._latch2
            self._clear_interrupt(IFR_BIT_T2)
            self._timer2_initialized = True
            self._timer2_enable = True
        elif offset == REG_SR:
            self._SR = value
        elif offset == REG_ACR:
            self._ACR = value
            self._update_port_b_cache()
        elif offset == REG_PCR:
            self._PCR = value
            self._handle_store_pcr()
        elif offset == REG_IFR:
            mask = 0x7F if (value & 0x80) else value
            self._IFR &= ~mask
            self._process_irq()
        elif offset == REG_IER:
            if value & 0x80:
                self._IER |= value & 0x7F
            else:
                self._IER &= ~(value & 0x7F)
            self._process_irq()
        elif offset == REG_IORANH:
            self._ORA = value
            if self._DDRA != 0:
                self._output_port_a()
            self._handle_store_iora_nohs()

    # ------------------------------------------------------------------
    # Internal cycle emulation

    def _step_cycle(self) -> None:
        self._current_clock += 1

        if self._ca2_timer >= 0:
            self._ca2_timer -= 1
            if self._ca2_timer < 0:
                self._set_ca2_output(1)

        # Timer1 behaviour
        if self._timer1_initialized:
            self._timer1_initialized = False
        elif self._timer1 > 0:
            self._timer1 -= 1
        elif self._timer1 == 0:
            self._timer1 = -1
        else:
            if self._timer1_enable:
                self._set_interrupt(IFR_BIT_T1)
                mode = self._ACR & 0xC0
                if mode == 0x00:
                    self._timer1_enable = False
                    self._handle_timer1_timeout_mode0()
                elif mode == 0x40:
                    self._invert_port_b_bit(7)
                    self._handle_timer1_timeout_mode1()
                elif mode == 0x80:
                    self._timer1_enable = False
                    self._set_port_b_bit(7, 1)
                    self._handle_timer1_timeout_mode2()
                elif mode == 0xC0:
                    self._invert_port_b_bit(7)
                    self._handle_timer1_timeout_mode3()
            self._timer1 = self._latch1
            self._handle_store_t1ch()

        # Timer2 behaviour
        if self._timer2 >= 0:
            if (self._ACR & 0x20) == 0x00:
                if self._timer2_initialized:
                    self._timer2_initialized = False
                else:
                    self._timer2 -= 1
            else:
                current_pb6 = self._port_b_cache & PB6_MASK
                if self._previous_pb6 and not current_pb6:
                    self._timer2 -= 1
                self._previous_pb6 = current_pb6
        else:
            if self._timer2_enable:
                self._set_interrupt(IFR_BIT_T2)
                self._timer2_enable = False
            self._timer2 = self._latch2

    # ------------------------------------------------------------------
    # Port helpers

    def _read_port_b(self) -> int:
        return self._port_b_cache

    def _read_port_a(self) -> int:
        return self._IRA

    def _output_port_b(self) -> None:
        self._update_port_b_cache()

    def _output_port_a(self) -> None:
        pass

    def _set_port_b_bit(self, bit: int, state: int) -> None:
        mask = 1 << bit
        if self._DDRB & mask:
            return
        if state:
            self._port_b_state |= mask
        else:
            self._port_b_state &= ~mask
        if (self._ACR & 0x02) == 0:
            self._IRB = (self._IRB & self._DDRB) | (self._port_b_state & ~self._DDRB)
        self._update_port_b_cache()

    def _invert_port_b_bit(self, bit: int) -> None:
        mask = 1 << bit
        if self._DDRB & mask:
            return
        if self._port_b_state & mask:
            self._port_b_state &= ~mask
        else:
            self._port_b_state |= mask
        if (self._ACR & 0x02) == 0:
            self._IRB = (self._IRB & self._DDRB) | (self._port_b_state & ~self._DDRB)
        self._update_port_b_cache()

    def _update_port_b_cache(self) -> None:
        if self._DDRB & PB5_MASK:
            if self._ORB & PB5_MASK:
                self._port_b_state |= PB5_MASK
            else:
                self._port_b_state &= ~PB5_MASK
        inputs = self._port_b_state & (~self._DDRB & 0xFF)
        outputs = self._ORB & self._DDRB
        port_value = (inputs | outputs) & 0xFF
        if self._DDRB & PB5_MASK:
            if self._ORB & PB5_MASK:
                port_value |= PB5_MASK
            else:
                port_value &= ~PB5_MASK
        if port_value & PB7_MASK:
            port_value |= PB6_MASK
        else:
            port_value &= ~PB6_MASK
        if (self._ACR & 0x02) == 0:
            self._IRB = (self._IRB & self._DDRB) | (self._port_b_state & ~self._DDRB)
        self._port_b_cache = port_value & 0xFF
    # ------------------------------------------------------------------
    # Interrupt helpers

    def _set_interrupt(self, mask: int) -> None:
        if (self._IFR & mask) == 0:
            self._IFR |= mask
            self._process_irq()

    def _clear_interrupt(self, mask: int) -> None:
        if mask & IFR_BIT_IRQ:
            mask &= 0x7F
        if (self._IFR & mask) != 0:
            self._IFR &= ~mask
            self._process_irq()

    def _process_irq(self) -> None:
        if (self._IER & self._IFR & 0x7F) != 0:
            if (self._IFR & IFR_BIT_IRQ) == 0:
                self._IFR |= IFR_BIT_IRQ
                self._cpu.request_irq()
        else:
            if self._IFR & IFR_BIT_IRQ:
                self._IFR &= ~IFR_BIT_IRQ
                self._cpu.clear_irq()

    # ------------------------------------------------------------------
    # JR-100 specific hooks

    def _handle_store_orb(self) -> None:
        self._update_port_b_cache()
        if self._font_callback is not None:
            self._font_callback(bool(self._ORB & PB5_MASK))

    def _handle_store_iora(self) -> None:
        self._refresh_keyboard_matrix()

    def _handle_store_ddrb(self) -> None:
        self._update_port_b_cache()
        if self._font_callback is not None:
            self._font_callback(bool(self._ORB & PB5_MASK))
        self._refresh_keyboard_matrix()

    def _handle_store_ddra(self) -> None:
        pass

    def _handle_store_t1ch(self) -> None:
        if self._buzzer_callback is None:
            return
        if (self._ACR & 0xC0) == 0xC0 and (self._timer1 + 2) != 0:
            frequency = (self._clock_hz / (self._timer1 + 2)) / 2.0
            self._buzzer_callback(True, frequency)
        else:
            self._buzzer_callback(False, 0.0)

    def _handle_store_pcr(self) -> None:
        self._set_ca1_input(self._ca1_in)

    def _handle_store_iora_nohs(self) -> None:
        self._refresh_keyboard_matrix()

    def _handle_timer1_timeout_mode0(self) -> None:
        if self._buzzer_callback is not None:
            self._buzzer_callback(False, 0.0)

    def _handle_timer1_timeout_mode1(self) -> None:
        pass

    def _handle_timer1_timeout_mode2(self) -> None:
        self._update_port_b_cache()

    def _handle_timer1_timeout_mode3(self) -> None:
        self._update_port_b_cache()

    # ------------------------------------------------------------------
    # CA/CB lines

    def _set_ca2_output(self, state: int) -> None:
        self._ca2_out = 1 if state else 0

    def _set_cb2_output(self, state: int) -> None:
        self._cb2_out = 1 if state else 0

    def set_cb1_input(self, state: int) -> None:
        new_state = 1 if state else 0
        if self._cb1_in == new_state:
            return
        self._cb1_in = new_state
        edge_positive = (self._PCR & 0x10) == 0x10
        if (new_state == 1 and edge_positive) or (new_state == 0 and not edge_positive):
            if (self._ACR & 0x02) == 0x02:
                self._IRB = self._read_port_b()
            self._set_interrupt(IFR_BIT_CB1)
            if (self._cb2_out == 0) and ((self._PCR & 0xC0) == 0x80):
                self._set_cb2_output(1)

    def set_cb2_input(self, state: int) -> None:
        new_state = 1 if state else 0
        if self._cb2_in == new_state:
            return
        self._cb2_in = new_state
        if (self._PCR & 0x80) == 0x00:
            mode = self._PCR & 0xC0
            if (new_state == 1 and mode == 0x40) or (new_state == 0 and mode == 0x00):
                self._set_interrupt(IFR_BIT_CB2)

    def set_port_b_input(self, bit: int, state: int) -> None:
        mask = 1 << bit
        if self._DDRB & mask:
            return
        if state:
            self._port_b_state |= mask
        else:
            self._port_b_state &= ~mask
        if (self._ACR & 0x02) == 0:
            self._IRB = (self._IRB & self._DDRB) | (self._port_b_state & ~self._DDRB)
        self._update_port_b_cache()
        if bit < 5:
            self._update_ca1_from_keyboard()

    # ------------------------------------------------------------------
    # Reset helpers

    def _reset_state(self) -> None:
        self._ORB = DEFAULT_ORB
        self._ORA = 0
        self._DDRB = 0
        self._DDRA = 0
        self._ACR = 0
        self._PCR = 0
        self._IFR = 0
        self._IER = IFR_BIT_CA1
        self._SR = 0
        self._IRA = 0
        self._IRB = DEFAULT_IRB
        self._port_b_state = DEFAULT_ORB
        self._port_b_cache = DEFAULT_ORB
        self._timer1 = 0
        self._timer2 = 0
        self._latch1 = 0
        self._latch2 = 0
        self._timer1_initialized = False
        self._timer1_enable = False
        self._timer2_initialized = False
        self._timer2_enable = False
        self._ca2_timer = -1
        self._ca2_out = 1
        self._ca1_in = 1
        self._cb1_in = 0
        self._cb2_in = 1
        self._cb2_out = 1
        self._previous_pb6 = 0
        self._current_clock = 0
        self._refresh_keyboard_matrix()

    # ------------------------------------------------------------------
    # Keyboard hook placeholder

    def _handle_keyboard_event(self, _row: int, _mask: int, _pressed: bool) -> None:
        self._refresh_keyboard_matrix()

    def _refresh_keyboard_matrix(self) -> None:
        matrix = self._keyboard.snapshot()
        selected = self._ORA & 0x0F
        row_value = matrix[selected] if selected < len(matrix) else 0x00
        pressed_mask = (~row_value) & KEY_INPUT_MASK
        self._port_b_state &= ~KEY_INPUT_MASK
        self._port_b_state |= pressed_mask
        if (self._ACR & 0x02) == 0:
            self._IRB = (self._IRB & self._DDRB) | (self._port_b_state & ~self._DDRB)
        self._update_port_b_cache()
        self._set_ca1_input(0 if pressed_mask != KEY_INPUT_MASK else 1)

    def _update_ca1_from_keyboard(self, matrix: Optional[tuple[int, ...]] = None) -> None:
        if matrix is None:
            matrix = self._keyboard.snapshot()
        selected = self._ORA & 0x0F
        row_value = matrix[selected] if selected < len(matrix) else 0x00
        pressed_mask = (~row_value) & KEY_INPUT_MASK
        self._set_ca1_input(0 if pressed_mask != KEY_INPUT_MASK else 1)

    def _set_ca1_input(self, state: int) -> None:
        new_state = 1 if state else 0
        if self._ca1_in == new_state:
            return
        self._ca1_in = new_state
        trigger_on_rising = (self._PCR & 0x01) == 0x01
        if (new_state == 1 and trigger_on_rising) or (new_state == 0 and not trigger_on_rising):
            if (self._ACR & 0x01) == 0x01:
                self._IRA = self._read_port_a()
            self._set_interrupt(IFR_BIT_CA1)
            if self._ca2_out == 0 and (self._PCR & 0x0E) == 0x08:
                self._set_ca2_output(1)

    def cancel_key_click(self) -> None:
        """Compatibility stub for the legacy VIA API."""
        return


__all__ = [
    "Via6522",
    "REG_IORB",
    "REG_IORA",
    "REG_DDRB",
    "REG_DDRA",
    "REG_T1CL",
    "REG_T1CH",
    "REG_T1LL",
    "REG_T1LH",
    "REG_T2CL",
    "REG_T2CH",
    "REG_SR",
    "REG_ACR",
    "REG_PCR",
    "REG_IFR",
    "REG_IER",
    "REG_IORANH",
    "IFR_BIT_CA1",
    "IFR_BIT_CA2",
    "IFR_BIT_CB1",
    "IFR_BIT_CB2",
    "IFR_BIT_T1",
    "IFR_BIT_T2",
    "IFR_BIT_IRQ",
    "PB5_MASK",
    "PB6_MASK",
    "PB7_MASK",
]
