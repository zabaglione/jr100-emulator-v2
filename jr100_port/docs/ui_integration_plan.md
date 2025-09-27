# UI統合タスク計画と進捗メモ

## 現状サマリ
- `JR100App` は ROM/PRG のロードと `JR100Machine` 初期化までを担当。Pygame ループは未実装。
- 描画 (`JR100Display` → Pygame Surface)・音声 (`Beeper` → mixer)・入力 (キーボード/ゲームパッド) は最小 stub のまま。
- `run.py` から `--scale` / `--fullscreen` オプションを受け取れるが、画面生成処理が未定義のため未活用。

## 優先タスク
1. **Pygame ループ骨格実装**
   - メインループ、FPS 管理 (`pygame.time.Clock`) 、終了処理。
   - CPU ステップ→VIA tick→描画更新の順序を Java 版 `JR100Application` と揃える。
2. **描画パイプライン整備**
   - `JR100Display` にフォントデータ→Surface 生成までのAPIを実装。
   - `JR100App` 側で `Renderer` を呼び出し `screen.blit()` まで構築。
   - スケール倍率とフルスクリーン指定の反映。
3. **音声出力連携**
   - `Beeper` と `pygame.mixer` を接続し、VIA の PB7/Timer1 変化で波形更新。
   - ミュート時のフェイルセーフ (mixer 未使用環境向け例外処理)。
4. **入力デバイス実装**
   - キーボード: Pygame キーコード→JR-100 マトリクス conversion。押下/離上/リピート。
   - ゲームパッド: 軸・ボタン→マトリクス/拡張IO のマッピング定義。
5. **デバッグ/ログ機能**
   - トレース・fps オーバーレイ・簡易メニュー (リセット/PRG再読込) の要否を検討。

## 依存関係
- 描画/音声/入力はメインループ骨格に依存。
- フォント描画は `JR100Display` の差し替え (pyjr100/video) と連携が必要。
- 音声/入力は VIA のイベント処理を先に安定化させることが前提。

## 進捗メモ
- 2024-XX-XX: CLI から `JR100App` を呼び出し、ROM/PRG のロードと `JR100Machine` 初期化が可能になった。
- 次の作業は「Pygame ループ骨格実装」。完了後に描画ハンドリングへ着手予定。
