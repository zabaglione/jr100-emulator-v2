import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jr100_port.cpu.mb8861 import MB8861  # noqa: E402


class DummyMemory:
    def __init__(self, data: bytes) -> None:
        self.data = bytearray(data)

    def load8(self, address: int) -> int:
        return self.data[address & 0xFFFF]

    def store8(self, address: int, value: int) -> None:
        self.data[address & 0xFFFF] = value & 0xFF


@pytest.fixture()
def cpu() -> MB8861:
    memory = DummyMemory(bytes([0x00] * 0x10000))
    return MB8861(memory)


def test_nop_advances_pc_and_cycles(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x01

    cycles = cpu.step()

    assert cpu.pc == 0x0001
    assert cycles == 2
    assert cpu.cc is False
    assert cpu.cz is False


def test_lda_immediate_loads_accumulator(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x86
    cpu.memory.data[0x0001] = 0x42

    cycles = cpu.step()

    assert cpu.a == 0x42
    assert cpu.pc == 0x0002
    assert cycles == 2
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False


def test_sta_direct_stores_value(cpu: MB8861) -> None:
    cpu.a = 0x99
    cpu.memory.data[0x0000] = 0x97
    cpu.memory.data[0x0001] = 0x10

    cycles = cpu.step()

    assert cpu.memory.data[0x0010] == 0x99
    assert cpu.pc == 0x0002
    assert cycles == 4
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False


def test_ldaa_direct_reads_zero_page(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x96
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0040] = 0xF0

    cycles = cpu.step()

    assert cpu.a == 0xF0
    assert cpu.pc == 0x0002
    assert cycles == 3
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False


def test_ldaa_indexed_uses_ix_plus_offset(cpu: MB8861) -> None:
    cpu.ix = 0x1200
    cpu.memory.data[0x0000] = 0xA6
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x1210] = 0x00

    cycles = cpu.step()

    assert cpu.a == 0x00
    assert cpu.pc == 0x0002
    assert cycles == 5
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cv is False


def test_ldaa_extended_reads_absolute_address(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0xB6
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x0002] = 0x20
    cpu.memory.data[0x1020] = 0x7F

    cycles = cpu.step()

    assert cpu.a == 0x7F
    assert cpu.pc == 0x0003
    assert cycles == 4
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False


def test_ldab_immediate_loads_register(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0xC6
    cpu.memory.data[0x0001] = 0x80

    cycles = cpu.step()

    assert cpu.b == 0x80
    assert cpu.pc == 0x0002
    assert cycles == 2
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False


def test_ldab_direct_reads_memory(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0xD6
    cpu.memory.data[0x0001] = 0xFF
    cpu.memory.data[0x00FF] = 0x00

    cycles = cpu.step()

    assert cpu.b == 0x00
    assert cpu.pc == 0x0002
    assert cycles == 3
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cv is False


def test_ldab_indexed_reads_memory(cpu: MB8861) -> None:
    cpu.ix = 0x2200
    cpu.memory.data[0x0000] = 0xE6
    cpu.memory.data[0x0001] = 0x05
    cpu.memory.data[0x2205] = 0x11

    cycles = cpu.step()

    assert cpu.b == 0x11
    assert cpu.pc == 0x0002
    assert cycles == 5
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False


def test_ldab_extended_reads_memory(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0xF6
    cpu.memory.data[0x0001] = 0x12
    cpu.memory.data[0x0002] = 0x34
    cpu.memory.data[0x1234] = 0x40

    cycles = cpu.step()

    assert cpu.b == 0x40
    assert cpu.pc == 0x0003
    assert cycles == 4
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False


def test_stab_direct_stores_b_register(cpu: MB8861) -> None:
    cpu.b = 0x55
    cpu.memory.data[0x0000] = 0xD7
    cpu.memory.data[0x0001] = 0x80

    cycles = cpu.step()

    assert cpu.memory.data[0x0080] == 0x55
    assert cpu.pc == 0x0002
    assert cycles == 4
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False


def test_stab_indexed_stores_value(cpu: MB8861) -> None:
    cpu.b = 0x00
    cpu.ix = 0x0100
    cpu.memory.data[0x0000] = 0xE7
    cpu.memory.data[0x0001] = 0xFE

    cycles = cpu.step()

    assert cpu.memory.data[0x0100 + 0xFE] == 0x00
    assert cpu.pc == 0x0002
    assert cycles == 6
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cv is False


def test_stab_extended_stores_value(cpu: MB8861) -> None:
    cpu.b = 0xFF
    cpu.memory.data[0x0000] = 0xF7
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0002] = 0x10

    cycles = cpu.step()

    assert cpu.memory.data[0x2010] == 0xFF
    assert cpu.pc == 0x0003
    assert cycles == 5
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False


def test_anda_immediate_clears_zero(cpu: MB8861) -> None:
    cpu.a = 0xF0
    cpu.memory.data[0x0000] = 0x84
    cpu.memory.data[0x0001] = 0x0F

    cycles = cpu.step()

    assert cpu.a == 0x00
    assert cpu.cz is True
    assert cpu.cn is False
    assert cpu.cv is False
    assert cpu.pc == 0x0002
    assert cycles == 2


def test_anda_direct_sets_negative(cpu: MB8861) -> None:
    cpu.a = 0xF0
    cpu.memory.data[0x0000] = 0x94
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x0010] = 0x80

    cycles = cpu.step()

    assert cpu.a == 0x80
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cpu.pc == 0x0002
    assert cycles == 3


def test_andb_indexed_reads_memory(cpu: MB8861) -> None:
    cpu.b = 0xF5
    cpu.ix = 0x1100
    cpu.memory.data[0x0000] = 0xE4
    cpu.memory.data[0x0001] = 0x04
    cpu.memory.data[0x1104] = 0x0F

    cycles = cpu.step()

    assert cpu.b == 0x05
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cpu.pc == 0x0002
    assert cycles == 5


def test_eora_extended_xors_value(cpu: MB8861) -> None:
    cpu.a = 0x55
    cpu.memory.data[0x0000] = 0xB8
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0002] = 0x30
    cpu.memory.data[0x4030] = 0xFF

    cycles = cpu.step()

    assert cpu.a == 0xAA
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cpu.pc == 0x0003
    assert cycles == 4


def test_eorb_immediate_zero_result(cpu: MB8861) -> None:
    cpu.b = 0x3C
    cpu.memory.data[0x0000] = 0xC8
    cpu.memory.data[0x0001] = 0x3C

    cycles = cpu.step()

    assert cpu.b == 0x00
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cv is False
    assert cpu.pc == 0x0002
    assert cycles == 2


def test_oraa_direct_sets_flags(cpu: MB8861) -> None:
    cpu.a = 0x10
    cpu.memory.data[0x0000] = 0x9A
    cpu.memory.data[0x0001] = 0x22
    cpu.memory.data[0x0022] = 0x80

    cycles = cpu.step()

    assert cpu.a == 0x90
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cpu.pc == 0x0002
    assert cycles == 3


def test_orab_extended_sets_result(cpu: MB8861) -> None:
    cpu.b = 0x00
    cpu.memory.data[0x0000] = 0xFA
    cpu.memory.data[0x0001] = 0x60
    cpu.memory.data[0x0002] = 0x50
    cpu.memory.data[0x6050] = 0x01

    cycles = cpu.step()

    assert cpu.b == 0x01
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cpu.pc == 0x0003
    assert cycles == 4


def test_bita_immediate_sets_zero_flag(cpu: MB8861) -> None:
    cpu.a = 0xF0
    cpu.memory.data[0x0000] = 0x85
    cpu.memory.data[0x0001] = 0x0F

    cycles = cpu.step()

    assert cpu.a == 0xF0
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cv is False
    assert cpu.cc is False
    assert cycles == 2


def test_bita_direct_sets_negative(cpu: MB8861) -> None:
    cpu.a = 0xFF
    cpu.memory.data[0x0000] = 0x95
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0040] = 0x80

    cycles = cpu.step()

    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 3


