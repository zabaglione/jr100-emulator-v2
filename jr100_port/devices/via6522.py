"""R6522 VIA (Versatile Interface Adapter) implementation for JR-100."""

from __future__ import annotations

from typing import Protocol


class HardwareProvider(Protocol):
    """Minimal hardware facade expected by the VIA implementation."""

    def getDisplay(self):  # noqa: N802 - Java互換API
        ...

    def getKeyboard(self):  # noqa: N802 - Java互換API
        ...

    def getSoundProcessor(self):  # noqa: N802 - Java互換API
        ...


class ComputerLike(Protocol):
    """Minimal computer interface required by the VIA."""

    def getClockCount(self) -> int:  # noqa: N802 - Java互換API
        ...

    def getHardware(self) -> HardwareProvider:  # noqa: N802 - Java互換API
        ...

    def getBaseTime(self) -> int:  # noqa: N802 - Java互換API
        ...


JR100_CPU_CLOCK_HZ = 894_886


class Via6522:
    """Python port of jp.asamomiji.emulator.device.R6522."""

    VIA_REG_IORB = 0x00
    VIA_REG_IORA = 0x01
    VIA_REG_DDRB = 0x02
    VIA_REG_DDRA = 0x03
    VIA_REG_T1CL = 0x04
    VIA_REG_T1CH = 0x05
    VIA_REG_T1LL = 0x06
    VIA_REG_T1LH = 0x07
    VIA_REG_T2CL = 0x08
    VIA_REG_T2CH = 0x09
    VIA_REG_SR = 0x0A
    VIA_REG_ACR = 0x0B
    VIA_REG_PCR = 0x0C
    VIA_REG_IFR = 0x0D
    VIA_REG_IER = 0x0E
    VIA_REG_IORANH = 0x0F

    IFR_BIT_CA2 = 0x01
    IFR_BIT_CA1 = 0x02
    IFR_BIT_SR = 0x04
    IFR_BIT_CB2 = 0x08
    IFR_BIT_CB1 = 0x10
    IFR_BIT_T2 = 0x20
    IFR_BIT_T1 = 0x40
    IFR_BIT_IRQ = 0x80

    def __init__(self, computer: ComputerLike, start_address: int) -> None:
        self.computer = computer
        self.start_address = start_address
        self.end_address = start_address + 0x0F

        # Registers
        self.ifr = 0
        self.ier = 0
        self.pcr = 0
        self.acr = 0
        self.ira = 0
        self.ora = 0
        self.ddra = 0
        self.irb = 0
        self.orb = 0
        self.ddrb = 0
        self.sr = 0

        # Port states and control lines
        self.port_a = 0
        self.port_b = 0
        self.ca1_in = 0
        self.ca2_in = 0
        self.ca2_out = 0
        self.ca2_timer = -1
        self.cb1_in = 0
        self.cb1_out = 0
        self.cb2_in = 0
        self.cb2_out = 0

        # Timer state
        self.previous_pb6 = 0
        self.latch1 = 0
        self.latch2 = 0
        self.timer1 = 0
        self.timer2 = 0
        self.timer1_initialized = False
        self.timer1_enable = False
        self.timer2_initialized = False
        self.timer2_enable = False
        self.timer2_low_byte_timeout = False

        # Shift register state
        self.shift_tick = False
        self.shift_counter = 0
        self.shift_started = False

        self.current_clock = 0

        self.reset()

    def getStartAddress(self) -> int:  # noqa: N802
        return self.start_address

    def getEndAddress(self) -> int:  # noqa: N802
        return self.end_address

    # ---------------------------------------------------------------------
    # IRQ handling helpers
    # ---------------------------------------------------------------------
    def _process_irq(self) -> None:
        if self.ier & self.ifr & 0x7F:
            if (self.ifr & self.IFR_BIT_IRQ) == 0:
                self.ifr |= self.IFR_BIT_IRQ
                self.handlerIRQ(1)
        else:
            if (self.ifr & self.IFR_BIT_IRQ) != 0:
                self.ifr &= ~self.IFR_BIT_IRQ
                self.handlerIRQ(0)

    def _set_interrupt(self, value: int) -> None:
        if (self.ifr & value) == 0:
            self.ifr |= value
            self._process_irq()

    def _clear_interrupt(self, value: int) -> None:
        if (self.ifr & value) != 0:
            self.ifr &= ~value
            self._process_irq()

    def handlerIRQ(self, state: int) -> None:  # noqa: N802 - override hook
        """IRQ線の変化を通知するフック。サブクラス側で接続先へ伝える。"""
        # デフォルト実装は何もしない

    # ---------------------------------------------------------------------
    # Port A helpers
    # ---------------------------------------------------------------------
    def setPortA(self, bit: int, state: int) -> None:  # noqa: N802
        mask = 1 << bit
        if self.ddra & mask:
            return
        if state:
            self.port_a |= mask
        else:
            self.port_a &= ~mask
        if (self.acr & 0x01) == 0:
            self.ira = self.port_a & 0xFF

    def setPortAValue(self, value: int) -> None:
        self.port_a = (self.port_a & self.ddra) | (value & ~self.ddra)
        if (self.acr & 0x01) == 0:
            self.ira = self.port_a & 0xFF

    def inputPortA(self) -> int:  # noqa: N802
        return ((self.ira & ~self.ddra) | (self.port_a & self.ddra)) & 0xFF

    def inputPortABit(self, bit: int) -> int:  # noqa: N802
        return (self.inputPortA() >> bit) & 0x01

    def outputPortA(self) -> None:  # noqa: N802
        self.handlerPortA(self.ora)

    def handlerPortA(self, state: int) -> None:  # noqa: N802
        """Port A が変化した際のハンドラ。"""
        # サブクラスで実装

    def setCA1(self, state: int) -> None:  # noqa: N802
        if self.ca1_in == state:
            return
        self.ca1_in = state
        edge_pos = (self.pcr & 0x01) == 0x01
        if (state == 1 and edge_pos) or (state == 0 and not edge_pos):
            if (self.acr & 0x01) == 0x01:
                self.ira = self.inputPortA()
            self._set_interrupt(self.IFR_BIT_CA1)
            if self.ca2_out == 0 and (self.pcr & 0x0E) == 0x08:
                self.ca2_out = 1
                self.handlerCA2(self.ca2_out)

    def setCA2(self, state: int) -> None:  # noqa: N802
        if self.ca2_in == state:
            return
        self.ca2_in = state
        if (self.pcr & 0x08) != 0x00:
            return
        rising = (self.pcr & 0x0C) == 0x04
        if (state == 1 and rising) or (state == 0 and not rising):
            self._set_interrupt(self.IFR_BIT_CA2)

    def handlerCA2(self, status: int) -> None:  # noqa: N802
        """CA2線の出力状態が変化した際のハンドラ。"""
        # サブクラスで実装

    # ---------------------------------------------------------------------
    # Port B helpers
    # ---------------------------------------------------------------------
    def setPortB(self, bit: int, state: int) -> None:  # noqa: N802
        mask = 1 << bit
        if self.ddrb & mask:
            return
        if state:
            self.port_b |= mask
        else:
            self.port_b &= ~mask
        if (self.acr & 0x02) == 0:
            self.irb = self.port_b & 0xFF

    def setPortBValue(self, value: int) -> None:
        self.port_b = (self.port_b & self.ddrb) | (value & ~self.ddrb)
        if (self.acr & 0x02) == 0:
            self.irb = self.port_b & 0xFF

    def invertPortB(self, bit: int) -> None:  # noqa: N802
        mask = 1 << bit
        if self.ddrb & mask:
            return
        if self.port_b & mask:
            self.port_b &= ~mask
        else:
            self.port_b |= mask
        if (self.acr & 0x02) == 0:
            self.irb = self.port_b & 0xFF

    def inputPortB(self) -> int:  # noqa: N802
        return ((self.irb & ~self.ddrb) | (self.orb & self.ddrb)) & 0xFF

    def inputPortBBit(self, bit: int) -> int:  # noqa: N802
        return (self.inputPortB() >> bit) & 0x01

    def outputPortB(self) -> None:  # noqa: N802
        self.handlerPortB(self.orb & 0xFF)

    def handlerPortB(self, state: int) -> None:  # noqa: N802
        """Port B が変化した際のハンドラ。"""
        # サブクラスで実装

    def setCB1(self, state: int) -> None:  # noqa: N802
        if self.cb1_in == state:
            return
        self.cb1_in = state
        edge_pos = (self.pcr & 0x10) == 0x10
        if (state == 1 and edge_pos) or (state == 0 and not edge_pos):
            if (self.acr & 0x02) == 0x02:
                self.irb = self.inputPortB()
            if self.shift_started and (self.acr & 0x1C) == 0x0C:
                self._process_shift_in()
            if self.shift_started and (self.acr & 0x1C) == 0x1C:
                self._process_shift_out()
            self._set_interrupt(self.IFR_BIT_CB1)
            if self.cb2_out == 0 and (self.pcr & 0xC0) == 0x80:
                self.cb2_out = 1
                self.handlerCB2(self.cb2_out)

    def setCB2(self, state: int) -> None:  # noqa: N802
        if self.cb2_in == state:
            return
        self.cb2_in = state
        if (self.pcr & 0x80) != 0x00:
            return
        rising = (self.pcr & 0xC0) == 0x40
        if (state == 1 and rising) or (state == 0 and not rising):
            self._set_interrupt(self.IFR_BIT_CB2)

    def handlerCB1(self, status: int) -> None:  # noqa: N802
        """CB1線が変化した際のハンドラ。"""
        # サブクラスで実装

    def handlerCB2(self, status: int) -> None:  # noqa: N802
        """CB2線が変化した際のハンドラ。"""
        # サブクラスで実装

    # ---------------------------------------------------------------------
    # Shift register helpers
    # ---------------------------------------------------------------------
    def _initialize_shift_in(self) -> None:
        self.shift_tick = False
        self.shift_counter = 0
        if self.ifr & self.IFR_BIT_SR:
            self._clear_interrupt(self.IFR_BIT_SR)
            self._process_shift_in()
        self.shift_started = True

    def _initialize_shift_out(self) -> None:
        self.shift_tick = False
        self.shift_counter = 0
        if self.ifr & self.IFR_BIT_SR:
            self._clear_interrupt(self.IFR_BIT_SR)
            self._process_shift_out()
        self.shift_started = True

    def _process_shift_in(self) -> None:
        if not self.shift_started:
            return
        if not self.shift_tick:
            # notify shift-in
            self.cb1_out = 1
            self.handlerCB1(self.cb1_out)
        else:
            lb = self.sr & 0x01
            self.sr >>= 1
            self.sr &= 0x7F
            self.sr |= self.cb2_in << 7
            self.shift_counter = (self.shift_counter + 1) % 8
            if self.shift_counter == 0:
                self._set_interrupt(self.IFR_BIT_SR)
                self.shift_started = False
            self.cb1_out = 0
            self.handlerCB1(self.cb1_out)
        self.shift_tick = not self.shift_tick

    def _process_shift_out(self) -> None:
        if not self.shift_started:
            return
        if not self.shift_tick:
            self.cb1_out = 1
            self.handlerCB1(self.cb1_out)
        else:
            out_bit = (self.sr >> 7) & 0x01
            self.cb2_out = out_bit
            self.handlerCB2(self.cb2_out)
            self.sr = ((self.sr << 1) & 0xFE) | 0x01
            self.shift_counter = (self.shift_counter + 1) % 8
            if self.shift_counter == 0:
                self._set_interrupt(self.IFR_BIT_SR)
                self.shift_started = False
            self.cb1_out = 0
            self.handlerCB1(self.cb1_out)
        self.shift_tick = not self.shift_tick

    # ---------------------------------------------------------------------
    # Memory access API
    # ---------------------------------------------------------------------
    def load8(self, address: int) -> int:
        delay = 0
        self._execute(self.computer.getClockCount() - 1 + delay)
        offset = address - self.start_address
        result = 0
        if offset == self.VIA_REG_IORB:
            if (self.acr & 0x02) == 0:
                result = self.inputPortB()
            else:
                result = self.irb & 0xFF
            self._clear_interrupt(self.IFR_BIT_CB1 | (0x00 if (self.pcr & 0xA0) == 0x20 else self.IFR_BIT_CB2))
        elif offset == self.VIA_REG_IORA:
            result = self.inputPortA() if (self.acr & 0x01) == 0 else self.ira & 0xFF
            self._clear_interrupt(self.IFR_BIT_CA1 | (0x00 if (self.pcr & 0x0A) == 0x02 else self.IFR_BIT_CA2))
            if self.ca2_out == 1 and (((self.pcr & 0x0E) == 0x0A) or ((self.pcr & 0x0E) == 0x08)):
                self.ca2_out = 0
                self.handlerCA2(self.ca2_out)
                if (self.pcr & 0x0E) == 0x08:
                    self.ca2_timer = 1
        elif offset == self.VIA_REG_DDRB:
            result = self.ddrb & 0xFF
        elif offset == self.VIA_REG_DDRA:
            result = self.ddra & 0xFF
        elif offset == self.VIA_REG_T1CL:
            self._clear_interrupt(self.IFR_BIT_T1)
            result = self.timer1 & 0xFF
        elif offset == self.VIA_REG_T1CH:
            result = (self.timer1 >> 8) & 0xFF
        elif offset == self.VIA_REG_T1LL:
            result = self.latch1 & 0xFF
        elif offset == self.VIA_REG_T1LH:
            result = (self.latch1 >> 8) & 0xFF
        elif offset == self.VIA_REG_T2CL:
            self._clear_interrupt(self.IFR_BIT_T2)
            result = self.timer2 & 0xFF
        elif offset == self.VIA_REG_T2CH:
            result = (self.timer2 >> 8) & 0xFF
        elif offset == self.VIA_REG_SR:
            mode = self.acr & 0x1C
            if mode in (0x04, 0x08, 0x0C):
                self._initialize_shift_in()
            elif mode in (0x10, 0x14, 0x18, 0x1C):
                self._initialize_shift_out()
            result = self.sr & 0xFF
        elif offset == self.VIA_REG_ACR:
            result = self.acr & 0xFF
        elif offset == self.VIA_REG_PCR:
            result = self.pcr & 0xFF
        elif offset == self.VIA_REG_IFR:
            result = self.ifr & 0xFF
        elif offset == self.VIA_REG_IER:
            result = self.ier | 0x80
        elif offset == self.VIA_REG_IORANH:
            result = self.inputPortA() if (self.acr & 0x01) == 0 else self.ira & 0xFF
        else:
            raise AssertionError(f"invalid register {address:#04x}")
        self._execute(self.computer.getClockCount() + delay)
        return result & 0xFF

    def store8(self, address: int, value: int) -> None:
        value &= 0xFF
        delay = 0
        self._execute(self.computer.getClockCount() - 1 + delay)
        offset = address - self.start_address
        if offset == self.VIA_REG_IORB:
            self.orb = value
            self.outputPortB()
            self._clear_interrupt(self.IFR_BIT_CB1 | (0x00 if (self.pcr & 0xA0) == 0x20 else self.IFR_BIT_CB2))
            if self.cb2_out == 1 and (self.pcr & 0xC0) == 0x80:
                self.cb2_out = 0
                self.handlerCB2(self.cb2_out)
            self.storeORB_option()
        elif offset == self.VIA_REG_IORA:
            self.ora = value
            if self.ddra != 0x00:
                self.outputPortA()
            self._clear_interrupt(self.IFR_BIT_CA1 | (0x00 if (self.pcr & 0x0A) == 0x02 else self.IFR_BIT_CA2))
            if self.ca2_out == 1 and (((self.pcr & 0x0E) == 0x0A) or (self.pcr & 0x0C) == 0x08):
                self.ca2_out = 0
                self.handlerCA2(self.ca2_out)
            if (self.pcr & 0x0E) == 0x0A:
                self.ca2_timer = 1
            self.storeIORA_option()
        elif offset == self.VIA_REG_DDRB:
            self.ddrb = value
            self.storeDDRB_option()
        elif offset == self.VIA_REG_DDRA:
            self.ddra = value
            self.storeDDRA_option()
        elif offset == self.VIA_REG_T1CL:
            self.latch1 = (self.latch1 & 0xFF00) | value
            self.storeT1CL_option()
        elif offset == self.VIA_REG_T1CH:
            self.latch1 = (self.latch1 & 0x00FF) | ((value << 8) & 0xFF00)
            self.timer1 = self.latch1
            self.timer1_initialized = True
            self.timer1_enable = True
            self.setPortB(7, 0)
            self.storeT1CH_option()
        elif offset == self.VIA_REG_T1LL:
            self.latch1 = (self.latch1 & 0xFF00) | value
            self.storeT1LL_option()
        elif offset == self.VIA_REG_T1LH:
            self.latch1 = (self.latch1 & 0x00FF) | ((value << 8) & 0xFF00)
            self.storeT1LH_option()
        elif offset == self.VIA_REG_T2CL:
            self.latch2 = (self.latch2 & 0xFF00) | value
            self.storeT2CL_option()
        elif offset == self.VIA_REG_T2CH:
            self.latch2 = (self.latch2 & 0x00FF) | ((value << 8) & 0xFF00)
            self.timer2 = self.latch2
            self._clear_interrupt(self.IFR_BIT_T2)
            self.timer2_initialized = True
            self.timer2_enable = True
            self.storeT2CH_option()
        elif offset == self.VIA_REG_SR:
            mode = self.acr & 0x1C
            if mode in (0x04, 0x08, 0x0C):
                self._initialize_shift_in()
            elif mode in (0x10, 0x14, 0x18, 0x1C):
                self._initialize_shift_out()
            elif mode != 0x00:
                raise AssertionError(f"invalid sr mode {mode:#02x}")
            self.sr = value
            self.storeSR_option()
        elif offset == self.VIA_REG_ACR:
            self.acr = value
            self.storeACR_option()
        elif offset == self.VIA_REG_PCR:
            self.pcr = value
            self.storePCR_option()
        elif offset == self.VIA_REG_IFR:
            if value & 0x80:
                value = 0x7F
            self._clear_interrupt(value)
            self.storeIFR_option()
        elif offset == self.VIA_REG_IER:
            self.ier = value
            self.storeIER_option()
        elif offset == self.VIA_REG_IORANH:
            self.ora = value
            if self.ddra != 0x00:
                self.outputPortA()
            self.storeIORA_NOHS_option()
        else:
            raise AssertionError(f"invalid register {address:#04x}")
        self._execute(self.computer.getClockCount() + delay)

    # ---------------------------------------------------------------------
    # Extension points (no-op by default)
    # ---------------------------------------------------------------------
    def storeORB_option(self) -> None:
        pass

    def storeIORA_option(self) -> None:
        pass

    def storeDDRB_option(self) -> None:
        pass

    def storeDDRA_option(self) -> None:
        pass

    def storeT1CL_option(self) -> None:
        pass

    def storeT1CH_option(self) -> None:
        pass

    def storeT1LL_option(self) -> None:
        pass

    def storeT1LH_option(self) -> None:
        pass

    def storeT2CL_option(self) -> None:
        pass

    def storeT2CH_option(self) -> None:
        pass

    def storeSR_option(self) -> None:
        pass

    def storeACR_option(self) -> None:
        pass

    def storePCR_option(self) -> None:
        pass

    def storeIFR_option(self) -> None:
        pass

    def storeIER_option(self) -> None:
        pass

    def storeIORA_NOHS_option(self) -> None:
        pass

    def timer1TimeoutMode0_option(self) -> None:
        pass

    def timer1TimeoutMode1_option(self) -> None:
        pass

    def timer1TimeoutMode2_option(self) -> None:
        pass

    def timer1TimeoutMode3_option(self) -> None:
        pass

    # ---------------------------------------------------------------------
    # Execution core
    # ---------------------------------------------------------------------
    def _execute(self, clock: int) -> None:
        while self.current_clock <= clock:
            if self.ca2_timer >= 0:
                self.ca2_timer -= 1
                if self.ca2_timer < 0:
                    self.ca2_out = 1
                    self.handlerCA2(self.ca2_out)

            if self.timer1_initialized:
                self.timer1_initialized = False
            elif self.timer1 >= 0:
                self.timer1 -= 1
            else:
                if self.timer1_enable:
                    self._set_interrupt(self.IFR_BIT_T1)
                    mode = self.acr & 0xC0
                    if mode == 0x00:
                        self.timer1_enable = False
                        self.timer1TimeoutMode0_option()
                    elif mode == 0x40:
                        self.invertPortB(7)
                        self.timer1TimeoutMode1_option()
                    elif mode == 0x80:
                        self.timer1_enable = False
                        self.setPortB(7, 1)
                        self.timer1TimeoutMode2_option()
                    elif mode == 0xC0:
                        self.invertPortB(7)
                        self.timer1TimeoutMode3_option()
                    else:
                        raise AssertionError(f"invalid t1mode: {mode:#02x}")
                self.timer1 = self.latch1
                self.storeT1CH_option()

            current_pb6 = self.inputPortB() & 0x40
            pb6_negative = self.previous_pb6 != 0 and current_pb6 == 0
            self.previous_pb6 = current_pb6

            if self.timer2 >= 0:
                mode = self.acr & 0x20
                if mode == 0x00:
                    if self.timer2_initialized:
                        self.timer2_initialized = False
                    else:
                        self.timer2 -= 1
                elif mode == 0x20:
                    if pb6_negative:
                        self.timer2 -= 1
                else:
                    raise AssertionError(f"invalid t2mode: {mode:#02x}")
            else:
                if self.timer2_enable:
                    self._set_interrupt(self.IFR_BIT_T2)
                    self.timer2_enable = False
                if self.shift_started and (self.timer2 & 0xFF) == 0xFF:
                    mode = self.acr & 0x1C
                    if mode == 0x04:
                        self._process_shift_in()
                    elif mode in (0x10, 0x14):
                        self._process_shift_out()
                self.timer2 = self.latch2

            mode = self.acr & 0x1C
            if mode == 0x08:
                self._process_shift_in()
            elif mode == 0x18:
                self._process_shift_out()

            self.current_clock += 1

    def execute(self) -> None:
        self._execute(self.computer.getClockCount())

    def reset(self) -> None:
        self.ifr = 0
        self.ier = 0
        self.pcr = 0
        self.acr = 0
        self.ira = 0
        self.ora = 0
        self.ddra = 0
        self.irb = 0
        self.orb = 0
        self.ddrb = 0
        self.sr = 0

        self.port_a = 0
        self.port_b = 0
        self.ca1_in = 0
        self.ca2_in = 0
        self.ca2_out = 0
        self.ca2_timer = -1
        self.cb1_in = 0
        self.cb1_out = 0
        self.cb2_in = 0
        self.cb2_out = 0

        self.latch1 = 0
        self.latch2 = 0
        self.timer1 = 0
        self.timer2 = 0
        self.timer1_initialized = False
        self.timer1_enable = False
        self.timer2_initialized = False
        self.timer2_enable = False
        self.timer2_low_byte_timeout = False

        self.previous_pb6 = 0

        self.shift_tick = False
        self.shift_started = False
        self.shift_counter = 0

        self.current_clock = 0


