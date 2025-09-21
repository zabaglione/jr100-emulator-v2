"""Tests for the MB8861 CPU scaffold."""

from __future__ import annotations

import pytest

from pyjr100.bus import Memory, MemorySystem
from pyjr100.cpu import IllegalOpcodeError, MB8861
from pyjr100.cpu.core import FLAG_C, FLAG_H, FLAG_I, FLAG_N, FLAG_V, FLAG_Z


def make_cpu(entry_point: int) -> tuple[MB8861, Memory]:
    ms = MemorySystem()
    ms.allocate_space(0x10000)
    ram = Memory(0x0000, 0x10000)
    ms.register_memory(ram)
    ram.store16(0xFFFE, entry_point)

    cpu = MB8861(ms)
    cpu.reset()
    return cpu, ram


def read_flag(cpu: MB8861, flag: int) -> bool:
    return (cpu.state.cc & flag) != 0


def test_reset_loads_restart_vector() -> None:
    cpu, _ = make_cpu(0x1234)
    assert cpu.state.pc == 0x1234


def test_step_executes_nop() -> None:
    cpu, ram = make_cpu(0x2000)
    ram.store8(0x2000, 0x01)  # NOP

    cycles = cpu.step()

    assert cycles == 2
    assert cpu.state.pc == 0x2001
    assert cpu.cycle_count == 2


def test_illegal_opcode_raises() -> None:
    cpu, ram = make_cpu(0x3000)
    ram.store8(0x3000, 0x02)  # not yet implemented

    with pytest.raises(IllegalOpcodeError):
        cpu.step()


def test_ldaa_immediate_sets_flags() -> None:
    cpu, ram = make_cpu(0x4000)
    ram.store8(0x4000, 0x86)  # LDAA #imm
    ram.store8(0x4001, 0x80)

    cycles = cpu.step()

    assert cycles == 2
    assert cpu.state.a == 0x80
    assert read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)
    assert not read_flag(cpu, FLAG_V)


def test_ldaa_direct_reads_zero_page() -> None:
    cpu, ram = make_cpu(0x4100)
    ram.store8(0x4100, 0x96)  # LDAA direct
    ram.store8(0x4101, 0x40)
    ram.store8(0x0040, 0x12)

    cycles = cpu.step()

    assert cycles == 3
    assert cpu.state.a == 0x12
    assert cpu.state.pc == 0x4102


def test_staa_direct_writes_memory_and_flags() -> None:
    cpu, ram = make_cpu(0x4200)
    cpu.state.a = 0x55
    ram.store8(0x4200, 0x97)  # STAA direct
    ram.store8(0x4201, 0x50)

    cycles = cpu.step()

    assert cycles == 4
    assert ram.load8(0x0050) == 0x55
    assert not read_flag(cpu, FLAG_V)
    assert not read_flag(cpu, FLAG_Z)
    assert read_flag(cpu, FLAG_N) is False  # sign bit cleared


def test_inca_sets_overflow_when_wrapping_positive() -> None:
    cpu, ram = make_cpu(0x4300)
    cpu.state.a = 0x7F
    ram.store8(0x4300, 0x4C)  # INCA

    cycles = cpu.step()

    assert cycles == 2
    assert cpu.state.a == 0x80
    assert read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)
    assert read_flag(cpu, FLAG_V)


def test_deca_sets_overflow_on_negative_cross() -> None:
    cpu, ram = make_cpu(0x4400)
    cpu.state.a = 0x80
    ram.store8(0x4400, 0x4A)  # DECA

    cycles = cpu.step()

    assert cycles == 2
    assert cpu.state.a == 0x7F
    assert not read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)
    assert read_flag(cpu, FLAG_V)


def test_tab_transfers_a_to_b() -> None:
    cpu, ram = make_cpu(0x4500)
    cpu.state.a = 0xFF
    cpu.state.b = 0x00
    ram.store8(0x4500, 0x16)  # TAB

    cycles = cpu.step()

    assert cycles == 2
    assert cpu.state.b == 0xFF
    assert read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)
    assert not read_flag(cpu, FLAG_V)


