"""Opcode metadata for the JR-100 MB8861 CPU."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, Iterable, List, Sequence


class AddressingMode(Enum):
    """Supported addressing modes for the MB8861 instruction set."""

    INHERENT = auto()
    IMMEDIATE = auto()
    IMMEDIATE16 = auto()
    DIRECT = auto()
    DIRECT16 = auto()
    INDEXED = auto()
    INDEXED16 = auto()
    EXTENDED = auto()
    EXTENDED16 = auto()
    RELATIVE = auto()
    RELATIVE_LONG = auto()
    SPECIAL = auto()


@dataclass(frozen=True)
class Instruction:
    """Metadata describing a single MB8861 opcode."""

    opcode: int
    mnemonic: str
    mode: AddressingMode
    cycles: int
    handler: str
    extra_cycles: int = 0
    accumulator: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.opcode <= 0xFF:
            raise ValueError(f"opcode out of range: {self.opcode}")
        if self.cycles <= 0:
            raise ValueError("cycles must be positive")


class OpcodeTable:
    """Mutable builder for the 256-entry instruction table."""

    _TABLE_SIZE: Final[int] = 0x100

    def __init__(self) -> None:
        self._table: List[Instruction | None] = [None] * self._TABLE_SIZE

    def register(self, instruction: Instruction) -> None:
        opcode = instruction.opcode
        if self._table[opcode] is not None:
            existing = self._table[opcode]
            raise ValueError(
                f"opcode {opcode:#04x} already registered as {existing.mnemonic}")
        self._table[opcode] = instruction

    def register_all(self, instructions: Iterable[Instruction]) -> None:
        for instruction in instructions:
            self.register(instruction)

    def freeze(self) -> Sequence[Instruction | None]:
        return tuple(self._table)


def build_instruction_table(instructions: Iterable[Instruction]) -> Sequence[Instruction | None]:
    """Build a 256-entry instruction lookup table."""

    table = OpcodeTable()
    table.register_all(instructions)
    return table.freeze()


DEFAULT_INSTRUCTIONS: Sequence[Instruction] = (
    Instruction(0x01, "NOP", AddressingMode.INHERENT, 2, "op_nop"),
    # LDAA
    Instruction(0x86, "LDAA", AddressingMode.IMMEDIATE, 2, "op_ld_accumulator", accumulator="A"),
    Instruction(0x96, "LDAA", AddressingMode.DIRECT, 3, "op_ld_accumulator", accumulator="A"),
    Instruction(0xA6, "LDAA", AddressingMode.INDEXED, 5, "op_ld_accumulator", accumulator="A"),
    Instruction(0xB6, "LDAA", AddressingMode.EXTENDED, 4, "op_ld_accumulator", accumulator="A"),
    # LDAB
    Instruction(0xC6, "LDAB", AddressingMode.IMMEDIATE, 2, "op_ld_accumulator", accumulator="B"),
    Instruction(0xD6, "LDAB", AddressingMode.DIRECT, 3, "op_ld_accumulator", accumulator="B"),
    Instruction(0xE6, "LDAB", AddressingMode.INDEXED, 5, "op_ld_accumulator", accumulator="B"),
    Instruction(0xF6, "LDAB", AddressingMode.EXTENDED, 4, "op_ld_accumulator", accumulator="B"),
    # STAA
    Instruction(0x97, "STAA", AddressingMode.DIRECT, 4, "op_st_accumulator", accumulator="A"),
    Instruction(0xA7, "STAA", AddressingMode.INDEXED, 6, "op_st_accumulator", accumulator="A"),
    Instruction(0xB7, "STAA", AddressingMode.EXTENDED, 5, "op_st_accumulator", accumulator="A"),
    # STAB
    Instruction(0xD7, "STAB", AddressingMode.DIRECT, 4, "op_st_accumulator", accumulator="B"),
    Instruction(0xE7, "STAB", AddressingMode.INDEXED, 6, "op_st_accumulator", accumulator="B"),
    Instruction(0xF7, "STAB", AddressingMode.EXTENDED, 5, "op_st_accumulator", accumulator="B"),
    # INC/DEC
    Instruction(0x4C, "INCA", AddressingMode.INHERENT, 2, "op_inc_accumulator", accumulator="A"),
    Instruction(0x5C, "INCB", AddressingMode.INHERENT, 2, "op_inc_accumulator", accumulator="B"),
    Instruction(0x4A, "DECA", AddressingMode.INHERENT, 2, "op_dec_accumulator", accumulator="A"),
    Instruction(0x5A, "DECB", AddressingMode.INHERENT, 2, "op_dec_accumulator", accumulator="B"),
    # Transfers
    Instruction(0x16, "TAB", AddressingMode.INHERENT, 2, "op_tab"),
    Instruction(0x17, "TBA", AddressingMode.INHERENT, 2, "op_tba"),
    # ADDA / ADDB
    Instruction(0x8B, "ADDA", AddressingMode.IMMEDIATE, 2, "op_add_accumulator", accumulator="A"),
    Instruction(0x9B, "ADDA", AddressingMode.DIRECT, 3, "op_add_accumulator", accumulator="A"),
    Instruction(0xAB, "ADDA", AddressingMode.INDEXED, 5, "op_add_accumulator", accumulator="A"),
    Instruction(0xBB, "ADDA", AddressingMode.EXTENDED, 4, "op_add_accumulator", accumulator="A"),
    Instruction(0xCB, "ADDB", AddressingMode.IMMEDIATE, 2, "op_add_accumulator", accumulator="B"),
    Instruction(0xDB, "ADDB", AddressingMode.DIRECT, 3, "op_add_accumulator", accumulator="B"),
    Instruction(0xEB, "ADDB", AddressingMode.INDEXED, 5, "op_add_accumulator", accumulator="B"),
    Instruction(0xFB, "ADDB", AddressingMode.EXTENDED, 4, "op_add_accumulator", accumulator="B"),
    # ADCA / ADCB
    Instruction(0x89, "ADCA", AddressingMode.IMMEDIATE, 2, "op_adc_accumulator", accumulator="A"),
    Instruction(0x99, "ADCA", AddressingMode.DIRECT, 3, "op_adc_accumulator", accumulator="A"),
    Instruction(0xA9, "ADCA", AddressingMode.INDEXED, 5, "op_adc_accumulator", accumulator="A"),
    Instruction(0xB9, "ADCA", AddressingMode.EXTENDED, 4, "op_adc_accumulator", accumulator="A"),
    Instruction(0xC9, "ADCB", AddressingMode.IMMEDIATE, 2, "op_adc_accumulator", accumulator="B"),
    Instruction(0xD9, "ADCB", AddressingMode.DIRECT, 3, "op_adc_accumulator", accumulator="B"),
    Instruction(0xE9, "ADCB", AddressingMode.INDEXED, 5, "op_adc_accumulator", accumulator="B"),
    Instruction(0xF9, "ADCB", AddressingMode.EXTENDED, 4, "op_adc_accumulator", accumulator="B"),
    # SUBA / SUBB
    Instruction(0x80, "SUBA", AddressingMode.IMMEDIATE, 2, "op_sub_accumulator", accumulator="A"),
    Instruction(0x90, "SUBA", AddressingMode.DIRECT, 3, "op_sub_accumulator", accumulator="A"),
    Instruction(0xA0, "SUBA", AddressingMode.INDEXED, 5, "op_sub_accumulator", accumulator="A"),
    Instruction(0xB0, "SUBA", AddressingMode.EXTENDED, 4, "op_sub_accumulator", accumulator="A"),
    Instruction(0xC0, "SUBB", AddressingMode.IMMEDIATE, 2, "op_sub_accumulator", accumulator="B"),
    Instruction(0xD0, "SUBB", AddressingMode.DIRECT, 3, "op_sub_accumulator", accumulator="B"),
    Instruction(0xE0, "SUBB", AddressingMode.INDEXED, 5, "op_sub_accumulator", accumulator="B"),
    Instruction(0xF0, "SUBB", AddressingMode.EXTENDED, 4, "op_sub_accumulator", accumulator="B"),
    # SBCA / SBCB
    Instruction(0x82, "SBCA", AddressingMode.IMMEDIATE, 2, "op_sbc_accumulator", accumulator="A"),
    Instruction(0x92, "SBCA", AddressingMode.DIRECT, 3, "op_sbc_accumulator", accumulator="A"),
    Instruction(0xA2, "SBCA", AddressingMode.INDEXED, 5, "op_sbc_accumulator", accumulator="A"),
    Instruction(0xB2, "SBCA", AddressingMode.EXTENDED, 4, "op_sbc_accumulator", accumulator="A"),
    Instruction(0xC2, "SBCB", AddressingMode.IMMEDIATE, 2, "op_sbc_accumulator", accumulator="B"),
    Instruction(0xD2, "SBCB", AddressingMode.DIRECT, 3, "op_sbc_accumulator", accumulator="B"),
    Instruction(0xE2, "SBCB", AddressingMode.INDEXED, 5, "op_sbc_accumulator", accumulator="B"),
    Instruction(0xF2, "SBCB", AddressingMode.EXTENDED, 4, "op_sbc_accumulator", accumulator="B"),
    # Logical operations
    Instruction(0x84, "ANDA", AddressingMode.IMMEDIATE, 2, "op_and_accumulator", accumulator="A"),
    Instruction(0x94, "ANDA", AddressingMode.DIRECT, 3, "op_and_accumulator", accumulator="A"),
    Instruction(0xA4, "ANDA", AddressingMode.INDEXED, 5, "op_and_accumulator", accumulator="A"),
    Instruction(0xB4, "ANDA", AddressingMode.EXTENDED, 4, "op_and_accumulator", accumulator="A"),
    Instruction(0xC4, "ANDB", AddressingMode.IMMEDIATE, 2, "op_and_accumulator", accumulator="B"),
    Instruction(0xD4, "ANDB", AddressingMode.DIRECT, 3, "op_and_accumulator", accumulator="B"),
    Instruction(0xE4, "ANDB", AddressingMode.INDEXED, 5, "op_and_accumulator", accumulator="B"),
    Instruction(0xF4, "ANDB", AddressingMode.EXTENDED, 4, "op_and_accumulator", accumulator="B"),
    Instruction(0x8A, "ORAA", AddressingMode.IMMEDIATE, 2, "op_ora_accumulator", accumulator="A"),
    Instruction(0x9A, "ORAA", AddressingMode.DIRECT, 3, "op_ora_accumulator", accumulator="A"),
    Instruction(0xAA, "ORAA", AddressingMode.INDEXED, 5, "op_ora_accumulator", accumulator="A"),
    Instruction(0xBA, "ORAA", AddressingMode.EXTENDED, 4, "op_ora_accumulator", accumulator="A"),
    Instruction(0xCA, "ORAB", AddressingMode.IMMEDIATE, 2, "op_ora_accumulator", accumulator="B"),
    Instruction(0xDA, "ORAB", AddressingMode.DIRECT, 3, "op_ora_accumulator", accumulator="B"),
    Instruction(0xEA, "ORAB", AddressingMode.INDEXED, 5, "op_ora_accumulator", accumulator="B"),
    Instruction(0xFA, "ORAB", AddressingMode.EXTENDED, 4, "op_ora_accumulator", accumulator="B"),
    Instruction(0x88, "EORA", AddressingMode.IMMEDIATE, 2, "op_eor_accumulator", accumulator="A"),
    Instruction(0x98, "EORA", AddressingMode.DIRECT, 3, "op_eor_accumulator", accumulator="A"),
    Instruction(0xA8, "EORA", AddressingMode.INDEXED, 5, "op_eor_accumulator", accumulator="A"),
    Instruction(0xB8, "EORA", AddressingMode.EXTENDED, 4, "op_eor_accumulator", accumulator="A"),
    Instruction(0xC8, "EORB", AddressingMode.IMMEDIATE, 2, "op_eor_accumulator", accumulator="B"),
    Instruction(0xD8, "EORB", AddressingMode.DIRECT, 3, "op_eor_accumulator", accumulator="B"),
    Instruction(0xE8, "EORB", AddressingMode.INDEXED, 5, "op_eor_accumulator", accumulator="B"),
    Instruction(0xF8, "EORB", AddressingMode.EXTENDED, 4, "op_eor_accumulator", accumulator="B"),
    # Branches
    Instruction(0x26, "BNE", AddressingMode.RELATIVE, 4, "op_branch_bne"),
    Instruction(0x27, "BEQ", AddressingMode.RELATIVE, 4, "op_branch_beq"),
    Instruction(0x24, "BCC", AddressingMode.RELATIVE, 4, "op_branch_bcc"),
    Instruction(0x25, "BCS", AddressingMode.RELATIVE, 4, "op_branch_bcs"),
    Instruction(0x2A, "BPL", AddressingMode.RELATIVE, 4, "op_branch_bpl"),
    Instruction(0x2B, "BMI", AddressingMode.RELATIVE, 4, "op_branch_bmi"),
    Instruction(0x20, "BRA", AddressingMode.RELATIVE, 4, "op_branch_bra"),
    Instruction(0x22, "BHI", AddressingMode.RELATIVE, 4, "op_branch_bhi"),
    Instruction(0x23, "BLS", AddressingMode.RELATIVE, 4, "op_branch_bls"),
    Instruction(0x28, "BVC", AddressingMode.RELATIVE, 4, "op_branch_bvc"),
    Instruction(0x29, "BVS", AddressingMode.RELATIVE, 4, "op_branch_bvs"),
    Instruction(0x2C, "BGE", AddressingMode.RELATIVE, 4, "op_branch_bge"),
    Instruction(0x2D, "BLT", AddressingMode.RELATIVE, 4, "op_branch_blt"),
    Instruction(0x2E, "BGT", AddressingMode.RELATIVE, 4, "op_branch_bgt"),
    Instruction(0x2F, "BLE", AddressingMode.RELATIVE, 4, "op_branch_ble"),
    # Flag transfers
    Instruction(0x06, "TAP", AddressingMode.INHERENT, 2, "op_tap"),
    Instruction(0x07, "TPA", AddressingMode.INHERENT, 2, "op_tpa"),
    Instruction(0x0A, "CLV", AddressingMode.INHERENT, 2, "op_clv"),
    Instruction(0x0B, "SEV", AddressingMode.INHERENT, 2, "op_sev"),
    Instruction(0x0C, "CLC", AddressingMode.INHERENT, 2, "op_clc"),
    Instruction(0x0D, "SEC", AddressingMode.INHERENT, 2, "op_sec"),
    Instruction(0x0E, "CLI", AddressingMode.INHERENT, 2, "op_cli"),
    Instruction(0x0F, "SEI", AddressingMode.INHERENT, 2, "op_sei"),
    # Accumulator arithmetic shortcuts
    Instruction(0x10, "SBA", AddressingMode.INHERENT, 2, "op_sba"),
    Instruction(0x11, "CBA", AddressingMode.INHERENT, 2, "op_cba"),
    Instruction(0x19, "DAA", AddressingMode.INHERENT, 2, "op_daa"),
    Instruction(0x1B, "ABA", AddressingMode.INHERENT, 2, "op_aba"),
    # CLR/COM/NEG register
    Instruction(0x4F, "CLRA", AddressingMode.INHERENT, 2, "op_clr_accumulator", accumulator="A"),
    Instruction(0x5F, "CLRB", AddressingMode.INHERENT, 2, "op_clr_accumulator", accumulator="B"),
    Instruction(0x43, "COMA", AddressingMode.INHERENT, 2, "op_com_accumulator", accumulator="A"),
    Instruction(0x53, "COMB", AddressingMode.INHERENT, 2, "op_com_accumulator", accumulator="B"),
    Instruction(0x40, "NEGA", AddressingMode.INHERENT, 2, "op_neg_accumulator", accumulator="A"),
    Instruction(0x50, "NEGB", AddressingMode.INHERENT, 2, "op_neg_accumulator", accumulator="B"),
    # Shifts and rotates (register)
    Instruction(0x44, "LSRA", AddressingMode.INHERENT, 2, "op_lsr_accumulator", accumulator="A"),
    Instruction(0x54, "LSRB", AddressingMode.INHERENT, 2, "op_lsr_accumulator", accumulator="B"),
    Instruction(0x47, "ASRA", AddressingMode.INHERENT, 2, "op_asr_accumulator", accumulator="A"),
    Instruction(0x57, "ASRB", AddressingMode.INHERENT, 2, "op_asr_accumulator", accumulator="B"),
    Instruction(0x48, "ASLA", AddressingMode.INHERENT, 2, "op_asl_accumulator", accumulator="A"),
    Instruction(0x58, "ASLB", AddressingMode.INHERENT, 2, "op_asl_accumulator", accumulator="B"),
    Instruction(0x49, "ROLA", AddressingMode.INHERENT, 2, "op_rol_accumulator", accumulator="A"),
    Instruction(0x59, "ROLB", AddressingMode.INHERENT, 2, "op_rol_accumulator", accumulator="B"),
    Instruction(0x46, "RORA", AddressingMode.INHERENT, 2, "op_ror_accumulator", accumulator="A"),
    Instruction(0x56, "RORB", AddressingMode.INHERENT, 2, "op_ror_accumulator", accumulator="B"),
    # TST register
    Instruction(0x4D, "TSTA", AddressingMode.INHERENT, 2, "op_tst_accumulator", accumulator="A"),
    Instruction(0x5D, "TSTB", AddressingMode.INHERENT, 2, "op_tst_accumulator", accumulator="B"),
    # CLR/COM/NEG memory
    Instruction(0x6F, "CLR", AddressingMode.INDEXED, 7, "op_clr_memory"),
    Instruction(0x7F, "CLR", AddressingMode.EXTENDED, 6, "op_clr_memory"),
    Instruction(0x63, "COM", AddressingMode.INDEXED, 7, "op_com_memory"),
    Instruction(0x73, "COM", AddressingMode.EXTENDED, 6, "op_com_memory"),
    Instruction(0x60, "NEG", AddressingMode.INDEXED, 7, "op_neg_memory"),
    Instruction(0x70, "NEG", AddressingMode.EXTENDED, 6, "op_neg_memory"),
    # Shifts/Rots memory
    Instruction(0x64, "LSR", AddressingMode.INDEXED, 7, "op_lsr_memory"),
    Instruction(0x74, "LSR", AddressingMode.EXTENDED, 6, "op_lsr_memory"),
    Instruction(0x67, "ASR", AddressingMode.INDEXED, 7, "op_asr_memory"),
    Instruction(0x77, "ASR", AddressingMode.EXTENDED, 6, "op_asr_memory"),
    Instruction(0x68, "ASL", AddressingMode.INDEXED, 7, "op_asl_memory"),
    Instruction(0x78, "ASL", AddressingMode.EXTENDED, 6, "op_asl_memory"),
    Instruction(0x69, "ROL", AddressingMode.INDEXED, 7, "op_rol_memory"),
    Instruction(0x79, "ROL", AddressingMode.EXTENDED, 6, "op_rol_memory"),
    Instruction(0x66, "ROR", AddressingMode.INDEXED, 7, "op_ror_memory"),
    Instruction(0x76, "ROR", AddressingMode.EXTENDED, 6, "op_ror_memory"),
    # INC/DEC memory
    Instruction(0x6C, "INC", AddressingMode.INDEXED, 7, "op_inc_memory"),
    Instruction(0x7C, "INC", AddressingMode.EXTENDED, 6, "op_inc_memory"),
    Instruction(0x6A, "DEC", AddressingMode.INDEXED, 7, "op_dec_memory"),
    Instruction(0x7A, "DEC", AddressingMode.EXTENDED, 6, "op_dec_memory"),
    # TST memory
    Instruction(0x6D, "TST", AddressingMode.INDEXED, 7, "op_tst_memory"),
    Instruction(0x7D, "TST", AddressingMode.EXTENDED, 6, "op_tst_memory"),
    # Indexed immediate operations
    Instruction(0x71, "NIM", AddressingMode.SPECIAL, 8, "op_nim"),
    Instruction(0x72, "OIM", AddressingMode.SPECIAL, 8, "op_oim"),
    Instruction(0x75, "XIM", AddressingMode.SPECIAL, 8, "op_xim"),
    Instruction(0x7B, "TMM", AddressingMode.SPECIAL, 7, "op_tmm"),
    # Stack operations
    Instruction(0x36, "PSHA", AddressingMode.INHERENT, 4, "op_psh_accumulator", accumulator="A"),
    Instruction(0x37, "PSHB", AddressingMode.INHERENT, 4, "op_psh_accumulator", accumulator="B"),
    Instruction(0x32, "PULA", AddressingMode.INHERENT, 5, "op_pul_accumulator", accumulator="A"),
    Instruction(0x33, "PULB", AddressingMode.INHERENT, 5, "op_pul_accumulator", accumulator="B"),
    Instruction(0x3E, "WAI", AddressingMode.INHERENT, 9, "op_wai"),
    Instruction(0x3F, "SWI", AddressingMode.INHERENT, 12, "op_swi"),
    Instruction(0x39, "RTS", AddressingMode.INHERENT, 5, "op_rts"),
    Instruction(0x3B, "RTI", AddressingMode.INHERENT, 10, "op_rti"),
    # CMPA / CMPB
    Instruction(0x81, "CMPA", AddressingMode.IMMEDIATE, 2, "op_cmp_accumulator", accumulator="A"),
    Instruction(0x91, "CMPA", AddressingMode.DIRECT, 3, "op_cmp_accumulator", accumulator="A"),
    Instruction(0xA1, "CMPA", AddressingMode.INDEXED, 5, "op_cmp_accumulator", accumulator="A"),
    Instruction(0xB1, "CMPA", AddressingMode.EXTENDED, 4, "op_cmp_accumulator", accumulator="A"),
    Instruction(0xC1, "CMPB", AddressingMode.IMMEDIATE, 2, "op_cmp_accumulator", accumulator="B"),
    Instruction(0xD1, "CMPB", AddressingMode.DIRECT, 3, "op_cmp_accumulator", accumulator="B"),
    Instruction(0xE1, "CMPB", AddressingMode.INDEXED, 5, "op_cmp_accumulator", accumulator="B"),
    Instruction(0xF1, "CMPB", AddressingMode.EXTENDED, 4, "op_cmp_accumulator", accumulator="B"),
    # BITA / BITB
    Instruction(0x85, "BITA", AddressingMode.IMMEDIATE, 2, "op_bit_accumulator", accumulator="A"),
    Instruction(0x95, "BITA", AddressingMode.DIRECT, 3, "op_bit_accumulator", accumulator="A"),
    Instruction(0xA5, "BITA", AddressingMode.INDEXED, 5, "op_bit_accumulator", accumulator="A"),
    Instruction(0xB5, "BITA", AddressingMode.EXTENDED, 4, "op_bit_accumulator", accumulator="A"),
    Instruction(0xC5, "BITB", AddressingMode.IMMEDIATE, 2, "op_bit_accumulator", accumulator="B"),
    Instruction(0xD5, "BITB", AddressingMode.DIRECT, 3, "op_bit_accumulator", accumulator="B"),
    Instruction(0xE5, "BITB", AddressingMode.INDEXED, 5, "op_bit_accumulator", accumulator="B"),
    Instruction(0xF5, "BITB", AddressingMode.EXTENDED, 4, "op_bit_accumulator", accumulator="B"),
    # 16bit load/store
    Instruction(0xCE, "LDX", AddressingMode.IMMEDIATE16, 3, "op_ld_index"),
    Instruction(0xDE, "LDX", AddressingMode.DIRECT16, 4, "op_ld_index"),
    Instruction(0xEE, "LDX", AddressingMode.INDEXED16, 6, "op_ld_index"),
    Instruction(0xFE, "LDX", AddressingMode.EXTENDED16, 5, "op_ld_index"),
    Instruction(0x8E, "LDS", AddressingMode.IMMEDIATE16, 3, "op_ld_stack"),
    Instruction(0x9E, "LDS", AddressingMode.DIRECT16, 4, "op_ld_stack"),
    Instruction(0xAE, "LDS", AddressingMode.INDEXED16, 6, "op_ld_stack"),
    Instruction(0xBE, "LDS", AddressingMode.EXTENDED16, 5, "op_ld_stack"),
    Instruction(0xDF, "STX", AddressingMode.DIRECT16, 5, "op_st_index"),
    Instruction(0xEF, "STX", AddressingMode.INDEXED16, 7, "op_st_index"),
    Instruction(0xFF, "STX", AddressingMode.EXTENDED16, 6, "op_st_index"),
    Instruction(0x9F, "STS", AddressingMode.DIRECT16, 5, "op_st_stack"),
    Instruction(0xAF, "STS", AddressingMode.INDEXED16, 7, "op_st_stack"),
    Instruction(0xBF, "STS", AddressingMode.EXTENDED16, 6, "op_st_stack"),
    # 16bit inc/dec/compare
    Instruction(0x08, "INX", AddressingMode.INHERENT, 4, "op_inx"),
    Instruction(0x09, "DEX", AddressingMode.INHERENT, 4, "op_dex"),
    Instruction(0x31, "INS", AddressingMode.INHERENT, 4, "op_ins"),
    Instruction(0x34, "DES", AddressingMode.INHERENT, 4, "op_des"),
    Instruction(0x8C, "CPX", AddressingMode.IMMEDIATE16, 3, "op_cpx"),
    Instruction(0x9C, "CPX", AddressingMode.DIRECT16, 4, "op_cpx"),
    Instruction(0xAC, "CPX", AddressingMode.INDEXED16, 6, "op_cpx"),
    Instruction(0xBC, "CPX", AddressingMode.EXTENDED16, 5, "op_cpx"),
    # Stack/index transfers
    Instruction(0x35, "TXS", AddressingMode.INHERENT, 4, "op_txs"),
    Instruction(0x30, "TSX", AddressingMode.INHERENT, 4, "op_tsx"),
    # Subroutine and jump
    Instruction(0x8D, "BSR", AddressingMode.RELATIVE, 8, "op_branch_bsr"),
    Instruction(0xAD, "JSR", AddressingMode.INDEXED, 8, "op_jsr"),
    Instruction(0xBD, "JSR", AddressingMode.EXTENDED, 9, "op_jsr"),
    Instruction(0x6E, "JMP", AddressingMode.INDEXED, 4, "op_jmp"),
    Instruction(0x7E, "JMP", AddressingMode.EXTENDED, 3, "op_jmp"),
    Instruction(0xEC, "ADX", AddressingMode.IMMEDIATE, 3, "op_adx_immediate"),
    Instruction(0xFC, "ADX", AddressingMode.EXTENDED16, 7, "op_adx_extended"),
)


OPCODE_TABLE: Sequence[Instruction | None] = build_instruction_table(DEFAULT_INSTRUCTIONS)
