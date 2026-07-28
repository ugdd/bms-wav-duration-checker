# BMS 音源長さチェッカー

BMS/BME/BML譜面ファイル内のキー音定義(`#WAVxx`)を読み込み、各定義番号・音源ファイル名・音源ファイルの再生時間(長さ)を一覧表示するWindows向けツールです。
譜面制作時に、長すぎる音源を誤ってキー音に割り当てていないかを長さ順ソートで確認できます。

## 主な機能

- BMS/BME/BMLファイルの`#WAVxx`定義を解析し、定義番号・ファイル名・長さ・状態を一覧表示
- wav / ogg / mp3 / flac に対応(`#WAV`定義が`.wav`でも実体が`.ogg`等の場合は自動で解決)
- 各列ヘッダをクリックして昇順・降順ソート
- ダークモード/ライトモードの切り替え(設定は次回起動時も保持)
- パストラバーサル対策済み(譜面ファイル記載のパスがフォルダ外を指す場合は無視)

## 動作環境

- Windows 10 / 11
- ソースから実行する場合: Python 3.10 以降

## 使い方

どの方法でも、事前にPythonのインストールが必要です。

### 事前準備: Pythonのインストール

1. [Python公式サイト](https://www.python.org/downloads/)からWindows用インストーラーをダウンロードして実行
2. インストール画面の一番下にある **「Add python.exe to PATH」に必ずチェックを入れて**からインストールを進める

### 方法A: コマンド操作をしない(ZIPをダウンロードする)

コマンドやgitに慣れていない方向けの手順です。

1. このページ右上の緑色の **「Code」** ボタンをクリックし、**「Download ZIP」** を選択してダウンロード
2. ダウンロードしたZIPファイルを右クリックし、**「すべて展開」** を選んで好きな場所に展開(解凍)する
3. 展開してできたフォルダを開き、`build.bat` を**ダブルクリック**して実行する
   - 黒い画面(コマンドプロンプト)が開き、自動で必要なライブラリのインストールとexeの作成が進む
   - 「ビルド完了」と表示されたら何かキーを押すとウィンドウが閉じる
4. フォルダ内に新しくできた `dist` フォルダを開き、`BMSWavDurationChecker.exe` をダブルクリックして起動する

以降はこの`BMSWavDurationChecker.exe`を好きな場所に移動して使えます(再ビルドは不要です)。

### 方法B: gitでクローンしてビルドする

```bat
git clone https://github.com/ugdd/bms-wav-duration-checker.git
cd bms-wav-duration-checker
build.bat
```

`build.bat`が依存関係のインストールとPyInstallerによるexe化を行い、`dist\BMSWavDurationChecker.exe`が生成されます。生成されたexeはそのまま配布・起動できます。

### 方法C: ソースから直接実行する(exe化しない)

```bat
git clone https://github.com/ugdd/bms-wav-duration-checker.git
cd bms-wav-duration-checker
pip install -r requirements.txt
python main.py
```

### 操作方法

1. アプリを起動し、「参照...」からBMS/BME/BMLファイルを選択
2. 各キー音定義の長さが一覧表示される
3. 列ヘッダ(定義番号 / ファイル名 / 長さ / 状態)をクリックするとその列でソート、再クリックで昇順⇔降順を切り替え
4. 右上のボタンでダークモード/ライトモードを切り替え可能

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `main.py` | GUI本体(tkinter) |
| `bms_parser.py` | BMS/BME/BMLファイルから`#WAVxx`定義を抽出 |
| `audio_duration.py` | 音源ファイルの解決(拡張子フォールバック含む)と長さ取得 |
| `settings.py` | テーマ設定の保存・読込 |
| `build.bat` | 依存関係インストール+PyInstallerによるexe化 |

## セキュリティについて

- BMSファイル内に記載された音源ファイル名は、譜面ファイルが置かれたフォルダの外を参照できないよう検証しています(`../`や絶対パス、シンボリックリンク経由の参照も拒否)。
- 音源の長さ取得には外部プロセス(ffmpeg等)を呼び出さず、Pythonライブラリ([mutagen](https://github.com/quodlibet/mutagen))のみで解析しています。
- 巨大なファイルの誤読み込みを防ぐため、譜面ファイルのサイズには上限(20MB)を設けています。

## 備考

個人利用目的で作成されたツールです。