def test_clra_clears_flags() -> None:
    cpu, ram = make_cpu(0x4510)
    cpu.state.a = 0x33
    cpu.state.cc |= FLAG_N | FLAG_C | FLAG_V
    ram.store8(0x4510, 0x4F)  # CLRA

    cpu.step()

    assert cpu.state.a == 0x00
    assert read_flag(cpu, FLAG_Z)
    assert not read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_C)


def test_coma_sets_carry_and_inverts() -> None:
    cpu, ram = make_cpu(0x4520)
    cpu.state.a = 0x55
    ram.store8(0x4520, 0x43)  # COMA

    cpu.step()

    assert cpu.state.a == 0xAA
    assert read_flag(cpu, FLAG_C)
    assert not read_flag(cpu, FLAG_V)


def test_negb_sets_overflow_on_0x80() -> None:
    cpu, ram = make_cpu(0x4530)
    cpu.state.b = 0x80
    ram.store8(0x4530, 0x50)  # NEGB

    cpu.step()

    assert cpu.state.b == 0x80
    assert read_flag(cpu, FLAG_V)
    assert read_flag(cpu, FLAG_C) is False


def test_rola_uses_carry_in() -> None:
    cpu, ram = make_cpu(0x4540)
    cpu.state.a = 0x80
    cpu.state.cc |= FLAG_C
    ram.store8(0x4540, 0x49)  # ROLA

    cpu.step()

    assert cpu.state.a == 0x01
    assert read_flag(cpu, FLAG_C)
    assert read_flag(cpu, FLAG_V)


def test_ror_memory_updates_flags_and_carry() -> None:
    cpu, ram = make_cpu(0x4550)
    cpu.state.x = 0x2000
    ram.store8(0x2003, 0x03)
    ram.store8(0x4550, 0x66)  # ROR ,X
    ram.store8(0x4551, 0x03)

    cpu.step()

    assert ram.load8(0x2003) == 0x01
    assert read_flag(cpu, FLAG_C)
    assert not read_flag(cpu, FLAG_N)


def test_clr_memory_indexed_zeroes_value() -> None:
    cpu, ram = make_cpu(0x4560)
    cpu.state.x = 0x2000
    ram.store8(0x2002, 0x7E)
    ram.store8(0x4560, 0x6F)  # CLR ,X
    ram.store8(0x4561, 0x02)

    cpu.step()

    assert ram.load8(0x2002) == 0x00
    assert read_flag(cpu, FLAG_Z)
    assert not read_flag(cpu, FLAG_N)


def test_neg_memory_indexed_sets_sign() -> None:
    cpu, ram = make_cpu(0x4570)
    cpu.state.x = 0x2100
    ram.store8(0x2101, 0x40)
    ram.store8(0x4570, 0x60)  # NEG ,X
    ram.store8(0x4571, 0x01)

    cpu.step()

    assert ram.load8(0x2101) == 0xC0
    assert read_flag(cpu, FLAG_N)


def test_lsr_memory_sets_carry_and_zero() -> None:
    cpu, ram = make_cpu(0x4580)
    cpu.state.x = 0x2200
    ram.store8(0x2204, 0x01)
    ram.store8(0x4580, 0x64)  # LSR ,X
    ram.store8(0x4581, 0x04)

    cpu.step()

    assert ram.load8(0x2204) == 0x00
    assert read_flag(cpu, FLAG_C)
    assert read_flag(cpu, FLAG_V)
    assert read_flag(cpu, FLAG_Z)


def test_tst_memory_sets_flags_without_writing() -> None:
    cpu, ram = make_cpu(0x4590)
    cpu.state.x = 0x2300
    ram.store8(0x2301, 0x80)
    ram.store8(0x4590, 0x6D)  # TST ,X
    ram.store8(0x4591, 0x01)

    cpu.step()

    assert ram.load8(0x2301) == 0x80
    assert read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)

