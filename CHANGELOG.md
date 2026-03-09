# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2026-03-09

### Added
- `dr mcp install/uninstall/status/test` — Claude Desktop / Cowork 設定ファイルへの MCP サーバー自動登録 (lightroom-cli と UX 統一)
- Claude Code Marketplace 対応 (`marketplace.json`, `plugin.json`)
- バージョン同期スクリプトが Marketplace JSON もカバー

### Fixed
- Linux の Claude config パスのケーシング修正 (`claude` → `Claude`)
- `test_dr_version` のバージョンハードコード除去

### Changed
- README を lightroom-cli 構成に合わせて全面改訂 (Architecture 図、Option A/B/C、Project Structure 等)
- 内部ドキュメント (`docs/plans/`) をリポジトリから除外

## [1.0.0] - 2026-03-09

Initial public release — CLI and MCP server wrapping the DaVinci Resolve Python API with an agent-first design.

### Highlights
- **CLI tool (`dr`)** with 9 command groups covering ~90 operations
- **MCP Server** with ~90 tools for AI agent integration (FastMCP)
- **Agent-first design** — `--json` input, `--fields` filtering, `--dry-run` preview, `dr schema` for runtime discovery
- **Environment auto-detection** for macOS and Windows (Linux not yet supported)
- **536+ tests** (unit + E2E smoke tests)

### Added

#### Command Groups
- **system** — `ping`, `version`, `edition`, `info`, `page get/set`, `keyframe-mode get/set`
- **project** — `list`, `open`, `close`, `create`, `delete`, `save`, `info`, `settings`, `rename`
- **timeline** — `list`, `current`, `switch`, `create`, `delete`, `export`, `marker list/add/delete`, `timecode get/set`, `current-item`, `track list/add/delete/enable/lock`, `duplicate`, `detect-scene-cuts`, `create-subtitles`
- **clip** — `list`, `info`, `select`, `property get/set`, `enable`, `color get/set/clear`, `flag add/list/clear`
- **color** — `apply-lut`, `reset`, `reset-all`, `copy-grade`, `version list/current/add/load/delete/rename`, `node list/lut-set/lut-get/enable`, `cdl set`, `lut-export`, `still list/grab`
- **media** — `list`, `import`, `move`, `delete`, `relink`, `unlink`, `metadata get/set`, `export-metadata`, `transcribe`, `folder list/create/delete`
- **deliver** — `presets list/load`, `add-job`, `list-jobs`, `start`, `stop`, `status`, `delete-job`, `delete-all-jobs`, `job-status`, `is-rendering`, `format list`, `codec list`, `preset import/export`
- **gallery** — `album list/current/set/create`, `still list/grab/export/import/delete`
- **schema** — `show`, `list` for runtime JSON Schema discovery

#### Special Features
- **Beat markers** — `dr timeline marker beats` for BPM-based marker placement on clips

#### MCP Server
- **~90 MCP tools** — all `_impl` functions exposed via FastMCP for Claude Desktop / AI agent integration
- **Agent instruction guide** — built-in Getting Started, Safety Rules, Error Recovery, and Workflow documentation
- **English metadata tags** on all tool descriptions for better agent comprehension

#### Agent-First Design
- **`--json` input** — structured JSON input via Pydantic v2 models for all commands
- **`--fields` filter** — select specific output fields (`--fields name,fps`)
- **`--dry-run`** — preview destructive operations before execution
- **Schema registry** — `dr schema show <command>` returns JSON Schema for any command
- **Structured error output** — typed exceptions with consistent exit codes (1-5)
- **Output format auto-detection** — NDJSON when piped, JSON for dicts, Rich tables for TTY

#### Environment & Platform
- **macOS/Windows auto-detection** — `RESOLVE_SCRIPT_API`, `RESOLVE_SCRIPT_LIB`, `RESOLVE_MODULES` environment variables set automatically
- **Free/Studio edition detection** — `core/edition.py` identifies DaVinci Resolve edition

### Technical

#### Architecture
- **`_impl` pure function pattern** — all business logic in `<command>_impl()` functions, shared by both CLI (Click) and MCP (FastMCP) entry points
- **Environment-Injected Direct Call** — connects to DaVinci Resolve Python API via environment variables (no socket/HTTP bridge)
- **Click CLI framework** with `DavinciCLIGroup` for global error handling
- **Common decorators** — `@json_input_option`, `@fields_option`, `@dry_run_option` for consistent command interfaces
- **lru_cache connection** — Resolve API connection cached with `clear_resolve_cache()` for test isolation

#### Dependencies
- Python 3.10+, Click, FastMCP, Pydantic v2, Rich, pytest

#### Security
- **Path traversal protection** — segment-level `..` detection in `core/validation.py`
- **Input validation** — Pydantic v2 models with type coercion and constraint enforcement
- **Injection prevention** — null byte and suspicious pattern rejection
- **API return value checking** — all mutating Resolve API calls verify return values to prevent false success reports

#### Testing
- **536+ tests** — unit tests and E2E smoke tests
- **MockResolve** — full Resolve API mock in `tests/mocks/resolve_mock.py` for testing without DaVinci Resolve
- **E2E smoke tests** — all command groups exercised against MockResolve

#### CI/CD
- **GitHub Actions** — pytest + ruff + mypy (strict mode) on macOS and Windows matrix
- **Linting** — ruff with RUF002/RUF003 exclusions for Japanese strings
- **Type checking** — mypy in strict mode
