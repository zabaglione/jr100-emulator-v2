* 目的

  * リポジトリ「jr100-emulator-v2」（Java版）をPython（Pygame）へ移植するための実行可能な作業指示を「AGENTS.md」として整備する。
  * 実装作業は対話型コード生成（Codex系）を前提に、反復可能なプロンプト、評価基準、テスト計画を含めた運用手順を定義する。

* スコープ

  * Java版の機能（CPU/メモリ/キーボード/表示/サウンド/外部ファイル読込）をPythonで再現。
  * 画面・入力・音声はPygameを用いて置換。
  * 可能な場合、Python製ライブラリ（jr100emulib）の再利用も検討（互換性・品質を検証した上で採否判断）。([asamomiji.jp][1])
  * 既存の配布形態（jar, jinput等）の置換・削除方針を定義。([GitHub][2])

* 成果物

  * ルートに「AGENTS.md」：エージェント運用方針、プロンプト、タスク分解、受入条件、テスト手順、ディレクトリ構成指針、ライセンス・依存関係。
  * Python実装一式（`/pyjr100/`）と最小起動スクリプト（`run.py`）。
  * 自動テスト（pytest）と簡易ゴールデンテスト（ビデオRAM描画・キースキャン等）。

* 非スコープ

  * 新機能追加（JR-100拡張仕様や新UI）。
  * オリジナル以外のPRG/ROM配布。
  * Web配信（pygame-web等）最適化。

* 前提・制約

  * 元リポジトリはJava 12+、JInputを利用（ゲームパッド）し、配布はjar中心。([GitHub][2])
  * Python 3.10+、Pygame 2.5+ を想定。
  * OSはWindows/macOS/Linux。
  * ライセンスはMITに従う（派生物に明記）。([GitHub][2])

* 受入基準（抜粋）

  * 起動後、JR-100の基本画面が所定解像度で表示され、キーボードからのBASIC入力と描画が応答する。
  * 最低1本のサンプルPRGがロード・実行可能（ファイル形式はPROGに準拠。エミュ側ローダの互換層を提供）。([asamomiji.jp][1])
  * CPUクロック・タイマ駆動でフレーム落ちが致命にならない（60FPS目標、内部は可変Δt許容）。
  * 主要ユニットにpytestがあり、CIで自動実行される。

---

# AGENTS.md

## 0. 概要

* 目的：Java版「JR-100 Emulator v2」コードベースをPython + Pygameへ移植し、等価機能を再現する。
* 原典：`zabaglione/jr100-emulator-v2`（fork元は`kemusiro/jr100-emulator-v2`）。構成は`src/jp/asamomiji/**`配下にJava実装、jar配布、JInput同梱。([GitHub][2])
* 参考：Pythonパッケージ「jr100emulib」（FSKローダや関連ツール群の情報あり）。必要に応じて再利用・比較検証を行う。([asamomiji.jp][1])

## 1. リポジトリ構成（移植後の提案）

```
/pyjr100/                 # Python実装ルート
  cpu/                    # CPUエミュレーション（命令/アドレッシング/フラグ）
  bus/                    # バス、メモリ、I/Oデコーダ
  video/                  # 文字/グラフィック描画、タイル/フォント、VRAMミラー
  audio/                  # 簡易サウンド（将来PCM/矩形波等）
  io/                     # キーボード、（任意）ゲームパッド
  rom/                    # ROM/フォント/初期データ（*.prgは置かない方針）
  loader/                 # PROG形式ローダ（jr100emulib互換検討）
  ui/                     # Pygame画面/イベントループ
  utils/                  # ログ/設定/タイマ等
tests/                    # pytest一式（CPU命令、VRAM、キー、ローダ）
run.py                    # エントリポイント
AGENTS.md                 # 本ファイル
README.md                 # 起動手順・依存関係
LICENSE                   # MIT（原典継承）
```

## 2. 技術方針