def test_addb_immediate_sets_carry_when_overflowing() -> None:
    cpu, ram = make_cpu(0x4600)
    cpu.state.b = 0xF0
    ram.store8(0x4600, 0xCB)  # ADDB #imm
    ram.store8(0x4601, 0x20)

    cycles = cpu.step()

    assert cycles == 2
    assert cpu.state.b == 0x10
    assert read_flag(cpu, FLAG_C)
    assert not read_flag(cpu, FLAG_V)
    assert not read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)


def test_adda_sets_half_carry() -> None:
    cpu, ram = make_cpu(0x4610)
    cpu.state.a = 0x0F
    ram.store8(0x4610, 0x8B)  # ADDA #imm
    ram.store8(0x4611, 0x01)

    cpu.step()

    assert cpu.state.a == 0x10
    assert read_flag(cpu, FLAG_H)
    assert not read_flag(cpu, FLAG_C)


def test_adca_consumes_carry_in() -> None:
    cpu, ram = make_cpu(0x4620)
    cpu.state.a = 0x00
    cpu.state.cc |= FLAG_C
    ram.store8(0x4620, 0x89)  # ADCA #imm
    ram.store8(0x4621, 0x00)

    cpu.step()

    assert cpu.state.a == 0x01
    assert not read_flag(cpu, FLAG_C)


def test_suba_sets_borrow_flag() -> None:
    cpu, ram = make_cpu(0x4630)
    cpu.state.a = 0x05
    ram.store8(0x4630, 0x80)  # SUBA #imm
    ram.store8(0x4631, 0x07)

    cpu.step()

    assert cpu.state.a == 0xFE
    assert read_flag(cpu, FLAG_C)
    assert read_flag(cpu, FLAG_N)


def test_sbcb_includes_borrow_on_carry_set() -> None:
    cpu, ram = make_cpu(0x4640)
    cpu.state.b = 0x10
    cpu.state.cc |= FLAG_C
    ram.store8(0x4640, 0xC2)  # SBCB #imm
    ram.store8(0x4641, 0x05)

    cpu.step()

    assert cpu.state.b == 0x0A
    assert not read_flag(cpu, FLAG_C)


def test_anda_preserves_carry_flag() -> None:
    cpu, ram = make_cpu(0x4650)
    cpu.state.a = 0xAA
    cpu.state.cc |= FLAG_C
    ram.store8(0x4650, 0x84)  # ANDA #imm
    ram.store8(0x4651, 0x0F)

    cpu.step()

    assert cpu.state.a == 0x0A
    assert read_flag(cpu, FLAG_C)
    assert not read_flag(cpu, FLAG_V)


def test_orab_sets_zero_flag() -> None:
    cpu, ram = make_cpu(0x4660)
    cpu.state.b = 0x0F
    ram.store8(0x4660, 0xCA)  # ORAB #imm
    ram.store8(0x4661, 0xF0)

    cpu.step()

    assert cpu.state.b == 0xFF
    assert not read_flag(cpu, FLAG_Z)


def test_eora_clears_result_and_sets_zero() -> None:
    cpu, ram = make_cpu(0x4670)
    cpu.state.a = 0x5A
    ram.store8(0x4670, 0x88)  # EORA #imm
    ram.store8(0x4671, 0x5A)

    cpu.step()

    assert cpu.state.a == 0x00
    assert read_flag(cpu, FLAG_Z)
    assert not read_flag(cpu, FLAG_N)


def test_bne_taken_updates_program_counter() -> None:
    cpu, ram = make_cpu(0x4680)
    cpu.state.cc &= ~FLAG_Z
    ram.store8(0x4680, 0x26)  # BNE +2
    ram.store8(0x4681, 0x02)
    ram.store8(0x4682, 0x01)  # NOP (skipped)

    cycles = cpu.step()

    assert cycles == 4
    assert cpu.state.pc == 0x4684


def test_beq_not_taken_when_zero_clear() -> None:
    cpu, ram = make_cpu(0x4690)
    cpu.state.cc &= ~FLAG_Z
    ram.store8(0x4690, 0x27)  # BEQ +2
    ram.store8(0x4691, 0x02)

    cycles = cpu.step()

    assert cycles == 4
    assert cpu.state.pc == 0x4692


