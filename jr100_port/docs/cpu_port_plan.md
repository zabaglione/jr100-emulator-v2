# CPU (MB8861) 移植方針

## 対象
- Java `src/jp/asamomiji/emulator/CPU.java`
- Java `src/jp/asamomiji/emulator/device/MB8861.java`
- 依存ユーティリティ: `StateSavable`, `Device`, `Computer`, `MemorySystem`

## Python 側構成
- `jr100_port/cpu/mb8861.py`: CPU クラス本体
- `jr100_port/cpu/decoder.py`: オペコード→ハンドラ/アドレッシングモード
- `jr100_port/cpu/instructions.py`: 命令テーブル定義 (`Instruction` dataclass)
- `jr100_port/cpu/addressing.py`: アドレッシングモード utilities
- `jr100_port/cpu/flags.py`: フラグ操作 helpers
- `jr100_port/tests/cpu/test_mb8861_execute.py`: ステップ単位テスト
- `jr100_port/tests/cpu/test_instructions_table.py`: 命令定義検証

## 実装ステップ（t-wada）
1. 命令定義テーブルの最小構造（Instruction dataclass, Addressing enum）→レジスタ変化をハードコードしたスモールテストで赤
2. `MB8861.fetch_opcode()` → `decoder` → `execute_opcode()` の骨格を実装し、NOP/LD 等の簡単な命令から緑化
3. 逐次命令を追加（算術、分岐、スタック、割り込み）→ Java 実装の switch-case と1:1対応
4. 割り込み制御（NMI/IRQ/WAI/SWI）とクロック計数 → `Computer` / `TimeManager` 連携を仮 stub でテスト
5. Illegal opcode 検出と例外 → テストで assertRaises

## 参照データ
- Java `MB8861` の `execute()` / `calc()` / `incrementClock()` 実装からサイクル数とフラグ挙動を写経
- 命令タイミング表: 付属資料 or ソースコメント

## テストケース（初期）
### test_mb8861_execute.py
- `test_nop_advances_pc_and_cycles`
- `test_lda_immediate_loads_accumulator`
- `test_sta_direct_stores_value`
- `test_bcc_taken_updates_pc`
- `test_jsr_rts_stack_roundtrip`

### 命令実装ガイドライン
1. Java 実装で使用されている opcode を `instructions.py` に登録し、`MB8861._register_instructions()` から呼び出す。
2. ハンドラは `MB8861` メソッド（または専用 helper）として実装し、テーブルで引数に渡す。
3. サイクル数は Java の `getInstructionCycle` / `clockCount` 参照。ページ跨ぎ加算などがある命令はメソッド側で追加し、戻り値に含める。
4. アキュムレータ/レジスタ/フラグ更新は Java の `calc*` 系 helper を基に `flags.py` に切り出し、単体テストで検証。
5. opcode 未登録の場合は `KeyError` → `NotImplementedError` 等へラップし、テストで検証。

