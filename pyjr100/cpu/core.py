"""Core MB8861 CPU implementation scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from pyjr100.bus import MemorySystem
from pyjr100.utils import debug_enabled, debug_log

from .opcodes import AddressingMode, Instruction, OPCODE_TABLE


class CPUError(Exception):
    """Base error for CPU-related failures."""


class IllegalOpcodeError(CPUError):
    """Raised when the CPU encounters an unimplemented opcode."""


FLAG_H = 0x20
FLAG_I = 0x10
FLAG_N = 0x08
FLAG_Z = 0x04
FLAG_V = 0x02
FLAG_C = 0x01


@dataclass
class CPUState:
    """Snapshot of the MB8861 register file."""

    a: int = 0x00
    b: int = 0x00
    x: int = 0x0000
    sp: int = 0x01FF
    pc: int = 0x0000
    cc: int = 0x00

    def clone(self) -> "CPUState":
        return CPUState(self.a, self.b, self.x, self.sp, self.pc, self.cc)


@dataclass
class MB8861:
    """Scaffold implementation of the JR-100 main CPU."""

    memory: MemorySystem
    instruction_table: Sequence[Instruction | None] = field(default=OPCODE_TABLE)

    RESET_VECTOR: int = 0xFFFE
    NMI_VECTOR: int = 0xFFFC
    IRQ_VECTOR: int = 0xFFF8
    SWI_VECTOR: int = 0xFFFA

    state: CPUState = field(default_factory=CPUState)
    cycle_count: int = 0
    halted: bool = False
    wai_latch: bool = False
    irq_pending: bool = False
    nmi_pending: bool = False

    def reset(self) -> None:
        """Reset CPU state and load the restart vector."""

        self.state = CPUState()
        self.cycle_count = 0
        self.halted = False
        self.wai_latch = False
        self.irq_pending = False
        self.nmi_pending = False
        self.state.pc = self._read_word(self.RESET_VECTOR)

    def step(self) -> int:
        """Execute a single instruction and return the cycle count."""

        if self.halted:
            return 0

        interrupt_cycles = 0

        if self.nmi_pending:
            interrupt_cycles += self._service_nmi()
            self.nmi_pending = False

        if self.irq_pending and not self._get_flag(FLAG_I):
            interrupt_cycles += self._service_irq()
            self.irq_pending = False

        if self.wai_latch and interrupt_cycles == 0:
            if debug_enabled("cpu"):
                debug_log("cpu", "wai idle pc=%04x", self.state.pc)
            return 0

        pc_before = self.state.pc
        opcode = self._fetch_byte()
        if debug_enabled("cpu"):
            debug_log(
                "cpu",
                "pc=%04x opcode=%02x interrupts=%d",
                pc_before,
                opcode,
                interrupt_cycles,
            )
        instruction = self._decode(opcode)
        handler = getattr(self, instruction.handler, None)
        if handler is None:
            raise CPUError(f"handler '{instruction.handler}' not implemented")

        handler_cycles = handler(instruction) or 0
        instruction_cycles = instruction.cycles + handler_cycles
        total_cycles = interrupt_cycles + instruction_cycles
        self.cycle_count += total_cycles
        if debug_enabled("cpu"):
            debug_log(
                "cpu",
                "pc=%04x cycles=%d",
                self.state.pc,
                total_cycles,
            )
        return total_cycles

    # ------------------------------------------------------------------
    # Instruction handlers

    def op_nop(self, _: Instruction) -> int:
        """No operation."""

        return 0

    def request_irq(self) -> None:
        """Schedule a maskable interrupt to be serviced on the next step."""

        self.irq_pending = True

    def clear_irq(self) -> None:
        """Clear any pending IRQ request."""

        self.irq_pending = False

    def request_nmi(self) -> None:
        """Assert the non-maskable interrupt line."""

        self.nmi_pending = True

    def op_ld_accumulator(self, instruction: Instruction) -> int:
        value = self._fetch_operand(instruction.mode)
        accumulator = self._require_accumulator(instruction)
        self._set_accumulator(accumulator, value)
        self._update_nz_flags(value)
        self._set_flag(FLAG_V, False)
        return 0

    def op_st_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        address = self._resolve_address(instruction.mode)
        self._update_nz_flags(value)
        self._set_flag(FLAG_V, False)
        self._write_byte(address, value)
        return 0

    def op_inc_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_inc(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_dec_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_dec(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_tab(self, _: Instruction) -> int:
        value = self._get_accumulator("A")
        self._set_accumulator("B", value)
        self._update_nz_flags(value)
        self._set_flag(FLAG_V, False)
        return 0

    def op_tba(self, _: Instruction) -> int:
        value = self._get_accumulator("B")
        self._set_accumulator("A", value)
        self._update_nz_flags(value)
        self._set_flag(FLAG_V, False)
        return 0

    def op_clr_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        result = self._op_clr()
        self._set_accumulator(accumulator, result)
        return 0

    def op_com_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_com(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_neg_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_neg(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_lsr_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_lsr(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_asr_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_asr(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_asl_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_asl(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_rol_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_rol(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_ror_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        result = self._op_ror(value)
        self._set_accumulator(accumulator, result)
        return 0

    def op_tst_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        self._tst(value)
        return 0

    def op_clr_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, lambda _: self._op_clr())
        return 0

    def op_com_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_com)
        return 0

    def op_neg_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_neg)
        return 0

    def op_lsr_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_lsr)
        return 0

    def op_asr_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_asr)
        return 0

    def op_asl_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_asl)
        return 0

    def op_rol_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_rol)
        return 0

    def op_ror_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_ror)
        return 0

    def op_inc_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_inc)
        return 0

    def op_dec_memory(self, instruction: Instruction) -> int:
        self._modify_memory(instruction, self._op_dec)
        return 0

    def op_tst_memory(self, instruction: Instruction) -> int:
        _, value = self._read_memory(instruction)
        self._tst(value)
        return 0

    def op_nim(self, _: Instruction) -> int:
        immediate = self._fetch_byte()
        offset = self._fetch_byte()
        address = (self.state.x + offset) & 0xFFFF
        current = self._read_byte(address)
        result = self._nim(immediate, current)
        self._write_byte(address, result)
        return 0

    def op_oim(self, _: Instruction) -> int:
        immediate = self._fetch_byte()
        offset = self._fetch_byte()
        address = (self.state.x + offset) & 0xFFFF
        current = self._read_byte(address)
        result = self._oim(immediate, current)
        self._write_byte(address, result)
        return 0

    def op_xim(self, _: Instruction) -> int:
        immediate = self._fetch_byte()
        offset = self._fetch_byte()
        address = (self.state.x + offset) & 0xFFFF
        current = self._read_byte(address)
        result = self._xim(immediate, current)
        self._write_byte(address, result)
        return 0

    def op_tmm(self, _: Instruction) -> int:
        immediate = self._fetch_byte()
        offset = self._fetch_byte()
        value = self._read_byte((self.state.x + offset) & 0xFFFF)
        self._tmm(immediate, value)
        return 0

    def op_add_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        current = self._get_accumulator(accumulator)
        result = self._add8(current, operand, carry_in=False)
        self._set_accumulator(accumulator, result)
        return 0

    def op_adc_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        current = self._get_accumulator(accumulator)
        result = self._add8(current, operand, carry_in=self._get_flag(FLAG_C))
        self._set_accumulator(accumulator, result)
        return 0

    def op_sub_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        current = self._get_accumulator(accumulator)
        result = self._sub8(current, operand, borrow_in=False)
        self._set_accumulator(accumulator, result)
        return 0

    def op_sbc_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        current = self._get_accumulator(accumulator)
        result = self._sub8(current, operand, borrow_in=self._get_flag(FLAG_C))
        self._set_accumulator(accumulator, result)
        return 0

    def op_and_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        result = self._get_accumulator(accumulator) & operand
        self._set_accumulator(accumulator, result)
        self._update_nz_flags(result)
        self._set_flag(FLAG_V, False)
        return 0

    def op_ora_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        result = self._get_accumulator(accumulator) | operand
        self._set_accumulator(accumulator, result)
        self._update_nz_flags(result)
        self._set_flag(FLAG_V, False)
        return 0

    def op_eor_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        result = self._get_accumulator(accumulator) ^ operand
        self._set_accumulator(accumulator, result)
        self._update_nz_flags(result)
        self._set_flag(FLAG_V, False)
        return 0

    def op_cmp_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        current = self._get_accumulator(accumulator)
        self._sub8(current, operand, borrow_in=False)
        return 0

    def op_bit_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        operand = self._fetch_operand(instruction.mode)
        value = self._get_accumulator(accumulator) & operand
        self._set_flag(FLAG_N, (value & 0x80) != 0)
        self._set_flag(FLAG_Z, value == 0)
        self._set_flag(FLAG_V, False)
        return 0

    def op_ld_index(self, instruction: Instruction) -> int:
        value = self._fetch_operand(instruction.mode)
        self.state.x = value & 0xFFFF
        self._set_flag(FLAG_N, (self.state.x & 0x8000) != 0)
        self._set_flag(FLAG_Z, self.state.x == 0)
        self._set_flag(FLAG_V, False)
        return 0

    def op_ld_stack(self, instruction: Instruction) -> int:
        value = self._fetch_operand(instruction.mode)
        self.state.sp = value & 0xFFFF
        self._set_flag(FLAG_N, (self.state.sp & 0x8000) != 0)
        self._set_flag(FLAG_Z, self.state.sp == 0)
        self._set_flag(FLAG_V, False)
        return 0

    def op_st_index(self, instruction: Instruction) -> int:
        address = self._resolve_address_16(instruction.mode)
        self._write_word(address, self.state.x)
        self._set_flag(FLAG_N, (self.state.x & 0x8000) != 0)
        self._set_flag(FLAG_Z, self.state.x == 0)
        self._set_flag(FLAG_V, False)
        return 0

    def op_st_stack(self, instruction: Instruction) -> int:
        address = self._resolve_address_16(instruction.mode)
        self._write_word(address, self.state.sp)
        self._set_flag(FLAG_N, (self.state.sp & 0x8000) != 0)
        self._set_flag(FLAG_Z, self.state.sp == 0)
        self._set_flag(FLAG_V, False)
        return 0

    def op_inx(self, _: Instruction) -> int:
        self.state.x = (self.state.x + 1) & 0xFFFF
        self._set_flag(FLAG_Z, self.state.x == 0)
        return 0

    def op_dex(self, _: Instruction) -> int:
        self.state.x = (self.state.x - 1) & 0xFFFF
        self._set_flag(FLAG_Z, self.state.x == 0)
        return 0

    def op_ins(self, _: Instruction) -> int:
        self.state.sp = (self.state.sp + 1) & 0xFFFF
        return 0

    def op_des(self, _: Instruction) -> int:
        self.state.sp = (self.state.sp - 1) & 0xFFFF
        return 0

    def op_cpx(self, instruction: Instruction) -> int:
        operand = self._fetch_operand(instruction.mode)
        x = self.state.x
        result = (x - operand) & 0xFFFF
        self._set_flag(FLAG_N, (result & 0x8000) != 0)
        self._set_flag(FLAG_Z, result == 0)
        overflow = ((x ^ operand) & (x ^ result) & 0x8000) != 0
        self._set_flag(FLAG_V, overflow)
        self._set_flag(FLAG_C, x < operand)
        return 0

    def op_adx_immediate(self, instruction: Instruction) -> int:
        operand = self._fetch_operand(instruction.mode) & 0xFF
        self.state.x = self._add16(self.state.x, operand)
        return 0

    def op_adx_extended(self, instruction: Instruction) -> int:
        address = self._fetch_word()
        operand = self._read_word(address)
        self.state.x = self._add16(self.state.x, operand)
        return 0

    def op_txs(self, _: Instruction) -> int:
        self.state.sp = (self.state.x - 1) & 0xFFFF
        return 0

    def op_tsx(self, _: Instruction) -> int:
        self.state.x = (self.state.sp + 1) & 0xFFFF
        return 0
    def op_branch_bne(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if not self._get_flag(FLAG_Z):
            self._branch(offset)
        return 0

    def op_branch_beq(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if self._get_flag(FLAG_Z):
            self._branch(offset)
        return 0

    def op_branch_bcc(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if not self._get_flag(FLAG_C):
            self._branch(offset)
        return 0

    def op_branch_bcs(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if self._get_flag(FLAG_C):
            self._branch(offset)
        return 0

    def op_branch_bpl(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if not self._get_flag(FLAG_N):
            self._branch(offset)
        return 0

    def op_branch_bmi(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if self._get_flag(FLAG_N):
            self._branch(offset)
        return 0

    def op_branch_bra(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        self._branch(offset)
        return 0

    def op_branch_brn(self, instruction: Instruction) -> int:
        self._fetch_operand(instruction.mode)
        return 0

    def op_branch_bhi(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if not self._get_flag(FLAG_C) and not self._get_flag(FLAG_Z):
            self._branch(offset)
        return 0

    def op_branch_bls(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if self._get_flag(FLAG_C) or self._get_flag(FLAG_Z):
            self._branch(offset)
        return 0

    def op_branch_bvc(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if not self._get_flag(FLAG_V):
            self._branch(offset)
        return 0

    def op_branch_bvs(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if self._get_flag(FLAG_V):
            self._branch(offset)
        return 0

    def op_branch_bge(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if self._get_flag(FLAG_N) == self._get_flag(FLAG_V):
            self._branch(offset)
        return 0

    def op_branch_blt(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if self._get_flag(FLAG_N) != self._get_flag(FLAG_V):
            self._branch(offset)
        return 0

    def op_branch_bgt(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if not self._get_flag(FLAG_Z) and self._get_flag(FLAG_N) == self._get_flag(FLAG_V):
            self._branch(offset)
        return 0

    def op_branch_ble(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        if self._get_flag(FLAG_Z) or self._get_flag(FLAG_N) != self._get_flag(FLAG_V):
            self._branch(offset)
        return 0

    def op_branch_bsr(self, instruction: Instruction) -> int:
        offset = self._fetch_operand(instruction.mode)
        self._push_word(self.state.pc)
        self._branch(offset)
        return 0

    def op_jsr(self, instruction: Instruction) -> int:
        address = self._resolve_address(instruction.mode)
        self._push_word(self.state.pc)
        self.state.pc = address & 0xFFFF
        return 0

    def op_jmp(self, instruction: Instruction) -> int:
        address = self._resolve_address(instruction.mode)
        self.state.pc = address & 0xFFFF
        return 0

    def op_psh_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._get_accumulator(accumulator)
        self._push_byte(value)
        return 0

    def op_pul_accumulator(self, instruction: Instruction) -> int:
        accumulator = self._require_accumulator(instruction)
        value = self._pull_byte()
        self._set_accumulator(accumulator, value)
        return 0

    def op_rts(self, _: Instruction) -> int:
        self.state.pc = self._pull_word() & 0xFFFF
        return 0

    def op_rti(self, _: Instruction) -> int:
        self._pull_all_registers()
        self.wai_latch = False
        return 0

    def op_wai(self, _: Instruction) -> int:
        self.wai_latch = True
        return 0

    def op_swi(self, _: Instruction) -> int:
        self.state.pc = (self.state.pc + 1) & 0xFFFF
        self._push_all_registers()
        self._set_flag(FLAG_I, True)
        self.state.pc = self._read_word(self.SWI_VECTOR)
        return 0

    def op_tap(self, _: Instruction) -> int:
        self._apply_cc(self.state.a)
        return 0

    def op_tpa(self, _: Instruction) -> int:
        self.state.a = (self._compose_cc() | 0xC0) & 0xFF
        return 0

    def op_orcc(self, instruction: Instruction) -> int:
        value = self._fetch_operand(instruction.mode) & 0xFF
        self.state.cc = ((self.state.cc | value) | 0xC0) & 0xFF
        return 0

    def op_andcc(self, instruction: Instruction) -> int:
        value = self._fetch_operand(instruction.mode) & 0xFF
        self.state.cc = ((self.state.cc & value) | 0xC0) & 0xFF
        return 0

    def op_nim(self, _: Instruction) -> int:
        mask = self._fetch_byte()
        offset = self._fetch_byte()
        address = (self.state.x + offset) & 0xFFFF
        original = self._read_byte(address)
        result = mask & original
        self._write_byte(address, result)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_N, result != 0)
        self._set_flag(FLAG_V, False)
        return 0

    def op_oim(self, _: Instruction) -> int:
        mask = self._fetch_byte()
        offset = self._fetch_byte()
        address = (self.state.x + offset) & 0xFFFF
        original = self._read_byte(address)
        result = (mask | original) & 0xFF
        self._write_byte(address, result)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_N, result != 0)
        self._set_flag(FLAG_V, False)
        return 0

    def op_xim(self, _: Instruction) -> int:
        mask = self._fetch_byte()
        offset = self._fetch_byte()
        address = (self.state.x + offset) & 0xFFFF
        original = self._read_byte(address)
        result = (mask ^ original) & 0xFF
        self._write_byte(address, result)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_N, result != 0)
        self._set_flag(FLAG_V, False)
        return 0

    def op_tmm(self, _: Instruction) -> int:
        mask = self._fetch_byte() & 0xFF
        offset = self._fetch_byte()
        value = self._read_byte((self.state.x + offset) & 0xFFFF)
        if mask == 0 or value == 0:
            self._set_flag(FLAG_N, False)
            self._set_flag(FLAG_Z, True)
            self._set_flag(FLAG_V, False)
        elif value == 0xFF:
            self._set_flag(FLAG_N, False)
            self._set_flag(FLAG_Z, False)
            self._set_flag(FLAG_V, True)
        else:
            self._set_flag(FLAG_N, True)
            self._set_flag(FLAG_Z, False)
            self._set_flag(FLAG_V, False)
        return 0

    def op_clc(self, _: Instruction) -> int:
        self._set_flag(FLAG_C, False)
        return 0

    def op_sec(self, _: Instruction) -> int:
        self._set_flag(FLAG_C, True)
        return 0

    def op_cli(self, _: Instruction) -> int:
        self._set_flag(FLAG_I, False)
        return 0

    def op_sei(self, _: Instruction) -> int:
        self._set_flag(FLAG_I, True)
        return 0

    def op_clv(self, _: Instruction) -> int:
        self._set_flag(FLAG_V, False)
        return 0

    def op_sev(self, _: Instruction) -> int:
        self._set_flag(FLAG_V, True)
        return 0

    def op_sba(self, _: Instruction) -> int:
        result = self._sub8(self.state.a, self.state.b, borrow_in=False)
        self.state.a = result
        return 0

    def op_cba(self, _: Instruction) -> int:
        self._sub8(self.state.a, self.state.b, borrow_in=False)
        return 0

    def op_aba(self, _: Instruction) -> int:
        result = self._add8(self.state.a, self.state.b, carry_in=False)
        self.state.a = result
        return 0

    def op_daa(self, _: Instruction) -> int:
        original = self.state.a & 0xFF
        t = original
        if (t & 0x0F) >= 0x0A or self._get_flag(FLAG_H):
            t += 0x06
        if (t & 0xF0) >= 0xA0:
            t += 0x60
            self._set_flag(FLAG_C, True)
        else:
            self._set_flag(FLAG_C, self._get_flag(FLAG_C))
        result = t & 0xFF
        self.state.a = result
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        overflow = (((original ^ result) & 0x80) != 0)
        self._set_flag(FLAG_V, overflow)
        self._set_flag(FLAG_H, False)
        return 0

    # ------------------------------------------------------------------
    # Fetch helpers

    def _fetch_byte(self) -> int:
        value = self._read_byte(self.state.pc)
        self.state.pc = (self.state.pc + 1) & 0xFFFF
        return value

    def _fetch_operand(self, mode: AddressingMode) -> int:
        if mode == AddressingMode.INHERENT:
            return 0
        if mode == AddressingMode.IMMEDIATE:
            return self._fetch_byte()
        if mode == AddressingMode.IMMEDIATE16:
            return self._fetch_word()
        if mode == AddressingMode.DIRECT:
            return self._read_byte(self._fetch_byte())
        if mode == AddressingMode.DIRECT16:
            return self._read_word(self._fetch_byte())
        if mode == AddressingMode.EXTENDED:
            return self._read_byte(self._fetch_word())
        if mode == AddressingMode.EXTENDED16:
            return self._read_word(self._fetch_word())
        if mode == AddressingMode.INDEXED:
            offset = self._fetch_byte()
            address = (self.state.x + offset) & 0xFFFF
            return self._read_byte(address)
        if mode == AddressingMode.INDEXED16:
            offset = self._fetch_byte()
            address = (self.state.x + offset) & 0xFFFF
            return self._read_word(address)
        if mode == AddressingMode.RELATIVE:
            displacement = self._fetch_byte()
            if displacement & 0x80:
                displacement -= 0x100
            return displacement
        if mode == AddressingMode.RELATIVE_LONG:
            displacement = self._fetch_word()
            if displacement & 0x8000:
                displacement -= 0x10000
            return displacement
        raise CPUError(f"unsupported addressing mode: {mode}")

    def _fetch_word(self) -> int:
        hi = self._fetch_byte()
        lo = self._fetch_byte()
        return (hi << 8) | lo

    # ------------------------------------------------------------------
    # Memory helpers

    def _read_byte(self, address: int) -> int:
        return self.memory.load8(address & 0xFFFF)

    def _read_word(self, address: int) -> int:
        return self.memory.load16(address & 0xFFFF)

    def _write_byte(self, address: int, value: int) -> None:
        self.memory.store8(address & 0xFFFF, value & 0xFF)

    def _write_word(self, address: int, value: int) -> None:
        self.memory.store16(address & 0xFFFF, value & 0xFFFF)

    def _read_memory(self, instruction: Instruction) -> tuple[int, int]:
        address = self._resolve_address(instruction.mode)
        return address, self._read_byte(address)

    def _modify_memory(self, instruction: Instruction, mutate: Callable[[int], int]) -> int:
        address = self._resolve_address(instruction.mode)
        original = self._read_byte(address)
        result = mutate(original & 0xFF) & 0xFF
        self._write_byte(address, result)
        return result

    def _decode(self, opcode: int) -> Instruction:
        instruction = self.instruction_table[opcode]
        if instruction is None:
            raise IllegalOpcodeError(f"illegal opcode {opcode:#04x}")
        return instruction

    # ------------------------------------------------------------------
    # Addressing helpers

    def _resolve_address(self, mode: AddressingMode) -> int:
        if mode == AddressingMode.DIRECT:
            return self._fetch_byte()
        if mode == AddressingMode.INDEXED:
            offset = self._fetch_byte()
            return (self.state.x + offset) & 0xFFFF
        if mode == AddressingMode.EXTENDED:
            return self._fetch_word()
        raise CPUError(f"addressing mode {mode} cannot be resolved to an address")

    def _resolve_address_16(self, mode: AddressingMode) -> int:
        if mode == AddressingMode.DIRECT16:
            return self._fetch_byte()
        if mode == AddressingMode.INDEXED16:
            offset = self._fetch_byte()
            return (self.state.x + offset) & 0xFFFF
        if mode == AddressingMode.EXTENDED16:
            return self._fetch_word()
        raise CPUError(f"addressing mode {mode} cannot be resolved to 16-bit address")

    # ------------------------------------------------------------------
    # Register helpers

    def _get_accumulator(self, which: str) -> int:
        if which == "A":
            return self.state.a
        if which == "B":
            return self.state.b
        raise CPUError(f"unknown accumulator {which}")

    def _set_accumulator(self, which: str, value: int) -> None:
        value &= 0xFF
        if which == "A":
            self.state.a = value
        elif which == "B":
            self.state.b = value
        else:
            raise CPUError(f"unknown accumulator {which}")

    def _require_accumulator(self, instruction: Instruction) -> str:
        if instruction.accumulator is None:
            raise CPUError(f"instruction {instruction.mnemonic} missing accumulator metadata")
        return instruction.accumulator

    # ------------------------------------------------------------------
    # Flag helpers

    def _set_flag(self, flag: int, enabled: bool) -> None:
        if enabled:
            self.state.cc |= flag
        else:
            self.state.cc &= ~flag & 0xFF

    def _get_flag(self, flag: int) -> bool:
        return (self.state.cc & flag) != 0

    def _update_nz_flags(self, value: int) -> None:
        value &= 0xFF
        self._set_flag(FLAG_N, (value & 0x80) != 0)
        self._set_flag(FLAG_Z, value == 0)

    def _add8(self, x: int, y: int, *, carry_in: bool) -> int:
        x &= 0xFF
        y &= 0xFF
        carry = 1 if carry_in else 0
        total = x + y + carry
        result = total & 0xFF
        half = (x & 0x0F) + (y & 0x0F) + carry

        self._set_flag(FLAG_H, half > 0x0F)
        self._update_nz_flags(result)
        overflow = (~(x ^ y) & (x ^ result) & 0x80) != 0
        self._set_flag(FLAG_V, overflow)
        self._set_flag(FLAG_C, total > 0xFF)
        return result

    def _sub8(self, x: int, y: int, *, borrow_in: bool) -> int:
        x &= 0xFF
        y &= 0xFF
        borrow = 1 if borrow_in else 0
        total = x - y - borrow
        result = total & 0xFF
        half = (x & 0x0F) - (y & 0x0F) - borrow

        self._set_flag(FLAG_H, half < 0)
        self._update_nz_flags(result)
        overflow = ((x ^ y) & (x ^ result) & 0x80) != 0
        self._set_flag(FLAG_V, overflow)
        self._set_flag(FLAG_C, total < 0)
        return result

    def _branch(self, displacement: int) -> None:
        self.state.pc = (self.state.pc + displacement) & 0xFFFF

    # ------------------------------------------------------------------
    # 8-bit operation helpers

    def _op_inc(self, value: int) -> int:
        result = (value + 1) & 0xFF
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_V, value == 0x7F)
        return result

    def _op_dec(self, value: int) -> int:
        result = (value - 1) & 0xFF
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_V, value == 0x80)
        return result

    def _op_clr(self) -> int:
        self._set_flag(FLAG_N, False)
        self._set_flag(FLAG_Z, True)
        self._set_flag(FLAG_V, False)
        self._set_flag(FLAG_C, False)
        return 0

    def _op_com(self, value: int) -> int:
        result = (~value) & 0xFF
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_V, False)
        self._set_flag(FLAG_C, True)
        return result

    def _op_neg(self, value: int) -> int:
        result = (-value) & 0xFF
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_V, result == 0x80)
        self._set_flag(FLAG_C, result == 0x00)
        return result

    def _op_lsr(self, value: int) -> int:
        carry = value & 0x01
        result = (value >> 1) & 0xFF
        self._set_flag(FLAG_N, False)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_C, carry != 0)
        self._set_flag(FLAG_V, carry != 0)
        return result

    def _op_asr(self, value: int) -> int:
        carry = value & 0x01
        result = ((value >> 1) | (value & 0x80)) & 0xFF
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_C, carry != 0)
        self._set_flag(FLAG_V, ((result & 0x80) != 0) != (carry != 0))
        return result

    def _op_asl(self, value: int) -> int:
        total = (value << 1) & 0x1FF
        result = total & 0xFF
        carry = (total & 0x100) != 0
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_C, carry)
        self._set_flag(FLAG_V, ((result & 0x80) != 0) != carry)
        return result

    def _op_rol(self, value: int) -> int:
        carry_in = 1 if self._get_flag(FLAG_C) else 0
        total = ((value << 1) | carry_in) & 0x1FF
        result = total & 0xFF
        carry = (total & 0x100) != 0
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_C, carry)
        self._set_flag(FLAG_V, ((result & 0x80) != 0) != carry)
        return result

    def _op_ror(self, value: int) -> int:
        carry_in = 0x80 if self._get_flag(FLAG_C) else 0
        carry_out = value & 0x01
        result = ((value >> 1) | carry_in) & 0xFF
        self._set_flag(FLAG_N, (result & 0x80) != 0)
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_C, carry_out != 0)
        self._set_flag(FLAG_V, ((result & 0x80) != 0) != (carry_out != 0))
        return result

    def _tst(self, value: int) -> None:
        self._set_flag(FLAG_N, (value & 0x80) != 0)
        self._set_flag(FLAG_Z, (value & 0xFF) == 0)
        self._set_flag(FLAG_V, False)
        self._set_flag(FLAG_C, False)

    def _nim(self, x: int, y: int) -> int:
        result = (x & y) & 0xFF
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_N, result != 0)
        self._set_flag(FLAG_V, False)
        return result

    def _oim(self, x: int, y: int) -> int:
        result = (x | y) & 0xFF
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_N, result != 0)
        self._set_flag(FLAG_V, False)
        return result

    def _xim(self, x: int, y: int) -> int:
        result = (x ^ y) & 0xFF
        self._set_flag(FLAG_Z, result == 0)
        self._set_flag(FLAG_N, result != 0)
        self._set_flag(FLAG_V, False)
        return result

    def _tmm(self, x: int, y: int) -> None:
        if x == 0 or y == 0:
            self._set_flag(FLAG_N, False)
            self._set_flag(FLAG_Z, True)
            self._set_flag(FLAG_V, False)
        elif y == 0xFF:
            self._set_flag(FLAG_N, False)
            self._set_flag(FLAG_Z, False)
            self._set_flag(FLAG_V, True)
        else:
            self._set_flag(FLAG_N, True)
            self._set_flag(FLAG_Z, False)
            self._set_flag(FLAG_V, False)

    def _add16(self, x: int, y: int) -> int:
        total = (x & 0xFFFF) + (y & 0xFFFF)
        result = total & 0xFFFF
        self._set_flag(FLAG_N, (result & 0x8000) != 0)
        self._set_flag(FLAG_Z, result == 0)
        overflow = (~((x ^ y) & 0x8000) & ((x ^ result) & 0x8000)) != 0
        self._set_flag(FLAG_V, overflow)
        self._set_flag(FLAG_C, total > 0xFFFF)
        self._set_flag(FLAG_H, False)
        return result

    def _service_nmi(self) -> int:
        self._push_all_registers()
        self.state.pc = self._read_word(self.NMI_VECTOR)
        self.wai_latch = False
        return 12

    def _service_irq(self) -> int:
        self._push_all_registers()
        self._set_flag(FLAG_I, True)
        self.state.pc = self._read_word(self.IRQ_VECTOR)
        self.wai_latch = False
        return 12

    # ------------------------------------------------------------------
    # Stack helpers

    def _push_byte(self, value: int) -> None:
        self._write_byte(self.state.sp, value)
        self.state.sp = (self.state.sp - 1) & 0xFFFF

    def _push_word(self, value: int) -> None:
        address = (self.state.sp - 1) & 0xFFFF
        self._write_word(address, value)
        self.state.sp = (self.state.sp - 2) & 0xFFFF

    def _pull_byte(self) -> int:
        self.state.sp = (self.state.sp + 1) & 0xFFFF
        return self._read_byte(self.state.sp)

    def _pull_word(self) -> int:
        self.state.sp = (self.state.sp + 2) & 0xFFFF
        address = (self.state.sp - 1) & 0xFFFF
        return self._read_word(address)

    def _compose_cc(self) -> int:
        return self.state.cc & 0xFF

    def _apply_cc(self, value: int) -> None:
        self.state.cc = value & 0xFF

    def _push_all_registers(self) -> None:
        ccr = (self._compose_cc() | 0xC0) & 0xFF
        # MB8861は16ビットレジスタをスタックに積む際、下位バイトを先に書き込む。
        self._push_byte(self.state.pc & 0xFF)
        self._push_byte((self.state.pc >> 8) & 0xFF)
        self._push_byte(self.state.x & 0xFF)
        self._push_byte((self.state.x >> 8) & 0xFF)
        self._push_byte(self.state.a)
        self._push_byte(self.state.b)
        self._push_byte(ccr)

    def _pull_all_registers(self) -> None:
        ccr = self._pull_byte() & 0xFF
        self._apply_cc(ccr)
        self.state.b = self._pull_byte() & 0xFF
        self.state.a = self._pull_byte() & 0xFF
        x_hi = self._pull_byte() & 0xFF
        x_lo = self._pull_byte() & 0xFF
        self.state.x = ((x_hi << 8) | x_lo) & 0xFFFF
        pc_hi = self._pull_byte() & 0xFF
        pc_lo = self._pull_byte() & 0xFF
        self.state.pc = ((pc_hi << 8) | pc_lo) & 0xFFFF