def test_bitb_indexed_uses_memory(cpu: MB8861) -> None:
    cpu.b = 0xFF
    cpu.ix = 0x3000
    cpu.memory.data[0x0000] = 0xE5
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x3010] = 0x80

    cycles = cpu.step()

    assert cpu.b == 0xFF
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 5


def test_bitb_extended_zero_result(cpu: MB8861) -> None:
    cpu.b = 0x0F
    cpu.memory.data[0x0000] = 0xF5
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0002] = 0x10
    cpu.memory.data[0x1020] = 0xF0

    cycles = cpu.step()

    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cv is False
    assert cycles == 4


def test_psha_pushes_a_to_stack(cpu: MB8861) -> None:
    cpu.a = 0x42
    cpu.sp = 0x2000
    cpu.memory.data[0x0000] = 0x36

    cycles = cpu.step()

    assert cpu.sp == 0x1FFF
    assert cpu.memory.data[0x2000] == 0x42
    assert cycles == 4


def test_pshb_pushes_b(cpu: MB8861) -> None:
    cpu.b = 0x99
    cpu.sp = 0x1000
    cpu.memory.data[0x0000] = 0x37

    cycles = cpu.step()

    assert cpu.sp == 0x0FFF
    assert cpu.memory.data[0x1000] == 0x99
    assert cycles == 4


def test_pula_restores_a(cpu: MB8861) -> None:
    cpu.sp = 0x0FFE
    cpu.memory.data[0x0FFF] = 0x55
    cpu.memory.data[0x0000] = 0x32

    cycles = cpu.step()

    assert cpu.a == 0x55
    assert cpu.sp == 0x0FFF
    assert cycles == 4


def test_pulb_restores_b(cpu: MB8861) -> None:
    cpu.sp = 0x1FFE
    cpu.memory.data[0x1FFF] = 0xAA
    cpu.memory.data[0x0000] = 0x33

    cycles = cpu.step()

    assert cpu.b == 0xAA
    assert cpu.sp == 0x1FFF
    assert cycles == 4


def test_tsx_transfers_sp_plus_one_to_index(cpu: MB8861) -> None:
    cpu.sp = 0x1234
    cpu.memory.data[0x0000] = 0x30

    cycles = cpu.step()

    assert cpu.ix == 0x1235
    assert cpu.sp == 0x1234
    assert cycles == 4


def test_txs_transfers_index_minus_one_to_sp(cpu: MB8861) -> None:
    cpu.ix = 0x4000
    cpu.memory.data[0x0000] = 0x35

    cycles = cpu.step()

    assert cpu.sp == 0x3FFF
    assert cpu.ix == 0x4000
    assert cycles == 4


def test_cba_compares_registers(cpu: MB8861) -> None:
    cpu.a = 0x30
    cpu.b = 0x30
    cpu.memory.data[0x0000] = 0x11

    cycles = cpu.step()

    assert cpu.cz is True
    assert cpu.cc is False
    assert cycles == 2


def test_daa_adjusts_bcd(cpu: MB8861) -> None:
    cpu.a = 0x9A
    cpu.ch = False
    cpu.cc = False
    cpu.memory.data[0x0000] = 0x19

    cycles = cpu.step()

    assert cpu.a == 0x00
    assert cpu.cc is True
    assert cpu.cz is True
    assert cpu.cv is True
    assert cycles == 2


def test_aba_adds_b_to_a(cpu: MB8861) -> None:
    cpu.a = 0x12
    cpu.b = 0x34
    cpu.memory.data[0x0000] = 0x1B

    cycles = cpu.step()

    assert cpu.a == 0x46
    assert cpu.cc is False
    assert cycles == 2


def test_clc_clears_carry(cpu: MB8861) -> None:
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x0C

    cycles = cpu.step()

    assert cpu.cc is False
    assert cycles == 2


def test_cli_clears_irq_mask(cpu: MB8861) -> None:
    cpu.ci = True
    cpu.memory.data[0x0000] = 0x0E

    cycles = cpu.step()

    assert cpu.ci is False
    assert cycles == 2


def test_clv_clears_overflow(cpu: MB8861) -> None:
    cpu.cv = True
    cpu.memory.data[0x0000] = 0x0A

    cycles = cpu.step()

    assert cpu.cv is False
    assert cycles == 2


def test_sec_sets_carry(cpu: MB8861) -> None:
    cpu.cc = False
    cpu.memory.data[0x0000] = 0x0B

    cycles = cpu.step()

    assert cpu.cc is True
    assert cycles == 2


def test_sei_sets_irq_mask(cpu: MB8861) -> None:
    cpu.ci = False
    cpu.memory.data[0x0000] = 0x0F

    cycles = cpu.step()

    assert cpu.ci is True
    assert cycles == 2


def test_sev_sets_overflow(cpu: MB8861) -> None:
    cpu.cv = False
    cpu.memory.data[0x0000] = 0x0D

    cycles = cpu.step()

    assert cpu.cv is True
    assert cycles == 2

def test_irq_then_nmi_sequence(cpu: MB8861) -> None:
    cpu.sp = 0x1FFF
    cpu.memory.data[0x0000] = 0x3E
    cpu.memory.data[0xFFF8] = 0x01
    cpu.memory.data[0xFFF9] = 0x20  # IRQ -> 0x0120
    cpu.memory.data[0xFFFC] = 0x02
    cpu.memory.data[0xFFFD] = 0x30  # NMI -> 0x0230

    cpu.step()
    cpu.request_irq()
    cpu.step()
    cpu.request_nmi()

    cpu.step()

    assert cpu.pc == 0x0230
    assert cpu.sp == 0x1FF1
    assert cpu.waiting is False

def test_swi_sets_irq_mask(cpu: MB8861) -> None:
    cpu.pc = 0x0000
    cpu.sp = 0x1FFF
    cpu.memory.data[0x0000] = 0x3F
    cpu.memory.data[0xFFFA] = 0x12
    cpu.memory.data[0xFFFB] = 0x34

    cpu.step()

    assert cpu.ci is True
    assert cpu.pc == 0x1234

    entry_high = cpu.memory.data[0x1FF9]
    assert entry_high & 0x40


