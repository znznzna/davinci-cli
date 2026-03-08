"""dr timeline — タイムライン操作コマンド。

共通デコレータ使用。Resolve接続は core.connection を使用。
"""

from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.decorators import dry_run_option, fields_option, json_input_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema

# --- Pydantic Models ---


class TimelineListItem(BaseModel):
    name: str
    fps: float | None = None


class TimelineCurrentOutput(BaseModel):
    name: str
    fps: float | None = None
    width: int | None = None
    height: int | None = None
    start_timecode: str | None = None


class TimelineSwitchOutput(BaseModel):
    switched: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    name: str | None = None


class TimelineSwitchInput(BaseModel):
    name: str


class TimelineCreateOutput(BaseModel):
    created: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    name: str | None = None


class TimelineCreateInput(BaseModel):
    name: str
    fps: float | None = None
    width: int | None = None
    height: int | None = None


class TimelineDeleteOutput(BaseModel):
    deleted: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    name: str | None = None


class TimelineDeleteInput(BaseModel):
    name: str


class TimelineExportOutput(BaseModel):
    exported: str | None = None
    format: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    output: str | None = None


class TimelineExportInput(BaseModel):
    format: str
    output: str
    timeline: str | None = None


class MarkerInfo(BaseModel):
    frame_id: int
    color: str
    name: str
    note: str | None = None
    duration: int = 1


class MarkerAddOutput(BaseModel):
    added: bool | None = None
    frame_id: int | None = None
    dry_run: bool | None = None
    action: str | None = None
    color: str | None = None
    name: str | None = None


class MarkerAddInput(BaseModel):
    frame_id: int
    color: str
    name: str
    note: str | None = None
    duration: int = 1


class MarkerDeleteInput(BaseModel):
    frame_id: int


class MarkerDeleteOutput(BaseModel):
    deleted: bool | None = None
    frame_id: int | None = None
    dry_run: bool | None = None
    action: str | None = None


class TimecodeGetOutput(BaseModel):
    timecode: str


class TimecodeSetOutput(BaseModel):
    set: bool | None = None
    timecode: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class TimecodeSetInput(BaseModel):
    timecode: str


class TrackListItem(BaseModel):
    type: str
    index: int
    name: str


class TrackAddOutput(BaseModel):
    added: bool | None = None
    track_type: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    sub_track_type: str | None = None


class TrackAddInput(BaseModel):
    track_type: str
    sub_track_type: str | None = None


class TrackDeleteOutput(BaseModel):
    deleted: bool | None = None
    track_type: str | None = None
    index: int | None = None
    dry_run: bool | None = None
    action: str | None = None


class TrackDeleteInput(BaseModel):
    track_type: str
    index: int


class TrackEnableOutput(BaseModel):
    enabled: bool | None = None
    track_type: str | None = None
    index: int | None = None
    set: bool | None = None


class TrackEnableInput(BaseModel):
    track_type: str
    index: int
    enabled: bool | None = None


class TrackLockOutput(BaseModel):
    locked: bool | None = None
    track_type: str | None = None
    index: int | None = None
    set: bool | None = None


class TrackLockInput(BaseModel):
    track_type: str
    index: int
    locked: bool | None = None


class CurrentItemOutput(BaseModel):
    name: str | None = None


class TimelineDuplicateOutput(BaseModel):
    duplicated: bool | None = None
    name: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class TimelineDuplicateInput(BaseModel):
    name: str | None = None


class TimelineDetectSceneCutsOutput(BaseModel):
    detected: bool


class TimelineCreateSubtitlesOutput(BaseModel):
    created: bool


# --- Helper ---


def _get_current_project() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise ProjectNotOpenError()
    return project


def _get_current_timeline() -> Any:
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    return tl


def _get_start_frame_offset(tl: Any) -> int:
    """タイムラインの開始タイムコードをフレーム数に変換して返す。"""
    tc = tl.GetStartTimecode() or "00:00:00:00"
    parts = tc.replace(";", ":").split(":")
    if len(parts) != 4:
        return 0
    h, m, s, f = (int(p) for p in parts)
    fps_str = tl.GetSetting("timelineFrameRate") or "24"
    fps = int(float(fps_str))
    return h * 3600 * fps + m * 60 * fps + s * fps + f