def test_bcc_branches_when_carry_clear() -> None:
    cpu, ram = make_cpu(0x46A0)
    cpu.state.cc &= ~FLAG_C
    ram.store8(0x46A0, 0x24)  # BCC +1
    ram.store8(0x46A1, 0x01)

    cpu.step()

    assert cpu.state.pc == 0x46A3


def test_bmi_branches_on_negative_flag() -> None:
    cpu, ram = make_cpu(0x46B0)
    cpu.state.cc |= FLAG_N
    ram.store8(0x46B0, 0x2B)  # BMI -2 (back to self)
    ram.store8(0x46B1, 0xFE)

    cpu.step()

    assert cpu.state.pc == 0x46B0


def test_bhi_branches_when_carry_and_zero_clear() -> None:
    cpu, ram = make_cpu(0x46C0)
    cpu.state.cc &= ~(FLAG_C | FLAG_Z)
    ram.store8(0x46C0, 0x22)  # BHI +2
    ram.store8(0x46C1, 0x02)

    cpu.step()

    assert cpu.state.pc == 0x46C4


def test_bls_branches_when_carry_set() -> None:
    cpu, ram = make_cpu(0x46D0)
    cpu.state.cc |= FLAG_C
    ram.store8(0x46D0, 0x23)  # BLS +1
    ram.store8(0x46D1, 0x01)

    cpu.step()

    assert cpu.state.pc == 0x46D3


def test_bvc_branches_when_overflow_clear() -> None:
    cpu, ram = make_cpu(0x46E0)
    cpu.state.cc &= ~FLAG_V
    ram.store8(0x46E0, 0x28)  # BVC +1
    ram.store8(0x46E1, 0x01)

    cpu.step()

    assert cpu.state.pc == 0x46E3


def test_bvs_branches_when_overflow_set() -> None:
    cpu, ram = make_cpu(0x46F0)
    cpu.state.cc |= FLAG_V
    ram.store8(0x46F0, 0x29)  # BVS +1
    ram.store8(0x46F1, 0x01)

    cpu.step()

    assert cpu.state.pc == 0x46F3


def test_bge_branch_when_n_equals_v() -> None:
    cpu, ram = make_cpu(0x4700)
    cpu.state.cc &= ~(FLAG_N | FLAG_V)
    ram.store8(0x4700, 0x2C)  # BGE +2
    ram.store8(0x4701, 0x02)

    cpu.step()

    assert cpu.state.pc == 0x4704


def test_blt_branch_when_sign_differs() -> None:
    cpu, ram = make_cpu(0x4710)
    cpu.state.cc |= FLAG_N
    cpu.state.cc &= ~FLAG_V
    ram.store8(0x4710, 0x2D)  # BLT +1
    ram.store8(0x4711, 0x01)

    cpu.step()

    assert cpu.state.pc == 0x4713


def test_bgt_requires_zero_clear_and_sign_equal() -> None:
    cpu, ram = make_cpu(0x4720)
    cpu.state.cc &= ~(FLAG_Z | FLAG_N | FLAG_V)
    ram.store8(0x4720, 0x2E)  # BGT +2
    ram.store8(0x4721, 0x02)

    cpu.step()

    assert cpu.state.pc == 0x4724


def test_ble_branches_when_zero_set() -> None:
    cpu, ram = make_cpu(0x4730)
    cpu.state.cc |= FLAG_Z
    ram.store8(0x4730, 0x2F)  # BLE +1
    ram.store8(0x4731, 0x01)

    cpu.step()

    assert cpu.state.pc == 0x4733


def test_bra_unconditional() -> None:
    cpu, ram = make_cpu(0x4740)
    ram.store8(0x4740, 0x20)  # BRA +2
    ram.store8(0x4741, 0x02)

    cpu.step()

    assert cpu.state.pc == 0x4744