def test_nmi_preempts_irq_during_wai(cpu: MB8861) -> None:
    cpu.sp = 0x1FFF
    cpu.memory.data[0x0000] = 0x3E
    cpu.memory.data[0xFFF8] = 0x01  # IRQ vector high byte
    cpu.memory.data[0xFFF9] = 0x20  # low byte -> 0x0120
    cpu.memory.data[0xFFFC] = 0x02  # NMI vector high byte
    cpu.memory.data[0xFFFD] = 0x30  # low byte -> 0x0230

    cpu.step()
    cpu.request_irq()
    cpu.request_nmi()

    cycles = cpu.step()

    assert cpu.pc == 0x0230
    assert cpu.sp == 0x1FF8
    assert cycles == 12


def test_irq_then_rti_returns_to_wait_loop(cpu: MB8861) -> None:
    cpu.sp = 0x1FFF
    cpu.memory.data[0x0000] = 0x3E
    cpu.memory.data[0x0001] = 0x3E
    cpu.memory.data[0xFFF8] = 0x00  # IRQ handler at 0x0010
    cpu.memory.data[0xFFF9] = 0x10
    cpu.memory.data[0x0010] = 0x3B  # RTI

    cpu.step()
    cpu.request_irq()

    cpu.step()
    cycles = cpu.step()

    assert cycles == 10
    assert cpu.pc == 0x0001
    assert cpu.waiting is False
    assert cpu.sp == 0x1FFF

