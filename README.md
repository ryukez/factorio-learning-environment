# Factorio Learning Environment

[オリジナル版](https://github.com/JackHopkins/factorio-learning-environment) を独自にカスタマイズして扱いやすくしたリポジトリ

## Usage

1. Factorio サーバーの立ち上げ

```sh
cd extension && docker compose up
```

公開しているイメージを使ってすぐにサーバーを起動できます。
`cluster/docker` 以下で手元でイメージをビルドすることもできます。詳細は[オリジナル版](https://github.com/JackHopkins/factorio-learning-environment)を参照してください。

※ Factorio サーバーは、エージェントやゲームクライアントとは別のマシンで実行することもできます。その場合はサーバーのアドレスで指定している `localhost` をマシンの IP アドレスに変更してください。

2. ゲームクライアントからサーバーにログイン

ライセンスの認証のため、一度ゲームクライアントからのログインが必要です。
マルチプレイで `localhost:34197` を指定して接続します。
ログインできたら、ゲームの中の様子を観察できるようそのままにしておきます。

3. SQLite のセットアップ

エージェントの実行を記録するためのデータベースのセットアップが必要です。
[sqlite3](https://www.sqlite.org/download.html) をインストールし、extension のディレクトリで以下を実行します。

```sh
sqlite3 mydatabase.db < create_table.sql
```

4. 環境変数の設定
   `extension/.example.env` をコピーして.env ファイルを作成し、以下を設定します。

- 利用するプロバイダーの API キー。OpenRouter が便利です
- SQLITE_DB_FILE: 先ほど設定した DB ファイルのパス

5. 実行設定

最後に `extension/freeplay/configs/run_config.json` で実行の設定を行います。

```json
[
  {
    "task": "open_play.json", // そのままでOK
    "version": "20240330006", // 実行するエージェントのバージョンを自由に指定
    "model": "open-router-google/gemini-2.0-flash-001", // 利用するモデルのバージョン。OpenRouterの場合 `open-router-{model_name}`。それ以外はagents/utils/llm_factoryの実装を参照してください
    "runtime_version": "f923451" // 実行環境のバージョンとしてこのリポジトリのコミットハッシュを入れておく
  }
]
```

6. 実行

```sh
# ライブラリのインストール
uv venv && uv sync && .venv/bin/activate

cd extension && python trajectory_runner.py --run_config configs/run_config.json
```

イテレーションの開始ごとに指示を入力してください（例：発電所を建設する、鉄板の生産を自動化する、太陽光発電の研究を完了させる）。
入力するとイテレーションの実行が開始され、既定ステップを繰り返すとまた指示の待機待ちになります。

## オリジナル実装からの差分

- agent や 実行ログの保存について取り回しやすく実装し直した (extension/core)
- 全ての実行履歴をエージェントに渡す代わりに、イテレーションという単位を導入し、数十回の実行ごとに履歴がリセットされるようにした。（オリジナル版では recursive_formatter で実行履歴を圧縮している）
- 完全にフリーでプレイさせる代わりに、イテレーションごとに指示を与えられるようにした
- 毎回の実行ごとに最新のエンティティとインベントリ、研究の情報を与え、エージェントが最低限必要な情報を常に把握できるようにした。（オリジナル版ではエラー発生のたびに entities や inventory を返すようにしていたが、コンテキストが肥大化する原因になっていた）
- map を固定 (map.zip) し Docker イメージとして公開
- その他細かいバグやツールの挙動を修正（move_to でスタックを防ぐためにランダム性を入れる、lab が get_entities で取得できなくなるバグの修正、エラーメッセージの追加等）

## コード解説

### GameState

Factorio 内の設置されたエンティティ、プレイヤーのインベントリ、研究の進捗状況、エージェントがこれまでに書いたコードの名前空間など、現在のゲームの状態を表すほとんどの状態がこのクラスに集約され、シリアライズされて DB に保存されています。
この GameState を DB から読み込むことで、任意の状態からプレイを再開させることができます。
これを利用してエンティティやインベントリ・研究の情報をエージェントに与えています（core/definitions の ParsedGameState）

### agent / evaulator / trajectory_runner

trajector_runner がゲームのループを管理するクラスで、agent と evaluator を実行します。
基本的な流れは以下の通りです。

1. ゲームの初期化 (GameState の読み込み)
2. イテレーションごとに人間の指示を待ち受ける
3. 指示と GameState を与えて agent を実行
4. agent の出力したコードを evaluator が実行し、結果を評価。結果を DB に保存
5. 3 と 4 を数 step 繰り返す。
6. イテレーションを完了し、agent にイテレーションのサマリを出力させる。
7. 2 に戻り、次のイテレーションを開始する。

evaluator は agent の出力コードを実際に実行する他、一定時間スリープしてその間の各アイテムの生産量の評価も行います。
報酬設計の詳細は [元論文](https://arxiv.org/abs/2503.09617) を参照してください。

### フォルダ構成

extension の実行に必要な処理の大半は extension の中にまとまっています。
その他 GameState や FactorioInstance、Entity といったコアなクラスのみをオリジナル実装から参照しています。
offline_benchmark はオフラインのリプレイをもとにモデルの評価を行うためのパッケージです（開発中）。
