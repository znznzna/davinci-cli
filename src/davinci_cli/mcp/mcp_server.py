"""FastMCP server — exposes all _impl functions as MCP tools.

Design:
  - MCP tools default dry_run=True (CLI defaults to False)
  - Each tool description includes metadata tags: [risk_level], [mutating], [supports_dry_run]
  - mcp_error_handler catches exceptions and returns structured error responses
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from davinci_cli.commands.beat_markers import beat_marker_impl
from davinci_cli.commands.clip import (
    clip_color_clear_impl,
    clip_color_get_impl,
    clip_color_set_impl,
    clip_enable_impl,
    clip_flag_add_impl,
    clip_flag_clear_impl,
    clip_flag_list_impl,
    clip_info_impl,
    clip_list_impl,
    clip_property_get_impl,
    clip_property_set_impl,
    clip_select_impl,
)
from davinci_cli.commands.color import (
    color_apply_lut_impl,
    color_cdl_set_impl,
    color_copy_grade_impl,
    color_lut_export_impl,
    color_reset_all_impl,
    color_reset_impl,
    color_version_add_impl,
    color_version_current_impl,
    color_version_delete_impl,
    color_version_list_impl,
    color_version_load_impl,
    color_version_rename_impl,
    node_enable_impl,
    node_lut_get_impl,
    node_lut_set_impl,
    still_grab_impl,
    still_list_impl,
)
from davinci_cli.commands.deliver import (
    deliver_add_job_impl,
    deliver_codec_list_impl,
    deliver_delete_all_jobs_impl,
    deliver_delete_job_impl,
    deliver_format_list_impl,
    deliver_is_rendering_impl,
    deliver_job_status_impl,
    deliver_list_jobs_impl,
    deliver_preset_export_impl,
    deliver_preset_import_impl,
    deliver_preset_list_impl,
    deliver_preset_load_impl,
    deliver_start_impl,
    deliver_status_impl,
    deliver_stop_impl,
)
from davinci_cli.commands.gallery import (
    gallery_album_create_impl,
    gallery_album_current_impl,
    gallery_album_list_impl,
    gallery_album_set_impl,
    gallery_still_delete_impl,
    gallery_still_export_impl,
    gallery_still_import_impl,
)
from davinci_cli.commands.media import (
    folder_create_impl,
    folder_delete_impl,
    folder_list_impl,
    media_delete_impl,
    media_export_metadata_impl,
    media_import_impl,
    media_list_impl,
    media_metadata_get_impl,
    media_metadata_set_impl,
    media_move_impl,
    media_relink_impl,
    media_transcribe_impl,
    media_unlink_impl,
)
from davinci_cli.commands.project import (
    project_close_impl,
    project_create_impl,
    project_delete_impl,
    project_info_impl,
    project_list_impl,
    project_open_impl,
    project_rename_impl,
    project_save_impl,
    project_settings_get_impl,
    project_settings_set_impl,
)
from davinci_cli.commands.system import (
    edition_impl,
    info_impl,
    keyframe_mode_get_impl,
    keyframe_mode_set_impl,
    page_get_impl,
    page_set_impl,
    ping_impl,
    version_impl,
)
from davinci_cli.commands.timeline import (
    current_item_impl,
    marker_add_impl,
    marker_delete_impl,
    marker_list_impl,
    timecode_get_impl,
    timecode_set_impl,
    timeline_create_impl,
    timeline_create_subtitles_impl,
    timeline_current_impl,
    timeline_delete_impl,
    timeline_detect_scene_cuts_impl,
    timeline_duplicate_impl,
    timeline_export_impl,
    timeline_list_impl,
    timeline_switch_impl,
    track_add_impl,
    track_delete_impl,
    track_enable_impl,
    track_list_impl,
    track_lock_impl,
)
from davinci_cli.core.exceptions import DavinciCLIError
from davinci_cli.mcp.instructions import INSTRUCTIONS

# --- Error Handler ---


def mcp_error_handler(func: Callable[..., Any]) -> Callable[..., Any]:
    """MCP tool 用エラーハンドリングラッパー。"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except DavinciCLIError as exc:
            return {
                "error": True,
                "message": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": exc.exit_code,
            }
        except Exception as exc:
            return {
                "error": True,
                "message": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": 99,
            }

    return wrapper


# --- MCP Server ---

mcp = FastMCP("davinci-cli", instructions=INSTRUCTIONS)


# ---- system ----


@mcp.tool(
    description=(
        "Check connection to DaVinci Resolve. Returns status and version.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required. Call this first to verify Resolve is running."
    )
)
@mcp_error_handler
def system_ping() -> dict[str, Any]:
    return ping_impl()