def test_wai_remains_waiting_without_interrupt(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x3E

    cpu.step()
    idle = cpu.step()

    assert cpu.waiting is True
    assert idle == 1
    assert cpu.pc == 0x0001

def test_tab_transfers_a_to_b(cpu: MB8861) -> None:
    cpu.a = 0x80
    cpu.b = 0x00
    cpu.memory.data[0x0000] = 0x16

    cycles = cpu.step()

    assert cpu.b == 0x80
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 2


def test_tba_transfers_b_to_a(cpu: MB8861) -> None:
    cpu.b = 0x01
    cpu.a = 0x00
    cpu.memory.data[0x0000] = 0x17

    cycles = cpu.step()

    assert cpu.a == 0x01
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 2


def test_tap_sets_flags_from_a(cpu: MB8861) -> None:
    cpu.a = 0x2B  # 0b0010_1011 -> CH, CN, CV, CC set
    cpu.memory.data[0x0000] = 0x06

    cycles = cpu.step()

    assert cpu.ch is True
    assert cpu.ci is False
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is True
    assert cpu.cc is True
    assert cycles == 2


def test_tpa_packs_flags_into_a(cpu: MB8861) -> None:
    cpu.ch = True
    cpu.ci = False
    cpu.cn = True
    cpu.cz = True
    cpu.cv = False
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x07

    cycles = cpu.step()

    assert cpu.a == 0xC0 | 0x20 | 0x08 | 0x04 | 0x01  # 0xED
    assert cycles == 2


def test_dex_decrements_ix_and_sets_zero(cpu: MB8861) -> None:
    cpu.ix = 0x0001
    cpu.memory.data[0x0000] = 0x09

    cycles = cpu.step()

    assert cpu.ix == 0x0000
    assert cpu.cz is True
    assert cycles == 4


def test_inx_increments_ix(cpu: MB8861) -> None:
    cpu.ix = 0xFFFF
    cpu.memory.data[0x0000] = 0x08

    cycles = cpu.step()

    assert cpu.ix == 0x0000
    assert cpu.cz is True
    assert cycles == 4


def test_wai_sets_waiting(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x3E
    cpu.memory.data[0x0001] = 0x01

    cycles = cpu.step()

    assert cycles == 9
    assert cpu.waiting is True
    assert cpu.pc == 0x0001

    idle_cycles = cpu.step()

    assert idle_cycles == 1
    assert cpu.waiting is True
    assert cpu.pc == 0x0001


def test_wai_waits_until_nmi(cpu: MB8861) -> None:
    cpu.sp = 0x1FFF
    cpu.memory.data[0x0000] = 0x3E
    cpu.memory.data[0xFFFC] = 0x56
    cpu.memory.data[0xFFFD] = 0x78

    cpu.step()
    cpu.request_nmi()

    cycles = cpu.step()

    assert cpu.waiting is False
    assert cpu.pc == 0x5678
    assert cpu.sp == 0x1FF8
    assert cycles == 12


def test_swi_followed_by_rti_restores_state(cpu: MB8861) -> None:
    cpu.pc = 0x0100
    cpu.sp = 0x1FFE
    cpu.a = 0x11
    cpu.b = 0x22
    cpu.ix = 0x3344
    cpu.ch = True
    cpu.ci = False
    cpu.cn = True
    cpu.cz = False
    cpu.cv = True
    cpu.cc = False

    cpu.memory.data[0x0100] = 0x3F
    cpu.memory.data[0x0101] = 0x3B
    cpu.memory.data[0xFFFA] = 0x20
    cpu.memory.data[0xFFFB] = 0x00
    cpu.memory.data[0x2000] = 0x3B

    cpu.step()
    cycles = cpu.step()

    assert cycles == 10
    assert cpu.pc == 0x0101
    assert cpu.sp == 0x1FFE
    assert cpu.a == 0x11
    assert cpu.b == 0x22
    assert cpu.ix == 0x3344
    assert cpu.ch is True
    assert cpu.ci is False
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is True
    assert cpu.cc is False

def test_wai_resumes_on_irq(cpu: MB8861) -> None:
    cpu.sp = 0x1FFF
    cpu.memory.data[0x0000] = 0x3E
    cpu.memory.data[0xFFF8] = 0x12
    cpu.memory.data[0xFFF9] = 0x34

    cpu.step()
    cpu.request_irq()

    cycles = cpu.step()

    assert cpu.waiting is False
    assert cpu.pc == 0x1234
    assert cpu.sp == 0x1FF8


def test_swi_pushes_registers_and_sets_vector(cpu: MB8861) -> None:
    cpu.pc = 0x0100
    cpu.sp = 0x1FFF
    cpu.a = 0x56
    cpu.b = 0x78
    cpu.ix = 0x9ABC
    cpu.ch = True
    cpu.ci = False
    cpu.cn = True
    cpu.cz = False
    cpu.cv = False
    cpu.cc = True

    cpu.memory.data[0x0100] = 0x3F
    cpu.memory.data[0xFFFA] = 0x20
    cpu.memory.data[0xFFFB] = 0x40

    cycles = cpu.step()

    assert cycles == 12
    assert cpu.pc == 0x2040
    assert cpu.ci is True
    assert cpu.sp == 0x1FF8

    assert cpu.memory.data[0x1FF9] == 0xE9
    assert cpu.memory.data[0x1FFA] == 0x78
    assert cpu.memory.data[0x1FFB] == 0x56
    assert cpu.memory.data[0x1FFC] == 0x9A
    assert cpu.memory.data[0x1FFD] == 0xBC
    assert cpu.memory.data[0x1FFE] == 0x01
    assert cpu.memory.data[0x1FFF] == 0x01


def test_nim_ind_masks_memory(cpu: MB8861) -> None:
    cpu.ix = 0x3000
    cpu.memory.data[0x0000] = 0x71
    cpu.memory.data[0x0001] = 0x0F
    cpu.memory.data[0x0002] = 0x05
    cpu.memory.data[0x3005] = 0xF0

    cycles = cpu.step()

    assert cycles == 8
    assert cpu.memory.data[0x3005] == 0x00
    assert cpu.cz is True
    assert cpu.cn is False


def test_oim_ind_sets_bits(cpu: MB8861) -> None:
    cpu.ix = 0x2100
    cpu.memory.data[0x0000] = 0x72
    cpu.memory.data[0x0001] = 0x0F
    cpu.memory.data[0x0002] = 0x10
    cpu.memory.data[0x2110] = 0x80

    cycles = cpu.step()

    assert cycles == 8
    assert cpu.memory.data[0x2110] == 0x8F
    assert cpu.cn is True
    assert cpu.cz is False


def test_xim_ind_xors_bits(cpu: MB8861) -> None:
    cpu.ix = 0x2200
    cpu.memory.data[0x0000] = 0x75
    cpu.memory.data[0x0001] = 0xF0
    cpu.memory.data[0x0002] = 0x20
    cpu.memory.data[0x2220] = 0xFF

    cycles = cpu.step()

    assert cycles == 8
    assert cpu.memory.data[0x2220] == 0x0F
    assert cpu.cn is True
    assert cpu.cz is False


def test_tmm_ind_with_zero_operand_sets_zero_flag(cpu: MB8861) -> None:
    cpu.ix = 0x2300
    cpu.memory.data[0x0000] = 0x7B
    cpu.memory.data[0x0001] = 0x00
    cpu.memory.data[0x0002] = 0x10
    cpu.memory.data[0x2310] = 0x12

    cycles = cpu.step()

    assert cycles == 7
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cv is False


def test_tmm_ind_with_full_mask_sets_overflow(cpu: MB8861) -> None:
    cpu.ix = 0x2400
    cpu.memory.data[0x0000] = 0x7B
    cpu.memory.data[0x0001] = 0x34
    cpu.memory.data[0x0002] = 0x20
    cpu.memory.data[0x2420] = 0xFF

    cycles = cpu.step()

    assert cycles == 7
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is True


def test_tmm_ind_general_case_sets_negative(cpu: MB8861) -> None:
    cpu.ix = 0x2500
    cpu.memory.data[0x0000] = 0x7B
    cpu.memory.data[0x0001] = 0x01
    cpu.memory.data[0x0002] = 0x04
    cpu.memory.data[0x2504] = 0x7F

    cycles = cpu.step()

    assert cycles == 7
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False


def test_des_decrements_stack_pointer(cpu: MB8861) -> None:
    cpu.sp = 0x0100
    cpu.memory.data[0x0000] = 0x34

    cycles = cpu.step()

    assert cpu.sp == 0x00FF
    assert cycles == 4


def test_ins_increments_stack_pointer(cpu: MB8861) -> None:
    cpu.sp = 0x1FFE
    cpu.memory.data[0x0000] = 0x31

    cycles = cpu.step()

    assert cpu.sp == 0x1FFF
    assert cycles == 4


def test_asla_sets_carry_and_overflow(cpu: MB8861) -> None:
    cpu.a = 0x80
    cpu.memory.data[0x0000] = 0x48

    cycles = cpu.step()

    assert cpu.a == 0x00
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cc is True
    assert cpu.cv is True
    assert cycles == 2


def test_rola_includes_previous_carry(cpu: MB8861) -> None:
    cpu.a = 0x7F
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x49

    cycles = cpu.step()

    assert cpu.a == 0xFF
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cc is False
    assert cpu.cv is True
    assert cycles == 2


def test_rora_rotates_through_carry(cpu: MB8861) -> None:
    cpu.a = 0x02
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x46

    cycles = cpu.step()

    assert cpu.a == 0x81
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cc is False
    assert cpu.cv is True
    assert cycles == 2


def test_lsr_indexed_shifts_memory(cpu: MB8861) -> None:
    cpu.ix = 0x2000
    cpu.memory.data[0x0000] = 0x64
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x2010] = 0x01

    cycles = cpu.step()

    assert cpu.memory.data[0x2010] == 0x00
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cc is True
    assert cycles == 7


def test_com_extended_sets_cc(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x73
    cpu.memory.data[0x0001] = 0x30
    cpu.memory.data[0x0002] = 0x20
    cpu.memory.data[0x3020] = 0x55

    cycles = cpu.step()

    assert cpu.memory.data[0x3020] == 0xAA
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cc is True
    assert cpu.cv is False
    assert cycles == 6


def test_neg_indexed_sets_flags(cpu: MB8861) -> None:
    cpu.ix = 0x1800
    cpu.memory.data[0x0000] = 0x60
    cpu.memory.data[0x0001] = 0x05
    cpu.memory.data[0x1805] = 0x80

    cycles = cpu.step()

    assert cpu.memory.data[0x1805] == 0x80
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cc is False
    assert cpu.cv is True
    assert cycles == 7


def test_inc_extended_sets_overflow(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x7C
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0002] = 0x10
    cpu.memory.data[0x4010] = 0x7F

    cycles = cpu.step()

    assert cpu.memory.data[0x4010] == 0x80
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is True
    assert cycles == 6


def test_dec_indexed_sets_overflow(cpu: MB8861) -> None:
    cpu.ix = 0x2200
    cpu.memory.data[0x0000] = 0x6A
    cpu.memory.data[0x0001] = 0x04
    cpu.memory.data[0x2204] = 0x80

    cycles = cpu.step()

    assert cpu.memory.data[0x2204] == 0x7F
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is True
    assert cycles == 7


def test_clra_clears_accumulator(cpu: MB8861) -> None:
    cpu.a = 0x12
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x4F

    cycles = cpu.step()

    assert cpu.a == 0x00
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cc is False
    assert cycles == 2


def test_clr_extended_stores_zero(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x7F
    cpu.memory.data[0x0001] = 0x55
    cpu.memory.data[0x0002] = 0x66
    cpu.memory.data[0x5566] = 0xAA

    cycles = cpu.step()

    assert cpu.memory.data[0x5566] == 0x00
    assert cpu.cn is False
    assert cpu.cz is True
    assert cpu.cc is False
    assert cycles == 6


def test_tsta_updates_flags_and_clears_carry(cpu: MB8861) -> None:
    cpu.a = 0x80
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x4D

    cycles = cpu.step()

    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cc is False
    assert cpu.cv is False
    assert cycles == 2


def test_tst_extended_updates_flags(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x7D
    cpu.memory.data[0x0001] = 0x12
    cpu.memory.data[0x0002] = 0x34
    cpu.memory.data[0x1234] = 0xFF

    cycles = cpu.step()

    assert cpu.memory.data[0x1234] == 0xFF
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cc is False
    assert cpu.cv is False
    assert cycles == 6


def test_adda_immediate_sets_flags(cpu: MB8861) -> None:
    cpu.a = 0x7F
    cpu.memory.data[0x0000] = 0x8B
    cpu.memory.data[0x0001] = 0x01

    cycles = cpu.step()

    assert cpu.a == 0x80
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cc is False
    assert cpu.cv is True
    assert cpu.ch is True
    assert cycles == 2


def test_adca_immediate_uses_carry(cpu: MB8861) -> None:
    cpu.a = 0x10
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x89
    cpu.memory.data[0x0001] = 0x0F

    cycles = cpu.step()

    assert cpu.a == 0x20
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cpu.ch is False
    assert cycles == 2


def test_adda_direct_adds_memory(cpu: MB8861) -> None:
    cpu.a = 0x10
    cpu.memory.data[0x0000] = 0x9B
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0020] = 0x05

    cycles = cpu.step()

    assert cpu.a == 0x15
    assert cpu.ch is False
    assert cpu.cc is False
    assert cycles == 3


def test_adda_indexed_sets_half_carry(cpu: MB8861) -> None:
    cpu.a = 0x0F
    cpu.ix = 0x1200
    cpu.memory.data[0x0000] = 0xAB
    cpu.memory.data[0x0001] = 0x03
    cpu.memory.data[0x1203] = 0x02

    cycles = cpu.step()

    assert cpu.a == 0x11
    assert cpu.ch is True
    assert cpu.cc is False
    assert cycles == 5


def test_adda_extended_sets_carry(cpu: MB8861) -> None:
    cpu.a = 0xF0
    cpu.memory.data[0x0000] = 0xBB
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x4000] = 0x20

    cycles = cpu.step()

    assert cpu.a == 0x10
    assert cpu.cc is True
    assert cpu.cn is False
    assert cycles == 4


def test_adca_direct_consumes_carry(cpu: MB8861) -> None:
    cpu.a = 0x20
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x99
    cpu.memory.data[0x0001] = 0x30
    cpu.memory.data[0x0030] = 0x05

    cycles = cpu.step()

    assert cpu.a == 0x26
    assert cpu.cc is False
    assert cpu.ch is False
    assert cycles == 3


def test_adca_indexed_sets_carry(cpu: MB8861) -> None:
    cpu.a = 0xFF
    cpu.cc = False
    cpu.ix = 0x2000
    cpu.memory.data[0x0000] = 0xA9
    cpu.memory.data[0x0001] = 0x04
    cpu.memory.data[0x2004] = 0x02

    cycles = cpu.step()

    assert cpu.a == 0x01
    assert cpu.cc is True
    assert cpu.cz is False
    assert cycles == 5


def test_adca_extended_sets_half_carry(cpu: MB8861) -> None:
    cpu.a = 0x09
    cpu.cc = False
    cpu.memory.data[0x0000] = 0xB9
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x1000] = 0x07

    cycles = cpu.step()

    assert cpu.a == 0x10
    assert cpu.ch is True
    assert cycles == 4


def test_addb_immediate_updates_register(cpu: MB8861) -> None:
    cpu.b = 0x20
    cpu.memory.data[0x0000] = 0xCB
    cpu.memory.data[0x0001] = 0x10

    cycles = cpu.step()

    assert cpu.b == 0x30
    assert cpu.ch is False
    assert cpu.cc is False
    assert cycles == 2


def test_addb_direct_sets_half_carry(cpu: MB8861) -> None:
    cpu.b = 0x0F
    cpu.memory.data[0x0000] = 0xDB
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0040] = 0x01

    cycles = cpu.step()

    assert cpu.b == 0x10
    assert cpu.ch is True
    assert cycles == 3