class JR100Via6522(Via6522):
    """JR-100 specific VIA wiring (port of JR100R6522)."""

    FONT_NORMAL = 0
    FONT_USER_DEFINED = 1

    def __init__(self, computer: ComputerLike, start_address: int) -> None:
        super().__init__(computer, start_address)
        self.prev_frequency = 0.0

    def _jumper_pb7_pb6(self) -> None:
        self.setPortB(6, self.inputPortBBit(7))

    def storeORB_option(self) -> None:  # noqa: N802
        display = self.computer.getHardware().getDisplay()
        if self.inputPortB() & 0x20:
            display.setCurrentFont(self.FONT_USER_DEFINED)
        else:
            display.setCurrentFont(self.FONT_NORMAL)
        self._jumper_pb7_pb6()

    def storeIORA_option(self) -> None:  # noqa: N802
        keyboard = self.computer.getHardware().getKeyboard()
        matrix = keyboard.getKeyMatrix()
        row = self.ora & 0x0F
        value = self.inputPortB() & 0xE0
        if 0 <= row < len(matrix):
            value |= (~matrix[row]) & 0x1F
        else:
            value |= 0x1F
        self.setPortBValue(value & 0xFF)
        self._jumper_pb7_pb6()

    def storeT1CH_option(self) -> None:  # noqa: N802
        sound = self.computer.getHardware().getSoundProcessor()
        if (self.acr & 0xC0) == 0xC0:
            period = self.timer1 + 2
            if period <= 0:
                frequency = 0.0
            else:
                frequency = 894_886.25 / period / 2.0
            if frequency == self.prev_frequency:
                sound.setLineOn()
                return
            self.prev_frequency = frequency
            timestamp = (
                self.current_clock * 1_000_000_000 // JR100_CPU_CLOCK_HZ
                + self.computer.getBaseTime()
            )
            sound.setFrequency(timestamp, frequency)
            sound.setLineOn()
        else:
            sound.setLineOff()

    def timer1TimeoutMode0_option(self) -> None:  # noqa: N802
        self.computer.getHardware().getSoundProcessor().setLineOff()

    def timer1TimeoutMode2_option(self) -> None:  # noqa: N802
        self._jumper_pb7_pb6()

    def timer1TimeoutMode3_option(self) -> None:  # noqa: N802
        self._jumper_pb7_pb6()
