"""JR-100 specific implementation of the MOS 6522 VIA."""

from __future__ import annotations

from typing import Callable, Optional

from pyjr100.bus import Addressable
from pyjr100.cpu import MB8861
from pyjr100.io import Keyboard
from pyjr100.utils import debug_enabled, debug_log

# Interrupt flag bits (matching the original hardware definitions)
IFR_BIT_CA2 = 0x01
IFR_BIT_CA1 = 0x02
IFR_BIT_SR = 0x04
IFR_BIT_CB2 = 0x08
IFR_BIT_CB1 = 0x10
IFR_BIT_T2 = 0x20
IFR_BIT_T1 = 0x40
IFR_BIT_IRQ = 0x80

DEFAULT_PORTB_IDLE = 0xC0  # PB6/PB7 pulled up via internal wiring
TIMER1_INTERRUPT_BIT = IFR_BIT_T1

FontCallback = Callable[[bool], None]
BuzzerCallback = Callable[[bool, float], None]


class Via6522(Addressable):
    """Subset of the 6522 VIA used by the JR-100."""

    def __init__(
        self,
        start: int,
        keyboard: Keyboard,
        cpu: MB8861,
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

        # Data registers
        self._ora = 0x00
        self._orb = DEFAULT_PORTB_IDLE
        self._ddr_a = 0x00
        self._ddr_b = 0x00
        self._acr = 0x00
        self._pcr = 0x00
        self._ifr = 0x00
        # Enable CA1 interrupt by default to match JR-100 keyboard scanning.
        self._ier = IFR_BIT_CA1

        # Timers
        self._timer1 = 0xFFFF
        self._timer1_latch = 0xFFFF
        self._timer1_active = False

        self._timer2 = 0x0000
        self._timer2_latch = 0x0000
        self._timer2_active = False
        self._timer2_auto_reload = False
        self._key_timer_period = 1
        self._key_irq_pending = False

        # PB7 mirrors PB6 through JR-100 wiring
        self._pb7 = 1
        self._row_cache = [0x1F] * 16
        self._ca1_level = 1
        self._ca2_level = 1
        self._ca2_latched = False
        self._sync_port_b()
        self._debug("init", start="%04x" % start)

    # ------------------------------------------------------------------
    # Addressable implementation

    def get_start_address(self) -> int:
        return self._start

    def get_end_address(self) -> int:
        return self._end

    # ------------------------------------------------------------------
    # Memory interface

    def load8(self, address: int) -> int:
        offset = address - self._start
        if debug_enabled("via-reg"):
            self._debug("load", offset=offset)
        if offset == 0x00:
            return self._read_port_b()
        if offset == 0x01:
            return self._read_port_a()
        if offset == 0x02:
            return self._ddr_b
        if offset == 0x03:
            return self._ddr_a
        if offset == 0x04:
            value = self._timer1 & 0xFF
            self._clear_timer1_interrupt()
            return value
        if offset == 0x05:
            return (self._timer1 >> 8) & 0xFF
        if offset == 0x06:
            return self._timer1_latch & 0xFF
        if offset == 0x07:
            return (self._timer1_latch >> 8) & 0xFF
        if offset == 0x08:
            return self._timer2 & 0xFF
        if offset == 0x09:
            return (self._timer2 >> 8) & 0xFF
        if offset == 0x0A:
            return 0x00
        if offset == 0x0B:
            return self._acr
        if offset == 0x0C:
            return self._pcr
        if offset == 0x0D:
            value = self._ifr
            if self._key_irq_pending or self._any_keys_pressed():
                value |= IFR_BIT_T2
            return value
        if offset == 0x0E:
            return self._ier | 0x80
        if offset == 0x0F:
            return self._read_port_a()
        return 0x00

    def store8(self, address: int, value: int) -> None:
        offset = address - self._start
        value &= 0xFF
        if debug_enabled("via-reg"):
            self._debug("store", offset=offset, value=value)

        if offset == 0x00:
            self._write_port_b(value)
        elif offset == 0x01:
            self._write_port_a(value)
        elif offset == 0x02:
            self._ddr_b = value
            self._debug("ddr_b", ddr=self._ddr_b)
            self._sync_port_b()
        elif offset == 0x03:
            self._ddr_a = value
            self._debug("ddr_a", ddr=self._ddr_a)
        elif offset == 0x04:
            self._timer1_latch = (self._timer1_latch & 0xFF00) | value
        elif offset == 0x05:
            self._write_timer1_high(value)
        elif offset == 0x06:
            self._timer1_latch = (self._timer1_latch & 0xFF00) | value
        elif offset == 0x07:
            self._timer1_latch = (value << 8) | (self._timer1_latch & 0x00FF)
        elif offset == 0x08:
            self._timer2_latch = (self._timer2_latch & 0xFF00) | value
        elif offset == 0x09:
            self._timer2_latch = (value << 8) | (self._timer2_latch & 0x00FF)
            self._timer2 = self._timer2_latch or 0x10000
            self._timer2_active = True
            self._clear_timer2_interrupt()
        elif offset == 0x0B:
            self._acr = value
            self._debug("acr", acr=self._acr)
        elif offset == 0x0C:
            self._pcr = value
            self._debug("pcr", pcr=self._pcr)
        elif offset == 0x0D:
            self._clear_ifr(value)
        elif offset == 0x0E:
            self._write_ier(value)
        elif offset == 0x0F:
            self._write_port_a(value)

    # ------------------------------------------------------------------
    # Public helpers

    def tick(self, cycles: int) -> None:
        if cycles <= 0:
            return

        if debug_enabled("via-tick"):
            self._debug("tick", cycles=cycles, t1=self._timer1, t2=self._timer2)

        # Timer 1 (Φ2 clocked)
        if self._timer1_active:
            self._timer1 -= cycles
            while self._timer1 <= 0:
                reload = self._timer1_reload()
                self._timer1 += reload
                self._trigger_timer1()
                if not self._timer1_continuous():
                    self._timer1_active = False
                    break

        # Timer 2 (used minimally on JR-100)
        if self._timer2_active and not self._timer2_pulse_mode():
            self._timer2 -= cycles
            if self._timer2 <= 0:
                self._set_interrupt(IFR_BIT_T2)
                if self._timer2_auto_reload:
                    period = self._timer2_latch or self._key_timer_period or 1
                    self._timer2 += period
                else:
                    self._timer2 = self._timer2_latch or 0x10000
                    self._timer2_active = False

    # ------------------------------------------------------------------
    # Internal helpers

    def _read_port_a(self) -> int:
        inputs = (~self._ddr_a) & 0xFF
        outputs = self._ddr_a & 0xFF
        value = (self._ora & outputs) | (self._ora & inputs)
        self._debug("read_pa", value=value)
        self._clear_ifr(IFR_BIT_CA1)
        return value

    def _read_port_b(self) -> int:
        self._update_keyboard_matrix()
        self._debug("read_pb", value=self._orb)
        self._clear_ifr(IFR_BIT_CA1)
        if self._ca2_handshake_enabled() and self._ca2_latched:
            self._set_ca2(True)
            self._ca2_latched = False
        return self._orb

    def _write_port_a(self, value: int) -> None:
        self._ora = value & 0xFF
        self._debug("write_pa", ora=self._ora, ddr=self._ddr_a)
        self._update_keyboard_matrix()

    def _write_port_b(self, value: int) -> None:
        self._orb = (self._orb & ~self._ddr_b) | (value & self._ddr_b)
        self._pb7 = (self._orb >> 7) & 0x01
        self._debug("write_pb", orb=self._orb, pb7=self._pb7)
        self._sync_port_b()

    def _update_keyboard_matrix(self) -> None:
        selected = self._ora & 0x0F
        matrix = self._keyboard.snapshot()
        row_value = matrix[selected] if selected < len(matrix) else 0
        inputs_mask = (~self._ddr_b) & 0x1F
        pressed_mask = (~row_value) & 0x1F
        self._debug(
            "matrix",
            row=selected,
            ddr_a=self._ddr_a,
            ddr_b=self._ddr_b,
            raw=row_value,
            mask=pressed_mask,
        )
        self._orb = (self._orb & ~inputs_mask) | (pressed_mask & inputs_mask)
        if pressed_mask != self._row_cache[selected]:
            self._row_cache[selected] = pressed_mask
            self._debug("row", row=selected, mask=pressed_mask)
            if pressed_mask == 0x1F:
                self._stop_key_click()
        self._update_ca1(pressed_mask != 0x1F)
        self._sync_port_b()

    def _write_timer1_high(self, value: int) -> None:
        self._timer1_latch = (value << 8) | (self._timer1_latch & 0x00FF)
        self._timer1 = self._timer1_latch or 0x10000
        self._timer1_active = True
        self._pb7 = 0
        self._sync_port_b()
        self._clear_timer1_interrupt()
        self._update_buzzer(True)
        self._debug("t1_load", latch=self._timer1_latch, active=True)

    def _timer1_reload(self) -> int:
        return self._timer1_latch or 0x10000

    def _timer1_frequency(self) -> float:
        divisor = (self._timer1_latch + 2) * 2
        if divisor <= 0:
            return 0.0
        return self._clock_hz / divisor

    def _timer1_continuous(self) -> bool:
        return (self._acr & 0xC0) in (0x40, 0xC0)

    def _timer2_pulse_mode(self) -> bool:
        return (self._acr & 0x20) != 0

    def _trigger_timer1(self) -> None:
        self._set_interrupt(IFR_BIT_T1)
        mode = self._acr & 0xC0
        if mode == 0x00:  # one-shot, PB7 disabled
            self._timer1_active = False
            self._update_buzzer(False)
        elif mode == 0x40:  # continuous, PB7 toggles
            self._toggle_pb7()
        elif mode == 0x80:  # one-shot, PB7 pulses high once
            self._timer1_active = False
            self._pb7 = 1
            self._sync_port_b()
            self._update_buzzer(False)
        elif mode == 0xC0:  # square wave
            self._toggle_pb7()
        self._debug("t1_irq", mode=mode, pb7=self._pb7)

    def _toggle_pb7(self) -> None:
        self._pb7 ^= 1
        self._sync_port_b()

    def _sync_port_b(self) -> None:
        if self._pb7:
            self._orb |= 0x80
            self._orb |= 0x40
        else:
            self._orb &= ~0x80
            self._orb &= ~0x40
        self._notify_font_change()

    def _set_interrupt(self, mask: int) -> None:
        if self._ifr & mask:
            return
        self._ifr |= mask
        self._update_ifr_global()
        if mask & IFR_BIT_T2:
            self._key_irq_pending = True
        if (mask & IFR_BIT_CA1) != 0:
            self._cpu.request_irq()
        elif self._ier & mask:
            self._cpu.request_irq()
        self._debug("ifr_set", mask=mask, ifr=self._ifr, ier=self._ier)

    def _clear_timer1_interrupt(self) -> None:
        if self._ifr & IFR_BIT_T1:
            self._ifr &= ~IFR_BIT_T1
            self._update_ifr_global()

    def _clear_timer2_interrupt(self) -> None:
        if self._ifr & IFR_BIT_T2:
            self._ifr &= ~IFR_BIT_T2
            self._update_ifr_global()

    def _clear_ifr(self, mask: int) -> None:
        if mask & IFR_BIT_IRQ:
            mask = 0x7F
        if mask & IFR_BIT_CA1:
            mask |= IFR_BIT_CB2
        if mask & IFR_BIT_T2:
            self._key_irq_pending = False
        if mask:
            self._ifr &= ~mask
            self._update_ifr_global()
            self._debug("ifr_clr", mask=mask, ifr=self._ifr)
        if (mask & IFR_BIT_T2) and self._any_keys_pressed():
            self._key_irq_pending = True
            self._set_interrupt(IFR_BIT_T2)

    def _write_ier(self, value: int) -> None:
        if value & 0x80:
            self._ier |= value & 0x7F
        else:
            self._ier &= ~(value & 0x7F)
        self._update_ifr_global()
        self._debug("ier", value=value, ier=self._ier)

    def _update_ifr_global(self) -> None:
        if self._ifr & 0x7F:
            self._ifr |= IFR_BIT_IRQ
        else:
            self._ifr &= ~IFR_BIT_IRQ

    def _notify_font_change(self) -> None:
        if self._font_callback is None:
            return
        self._font_callback(bool(self._orb & 0x20))

    def _update_buzzer(self, enabled: bool) -> None:
        if self._buzzer_callback is None:
            return
        frequency = self._timer1_frequency() if enabled else 0.0
        self._buzzer_callback(enabled, frequency)
        self._debug("buzzer", enabled=enabled, freq=frequency)

    def _update_ca1(self, active: bool) -> None:
        level = 0 if active else 1
        if level == self._ca1_level:
            return
        self._ca1_level = level
        trigger_on_rising = (self._pcr & 0x01) == 0x01
        if (level == 1 and trigger_on_rising) or (level == 0 and not trigger_on_rising):
            if (self._acr & 0x01) == 0x01:
                self._read_port_a()
            self._set_interrupt(IFR_BIT_CA1)
            self._set_interrupt(IFR_BIT_T2)
            self._set_interrupt(IFR_BIT_CB2)
            if level == 0:
                self._arm_timer2_for_key()
            self._debug("ca1", level=level, pcr=self._pcr)
            if self._ca2_handshake_enabled():
                self._set_ca2(False)
                self._ca2_latched = True

    def _set_ca2(self, high: bool) -> None:
        level = 1 if high else 0
        if level == self._ca2_level:
            return
        self._ca2_level = level
        self._debug("ca2", level=level)
        if level == 1 and self._ca2_latched:
            self._ca2_latched = False
            self._stop_key_click()

    def _ca2_handshake_enabled(self) -> bool:
        return (self._pcr & 0x0E) == 0x08

    def _stop_key_click(self) -> None:
        if (self._acr & 0xC0) != 0xC0:
            return
        self._timer1_active = False
        self._pb7 = 1
        self._sync_port_b()
        self._update_buzzer(False)
        self._debug("t1_stop", pb7=self._pb7)

    def cancel_key_click(self) -> None:
        self._stop_key_click()

    def _handle_keyboard_event(self, row: int, _mask: int, _pressed: bool) -> None:
        selected = self._ora & 0x0F
        if row == selected:
            self._update_keyboard_matrix()
        else:
            self._update_ca1(self._any_keys_pressed())
        self._update_ca1(self._any_keys_pressed())
        if not self._any_keys_pressed():
            self._timer2_auto_reload = False
            self._key_irq_pending = False

    def _any_keys_pressed(self) -> bool:
        return any(value & 0x1F for value in self._keyboard.snapshot())

    def _arm_timer2_for_key(self) -> None:
        if self._timer2_pulse_mode():
            return
        self._timer2_auto_reload = True
        period = max(self._key_timer_period, 1)
        if self._timer2_latch == 0:
            self._timer2_latch = period
        if self._timer2 <= 0 or self._timer2 > self._timer2_latch:
            self._timer2 = period
        self._timer2_active = True
        self._clear_timer2_interrupt()

    def _debug(self, event: str, **fields) -> None:
        if not debug_enabled("via"):
            return
        field_str = " ".join(f"{key}={value}" for key, value in fields.items())
        debug_log("via", f"{event}: {field_str}")
