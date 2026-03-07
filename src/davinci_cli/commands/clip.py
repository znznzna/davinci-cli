"""dr clip — クリップ操作コマンド。

共通デコレータ使用。Resolve接続は core.connection を使用。
"""

from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.decorators import dry_run_option, fields_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema

# --- Pydantic Models ---


class ClipInfo(BaseModel):
    index: int
    name: str
    start: int | str | None = None
    end: int | str | None = None
    duration: int | str | None = None
    type: str | None = None
    track: int | None = None


class ClipSelectOutput(BaseModel):
    selected: int
    name: str


class ClipPropertyGetOutput(BaseModel):
    index: int
    key: str
    value: str | None = None


class ClipPropertySetOutput(BaseModel):
    set: bool | None = None
    index: int | None = None
    key: str | None = None
    value: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class ClipPropertySetInput(BaseModel):
    index: int
    key: str
    value: str


# --- Helper ---


def _get_current_timeline() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise ProjectNotOpenError()
    tl = project.GetCurrentTimeline()
    if tl is None:
        raise ProjectNotOpenError()
    return tl


def _collect_clips(tl: Any) -> list[tuple[dict, Any]]:
    """タイムラインから全クリップを収集する。"""
    clips: list[tuple[dict, Any]] = []
    for track_type in ["video", "audio"]:
        track_count = tl.GetTrackCount(track_type)
        for track_idx in range(1, track_count + 1):
            track_clips = tl.GetItemListInTrack(track_type, track_idx) or []
            for clip_item in track_clips:
                info = {
                    "index": len(clips),
                    "name": clip_item.GetName(),
                    "start": clip_item.GetStart(),
                    "end": clip_item.GetEnd(),
                    "duration": clip_item.GetDuration(),
                    "type": track_type,
                    "track": track_idx,
                }
                clips.append((info, clip_item))
    return clips


# --- _impl Functions ---


def clip_list_impl(
    timeline_name: str | None = None,
    fields: list[str] | None = None,
) -> list[dict]:
    if timeline_name:
        resolve = get_resolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        if not project:
            raise ProjectNotOpenError()
        count = project.GetTimelineCount()
        tl = None
        for i in range(1, count + 1):
            t = project.GetTimelineByIndex(i)
            if t and t.GetName() == timeline_name:
                tl = t
                break
        if not tl:
            raise ValidationError(
                field="timeline",
                reason=f"Timeline not found: {timeline_name}",
            )
    else:
        tl = _get_current_timeline()

    clips = _collect_clips(tl)
    result = [info for info, _ in clips]
    if fields:
        result = [{k: v for k, v in c.items() if k in fields} for c in result]
    return result


def clip_info_impl(index: int, fields: list[str] | None = None) -> dict:
    tl = _get_current_timeline()
    clips = _collect_clips(tl)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="index",
            reason=f"Clip index {index} out of range (0..{len(clips) - 1})",
        )
    info = clips[index][0]
    if fields:
        info = {k: v for k, v in info.items() if k in fields}
    return info


def clip_select_impl(index: int) -> dict:
    tl = _get_current_timeline()
    clips = _collect_clips(tl)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="index",
            reason=f"Clip index {index} out of range",
        )
    return {"selected": index, "name": clips[index][0]["name"]}


def clip_property_get_impl(index: int, key: str) -> dict:
    tl = _get_current_timeline()
    clips = _collect_clips(tl)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="index",
            reason=f"Clip index {index} out of range",
        )
    _, clip_item = clips[index]
    value = clip_item.GetProperty(key)
    return {"index": index, "key": key, "value": value}


def clip_property_set_impl(
    index: int,
    key: str,
    value: str,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "property_set",
            "index": index,
            "key": key,
            "value": value,
        }
    tl = _get_current_timeline()
    clips = _collect_clips(tl)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="index",
            reason=f"Clip index {index} out of range",
        )
    _, clip_item = clips[index]
    result = clip_item.SetProperty(key, value)
    if result is False:
        raise ValidationError(
            field="key",
            reason=f"Failed to set property '{key}' to '{value}'",
        )
    return {"set": True, "index": index, "key": key, "value": value}


# --- CLI Commands ---


@click.group()
def clip() -> None:
    """Clip operations."""


@clip.command(name="list")
@click.option(
    "--timeline", default=None, help="Timeline name (default: current)"
)
@fields_option
@click.pass_context
def clip_list(
    ctx: click.Context,
    timeline: str | None,
    fields: list[str] | None,
) -> None:
    """クリップ一覧（NDJSON対応）。"""
    result = clip_list_impl(timeline_name=timeline, fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@clip.command(name="info")
@click.argument("index", type=int)
@fields_option
@click.pass_context
def clip_info(
    ctx: click.Context, index: int, fields: list[str] | None
) -> None:
    """クリップ詳細。"""
    result = clip_info_impl(index=index, fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@clip.command(name="select")
@click.argument("index", type=int)
@click.pass_context
def clip_select(ctx: click.Context, index: int) -> None:
    """クリップ選択。"""
    result = clip_select_impl(index=index)
    output(result, pretty=ctx.obj.get("pretty"))


@clip.group(name="property")
def clip_property() -> None:
    """Clip property operations."""


@clip_property.command(name="get")
@click.argument("index", type=int)
@click.argument("key")
@click.pass_context
def property_get(ctx: click.Context, index: int, key: str) -> None:
    """プロパティ取得。"""
    result = clip_property_get_impl(index=index, key=key)
    output(result, pretty=ctx.obj.get("pretty"))


@clip_property.command(name="set")
@click.argument("index", type=int)
@click.argument("key")
@click.argument("value")
@dry_run_option
@click.pass_context
def property_set(
    ctx: click.Context,
    index: int,
    key: str,
    value: str,
    dry_run: bool,
) -> None:
    """プロパティ設定。"""
    result = clip_property_set_impl(
        index=index, key=key, value=value, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("clip.list", output_model=ClipInfo)
register_schema("clip.info", output_model=ClipInfo)
register_schema("clip.select", output_model=ClipSelectOutput)
register_schema("clip.property.get", output_model=ClipPropertyGetOutput)
register_schema(
    "clip.property.set",
    output_model=ClipPropertySetOutput,
    input_model=ClipPropertySetInput,
)