@mcp.tool(
    description=(
        "Return DaVinci Resolve version string.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def system_version() -> dict[str, Any]:
    return version_impl()


@mcp.tool(
    description=(
        "Return DaVinci Resolve edition (Free or Studio).\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def system_edition() -> dict[str, Any]:
    return edition_impl()


@mcp.tool(
    description=(
        "Return combined info: version, edition, and current project.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def system_info() -> dict[str, Any]:
    return info_impl()


@mcp.tool(
    description=(
        "Get the current Resolve UI page.\n"
        "[risk_level: read] [mutating: false]\n"
        "Returns one of: media, cut, edit, fusion, color, fairlight, deliver."
    )
)
@mcp_error_handler
def system_page_get() -> dict[str, Any]:
    return page_get_impl()


@mcp.tool(
    description=(
        "Switch the Resolve UI page.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: page (str) — media, cut, edit, fusion, color, fairlight, deliver.\n"
        "IMPORTANT: Always dry_run=True first to preview."
    )
)
@mcp_error_handler
def system_page_set(page: str, dry_run: bool = True) -> dict[str, Any]:
    return page_set_impl(page=page, dry_run=dry_run)


@mcp.tool(
    description=(
        "Get the current keyframe mode.\n"
        "[risk_level: read] [mutating: false]\n"
        "Returns mode: 0=all, 1=color, 2=sizing."
    )
)
@mcp_error_handler
def system_keyframe_mode_get() -> dict[str, Any]:
    return keyframe_mode_get_impl()


@mcp.tool(
    description=(
        "Set the keyframe mode.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: mode (int) — 0=all, 1=color, 2=sizing.\n"
        "IMPORTANT: Always dry_run=True first to preview."
    )
)
@mcp_error_handler
def system_keyframe_mode_set(mode: int, dry_run: bool = True) -> dict[str, Any]:
    return keyframe_mode_set_impl(mode=mode, dry_run=dry_run)


# ---- project ----


@mcp.tool(
    description=(
        "List all projects in the current database.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: fields (str, optional) — comma-separated field names.\n"
        "IMPORTANT: Always specify fields (e.g., 'name') to minimize response size."
    )
)
@mcp_error_handler
def project_list(fields: str | None = None) -> list[dict[str, Any]]:
    field_list = fields.split(",") if fields else None
    return project_list_impl(fields=field_list)


@mcp.tool(
    description=(
        "Open a project by name. Closes the current project as a side effect.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True).\n"
        "IMPORTANT: Call project_list first to verify the project name exists.\n"
        "Unsaved changes in the current project will be lost."
    )
)
@mcp_error_handler
def project_open(name: str, dry_run: bool = True) -> dict[str, Any]:
    return project_open_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Close the current project.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: dry_run (bool, default=True).\n"
        "Unsaved changes will be lost."
    )
)
@mcp_error_handler
def project_close(dry_run: bool = True) -> dict[str, Any]:
    return project_close_impl(dry_run=dry_run)


@mcp.tool(
    description=(
        "Create a new project.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def project_create(name: str, dry_run: bool = True) -> dict[str, Any]:
    return project_create_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Permanently delete a project. This action is irreversible.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first, present the result to the user,\n"
        "and obtain explicit approval before executing with dry_run=False.\n"
        "The Resolve API has no undo — deleted projects cannot be recovered."
    )
)
@mcp_error_handler
def project_delete(name: str, dry_run: bool = True) -> dict[str, Any]:
    return project_delete_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Rename the current project.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def project_rename(name: str, dry_run: bool = True) -> dict[str, Any]:
    return project_rename_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Save the current project.\n[risk_level: write] [mutating: true]\nNo parameters required."
    )
)
@mcp_error_handler
def project_save() -> dict[str, Any]:
    return project_save_impl()


@mcp.tool(
    description=(
        "Return current project information.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: fields (str, optional) — comma-separated field names.\n"
        "IMPORTANT: Always specify fields to minimize response size."
    )
)
@mcp_error_handler
def project_info(fields: str | None = None) -> dict[str, Any]:
    field_list = fields.split(",") if fields else None
    return project_info_impl(fields=field_list)


@mcp.tool(
    description=(
        "Get project settings. Returns a specific setting by key or all settings.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: key (str, optional) — setting key. Omit to get all settings.\n"
        "IMPORTANT: Specify a key when possible to minimize response size."
    )
)
@mcp_error_handler
def project_settings_get(key: str | None = None) -> dict[str, Any]:
    return project_settings_get_impl(key=key)


@mcp.tool(
    description=(
        "Set a project setting value.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: key (str, required), value (str, required), dry_run (bool, default=True).\n"
        "IMPORTANT: Call project_settings_get(key) first to check the current value."
    )
)
@mcp_error_handler
def project_settings_set(key: str, value: str, dry_run: bool = True) -> dict[str, Any]:
    return project_settings_set_impl(key=key, value=value, dry_run=dry_run)


# ---- timeline ----


@mcp.tool(
    description=(
        "List all timelines in the current project.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: fields (str, optional) — comma-separated field names.\n"
        "IMPORTANT: Always specify fields (e.g., 'name') to minimize response size."
    )
)
@mcp_error_handler
def timeline_list(fields: str | None = None) -> list[dict[str, Any]]:
    field_list = fields.split(",") if fields else None
    return timeline_list_impl(fields=field_list)


@mcp.tool(
    description=(
        "Return current timeline information.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: fields (str, optional) — comma-separated field names.\n"
        "IMPORTANT: Always specify fields to minimize response size."
    )
)
@mcp_error_handler
def timeline_current(fields: str | None = None) -> dict[str, Any]:
    field_list = fields.split(",") if fields else None
    return timeline_current_impl(fields=field_list)


@mcp.tool(
    description=(
        "Switch to a different timeline by name.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True).\n"
        "IMPORTANT: After switching, all previously obtained clip_index values become invalid.\n"
        "Always re-fetch clip_list after switching timelines."
    )
)
@mcp_error_handler
def timeline_switch(name: str, dry_run: bool = True) -> dict[str, Any]:
    return timeline_switch_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Create a new empty timeline.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def timeline_create(name: str, dry_run: bool = True) -> dict[str, Any]:
    return timeline_create_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Delete a timeline. This action is irreversible.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first and obtain user approval."
    )
)
@mcp_error_handler
def timeline_delete(name: str, dry_run: bool = True) -> dict[str, Any]:
    return timeline_delete_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Get the current playhead timecode.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required. Returns timecode in HH:MM:SS:FF format."
    )
)
@mcp_error_handler
def timeline_timecode_get() -> dict[str, Any]:
    return timecode_get_impl()


