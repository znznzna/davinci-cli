# davinci-cli

[![CI](https://github.com/znznzna/davinci-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/znznzna/davinci-cli/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

English | [日本語](README.ja.md)

**Agent-first CLI and MCP server for DaVinci Resolve — ~90 commands.**

Control projects, timelines, clips, color grading, media pool, rendering, and gallery operations from the command line or through AI agents. Built with an `_impl` function pattern that shares logic between CLI (Click) and MCP (FastMCP).

## Features

- **Agent-first design** — structured JSON I/O, `--json` input, `--fields` filtering, `--dry-run` for all destructive operations
- **~90 CLI commands** across 9 command groups (system, project, timeline, clip, color, media, deliver, gallery, schema)
- **MCP server** with all commands exposed as tools (mutating tools default to `dry_run=True`)
- **Schema-first discovery** — `dr schema list` and `dr schema show <command>` for runtime JSON Schema
- **Auto-detected output** — NDJSON for pipes/agents, Rich tables for TTY
- **Environment auto-setup** — DaVinci Resolve API paths detected automatically on macOS and Windows
- **Pydantic v2 validation** with path traversal and injection protection

## Quick Start

### Prerequisites

- **Python 3.10+**
- **DaVinci Resolve** (Free or Studio, must be running)
- macOS / Windows

### Installation

```bash
pip install davinci-cli
```

DaVinci Resolve must be installed and running. The CLI connects to its scripting API directly — no plugin installation required.

### Verify Connection

```bash
dr system ping
# -> pong

dr system info
# -> version, edition, current project, current page
```

### Basic Workflow

```bash
# List projects
dr project list --fields name

# Open a project (dry-run first)
dr project open "MyProject" --dry-run
dr project open "MyProject"

# List timelines
dr timeline list --fields name

# List clips in current timeline
dr clip list --fields index,name

# Apply a LUT (dry-run first)
dr color apply-lut 1 /path/to/lut.cube --dry-run
dr color apply-lut 1 /path/to/lut.cube
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| `dr system` | 6 | Connection check, version/edition info, page and keyframe mode control |
| `dr project` | 9 | List, open, close, create, delete, save, rename, info, settings |
| `dr timeline` | 15+ | List, switch, create, delete, export, markers, timecode, tracks, duplicate, scene cuts, subtitles |
| `dr clip` | 9+ | List, info, select, properties, enable/disable, color labels, flags |
| `dr color` | 14+ | LUT apply, grade reset/copy, color versions, node LUT, CDL, LUT export, stills |
| `dr media` | 13+ | Import, list, move, delete, relink, metadata, transcribe, folders |
| `dr deliver` | 14+ | Render presets, jobs, start/stop, status, formats/codecs, preset import/export |
| `dr gallery` | 9 | Gallery albums (list/current/set/create), stills (list/grab/export/import/delete) |
| `dr schema` | 2 | Command discovery: list all commands, show JSON Schema |

### Usage Examples

```bash
# Get system info
dr system info

# Project management
dr project list --fields name
dr project create "NewProject" --dry-run
dr project save

# Timeline operations
dr timeline current --fields name,fps
dr timeline marker list
dr timeline timecode get

# Color grading (always create a version first — there is NO undo)
dr color version add 1 "before-edit"
dr color apply-lut 1 /path/to/lut.cube
dr color copy-grade --from 1 --to 2

# Media pool
dr media list --fields clip_name,file_path
dr media folder create "B-Roll"
dr media import /path/to/file.mov

# Render
dr deliver preset list
dr deliver preset load "YouTube 1080p"
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}'
dr deliver start

# Schema discovery (for agents)
dr schema list
dr schema show project.open
```

### Global Options

```bash
dr --pretty ...       # Rich formatted output (TTY only)
dr --fields f1,f2 ... # Filter output fields
dr --json '{...}' ... # Structured JSON input
dr --dry-run ...      # Preview destructive operations
```

## MCP Server

Start the MCP server:

```bash
dr-mcp
```

Key differences from CLI:

- All mutating tools default to `dry_run=True` (CLI defaults to `False`)
- Tool descriptions include metadata: `[risk_level]`, `[mutating]`, `[supports_dry_run]`
- Built-in agent onboarding instructions

For Claude Desktop / Cowork, add the server to your MCP configuration.

## Claude Code Skill

Install as a Claude Code plugin for agent-driven DaVinci Resolve control:

```bash
/plugin marketplace add znznzna/davinci-cli
/plugin install davinci-cli@davinci-cli
```

The agent reads `SKILL.md` to discover all commands, parameters, and workflows automatically.

## Architecture

```
src/davinci_cli/
├── cli.py                 # Click entry point (@click.group "dr")
├── schema_registry.py     # Command → Pydantic Schema mapping
├── core/                  # Connection, environment, validation, exceptions
├── output/formatter.py    # NDJSON / JSON / Rich auto-detection
├── commands/              # system, project, timeline, clip, color, media, deliver, gallery, schema
└── mcp/mcp_server.py      # FastMCP server (~90 tools, reuses _impl functions)
```

All commands are implemented as `_impl()` pure functions. Both CLI (Click) and MCP (FastMCP) call these functions, avoiding logic duplication.

## Known Limitations

- **No undo in DaVinci Resolve API** — all write operations are permanent. Always use `--dry-run` and create color versions before grading.
- **ExportStills API bug** — DaVinci Resolve 20.x `ExportStills()` always returns `False` regardless of actual success.
- **Beat markers** — integer frame rounding causes +/-0.5 frame (+/-21ms @24fps) timing offset.
- **MediaStorage / Fusion not supported** — media operations use the MediaPool API only.
- **Studio-only features** — some operations require DaVinci Resolve Studio. Check with `dr system edition`.

## Development

> **Regular users can skip this section.** `pip install davinci-cli` is all you need.

```bash
git clone https://github.com/znznzna/davinci-cli.git
cd davinci-cli
pip install -e ".[dev]"
```

```bash
# Run tests
python -m pytest tests/unit/ -v

# With coverage
python -m pytest tests/unit/ -v --cov=davinci_cli

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RESOLVE_SCRIPT_API` | Path to DaVinci Resolve scripting API |
| `RESOLVE_SCRIPT_LIB` | Path to DaVinci Resolve shared library |
| `RESOLVE_MODULES` | Path to DaVinci Resolve Python modules |

Auto-detected on macOS and Windows when not set.

## Requirements

- Python >= 3.10
- DaVinci Resolve (Free or Studio)
- macOS / Windows

### Python Dependencies

- [click](https://click.palletsprojects.com/) >= 8.1 — CLI framework
- [rich](https://rich.readthedocs.io/) >= 13.0 — Table output
- [pydantic](https://docs.pydantic.dev/) >= 2.0 — Data validation
- [fastmcp](https://github.com/jlowin/fastmcp) >= 0.1 — MCP server framework

## License

[MIT](LICENSE)
