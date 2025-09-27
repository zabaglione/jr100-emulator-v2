"""Partial MB8861 CPU core implemented for growing instruction coverage."""

from __future__ import annotations

from .decoder import Decoder
from .instructions import AddressingMode, Instruction


class MB8861:
    """MB8861 CPU core with a subset of instructions ported from Java implementation."""

    VECTOR_RESTART = 0xFFFE
    VECTOR_IRQ = 0xFFF8
    VECTOR_SWI = 0xFFFA
    VECTOR_NMI = 0xFFFC

    def __init__(self, memory) -> None:
        self.memory = memory
        self.pc = 0
        self.a = 0
        self.b = 0
        self.ix = 0
        self.sp = 0
        self.ch = False
        self.ci = False
        self.cn = False
        self.cz = False
        self.cv = False
        self.cc = False
        self._waiting = False
        self._pending_irq = False
        self._pending_nmi = False
        self._decoder = Decoder()
        self._register_instructions()

    def reset(self) -> None:
        self.pc = self.memory.load16(self.VECTOR_RESTART)
        self.a = 0
        self.b = 0
        self.ix = 0
        self.sp = 0x01FF
        self.ch = False
        self.ci = False
        self.cn = False
        self.cz = False
        self.cv = False
        self.cc = False
        self._waiting = False
        self._pending_irq = False
        self._pending_nmi = False

    def step(self) -> int:
        if self._waiting:
            if self._pending_nmi:
                self._pending_nmi = False
                return self._service_interrupt(self.VECTOR_NMI, 12)
            if self._pending_irq and not self.ci:
                self._pending_irq = False
                return self._service_interrupt(self.VECTOR_IRQ, 12)
            return 1

        if self._pending_nmi:
            self._pending_nmi = False
            return self._service_interrupt(self.VECTOR_NMI, 12)

        if self._pending_irq and not self.ci:
            self._pending_irq = False
            return self._service_interrupt(self.VECTOR_IRQ, 12)

        opcode = self.memory.load8(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        instruction = self._decoder.lookup(opcode)
        return instruction.handler(self, instruction.mode)

    def execute(self, clocks: int) -> int:
        elapsed = 0
        while elapsed < clocks:
            elapsed += self.step()
        return elapsed - clocks

    @property
    def waiting(self) -> bool:
        return self._waiting

    def request_irq(self) -> None:
        self._pending_irq = True

    def request_nmi(self) -> None:
        self._pending_nmi = True

    def clear_irq(self) -> None:
        self._pending_irq = False

    def clear_nmi(self) -> None:
        self._pending_nmi = False

    # ------------------------------------------------------------------
    # Instruction registration

    def _register_instructions(self) -> None:
        register = self._decoder.register

        register(Instruction(0x01, "NOP", AddressingMode.IMPLIED, 2, MB8861._opcode_nop))
        register(Instruction(0x86, "LDAA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_ldaa_imm))
        register(Instruction(0x96, "LDAA", AddressingMode.DIRECT, 3, MB8861._opcode_ldaa_dir))
        register(Instruction(0xA6, "LDAA", AddressingMode.DIRECT, 5, MB8861._opcode_ldaa_ind))
        register(Instruction(0xB6, "LDAA", AddressingMode.DIRECT, 4, MB8861._opcode_ldaa_ext))
        register(Instruction(0x97, "STAA", AddressingMode.DIRECT, 4, MB8861._opcode_staa_dir))
        register(Instruction(0xA7, "STAA", AddressingMode.DIRECT, 6, MB8861._opcode_staa_ind))
        register(Instruction(0xB7, "STAA", AddressingMode.DIRECT, 5, MB8861._opcode_staa_ext))
        register(Instruction(0x48, "ASLA", AddressingMode.IMPLIED, 2, MB8861._opcode_asla))
        register(Instruction(0x58, "ASLB", AddressingMode.IMPLIED, 2, MB8861._opcode_aslb))
        register(Instruction(0x47, "ASRA", AddressingMode.IMPLIED, 2, MB8861._opcode_asra))
        register(Instruction(0x57, "ASRB", AddressingMode.IMPLIED, 2, MB8861._opcode_asrb))
        register(Instruction(0x44, "LSRA", AddressingMode.IMPLIED, 2, MB8861._opcode_lsra))
        register(Instruction(0x54, "LSRB", AddressingMode.IMPLIED, 2, MB8861._opcode_lsrb))
        register(Instruction(0x49, "ROLA", AddressingMode.IMPLIED, 2, MB8861._opcode_rola))
        register(Instruction(0x59, "ROLB", AddressingMode.IMPLIED, 2, MB8861._opcode_rolb))
        register(Instruction(0x46, "RORA", AddressingMode.IMPLIED, 2, MB8861._opcode_rora))
        register(Instruction(0x56, "RORB", AddressingMode.IMPLIED, 2, MB8861._opcode_rorb))
        register(Instruction(0x40, "NEGA", AddressingMode.IMPLIED, 2, MB8861._opcode_nega))
        register(Instruction(0x50, "NEGB", AddressingMode.IMPLIED, 2, MB8861._opcode_negb))
        register(Instruction(0x43, "COMA", AddressingMode.IMPLIED, 2, MB8861._opcode_coma))
        register(Instruction(0x53, "COMB", AddressingMode.IMPLIED, 2, MB8861._opcode_comb))
        register(Instruction(0x4A, "DECA", AddressingMode.IMPLIED, 2, MB8861._opcode_deca))
        register(Instruction(0x5A, "DECB", AddressingMode.IMPLIED, 2, MB8861._opcode_decb))
        register(Instruction(0x4C, "INCA", AddressingMode.IMPLIED, 2, MB8861._opcode_inca))
        register(Instruction(0x5C, "INCB", AddressingMode.IMPLIED, 2, MB8861._opcode_incb))
        register(Instruction(0x4F, "CLRA", AddressingMode.IMPLIED, 2, MB8861._opcode_clra))
        register(Instruction(0x5F, "CLRB", AddressingMode.IMPLIED, 2, MB8861._opcode_clrb))
        register(Instruction(0x4D, "TSTA", AddressingMode.IMPLIED, 2, MB8861._opcode_tsta))
        register(Instruction(0x5D, "TSTB", AddressingMode.IMPLIED, 2, MB8861._opcode_tstb))
        register(Instruction(0x19, "DAA", AddressingMode.IMPLIED, 2, MB8861._opcode_daa))
        register(Instruction(0x1B, "ABA", AddressingMode.IMPLIED, 2, MB8861._opcode_aba))
        register(Instruction(0x36, "PSHA", AddressingMode.IMPLIED, 4, MB8861._opcode_psha))
        register(Instruction(0x37, "PSHB", AddressingMode.IMPLIED, 4, MB8861._opcode_pshb))
        register(Instruction(0x32, "PULA", AddressingMode.IMPLIED, 4, MB8861._opcode_pula))
        register(Instruction(0x33, "PULB", AddressingMode.IMPLIED, 4, MB8861._opcode_pulb))
        register(Instruction(0x16, "TAB", AddressingMode.IMPLIED, 2, MB8861._opcode_tab))
        register(Instruction(0x17, "TBA", AddressingMode.IMPLIED, 2, MB8861._opcode_tba))
        register(Instruction(0x11, "CBA", AddressingMode.IMPLIED, 2, MB8861._opcode_cba))
        register(Instruction(0x10, "SBA", AddressingMode.IMPLIED, 2, MB8861._opcode_sba))
        register(Instruction(0x06, "TAP", AddressingMode.IMPLIED, 2, MB8861._opcode_tap))
        register(Instruction(0x07, "TPA", AddressingMode.IMPLIED, 2, MB8861._opcode_tpa))
        register(Instruction(0x09, "DEX", AddressingMode.IMPLIED, 4, MB8861._opcode_dex))
        register(Instruction(0x08, "INX", AddressingMode.IMPLIED, 4, MB8861._opcode_inx))
        register(Instruction(0x34, "DES", AddressingMode.IMPLIED, 4, MB8861._opcode_des))
        register(Instruction(0x31, "INS", AddressingMode.IMPLIED, 4, MB8861._opcode_ins))
        register(Instruction(0x30, "TSX", AddressingMode.IMPLIED, 4, MB8861._opcode_tsx))
        register(Instruction(0x35, "TXS", AddressingMode.IMPLIED, 4, MB8861._opcode_txs))
        register(Instruction(0x3E, "WAI", AddressingMode.IMPLIED, 9, MB8861._opcode_wai))
        register(Instruction(0x3F, "SWI", AddressingMode.IMPLIED, 12, MB8861._opcode_swi))
        register(Instruction(0x0C, "CLC", AddressingMode.IMPLIED, 2, MB8861._opcode_clc))
        register(Instruction(0x0E, "CLI", AddressingMode.IMPLIED, 2, MB8861._opcode_cli))
        register(Instruction(0x0A, "CLV", AddressingMode.IMPLIED, 2, MB8861._opcode_clv))
        register(Instruction(0x0B, "SEC", AddressingMode.IMPLIED, 2, MB8861._opcode_sec))
        register(Instruction(0x0F, "SEI", AddressingMode.IMPLIED, 2, MB8861._opcode_sei))
        register(Instruction(0x0D, "SEV", AddressingMode.IMPLIED, 2, MB8861._opcode_sev))
        register(Instruction(0x85, "BITA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_bita_imm))
        register(Instruction(0x95, "BITA", AddressingMode.DIRECT, 3, MB8861._opcode_bita_dir))
        register(Instruction(0xA5, "BITA", AddressingMode.DIRECT, 5, MB8861._opcode_bita_ind))
        register(Instruction(0xB5, "BITA", AddressingMode.DIRECT, 4, MB8861._opcode_bita_ext))
        register(Instruction(0x71, "NIM", AddressingMode.DIRECT, 8, MB8861._opcode_nim_ind))
        register(Instruction(0x72, "OIM", AddressingMode.DIRECT, 8, MB8861._opcode_oim_ind))
        register(Instruction(0x75, "XIM", AddressingMode.DIRECT, 8, MB8861._opcode_xim_ind))
        register(Instruction(0x7B, "TMM", AddressingMode.DIRECT, 7, MB8861._opcode_tmm_ind))
        register(Instruction(0x84, "ANDA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_anda_imm))
        register(Instruction(0x94, "ANDA", AddressingMode.DIRECT, 3, MB8861._opcode_anda_dir))
        register(Instruction(0xA4, "ANDA", AddressingMode.DIRECT, 5, MB8861._opcode_anda_ind))
        register(Instruction(0xB4, "ANDA", AddressingMode.DIRECT, 4, MB8861._opcode_anda_ext))
        register(Instruction(0x8B, "ADDA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_adda_imm))
        register(Instruction(0x9B, "ADDA", AddressingMode.DIRECT, 3, MB8861._opcode_adda_dir))
        register(Instruction(0xAB, "ADDA", AddressingMode.DIRECT, 5, MB8861._opcode_adda_ind))
        register(Instruction(0xBB, "ADDA", AddressingMode.DIRECT, 4, MB8861._opcode_adda_ext))
        register(Instruction(0x89, "ADCA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_adca_imm))
        register(Instruction(0x99, "ADCA", AddressingMode.DIRECT, 3, MB8861._opcode_adca_dir))
        register(Instruction(0xA9, "ADCA", AddressingMode.DIRECT, 5, MB8861._opcode_adca_ind))
        register(Instruction(0xB9, "ADCA", AddressingMode.DIRECT, 4, MB8861._opcode_adca_ext))
        register(Instruction(0x82, "SBCA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_sbca_imm))
        register(Instruction(0x81, "CMPA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_cmpa_imm))
        register(Instruction(0x91, "CMPA", AddressingMode.DIRECT, 3, MB8861._opcode_cmpa_dir))
        register(Instruction(0xA1, "CMPA", AddressingMode.DIRECT, 5, MB8861._opcode_cmpa_ind))
        register(Instruction(0xB1, "CMPA", AddressingMode.DIRECT, 4, MB8861._opcode_cmpa_ext))
        register(Instruction(0x80, "SUBA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_suba_imm))
        register(Instruction(0x90, "SUBA", AddressingMode.DIRECT, 3, MB8861._opcode_suba_dir))
        register(Instruction(0xA0, "SUBA", AddressingMode.DIRECT, 5, MB8861._opcode_suba_ind))
        register(Instruction(0xB0, "SUBA", AddressingMode.DIRECT, 4, MB8861._opcode_suba_ext))
        register(Instruction(0x92, "SBCA", AddressingMode.DIRECT, 3, MB8861._opcode_sbca_dir))
        register(Instruction(0xA2, "SBCA", AddressingMode.DIRECT, 5, MB8861._opcode_sbca_ind))
        register(Instruction(0xB2, "SBCA", AddressingMode.DIRECT, 4, MB8861._opcode_sbca_ext))

        register(Instruction(0x88, "EORA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_eora_imm))
        register(Instruction(0x98, "EORA", AddressingMode.DIRECT, 3, MB8861._opcode_eora_dir))
        register(Instruction(0xA8, "EORA", AddressingMode.DIRECT, 5, MB8861._opcode_eora_ind))
        register(Instruction(0xB8, "EORA", AddressingMode.DIRECT, 4, MB8861._opcode_eora_ext))

        register(Instruction(0x8A, "ORAA", AddressingMode.IMMEDIATE, 2, MB8861._opcode_oraa_imm))
        register(Instruction(0x9A, "ORAA", AddressingMode.DIRECT, 3, MB8861._opcode_oraa_dir))
        register(Instruction(0xAA, "ORAA", AddressingMode.DIRECT, 5, MB8861._opcode_oraa_ind))
        register(Instruction(0xBA, "ORAA", AddressingMode.DIRECT, 4, MB8861._opcode_oraa_ext))

        register(Instruction(0xC6, "LDAB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_ldab_imm))
        register(Instruction(0xD6, "LDAB", AddressingMode.DIRECT, 3, MB8861._opcode_ldab_dir))
        register(Instruction(0xE6, "LDAB", AddressingMode.DIRECT, 5, MB8861._opcode_ldab_ind))
        register(Instruction(0xF6, "LDAB", AddressingMode.DIRECT, 4, MB8861._opcode_ldab_ext))
        register(Instruction(0xC5, "BITB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_bitb_imm))
        register(Instruction(0xD5, "BITB", AddressingMode.DIRECT, 3, MB8861._opcode_bitb_dir))
        register(Instruction(0xE5, "BITB", AddressingMode.DIRECT, 5, MB8861._opcode_bitb_ind))
        register(Instruction(0xF5, "BITB", AddressingMode.DIRECT, 4, MB8861._opcode_bitb_ext))
        register(Instruction(0xCB, "ADDB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_addb_imm))
        register(Instruction(0xDB, "ADDB", AddressingMode.DIRECT, 3, MB8861._opcode_addb_dir))
        register(Instruction(0xEB, "ADDB", AddressingMode.DIRECT, 5, MB8861._opcode_addb_ind))
        register(Instruction(0xFB, "ADDB", AddressingMode.DIRECT, 4, MB8861._opcode_addb_ext))
        register(Instruction(0xEC, "ADX", AddressingMode.IMMEDIATE, 3, MB8861._opcode_adx_imm))
        register(Instruction(0xFC, "ADX", AddressingMode.DIRECT, 7, MB8861._opcode_adx_ext))
        register(Instruction(0xC9, "ADCB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_adcb_imm))
        register(Instruction(0xD9, "ADCB", AddressingMode.DIRECT, 3, MB8861._opcode_adcb_dir))
        register(Instruction(0xE9, "ADCB", AddressingMode.DIRECT, 5, MB8861._opcode_adcb_ind))
        register(Instruction(0xF9, "ADCB", AddressingMode.DIRECT, 4, MB8861._opcode_adcb_ext))

        register(Instruction(0xC4, "ANDB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_andb_imm))
        register(Instruction(0xD4, "ANDB", AddressingMode.DIRECT, 3, MB8861._opcode_andb_dir))
        register(Instruction(0xE4, "ANDB", AddressingMode.DIRECT, 5, MB8861._opcode_andb_ind))
        register(Instruction(0xF4, "ANDB", AddressingMode.DIRECT, 4, MB8861._opcode_andb_ext))

        register(Instruction(0xC1, "CMPB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_cmpb_imm))
        register(Instruction(0xD1, "CMPB", AddressingMode.DIRECT, 3, MB8861._opcode_cmpb_dir))
        register(Instruction(0xE1, "CMPB", AddressingMode.DIRECT, 5, MB8861._opcode_cmpb_ind))
        register(Instruction(0xF1, "CMPB", AddressingMode.DIRECT, 4, MB8861._opcode_cmpb_ext))

        register(Instruction(0xC8, "EORB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_eorb_imm))
        register(Instruction(0xD8, "EORB", AddressingMode.DIRECT, 3, MB8861._opcode_eorb_dir))
        register(Instruction(0xE8, "EORB", AddressingMode.DIRECT, 5, MB8861._opcode_eorb_ind))
        register(Instruction(0xF8, "EORB", AddressingMode.DIRECT, 4, MB8861._opcode_eorb_ext))

        register(Instruction(0xD7, "STAB", AddressingMode.DIRECT, 4, MB8861._opcode_stab_dir))
        register(Instruction(0xE7, "STAB", AddressingMode.DIRECT, 6, MB8861._opcode_stab_ind))
        register(Instruction(0xF7, "STAB", AddressingMode.DIRECT, 5, MB8861._opcode_stab_ext))

        register(Instruction(0xCA, "ORAB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_orab_imm))
        register(Instruction(0xDA, "ORAB", AddressingMode.DIRECT, 3, MB8861._opcode_orab_dir))
        register(Instruction(0xEA, "ORAB", AddressingMode.DIRECT, 5, MB8861._opcode_orab_ind))
        register(Instruction(0xFA, "ORAB", AddressingMode.DIRECT, 4, MB8861._opcode_orab_ext))

        register(Instruction(0x68, "ASL", AddressingMode.DIRECT, 7, MB8861._opcode_asl_ind))
        register(Instruction(0x78, "ASL", AddressingMode.DIRECT, 6, MB8861._opcode_asl_ext))
        register(Instruction(0x67, "ASR", AddressingMode.DIRECT, 7, MB8861._opcode_asr_ind))
        register(Instruction(0x77, "ASR", AddressingMode.DIRECT, 6, MB8861._opcode_asr_ext))
        register(Instruction(0x64, "LSR", AddressingMode.DIRECT, 7, MB8861._opcode_lsr_ind))
        register(Instruction(0x74, "LSR", AddressingMode.DIRECT, 6, MB8861._opcode_lsr_ext))
        register(Instruction(0x69, "ROL", AddressingMode.DIRECT, 7, MB8861._opcode_rol_ind))
        register(Instruction(0x79, "ROL", AddressingMode.DIRECT, 6, MB8861._opcode_rol_ext))
        register(Instruction(0x66, "ROR", AddressingMode.DIRECT, 7, MB8861._opcode_ror_ind))
        register(Instruction(0x76, "ROR", AddressingMode.DIRECT, 6, MB8861._opcode_ror_ext))
        register(Instruction(0x60, "NEG", AddressingMode.DIRECT, 7, MB8861._opcode_neg_ind))
        register(Instruction(0x70, "NEG", AddressingMode.DIRECT, 6, MB8861._opcode_neg_ext))
        register(Instruction(0x63, "COM", AddressingMode.DIRECT, 7, MB8861._opcode_com_ind))
        register(Instruction(0x73, "COM", AddressingMode.DIRECT, 6, MB8861._opcode_com_ext))
        register(Instruction(0x6A, "DEC", AddressingMode.DIRECT, 7, MB8861._opcode_dec_ind))
        register(Instruction(0x7A, "DEC", AddressingMode.DIRECT, 6, MB8861._opcode_dec_ext))
        register(Instruction(0x6C, "INC", AddressingMode.DIRECT, 7, MB8861._opcode_inc_ind))
        register(Instruction(0x7C, "INC", AddressingMode.DIRECT, 6, MB8861._opcode_inc_ext))
        register(Instruction(0x6F, "CLR", AddressingMode.DIRECT, 7, MB8861._opcode_clr_ind))
        register(Instruction(0x7F, "CLR", AddressingMode.DIRECT, 6, MB8861._opcode_clr_ext))
        register(Instruction(0x6D, "TST", AddressingMode.DIRECT, 7, MB8861._opcode_tst_ind))
        register(Instruction(0x7D, "TST", AddressingMode.DIRECT, 6, MB8861._opcode_tst_ext))

        register(Instruction(0xC0, "SUBB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_subb_imm))
        register(Instruction(0xD0, "SUBB", AddressingMode.DIRECT, 3, MB8861._opcode_subb_dir))
        register(Instruction(0xE0, "SUBB", AddressingMode.DIRECT, 5, MB8861._opcode_subb_ind))
        register(Instruction(0xF0, "SUBB", AddressingMode.DIRECT, 4, MB8861._opcode_subb_ext))
        register(Instruction(0xC2, "SBCB", AddressingMode.IMMEDIATE, 2, MB8861._opcode_sbcb_imm))
        register(Instruction(0xD2, "SBCB", AddressingMode.DIRECT, 3, MB8861._opcode_sbcb_dir))
        register(Instruction(0xE2, "SBCB", AddressingMode.DIRECT, 5, MB8861._opcode_sbcb_ind))
        register(Instruction(0xF2, "SBCB", AddressingMode.DIRECT, 4, MB8861._opcode_sbcb_ext))

        register(Instruction(0xCE, "LDX", AddressingMode.IMMEDIATE, 3, MB8861._opcode_ldx_imm))
        register(Instruction(0xDE, "LDX", AddressingMode.DIRECT, 4, MB8861._opcode_ldx_dir))
        register(Instruction(0xEE, "LDX", AddressingMode.DIRECT, 6, MB8861._opcode_ldx_ind))
        register(Instruction(0xFE, "LDX", AddressingMode.DIRECT, 5, MB8861._opcode_ldx_ext))
        register(Instruction(0x8E, "LDS", AddressingMode.IMMEDIATE, 3, MB8861._opcode_lds_imm))
        register(Instruction(0x9E, "LDS", AddressingMode.DIRECT, 4, MB8861._opcode_lds_dir))
        register(Instruction(0xAE, "LDS", AddressingMode.DIRECT, 6, MB8861._opcode_lds_ind))
        register(Instruction(0xBE, "LDS", AddressingMode.DIRECT, 5, MB8861._opcode_lds_ext))

        register(Instruction(0x8C, "CPX", AddressingMode.IMMEDIATE, 3, MB8861._opcode_cpx_imm))
        register(Instruction(0x9C, "CPX", AddressingMode.DIRECT, 4, MB8861._opcode_cpx_dir))
        register(Instruction(0xAC, "CPX", AddressingMode.DIRECT, 6, MB8861._opcode_cpx_ind))
        register(Instruction(0xBC, "CPX", AddressingMode.DIRECT, 5, MB8861._opcode_cpx_ext))

        register(Instruction(0xDF, "STX", AddressingMode.DIRECT, 5, MB8861._opcode_stx_dir))
        register(Instruction(0xEF, "STX", AddressingMode.DIRECT, 7, MB8861._opcode_stx_ind))
        register(Instruction(0xFF, "STX", AddressingMode.DIRECT, 6, MB8861._opcode_stx_ext))
        register(Instruction(0x9F, "STS", AddressingMode.DIRECT, 5, MB8861._opcode_sts_dir))
        register(Instruction(0xAF, "STS", AddressingMode.DIRECT, 7, MB8861._opcode_sts_ind))
        register(Instruction(0xBF, "STS", AddressingMode.DIRECT, 6, MB8861._opcode_sts_ext))

        register(Instruction(0x8D, "BSR", AddressingMode.RELATIVE, 8, MB8861._opcode_bsr_rel))
        register(Instruction(0xAD, "JSR", AddressingMode.DIRECT, 8, MB8861._opcode_jsr_ind))
        register(Instruction(0xBD, "JSR", AddressingMode.DIRECT, 9, MB8861._opcode_jsr_ext))
        register(Instruction(0x6E, "JMP", AddressingMode.DIRECT, 4, MB8861._opcode_jmp_ind))
        register(Instruction(0x7E, "JMP", AddressingMode.DIRECT, 3, MB8861._opcode_jmp_ext))
        register(Instruction(0x39, "RTS", AddressingMode.IMPLIED, 5, MB8861._opcode_rts))
        register(Instruction(0x3B, "RTI", AddressingMode.IMPLIED, 10, MB8861._opcode_rti))

        register(Instruction(0x24, "BCC", AddressingMode.RELATIVE, 4, MB8861._opcode_bcc_rel))
        register(Instruction(0x22, "BHI", AddressingMode.RELATIVE, 4, MB8861._opcode_bhi_rel))
        register(Instruction(0x23, "BLS", AddressingMode.RELATIVE, 4, MB8861._opcode_bls_rel))
        register(Instruction(0x25, "BCS", AddressingMode.RELATIVE, 4, MB8861._opcode_bcs_rel))
        register(Instruction(0x26, "BNE", AddressingMode.RELATIVE, 4, MB8861._opcode_bne_rel))
        register(Instruction(0x27, "BEQ", AddressingMode.RELATIVE, 4, MB8861._opcode_beq_rel))
        register(Instruction(0x28, "BVC", AddressingMode.RELATIVE, 4, MB8861._opcode_bvc_rel))
        register(Instruction(0x29, "BVS", AddressingMode.RELATIVE, 4, MB8861._opcode_bvs_rel))
        register(Instruction(0x2A, "BPL", AddressingMode.RELATIVE, 4, MB8861._opcode_bpl_rel))
        register(Instruction(0x2D, "BLT", AddressingMode.RELATIVE, 4, MB8861._opcode_blt_rel))
        register(Instruction(0x2E, "BGT", AddressingMode.RELATIVE, 4, MB8861._opcode_bgt_rel))
        register(Instruction(0x2B, "BMI", AddressingMode.RELATIVE, 4, MB8861._opcode_bmi_rel))
        register(Instruction(0x2C, "BGE", AddressingMode.RELATIVE, 4, MB8861._opcode_bge_rel))
        register(Instruction(0x2F, "BLE", AddressingMode.RELATIVE, 4, MB8861._opcode_ble_rel))
        register(Instruction(0x20, "BRA", AddressingMode.RELATIVE, 4, MB8861._opcode_bra_rel))

    # ------------------------------------------------------------------
    # Opcode handlers (8-bit data)

    def _opcode_nop(self, _mode: AddressingMode) -> int:
        return 2

    def _opcode_ldaa_imm(self, _mode: AddressingMode) -> int:
        value = self._fetch_byte()
        self.a = self._lda(value)
        return 2

    def _opcode_ldaa_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.a = self._lda(self._load_direct(address))
        return 3

    def _opcode_ldaa_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.a = self._lda(self._load_indexed(offset))
        return 5

    def _opcode_ldaa_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.a = self._lda(self._load_extended(address))
        return 4

    def _opcode_staa_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._sta_direct(address, self.a)
        return 4

    def _opcode_staa_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._sta_indexed(offset, self.a)
        return 6

    def _opcode_staa_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._sta_extended(address, self.a)
        return 5

    def _opcode_asla(self, _mode: AddressingMode) -> int:
        self.a = self._asl(self.a)
        return 2

    def _opcode_aslb(self, _mode: AddressingMode) -> int:
        self.b = self._asl(self.b)
        return 2

    def _opcode_asra(self, _mode: AddressingMode) -> int:
        self.a = self._asr(self.a)
        return 2

    def _opcode_asrb(self, _mode: AddressingMode) -> int:
        self.b = self._asr(self.b)
        return 2

    def _opcode_lsra(self, _mode: AddressingMode) -> int:
        self.a = self._lsr(self.a)
        return 2

    def _opcode_lsrb(self, _mode: AddressingMode) -> int:
        self.b = self._lsr(self.b)
        return 2

    def _opcode_rola(self, _mode: AddressingMode) -> int:
        self.a = self._rol(self.a)
        return 2

    def _opcode_rolb(self, _mode: AddressingMode) -> int:
        self.b = self._rol(self.b)
        return 2

    def _opcode_rora(self, _mode: AddressingMode) -> int:
        self.a = self._ror(self.a)
        return 2

    def _opcode_rorb(self, _mode: AddressingMode) -> int:
        self.b = self._ror(self.b)
        return 2

    def _opcode_nega(self, _mode: AddressingMode) -> int:
        self.a = self._neg(self.a)
        return 2

    def _opcode_negb(self, _mode: AddressingMode) -> int:
        self.b = self._neg(self.b)
        return 2

    def _opcode_coma(self, _mode: AddressingMode) -> int:
        self.a = self._com(self.a)
        return 2

    def _opcode_comb(self, _mode: AddressingMode) -> int:
        self.b = self._com(self.b)
        return 2

    def _opcode_deca(self, _mode: AddressingMode) -> int:
        self.a = self._dec(self.a)
        return 2

    def _opcode_decb(self, _mode: AddressingMode) -> int:
        self.b = self._dec(self.b)
        return 2

    def _opcode_inca(self, _mode: AddressingMode) -> int:
        self.a = self._inc(self.a)
        return 2

    def _opcode_incb(self, _mode: AddressingMode) -> int:
        self.b = self._inc(self.b)
        return 2

    def _opcode_clra(self, _mode: AddressingMode) -> int:
        self.a = self._clr()
        return 2

    def _opcode_clrb(self, _mode: AddressingMode) -> int:
        self.b = self._clr()
        return 2

    def _opcode_tsta(self, _mode: AddressingMode) -> int:
        self._tst(self.a)
        return 2

    def _opcode_tstb(self, _mode: AddressingMode) -> int:
        self._tst(self.b)
        return 2

    def _opcode_psha(self, _mode: AddressingMode) -> int:
        self._push_byte(self.a)
        return 4

    def _opcode_pshb(self, _mode: AddressingMode) -> int:
        self._push_byte(self.b)
        return 4

    def _opcode_pula(self, _mode: AddressingMode) -> int:
        self.a = self._pull_byte()
        return 4

    def _opcode_pulb(self, _mode: AddressingMode) -> int:
        self.b = self._pull_byte()
        return 4

    def _opcode_tab(self, _mode: AddressingMode) -> int:
        self._tab()
        return 2

    def _opcode_tba(self, _mode: AddressingMode) -> int:
        self._tba()
        return 2

    def _opcode_cba(self, _mode: AddressingMode) -> int:
        self._cmp(self.a, self.b)
        return 2

    def _opcode_daa(self, _mode: AddressingMode) -> int:
        self.a = self._daa()
        return 2

    def _opcode_aba(self, _mode: AddressingMode) -> int:
        self.a = self._add(self.a, self.b)
        return 2

    def _opcode_sba(self, _mode: AddressingMode) -> int:
        self.a = self._sub(self.a, self.b)
        return 2

    def _opcode_tap(self, _mode: AddressingMode) -> int:
        self._tap()
        return 2

    def _opcode_tpa(self, _mode: AddressingMode) -> int:
        self._tpa()
        return 2

    def _opcode_dex(self, _mode: AddressingMode) -> int:
        self._dex()
        return 4

    def _opcode_inx(self, _mode: AddressingMode) -> int:
        self._inx()
        return 4

    def _opcode_des(self, _mode: AddressingMode) -> int:
        self._des()
        return 4

    def _opcode_ins(self, _mode: AddressingMode) -> int:
        self._ins()
        return 4

    def _opcode_tsx(self, _mode: AddressingMode) -> int:
        self.ix = (self.sp + 1) & 0xFFFF
        return 4

    def _opcode_txs(self, _mode: AddressingMode) -> int:
        self.sp = (self.ix - 1) & 0xFFFF
        return 4

    def _opcode_clc(self, _mode: AddressingMode) -> int:
        self.cc = False
        return 2

    def _opcode_cli(self, _mode: AddressingMode) -> int:
        self.ci = False
        return 2

    def _opcode_clv(self, _mode: AddressingMode) -> int:
        self.cv = False
        return 2

    def _opcode_sec(self, _mode: AddressingMode) -> int:
        self.cc = True
        return 2

    def _opcode_sei(self, _mode: AddressingMode) -> int:
        self.ci = True
        return 2

    def _opcode_sev(self, _mode: AddressingMode) -> int:
        self.cv = True
        return 2

    def _opcode_wai(self, _mode: AddressingMode) -> int:
        self._waiting = True
        return 9

    def _opcode_swi(self, _mode: AddressingMode) -> int:
        self._push_all_registers()
        self.ci = True
        self.pc = self._load16_extended(self.VECTOR_SWI)
        self._waiting = False
        return 12

    def _opcode_bita_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self._bit(self.a, operand)
        return 2

    def _opcode_bita_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._bit(self.a, self._load_direct(address))
        return 3

    def _opcode_bita_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._bit(self.a, self._load_indexed(offset))
        return 5

    def _opcode_bita_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._bit(self.a, self._load_extended(address))
        return 4

    def _opcode_bitb_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self._bit(self.b, operand)
        return 2

    def _opcode_bitb_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._bit(self.b, self._load_direct(address))
        return 3

    def _opcode_bitb_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._bit(self.b, self._load_indexed(offset))
        return 5

    def _opcode_bitb_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._bit(self.b, self._load_extended(address))
        return 4

    def _opcode_nim_ind(self, _mode: AddressingMode) -> int:
        value = self._fetch_byte()
        offset = self._fetch_byte()
        result = self._nim(value, self._load_indexed(offset))
        self._store_indexed(offset, result)
        return 8

    def _opcode_oim_ind(self, _mode: AddressingMode) -> int:
        value = self._fetch_byte()
        offset = self._fetch_byte()
        result = self._oim(value, self._load_indexed(offset))
        self._store_indexed(offset, result)
        return 8

    def _opcode_xim_ind(self, _mode: AddressingMode) -> int:
        value = self._fetch_byte()
        offset = self._fetch_byte()
        result = self._xim(value, self._load_indexed(offset))
        self._store_indexed(offset, result)
        return 8

    def _opcode_tmm_ind(self, _mode: AddressingMode) -> int:
        value = self._fetch_byte()
        offset = self._fetch_byte()
        self._tmm(value, self._load_indexed(offset))
        return 7

    def _opcode_asl_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._asl(value))
        return 7

    def _opcode_asl_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._asl(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_asr_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._asr(value))
        return 7

    def _opcode_asr_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._asr(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_lsr_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._lsr(value))
        return 7

    def _opcode_lsr_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._lsr(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_rol_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._rol(value))
        return 7

    def _opcode_rol_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._rol(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_ror_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._ror(value))
        return 7

    def _opcode_ror_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._ror(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_neg_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._neg(value))
        return 7

    def _opcode_neg_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._neg(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_com_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._com(value))
        return 7

    def _opcode_com_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._com(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_dec_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._dec(value))
        return 7

    def _opcode_dec_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._dec(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_inc_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._store_indexed(offset, self._inc(value))
        return 7

    def _opcode_inc_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        result = self._inc(self._load_extended(address))
        self.memory.store8(address & 0xFFFF, result & 0xFF)
        return 6

    def _opcode_clr_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._store_indexed(offset, self._clr())
        return 7

    def _opcode_clr_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        value = self._clr()
        self.memory.store8(address & 0xFFFF, value & 0xFF)
        return 6

    def _opcode_tst_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        value = self._load_indexed(offset)
        self._tst(value)
        return 7

    def _opcode_tst_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        value = self._load_extended(address)
        self._tst(value)
        return 6

    def _opcode_adda_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.a = self._add(self.a, operand)
        return 2

    def _opcode_adda_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        operand = self._load_direct(address)
        self.a = self._add(self.a, operand)
        return 3

    def _opcode_adda_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        operand = self._load_indexed(offset)
        self.a = self._add(self.a, operand)
        return 5

    def _opcode_adda_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load_extended(address)
        self.a = self._add(self.a, operand)
        return 4

    def _opcode_anda_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.a = self._and(self.a, operand)
        return 2

    def _opcode_anda_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.a = self._and(self.a, self._load_direct(address))
        return 3

    def _opcode_anda_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.a = self._and(self.a, self._load_indexed(offset))
        return 5

    def _opcode_anda_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.a = self._and(self.a, self._load_extended(address))
        return 4

    def _opcode_eora_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.a = self._eor(self.a, operand)
        return 2

    def _opcode_eora_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.a = self._eor(self.a, self._load_direct(address))
        return 3

    def _opcode_eora_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.a = self._eor(self.a, self._load_indexed(offset))
        return 5

    def _opcode_eora_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.a = self._eor(self.a, self._load_extended(address))
        return 4

    def _opcode_oraa_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.a = self._ora(self.a, operand)
        return 2

    def _opcode_oraa_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.a = self._ora(self.a, self._load_direct(address))
        return 3

    def _opcode_oraa_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.a = self._ora(self.a, self._load_indexed(offset))
        return 5

    def _opcode_oraa_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.a = self._ora(self.a, self._load_extended(address))
        return 4

    def _opcode_adca_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.a = self._adc(self.a, operand)
        return 2

    def _opcode_adca_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        operand = self._load_direct(address)
        self.a = self._adc(self.a, operand)
        return 3

    def _opcode_adca_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        operand = self._load_indexed(offset)
        self.a = self._adc(self.a, operand)
        return 5

    def _opcode_adca_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load_extended(address)
        self.a = self._adc(self.a, operand)
        return 4

    def _opcode_sbca_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.a = self._sbc(self.a, operand)
        return 2

    def _opcode_sbca_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        operand = self._load_direct(address)
        self.a = self._sbc(self.a, operand)
        return 3

    def _opcode_sbca_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        operand = self._load_indexed(offset)
        self.a = self._sbc(self.a, operand)
        return 5

    def _opcode_sbca_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load_extended(address)
        self.a = self._sbc(self.a, operand)
        return 4

    def _opcode_cmpa_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self._cmp(self.a, operand)
        return 2

    def _opcode_cmpa_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        operand = self._load_direct(address)
        self._cmp(self.a, operand)
        return 3

    def _opcode_cmpa_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        operand = self._load_indexed(offset)
        self._cmp(self.a, operand)
        return 5

    def _opcode_cmpa_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load_extended(address)
        self._cmp(self.a, operand)
        return 4

    def _opcode_suba_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.a = self._sub(self.a, operand)
        return 2

    def _opcode_suba_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        operand = self._load_direct(address)
        self.a = self._sub(self.a, operand)
        return 3

    def _opcode_suba_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        operand = self._load_indexed(offset)
        self.a = self._sub(self.a, operand)
        return 5

    def _opcode_suba_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load_extended(address)
        self.a = self._sub(self.a, operand)
        return 4

    def _opcode_ldab_imm(self, _mode: AddressingMode) -> int:
        value = self._fetch_byte()
        self.b = self._lda(value)
        return 2

    def _opcode_andb_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.b = self._and(self.b, operand)
        return 2

    def _opcode_andb_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.b = self._and(self.b, self._load_direct(address))
        return 3

    def _opcode_andb_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.b = self._and(self.b, self._load_indexed(offset))
        return 5

    def _opcode_andb_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.b = self._and(self.b, self._load_extended(address))
        return 4

    def _opcode_adcb_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.b = self._adc(self.b, operand)
        return 2

    def _opcode_adcb_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        operand = self._load_direct(address)
        self.b = self._adc(self.b, operand)
        return 3

    def _opcode_adcb_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        operand = self._load_indexed(offset)
        self.b = self._adc(self.b, operand)
        return 5

    def _opcode_adcb_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load_extended(address)
        self.b = self._adc(self.b, operand)
        return 4

    def _opcode_ldab_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.b = self._lda(self._load_direct(address))
        return 3

    def _opcode_ldab_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.b = self._lda(self._load_indexed(offset))
        return 5

    def _opcode_ldab_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.b = self._lda(self._load_extended(address))
        return 4

    def _opcode_addb_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.b = self._add(self.b, operand)
        return 2

    def _opcode_addb_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        operand = self._load_direct(address)
        self.b = self._add(self.b, operand)
        return 3

    def _opcode_addb_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        operand = self._load_indexed(offset)
        self.b = self._add(self.b, operand)
        return 5

    def _opcode_addb_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load_extended(address)
        self.b = self._add(self.b, operand)
        return 4

    def _opcode_eorb_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.b = self._eor(self.b, operand)
        return 2

    def _opcode_eorb_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.b = self._eor(self.b, self._load_direct(address))
        return 3

    def _opcode_eorb_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.b = self._eor(self.b, self._load_indexed(offset))
        return 5

    def _opcode_eorb_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.b = self._eor(self.b, self._load_extended(address))
        return 4

    def _opcode_cmpb_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self._cmp(self.b, operand)
        return 2

    def _opcode_cmpb_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._cmp(self.b, self._load_direct(address))
        return 3

    def _opcode_cmpb_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._cmp(self.b, self._load_indexed(offset))
        return 5

    def _opcode_cmpb_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._cmp(self.b, self._load_extended(address))
        return 4

    def _opcode_subb_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.b = self._sub(self.b, operand)
        return 2

    def _opcode_subb_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.b = self._sub(self.b, self._load_direct(address))
        return 3

    def _opcode_subb_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.b = self._sub(self.b, self._load_indexed(offset))
        return 5

    def _opcode_subb_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.b = self._sub(self.b, self._load_extended(address))
        return 4

    def _opcode_sbcb_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.b = self._sbc(self.b, operand)
        return 2

    def _opcode_sbcb_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        operand = self._load_direct(address)
        self.b = self._sbc(self.b, operand)
        return 3

    def _opcode_sbcb_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        operand = self._load_indexed(offset)
        self.b = self._sbc(self.b, operand)
        return 5

    def _opcode_sbcb_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load_extended(address)
        self.b = self._sbc(self.b, operand)
        return 4

    def _opcode_orab_imm(self, _mode: AddressingMode) -> int:
        operand = self._fetch_byte()
        self.b = self._ora(self.b, operand)
        return 2

    def _opcode_orab_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self.b = self._ora(self.b, self._load_direct(address))
        return 3

    def _opcode_orab_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.b = self._ora(self.b, self._load_indexed(offset))
        return 5

    def _opcode_orab_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.b = self._ora(self.b, self._load_extended(address))
        return 4

    def _opcode_stab_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._sta_direct(address, self.b)
        return 4

    def _opcode_stab_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._sta_indexed(offset, self.b)
        return 6

    def _opcode_stab_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._sta_extended(address, self.b)
        return 5

    def _opcode_adx_imm(self, _mode: AddressingMode) -> int:
        value = self._fetch_byte()
        self.ix = self._add16(self.ix, value & 0xFF)
        return 3

    def _opcode_adx_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        operand = self._load16_extended(address)
        self.ix = self._add16(self.ix, operand)
        return 7

    # ------------------------------------------------------------------
    # Opcode handlers (16-bit data)

    def _opcode_ldx_imm(self, _mode: AddressingMode) -> int:
        value = self._fetch_word()
        self._ldx(value)
        return 3

    def _opcode_ldx_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._ldx(self._load16_direct(address))
        return 4

    def _opcode_ldx_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._ldx(self._load16_indexed(offset))
        return 6

    def _opcode_ldx_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._ldx(self._load16_extended(address))
        return 5

    def _opcode_lds_imm(self, _mode: AddressingMode) -> int:
        value = self._fetch_word()
        self._lds(value)
        return 3

    def _opcode_lds_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._lds(self._load16_direct(address))
        return 4

    def _opcode_lds_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._lds(self._load16_indexed(offset))
        return 6

    def _opcode_lds_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._lds(self._load16_extended(address))
        return 5

    def _opcode_cpx_imm(self, _mode: AddressingMode) -> int:
        value = self._fetch_word()
        self._cpx(value)
        return 3

    def _opcode_cpx_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._cpx(self._load16_direct(address))
        return 4

    def _opcode_cpx_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._cpx(self._load16_indexed(offset))
        return 6

    def _opcode_cpx_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._cpx(self._load16_extended(address))
        return 5

    def _opcode_stx_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._stx_direct(address)
        return 5

    def _opcode_stx_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._stx_indexed(offset)
        return 7

    def _opcode_stx_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._stx_extended(address)
        return 6

    def _opcode_sts_dir(self, _mode: AddressingMode) -> int:
        address = self._fetch_byte()
        self._store16_direct(address, self.sp)
        self.cn = (self.ix & 0x8000) != 0
        self.cz = self.ix == 0
        self.cv = False
        return 5

    def _opcode_sts_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._store16_indexed(offset, self.sp)
        self.cn = (self.ix & 0x8000) != 0
        self.cz = self.ix == 0
        self.cv = False
        return 7

    def _opcode_sts_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._store16_extended(address, self.sp)
        self.cn = (self.ix & 0x8000) != 0
        self.cz = self.ix == 0
        self.cv = False
        return 6

    # ------------------------------------------------------------------
    # Opcode handlers (branches)

    def _opcode_bra_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, True)
        return 4

    def _opcode_bcc_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, not self.cc)
        return 4

    def _opcode_bhi_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, not (self.cc or self.cz))
        return 4

    def _opcode_bls_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, self.cc or self.cz)
        return 4

    def _opcode_bcs_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, self.cc)
        return 4

    def _opcode_bne_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, not self.cz)
        return 4

    def _opcode_beq_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, self.cz)
        return 4

    def _opcode_bvc_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, not self.cv)
        return 4

    def _opcode_bvs_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, self.cv)
        return 4

    def _opcode_bpl_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, not self.cn)
        return 4

    def _opcode_bmi_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, self.cn)
        return 4

    def _opcode_blt_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, self.cn ^ self.cv)
        return 4

    def _opcode_bgt_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, not (self.cz or (self.cn ^ self.cv)))
        return 4

    def _opcode_bge_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, not (self.cn ^ self.cv))
        return 4

    def _opcode_ble_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._branch(offset, self.cz or (self.cn ^ self.cv))
        return 4

    def _opcode_bsr_rel(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self._push_word(self.pc)
        self._branch(offset, True)
        return 8

    def _opcode_jsr_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        target = (self.ix + (offset & 0xFF)) & 0xFFFF
        self._push_word(self.pc)
        self.pc = target
        return 8

    def _opcode_jsr_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self._push_word(self.pc)
        self.pc = address
        return 9

    def _opcode_jmp_ind(self, _mode: AddressingMode) -> int:
        offset = self._fetch_byte()
        self.pc = (self.ix + (offset & 0xFF)) & 0xFFFF
        return 4

    def _opcode_jmp_ext(self, _mode: AddressingMode) -> int:
        address = self._fetch_word()
        self.pc = address & 0xFFFF
        return 3

    def _opcode_rts(self, _mode: AddressingMode) -> int:
        self.pc = self._pop_word()
        return 5

    def _opcode_rti(self, _mode: AddressingMode) -> int:
        self._pop_all_registers()
        return 10

    # ------------------------------------------------------------------
    # Memory helpers

    def _fetch_byte(self) -> int:
        value = self.memory.load8(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return value & 0xFF

    def _fetch_word(self) -> int:
        hi = self._fetch_byte()
        lo = self._fetch_byte()
        return ((hi << 8) | lo) & 0xFFFF

    def _load_direct(self, address: int) -> int:
        return self.memory.load8(address & 0xFF)

    def _load_indexed(self, offset: int) -> int:
        base = (self.ix + (offset & 0xFF)) & 0xFFFF
        return self.memory.load8(base)

    def _store_indexed(self, offset: int, value: int) -> None:
        base = (self.ix + (offset & 0xFF)) & 0xFFFF
        self.memory.store8(base, value & 0xFF)

    def _load_extended(self, address: int) -> int:
        return self.memory.load8(address & 0xFFFF)

    def _load16_direct(self, address: int) -> int:
        hi = self.memory.load8(address & 0xFF)
        lo = self.memory.load8((address + 1) & 0xFF)
        return ((hi << 8) | lo) & 0xFFFF

    def _load16_indexed(self, offset: int) -> int:
        base = (self.ix + (offset & 0xFF)) & 0xFFFF
        hi = self.memory.load8(base)
        lo = self.memory.load8((base + 1) & 0xFFFF)
        return ((hi << 8) | lo) & 0xFFFF

    def _load16_extended(self, address: int) -> int:
        hi = self.memory.load8(address & 0xFFFF)
        lo = self.memory.load8((address + 1) & 0xFFFF)
        return ((hi << 8) | lo) & 0xFFFF

    def _sta_flags(self, value: int) -> int:
        value &= 0xFF
        self.cn = (value & 0x80) != 0
        self.cz = value == 0
        self.cv = False
        return value

    def _sta_direct(self, address: int, value: int) -> None:
        self.memory.store8(address & 0xFF, self._sta_flags(value))

    def _sta_indexed(self, offset: int, value: int) -> None:
        base = (self.ix + (offset & 0xFF)) & 0xFFFF
        self.memory.store8(base, self._sta_flags(value))

    def _sta_extended(self, address: int, value: int) -> None:
        self.memory.store8(address & 0xFFFF, self._sta_flags(value))

    def _store16_direct(self, address: int, value: int) -> None:
        hi = (value >> 8) & 0xFF
        lo = value & 0xFF
        self.memory.store8(address & 0xFF, hi)
        self.memory.store8((address + 1) & 0xFF, lo)

    def _store16_indexed(self, offset: int, value: int) -> None:
        base = (self.ix + (offset & 0xFF)) & 0xFFFF
        hi = (value >> 8) & 0xFF
        lo = value & 0xFF
        self.memory.store8(base, hi)
        self.memory.store8((base + 1) & 0xFFFF, lo)

    def _store16_extended(self, address: int, value: int) -> None:
        hi = (value >> 8) & 0xFF
        lo = value & 0xFF
        self.memory.store8(address & 0xFFFF, hi)
        self.memory.store8((address + 1) & 0xFFFF, lo)

    # ------------------------------------------------------------------
    # Arithmetic helpers

    def _lda(self, value: int) -> int:
        value &= 0xFF
        self.cn = (value & 0x80) != 0
        self.cz = value == 0
        self.cv = False
        return value

    def _and(self, x: int, y: int) -> int:
        result = (x & 0xFF) & (y & 0xFF)
        value = result & 0xFF
        self.cn = (value & 0x80) != 0
        self.cz = value == 0
        self.cv = False
        return value

    def _eor(self, x: int, y: int) -> int:
        value = ((x & 0xFF) ^ (y & 0xFF)) & 0xFF
        self.cn = (value & 0x80) != 0
        self.cz = value == 0
        self.cv = False
        return value

    def _ora(self, x: int, y: int) -> int:
        value = ((x & 0xFF) | (y & 0xFF)) & 0xFF
        self.cn = (value & 0x80) != 0
        self.cz = value == 0
        self.cv = False
        return value

    def _bit(self, x: int, y: int) -> None:
        result = (x & 0xFF) & (y & 0xFF)
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        self.cv = False

    def _nim(self, x: int, y: int) -> int:
        result = (x & 0xFF) & (y & 0xFF)
        value = result & 0xFF
        self.cz = value == 0
        self.cn = not self.cz
        self.cv = False
        return value

    def _oim(self, x: int, y: int) -> int:
        result = (x & 0xFF) | (y & 0xFF)
        value = result & 0xFF
        self.cz = value == 0
        self.cn = not self.cz
        self.cv = False
        return value

    def _xim(self, x: int, y: int) -> int:
        result = (x & 0xFF) ^ (y & 0xFF)
        value = result & 0xFF
        self.cz = value == 0
        self.cn = not self.cz
        self.cv = False
        return value

    def _tmm(self, x: int, y: int) -> None:
        value_x = x & 0xFF
        value_y = y & 0xFF
        if value_x == 0 or value_y == 0:
            self.cn = False
            self.cz = True
            self.cv = False
        elif value_y == 0xFF:
            self.cn = False
            self.cz = False
            self.cv = True
        else:
            self.cn = True
            self.cz = False
            self.cv = False

    def _tab(self) -> None:
        self.b = self._lda(self.a)

    def _tba(self) -> None:
        self.a = self._lda(self.b)

    def _tap(self) -> None:
        value = self.a & 0xFF
        self.ch = bool(value & 0x20)
        self.ci = bool(value & 0x10)
        self.cn = bool(value & 0x08)
        self.cz = bool(value & 0x04)
        self.cv = bool(value & 0x02)
        self.cc = bool(value & 0x01)

    def _tpa(self) -> None:
        value = 0xC0
        if self.ch:
            value |= 0x20
        if self.ci:
            value |= 0x10
        if self.cn:
            value |= 0x08
        if self.cz:
            value |= 0x04
        if self.cv:
            value |= 0x02
        if self.cc:
            value |= 0x01
        self.a = value & 0xFF

    def _dex(self) -> None:
        self.ix = (self.ix - 1) & 0xFFFF
        self.cz = self.ix == 0

    def _inx(self) -> None:
        self.ix = (self.ix + 1) & 0xFFFF
        self.cz = self.ix == 0

    def _des(self) -> None:
        self.sp = (self.sp - 1) & 0xFFFF

    def _ins(self) -> None:
        self.sp = (self.sp + 1) & 0xFFFF

    def _asl(self, value: int) -> int:
        total = (value & 0xFF) << 1
        result = total & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        self.cc = total > 0xFF
        self.cv = self.cn != self.cc
        return result

    def _asr(self, value: int) -> int:
        result = ((value & 0xFF) >> 1) | (value & 0x80)
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        self.cc = (value & 0x01) != 0
        self.cv = self.cn != self.cc
        return result & 0xFF

    def _lsr(self, value: int) -> int:
        result = (value & 0xFF) >> 1
        self.cn = False
        self.cz = result == 0
        self.cc = (value & 0x01) != 0
        self.cv = self.cn != self.cc
        return result & 0xFF

    def _rol(self, value: int) -> int:
        total = ((value & 0xFF) << 1) | (1 if self.cc else 0)
        result = total & 0xFF
        new_cc = total > 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        self.cc = new_cc
        self.cv = self.cn != self.cc
        return result

    def _ror(self, value: int) -> int:
        result = ((value & 0xFF) >> 1) | (0x80 if self.cc else 0)
        new_cc = (value & 0x01) != 0
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        self.cc = new_cc
        self.cv = self.cn != self.cc
        return result & 0xFF

    def _neg(self, value: int) -> int:
        total = - (value & 0xFF)
        result = total & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = total == 0
        self.cv = result == 0x80
        self.cc = result == 0x00
        return result

    def _com(self, value: int) -> int:
        result = (~value) & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        self.cv = False
        self.cc = True
        return result

    def _clr(self) -> int:
        self.cn = False
        self.cz = True
        self.cv = False
        self.cc = False
        return 0

    def _inc(self, value: int) -> int:
        result = (value + 1) & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        self.cv = (value & 0xFF) == 0x7F
        return result

    def _dec(self, value: int) -> int:
        result = (value - 1) & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        self.cv = (value & 0xFF) == 0x80
        return result

    def _daa(self) -> int:
        original = self.a & 0xFF
        value = original
        if (value & 0x0F) >= 0x0A or self.ch:
            value += 0x06
        carry_adjust = (value & 0xF0) >= 0xA0
        if carry_adjust:
            value += 0x60
        result = value & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        signed_original = self._to_signed(original)
        self.cv = (signed_original > 0 and self.cn) or (signed_original < 0 and not self.cn)
        self.a = result
        self.cc = carry_adjust or self.cc
        return result

    def _tst(self, value: int) -> None:
        masked = value & 0xFF
        self.cn = (masked & 0x80) != 0
        self.cz = masked == 0
        self.cv = False
        self.cc = False

    def _ldx(self, value: int) -> None:
        self.ix = value & 0xFFFF
        self.cn = (self.ix & 0x8000) != 0
        self.cz = self.ix == 0
        self.cv = False

    def _lds(self, value: int) -> None:
        self.sp = value & 0xFFFF
        self.cn = (self.sp & 0x8000) != 0
        self.cz = self.sp == 0
        self.cv = False

    def _cpx(self, value: int) -> None:
        diff = (self.ix - (value & 0xFFFF)) & 0x1FFFF
        result = diff & 0xFFFF
        self.cn = (result & 0x8000) != 0
        self.cz = result == 0
        ix_signed = self._to_signed16(self.ix)
        val_signed = self._to_signed16(value)
        self.cv = (ix_signed > 0 and val_signed < 0 and self.cn) or (
            ix_signed < 0 and val_signed > 0 and not self.cn
        )

    def _stx_direct(self, address: int) -> None:
        self._store16_direct(address, self.ix)
        self.cn = (self.ix & 0x8000) != 0
        self.cz = self.ix == 0
        self.cv = False

    def _stx_indexed(self, offset: int) -> None:
        self._store16_indexed(offset, self.ix)
        self.cn = (self.ix & 0x8000) != 0
        self.cz = self.ix == 0
        self.cv = False

    def _stx_extended(self, address: int) -> None:
        self._store16_extended(address, self.ix)
        self.cn = (self.ix & 0x8000) != 0
        self.cz = self.ix == 0
        self.cv = False

    def _add(self, x: int, y: int) -> int:
        total = (x & 0xFF) + (y & 0xFF)
        result = total & 0xFF
        self.ch = ((x & 0x0F) + (y & 0x0F)) > 0x0F
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        sx = self._to_signed(x)
        sy = self._to_signed(y)
        self.cv = (sx > 0 and sy > 0 and self.cn) or (sx < 0 and sy < 0 and not self.cn)
        self.cc = total > 0xFF
        return result

    def _adc(self, x: int, y: int) -> int:
        carry_in = 1 if self.cc else 0
        total = (x & 0xFF) + (y & 0xFF) + carry_in
        result = total & 0xFF
        self.ch = ((x & 0x0F) + (y & 0x0F)) > 0x0F
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        sx = self._to_signed(x)
        sy = self._to_signed(y)
        self.cv = (sx > 0 and sy > 0 and self.cn) or (sx < 0 and sy < 0 and not self.cn)
        self.cc = total > 0xFF
        return result

    def _sbc(self, x: int, y: int) -> int:
        borrow = 1 if self.cc else 0
        total = (x & 0xFF) - (y & 0xFF) - borrow
        result = total & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        sx = self._to_signed(x)
        sy = self._to_signed(y)
        self.cv = (sx > 0 and sy < 0 and self.cn) or (sx < 0 and sy > 0 and not self.cn)
        self.cc = (total & 0x100) != 0
        return result

    def _sub(self, x: int, y: int) -> int:
        total = (x & 0xFF) - (y & 0xFF)
        result = total & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        sx = self._to_signed(x)
        sy = self._to_signed(y)
        self.cv = (sx > 0 and sy < 0 and self.cn) or (sx < 0 and sy > 0 and not self.cn)
        self.cc = (total & 0x100) != 0
        return result

    def _cmp(self, x: int, y: int) -> None:
        total = (x & 0xFF) - (y & 0xFF)
        result = total & 0xFF
        self.cn = (result & 0x80) != 0
        self.cz = result == 0
        sx = self._to_signed(x)
        sy = self._to_signed(y)
        self.cv = (sx > 0 and sy < 0 and self.cn) or (sx < 0 and sy > 0 and not self.cn)
        self.cc = (total & 0x100) != 0

    def _add16(self, x: int, y: int) -> int:
        total = (x & 0xFFFF) + (y & 0xFFFF)
        result = total & 0xFFFF
        self.cn = (result & 0x8000) != 0
        self.cz = result == 0
        sx = self._to_signed16(x)
        sy = self._to_signed16(y)
        self.cv = (sx > 0 and sy > 0 and self.cn) or (sx < 0 and sy < 0 and not self.cn)
        self.cc = (total & 0x10000) != 0
        return result

    def _push_word(self, value: int) -> None:
        self.sp = (self.sp - 2) & 0xFFFF
        hi = (value >> 8) & 0xFF
        lo = value & 0xFF
        self.memory.store8((self.sp + 1) & 0xFFFF, hi)
        self.memory.store8((self.sp + 2) & 0xFFFF, lo)

    def _pop_word(self) -> int:
        hi = self.memory.load8((self.sp + 1) & 0xFFFF)
        lo = self.memory.load8((self.sp + 2) & 0xFFFF)
        self.sp = (self.sp + 2) & 0xFFFF
        return ((hi << 8) | lo) & 0xFFFF

    def _push_all_registers(self) -> None:
        ccr = 0xC0
        if self.ch:
            ccr |= 0x20
        if self.ci:
            ccr |= 0x10
        if self.cn:
            ccr |= 0x08
        if self.cz:
            ccr |= 0x04
        if self.cv:
            ccr |= 0x02
        if self.cc:
            ccr |= 0x01
        self._store16_extended((self.sp - 1) & 0xFFFF, self.pc)
        self._store16_extended((self.sp - 3) & 0xFFFF, self.ix)
        self.memory.store8((self.sp - 4) & 0xFFFF, self.a & 0xFF)
        self.memory.store8((self.sp - 5) & 0xFFFF, self.b & 0xFF)
        self.memory.store8((self.sp - 6) & 0xFFFF, ccr & 0xFF)
        self.sp = (self.sp - 7) & 0xFFFF

    def _pull_byte(self) -> int:
        value = self.memory.load8((self.sp + 1) & 0xFFFF)
        self.sp = (self.sp + 1) & 0xFFFF
        return value

    def _push_byte(self, value: int) -> None:
        self.memory.store8(self.sp & 0xFFFF, value & 0xFF)
        self.sp = (self.sp - 1) & 0xFFFF

    def _pop_all_registers(self) -> None:
        self.sp = (self.sp + 7) & 0xFFFF
        ccr_addr = (self.sp - 6) & 0xFFFF
        ccr = self.memory.load8(ccr_addr)
        self.ch = bool(ccr & 0x20)
        self.ci = bool(ccr & 0x10)
        self.cn = bool(ccr & 0x08)
        self.cz = bool(ccr & 0x04)
        self.cv = bool(ccr & 0x02)
        self.cc = bool(ccr & 0x01)
        self.b = self.memory.load8((self.sp - 5) & 0xFFFF)
        self.a = self.memory.load8((self.sp - 4) & 0xFFFF)
        self.ix = self._load16_extended((self.sp - 3) & 0xFFFF)
        self.pc = self._load16_extended((self.sp - 1) & 0xFFFF)

    def _service_interrupt(self, vector: int, cycles: int) -> int:
        self._push_all_registers()
        self.pc = self._load16_extended(vector)
        self._waiting = False
        return cycles

    # ------------------------------------------------------------------
    # Branch helper

    def _branch(self, offset: int, condition: bool) -> None:
        if condition:
            signed = offset - 0x100 if offset & 0x80 else offset
            self.pc = (self.pc + signed) & 0xFFFF

    # ------------------------------------------------------------------
    # Utility conversions

    @staticmethod
    def _to_signed(value: int) -> int:
        value &= 0xFF
        return value - 0x100 if value & 0x80 else value

    @staticmethod
    def _to_signed16(value: int) -> int:
        value &= 0xFFFF
        return value - 0x10000 if value & 0x8000 else value