* 表示：Pygame（固定解像度のスケーリング表示、整数倍スケールを優先）。
* 入力：Pygameキーボード（JIS/US差異はスキャンコード→マトリクス変換で吸収）。ゲームパッドは後続。
* 音：初期は無音または簡易波形。オリジナルのJInput/DLL依存を全廃。([GitHub][2])
* ファイル：PROG形式の読み込みに対応。内部ローダ実装 or `jr100emulib`のコンポーネント流用を比較検討。([asamomiji.jp][1])
* タイマ：固定ステップ（例1/60秒）＋内部サブステップ。音実装時はオーディオバッファに同期。
* **互換性**：Java版 (`jr100-emulator-v2`) の挙動を全面的に模倣することを第一優先にする。フォント更新やCMODE処理を含む描画、VRAM/UDCハンドリング、VIA周辺の状態変化など、差分が判明した場合は必ずJava版の実装を参照し仕様を一致させること。

## 3. 主要タスク分解（Codex用指示付き）

### T1. 原典の調査・境界定義

* 目的：Java側のコンポーネント（CPU、メモリ、VRAM、キーボード、サウンド、ローダ）の所在と責務を同定し、Python側の対応表を作成。
* Codexプロンプト例：

  * 「`src/jp/asamomiji`配下のクラス一覧と依存関係を抽出し、CPU/メモリ/表示/入力/音/ローダ別に表へ整理。各クラスのpublic APIと状態を要約。」

### T2. CPUコア実装

* 目的：命令セット・フラグ・割り込み・タイミングをPythonで再現。
* 成果：`pyjr100/cpu/core.py`, `decoder.py`, `flags.py` ほか。
* 受入：命令ごとのユニットテスト（ゴールデン：Javaの単体テスト/コメント仕様を転記）。
* Codexプロンプト例：

  * 「この命令表からPythonクラス`CPU`の`step()`と`exec_opcode()`を実装。命令毎に副作用（レジスタ/フラグ/PC/サイクル）をテーブル駆動化。」

#### T2設計メモ（MB8861命令テーブル化方針）

* **データ構造**
  * `pyjr100/cpu/opcodes.py`（新規）に`Instruction`データクラスを定義。フィールド例：`opcode`（0-255）、`mnemonic`、`mode`、`cycles`、`handler`（呼び出すメソッド名）、`extra_cycles`（分岐成功やページ跨ぎ用）。
  * アドレッシングモードは列挙型`AddressingMode`で表現（`IMMEDIATE`, `DIRECT`, `INDEXED`, `EXTENDED`, `INHERENT`, `RELATIVE`, `IMMEDIATE16`, `DIRECT16`, `INDEXED16`, `EXTENDED16`, `SPECIAL`など）。
  * Python側`CPU`は、命令テーブルを辞書（key: opcode, value: Instruction）もしくは256エントリのリストで保持。未定義opcodeは`self.illegal(opcode)`で例外を送出し、テストで検知。

* **実行ループ**
  * `CPU.step()`は現在の`pc`から1バイト読み取り、テーブルを引いてハンドラ関数を実行。ハンドラは必要に応じて追加オペランドを取得するため、`fetch_operand(mode)`ユーティリティを活用。
  * ハンドラは演算結果とフラグ更新を行い、戻り値として追加サイクル（ブランチ成功など）を返す。`step()`内で基礎サイクルとの合計を返却し、上位の`run_for(cycles)`が積算。
  * 割り込み処理（NMI/IRQ/SWI）はステップ前にキューを確認し、必要なら`service_interrupt(vector, cycles)`を実行して12サイクル加算（Java版`computer.clockCount += 12`に相当）。

* **レジスタ/フラグ**
  * 8bitレジスタ`A/B`、16bitレジスタ`PC/IX/SP`は`int`で保持し、`mask8`/`mask16`で常に正規化。
  * フラグはビットマスク（例: `FLAG_C = 0x01`など）で`cc`レジスタを表現し、プロパティ経由で取得/更新。Java版の`CH/CI/CN/CZ/CV/CC`に対応。
  * `tpa/tap`などCCRを直接扱う命令は、ビットマスク操作で実装。