@mcp.tool(
    description=(
        "Set the playhead timecode position.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: timecode (str, HH:MM:SS:FF, e.g., '01:00:00:00'),\n"
        "dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def timeline_timecode_set(timecode: str, dry_run: bool = True) -> dict[str, Any]:
    return timecode_set_impl(timecode=timecode, dry_run=dry_run)


@mcp.tool(
    description=(
        "Get the clip at the current playhead position.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def timeline_current_item() -> dict[str, Any]:
    return current_item_impl()


@mcp.tool(
    description=(
        "List all tracks (video, audio, subtitle) in the current timeline.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def timeline_track_list() -> list[dict[str, Any]]:
    return track_list_impl()


@mcp.tool(
    description=(
        "Add a new track to the current timeline.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: track_type (str) — video, audio, or subtitle."
    )
)
@mcp_error_handler
def timeline_track_add(track_type: str, dry_run: bool = True) -> dict[str, Any]:
    return track_add_impl(track_type=track_type, dry_run=dry_run)


@mcp.tool(
    description=(
        "Delete a track from the current timeline.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: track_type (str) — video, audio, subtitle; track_index (int).\n"
        "IMPORTANT: Get track_index from timeline_track_list first."
    )
)
@mcp_error_handler
def timeline_track_delete(
    track_type: str, track_index: int, dry_run: bool = True
) -> dict[str, Any]:
    return track_delete_impl(track_type=track_type, index=track_index, dry_run=dry_run)


@mcp.tool(
    description=(
        "Get or set track enabled state.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: track_type (str) — video, audio, subtitle;\n"
        "track_index (int); enabled (bool|None).\n"
        "Set enabled=None to get current state, True/False to set."
    )
)
@mcp_error_handler
def timeline_track_enable(
    track_type: str, track_index: int, enabled: bool | None = None
) -> dict[str, Any]:
    return track_enable_impl(track_type=track_type, index=track_index, enabled=enabled)


@mcp.tool(
    description=(
        "Get or set track lock state.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: track_type (str) — video, audio, subtitle;\n"
        "track_index (int); locked (bool|None).\n"
        "Set locked=None to get current state, True/False to set."
    )
)
@mcp_error_handler
def timeline_track_lock(
    track_type: str, track_index: int, locked: bool | None = None
) -> dict[str, Any]:
    return track_lock_impl(track_type=track_type, index=track_index, locked=locked)


@mcp.tool(
    description=(
        "Duplicate the current timeline.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, optional — auto-named if omitted), dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def timeline_duplicate(name: str | None = None, dry_run: bool = True) -> dict[str, Any]:
    return timeline_duplicate_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Detect scene cuts in the current timeline.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required.\n"
        "WARNING: This operation can take significant time on long timelines."
    )
)
@mcp_error_handler
def timeline_detect_scene_cuts() -> dict[str, Any]:
    return timeline_detect_scene_cuts_impl()


@mcp.tool(
    description=(
        "Auto-generate subtitles from audio in the current timeline.\n"
        "[risk_level: write] [mutating: true]\n"
        "No parameters required.\n"
        "WARNING: This operation can take significant time."
    )
)
@mcp_error_handler
def timeline_create_subtitles() -> dict[str, Any]:
    return timeline_create_subtitles_impl()


@mcp.tool(
    description=(
        "Export a timeline to a file.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: format (str — AAF, EDL, FCPXML, etc.), output_path (str, absolute path),\n"
        "timeline_name (str, optional — current if omitted), dry_run (bool, default=True).\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def timeline_export(
    format: str,
    output_path: str,
    timeline_name: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    return timeline_export_impl(
        format=format,
        output_path=output_path,
        timeline_name=timeline_name,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "List all markers in a timeline.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: timeline_name (str, optional — current timeline if omitted)."
    )
)
@mcp_error_handler
def timeline_marker_list(timeline_name: str | None = None) -> list[dict[str, Any]]:
    return marker_list_impl(timeline_name=timeline_name)


@mcp.tool(
    description=(
        "Add a marker to the current timeline.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: frame_id (int), color (str), name (str),\n"
        "note (str, optional), duration (int, default=1).\n"
        "Colors: Blue, Cyan, Green, Yellow, Red, Pink, Purple,\n"
        "Fuchsia, Rose, Lavender, Sky, Mint, Lemon, Sand, Cocoa, Cream."
    )
)
@mcp_error_handler
def timeline_marker_add(
    frame_id: int,
    color: str,
    name: str,
    note: str | None = None,
    duration: int = 1,
    dry_run: bool = True,
) -> dict[str, Any]:
    return marker_add_impl(
        frame_id=frame_id,
        color=color,
        name=name,
        note=note,
        duration=duration,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Delete a marker from the current timeline.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: frame_id (int), dry_run (bool, default=True).\n"
        "IMPORTANT: Get frame_id from timeline_marker_list first."
    )
)
@mcp_error_handler
def timeline_marker_delete(frame_id: int, dry_run: bool = True) -> dict[str, Any]:
    return marker_delete_impl(frame_id=frame_id, dry_run=dry_run)


@mcp.tool(
    description=(
        "Add beat markers on a clip's range at regular BPM intervals.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: bpm (float, required), clip_index (int, required, from clip list),\n"
        "note_value (str, default='1/4'), color (str, default='Blue'),\n"
        "name (str, default=''), duration (int, default=1), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first to preview marker count."
    )
)
@mcp_error_handler
def timeline_marker_beats(
    bpm: float,
    clip_index: int,
    note_value: str = "1/4",
    color: str = "Blue",
    name: str = "",
    duration: int = 1,
    dry_run: bool = True,
) -> dict[str, Any]:
    return beat_marker_impl(
        bpm=bpm,
        clip_index=clip_index,
        note_value=note_value,
        color=color,
        name=name,
        duration=duration,
        dry_run=dry_run,
    )


# ---- clip ----


@mcp.tool(
    description=(
        "List all clips in the current timeline.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: fields (str, optional) — comma-separated field names.\n"
        "IMPORTANT: Always specify fields (e.g., 'index,name') to minimize response size.\n"
        "clip_index values are timeline-dependent — they change when switching timelines."
    )
)
@mcp_error_handler
def clip_list(fields: str | None = None) -> list[dict[str, Any]]:
    field_list = fields.split(",") if fields else None
    return clip_list_impl(fields=field_list)


@mcp.tool(
    description=(
        "Return detailed information about a clip.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: index (int) — clip index from clip_list.\n"
        "IMPORTANT: Get index from clip_list first."
    )
)
@mcp_error_handler
def clip_info(index: int) -> dict[str, Any]:
    return clip_info_impl(index=index)


@mcp.tool(
    description=(
        "Select a clip in the current timeline.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: index (int) — clip index from clip_list.\n"
        "IMPORTANT: Get index from clip_list first."
    )
)
@mcp_error_handler
def clip_select(index: int) -> dict[str, Any]:
    return clip_select_impl(index=index)


@mcp.tool(
    description=(
        "Get a property value of a clip.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: index (int) — clip index from clip_list; key (str) — property name.\n"
        "IMPORTANT: Get index from clip_list first."
    )
)
@mcp_error_handler
def clip_property_get(index: int, key: str) -> dict[str, Any]:
    return clip_property_get_impl(index=index, key=key)


@mcp.tool(
    description=(
        "Set a property value on a clip.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: index (int), key (str), value (str), dry_run (bool, default=True).\n"
        "IMPORTANT: Get index from clip_list first."
    )
)
@mcp_error_handler
def clip_property_set(index: int, key: str, value: str, dry_run: bool = True) -> dict[str, Any]:
    return clip_property_set_impl(index=index, key=key, value=value, dry_run=dry_run)


@mcp.tool(
    description=(
        "Get or set clip enabled state.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: index (int), enabled (bool|None).\n"
        "Set enabled=None to get current state, True/False to set.\n"
        "IMPORTANT: Get index from clip_list first."
    )
)
@mcp_error_handler
def clip_enable(index: int, enabled: bool | None = None) -> dict[str, Any]:
    return clip_enable_impl(index=index, enabled=enabled)


@mcp.tool(
    description=(
        "Get the color label of a clip.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: index (int) — clip index from clip_list."
    )
)
@mcp_error_handler
def clip_color_get(index: int) -> dict[str, Any]:
    return clip_color_get_impl(index=index)


@mcp.tool(
    description=(
        "Set the color label of a clip.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: index (int), color (str).\n"
        "Colors: Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy,\n"
        "Blue, Purple, Violet, Pink, Tan, Beige, Brown, Chocolate."
    )
)
@mcp_error_handler
def clip_color_set(index: int, color: str) -> dict[str, Any]:
    return clip_color_set_impl(index=index, color=color)


@mcp.tool(
    description=(
        "Clear the color label of a clip.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: index (int) — clip index from clip_list."
    )
)
@mcp_error_handler
def clip_color_clear(index: int) -> dict[str, Any]:
    return clip_color_clear_impl(index=index)


@mcp.tool(
    description=(
        "Add a flag to a clip.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: index (int), color (str) — flag color."
    )
)
@mcp_error_handler
def clip_flag_add(index: int, color: str) -> dict[str, Any]:
    return clip_flag_add_impl(index=index, color=color)


@mcp.tool(
    description=(
        "List all flags on a clip.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: index (int) — clip index from clip_list."
    )
)
@mcp_error_handler
def clip_flag_list(index: int) -> list[Any]:
    return clip_flag_list_impl(index=index)


@mcp.tool(
    description=(
        "Clear flags from a clip.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: index (int), color (str, default='All') — specific color or 'All' to clear all."
    )
)
@mcp_error_handler
def clip_flag_clear(index: int, color: str = "All") -> dict[str, Any]:
    return clip_flag_clear_impl(index=index, color=color)


# ---- color ----


@mcp.tool(
    description=(
        "Apply a LUT file to a clip's color grade.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), lut_path (str, absolute path), dry_run (bool, default=True).\n"
        "Allowed extensions: .cube, .3dl, .lut, .mga, .m3d.\n"
        "Path traversal ('..') is rejected for security.\n"
        "IMPORTANT: Get clip_index from clip_list first. Node index is 1-based."
    )
)
@mcp_error_handler
def color_apply_lut(clip_index: int, lut_path: str, dry_run: bool = True) -> dict[str, Any]:
    return color_apply_lut_impl(clip_index=clip_index, lut_path=lut_path, dry_run=dry_run)


@mcp.tool(
    description=(
        "Reset the color grade on a clip.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), dry_run (bool, default=True).\n"
        "IMPORTANT: No undo — consider creating a color version checkpoint first."
    )
)
@mcp_error_handler
def color_reset(clip_index: int, dry_run: bool = True) -> dict[str, Any]:
    return color_reset_impl(clip_index=clip_index, dry_run=dry_run)


@mcp.tool(
    description=(
        "Copy a color grade from one clip to another.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: from_index (int), to_index (int), dry_run (bool, default=True).\n"
        "This is a direct copy — there is no separate paste step."
    )
)
@mcp_error_handler
def color_copy_grade(from_index: int, to_index: int, dry_run: bool = True) -> dict[str, Any]:
    return color_copy_grade_impl(from_index=from_index, to_index=to_index, dry_run=dry_run)


@mcp.tool(
    description=(
        "List color grading versions for a clip.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: clip_index (int), version_type (int, 0=local, 1=remote, default=0).\n"
        "Get clip_index from clip_list first."
    )
)
@mcp_error_handler
def color_version_list(clip_index: int, version_type: int = 0) -> list[dict[str, Any]]:
    return color_version_list_impl(clip_index=clip_index, version_type=version_type)


@mcp.tool(
    description=(
        "Get the current color version name for a clip.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: clip_index (int).\n"
        "Get clip_index from clip_list first."
    )
)
@mcp_error_handler
def color_version_current(clip_index: int) -> dict[str, Any]:
    return color_version_current_impl(clip_index=clip_index)


@mcp.tool(
    description=(
        "Add a new color version to a clip.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), name (str), version_type (int, 0=local, 1=remote, default=0),\n"
        "dry_run (bool, default=True).\n"
        "Use this to create checkpoints before destructive color operations."
    )
)
@mcp_error_handler
def color_version_add(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = True,
) -> dict[str, Any]:
    return color_version_add_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Load a color version by name.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), name (str), version_type (int, 0=local, 1=remote, default=0),\n"
        "dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def color_version_load(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = True,
) -> dict[str, Any]:
    return color_version_load_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Delete a color version. This action is irreversible.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), name (str), version_type (int, 0=local, 1=remote, default=0),\n"
        "dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first and obtain user approval."
    )
)
@mcp_error_handler
def color_version_delete(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = True,
) -> dict[str, Any]:
    return color_version_delete_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Rename a color version.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), old_name (str), new_name (str),\n"
        "version_type (int, 0=local, 1=remote, default=0), dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def color_version_rename(
    clip_index: int,
    old_name: str,
    new_name: str,
    version_type: int = 0,
    dry_run: bool = True,
) -> dict[str, Any]:
    return color_version_rename_impl(
        clip_index=clip_index,
        old_name=old_name,
        new_name=new_name,
        version_type=version_type,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Set a LUT on a specific node.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), node_index (int, 1-based), lut_path (str, absolute path),\n"
        "dry_run (bool, default=True).\n"
        "Allowed extensions: .cube, .3dl, .lut, .mga, .m3d.\n"
        "Path traversal ('..') is rejected for security.\n"
        "IMPORTANT: node_index is 1-based (first node = 1)."
    )
)
@mcp_error_handler
def color_node_lut_set(
    clip_index: int, node_index: int, lut_path: str, dry_run: bool = True
) -> dict[str, Any]:
    return node_lut_set_impl(
        clip_index=clip_index,
        node_index=node_index,
        lut_path=lut_path,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Get the LUT path set on a specific node.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: clip_index (int), node_index (int, 1-based).\n"
        "IMPORTANT: node_index is 1-based (first node = 1)."
    )
)
@mcp_error_handler
def color_node_lut_get(clip_index: int, node_index: int) -> dict[str, Any]:
    return node_lut_get_impl(clip_index=clip_index, node_index=node_index)