def _get_timeline_by_name(project: Any, name: str) -> Any:
    count = project.GetTimelineCount()
    for i in range(1, count + 1):
        tl = project.GetTimelineByIndex(i)
        if tl and tl.GetName() == name:
            return tl
    raise ValidationError(
        field="timeline", reason=f"Timeline not found: {name}"
    )


# --- _impl Functions ---


def timeline_list_impl(fields: list[str] | None = None) -> list[dict]:
    project = _get_current_project()
    count = project.GetTimelineCount()
    timelines: list[dict] = []
    for i in range(1, count + 1):
        tl = project.GetTimelineByIndex(i)
        if tl is None:
            continue
        info: dict = {"name": tl.GetName()}
        if fields is None or "fps" in fields:
            try:
                info["fps"] = float(tl.GetSetting("timelineFrameRate"))
            except (ValueError, TypeError):
                info["fps"] = None
        timelines.append(info)
    if fields:
        timelines = [
            {k: v for k, v in t.items() if k in fields} for t in timelines
        ]
    return timelines


def timeline_current_impl(fields: list[str] | None = None) -> dict:
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    info = {
        "name": tl.GetName(),
        "fps": float(tl.GetSetting("timelineFrameRate") or 0),
        "width": int(tl.GetSetting("timelineResolutionWidth") or 0),
        "height": int(tl.GetSetting("timelineResolutionHeight") or 0),
        "start_timecode": tl.GetStartTimecode(),
    }
    if fields:
        info = {k: v for k, v in info.items() if k in fields}
    return info


def timeline_switch_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "switch", "name": name}
    project = _get_current_project()
    tl = _get_timeline_by_name(project, name)
    project.SetCurrentTimeline(tl)
    return {"switched": name}


def timeline_create_impl(
    name: str,
    fps: float | None = None,
    width: int | None = None,
    height: int | None = None,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "create", "name": name}
    project = _get_current_project()
    media_pool = project.GetMediaPool()
    tl = media_pool.CreateEmptyTimeline(name)
    if not tl:
        raise ValidationError(
            field="name", reason=f"Failed to create timeline: {name}"
        )
    if fps is not None:
        tl.SetSetting("timelineFrameRate", str(fps))
    if width is not None:
        tl.SetSetting("timelineResolutionWidth", str(width))
    if height is not None:
        tl.SetSetting("timelineResolutionHeight", str(height))
    return {"created": name}


def timeline_delete_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "delete", "name": name}
    project = _get_current_project()
    tl = _get_timeline_by_name(project, name)
    media_pool = project.GetMediaPool()
    media_pool.DeleteTimelines([tl])
    return {"deleted": name}


def timeline_export_impl(
    format: str,
    output_path: str,
    timeline_name: str | None = None,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "export",
            "format": format,
            "output": output_path,
        }
    project = _get_current_project()
    tl = (
        _get_timeline_by_name(project, timeline_name)
        if timeline_name
        else project.GetCurrentTimeline()
    )
    if not tl:
        raise ProjectNotOpenError()
    result = tl.Export(output_path, format)
    if result is False:
        raise ValidationError(
            field="format",
            reason=f"Export failed for format '{format}' to '{output_path}'",
        )
    return {"exported": output_path, "format": format}


def marker_list_impl(timeline_name: str | None = None) -> list[dict]:
    project = _get_current_project()
    tl = (
        _get_timeline_by_name(project, timeline_name)
        if timeline_name
        else project.GetCurrentTimeline()
    )
    if not tl:
        raise ProjectNotOpenError()
    offset = _get_start_frame_offset(tl)
    markers = tl.GetMarkers() or {}
    return [
        {
            "frame_id": rel_frame + offset,
            "color": info.get("color", ""),
            "name": info.get("name", ""),
            "note": info.get("note", ""),
            "duration": info.get("duration", 1),
        }
        for rel_frame, info in markers.items()
    ]


