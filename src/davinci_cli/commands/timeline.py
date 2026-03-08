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


class CurrentItemOutput(BaseModel):
    name: str | None = None


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
    markers = tl.GetMarkers() or {}
    return [
        {
            "frame_id": frame_id,
            "color": info.get("color", ""),
            "name": info.get("name", ""),
            "note": info.get("note", ""),
            "duration": info.get("duration", 1),
        }
        for frame_id, info in markers.items()
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
    tl.AddMarker(frame_id, color, name, note or "", duration)
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
    tl.DeleteMarkerAtFrame(frame_id)
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


def current_item_impl() -> dict:
    tl = _get_current_timeline()
    item = tl.GetCurrentVideoItem()
    if not item:
        return {"name": None}
    return {"name": item.GetName()}


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
@click.argument("frame_id", type=int)
@dry_run_option
@click.pass_context
def marker_delete_cmd(
    ctx: click.Context, frame_id: int, dry_run: bool
) -> None:
    """マーカー削除。"""
    result = marker_delete_impl(frame_id=frame_id, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


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
register_schema("timeline.marker.delete", output_model=MarkerDeleteOutput)
register_schema("timeline.timecode.get", output_model=TimecodeGetOutput)
register_schema(
    "timeline.timecode.set",
    output_model=TimecodeSetOutput,
    input_model=TimecodeSetInput,
)
register_schema("timeline.current-item", output_model=CurrentItemOutput)