def test_addb_indexed_sets_carry(cpu: MB8861) -> None:
    cpu.b = 0xFE
    cpu.ix = 0x2200
    cpu.memory.data[0x0000] = 0xEB
    cpu.memory.data[0x0001] = 0x05
    cpu.memory.data[0x2205] = 0x04

    cycles = cpu.step()

    assert cpu.b == 0x02
    assert cpu.cc is True
    assert cycles == 5


def test_addb_extended_sets_negative(cpu: MB8861) -> None:
    cpu.b = 0x40
    cpu.memory.data[0x0000] = 0xFB
    cpu.memory.data[0x0001] = 0x80
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x8000] = 0x80

    cycles = cpu.step()

    assert cpu.b == 0xC0
    assert cpu.cn is True
    assert cycles == 4


def test_adcb_direct_includes_carry(cpu: MB8861) -> None:
    cpu.b = 0x10
    cpu.cc = True
    cpu.memory.data[0x0000] = 0xD9
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0020] = 0x0F

    cycles = cpu.step()

    assert cpu.b == 0x20
    assert cpu.cc is False
    assert cycles == 3


def test_adcb_indexed_sets_carry(cpu: MB8861) -> None:
    cpu.b = 0xFF
    cpu.cc = False
    cpu.ix = 0x1000
    cpu.memory.data[0x0000] = 0xE9
    cpu.memory.data[0x0001] = 0x04
    cpu.memory.data[0x1004] = 0x02

    cycles = cpu.step()

    assert cpu.b == 0x01
    assert cpu.cc is True
    assert cycles == 5


def test_adcb_extended_sets_half_carry(cpu: MB8861) -> None:
    cpu.b = 0x09
    cpu.cc = False
    cpu.memory.data[0x0000] = 0xF9
    cpu.memory.data[0x0001] = 0x30
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x3000] = 0x07

    cycles = cpu.step()

    assert cpu.b == 0x10
    assert cpu.ch is True
    assert cycles == 4


def test_adx_immediate_adds_unsigned_offset(cpu: MB8861) -> None:
    cpu.ix = 0x1000
    cpu.memory.data[0x0000] = 0xEC
    cpu.memory.data[0x0001] = 0x20

    cycles = cpu.step()

    assert cpu.ix == 0x1020
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cc is False
    assert cpu.cv is False
    assert cycles == 3


def test_adx_immediate_wraps_to_zero(cpu: MB8861) -> None:
    cpu.ix = 0xFFFF
    cpu.memory.data[0x0000] = 0xEC
    cpu.memory.data[0x0001] = 0x01

    cycles = cpu.step()

    assert cpu.ix == 0x0000
    assert cpu.cz is True
    assert cpu.cc is True
    assert cpu.cn is False
    assert cycles == 3


def test_adx_extended_adds_absolute_word(cpu: MB8861) -> None:
    cpu.ix = 0x1234
    cpu.memory.data[0x0000] = 0xFC
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x4000] = 0x00  # high byte
    cpu.memory.data[0x4001] = 0x10  # low byte

    cycles = cpu.step()

    assert cpu.ix == 0x1244
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cc is False
    assert cycles == 7


def test_sbca_immediate_sets_borrow(cpu: MB8861) -> None:
    cpu.a = 0x00
    cpu.cc = False
    cpu.memory.data[0x0000] = 0x82
    cpu.memory.data[0x0001] = 0x01

    cycles = cpu.step()

    assert cpu.a == 0xFF
    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 2


def test_sbca_immediate_consumes_previous_borrow(cpu: MB8861) -> None:
    cpu.a = 0x10
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x82
    cpu.memory.data[0x0001] = 0x05

    cycles = cpu.step()

    assert cpu.a == 0x0A
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 2