@mcp.tool(
    description=(
        "Set a node's enabled/disabled state.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), node_index (int, 1-based), enabled (bool),\n"
        "dry_run (bool, default=True).\n"
        "IMPORTANT: node_index is 1-based (first node = 1)."
    )
)
@mcp_error_handler
def color_node_enable(
    clip_index: int, node_index: int, enabled: bool, dry_run: bool = True
) -> dict[str, Any]:
    return node_enable_impl(
        clip_index=clip_index,
        node_index=node_index,
        enabled=enabled,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Set CDL (Color Decision List) values on a node.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), node_index (int, 1-based),\n"
        "slope (str, RGB space-separated, e.g., '1.0 1.0 1.0'),\n"
        "offset (str, RGB), power (str, RGB), saturation (str, RGB),\n"
        "dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def color_cdl_set(
    clip_index: int,
    node_index: int,
    slope: str,
    offset: str,
    power: str,
    saturation: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    return color_cdl_set_impl(
        clip_index=clip_index,
        node_index=node_index,
        slope=slope,
        offset=offset,
        power=power,
        saturation=saturation,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Export a LUT from a clip's grade to a file.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), export_type (int), path (str, absolute path),\n"
        "dry_run (bool, default=True).\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def color_lut_export(
    clip_index: int, export_type: int, path: str, dry_run: bool = True
) -> dict[str, Any]:
    return color_lut_export_impl(
        clip_index=clip_index,
        export_type=export_type,
        path=path,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Reset the entire node graph on a clip. More destructive than color_reset.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), dry_run (bool, default=True).\n"
        "IMPORTANT: This resets the full node graph, not just individual node values.\n"
        "No undo — consider creating a color version checkpoint first."
    )
)
@mcp_error_handler
def color_reset_all(clip_index: int, dry_run: bool = True) -> dict[str, Any]:
    return color_reset_all_impl(clip_index=clip_index, dry_run=dry_run)