* **アドレッシングモード補助**
  * 即値: `fetch_byte()`, `fetch_word()`でPCを進めつつ値取得。
  * 直接: 下位8bitでゼロページアクセス。`load8_direct(addr)`等、Java版`load8_dir`をラップ。
  * インデックス: `IX + offset`（符号なし8bit）を16bitで加算。`store8_indexed`, `load16_indexed`等を用意。
  * 拡張: 16bitアドレス。
  * 相対: 分岐命令はsigned 8bitオフセットで`pc = (pc + offset) & 0xFFFF`。成功時は基礎サイクルに+1、ページ跨ぎがあれば+1（Java版では+3/4固定だが、確認のうえPythonでも固定値にする）。

* **特殊命令**
  * `RTI/RTS/JSR/BSR`: スタック操作（`push_byte`, `pull_byte`, `push_word`, `pull_word`）をヘルパーとして実装。
  * `WAI`: `wai_latch`フラグを立て、`step()`が以降の割り込み待機状態へ遷移するよう制御。
  * `SWI`: Java版同様に`pushAllRegisters()`後にベクタロード、12サイクル加算。
  * `HALT`: `halt()`でフラグが立った場合は命令処理を一時停止し、外部から`resume()`されるまで消費サイクル0で待機。

* **タイミング管理**
  * Java版`computer.clockCount`の増分に相当する値を`step()`の戻り値で扱う。Pythonの`run_for(cycles)`は累積サイクルが目標以上になった時点で余剰サイクルを返す。
  * 割り込み発生時は`service_interrupt`が消費サイクルを返し、`run_for`側で合算する。

* **テスト方針連動**
  * `tests/cpu/test_opcodes.py`（予定）で命令ごとのゴールデン値（レジスタ・フラグ・サイクル）を検証。Java版helperメソッドの挙動（`add`, `adc`, `bit`, `sbc`等）に対する単体テストも個別に追加。
  * 分岐命令は成功/失敗、符号付きオフセット、ページ跨ぎケースを別々に検証。

### T3. メモリ/バス

* 目的：ROM/RAMマップ、I/Oデコード、VRAM窓口。
* 成果：`pyjr100/bus/memory.py`, `bus.py`, `io_map.py`。
* 受入：境界アドレスの読み書きテスト、I/Oミラー/エイリアス再現。
* Codexプロンプト例：

  * 「仕様表に基づき16bitアドレス空間のメモリマップを実装。読み書きフックでI/O領域へディスパッチ。」

### T4. 映像（VRAM→スクリーン）

* 目的：文字セル/フォント/属性、スキャン→Pygame Surface。
* 成果：`pyjr100/video/renderer.py`, `font.py`, `palette.py`。
* 受入：既定フォントでの文字描画一致、BASICプロンプトのレイアウト一致。
* Codexプロンプト例：

  * 「VRAMレイアウトを受け取り、タイル描画→Pygame Surfaceへ反映する`render_frame(vram)`を実装。整数スケール拡大。」

### T5. 入力（キーボード）

* 目的：PygameキーイベントをJR-100のキーマトリクスへ写像。リピート/モディファイア対応。
* 成果：`pyjr100/io/keyboard.py`。
* 受入：BASIC入力のキー配列が概ね再現。

### T6. 音（段階的）

* 目的：最小のビープ等から開始。タイミング安定後に強化。
* 成果：`pyjr100/audio/`一式。
* 受入：起動時エラーがなく無音でも実行可。

### T7. ローダ（PROG）