def marker_add_impl(
    frame_id: int,
    color: str,
    name: str,
    note: str | None = None,
    duration: int = 1,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "marker_add",
            "frame_id": frame_id,
            "color": color,
            "name": name,
        }
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    offset = _get_start_frame_offset(tl)
    rel_frame = frame_id - offset
    tl.AddMarker(rel_frame, color, name, note or "", duration)
    return {"added": True, "frame_id": frame_id}


def marker_delete_impl(frame_id: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "marker_delete",
            "frame_id": frame_id,
        }
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    offset = _get_start_frame_offset(tl)
    rel_frame = frame_id - offset
    tl.DeleteMarkerAtFrame(rel_frame)
    return {"deleted": True, "frame_id": frame_id}


def timecode_get_impl() -> dict:
    tl = _get_current_timeline()
    return {"timecode": tl.GetCurrentTimecode()}


def timecode_set_impl(timecode: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "timecode_set", "timecode": timecode}
    tl = _get_current_timeline()
    result = tl.SetCurrentTimecode(timecode)
    if result is False:
        raise ValidationError(
            field="timecode", reason=f"Failed to set timecode: {timecode}"
        )
    return {"set": True, "timecode": timecode}


_VALID_TRACK_TYPES = {"video", "audio", "subtitle"}


def track_list_impl() -> list[dict]:
    """全トラックタイプのトラック一覧を返す。"""
    tl = _get_current_timeline()
    result = []
    for track_type in ["video", "audio", "subtitle"]:
        count = tl.GetTrackCount(track_type)
        for idx in range(1, count + 1):
            name = tl.GetTrackName(track_type, idx)
            result.append(
                {"type": track_type, "index": idx, "name": name or f"{track_type} {idx}"}
            )
    return result


def track_add_impl(
    track_type: str, sub_track_type: str | None = None, dry_run: bool = False
) -> dict:
    """トラックを追加する。"""
    if track_type not in _VALID_TRACK_TYPES:
        raise ValidationError(
            field="track_type",
            reason=f"Invalid: {track_type}. Valid: {', '.join(sorted(_VALID_TRACK_TYPES))}",
        )
    if dry_run:
        return {
            "dry_run": True,
            "action": "track_add",
            "track_type": track_type,
            "sub_track_type": sub_track_type,
        }
    tl = _get_current_timeline()
    result = (
        tl.AddTrack(track_type, sub_track_type)
        if sub_track_type
        else tl.AddTrack(track_type)
    )
    if result is False:
        raise ValidationError(
            field="track_type", reason=f"Failed to add {track_type} track"
        )
    return {"added": True, "track_type": track_type}


def track_delete_impl(
    track_type: str, index: int, dry_run: bool = False
) -> dict:
    """トラックを削除する。"""
    if track_type not in _VALID_TRACK_TYPES:
        raise ValidationError(
            field="track_type",
            reason=f"Invalid: {track_type}. Valid: {', '.join(sorted(_VALID_TRACK_TYPES))}",
        )
    if dry_run:
        return {
            "dry_run": True,
            "action": "track_delete",
            "track_type": track_type,
            "index": index,
        }
    tl = _get_current_timeline()
    result = tl.DeleteTrack(track_type, index)
    if result is False:
        raise ValidationError(
            field="index",
            reason=f"Failed to delete {track_type} track at index {index}",
        )
    return {"deleted": True, "track_type": track_type, "index": index}


def track_enable_impl(
    track_type: str, index: int, enabled: bool | None = None
) -> dict:
    """トラックの有効/無効を取得または設定する。"""
    if track_type not in _VALID_TRACK_TYPES:
        raise ValidationError(
            field="track_type",
            reason=f"Invalid: {track_type}. Valid: {', '.join(sorted(_VALID_TRACK_TYPES))}",
        )
    tl = _get_current_timeline()
    if enabled is None:
        val = tl.GetIsTrackEnabled(track_type, index)
        return {"enabled": val, "track_type": track_type, "index": index}
    result = tl.SetTrackEnable(track_type, index, enabled)
    if result is False:
        raise ValidationError(
            field="enabled", reason="Failed to set track enable"
        )
    return {"set": True, "enabled": enabled, "track_type": track_type, "index": index}