def test_cmpa_immediate_sets_flags(cpu: MB8861) -> None:
    cpu.a = 0x20
    cpu.memory.data[0x0000] = 0x81
    cpu.memory.data[0x0001] = 0x20

    cpu.step()

    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is True


def test_cmpa_immediate_negative_result(cpu: MB8861) -> None:
    cpu.a = 0x10
    cpu.memory.data[0x0000] = 0x81
    cpu.memory.data[0x0001] = 0x20

    cpu.step()

    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False


def test_cmpa_direct_sets_zero(cpu: MB8861) -> None:
    cpu.a = 0x55
    cpu.memory.data[0x0000] = 0x91
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x0010] = 0x55

    cycles = cpu.step()

    assert cpu.cz is True
    assert cpu.cc is False
    assert cpu.cn is False
    assert cycles == 3


def test_cmpa_indexed_sets_negative(cpu: MB8861) -> None:
    cpu.a = 0x10
    cpu.ix = 0x3000
    cpu.memory.data[0x0000] = 0xA1
    cpu.memory.data[0x0001] = 0x05
    cpu.memory.data[0x3005] = 0x40

    cycles = cpu.step()

    assert cpu.cn is True
    assert cpu.cc is True
    assert cpu.cz is False
    assert cycles == 5


def test_cmpa_extended_sets_carry(cpu: MB8861) -> None:
    cpu.a = 0x00
    cpu.memory.data[0x0000] = 0xB1
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x2000] = 0x01

    cycles = cpu.step()

    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False
    assert cycles == 4


def test_suba_immediate_updates_accumulator(cpu: MB8861) -> None:
    cpu.a = 0x50
    cpu.memory.data[0x0000] = 0x80
    cpu.memory.data[0x0001] = 0x10

    cycles = cpu.step()

    assert cpu.a == 0x40
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 2


def test_sba_implied_subtracts_b_from_a(cpu: MB8861) -> None:
    cpu.a = 0x30
    cpu.b = 0x0A
    cpu.memory.data[0x0000] = 0x10

    cycles = cpu.step()

    assert cpu.a == 0x26
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 2


def test_suba_direct_reads_zero_page(cpu: MB8861) -> None:
    cpu.a = 0x22
    cpu.memory.data[0x0000] = 0x90
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0040] = 0x02

    cycles = cpu.step()

    assert cpu.a == 0x20
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cycles == 3


def test_suba_indexed_reads_relative_to_ix(cpu: MB8861) -> None:
    cpu.a = 0x10
    cpu.ix = 0x1200
    cpu.memory.data[0x0000] = 0xA0
    cpu.memory.data[0x0001] = 0x04
    cpu.memory.data[0x1204] = 0x01

    cycles = cpu.step()

    assert cpu.a == 0x0F
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cycles == 5


def test_suba_extended_reads_absolute(cpu: MB8861) -> None:
    cpu.a = 0x05
    cpu.memory.data[0x0000] = 0xB0
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x2000] = 0x08

    cycles = cpu.step()

    assert cpu.a == 0xFD
    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False
    assert cycles == 4


def test_sbca_direct_consumes_carry(cpu: MB8861) -> None:
    cpu.a = 0x10
    cpu.cc = True
    cpu.memory.data[0x0000] = 0x92
    cpu.memory.data[0x0001] = 0x30
    cpu.memory.data[0x0030] = 0x01

    cycles = cpu.step()

    assert cpu.a == 0x0E
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cycles == 3


def test_sbca_indexed_sets_borrow(cpu: MB8861) -> None:
    cpu.a = 0x00
    cpu.cc = False
    cpu.ix = 0x0100
    cpu.memory.data[0x0000] = 0xA2
    cpu.memory.data[0x0001] = 0x02
    cpu.memory.data[0x0102] = 0x01

    cycles = cpu.step()

    assert cpu.a == 0xFF
    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False
    assert cycles == 5


def test_sbca_extended_uses_absolute_address(cpu: MB8861) -> None:
    cpu.a = 0x02
    cpu.cc = False
    cpu.memory.data[0x0000] = 0xB2
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x4000] = 0x03

    cycles = cpu.step()

    assert cpu.a == 0xFF
    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False
    assert cycles == 4


def test_cmpb_immediate_sets_flags(cpu: MB8861) -> None:
    cpu.b = 0x30
    cpu.memory.data[0x0000] = 0xC1
    cpu.memory.data[0x0001] = 0x40

    cpu.step()

    assert cpu.b == 0x30
    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False


def test_subb_immediate_updates_accumulator(cpu: MB8861) -> None:
    cpu.b = 0x20
    cpu.memory.data[0x0000] = 0xC0
    cpu.memory.data[0x0001] = 0x05

    cycles = cpu.step()

    assert cpu.b == 0x1B
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 2


def test_bne_branches_when_zero_clear(cpu: MB8861) -> None:
    cpu.cz = False
    cpu.memory.data[0x0100] = 0x26
    cpu.memory.data[0x0101] = 0xFE

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0100
    assert cycles == 4


def test_bne_not_taken_when_zero_set(cpu: MB8861) -> None:
    cpu.cz = True
    cpu.memory.data[0x0100] = 0x26
    cpu.memory.data[0x0101] = 0x02

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0102
    assert cycles == 4


def test_cmpb_direct(cpu: MB8861) -> None:
    cpu.b = 0x40
    cpu.memory.data[0x0000] = 0xD1
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x0010] = 0x20

    cpu.step()

    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False


def test_cmpb_indexed(cpu: MB8861) -> None:
    cpu.b = 0x10
    cpu.ix = 0x2000
    cpu.memory.data[0x0000] = 0xE1
    cpu.memory.data[0x0001] = 0x05
    cpu.memory.data[0x2005] = 0x10

    cpu.step()

    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is True


def test_cmpb_extended(cpu: MB8861) -> None:
    cpu.b = 0x00
    cpu.memory.data[0x0000] = 0xF1
    cpu.memory.data[0x0001] = 0x80
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x8000] = 0xFF

    cpu.step()

    assert cpu.cc is True
    assert cpu.cn is False
    assert cpu.cz is False


def test_subb_direct(cpu: MB8861) -> None:
    cpu.b = 0x10
    cpu.memory.data[0x0000] = 0xD0
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x0010] = 0x04

    cpu.step()

    assert cpu.b == 0x0C
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False


def test_subb_indexed(cpu: MB8861) -> None:
    cpu.b = 0x05
    cpu.ix = 0x3000
    cpu.memory.data[0x0000] = 0xE0
    cpu.memory.data[0x0001] = 0x02
    cpu.memory.data[0x3002] = 0x06

    cpu.step()

    assert cpu.b == 0xFF
    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False


def test_subb_extended(cpu: MB8861) -> None:
    cpu.b = 0x80
    cpu.memory.data[0x0000] = 0xF0
    cpu.memory.data[0x0001] = 0x40
    cpu.memory.data[0x0002] = 0x00
    cpu.memory.data[0x4000] = 0x7F

    cpu.step()

    assert cpu.b == 0x01
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False