### 現在実装済み
- `NOP (0x01)`
- `LDAA #/dir/indexed/ext (0x86/0x96/0xA6/0xB6)`
- `STAA dir/indexed/ext (0x97/0xA7/0xB7)`
- `ANDA #/dir/indexed/ext (0x84/0x94/0xA4/0xB4)`
- `EORA #/dir/indexed/ext (0x88/0x98/0xA8/0xB8)`
- `ORAA #/dir/indexed/ext (0x8A/0x9A/0xAA/0xBA)`
- `ADDA #imm (0x8B)`
- `ADCA #imm (0x89)`
- `SBCA #imm (0x82)`
- `CMPA #imm (0x81)`
- `SUBA #imm (0x80)`
- `BCC rel (0x24)`
- `CMPB #imm (0xC1)`
- `CMPB dir/indexed/ext (0xD1/0xE1/0xF1)`
- `LDAB #/dir/indexed/ext (0xC6/0xD6/0xE6/0xF6)`
- `STAB dir/indexed/ext (0xD7/0xE7/0xF7)`
- `ANDB #/dir/indexed/ext (0xC4/0xD4/0xE4/0xF4)`
- `EORB #/dir/indexed/ext (0xC8/0xD8/0xE8/0xF8)`
- `ORAB #/dir/indexed/ext (0xCA/0xDA/0xEA/0xFA)`
- `ASLA/B (0x48/0x58)`、`ASRA/B (0x47/0x57)`、`LSRA/B (0x44/0x54)`
- `ROLA/B (0x49/0x59)`、`RORA/B (0x46/0x56)`
- `NEGA/B (0x40/0x50)`、`COMA/B (0x43/0x53)`
- `DECA/B (0x4A/0x5A)`、`INCA/B (0x4C/0x5C)`、`CLRA/B (0x4F/0x5F)`、`TSTA/B (0x4D/0x5D)`
- `ASL/ASR/LSR/ROL/ROR` indexed/ext (0x68/0x78、0x67/0x77、0x64/0x74、0x69/0x79、0x66/0x76)
- `NEG/COM/DEC/INC` indexed/ext (0x60/0x70、0x63/0x73、0x6A/0x7A、0x6C/0x7C)
- `CLR indexed/ext (0x6F/0x7F)`、`TST indexed/ext (0x6D/0x7D)`
- `BITA #/dir/indexed/ext (0x85/0x95/0xA5/0xB5)`、`BITB #/dir/indexed/ext (0xC5/0xD5/0xE5/0xF5)`
- `PSHA/PSHB (0x36/0x37)`、`PULA/PULB (0x32/0x33)`
- `TAB/TBA (0x16/0x17)`、`TAP/TPA (0x06/0x07)`
- `WAI/SWI (0x3E/0x3F)`
- `NIM/OIM/XIM (0x71/0x72/0x75)`
- `DEX/INX (0x09/0x08)`、`DES/INS (0x34/0x31)`
- `CLC/CLI/CLV (0x0C/0x0E/0x0A)`、`SEC/SEI/SEV (0x0B/0x0F/0x0D)`
- `SUBB #imm (0xC0)`
- `SUBB dir/indexed/ext (0xD0/0xE0/0xF0)`
- `BNE rel (0x26)`
- `BRA rel (0x20)`
- `BEQ rel (0x27)`
- `BMI rel (0x2B)`
- `BGE rel (0x2C)`
- `BLE rel (0x2F)`
- `LDX #/dir/indexed/ext (0xCE/0xDE/0xEE/0xFE)`
- `CPX #/dir/indexed/ext (0x8C/0x9C/0xAC/0xBC)`
- `STX dir/indexed/ext (0xDF/0xEF/0xFF)`
- `BSR rel (0x8D)`
- `JSR indexed/ext (0xAD/0xBD)`
- `RTS (0x39)`
- `RTI (0x3B)`

Indexedアドレッシングは Java 実装に合わせて「オフセットを 8bit 符号無し」として扱い、IX+offset でベースを算出。テストでは 0xFF や 0xFE を使って wrap 挙動を検証済み。

スタック操作（BSR/JSR/RTS/RTI）は Java 実装の `store16_ext((short)(SP + 1), value)` などと同じ順序でハイ・ローバイトを格納し、`RTI` では `pushAllRegisters`/`popAllRegisters` 相当の CCR→B→A→IX→PC の復元順を踏襲。

各命令は `jr100_port/tests/cpu/test_mb8861_execute.py` でフラグ設定（CN/CZ/CC/CV/CH）まで検証済み。

なお `STAA` / `STAB` は Java 版 `computer.clockCount` と同じく dir=4, ind=6, ext=5 サイクルへ修正し、pytest で緑確認済み。

### test_instructions_table.py
- `test_opcode_table_has_256_entries`
- `test_illegal_opcode_raises`

