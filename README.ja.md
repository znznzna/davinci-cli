[English](README.md) | 日本語

# davinci-cli

[![CI](https://github.com/znznzna/davinci-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/znznzna/davinci-cli/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**DaVinci Resolve をコマンドラインから完全操作 — エージェントファースト設計、約90コマンド。**

プロジェクト管理、タイムライン操作、クリップ編集、カラーグレーディング、メディアプール、レンダリング、ギャラリー操作を CLI または AI エージェント経由で制御できます。`_impl` 関数パターンにより CLI (Click) と MCP (FastMCP) でロジックを共有しています。

## Features

- **エージェントファースト設計** — JSON 構造化 I/O、`--json` 入力、`--fields` フィルタ、`--dry-run` による破壊的操作の事前確認
- **約90の CLI コマンド** — 9つのコマンドグループ (system, project, timeline, clip, color, media, deliver, gallery, schema)
- **MCP サーバー** — 全コマンドをツールとして公開（変更系ツールはデフォルト `dry_run=True`）
- **スキーマファースト探索** — `dr schema list` / `dr schema show <command>` でランタイム JSON Schema を取得
- **出力形式自動判定** — パイプ/エージェント向け NDJSON、TTY 向け Rich テーブル
- **環境自動設定** — macOS / Windows で DaVinci Resolve API パスを自動検出
- **Pydantic v2 バリデーション** — パストラバーサル・インジェクション防御付き

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

### 接続確認

```bash
dr system ping
# -> pong

dr system info
# -> バージョン、エディション、現在のプロジェクト、現在のページ
```

### 基本ワークフロー

```bash
# プロジェクト一覧
dr project list --fields name

# プロジェクトを開く (まず dry-run)
dr project open "MyProject" --dry-run
dr project open "MyProject"

# タイムライン一覧
dr timeline list --fields name

# 現在のタイムラインのクリップ一覧
dr clip list --fields index,name

# LUT を適用 (まず dry-run)
dr color apply-lut 1 /path/to/lut.cube --dry-run
dr color apply-lut 1 /path/to/lut.cube
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| `dr system` | 6 | 接続確認、バージョン/エディション情報、ページ・キーフレームモード制御 |
| `dr project` | 9 | 一覧、開く、閉じる、作成、削除、保存、リネーム、情報、設定 |
| `dr timeline` | 15+ | 一覧、切替、作成、削除、エクスポート、マーカー、タイムコード、トラック、複製、シーンカット、字幕 |
| `dr clip` | 9+ | 一覧、情報、選択、プロパティ、有効/無効、カラーラベル、フラグ |
| `dr color` | 14+ | LUT 適用、グレードリセット/コピー、カラーバージョン、ノード LUT、CDL、LUT エクスポート、スチル |
| `dr media` | 13+ | インポート、一覧、移動、削除、リリンク、メタデータ、文字起こし、フォルダ |
| `dr deliver` | 14+ | レンダープリセット、ジョブ、開始/停止、ステータス、フォーマット/コーデック、プリセット読込/書出 |
| `dr gallery` | 9 | ギャラリーアルバム (一覧/現在/設定/作成)、スチル (一覧/グラブ/エクスポート/インポート/削除) |
| `dr schema` | 2 | コマンド探索: 全コマンド一覧、JSON Schema 表示 |

### 使用例

```bash
# システム情報
dr system info

# プロジェクト管理
dr project list --fields name
dr project create "NewProject" --dry-run
dr project save

# タイムライン操作
dr timeline current --fields name,fps
dr timeline marker list
dr timeline timecode get

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

### グローバルオプション

```bash
dr --pretty ...       # Rich フォーマット出力 (TTY のみ)
dr --fields f1,f2 ... # 出力フィールドのフィルタ
dr --json '{...}' ... # JSON 構造化入力
dr --dry-run ...      # 破壊的操作のプレビュー
```

## MCP Server

MCP サーバーの起動:

```bash
dr-mcp
```

CLI との主な違い:

- 変更系ツールはデフォルト `dry_run=True`（CLI のデフォルトは `False`）
- ツール説明にメタデータタグ付き: `[risk_level]`, `[mutating]`, `[supports_dry_run]`
- エージェント向けオンボーディング命令を内蔵

Claude Desktop / Cowork で使用する場合は、MCP 設定にサーバーを追加してください。

## Claude Code Skill

Claude Code プラグインとしてインストールすると、エージェントが DaVinci Resolve を操作できます:

```bash
/plugin marketplace add znznzna/davinci-cli
/plugin install davinci-cli@davinci-cli
```

エージェントは `SKILL.md` を読んで利用可能なコマンド、パラメータ、ワークフローを自動的に把握します。

## Architecture

```
src/davinci_cli/
├── cli.py                 # Click エントリポイント (@click.group "dr")
├── schema_registry.py     # コマンド → Pydantic Schema マッピング
├── core/                  # 接続・環境・バリデーション・例外
├── output/formatter.py    # NDJSON / JSON / Rich 自動判定
├── commands/              # system, project, timeline, clip, color, media, deliver, gallery, schema
└── mcp/mcp_server.py      # FastMCP サーバー (約90ツール、_impl 関数を再利用)
```

全コマンドは `_impl()` 純粋関数として実装されています。CLI (Click) と MCP (FastMCP) の両方がこの関数を呼び出すことで、ロジックの重複を防いでいます。

## Known Limitations

- **DaVinci Resolve API に Undo はありません** — 全書き込み操作は不可逆です。必ず `--dry-run` を使い、グレーディング前にカラーバージョンを作成してください。
- **ExportStills API バグ** — DaVinci Resolve 20.x の `ExportStills()` は実際の成否に関わらず常に `False` を返します。
- **ビートマーカー** — 整数フレーム丸めにより +/-0.5 フレーム (+/-21ms @24fps) のタイミングオフセットが発生します。
- **MediaStorage / Fusion 非対応** — メディア操作は MediaPool API のみ使用します。
- **Studio 限定機能** — 一部の操作は DaVinci Resolve Studio (有料版) が必要です。`dr system edition` で確認してください。

## Development

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

## Environment Variables

| 変数 | 説明 |
|------|------|
| `RESOLVE_SCRIPT_API` | DaVinci Resolve スクリプティング API のパス |
| `RESOLVE_SCRIPT_LIB` | DaVinci Resolve 共有ライブラリのパス |
| `RESOLVE_MODULES` | DaVinci Resolve Python モジュールのパス |

macOS / Windows では未設定時に自動検出されます。

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
