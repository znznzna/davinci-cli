# davinci-cli

[![CI](https://github.com/znznzna/davinci-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/znznzna/davinci-cli/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Japanese / 日本語](README.ja.md)

**Agent-first CLI and MCP server for DaVinci Resolve — ~90 commands.**

Control projects, timelines, clips, color grading, media pool, rendering, and gallery operations from the command line or through AI agents. Built with an `_impl` function pattern that shares logic between CLI (Click) and MCP (FastMCP).

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

The CLI and MCP server connect directly to DaVinci Resolve's Python scripting API. No plugin installation required — just ensure DaVinci Resolve is running.

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

### Upgrading

```bash
pip install --upgrade davinci-cli
```

### Choose Your Integration

#### Option A: Claude Code (SKILL-based)

For **Claude Code** users — install the Claude Code Plugin so the agent can discover and use all ~90 commands via the SKILL file:

```bash
/plugin marketplace add znznzna/davinci-cli
/plugin install davinci-cli@davinci-cli
```

The agent reads `SKILL.md` to understand available commands, parameters, and workflows. No manual command typing needed.

#### Option B: Claude Desktop / Cowork (MCP Server)

For **Claude Desktop** or **Cowork** users — register the MCP server:

```bash
dr mcp install
```

Restart Claude Desktop / Cowork. All ~90 commands are available as MCP tools with snake_case naming (e.g., `project_open`, `clip_list`).

Check MCP status:

```bash
dr mcp status
dr mcp test       # Test connection to DaVinci Resolve
```

Key differences from CLI:

- All mutating tools default to `dry_run=True` (CLI defaults to `False`)
- Tool descriptions include metadata: `[risk_level]`, `[mutating]`, `[supports_dry_run]`
- Built-in agent onboarding instructions

#### Option C: Direct CLI / Scripting

Use the `dr` command directly for shell scripting and automation:

```bash
dr system ping
dr project list --fields name
dr color apply-lut 1 /path/to/lut.cube --dry-run
```

### Verify Connection

1. Open DaVinci Resolve
2. Run:

```bash
dr system ping
# -> pong

dr system info
# -> version, edition, current project, current page
```

## Usage Examples

```bash
# List projects
dr project list --fields name

# Open a project (dry-run first)
dr project open "MyProject" --dry-run
dr project open "MyProject"

# List timelines and clips
dr timeline list --fields name
dr clip list --fields index,name

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

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| [`dr system`](#dr-system) | 6 | Connection check, version/edition info, page and keyframe mode control |
| [`dr project`](#dr-project) | 9 | List, open, close, create, delete, save, rename, info, settings |
| [`dr timeline`](#dr-timeline) | 15+ | List, switch, create, delete, export, markers, timecode, tracks, duplicate, scene cuts, subtitles |
| [`dr clip`](#dr-clip) | 9+ | List, info, select, properties, enable/disable, color labels, flags |
| [`dr color`](#dr-color) | 14+ | LUT apply, grade reset/copy, color versions, node LUT, CDL, LUT export, stills |
| [`dr media`](#dr-media) | 13+ | Import, list, move, delete, relink, metadata, transcribe, folders |
| [`dr deliver`](#dr-deliver) | 14+ | Render presets, jobs, start/stop, status, formats/codecs, preset import/export |
| [`dr gallery`](#dr-gallery) | 9 | Gallery albums (list/current/set/create), stills (list/grab/export/import/delete) |
| [`dr schema`](#dr-schema) | 2 | Command discovery: list all commands, show JSON Schema |

### dr system

```bash
dr system ping                # Connection test
dr system version             # API version
dr system edition             # Free or Studio
dr system info                # All system info
dr system page get            # Current page (Edit, Color, etc.)
dr system keyframe-mode get   # Keyframe mode
```

### dr project

```bash
dr project list --fields name       # List projects
dr project open "Name" --dry-run    # Preview open
dr project open "Name"              # Open project
dr project close                    # Close project
dr project create "Name" --dry-run  # Create project
dr project save                     # Save project
dr project info                     # Project details
dr project settings                 # Project settings
dr project rename "NewName"         # Rename project
```

### dr timeline

```bash
dr timeline list --fields name      # List timelines
dr timeline current                 # Current timeline info
dr timeline switch "Name"           # Switch timeline
dr timeline create "Name"           # Create timeline
dr timeline delete "Name" --dry-run # Delete timeline
dr timeline marker list             # List markers
dr timeline marker add --frame 100 --name "Note" --color Blue
dr timeline timecode get            # Get timecode
dr timeline track list              # List tracks
dr timeline duplicate               # Duplicate timeline
```

### dr clip

```bash
dr clip list --fields index,name    # List clips
dr clip info 1                      # Clip details
dr clip select 1                    # Select clip
dr clip property get 1 "Pan"        # Get property
dr clip enable 1 --toggle           # Toggle enable
dr clip color set 1 Orange          # Set color label
dr clip flag add 1 --flag-color Blue
```

### dr color

```bash
dr color apply-lut 1 /path/to/lut.cube --dry-run
dr color reset 1                    # Reset grade
dr color copy-grade --from 1 --to 2 # Copy grade
dr color version list 1             # List versions
dr color version add 1 "checkpoint" # Save version
dr color version load 1 "checkpoint"
dr color node list 1                # List nodes
dr color cdl set 1 --slope 1.1,1.0,0.9
dr color still grab 1               # Grab still
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
dr deliver preset list              # List presets
dr deliver preset load "YouTube 1080p"
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}'
dr deliver start --dry-run          # Preview render
dr deliver start                    # Start render
dr deliver status                   # Render progress
dr deliver stop                     # Stop render
dr deliver format list              # Available formats
dr deliver codec list "mp4"         # Codecs for format
```

### dr gallery

```bash
dr gallery album list               # List albums
dr gallery album current            # Current album
dr gallery album set "Stills"       # Set album
dr gallery album create "New Album"
dr gallery still list               # List stills
dr gallery still export --folder-path /output --format png
```

### dr schema

```bash
dr schema list                      # List all commands
dr schema show project.open         # JSON Schema for command
```

## Global Options

```bash
dr --pretty ...       # Rich formatted output (TTY only)
dr --fields f1,f2 ... # Filter output fields
dr --json '{...}' ... # Structured JSON input
dr --dry-run ...      # Preview destructive operations
```

## Configuration

| Environment Variable | Description |
|---------------------|-------------|
| `RESOLVE_SCRIPT_API` | Path to DaVinci Resolve scripting API |
| `RESOLVE_SCRIPT_LIB` | Path to DaVinci Resolve shared library |
| `RESOLVE_MODULES` | Path to DaVinci Resolve Python modules |

Auto-detected on macOS and Windows when not set.

## Features

- **Agent-first design** — structured JSON I/O, `--json` input, `--fields` filtering, `--dry-run` for all destructive operations
- **Schema-first discovery** — `dr schema list` and `dr schema show <command>` for runtime JSON Schema
- **Auto-detected output** — NDJSON for pipes/agents, Rich tables for TTY
- **Environment auto-setup** — DaVinci Resolve API paths detected automatically on macOS and Windows
- **Pydantic v2 validation** — path traversal and injection protection
- **MCP Server** — native integration with Claude Desktop and Cowork

## Known Limitations

- **No undo in DaVinci Resolve API** — all write operations are permanent. Always use `--dry-run` and create color versions before grading.
- **ExportStills API bug** — DaVinci Resolve 20.x `ExportStills()` always returns `False` regardless of actual success.
- **Beat markers** — integer frame rounding causes +/-0.5 frame (+/-21ms @24fps) timing offset.
- **MediaStorage / Fusion not supported** — media operations use the MediaPool API only.
- **Studio-only features** — some operations require DaVinci Resolve Studio. Check with `dr system edition`.

## Development

### For Contributors Only

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

## Project Structure

```
davinci-cli/
├── src/davinci_cli/           # Main package
│   ├── cli.py                 # Click entry point (dr command)
│   ├── schema_registry.py     # Command → Pydantic Schema mapping
│   ├── decorators.py          # Shared decorators
│   ├── core/                  # Connection, environment, validation, exceptions
│   │   ├── connection.py      # lru_cache Resolve API connection
│   │   ├── environment.py     # macOS/Windows auto-detection
│   │   ├── validation.py      # Path traversal / injection protection
│   │   ├── exceptions.py      # DavinciCLIError hierarchy (exit codes)
│   │   └── edition.py         # Free/Studio detection
│   ├── output/
│   │   └── formatter.py       # NDJSON / JSON / Rich auto-detection
│   ├── commands/              # Command groups
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
│       ├── mcp_server.py      # FastMCP server (~90 tools, reuses _impl)
│       └── instructions.py    # Agent onboarding instructions
├── tests/                     # pytest test suite
├── plugin/                    # Claude Code Plugin
│   └── skills/davinci-cli/
│       └── SKILL.md           # Agent skill file
└── scripts/                   # Version sync utilities
```

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