def test_sbcb_immediate_uses_borrow(cpu: MB8861) -> None:
    cpu.b = 0x05
    cpu.cc = True
    cpu.memory.data[0x0000] = 0xC2
    cpu.memory.data[0x0001] = 0x02

    cycles = cpu.step()

    assert cpu.b == 0x02
    assert cpu.cc is False
    assert cpu.cn is False
    assert cpu.cz is False
    assert cycles == 2


def test_sbcb_direct_sets_borrow(cpu: MB8861) -> None:
    cpu.b = 0x01
    cpu.cc = False
    cpu.memory.data[0x0000] = 0xD2
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x0010] = 0x02

    cycles = cpu.step()

    assert cpu.b == 0xFF
    assert cpu.cc is True
    assert cpu.cn is True
    assert cpu.cz is False
    assert cycles == 3


def test_jmp_extended_sets_program_counter(cpu: MB8861) -> None:
    cpu.memory.data[0x0100] = 0x7E
    cpu.memory.data[0x0101] = 0x20
    cpu.memory.data[0x0102] = 0x00

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x2000
    assert cycles == 3


def test_jmp_indexed_uses_ix_plus_offset(cpu: MB8861) -> None:
    cpu.ix = 0x1800
    cpu.memory.data[0x0100] = 0x6E
    cpu.memory.data[0x0101] = 0x10

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x1810
    assert cycles == 4


@pytest.mark.parametrize(
    "opcode, flags, expected",
    [
        (0x22, {"cc": False, "cz": False}, 0x0108),  # BHI taken
        (0x23, {"cc": True, "cz": False}, 0x0108),   # BLS taken (carry set)
        (0x25, {"cc": True}, 0x0108),                 # BCS taken
        (0x28, {"cv": False}, 0x0108),                # BVC taken
        (0x29, {"cv": True}, 0x0108),                 # BVS taken
        (0x2A, {"cn": False}, 0x0108),                # BPL taken
        (0x2D, {"cn": True, "cv": False}, 0x0108),  # BLT taken (N xor V)
        (0x2E, {"cz": False, "cn": False, "cv": False}, 0x0108),  # BGT taken
    ],
)
def test_branch_new_conditions_taken(cpu: MB8861, opcode: int, flags: dict[str, bool], expected: int) -> None:
    cpu.memory.data[0x0100] = opcode
    cpu.memory.data[0x0101] = 0x06
    cpu.pc = 0x0100
    cpu.cc = flags.get("cc", False)
    cpu.cz = flags.get("cz", False)
    cpu.cn = flags.get("cn", False)
    cpu.cv = flags.get("cv", False)

    cycles = cpu.step()

    assert cpu.pc == expected
    assert cycles == 4


@pytest.mark.parametrize(
    "opcode, flags",
    [
        (0x22, {"cc": True, "cz": False}),
        (0x23, {"cc": False, "cz": False}),
        (0x25, {"cc": False}),
        (0x28, {"cv": True}),
        (0x29, {"cv": False}),
        (0x2A, {"cn": True}),
        (0x2D, {"cn": False, "cv": False}),
        (0x2E, {"cz": True, "cn": False, "cv": False}),
    ],
)
def test_branch_new_conditions_not_taken(cpu: MB8861, opcode: int, flags: dict[str, bool]) -> None:
    cpu.memory.data[0x0100] = opcode
    cpu.memory.data[0x0101] = 0x06
    cpu.pc = 0x0100
    cpu.cc = flags.get("cc", False)
    cpu.cz = flags.get("cz", False)
    cpu.cn = flags.get("cn", False)
    cpu.cv = flags.get("cv", False)

    cycles = cpu.step()

    assert cpu.pc == 0x0102
    assert cycles == 4


def test_ldx_indexed_offset_wrap(cpu: MB8861) -> None:
    cpu.ix = 0x2000
    cpu.memory.data[0x0000] = 0xEE
    cpu.memory.data[0x0001] = 0xFF
    cpu.memory.data[0x20FF] = 0x12
    cpu.memory.data[0x2100] = 0x34

    cycles = cpu.step()

    assert cpu.ix == 0x1234
    assert cycles == 6


def test_stx_indexed_offset_wrap(cpu: MB8861) -> None:
    cpu.ix = 0x4321
    cpu.memory.data[0x0000] = 0xEF
    cpu.memory.data[0x0001] = 0xFE

    cycles = cpu.step()

    offset_base = (0xFE & 0xFF)
    index_addr = (0x4321 + offset_base) & 0xFFFF
    assert cpu.memory.data[index_addr] == 0x43
    assert cpu.memory.data[(index_addr + 1) & 0xFFFF] == 0x21
    assert cycles == 7


def test_bra_relative(cpu: MB8861) -> None:
    cpu.memory.data[0x0100] = 0x20
    cpu.memory.data[0x0101] = 0x05

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0107
    assert cycles == 4


def test_beq_taken(cpu: MB8861) -> None:
    cpu.cz = True
    cpu.memory.data[0x0100] = 0x27
    cpu.memory.data[0x0101] = 0x05

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0107
    assert cycles == 4


def test_beq_not_taken(cpu: MB8861) -> None:
    cpu.cz = False
    cpu.memory.data[0x0100] = 0x27
    cpu.memory.data[0x0101] = 0x05

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0102
    assert cycles == 4


def test_bmi_taken(cpu: MB8861) -> None:
    cpu.cn = True
    cpu.memory.data[0x0100] = 0x2B
    cpu.memory.data[0x0101] = 0xF0

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x00F2
    assert cycles == 4


def test_bmi_not_taken(cpu: MB8861) -> None:
    cpu.cn = False
    cpu.memory.data[0x0100] = 0x2B
    cpu.memory.data[0x0101] = 0xF0

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0102
    assert cycles == 4


def test_bge_taken(cpu: MB8861) -> None:
    cpu.cn = False
    cpu.cv = False
    cpu.memory.data[0x0100] = 0x2C
    cpu.memory.data[0x0101] = 0x06

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0108
    assert cycles == 4


def test_bge_not_taken(cpu: MB8861) -> None:
    cpu.cn = False
    cpu.cv = True
    cpu.memory.data[0x0100] = 0x2C
    cpu.memory.data[0x0101] = 0x06

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0102
    assert cycles == 4


def test_ble_taken(cpu: MB8861) -> None:
    cpu.cz = True
    cpu.cn = False
    cpu.cv = True
    cpu.memory.data[0x0100] = 0x2F
    cpu.memory.data[0x0101] = 0xF0

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x00F2
    assert cycles == 4


def test_ble_not_taken(cpu: MB8861) -> None:
    cpu.cz = False
    cpu.cn = False
    cpu.cv = False
    cpu.memory.data[0x0100] = 0x2F
    cpu.memory.data[0x0101] = 0xF0

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0102
    assert cycles == 4