def test_cmpb_sets_flags_without_modifying_register() -> None:
    cpu, ram = make_cpu(0x4700)
    cpu.state.b = 0x20
    ram.store8(0x4700, 0xC1)  # CMPB #imm
    ram.store8(0x4701, 0x10)

    cpu.step()

    assert cpu.state.b == 0x20
    assert not read_flag(cpu, FLAG_Z)
    assert not read_flag(cpu, FLAG_C)


def test_bitb_sets_zero_and_negative() -> None:
    cpu, ram = make_cpu(0x4710)
    cpu.state.b = 0x80
    ram.store8(0x4710, 0xC5)  # BITB #imm
    ram.store8(0x4711, 0x80)

    cpu.step()

    assert read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)


def test_ldx_immediate_sets_flags() -> None:
    cpu, ram = make_cpu(0x4720)
    ram.store8(0x4720, 0xCE)  # LDX #imm16
    ram.store8(0x4721, 0x80)
    ram.store8(0x4722, 0x00)

    cpu.step()

    assert cpu.state.x == 0x8000
    assert read_flag(cpu, FLAG_N)


def test_stx_direct_writes_word() -> None:
    cpu, ram = make_cpu(0x4730)
    cpu.state.x = 0x1234
    ram.store8(0x4730, 0xDF)  # STX direct
    ram.store8(0x4731, 0x20)

    cpu.step()

    assert ram.load16(0x0020) == 0x1234


def test_inx_wraps_and_sets_zero_flag() -> None:
    cpu, ram = make_cpu(0x4740)
    cpu.state.x = 0xFFFF
    ram.store8(0x4740, 0x08)  # INX

    cpu.step()

    assert cpu.state.x == 0x0000
    assert read_flag(cpu, FLAG_Z)


def test_cpx_sets_carry_on_less_than() -> None:
    cpu, ram = make_cpu(0x4750)
    cpu.state.x = 0x1000
    ram.store8(0x4750, 0x8C)  # CPX #imm16
    ram.store8(0x4751, 0x20)
    ram.store8(0x4752, 0x00)

    cpu.step()

    assert read_flag(cpu, FLAG_C)


def test_psha_pula_restores_value() -> None:
    cpu, ram = make_cpu(0x4760)
    original_sp = cpu.state.sp
    cpu.state.a = 0xAA
    ram.store8(0x4760, 0x36)  # PSHA
    ram.store8(0x4761, 0x4F)  # CLRA
    ram.store8(0x4762, 0x32)  # PULA

    cpu.step()  # PSHA
    assert cpu.state.sp == (original_sp - 1) & 0xFFFF
    cpu.step()  # CLRA
    cpu.step()  # PULA

    assert cpu.state.a == 0xAA
    assert cpu.state.sp == original_sp


def test_jsr_ext_and_rts_restore_flow() -> None:
    cpu, ram = make_cpu(0x4770)
    ram.store8(0x4770, 0xBD)  # JSR $6000
    ram.store8(0x4771, 0x60)
    ram.store8(0x4772, 0x00)
    ram.store8(0x6000, 0x01)  # NOP
    ram.store8(0x6001, 0x39)  # RTS

    cpu.step()
    assert cpu.state.pc == 0x6000
    saved_sp = cpu.state.sp
    cpu.step()  # NOP
    cpu.step()  # RTS

    assert cpu.state.pc == 0x4773
    assert cpu.state.sp == (saved_sp + 2) & 0xFFFF


def test_bsr_pushes_return_address() -> None:
    cpu, ram = make_cpu(0x4780)
    initial_sp = cpu.state.sp
    ram.store8(0x4780, 0x8D)  # BSR +2
    ram.store8(0x4781, 0x02)
    ram.store8(0x4782, 0x01)  # NOP
    ram.store8(0x4784, 0x39)  # RTS

    cpu.step()
    assert cpu.state.pc == 0x4784
    assert cpu.state.sp == (initial_sp - 2) & 0xFFFF
    return_addr = ram.load16((cpu.state.sp + 1) & 0xFFFF)
    assert return_addr == 0x4782

    cpu.step()
    assert cpu.state.pc == 0x4782


