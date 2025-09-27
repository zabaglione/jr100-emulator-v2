# VIA (R6522) 全面移植計画

## ゴール
- Java 版 `R6522`/`JR100R6522` と同等の動作を Python 実装 (`pyjr100/bus/via6522.py`) で再現する。
- Z キー押下で STARFIRE が戦闘ルーチン (`0x0E45` 以降) に遷移できることを自動テストで保証する。
- 既存のフォント面切替・ユーザー定義文字 (UDC) 更新が退行しないことをベースラインテストで確認する。

## 作業ステップ
1. **Java 実装の精査**
   - `src/jp/asamomiji/emulator/device/R6522.java` と `src/jp/asamomiji/emulator/jr100/JR100R6522.java` を読み込み、各レジスタ更新・タイマ処理・割り込みハンドリングの流れを整理する。
   - 既存 Python 実装との差分（特に PB6/PB7 の結線、Timer2 のパルスカウント、CA1/CA2 ハンドシェイク）をドキュメント化する。

2. **Python 実装の全面置換**
   - `pyjr100/bus/via6522.py` をクラス単位で再設計し、Java 実装のステートマシンを忠実に移植する。
   - `Via6522` の public API（`load8`/`store8`/`tick`/`debug_snapshot` など）は変更せず、中身の挙動を合わせる。
   - UDC 関連 (`FontManager`, PB5 の CMODE 切替) が従来通り動作することを最優先で確認しながら実装する。

3. **ゲーム遷移テストの整備**
   - 既存の `tests/integration/test_starfire_title.py` を拡張し、Z キー押下後に PC が `0x0E45` 以降へ進むこと、かつ VRAM のタイトル行が変化することを検証する。
   - フォント更新・UDC に関する既存テスト (`tests/video/test_renderer.py` など) を併走して実行し、退行がないか確認する。

4. **最終確認**
   - `pytest` を全件実行。
   - `run.py --rom jr100rom.prg --program STARFIRE.prg` を手動で起動し、タイトル→本編遷移を目視確認する。

## 進捗メモ（2025-09-26）
- `newjr100/tests/test_via_timer_handshake.py` を追加し、Timer1 の PB7/PB6 連動と CA2 ハンドシェイク復帰を TDD でカバー。
- `Via6522.tick()` / `debug_snapshot()` を実装し、Timer1/Timer2・CA2 タイマ・IRQ 要求を Java 版のステートマシンに倣って移植。
- `pytest newjr100/tests` を実行し 7 件すべて緑化。基底テスト（初期 ORB、DDR、IFR）との後方互換性も維持済み。
- Timer2 パルスカウントと CB1/CB2 ハンドシェイクについて追加テスト（全10件）を整備し、`Via6522` を Java 実装準拠の挙動へ更新。IRQ 伝播やハンドシェイク線の状態を `debug_snapshot` から検証可能にした。
- CA1 割り込みとキーボードマトリクス更新を移植し、キー押下で PB 下位ビットがアクティブローになること、`LOAD IORA` で IFR がクリアされることをテストで保証。全12件の pytest が緑化。

## 留意点
- PB5 (CMODE1) と PB6/PB7 のハード結線を正しく再現しないとフォント表示と UDC 更新が壊れるため、`FontManager` の呼び出しフローも併せて確認する。
- Java 実装のコードコメントを参考に、パルスモード時は PB6 の立下りエッジでのみ Timer2 をデクリメントする点に注意する。
- `debug_snapshot` や `TraceRecorder` など既存のデバッグ API には手を入れない。
