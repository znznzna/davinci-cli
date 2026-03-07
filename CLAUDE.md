# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

davinci-cli は DaVinci Resolve Python API をラップする CLI / MCP サーバー。エージェントファースト設計で、AI エージェントが DaVinci Resolve を操作できることを主目的とする。

- **Tech Stack:** Python 3.10+, Click, FastMCP, Pydantic v2, Rich, pytest
- **Architecture:** Environment-Injected Direct Call — 環境変数で DaVinci Resolve Python API に直接接続
- **CLI コマンド名:** `dr`

## Build & Development

```bash
# セットアップ
pip install -e ".[dev]"

# テスト全実行
python -m pytest tests/unit/ -v

# 単一テスト実行
python -m pytest tests/unit/test_connection.py -v

# 特定テスト関数
python -m pytest tests/unit/test_connection.py::TestGetResolve::test_returns_resolve_object_when_running -v
```

## Architecture

### レイヤー構成

```
src/davinci_cli/
├── cli.py                 # Click エントリポイント (@click.group "dr")
├── schema_registry.py     # コマンド→Pydantic Schema マッピング
├── core/                  # 接続・環境・バリデーション・例外
│   ├── exceptions.py      # DavinciCLIError 階層 (exit_code付き)
│   ├── validation.py      # パストラバーサル・インジェクション拒絶
│   ├── environment.py     # macOS/Windows 環境変数自動設定
│   ├── connection.py      # lru_cache付き Resolve API 接続
│   └── edition.py         # Free/Studio 判定
├── output/
│   └── formatter.py       # NDJSON(pipe) / JSON(dict) / Rich(TTY) 自動判定
├── commands/              # サブコマンド群
│   ├── system.py          # ping/version/edition/info
│   ├── schema.py          # show/list (ランタイムスキーマ自己解決)
│   ├── project.py         # list/open/close/create/delete/save/info/settings
│   ├── timeline.py        # list/current/switch/create/delete/export/marker
│   ├── clip.py            # list/info/select/property
│   ├── color.py           # apply-lut/reset/copy-grade/paste-grade/node/still
│   ├── media.py           # import/list/info/move/delete
│   └── deliver.py         # presets/start/status/stop
└── mcp_server.py          # FastMCP サーバー (_impl関数を再利用)
```

### Key Design Patterns

- **`_impl` 純粋関数パターン:** 全コマンドは `<command>_impl()` 関数で実装。CLI (Click) と MCP (FastMCP) の両方がこの関数をラップして呼び出す。ビジネスロジックの重複を防ぐ。
- **`--json` 入力:** エージェント向けに `--json '{"name": "MyProject"}'` で Pydantic モデル経由の入力を受け付ける。
- **`--fields` フィルタ:** 出力フィールドを絞り込む (`--fields name,fps`)。
- **`--dry-run`:** 破壊的操作の事前確認。`{"dry_run": true, "action": "..."}` を返す。
- **出力形式自動判定:** 非TTY→NDJSON/JSON、TTY+`--pretty`→Rich 表示。
- **スキーマレジストリ:** 各コマンドファイル末尾で `register_schema()` を呼び、`dr schema show <command.path>` でエージェントが JSON Schema を取得可能。

### Exit Codes

| Code | Exception | 意味 |
|------|-----------|------|
| 1 | `ResolveNotRunningError` | DaVinci Resolve 未起動 |
| 2 | `ProjectNotOpenError` | プロジェクト未オープン |
| 3 | `ValidationError` | 入力バリデーション失敗 |
| 4 | `EnvironmentError` | 環境変数/パス設定エラー |
| 5 | `EditionError` | エディション不一致 (Studio必須機能) |

### テストでの Resolve モック

実際の DaVinci Resolve なしでテスト可能。`tests/mocks/resolve_mock.py` に `MockResolve`, `MockDaVinciResolveScript` 等を提供。`connection._import_resolve_script` をパッチして使用する。

### 環境変数

DaVinci Resolve Python API 接続に必要。未設定時は `core/environment.py` がプラットフォーム別デフォルトを自動設定：
- `RESOLVE_SCRIPT_API`
- `RESOLVE_SCRIPT_LIB`
- `RESOLVE_MODULES` (sys.path にも追加)

## Implementation Plans

このリポジトリには実装計画ドキュメントが含まれる：
- `2026-03-07-davinci-cli-phase1.md` — Phase 1: Core Layer (Task 1-8)
- `2026-03-07-davinci-cli-commands-a.md` — Phase 2: Commands (Task 9-14)
- `2026-03-07-davinci-cli-commands-b.md` — Phase 3: Color/Media/Deliver + MCP + E2E (Task 15-20)

実装時は `superpowers:executing-plans` skill で TDD サイクル（テスト先行→失敗確認→実装→通過確認→コミット）に従う。