* 目的：PRGの読込・配置・実行フロー。必要に応じ`jr100emulib`参照。([asamomiji.jp][1])
* 成果：`pyjr100/loader/prog.py`。
* 受入：サンプルPRG1本がロード・起動できる。
* Codexプロンプト例：

  * 「PROG形式仕様に基づき、Pythonで`load_prg(fp) -> memory_patch`を実装。BASIC/機械語いずれも対応。」

### T8. UI/メインループ

* 目的：Pygame初期化、メインループ、FPS制御、メニュー/ROM選択（簡易）。
* 成果：`pyjr100/ui/app.py`, `run.py`。
* 受入：ウィンドウ表示、FPS約60、入力応答。

### T9. テスト/CI

* 目的：pytest導入、CPU/VRAM/ローダの自動化。
* 成果：`tests/**`, GitHub Actions（任意）。
* 受入：ローカル/CIでgreen。

## 4. 作業順序（推奨）

1. T1 調査 → 2) T2/T3（CPU/バス核） → 3) T4（表示） → 4) T5（入力） → 5) T7（ローダ） → 6) T8（統合） → 7) T6（音） → 8) T9（仕上げ）

## 5. 受入テスト（サンプル）

* 起動：`python run.py --rom ./assets/jr100rom.prg` で起動。BASICプロンプトが表示されること。
* 入力：`PRINT 1+1` の表示・結果。
* 画面：既定フォントで80×?相当の文字格子（原典に準拠）で崩れがない。
* ロード：`LOAD "TEST"` のフローが成立（テストPRG）。PROGヘッダの判定・配置が正しいこと。([asamomiji.jp][1])

## 6. Codex運用・プロンプト設計

* 方針：

  * 1タスク＝1プロンプト（最大でも2〜3ファイルの変更に限定）。
  * プロンプトには「入出力仕様・インターフェイス・受入条件・テスト」を明記。
  * 差分レビュー前提（`git diff`前後のコンテキストを提示）。

* ひな型：

  ```
  あなたはJR-100エミュレータの移植担当です。
  目的: {タスク要約}
  既存: {関連ファイルと現状の要点}
  仕様: {入出力/制約/例外}
  成果: {生成/更新するファイル一覧}
  受入: {テスト観点/性能/FPS/互換性}
  次へ: {続きのタスク誘導}
  出力形式: 完全なコード差し替え（ファイル単位）/必要な場合は簡潔な解説
  ```

* 例（VRAM→Surface）：

  ```
  目的: VRAMバッファからPygame Surfaceを構築するrendererを実装
  既存: pyjr100/video/renderer.py は空。font.pyに8x8グリフがある想定
  仕様: 入力bytes(vram), 出力Surface; 文字セルは8x8; パレットは白黒/モノクロ開始
  成果: renderer.py の render_frame(vram)->Surface
  受入: サンプルVRAM（"READY"表示）とスクリーンショット一致
  次へ: キー入力→VRAM更新で応答確認
  ```

## 7. 互換・参考情報

* Java側配布物（`jr100v2.jar`、JInput DLL等）と実行・ROM吸出し手順はREADMEに記載。Pygame移植ではJInput依存を除去。([GitHub][2])
* PROG形式やツール群（fskloader、jr100emulib）の参考情報。([asamomiji.jp][1])

## 8. ライセンス・法務

* オリジナルはMIT。派生物のヘッダと`LICENSE`を整備。第三者配布が困難なROM/PRGは含めない。([GitHub][2])

## 9. 開発・実行要件

* Python 3.10+、pygame 2.5+、pytest。
* Windows/macOS/Linux。
* JR-100 BASIC ROM (`jr100rom.prg`) を必ず用意し、`python run.py --rom <path>` で起動すること。

## 10. リスクと軽減策

* CPUのタイミング差：描画と音に影響 → 固定ステップ＋内部サイクルで段階的同調。
* キーボード配列依存：スキャンコードマップを外出し設定化。
* PROG互換性：jr100emulibの仕様差に注意（複数セクション等）。([asamomiji.jp][1])