def test_ldx_immediate_sets_flags(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0xCE
    cpu.memory.data[0x0001] = 0x80
    cpu.memory.data[0x0002] = 0x00

    cycles = cpu.step()

    assert cpu.ix == 0x8000
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 3


def test_lds_immediate_loads_stack_pointer(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x8E
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0002] = 0x00

    cycles = cpu.step()

    assert cpu.sp == 0x2000
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 3


def test_lds_direct_reads_zero_page(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0x9E
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x0010] = 0x12
    cpu.memory.data[0x0011] = 0x34

    cycles = cpu.step()

    assert cpu.sp == 0x1234
    assert cpu.cn is False
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 4


def test_sts_direct_stores_stack_pointer(cpu: MB8861) -> None:
    cpu.sp = 0x4321
    cpu.ix = 0x1111
    cpu.memory.data[0x0000] = 0x9F
    cpu.memory.data[0x0001] = 0x40

    cycles = cpu.step()

    assert cpu.memory.data[0x0040] == 0x43
    assert cpu.memory.data[0x0041] == 0x21
    assert cpu.cn == ((cpu.ix & 0x8000) != 0)
    assert cpu.cz == (cpu.ix == 0)
    assert cpu.cv is False
    assert cycles == 5


def test_cpx_dir_sets_zero(cpu: MB8861) -> None:
    cpu.ix = 0x1234
    cpu.memory.data[0x0000] = 0x9C
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0020] = 0x12
    cpu.memory.data[0x0021] = 0x34

    cpu.step()

    assert cpu.cz is True
    assert cpu.cn is False


def test_stx_extended_writes_memory(cpu: MB8861) -> None:
    cpu.ix = 0x55AA
    cpu.memory.data[0x0000] = 0xFF
    cpu.memory.data[0x0001] = 0x80
    cpu.memory.data[0x0002] = 0x10

    cpu.step()

    assert cpu.memory.data[0x8010] == 0x55
    assert cpu.memory.data[0x8011] == 0xAA

def test_bge_taken(cpu: MB8861) -> None:
    cpu.cn = False
    cpu.cv = False
    cpu.memory.data[0x0100] = 0x2C
    cpu.memory.data[0x0101] = 0x06

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0108
    assert cycles == 4


def test_bge_not_taken(cpu: MB8861) -> None:
    cpu.cn = False
    cpu.cv = True
    cpu.memory.data[0x0100] = 0x2C
    cpu.memory.data[0x0101] = 0x06

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0102
    assert cycles == 4


def test_ble_taken(cpu: MB8861) -> None:
    cpu.cz = True
    cpu.cn = False
    cpu.cv = True
    cpu.memory.data[0x0100] = 0x2F
    cpu.memory.data[0x0101] = 0xF0

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x00F2
    assert cycles == 4


def test_ble_not_taken(cpu: MB8861) -> None:
    cpu.cz = False
    cpu.cn = False
    cpu.cv = False
    cpu.memory.data[0x0100] = 0x2F
    cpu.memory.data[0x0101] = 0xF0

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0102
    assert cycles == 4


def test_ldx_immediate_sets_flags(cpu: MB8861) -> None:
    cpu.memory.data[0x0000] = 0xCE
    cpu.memory.data[0x0001] = 0x80
    cpu.memory.data[0x0002] = 0x00

    cycles = cpu.step()

    assert cpu.ix == 0x8000
    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cycles == 3


def test_cpx_dir_sets_zero(cpu: MB8861) -> None:
    cpu.ix = 0x1234
    cpu.memory.data[0x0000] = 0x9C
    cpu.memory.data[0x0001] = 0x20
    cpu.memory.data[0x0020] = 0x12
    cpu.memory.data[0x0021] = 0x34

    cpu.step()

    assert cpu.cz is True
    assert cpu.cn is False


def test_stx_extended_writes_memory(cpu: MB8861) -> None:
    cpu.ix = 0x55AA
    cpu.memory.data[0x0000] = 0xFF
    cpu.memory.data[0x0001] = 0x80
    cpu.memory.data[0x0002] = 0x10

    cycles = cpu.step()

    assert cpu.memory.data[0x8010] == 0x55
    assert cpu.memory.data[0x8011] == 0xAA
    assert cycles == 6

def test_bsr_pushes_return_address(cpu: MB8861) -> None:
    cpu.sp = 0x2000
    cpu.memory.data[0x0100] = 0x8D
    cpu.memory.data[0x0101] = 0x05

    cpu.pc = 0x0100
    cycles = cpu.step()

    assert cpu.pc == 0x0107
    assert cpu.sp == 0x1FFE
    assert cpu.memory.data[0x1FFF] == 0x01
    assert cpu.memory.data[0x2000] == 0x02
    assert cycles == 8


def test_jsr_ext_pushes_pc(cpu: MB8861) -> None:
    cpu.sp = 0x1FF0
    cpu.memory.data[0x0000] = 0xBD
    cpu.memory.data[0x0001] = 0x80
    cpu.memory.data[0x0002] = 0x20

    cycles = cpu.step()

    assert cpu.pc == 0x8020
    assert cpu.sp == 0x1FEE
    assert cpu.memory.data[0x1FEF] == 0x00
    assert cpu.memory.data[0x1FF0] == 0x03
    assert cycles == 9


def test_jsr_indexed_pushes_pc(cpu: MB8861) -> None:
    cpu.ix = 0x4000
    cpu.sp = 0x1FF0
    cpu.memory.data[0x0000] = 0xAD
    cpu.memory.data[0x0001] = 0x10
    cpu.memory.data[0x4010] = 0x12
    cpu.memory.data[0x4011] = 0x34

    cycles = cpu.step()

    assert cpu.pc == 0x4010
    assert cpu.sp == 0x1FEE
    assert cpu.memory.data[0x1FEF] == 0x00
    assert cpu.memory.data[0x1FF0] == 0x02
    assert cycles == 8


def test_rts_pops_return_address(cpu: MB8861) -> None:
    cpu.sp = 0x1FFE
    cpu.memory.data[0x1FFF] = 0x00
    cpu.memory.data[0x2000] = 0x10
    cpu.memory.data[0x0000] = 0x39

    cycles = cpu.step()

    assert cpu.pc == 0x0010
    assert cpu.sp == 0x2000
    assert cycles == 5


def test_jsr_rts_roundtrip(cpu: MB8861) -> None:
    mem = cpu.memory.data
    cpu.sp = 0x1FF0
    mem[0x0000] = 0xBD
    mem[0x0001] = 0x80
    mem[0x0002] = 0x20
    mem[0x8020] = 0x39

    cpu.step()
    cpu.step()

    assert cpu.pc == 0x0003
    assert cpu.sp == 0x1FF0


def test_rti_pops_registers(cpu: MB8861) -> None:
    mem = cpu.memory.data
    cpu.sp = 0x1FF0
    mem[0x1FF1] = 0x20  # CCR bits (H set)
    mem[0x1FF2] = 0xAA  # B
    mem[0x1FF3] = 0x55  # A
    mem[0x1FF4] = 0x12  # IX high
    mem[0x1FF5] = 0x56  # IX low
    mem[0x1FF6] = 0x12  # PC high
    mem[0x1FF7] = 0x34  # PC low
    cpu.memory.data[0x0000] = 0x3B

    cycles = cpu.step()

    assert cpu.pc == 0x1234
    assert cpu.a == 0x55
    assert cpu.b == 0xAA
    assert cpu.ix == 0x1256
    assert cpu.ch is True
    assert cpu.sp == 0x1FF7
    assert cycles == 10