def track_lock_impl(
    track_type: str, index: int, locked: bool | None = None
) -> dict:
    """トラックのロック状態を取得または設定する。"""
    if track_type not in _VALID_TRACK_TYPES:
        raise ValidationError(
            field="track_type",
            reason=f"Invalid: {track_type}. Valid: {', '.join(sorted(_VALID_TRACK_TYPES))}",
        )
    tl = _get_current_timeline()
    if locked is None:
        val = tl.GetIsTrackLocked(track_type, index)
        return {"locked": val, "track_type": track_type, "index": index}
    result = tl.SetTrackLock(track_type, index, locked)
    if result is False:
        raise ValidationError(
            field="locked", reason="Failed to set track lock"
        )
    return {"set": True, "locked": locked, "track_type": track_type, "index": index}


def current_item_impl() -> dict:
    tl = _get_current_timeline()
    item = tl.GetCurrentVideoItem()
    if not item:
        return {"name": None}
    return {"name": item.GetName()}


def timeline_duplicate_impl(name: str | None = None, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "duplicate", "name": name}
    tl = _get_current_timeline()
    new_tl = tl.DuplicateTimeline(name) if name else tl.DuplicateTimeline()
    if not new_tl:
        raise ValidationError(field="name", reason="Failed to duplicate timeline")
    return {"duplicated": True, "name": new_tl.GetName()}


def timeline_detect_scene_cuts_impl() -> dict:
    tl = _get_current_timeline()
    result = tl.DetectSceneCuts()
    return {"detected": bool(result)}


def timeline_create_subtitles_impl() -> dict:
    tl = _get_current_timeline()
    result = tl.CreateSubtitlesFromAudio()
    return {"created": bool(result)}


# --- CLI Commands ---


@click.group()
def timeline() -> None:
    """Timeline operations."""


@timeline.command(name="list")
@fields_option
@click.pass_context
def timeline_list(ctx: click.Context, fields: list[str] | None) -> None:
    """タイムライン一覧。"""
    result = timeline_list_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="current")
@fields_option
@click.pass_context
def timeline_current(ctx: click.Context, fields: list[str] | None) -> None:
    """現在のタイムライン情報。"""
    result = timeline_current_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="switch")
@click.argument("name")
@dry_run_option
@click.pass_context
def timeline_switch(ctx: click.Context, name: str, dry_run: bool) -> None:
    """タイムライン切り替え。"""
    result = timeline_switch_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="create")
@click.option("--name", default=None)
@json_input_option
@dry_run_option
@click.pass_context
def timeline_create(
    ctx: click.Context,
    name: str | None,
    json_input: dict | None,
    dry_run: bool,
) -> None:
    """新規タイムライン作成。"""
    fps = width = height = None
    if json_input:
        data = TimelineCreateInput.model_validate(json_input)
        name = data.name
        fps = data.fps
        width = data.width
        height = data.height
    if not name:
        raise click.UsageError("--name or --json is required")
    result = timeline_create_impl(
        name=name, fps=fps, width=width, height=height, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="delete")
@click.argument("name")
@dry_run_option
@click.pass_context
def timeline_delete(ctx: click.Context, name: str, dry_run: bool) -> None:
    """タイムライン削除（破壊的操作）。"""
    result = timeline_delete_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="export")
@json_input_option
@dry_run_option
@click.pass_context
def timeline_export(
    ctx: click.Context, json_input: dict | None, dry_run: bool
) -> None:
    """タイムラインエクスポート（XML/AAF/EDL）。"""
    if not json_input:
        raise click.UsageError("--json is required for export")
    data = TimelineExportInput.model_validate(json_input)
    result = timeline_export_impl(
        format=data.format,
        output_path=data.output,
        timeline_name=data.timeline,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.group(name="timecode")
def timeline_timecode() -> None:
    """Timecode operations."""


@timeline_timecode.command(name="get")
@click.pass_context
def timecode_get_cmd(ctx: click.Context) -> None:
    """現在のタイムコード取得。"""
    result = timecode_get_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_timecode.command(name="set")
@click.argument("timecode")
@dry_run_option
@click.pass_context
def timecode_set_cmd(ctx: click.Context, timecode: str, dry_run: bool) -> None:
    """タイムコード設定。"""
    result = timecode_set_impl(timecode=timecode, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="current-item")
@click.pass_context
def current_item_cmd(ctx: click.Context) -> None:
    """現在のビデオアイテム取得。"""
    result = current_item_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="duplicate")