## 11. Javaコンポーネント対応表（T1調査結果）

| カテゴリ | Java主要クラス | 役割・相互作用 | Python側対応案 |
| --- | --- | --- | --- |
| CPU | `emulator.CPU`, `emulator.device.MB8861` | MB8861（6800系）命令セット、割り込み、クロック計数を管理。`Computer`から`execute`を呼び出され、`MemorySystem`経由でメモリ/I/Oへアクセス。 | `pyjr100/cpu/core.py`, `pyjr100/cpu/decoder.py`, `pyjr100/cpu/flags.py` |
| バス/メモリ | `emulator.MemorySystem`, `emulator.Memory`, `emulator.RAM`, `emulator.ROM`, `emulator.UnmappedMemory`, `jr100.MainRam`, `jr100.VideoRam`, `jr100.UserDefinedCharacterRam`, `jr100.ExtendedIOPort` | 16bit空間に各デバイスをマッピング。`JR100`コンストラクタで領域割当と`JR100R6522`を登録。VRAM/UCHRは`JR100Display`へ通知。 | `pyjr100/bus/memory.py`, `pyjr100/bus/io_map.py`, `pyjr100/bus/memory_map.py` |
| I/Oコントローラ | `emulator.device.R6522`, `jr100.JR100R6522` | VIAのレジスタ挙動を実装し、ポートBでキーマトリクスとフォント切替、タイマでビープ周波数指示。 | `pyjr100/bus/via6522.py`, `pyjr100/io/matrix_adapter.py`, `pyjr100/audio/tone_generator.py` |
| 表示 | `emulator.AbstractDisplay`, `jr100.JR100Display`, `jr100.VideoRam`, `jr100.UserDefinedCharacterRam` | 32×24文字、8×8ピクセルフォント描画。AWT `BufferedImage`でフォントビットマップを保持し、VRAM更新で`updateFont`を呼んで差分描画。 | `pyjr100/video/display.py`, `pyjr100/video/renderer.py`, `pyjr100/video/font.py` |
| 入力 | `emulator.AbstractKeyboard`, `jr100.JR100Keyboard`, `emulator.EventQueue`, `jr100.JR100R6522` | Swingイベント→キーマトリクス配列へ反映。VIAがスキャンラインを取得してポートBへ書き戻す。イベントキュー経由で状態変化を管理。 | `pyjr100/io/keyboard.py`, `pyjr100/ui/events.py`, `pyjr100/bus/via6522.py` |
| 音 | `emulator.AbstractSoundProcessor`, `emulator.device.Beep`, `jr100.JR100R6522` | VIAタイマ1の周波数計算で`Beep`に矩形波出力指示。ラインON/OFF制御がビープ持続を決定。 | `pyjr100/audio/beeper.py`, `pyjr100/audio/mixer.py` |
| ファイル/ローダ | `emulator.file.ProgFormatFile`, `emulator.file.BasicTextFormatFile`, `emulator.file.BinaryTextFormatFile`, `emulator.Program` | PROGフォーマット解析、BASIC/バイナリセクションを`Program`へ格納し、`MemorySystem`へパッチ適用。入出力はリトルエンディアン。 | `pyjr100/loader/prog.py`, `pyjr100/loader/basic_text.py`, `pyjr100/loader/program.py` |
| アプリ/UI | `emulator.Application`, `jr100.JR100Application`, `jr100.JR100Display`, `jr100.FileOpenHooker` ほか | SwingベースのGUI、メニューやファイル操作、スナップショット、設定ダイアログ。Pygame版ではメインループ・CLI中心に再設計予定。 | `pyjr100/ui/app.py`, `pyjr100/ui/menu.py` (必要に応じて), `run.py` |
| スケジューラ/システム | `emulator.Computer`, `emulator.TimeManager`, `emulator.EventQueue`, `emulator.AbstractHardware`, `emulator.Device` | CPUクロック管理、イベントディスパッチ、デバイス一覧・実行、サスペンド/レジューム処理。 | `pyjr100/utils/scheduler.py`, `pyjr100/utils/events.py`, `pyjr100/utils/hardware.py` |