@mcp.tool(
    description=(
        "Grab (capture) a still from a clip into the current gallery album.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def color_still_grab(clip_index: int, dry_run: bool = True) -> dict[str, Any]:
    return still_grab_impl(clip_index=clip_index, dry_run=dry_run)


@mcp.tool(
    description=(
        "List stills in the current gallery album.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def color_still_list() -> list[dict[str, Any]]:
    return still_list_impl()


# ---- media ----


@mcp.tool(
    description=(
        "List clips in the media pool.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: folder (str, optional), fields (str, optional) — comma-separated.\n"
        "IMPORTANT: Always specify fields (e.g., 'clip_name,file_path') to minimize response size."
    )
)
@mcp_error_handler
def media_list(folder: str | None = None, fields: str | None = None) -> list[dict[str, Any]]:
    field_list = fields.split(",") if fields else None
    return media_list_impl(folder_name=folder, fields=field_list)


@mcp.tool(
    description=(
        "Import media files into the media pool.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: paths (list[str]) — absolute file paths.\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def media_import(paths: list[str]) -> dict[str, Any]:
    return media_import_impl(paths=paths)


@mcp.tool(
    description=(
        "Move media clips to a different folder in the media pool.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_names (list[str]), target_folder (str), dry_run (bool, default=True).\n"
        "IMPORTANT: Get clip_names from media_list first."
    )
)
@mcp_error_handler
def media_move(clip_names: list[str], target_folder: str, dry_run: bool = True) -> dict[str, Any]:
    return media_move_impl(clip_names=clip_names, target_folder=target_folder, dry_run=dry_run)


@mcp.tool(
    description=(
        "Delete media clips from the media pool. This action is irreversible.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_names (list[str]), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first, present result, obtain user approval.\n"
        "Get clip_names from media_list first."
    )
)
@mcp_error_handler
def media_delete(clip_names: list[str], dry_run: bool = True) -> dict[str, Any]:
    return media_delete_impl(clip_names=clip_names, dry_run=dry_run)


@mcp.tool(
    description=(
        "Relink media clips to a new folder path.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_names (list[str]), folder_path (str, absolute),\n"
        "dry_run (bool, default=True).\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def media_relink(clip_names: list[str], folder_path: str, dry_run: bool = True) -> dict[str, Any]:
    return media_relink_impl(clip_names=clip_names, folder_path=folder_path, dry_run=dry_run)


@mcp.tool(
    description=(
        "Unlink media clips from their source files.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: clip_names (list[str]).\n"
        "Get clip_names from media_list first."
    )
)
@mcp_error_handler
def media_unlink(clip_names: list[str]) -> dict[str, Any]:
    return media_unlink_impl(clip_names=clip_names)


@mcp.tool(
    description=(
        "Get metadata for a media clip.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: clip_name (str), key (str, optional — omit for all metadata).\n"
        "IMPORTANT: Specify a key when possible to minimize response size."
    )
)
@mcp_error_handler
def media_metadata_get(clip_name: str, key: str | None = None) -> dict[str, Any]:
    return media_metadata_get_impl(clip_name=clip_name, key=key)


@mcp.tool(
    description=(
        "Set a metadata value on a media clip.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_name (str), key (str), value (str), dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def media_metadata_set(
    clip_name: str, key: str, value: str, dry_run: bool = True
) -> dict[str, Any]:
    return media_metadata_set_impl(clip_name=clip_name, key=key, value=value, dry_run=dry_run)


@mcp.tool(
    description=(
        "Export media pool metadata to a CSV file.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: file_name (str, absolute path), dry_run (bool, default=True).\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def media_export_metadata(file_name: str, dry_run: bool = True) -> dict[str, Any]:
    return media_export_metadata_impl(file_name=file_name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Transcribe audio from a media clip.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: clip_name (str).\n"
        "WARNING: This operation can take significant time."
    )
)
@mcp_error_handler
def media_transcribe(clip_name: str) -> dict[str, Any]:
    return media_transcribe_impl(clip_name=clip_name)


@mcp.tool(
    description=(
        "List folders in the media pool (root level).\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required. Returns sub-folders of the root folder."
    )
)
@mcp_error_handler
def media_folder_list() -> list[dict[str, Any]]:
    return folder_list_impl()


@mcp.tool(
    description=(
        "Create a new folder in the media pool.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: name (str) — folder name."
    )
)
@mcp_error_handler
def media_folder_create(name: str) -> dict[str, Any]:
    return folder_create_impl(name=name)


@mcp.tool(
    description=(
        "Delete a folder from the media pool. This action is irreversible.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first and obtain user approval.\n"
        "All clips inside the folder will also be deleted."
    )
)
@mcp_error_handler
def media_folder_delete(name: str, dry_run: bool = True) -> dict[str, Any]:
    return folder_delete_impl(name=name, dry_run=dry_run)


# ---- deliver ----


@mcp.tool(
    description=(
        "List available render presets.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def deliver_preset_list() -> list[dict[str, Any]]:
    return deliver_preset_list_impl()


@mcp.tool(
    description=(
        "Load a render preset by name.\n"
        "[risk_level: write] [mutating: true]\n"
        "Params: name (str) — preset name from deliver_preset_list.\n"
        "IMPORTANT: Call deliver_preset_list first to verify the name."
    )
)
@mcp_error_handler
def deliver_preset_load(name: str) -> dict[str, Any]:
    return deliver_preset_load_impl(name=name)


@mcp.tool(
    description=(
        "Add a render job to the queue.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: job_data (dict — keys: output_dir, filename, etc.), dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def deliver_add_job(job_data: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    return deliver_add_job_impl(job_data=job_data, dry_run=dry_run)


@mcp.tool(
    description=(
        "List render jobs in the queue.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: fields (str, optional) — comma-separated field names.\n"
        "IMPORTANT: Always specify fields (e.g., 'job_id,status') to minimize response size."
    )
)
@mcp_error_handler
def deliver_list_jobs(fields: str | None = None) -> list[dict[str, Any]]:
    field_list = fields.split(",") if fields else None
    return deliver_list_jobs_impl(fields=field_list)


@mcp.tool(
    description=(
        "Start rendering jobs in the deliver queue.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: job_ids (list[str], optional — None renders all), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first. Rendering consumes significant CPU/GPU resources.\n"
        "Present the dry-run result to the user and obtain explicit approval.\n"
        "Monitor progress with deliver_status (poll interval >= 5s)."
    )
)
@mcp_error_handler
def deliver_start(job_ids: list[str] | None = None, dry_run: bool = True) -> dict[str, Any]:
    return deliver_start_impl(job_ids=job_ids, dry_run=dry_run)


@mcp.tool(
    description=(
        "Stop all rendering immediately.\n"
        "[risk_level: write] [mutating: true]\n"
        "No parameters required. Partially rendered files may be incomplete."
    )
)
@mcp_error_handler
def deliver_stop() -> dict[str, Any]:
    return deliver_stop_impl()


@mcp.tool(
    description=(
        "Get overall render progress (percent, status, ETA).\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required. Use a poll interval of >= 5 seconds."
    )
)
@mcp_error_handler
def deliver_status() -> dict[str, Any]:
    return deliver_status_impl()


@mcp.tool(
    description=(
        "Delete a render job from the queue.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: job_id (str), dry_run (bool, default=True).\n"
        "IMPORTANT: Get job_id from deliver_list_jobs first."
    )
)
@mcp_error_handler
def deliver_delete_job(job_id: str, dry_run: bool = True) -> dict[str, Any]:
    return deliver_delete_job_impl(job_id=job_id, dry_run=dry_run)


@mcp.tool(
    description=(
        "Delete all render jobs from the queue. This action is irreversible.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first and obtain explicit user approval."
    )
)
@mcp_error_handler
def deliver_delete_all_jobs(dry_run: bool = True) -> dict[str, Any]:
    return deliver_delete_all_jobs_impl(dry_run=dry_run)


@mcp.tool(
    description=(
        "Get the status of a specific render job.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: job_id (str) — from deliver_list_jobs."
    )
)
@mcp_error_handler
def deliver_job_status(job_id: str) -> dict[str, Any]:
    return deliver_job_status_impl(job_id=job_id)


@mcp.tool(
    description=(
        "Check if rendering is currently in progress.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def deliver_is_rendering() -> dict[str, Any]:
    return deliver_is_rendering_impl()


@mcp.tool(
    description=(
        "List available render output formats.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def deliver_format_list() -> dict[str, Any]:
    return deliver_format_list_impl()


@mcp.tool(
    description=(
        "List available codecs for a given render format.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: format_name (str) — from deliver_format_list."
    )
)
@mcp_error_handler
def deliver_codec_list(format_name: str) -> dict[str, Any]:
    return deliver_codec_list_impl(format_name=format_name)


@mcp.tool(
    description=(
        "Import a render preset from a file.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: path (str, absolute), dry_run (bool, default=True).\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def deliver_preset_import(path: str, dry_run: bool = True) -> dict[str, Any]:
    return deliver_preset_import_impl(path=path, dry_run=dry_run)


@mcp.tool(
    description=(
        "Export a render preset to a file.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str), path (str, absolute), dry_run (bool, default=True).\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def deliver_preset_export(name: str, path: str, dry_run: bool = True) -> dict[str, Any]:
    return deliver_preset_export_impl(name=name, path=path, dry_run=dry_run)


# ---- gallery ----


@mcp.tool(
    description=(
        "List all gallery albums.\n[risk_level: read] [mutating: false]\nNo parameters required."
    )
)
@mcp_error_handler
def gallery_album_list() -> list[dict[str, Any]]:
    return gallery_album_list_impl()


@mcp.tool(
    description=(
        "Get the current gallery album.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required."
    )
)
@mcp_error_handler
def gallery_album_current() -> dict[str, Any]:
    return gallery_album_current_impl()


@mcp.tool(
    description=(
        "Switch to a different gallery album.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str) — album name from gallery_album_list, dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def gallery_album_set(name: str, dry_run: bool = True) -> dict[str, Any]:
    return gallery_album_set_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description=(
        "Create a new gallery album.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: dry_run (bool, default=True)."
    )
)
@mcp_error_handler
def gallery_album_create(dry_run: bool = True) -> dict[str, Any]:
    return gallery_album_create_impl(dry_run=dry_run)


@mcp.tool(
    description=(
        "Export stills from the current album to files.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: folder_path (str, absolute), file_prefix (str, default='still'),\n"
        "format (str, default='dpx') — dpx, cin, tif, jpg, png, tga, bmp, exr.\n"
        "dry_run (bool, default=True).\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def gallery_still_export(
    folder_path: str,
    file_prefix: str = "still",
    format: str = "dpx",
    dry_run: bool = True,
) -> dict[str, Any]:
    return gallery_still_export_impl(
        folder_path=folder_path,
        file_prefix=file_prefix,
        format=format,
        dry_run=dry_run,
    )


@mcp.tool(
    description=(
        "Import stills into the current gallery album.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: paths (list[str], absolute paths), dry_run (bool, default=True).\n"
        "Path traversal ('..') is rejected for security."
    )
)
@mcp_error_handler
def gallery_still_import(paths: list[str], dry_run: bool = True) -> dict[str, Any]:
    return gallery_still_import_impl(paths=paths, dry_run=dry_run)


@mcp.tool(
    description=(
        "Delete stills from the current gallery album. This action is irreversible.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: still_indices (list[int]) — from color_still_list, dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first and obtain user approval."
    )
)
@mcp_error_handler
def gallery_still_delete(still_indices: list[int], dry_run: bool = True) -> dict[str, Any]:
    return gallery_still_delete_impl(still_indices=still_indices, dry_run=dry_run)


if __name__ == "__main__":
    mcp.run()
