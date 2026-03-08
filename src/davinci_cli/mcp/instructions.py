"""MCP Server instructions for AI agents (Claude Desktop / Cowork).

Equivalent to SKILL.md but adapted for MCP tool naming conventions.
"""

INSTRUCTIONS = """\
# davinci-cli — MCP Server Guide

You are interacting with DaVinci Resolve through MCP tools.
All tool names use snake_case (e.g., system_ping, project_list, clip_list).

## Getting Started

1. **Verify connection:** Call `system_ping`. If it fails, DaVinci Resolve may not be running.
2. **Get context:** Call `system_info` for version, edition, and current project.
3. **List projects:** Call `project_list(fields="name")` to see available projects.
4. **Open a project:** Call `project_open(name="...", dry_run=True)` first, then confirm with the user.

## Safety Rules

- **All Resolve API writes are irreversible** — there is no undo.
- **Mutating tools default to `dry_run=True`** — preview changes before applying.
- **[risk_level: destroy] tools** require explicit user approval before `dry_run=False`.
- **Always use `fields` parameter** on list tools to minimize response size.
- **clip_index is timeline-dependent** — verify after switching timelines.
- **node_index is 1-based** (not 0-based).

## Error Recovery

| Error Type | exit_code | Recovery |
|------------|-----------|----------|
| ResolveNotRunningError | 1 | Ensure DaVinci Resolve is running, then retry system_ping. |
| ProjectNotOpenError | 2 | Open a project with project_open first. |
| ValidationError | 3 | Check parameter types/values. Use schema tools for reference. |
| EnvironmentError | 4 | Check RESOLVE_SCRIPT_API/LIB/MODULES environment variables. |
| EditionError | 5 | Feature requires DaVinci Resolve Studio (paid version). |

## Key Workflows

### Color Grading
1. `clip_list(fields="index,name")` — Get clip indices
2. `color_version_add(clip_index=N, name="before-edit")` — Save checkpoint (no undo!)
3. `color_apply_lut(clip_index=N, lut_path="...", dry_run=True)` — Preview LUT
4. Apply with `dry_run=False` after user approval

### Render / Deliver
1. `deliver_preset_list()` — List available presets
2. `deliver_preset_load(name="...")` — Load a preset
3. `deliver_add_job(job_data={...}, dry_run=True)` — Preview job
4. `deliver_start(dry_run=True)` — Preview render start
5. `deliver_status()` — Monitor progress (poll >= 5s interval)

### Media Import
1. `media_list(fields="clip_name")` — Check existing media
2. `media_import(paths=[...])` — Import files (absolute paths only)
3. `media_move(clip_names=[...], target_folder="...", dry_run=True)` — Organize

## Tips

- Use `system_page_get()` / `system_page_set()` to navigate Resolve pages.
- `timeline_current_item()` returns the clip at the playhead position.
- `color_copy_grade(from_index, to_index)` copies directly (no separate paste step).
- `gallery_still_grab()` captures a still for the current album.
- Studio-only features return EditionError (exit_code=5) on Free edition.
"""