def test_tap_tpa_exchange_condition_codes() -> None:
    cpu, ram = make_cpu(0x4790)
    cpu.state.cc = FLAG_C | FLAG_Z
    ram.store8(0x4790, 0x07)  # TPA
    ram.store8(0x4791, 0x86)  # LDAA #$03
    ram.store8(0x4792, 0x03)
    ram.store8(0x4793, 0x06)  # TAP

    cpu.step()
    assert cpu.state.a & 0xC0 == 0xC0
    assert cpu.state.a & 0x3F == (FLAG_C | FLAG_Z)

    cpu.step()
    cpu.step()

    assert read_flag(cpu, FLAG_V)
    assert read_flag(cpu, FLAG_C)
    assert not read_flag(cpu, FLAG_Z)


def test_daa_adjusts_bcd_addition() -> None:
    cpu, ram = make_cpu(0x47A0)
    ram.store8(0x47A0, 0x86)  # LDAA #$45
    ram.store8(0x47A1, 0x45)
    ram.store8(0x47A2, 0x8B)  # ADDA #$38
    ram.store8(0x47A3, 0x38)
    ram.store8(0x47A4, 0x19)  # DAA

    cpu.step()
    cpu.step()
    cpu.step()

    assert cpu.state.a == 0x83
    assert read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)


def test_nim_sets_zero_flag_when_and_clears_bit() -> None:
    cpu, ram = make_cpu(0x47B0)
    cpu.state.x = 0x5000
    ram.store8(0x5003, 0xF0)
    ram.store8(0x47B0, 0x71)  # NIM
    ram.store8(0x47B1, 0x0F)
    ram.store8(0x47B2, 0x03)

    cpu.step()

    assert ram.load8(0x5003) == 0x00
    assert read_flag(cpu, FLAG_Z)
    assert not read_flag(cpu, FLAG_N)


def test_oim_sets_negative_flag_when_bit_set() -> None:
    cpu, ram = make_cpu(0x47C0)
    cpu.state.x = 0x5010
    ram.store8(0x5011, 0x10)
    ram.store8(0x47C0, 0x72)  # OIM
    ram.store8(0x47C1, 0x80)
    ram.store8(0x47C2, 0x01)

    cpu.step()

    assert ram.load8(0x5011) == 0x90
    assert read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)


def test_xim_clears_bits_using_xor() -> None:
    cpu, ram = make_cpu(0x47D0)
    cpu.state.x = 0x5020
    ram.store8(0x5025, 0xAA)
    ram.store8(0x47D0, 0x75)  # XIM
    ram.store8(0x47D1, 0x0F)
    ram.store8(0x47D2, 0x05)

    cpu.step()

    assert ram.load8(0x5025) == 0xA5
    assert not read_flag(cpu, FLAG_Z)


def test_tmm_sets_flags_without_memory_write() -> None:
    cpu, ram = make_cpu(0x47E0)
    cpu.state.x = 0x5030
    ram.store8(0x5032, 0xFF)
    ram.store8(0x47E0, 0x7B)  # TMM
    ram.store8(0x47E1, 0x10)
    ram.store8(0x47E2, 0x02)

    cpu.step()

    assert ram.load8(0x5032) == 0xFF
    assert not read_flag(cpu, FLAG_N)
    assert not read_flag(cpu, FLAG_Z)
    assert read_flag(cpu, FLAG_V)


def test_adx_immediate_adds_unsigned_byte() -> None:
    cpu, ram = make_cpu(0x47F0)
    cpu.state.x = 0x1000
    ram.store8(0x47F0, 0xEC)  # ADX #$10
    ram.store8(0x47F1, 0x10)

    cpu.step()

    assert cpu.state.x == 0x1010
    assert not read_flag(cpu, FLAG_Z)


