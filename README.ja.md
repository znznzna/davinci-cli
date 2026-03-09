[English](README.md)

# davinci-cli

[![CI](https://github.com/znznzna/davinci-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/znznzna/davinci-cli/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**DaVinci Resolve をコマンドラインから完全操作 — エージェントファースト設計、約90コマンド。**

プロジェクト管理、タイムライン操作、クリップ編集、カラーグレーディング、メディアプール、レンダリング、ギャラリー操作を CLI または AI エージェント経由で制御できます。`_impl` 関数パターンにより CLI (Click) と MCP (FastMCP) でロジックを共有しています。

## Architecture

```
+---------------------+     Python Scripting API      +--------------+
|  DaVinci Resolve    |<----------------------------->|  Python SDK  |
|  (Free / Studio)    |   Direct API connection       |              |
+---------------------+                               +------+-------+
                                                              |
                                                   +----------+----------+
                                                   |                     |
                                            +------+-------+     +------+------+
                                            |   CLI (dr)   |     | MCP Server  |
                                            |   Click app  |     | (dr-mcp)    |
                                            +--------------+     +-------------+
```

CLI と MCP サーバーは DaVinci Resolve の Python スクリプティング API に直接接続します。プラグインのインストールは不要です — DaVinci Resolve が起動していれば OK です。

## Quick Start

### Prerequisites

- **Python 3.10+**
- **DaVinci Resolve** (Free または Studio、起動済みであること)
- macOS / Windows

### Installation

```bash
pip install davinci-cli
```

DaVinci Resolve がインストール・起動済みである必要があります。CLI はスクリプティング API に直接接続するため、プラグインのインストールは不要です。

### Upgrading

```bash
pip install --upgrade davinci-cli
```

### 利用方法を選択

#### Option A: Claude Code（SKILL ベース）

**Claude Code** ユーザー向け — Claude Code Plugin をインストールすると、エージェントが SKILL ファイルを通じて全約90コマンドを発見・利用できます：

```bash
/plugin marketplace add znznzna/davinci-cli
/plugin install davinci-cli@davinci-cli
```

エージェントは `SKILL.md` を読んで利用可能なコマンド、パラメータ、ワークフローを把握します。手動でコマンドを打つ必要はありません。

#### Option B: Claude Desktop / Cowork（MCP Server）

**Claude Desktop** または **Cowork** ユーザー向け — MCP サーバーを登録してください：

```bash
dr mcp install
```

Claude Desktop / Cowork を再起動してください。全約90コマンドが snake_case 命名の MCP ツールとして利用可能です（例: `project_open`, `clip_list`）。

MCP のステータス確認：

```bash
dr mcp status
dr mcp test       # DaVinci Resolve への接続テスト
```

CLI との主な違い：

- 変更系ツールはデフォルト `dry_run=True`（CLI のデフォルトは `False`）
- ツール説明にメタデータタグ付き: `[risk_level]`, `[mutating]`, `[supports_dry_run]`
- エージェント向けオンボーディング命令を内蔵

#### Option C: 直接 CLI / スクリプト

`dr` コマンドを直接使ってシェルスクリプトや自動化に活用できます：

```bash
dr system ping
dr project list --fields name
dr color apply-lut 1 /path/to/lut.cube --dry-run
```

### 接続確認

1. DaVinci Resolve を起動
2. 以下のコマンドを実行：

```bash
dr system ping
# -> pong

dr system info
# -> バージョン、エディション、現在のプロジェクト、現在のページ
```

## Usage Examples

```bash
# プロジェクト一覧
dr project list --fields name

# プロジェクトを開く (まず dry-run)
dr project open "MyProject" --dry-run
dr project open "MyProject"

# タイムラインとクリップの一覧
dr timeline list --fields name
dr clip list --fields index,name

# カラーグレーディング (必ずバージョンを先に作成 — Undo 機能はありません)
dr color version add 1 "before-edit"
dr color apply-lut 1 /path/to/lut.cube
dr color copy-grade --from 1 --to 2

# メディアプール
dr media list --fields clip_name,file_path
dr media folder create "B-Roll"
dr media import /path/to/file.mov

# レンダリング
dr deliver preset list
dr deliver preset load "YouTube 1080p"
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}'
dr deliver start

# スキーマ探索 (エージェント向け)
dr schema list
dr schema show project.open
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| [`dr system`](#dr-system) | 6 | 接続確認、バージョン/エディション情報、ページ・キーフレームモード制御 |
| [`dr project`](#dr-project) | 9 | 一覧、開く、閉じる、作成、削除、保存、リネーム、情報、設定 |
| [`dr timeline`](#dr-timeline) | 15+ | 一覧、切替、作成、削除、エクスポート、マーカー、タイムコード、トラック、複製、シーンカット、字幕 |
| [`dr clip`](#dr-clip) | 9+ | 一覧、情報、選択、プロパティ、有効/無効、カラーラベル、フラグ |
| [`dr color`](#dr-color) | 14+ | LUT 適用、グレードリセット/コピー、カラーバージョン、ノード LUT、CDL、LUT エクスポート、スチル |
| [`dr media`](#dr-media) | 13+ | インポート、一覧、移動、削除、リリンク、メタデータ、文字起こし、フォルダ |
| [`dr deliver`](#dr-deliver) | 14+ | レンダープリセット、ジョブ、開始/停止、ステータス、フォーマット/コーデック、プリセット読込/書出 |
| [`dr gallery`](#dr-gallery) | 9 | ギャラリーアルバム (一覧/現在/設定/作成)、スチル (一覧/グラブ/エクスポート/インポート/削除) |
| [`dr schema`](#dr-schema) | 2 | コマンド探索: 全コマンド一覧、JSON Schema 表示 |

### dr system

```bash
dr system ping                # 接続テスト
dr system version             # API バージョン
dr system edition             # Free or Studio
dr system info                # 全システム情報
dr system page get            # 現在のページ (Edit, Color 等)
dr system keyframe-mode get   # キーフレームモード
```

### dr project

```bash
dr project list --fields name       # プロジェクト一覧
dr project open "Name" --dry-run    # 開く (プレビュー)
dr project open "Name"              # プロジェクトを開く
dr project close                    # プロジェクトを閉じる
dr project create "Name" --dry-run  # 作成 (プレビュー)
dr project save                     # 保存
dr project info                     # プロジェクト詳細
dr project settings                 # プロジェクト設定
dr project rename "NewName"         # リネーム
```

### dr timeline

```bash
dr timeline list --fields name      # タイムライン一覧
dr timeline current                 # 現在のタイムライン情報
dr timeline switch "Name"           # タイムライン切替
dr timeline create "Name"           # タイムライン作成
dr timeline delete "Name" --dry-run # 削除 (プレビュー)
dr timeline marker list             # マーカー一覧
dr timeline marker add --frame 100 --name "Note" --color Blue
dr timeline timecode get            # タイムコード取得
dr timeline track list              # トラック一覧
dr timeline duplicate               # タイムライン複製
```

### dr clip

```bash
dr clip list --fields index,name    # クリップ一覧
dr clip info 1                      # クリップ詳細
dr clip select 1                    # クリップ選択
dr clip property get 1 "Pan"        # プロパティ取得
dr clip enable 1 --toggle           # 有効/無効トグル
dr clip color set 1 Orange          # カラーラベル設定
dr clip flag add 1 --flag-color Blue
```

### dr color

```bash
dr color apply-lut 1 /path/to/lut.cube --dry-run
dr color reset 1                    # グレードリセット
dr color copy-grade --from 1 --to 2 # グレードコピー
dr color version list 1             # バージョン一覧
dr color version add 1 "checkpoint" # バージョン保存
dr color version load 1 "checkpoint"
dr color node list 1                # ノード一覧
dr color cdl set 1 --slope 1.1,1.0,0.9
dr color still grab 1               # スチルグラブ
```

### dr media

```bash
dr media list --fields clip_name,file_path
dr media import /path/to/file.mov
dr media folder create "B-Roll"
dr media folder list
dr media move --clip-names "file.mov" --target-folder "B-Roll"
dr media metadata get <clip> "Clip Name"
dr media transcribe <clip>
```

### dr deliver

```bash
dr deliver preset list              # プリセット一覧
dr deliver preset load "YouTube 1080p"
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}'
dr deliver start --dry-run          # レンダー (プレビュー)
dr deliver start                    # レンダー開始
dr deliver status                   # 進捗確認
dr deliver stop                     # レンダー停止
dr deliver format list              # 利用可能なフォーマット
dr deliver codec list "mp4"         # フォーマットのコーデック
```

### dr gallery

```bash
dr gallery album list               # アルバム一覧
dr gallery album current            # 現在のアルバム
dr gallery album set "Stills"       # アルバム設定
dr gallery album create "New Album"
dr gallery still list               # スチル一覧
dr gallery still export --folder-path /output --format png
```

### dr schema

```bash
dr schema list                      # 全コマンド一覧
dr schema show project.open         # コマンドの JSON Schema
```

## Global Options

```bash
dr --pretty ...       # Rich フォーマット出力 (TTY のみ)
dr --fields f1,f2 ... # 出力フィールドのフィルタ
dr --json '{...}' ... # JSON 構造化入力
dr --dry-run ...      # 破壊的操作のプレビュー
```

## Configuration

| 環境変数 | 説明 |
|---------|------|
| `RESOLVE_SCRIPT_API` | DaVinci Resolve スクリプティング API のパス |
| `RESOLVE_SCRIPT_LIB` | DaVinci Resolve 共有ライブラリのパス |
| `RESOLVE_MODULES` | DaVinci Resolve Python モジュールのパス |

macOS / Windows では未設定時に自動検出されます。

## Features

- **エージェントファースト設計** — JSON 構造化 I/O、`--json` 入力、`--fields` フィルタ、`--dry-run` による破壊的操作の事前確認
- **スキーマファースト探索** — `dr schema list` / `dr schema show <command>` でランタイム JSON Schema を取得
- **出力形式自動判定** — パイプ/エージェント向け NDJSON、TTY 向け Rich テーブル
- **環境自動設定** — macOS / Windows で DaVinci Resolve API パスを自動検出
- **Pydantic v2 バリデーション** — パストラバーサル・インジェクション防御付き
- **MCP Server** — Claude Desktop および Cowork とのネイティブ連携

## Known Limitations

- **DaVinci Resolve API に Undo はありません** — 全書き込み操作は不可逆です。必ず `--dry-run` を使い、グレーディング前にカラーバージョンを作成してください。
- **ExportStills API バグ** — DaVinci Resolve 20.x の `ExportStills()` は実際の成否に関わらず常に `False` を返します。
- **ビートマーカー** — 整数フレーム丸めにより +/-0.5 フレーム (+/-21ms @24fps) のタイミングオフセットが発生します。
- **MediaStorage / Fusion 非対応** — メディア操作は MediaPool API のみ使用します。
- **Studio 限定機能** — 一部の操作は DaVinci Resolve Studio (有料版) が必要です。`dr system edition` で確認してください。

## Development

### コントリビューター向け

> **一般ユーザーはこのセクションをスキップしてください。** `pip install davinci-cli` だけで利用できます。

```bash
git clone https://github.com/znznzna/davinci-cli.git
cd davinci-cli
pip install -e ".[dev]"
```

```bash
# テスト実行
python -m pytest tests/unit/ -v

# カバレッジ付き
python -m pytest tests/unit/ -v --cov=davinci_cli

# Lint
ruff check src/ tests/

# 型チェック
mypy src/
```

## Project Structure

```
davinci-cli/
├── src/davinci_cli/           # メインパッケージ
│   ├── cli.py                 # Click エントリポイント (dr コマンド)
│   ├── schema_registry.py     # コマンド → Pydantic Schema マッピング
│   ├── decorators.py          # 共有デコレータ
│   ├── core/                  # 接続・環境・バリデーション・例外
│   │   ├── connection.py      # lru_cache Resolve API 接続
│   │   ├── environment.py     # macOS/Windows 自動検出
│   │   ├── validation.py      # パストラバーサル / インジェクション防御
│   │   ├── exceptions.py      # DavinciCLIError 階層 (exit codes)
│   │   └── edition.py         # Free/Studio 判定
│   ├── output/
│   │   └── formatter.py       # NDJSON / JSON / Rich 自動判定
│   ├── commands/              # コマンドグループ
│   │   ├── system.py          # dr system
│   │   ├── project.py         # dr project
│   │   ├── timeline.py        # dr timeline
│   │   ├── clip.py            # dr clip
│   │   ├── color.py           # dr color
│   │   ├── media.py           # dr media
│   │   ├── deliver.py         # dr deliver
│   │   ├── gallery.py         # dr gallery
│   │   └── schema.py          # dr schema
│   └── mcp/
│       ├── mcp_server.py      # FastMCP サーバー (約90ツール、_impl 再利用)
│       └── instructions.py    # エージェントオンボーディング命令
├── tests/                     # pytest テストスイート
├── plugin/                    # Claude Code Plugin
│   └── skills/davinci-cli/
│       └── SKILL.md           # エージェントスキルファイル
└── scripts/                   # バージョン同期ユーティリティ
```

## Requirements

- Python >= 3.10
- DaVinci Resolve (Free または Studio)
- macOS / Windows

### Python Dependencies

- [click](https://click.palletsprojects.com/) >= 8.1 — CLI フレームワーク
- [rich](https://rich.readthedocs.io/) >= 13.0 — テーブル出力
- [pydantic](https://docs.pydantic.dev/) >= 2.0 — データバリデーション
- [fastmcp](https://github.com/jlowin/fastmcp) >= 0.1 — MCP サーバーフレームワーク

## License

[MIT](LICENSE)
