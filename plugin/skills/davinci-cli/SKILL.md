---
name: davinci-cli
version: 1.0.1
description: "DaVinci Resolve CLI / MCP \u2014 agent-first interface for controlling DaVinci Resolve. Use when user asks to edit video, color grade, manage timelines, render/deliver, manage media pool, or interact with DaVinci Resolve in any way. Triggers: DaVinci, Resolve, timeline, color grading, rendering, LUT, media pool, dr command. Do NOT use for other video editors like Premiere Pro, Final Cut Pro, or CapCut."
---

# davinci-cli Skill

CLI and MCP server for controlling DaVinci Resolve. Designed for AI agents.

## Agent Quick Contract

1. **Always use `--fields`** to limit response size (e.g., `--fields name,fps`).
2. **Check `dr schema show <command>`** for parameter types before calling.
3. **Use `--dry-run`** before mutating commands to preview changes.
4. **Use `--json`** for structured input (e.g., `--json '{"name": "MyProject"}'`).
5. **Exit codes matter:** 0=ok, 1=resolve not running, 2=no project, 3=validation, 4=env, 5=edition.
6. **All Resolve API writes are irreversible** (no undo) — always dry-run first.

## Schema-First Discovery

```bash
# List all registered commands
dr schema list

# Get JSON Schema for a specific command
dr schema show project.open
```

Output includes `input_schema` (parameters) and `output_schema` (return type).

## Getting Started for Agents

```bash
# Step 1: Verify connection
dr system ping

# Step 2: Get version, edition, current project
dr system info

# Step 3: List projects
dr project list --fields name

# Step 4: Open a project (dry-run first!)
dr project open "ProjectName" --dry-run
# → Confirm with user → then:
dr project open "ProjectName"

# Step 5: List timelines
dr timeline list --fields name

# Step 6: List clips
dr clip list --fields index,name
```

## Module Overview

| Module | Description |
|--------|-------------|
| **system** | Connection check, version/edition info, page/keyframe control |
| **project** | List, open, close, create, delete, save, rename, settings |
| **timeline** | List, switch, create, delete, export, tracks, timecode, markers, duplicate, scene cuts, subtitles |
| **clip** | List timeline clips, info, select, properties, enable, color labels, flags |
| **color** | LUT apply, grade reset/copy, color versions, node LUT, CDL, LUT export, stills |
| **media** | Media pool: list, import, move, delete, relink, metadata, transcribe, folders |
| **deliver** | Render queue: presets, jobs, start/stop, status, formats/codecs, preset import/export |
| **gallery** | Gallery albums, still export/import/delete |
| **schema** | Command discovery: list all commands, show JSON Schema for any command |

## Common Workflows

For detailed workflow examples (color grading, render, media organization, timeline management, gallery stills), see [references/workflows.md](references/workflows.md).

## Input Options

### `--json` (Structured Input)

Pass complex parameters as a JSON object:

```bash
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}'
```

### `--fields` (Output Filtering)

Limit returned fields to reduce response size:

```bash
dr project list --fields name
dr clip list --fields index,name
```

### `--dry-run` (Preview Mode)

Preview destructive operations before executing:

```bash
dr project delete "OldProject" --dry-run
# Returns: {"dry_run": true, "action": "delete", "name": "OldProject"}
```

## Output Formats

Output format is auto-detected:

| Context | Format |
|---------|--------|
| Non-TTY (pipe/agent) | NDJSON (one JSON object per line) or single JSON |
| TTY + `--pretty` | Rich formatted table |

Error responses always use structured JSON:

```json
{"error": "...", "error_type": "ResolveNotRunningError", "exit_code": 1}
```

## Gotchas & Limitations

### No Undo / No Redo

The DaVinci Resolve API provides **no undo mechanism**. Every write operation is permanent.
**Always** use `--dry-run` first. For color grading, create a color version before editing:

```bash
dr color version add <clip_index> "checkpoint-name"
```

### clip_index is timeline-dependent

`clip_index` values belong to the current timeline. When you switch timelines, all previously obtained clip indices become invalid. **Always re-fetch** `clip list` after `timeline switch`.

### node_index is 1-based

Node indices start from 1, not 0. The first node in a clip's node graph is `node_index=1`.

### CopyGrade is a direct operation

`color copy-grade --from X --to Y` copies the grade directly. There is no separate "paste" step (unlike the Resolve GUI's copy/paste workflow).

### Graph object required for node operations

Node operations internally require `TimelineItem.GetNodeGraph()`. This is handled automatically, but it means node operations only work on timeline items (not media pool clips).

### MediaStorage and Fusion are not supported

The CLI does not wrap `MediaStorage` or `Fusion` APIs. Media operations go through the MediaPool API.

### Studio-only features

Some operations require DaVinci Resolve Studio (paid). If called on Free edition, they return `EditionError` (exit_code=5). Check edition with `dr system edition` before attempting.

### Path security

All file path parameters reject path traversal sequences (`..`). Only absolute paths are accepted. Allowed LUT extensions: `.cube`, `.3dl`, `.lut`, `.mga`, `.m3d`.

### Long-running operations

Scene cut detection (`timeline detect-scene-cuts`), subtitle creation (`timeline create-subtitles`), and transcription (`media transcribe`) can take significant time. Do not timeout prematurely.

### Render resource consumption

`deliver start` consumes significant CPU/GPU resources. Always preview with `--dry-run` and obtain user approval. Monitor with `deliver status` at intervals >= 5 seconds.

## Error Handling

All errors return structured JSON with consistent fields:

```json
{
  "error": "Human-readable message",
  "error_type": "ResolveNotRunningError",
  "exit_code": 1
}
```

### Recovery Playbook

| Exit Code | Error Type | Recovery |
|-----------|------------|----------|
| 1 | ResolveNotRunningError | Ensure DaVinci Resolve is running, retry `dr system ping`. |
| 2 | ProjectNotOpenError | Open a project with `dr project open <name>`. |
| 3 | ValidationError | Check parameter types/values. Use `dr schema show <command>`. |
| 4 | EnvironmentError | Check `RESOLVE_SCRIPT_API`, `RESOLVE_SCRIPT_LIB`, `RESOLVE_MODULES`. |
| 5 | EditionError | Feature requires DaVinci Resolve Studio. Check with `dr system edition`. |

## MCP Server

```bash
dr-mcp
```

The MCP server exposes all CLI commands as MCP tools with snake_case naming (e.g., `project_open`, `clip_list`).

**Key differences from CLI:**
- All mutating tools default to `dry_run=True` (CLI defaults to `False`).
- Tool descriptions include metadata tags: `[risk_level]`, `[mutating]`, `[supports_dry_run]`.
- The server includes built-in instructions for agent onboarding.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RESOLVE_SCRIPT_API` | Path to DaVinci Resolve scripting API |
| `RESOLVE_SCRIPT_LIB` | Path to DaVinci Resolve shared library |
| `RESOLVE_MODULES` | Path to DaVinci Resolve Python modules (added to sys.path) |

Auto-detected on macOS and Windows when not set. See `src/davinci_cli/core/environment.py`.