## 注意点
- Java `CPU` は `Computer` 経由で MemorySystem を操作 → Python では `memory` インターフェイスを注入
- Java 版は `clockCount` に cycle を加算 → Python では `step()` 戻り値で返却し TimeManager へ委譲
- Java 実装の `calc*` 系（加算/減算/比較）をヘルパー化し、フラグ一致をテストで担保
- Big-endian/Little-endian 取り扱いは Java の `fetchImmediate` 等を忠実移植

## 未実装命令と優先度（2025-09-27 時点）
- 解析結果：Java 版で使用している opcode 203 個のうち、Python 実装に未登録の命令が 53 個存在。
- `jr100_port/cpu/mb8861.py` と `src/jp/asamomiji/emulator/device/MB8861.java` の差分を機械抽出し、以下の 3 ステージへ分類。
- 優先度は STARFIRE・BASIC 起動の実挙動から決定。Stage A を実装しないとリセットベクタ先頭で `KeyError` が発生する。

### Stage A（最優先：ブート・制御フロー）
- `JMP` 系: `OP_JMP_IND (0x6E)`, `OP_JMP_EXT (0x7E)`
- スタック転送: `OP_TSX_IMP (0x30)`, `OP_TXS_IMP (0x35)`, `OP_LDS_IMM/ DIR/ IND/ EXT (0x8E/0x9E/0xAE/0xBE)`, `OP_STS_DIR/IND/EXT (0x9F/0xAF/0xBF)`
- 分岐（条件フラグ制御を含む）: `OP_BHI_REL (0x22)`, `OP_BLS_REL (0x23)`, `OP_BCS_REL (0x25)`, `OP_BVC_REL (0x28)`, `OP_BVS_REL (0x29)`, `OP_BPL_REL (0x2A)`, `OP_BLT_REL (0x2D)`, `OP_BGT_REL (0x2E)`
- 8bit 減算基礎: `OP_SBA_IMP (0x10)`, `OP_SUBA_DIR/IND/EXT (0x90/0xA0/0xB0)`, `OP_SBCA_DIR/IND/EXT (0x92/0xA2/0xB2)`, `OP_SBCB_IMM/DIR/IND/EXT (0xC2/0xD2/0xE2/0xF2)`。

### Stage B（完了：8bit 算術・比較・B レジスタ拡張）
- A/B レジスタ算術とキャリー連携（ADDA/ADCA/ADDB/ADCB 各種）を移植済み。pytest で加算・繰上り・ハーフキャリーの挙動を検証。
- 比較命令 `CBA` と `CMPA` の DIR/IND/EXT を実装し、CN/CZ/CC フラグの期待値をテストで固定。
- BCD 補正 `DAA` とレジスタ結合 `ABA` を移植、JR100 の数値入力系ワークロードで必要な CCR 挙動 (CC/CV) を確認。
- 付随テスト: `test_adda_*`, `test_adca_*`, `test_addb_*`, `test_adcb_*`, `test_cmpa_*`, `test_cba_*`, `test_daa_*`, `test_aba_*` を追加し 155 ケースに拡張。

### Stage C（進行中：拡張命令・IX 演算・メモリマスク）
- 拡張 I/O ビット操作 `OP_TMM_IND (0x7B)` と IX 加算拡張 `OP_ADX_IMM/EXT (0xEC/0xFC)` を移植済み。pytest でゼロ/フルマスク/一般ケースおよび 16bit 加算のフラグ挙動を確認。
- 残タスク：JR-100 拡張機能（ADX + STS 連携、フォント更新シーケンス）を含む統合テスト整備と、命令表の再集計。

### フォローアップタスク
1. ADX/STS/フォント更新を含む統合シナリオを作成し、STARFIRE デモでの動作確認を自動化する。
2. 残る Stage C 命令（TMM 応用シーンや ADX と VIA の連携など）を洗い出し、必要なら追加テストを作成する。
3. 命令表の総数とテストカバレッジを再集計し、`test_instructions_table.py` で Stage C 完了時のチェックを拡充する。
