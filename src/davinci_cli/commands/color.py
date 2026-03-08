"""dr color — カラーグレーディングコマンド。

パス検証は core/validation.py の validate_path() を使用する。
allowed_extensions で LUT ファイルの拡張子を制限する。
"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.core.validation import validate_path
from davinci_cli.decorators import dry_run_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema

# LUT 許可拡張子
_LUT_EXTENSIONS = [".cube", ".3dl", ".lut", ".mga", ".m3d"]


# --- Pydantic Models ---


class LutApplyInput(BaseModel):
    clip_index: int
    lut_path: str


class LutApplyOutput(BaseModel):
    applied: str | None = None
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None
    lut_path: str | None = None


class ColorResetOutput(BaseModel):
    reset: bool | None = None
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None


class ColorCopyGradeOutput(BaseModel):
    copied_from: int
    copied_to: int | None = None
    dry_run: bool | None = None
    action: str | None = None


class NodeInfo(BaseModel):
    index: int
    label: str | None = None


class StillInfo(BaseModel):
    index: int
    label: str | None = None


class StillGrabOutput(BaseModel):
    grabbed: bool | None = None
    clip_index: int | None = None
    dry_run: bool | None = None
    action: str | None = None


class VersionListInput(BaseModel):
    clip_index: int
    version_type: int = 0


class VersionListOutput(BaseModel):
    name: str
    version_type: int


class VersionCurrentOutput(BaseModel):
    versionName: str
    versionType: int


class VersionAddInput(BaseModel):
    clip_index: int
    name: str
    version_type: int = 0


class VersionAddOutput(BaseModel):
    added: bool | None = None
    name: str
    version_type: int
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None


# --- Helper ---


def _get_clip_item_by_index(tl: Any, index: int) -> Any:
    clips: list[Any] = []
    for track_type in ["video", "audio"]:
        track_count = tl.GetTrackCount(track_type)
        for track_idx in range(1, track_count + 1):
            track_clips = tl.GetItemListInTrack(track_type, track_idx) or []
            clips.extend(track_clips)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="clip_index",
            reason=f"Clip index {index} out of range (0..{len(clips) - 1})",
        )
    return clips[index]


def _get_current_timeline() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    return tl


# --- _impl Functions ---


def color_apply_lut_impl(
    clip_index: int,
    lut_path: str,
    dry_run: bool = False,
) -> dict:
    validated = validate_path(lut_path, allowed_extensions=_LUT_EXTENSIONS)
    if not validated.exists():
        raise ValidationError(
            field="lut_path",
            reason=f"LUT file not found: {lut_path}",
        )
    if dry_run:
        return {
            "dry_run": True,
            "action": "apply_lut",
            "clip_index": clip_index,
            "lut_path": str(validated),
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    result = clip_item.SetLUT(1, str(validated))
    if result is False:
        raise ValidationError(
            field="lut_path",
            reason=f"Failed to apply LUT: {lut_path}",
        )
    return {"applied": str(validated), "clip_index": clip_index}


def color_reset_impl(clip_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "reset", "clip_index": clip_index}
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    clip_item.ResetAllNodeColors()
    return {"reset": True, "clip_index": clip_index}


def color_copy_grade_impl(
    from_index: int,
    to_index: int,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "copy_grade",
            "from_index": from_index,
            "to_index": to_index,
        }
    tl = _get_current_timeline()
    src_clip = _get_clip_item_by_index(tl, from_index)
    tgt_clip = _get_clip_item_by_index(tl, to_index)
    result = src_clip.CopyGrades([tgt_clip])
    if result is False:
        raise ValidationError(
            field="copy_grade",
            reason="CopyGrades failed",
        )
    return {"copied_from": from_index, "copied_to": to_index}


def node_list_impl(clip_index: int) -> list[dict]:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    node_count = clip_item.GetNumNodes()
    result: list[dict] = []
    for i in range(1, node_count + 1):
        label = clip_item.GetNodeLabel(i)
        result.append({"index": i, "label": label or f"Node {i}"})
    return result


def still_grab_impl(clip_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "still_grab",
            "clip_index": clip_index,
        }
    tl = _get_current_timeline()
    _get_clip_item_by_index(tl, clip_index)  # validate index exists
    tl.GrabStill()
    return {"grabbed": True, "clip_index": clip_index}


def color_version_list_impl(
    clip_index: int, version_type: int = 0
) -> list[dict]:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    names = clip_item.GetVersionNameList(version_type) or []
    return [{"name": n, "version_type": version_type} for n in names]


def color_version_current_impl(clip_index: int) -> dict:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    return clip_item.GetCurrentVersion()


def color_version_add_impl(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "version_add",
            "name": name,
            "version_type": version_type,
            "clip_index": clip_index,
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    result = clip_item.AddVersion(name, version_type)
    if result is False:
        raise ValidationError(
            field="name",
            reason=f"Failed to add version: {name}",
        )
    return {
        "added": True,
        "name": name,
        "version_type": version_type,
        "clip_index": clip_index,
    }


def still_list_impl() -> list[dict]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    gallery = project.GetGallery()
    if not gallery:
        return []
    album = gallery.GetCurrentStillAlbum()
    if not album:
        return []
    stills = album.GetStills() or []
    result: list[dict] = []
    for i, s in enumerate(stills):
        label_fn = getattr(s, "GetLabel", None)
        label = label_fn() if label_fn else f"Still {i}"
        result.append({"index": i, "label": label})
    return result


# --- CLI Commands ---


@click.group()
def color() -> None:
    """Color grading operations."""


@color.command(name="apply-lut")
@click.argument("clip_index", type=int)
@click.argument("lut_path")
@dry_run_option
@click.pass_context
def apply_lut(
    ctx: click.Context, clip_index: int, lut_path: str, dry_run: bool
) -> None:
    """LUT をクリップに適用する。"""
    result = color_apply_lut_impl(
        clip_index=clip_index, lut_path=lut_path, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="reset")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def color_reset(
    ctx: click.Context, clip_index: int, dry_run: bool
) -> None:
    """グレードをリセットする。"""
    result = color_reset_impl(clip_index=clip_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="copy-grade")
@click.option("--from", "from_index", type=int, required=True)
@click.option("--to", "to_index", type=int, required=True)
@dry_run_option
@click.pass_context
def copy_grade(
    ctx: click.Context, from_index: int, to_index: int, dry_run: bool
) -> None:
    """グレードをコピーする。"""
    result = color_copy_grade_impl(
        from_index=from_index, to_index=to_index, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color.group(name="node")
def color_node() -> None:
    """Node operations."""


@color_node.command(name="list")
@click.argument("clip_index", type=int)
@click.pass_context
def node_list_cmd(ctx: click.Context, clip_index: int) -> None:
    """ノード一覧。"""
    result = node_list_impl(clip_index=clip_index)
    output(result, pretty=ctx.obj.get("pretty"))


@color.group(name="still")
def color_still() -> None:
    """Still operations."""


@color_still.command(name="grab")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def still_grab_cmd(
    ctx: click.Context, clip_index: int, dry_run: bool
) -> None:
    """スチルを取得する。"""
    result = still_grab_impl(clip_index=clip_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color_still.command(name="list")
@click.pass_context
def still_list_cmd(ctx: click.Context) -> None:
    """スチル一覧。"""
    result = still_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@color.group(name="version")
def color_version() -> None:
    """Version operations."""


@color_version.command(name="list")
@click.argument("clip_index", type=int)
@click.option("--version-type", type=int, default=0, help="0=local, 1=remote")
@click.pass_context
def version_list_cmd(
    ctx: click.Context, clip_index: int, version_type: int
) -> None:
    """バージョン一覧。"""
    result = color_version_list_impl(
        clip_index=clip_index, version_type=version_type
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color_version.command(name="current")
@click.argument("clip_index", type=int)
@click.pass_context
def version_current_cmd(ctx: click.Context, clip_index: int) -> None:
    """現在のバージョンを取得する。"""
    result = color_version_current_impl(clip_index=clip_index)
    output(result, pretty=ctx.obj.get("pretty"))


@color_version.command(name="add")
@click.argument("clip_index", type=int)
@click.argument("name")
@click.option("--version-type", type=int, default=0, help="0=local, 1=remote")
@dry_run_option
@click.pass_context
def version_add_cmd(
    ctx: click.Context,
    clip_index: int,
    name: str,
    version_type: int,
    dry_run: bool,
) -> None:
    """バージョンを追加する。"""
    result = color_version_add_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema(
    "color.apply-lut",
    output_model=LutApplyOutput,
    input_model=LutApplyInput,
)
register_schema("color.reset", output_model=ColorResetOutput)
register_schema("color.copy-grade", output_model=ColorCopyGradeOutput)
register_schema("color.node.list", output_model=NodeInfo)
register_schema("color.still.list", output_model=StillInfo)
register_schema("color.still.grab", output_model=StillGrabOutput)
register_schema(
    "color.version.list",
    output_model=VersionListOutput,
    input_model=VersionListInput,
)
register_schema("color.version.current", output_model=VersionCurrentOutput)
register_schema(
    "color.version.add",
    output_model=VersionAddOutput,
    input_model=VersionAddInput,
)