@click.option("--name", default=None, help="Name for the duplicated timeline")
@json_input_option
@dry_run_option
@click.pass_context
def timeline_duplicate_cmd(
    ctx: click.Context,
    name: str | None,
    json_input: dict | None,
    dry_run: bool,
) -> None:
    """タイムライン複製。"""
    if json_input:
        data = TimelineDuplicateInput.model_validate(json_input)
        name = data.name
    result = timeline_duplicate_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="detect-scene-cuts")
@click.pass_context
def timeline_detect_scene_cuts_cmd(ctx: click.Context) -> None:
    """シーンカット検出。"""
    result = timeline_detect_scene_cuts_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="create-subtitles")
@click.pass_context
def timeline_create_subtitles_cmd(ctx: click.Context) -> None:
    """音声から字幕生成。"""
    result = timeline_create_subtitles_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.group(name="track")
def timeline_track() -> None:
    """Track operations."""


@timeline_track.command(name="list")
@click.pass_context
def track_list_cmd(ctx: click.Context) -> None:
    """トラック一覧。"""
    result = track_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_track.command(name="add")
@click.option("--track-type", required=True, help="Track type: video, audio, subtitle")
@click.option("--sub-track-type", default=None, help="Sub track type (e.g., mono, stereo)")
@json_input_option
@dry_run_option
@click.pass_context
def track_add_cmd(
    ctx: click.Context,
    track_type: str | None,
    sub_track_type: str | None,
    json_input: dict | None,
    dry_run: bool,
) -> None:
    """トラック追加。"""
    if json_input:
        data = TrackAddInput.model_validate(json_input)
        track_type = data.track_type
        sub_track_type = data.sub_track_type
    if not track_type:
        raise click.UsageError("--track-type or --json is required")
    result = track_add_impl(
        track_type=track_type, sub_track_type=sub_track_type, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_track.command(name="delete")
@click.option("--track-type", required=True, help="Track type: video, audio, subtitle")
@click.option("--index", required=True, type=int, help="Track index (1-based)")
@json_input_option
@dry_run_option
@click.pass_context
def track_delete_cmd(
    ctx: click.Context,
    track_type: str | None,
    index: int | None,
    json_input: dict | None,
    dry_run: bool,
) -> None:
    """トラック削除（破壊的操作）。"""
    if json_input:
        data = TrackDeleteInput.model_validate(json_input)
        track_type = data.track_type
        index = data.index
    if not track_type or index is None:
        raise click.UsageError("--track-type and --index (or --json) are required")
    result = track_delete_impl(
        track_type=track_type, index=index, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_track.command(name="enable")
@click.option("--track-type", required=True, help="Track type: video, audio, subtitle")
@click.option("--index", required=True, type=int, help="Track index (1-based)")
@click.option("--value", type=bool, default=None, help="Set enabled state (omit to get)")
@json_input_option
@click.pass_context
def track_enable_cmd(
    ctx: click.Context,
    track_type: str | None,
    index: int | None,
    value: bool | None,
    json_input: dict | None,
) -> None:
    """トラック有効/無効の取得・設定。"""
    if json_input:
        data = TrackEnableInput.model_validate(json_input)
        track_type = data.track_type
        index = data.index
        value = data.enabled
    if not track_type or index is None:
        raise click.UsageError("--track-type and --index (or --json) are required")
    result = track_enable_impl(track_type=track_type, index=index, enabled=value)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_track.command(name="lock")
@click.option("--track-type", required=True, help="Track type: video, audio, subtitle")
@click.option("--index", required=True, type=int, help="Track index (1-based)")
@click.option("--value", type=bool, default=None, help="Set locked state (omit to get)")
@json_input_option
@click.pass_context
def track_lock_cmd(
    ctx: click.Context,
    track_type: str | None,
    index: int | None,
    value: bool | None,
    json_input: dict | None,
) -> None:
    """トラックロック状態の取得・設定。"""
    if json_input:
        data = TrackLockInput.model_validate(json_input)
        track_type = data.track_type
        index = data.index
        value = data.locked
    if not track_type or index is None:
        raise click.UsageError("--track-type and --index (or --json) are required")
    result = track_lock_impl(track_type=track_type, index=index, locked=value)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.group(name="marker")
def timeline_marker() -> None:
    """Marker operations."""


@timeline_marker.command(name="list")
@click.option("--timeline", "timeline_name", default=None)
@click.pass_context
def marker_list_cmd(ctx: click.Context, timeline_name: str | None) -> None:
    """マーカー一覧。"""
    result = marker_list_impl(timeline_name=timeline_name)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_marker.command(name="add")
@json_input_option
@dry_run_option
@click.pass_context
def marker_add_cmd(
    ctx: click.Context, json_input: dict | None, dry_run: bool
) -> None:
    """マーカー追加。"""
    if not json_input:
        raise click.UsageError("--json is required")
    data = MarkerAddInput.model_validate(json_input)
    result = marker_add_impl(
        frame_id=data.frame_id,
        color=data.color,
        name=data.name,
        note=data.note,
        duration=data.duration,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_marker.command(name="delete")
@click.argument("frame_id", required=False, type=int)
@json_input_option
@dry_run_option
@click.pass_context
def marker_delete_cmd(
    ctx: click.Context, frame_id: int | None, json_input: dict | None, dry_run: bool
) -> None:
    """マーカー削除。"""
    if json_input:
        data = MarkerDeleteInput.model_validate(json_input)
        frame_id = data.frame_id
    if frame_id is None:
        raise click.UsageError(
            "FRAME_ID is required (positional argument or --json)"
        )
    result = marker_delete_impl(frame_id=frame_id, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


from davinci_cli.commands.beat_markers import beat_marker_cmd

timeline_marker.add_command(beat_marker_cmd)


# --- Schema Registration ---

register_schema("timeline.list", output_model=TimelineListItem)
register_schema("timeline.current", output_model=TimelineCurrentOutput)
register_schema(
    "timeline.switch",
    output_model=TimelineSwitchOutput,
    input_model=TimelineSwitchInput,
)
register_schema(
    "timeline.create",
    output_model=TimelineCreateOutput,
    input_model=TimelineCreateInput,
)
register_schema(
    "timeline.delete",
    output_model=TimelineDeleteOutput,
    input_model=TimelineDeleteInput,
)
register_schema(
    "timeline.export",
    output_model=TimelineExportOutput,
    input_model=TimelineExportInput,
)
register_schema("timeline.marker.list", output_model=MarkerInfo)
register_schema(
    "timeline.marker.add",
    output_model=MarkerAddOutput,
    input_model=MarkerAddInput,
)
register_schema(
    "timeline.marker.delete",
    output_model=MarkerDeleteOutput,
    input_model=MarkerDeleteInput,
)
register_schema("timeline.timecode.get", output_model=TimecodeGetOutput)
register_schema(
    "timeline.timecode.set",
    output_model=TimecodeSetOutput,
    input_model=TimecodeSetInput,
)
register_schema("timeline.current-item", output_model=CurrentItemOutput)
register_schema(
    "timeline.duplicate",
    output_model=TimelineDuplicateOutput,
    input_model=TimelineDuplicateInput,
)
register_schema("timeline.detect-scene-cuts", output_model=TimelineDetectSceneCutsOutput)
register_schema("timeline.create-subtitles", output_model=TimelineCreateSubtitlesOutput)
register_schema("timeline.track.list", output_model=TrackListItem)
register_schema(
    "timeline.track.add",
    output_model=TrackAddOutput,
    input_model=TrackAddInput,
)
register_schema(
    "timeline.track.delete",
    output_model=TrackDeleteOutput,
    input_model=TrackDeleteInput,
)
register_schema(
    "timeline.track.enable",
    output_model=TrackEnableOutput,
    input_model=TrackEnableInput,
)
register_schema(
    "timeline.track.lock",
    output_model=TrackLockOutput,
    input_model=TrackLockInput,
)