補足:

* `Computer`は実行ループとイベント処理の中心であり、Python版でもループ制御・タイマの責務を切り出す必要がある。
* `JR100`コンストラクタが全デバイス結線のハブ。Python版では`pyjr100/system/machine.py`（名称検討）に相当する構築関数を用意し、Pygame初期化と分離する。
* ファイルI/Oは`Program`クラスが`AddressRegion`を用いてターゲットアドレスへ書き戻す設計。Python版は`dataclass`でメタデータとセクションを保持し、テストで丸ごと検証可能にする。

未解決・追加調査ポイント:

1. CPU: `MB8861`の命令実装は長大な`switch`構造。Pythonではテーブル駆動化を検討しつつ、サイクル数・フラグ計算の正確な抽出が必要（`execute()`内のタイミング処理を精読）。
2. メモリ/デバイス: `ExtendedIOPort`、`UserDefinedCharacterRam`の詳細動作とROMバンク切替有無を確認。Python側のメモリアロケーションAPIで事前定義を行う。
3. 表示: `JR100Display`の`updateFont`や`paintComponent`で行っている差分レンダリング・カラー適用ロジックをPygameへ移植する際の最適化方針を検討。フォントのビット列は`resources`配下CSVを解析。
4. 入力: `JR100Keyboard`のJIS配列対応と`FileOpenHooker`のショートカット処理などがPygameのイベントモデルにどう影響するか要検討。リピート・同時押し仕様を整理。
5. サウンド: `Beep`クラスがJava Sound APIで矩形波を生成している。Pythonでは`pygame.mixer`か`numpy`生成→`pygame.sndarray`のどちらを使うか選定し、タイマ精度をベンチマークする。
6. ローダ: `ProgFormatFile`で複数バイナリセクションを順番に適用する処理をpytestゴールデンテスト用にサンプル化する必要がある（テスト入力の作成方法を別途定義）。
7. システム: `TimeManager`/`EventQueue`のクロック同期アルゴリズムを簡略化するかそのまま移植するか検討。Pygameの`Clock`との二重管理を避ける設計方針を立てる。

---

## 付録A：初期実装コマンド（例）

```bash
# 仮の手順例
python -m venv .venv && . .venv/bin/activate
pip install pygame pytest
mkdir -p pyjr100/{cpu,bus,video,audio,io,rom,loader,ui,utils} tests
touch run.py
```

## 付録B：最小`run.py`仕様（要件）

* 画面生成（例：本体画面を整数スケール表示）。
* エミュ初期化（ROMロード、VRAM初期化）。
* メインループ（イベント→入力→CPUステップ→VRAM→描画）。
* `--rom`引数、`--scale`引数。

---

### 出典

* `zabaglione/jr100-emulator-v2` のREADMEおよび配布構成（Java, JInput, jar）を確認。([GitHub][2])
* 「計算機室」JR-100エミュレータの総合ページ／v2案内、およびPython系ツール・`jr100emulib`への言及。([asamomiji.jp][1])

---

自信の度合い：中〜高（0.7）。
根拠：元リポジトリの構成・READMEと関連エコシステムの一次情報に基づき、実装方針とCodex運用手順を具体化。ただし、Java側の個別クラス構造（`src/jp/asamomiji/**`）の詳細閲覧に一部制約があったため、CPU/VRAM仕様の細目は実コード確認後に微調整が必要。

[1]: https://asamomiji.jp/contents/jr-100-emulator?utm_source=chatgpt.com "JR-100エミュレータ | 計算機室"
[2]: https://github.com/zabaglione/jr100-emulator-v2 "GitHub - zabaglione/jr100-emulator-v2: JR-100 Emulator version2"