def test_adx_extended_reads_word_memory() -> None:
    cpu, ram = make_cpu(0x4800)
    cpu.state.x = 0x0001
    ram.store8(0x4800, 0xFC)  # ADX $6000
    ram.store8(0x4801, 0x60)
    ram.store8(0x4802, 0x00)
    ram.store16(0x6000, 0x00FF)

    cpu.step()

    assert cpu.state.x == 0x0100

def test_wai_sets_latch() -> None:
    cpu, ram = make_cpu(0x47B0)
    ram.store8(0x47B0, 0x3E)  # WAI

    cycles = cpu.step()
    assert cpu.wai_latch
    assert cycles == 9
    pc_after = cpu.state.pc
    assert cpu.step() == 0
    assert cpu.state.pc == pc_after


def test_irq_services_and_wakes_from_wai() -> None:
    cpu, ram = make_cpu(0x4800)
    ram.store16(0xFFF8, 0x5200)
    ram.store8(0x4800, 0x3E)  # WAI
    ram.store8(0x4801, 0x01)  # NOP (should not execute until after IRQ sequence)
    ram.store8(0x5200, 0x01)  # NOP at IRQ handler

    assert cpu.step() == 9  # execute WAI
    assert cpu.wai_latch

    cpu.request_irq()
    cycles = cpu.step()

    assert cycles == 14  # 12 for IRQ service + 2 for NOP
    assert cpu.state.pc == 0x5201
    assert not cpu.wai_latch
    assert read_flag(cpu, FLAG_I)


def test_irq_ignored_when_interrupts_disabled() -> None:
    cpu, ram = make_cpu(0x4810)
    ram.store8(0x4810, 0x01)  # NOP
    cpu.state.cc |= FLAG_I

    cpu.request_irq()
    cycles = cpu.step()

    assert cycles == 2
    assert cpu.state.pc == 0x4811
    assert cpu.irq_pending  # still waiting until I cleared


def test_nmi_services_even_when_masked() -> None:
    cpu, ram = make_cpu(0x4820)
    ram.store16(0xFFFC, 0x5300)
    ram.store8(0x4820, 0x3E)  # WAI
    ram.store8(0x5300, 0x01)  # NOP
    cpu.state.cc |= FLAG_I

    cpu.step()  # enter WAI
    cpu.request_nmi()
    cycles = cpu.step()

    assert cycles == 14
    assert cpu.state.pc == 0x5301
    assert not cpu.wai_latch
    assert cpu.nmi_pending is False


def test_swi_pushes_registers_and_vectors() -> None:
    cpu, ram = make_cpu(0x47C0)
    ram.store16(0xFFFA, 0x5000)
    cpu.state.a = 0x12
    cpu.state.b = 0x34
    cpu.state.x = 0x5678
    cpu.state.cc = FLAG_N | FLAG_C
    ram.store8(0x47C0, 0x3F)  # SWI

    cpu.step()

    assert cpu.state.pc == 0x5000
    sp = cpu.state.sp
    assert ram.load8((sp + 1) & 0xFFFF) & 0x3F == (FLAG_N | FLAG_C)
    assert ram.load8((sp + 2) & 0xFFFF) == 0x34
    assert ram.load8((sp + 3) & 0xFFFF) == 0x12
    assert ram.load16((sp + 4) & 0xFFFF) == 0x5678
    assert read_flag(cpu, FLAG_I)


def test_rti_restores_cpu_state() -> None:
    cpu, ram = make_cpu(0x47D0)
    cpu.state.sp = 0x01F8
    ram.store8(0x01F9, FLAG_C | FLAG_V)
    ram.store8(0x01FA, 0x44)
    ram.store8(0x01FB, 0x55)
    ram.store16(0x01FC, 0x6789)
    ram.store16(0x01FE, 0x47E0)
    ram.store8(0x47D0, 0x3B)  # RTI

    cpu.step()

    assert cpu.state.a == 0x55
    assert cpu.state.b == 0x44
    assert cpu.state.x == 0x6789
    assert cpu.state.pc == 0x47E0
    assert read_flag(cpu, FLAG_C)
    assert read_flag(cpu, FLAG_V)
    assert cpu.state.sp == 0x01FF
