# JR-100 Emulator version 2
松下電子工業が1981年に発売した8ビットマイコンJR-100のエミュレータのバージョン2です。

## Python移植（WIP）

このリポジトリには、Java版に加えてPython + Pygameによる移植版（開発中）が含まれます。Python版を試す場合は次の要件を満たしてください。

* Python 3.11 以上
* `pip install -r requirements-dev.txt` で依存関係（pygame等）を導入
* JR-100 実機から吸い出した BASIC ROM（生バイナリ or PROG形式）を用意

### 起動方法（Python版）

```
python run.py --rom /path/to/jr100rom.prg
```

`--rom` オプションは必須です。JR-100 BASIC ROMの生バイナリ（例: `jr100rom.bin`）か、従来通りのPROG形式（例: `jr100rom.prg`）のどちらでも指定できます。ROMファイルを指定しない、あるいはパスが存在しない場合はアプリケーションがエラーメッセージを表示して終了します。

追加で BASIC プログラムを PROG 形式でロードしたい場合は、次のように `--program` を併用してください。

```
python run.py --rom /path/to/jr100rom.prg --program /path/to/sample.prog
```

#### サウンド出力

Python版はVIAタイマ1からのビープを`pygame.mixer`経由で再生します。実行環境にオーディオデバイスがない、あるいはミキサ初期化が失敗した場合は自動的に無音モードへフォールバックします。動作確認やトラブルシュートを行う際は環境変数`JR100_DEBUG=audio`を指定すると、ミキサ初期化やビープのオン/オフをログで確認できます。

Java版の手順は以下を参照してください。

# 前提条件

* Java SE 12以上のJava実行環境
* JR-100実機

# インストール

## 1. エミュレータの最新版ZIPファイルをダウンロードする。

[Releases](https://github.com/kemusiro/jr100-emulator-v2/releases)から最新版のZIPファイルをダウンロードします。ファイル名は`jr100v2-2.x.x.zip`という形式です。

## 2. zipファイルを解凍する。

適当なフォルダ内にダウンロードしたzipファイルを解凍します。

## 3. JR-100 BASIC ROMのデータを用意する。

JR-100実機からBASIC ROMデータを読み出して、JR-100エミュレータ用のPROG形式のファイルに格納します。読み出しには[JR-100 Emulator Library](https://github.com/kemusiro/jr100emulib)のfskloaderコマンドを使うのが便利です。コマンドの詳細は[FSK Loaderのマニュアル](https://github.com/kemusiro/jr100emulib/blob/master/fskloader.md)を参照してください。ここではBASIC ROMの読み出し方を抜粋します。

### 取り込み環境の作成
JR-100とオーディオキャプチャデバイスを接続します。キャプチャ条件は以下を推奨します。

* サンプリング周波数: 22050Hz
* サンプリング ビット数: 16bit
* チャンネル数: 1 (モノラル)

### JR-100 Emulator Libraryのインストール

JR-100 Emulator LibraryはPython 3.7以上の実行環境が必要です。あらかじめPC上にPython環境を構築してから、pipでパッケージをインストールします。これによりPythonパッケージと音声データ取り込み用のコマンド`fskloader`がPC上にインストールされます。

```shell
$ pip install jr100emulib
```

###  JR-1oo上でBASIC ROM領域をセーブ

PCでキャプチャ開始してから、JR-100上でBASIC ROM領域($E000〜$FFFF)全てをマシン語データとしてセーブするコマンドを実行します。MSAVEで指定するプログラム名(この例では`JR100ROM`)は任意の文字列で構いません。

```basic
MSAVE "JR100ROM", $E000, $FFFF
```

セーブが完了したらキャプチャを停止し、音声データを以下の内容でファイルに保存します。現時点でFSK LoaderはMP3には未対応です。

* ファイル名: jr100rom.wav (任意で良いです)
* ファイル形式: WAV形式 (必須)

### WAVファイルから取り込み

`fskloader`コマンドに先ほど保存したWAVファイルを指定し、`jr100rom.prg`というファイル名でPROG形式のファイルに保存してください。

```shell
$ fskloader jr100rom.wav -o jr100rom.prg
```

## 4. JR-100のBASIC ROMファイルをコピー

あらかじめ用意しておいたJR-100のBASIC ROMファイルを`jr100rom.prg`というファイル名で、ZIPファイルを解凍したフォルダ直下に格納します。

~~~
jr100v2 -+- external -+- jinput.jar         # ゲームパッド用ライブラリ
         |            +- README-jinput.md   # jinputのREADME
         |            +- nativelib -+- jinput-dx8.dll    # ゲームパッド用ライブラリ(ネイティブ)
         |                          +- jinput-dx3_64.dll
         |                          +- jinput-raw_64.dll
         |                          +- libjinput-linux.so
         |                          +- libjinput-linux64.so
         |                          +- libjinput-osx.jnilib
         +- jr100v2.jar   # エミュレータ本体
         +- jr100v2.sh    # エミュレータ起動用シェルスクリプト(macOS, Linux)
         +- jr100v2.vbs   # エミュレータ起動用シェルスクリプト(Windows)
         +- jr100rom.prg  # JR-100 BASIC ROMデータ
         +- manual.jar    # エミュレータ画面から呼び出すマニュアル
~~~

# 実行方法

`jar100v2.jar`を実行してください。

```
$ java -Djava.library.path=./external/nativelib -jar jr100v2.jar
```

なおOS毎に同梱のシェルスクリプトを実行するのが便利です。

* `jr100v2.vbs` (Windows)
* `jr100v2.sh` (macOS, Linux)

# アンインストール

解凍したフォルダを丸ごと削除してください。このフォルダ以外の場所にファイルを作成することはありません。

# ライセンス
## JR-100 Emulator

JR-100 Emulator version 2 is licensed under the MIT License.  See the [LICENSE](LICENSE) file for details.

JR-100 Emulator version 2はMITライセンスの元にライセンスされています。詳細は[LICENSE](/LICENSE)を参照してください。

## JInput
Licensed under [BSD License](https://opensource.org/licenses/BSD-3-Clause), copyright is attributed in each source file committed.

ゲームパッドからの入力を処理するためにJInputのJARファイル及びDLLファイルを取り込んでいます。
