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


class VersionLoadInput(BaseModel):
    clip_index: int
    name: str
    version_type: int = 0


class VersionLoadOutput(BaseModel):
    loaded: bool | None = None
    name: str
    version_type: int
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None


class VersionDeleteInput(BaseModel):
    clip_index: int
    name: str
    version_type: int = 0


class VersionDeleteOutput(BaseModel):
    deleted: bool | None = None
    name: str
    version_type: int
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None


class VersionRenameInput(BaseModel):
    clip_index: int
    old_name: str
    new_name: str
    version_type: int = 0


class VersionRenameOutput(BaseModel):
    renamed: bool | None = None
    old_name: str
    new_name: str
    version_type: int
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None


class CdlSetInput(BaseModel):
    clip_index: int
    node_index: int
    slope: str
    offset: str
    power: str
    saturation: str


class CdlSetOutput(BaseModel):
    set: bool | None = None
    clip_index: int
    node_index: int
    dry_run: bool | None = None
    action: str | None = None


class LutExportInput(BaseModel):
    clip_index: int
    export_type: int
    path: str


class LutExportOutput(BaseModel):
    exported: bool | None = None
    clip_index: int
    path: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class ResetAllOutput(BaseModel):
    reset: bool | None = None
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None


class NodeLutSetInput(BaseModel):
    clip_index: int
    node_index: int
    lut_path: str


class NodeLutSetOutput(BaseModel):
    set: bool | None = None
    clip_index: int
    node_index: int
    lut_path: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class NodeLutGetInput(BaseModel):
    clip_index: int
    node_index: int


class NodeLutGetOutput(BaseModel):
    lut_path: str | None = None
    clip_index: int
    node_index: int


class NodeEnableInput(BaseModel):
    clip_index: int
    node_index: int
    enabled: bool


class NodeEnableOutput(BaseModel):
    set: bool | None = None
    clip_index: int
    node_index: int
    enabled: bool | None = None
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


def _get_node_graph(tl: Any, clip_index: int) -> Any:
    clip_item = _get_clip_item_by_index(tl, clip_index)
    graph = clip_item.GetNodeGraph()
    if not graph:
        raise ValidationError(field="graph", reason="Failed to get node graph for clip")
    return graph


# --- _impl Functions ---


def color_apply_lut_impl(
    clip_index: int,
    lut_path: str,
    dry_run: bool = False,
) -> dict[str, Any]:
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


def color_reset_impl(clip_index: int, dry_run: bool = False) -> dict[str, Any]:
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
) -> dict[str, Any]:
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


def node_list_impl(clip_index: int) -> list[dict[str, Any]]:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    node_count = clip_item.GetNumNodes()
    result: list[dict[str, Any]] = []
    for i in range(1, node_count + 1):
        label = clip_item.GetNodeLabel(i)
        result.append({"index": i, "label": label or f"Node {i}"})
    return result


def still_grab_impl(clip_index: int, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "action": "still_grab",
            "clip_index": clip_index,
        }
    tl = _get_current_timeline()
    _get_clip_item_by_index(tl, clip_index)  # validate index exists
    result = tl.GrabStill()
    if not result:
        raise ValidationError(
            field="clip_index",
            reason=f"GrabStill failed for clip at index {clip_index}. "
            "Ensure the Color page is active.",
        )
    return {"grabbed": True, "clip_index": clip_index}


def color_version_list_impl(clip_index: int, version_type: int = 0) -> list[dict[str, Any]]:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    names = clip_item.GetVersionNameList(version_type) or []
    return [{"name": n, "version_type": version_type} for n in names]


def color_version_current_impl(clip_index: int) -> dict[str, Any]:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    result: dict[str, Any] = clip_item.GetCurrentVersion()
    return result


def color_version_add_impl(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
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


def color_version_load_impl(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "action": "version_load",
            "name": name,
            "version_type": version_type,
            "clip_index": clip_index,
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    result = clip_item.LoadVersionByName(name, version_type)
    if result is False:
        raise ValidationError(
            field="name",
            reason=f"Failed to load version: {name}",
        )
    return {
        "loaded": True,
        "name": name,
        "version_type": version_type,
        "clip_index": clip_index,
    }


def color_version_delete_impl(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "action": "version_delete",
            "name": name,
            "version_type": version_type,
            "clip_index": clip_index,
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    result = clip_item.DeleteVersionByName(name, version_type)
    if result is False:
        raise ValidationError(
            field="name",
            reason=f"Failed to delete version: {name}",
        )
    return {
        "deleted": True,
        "name": name,
        "version_type": version_type,
        "clip_index": clip_index,
    }


def color_version_rename_impl(
    clip_index: int,
    old_name: str,
    new_name: str,
    version_type: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "action": "version_rename",
            "old_name": old_name,
            "new_name": new_name,
            "version_type": version_type,
            "clip_index": clip_index,
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    result = clip_item.RenameVersionByName(old_name, new_name, version_type)
    if result is False:
        raise ValidationError(
            field="old_name",
            reason=f"Failed to rename version: {old_name}",
        )
    return {
        "renamed": True,
        "old_name": old_name,
        "new_name": new_name,
        "version_type": version_type,
        "clip_index": clip_index,
    }


def still_list_impl() -> list[dict[str, Any]]:
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
    result: list[dict[str, Any]] = []
    for i, s in enumerate(stills):
        label_fn = getattr(s, "GetLabel", None)
        label = label_fn() if label_fn else f"Still {i}"
        result.append({"index": i, "label": label})
    return result


def color_cdl_set_impl(
    clip_index: int,
    node_index: int,
    slope: str,
    offset: str,
    power: str,
    saturation: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "action": "cdl_set",
            "clip_index": clip_index,
            "node_index": node_index,
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    cdl_map = {
        "NodeIndex": str(node_index),
        "Slope": slope,
        "Offset": offset,
        "Power": power,
        "Saturation": saturation,
    }
    result = clip_item.SetCDL(cdl_map)
    if result is False:
        raise ValidationError(field="cdl", reason="Failed to set CDL values")
    return {"set": True, "clip_index": clip_index, "node_index": node_index}


def color_lut_export_impl(
    clip_index: int,
    export_type: int,
    path: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    validated = validate_path(path)
    if dry_run:
        return {
            "dry_run": True,
            "action": "lut_export",
            "clip_index": clip_index,
            "path": str(validated),
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    result = clip_item.ExportLUT(export_type, str(validated))
    if result is False:
        raise ValidationError(field="path", reason=f"Failed to export LUT to: {path}")
    return {"exported": True, "clip_index": clip_index, "path": str(validated)}


def color_reset_all_impl(clip_index: int, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "action": "reset_all", "clip_index": clip_index}
    tl = _get_current_timeline()
    graph = _get_node_graph(tl, clip_index)
    result = graph.ResetAllGrades()
    if result is False:
        raise ValidationError(field="reset_all", reason="Failed to reset all grades")
    return {"reset": True, "clip_index": clip_index}


def node_lut_set_impl(
    clip_index: int,
    node_index: int,
    lut_path: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    validated = validate_path(lut_path, allowed_extensions=_LUT_EXTENSIONS)
    if not validated.exists():
        raise ValidationError(
            field="lut_path",
            reason=f"LUT file not found: {lut_path}",
        )
    if dry_run:
        return {
            "dry_run": True,
            "action": "node_lut_set",
            "clip_index": clip_index,
            "node_index": node_index,
            "lut_path": str(validated),
        }
    tl = _get_current_timeline()
    graph = _get_node_graph(tl, clip_index)
    result = graph.SetLUT(node_index, str(validated))
    if result is False:
        raise ValidationError(
            field="lut_path",
            reason=f"Failed to set LUT on node {node_index}",
        )
    return {
        "set": True,
        "clip_index": clip_index,
        "node_index": node_index,
        "lut_path": str(validated),
    }


def node_lut_get_impl(clip_index: int, node_index: int) -> dict[str, Any]:
    tl = _get_current_timeline()
    graph = _get_node_graph(tl, clip_index)
    lut_path = graph.GetLUT(node_index)
    return {
        "lut_path": lut_path or None,
        "clip_index": clip_index,
        "node_index": node_index,
    }


def node_enable_impl(
    clip_index: int,
    node_index: int,
    enabled: bool,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "action": "node_enable",
            "clip_index": clip_index,
            "node_index": node_index,
            "enabled": enabled,
        }
    tl = _get_current_timeline()
    graph = _get_node_graph(tl, clip_index)
    result = graph.SetNodeEnabled(node_index, enabled)
    if result is False:
        raise ValidationError(
            field="node_index",
            reason=f"Failed to set node {node_index} enabled={enabled}",
        )
    return {
        "set": True,
        "clip_index": clip_index,
        "node_index": node_index,
        "enabled": enabled,
    }


# --- CLI Commands ---


@click.group()
def color() -> None:
    """Color grading operations."""


@color.command(name="apply-lut")
@click.argument("clip_index", type=int)
@click.argument("lut_path")
@dry_run_option
@click.pass_context
def apply_lut(ctx: click.Context, clip_index: int, lut_path: str, dry_run: bool) -> None:
    """LUT をクリップに適用する。"""
    result = color_apply_lut_impl(clip_index=clip_index, lut_path=lut_path, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="reset")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def color_reset(ctx: click.Context, clip_index: int, dry_run: bool) -> None:
    """グレードをリセットする。"""
    result = color_reset_impl(clip_index=clip_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="copy-grade")
@click.option("--from", "from_index", type=int, required=True)
@click.option("--to", "to_index", type=int, required=True)
@dry_run_option
@click.pass_context
def copy_grade(ctx: click.Context, from_index: int, to_index: int, dry_run: bool) -> None:
    """グレードをコピーする。"""
    result = color_copy_grade_impl(from_index=from_index, to_index=to_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="cdl")
@click.argument("clip_index", type=int)
@click.option("--node-index", type=int, required=True, help="ノードインデックス")
@click.option("--slope", type=str, required=True, help="Slope (e.g. '0.5 0.4 0.2')")
@click.option("--offset", type=str, required=True, help="Offset (e.g. '0.4 0.3 0.2')")
@click.option("--power", type=str, required=True, help="Power (e.g. '0.6 0.7 0.8')")
@click.option("--saturation", type=str, required=True, help="Saturation (e.g. '0.65')")
@dry_run_option
@click.pass_context
def cdl_cmd(
    ctx: click.Context,
    clip_index: int,
    node_index: int,
    slope: str,
    offset: str,
    power: str,
    saturation: str,
    dry_run: bool,
) -> None:
    """CDL 値を設定する。"""
    result = color_cdl_set_impl(
        clip_index=clip_index,
        node_index=node_index,
        slope=slope,
        offset=offset,
        power=power,
        saturation=saturation,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="lut-export")
@click.argument("clip_index", type=int)
@click.option("--export-type", type=int, required=True, help="LUT export type (enum)")
@click.option("--path", type=str, required=True, help="出力先パス")
@dry_run_option
@click.pass_context
def lut_export_cmd(
    ctx: click.Context,
    clip_index: int,
    export_type: int,
    path: str,
    dry_run: bool,
) -> None:
    """LUT をエクスポートする。"""
    result = color_lut_export_impl(
        clip_index=clip_index,
        export_type=export_type,
        path=path,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="reset-all")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def reset_all_cmd(ctx: click.Context, clip_index: int, dry_run: bool) -> None:
    """全グレードをリセットする（Graph.ResetAllGrades）。"""
    result = color_reset_all_impl(clip_index=clip_index, dry_run=dry_run)
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


@color_node.group(name="lut")
def node_lut() -> None:
    """Node LUT operations."""


@node_lut.command(name="set")
@click.argument("clip_index", type=int)
@click.argument("node_index", type=int)
@click.argument("lut_path")
@dry_run_option
@click.pass_context
def node_lut_set_cmd(
    ctx: click.Context,
    clip_index: int,
    node_index: int,
    lut_path: str,
    dry_run: bool,
) -> None:
    """ノードに LUT を設定する。"""
    result = node_lut_set_impl(
        clip_index=clip_index,
        node_index=node_index,
        lut_path=lut_path,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@node_lut.command(name="get")
@click.argument("clip_index", type=int)
@click.argument("node_index", type=int)
@click.pass_context
def node_lut_get_cmd(ctx: click.Context, clip_index: int, node_index: int) -> None:
    """ノードの LUT を取得する。"""
    result = node_lut_get_impl(clip_index=clip_index, node_index=node_index)
    output(result, pretty=ctx.obj.get("pretty"))


@color_node.command(name="enable")
@click.argument("clip_index", type=int)
@click.argument("node_index", type=int)
@click.argument("enabled", type=bool)
@dry_run_option
@click.pass_context
def node_enable_cmd(
    ctx: click.Context,
    clip_index: int,
    node_index: int,
    enabled: bool,
    dry_run: bool,
) -> None:
    """ノードの有効/無効を切り替える。"""
    result = node_enable_impl(
        clip_index=clip_index,
        node_index=node_index,
        enabled=enabled,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color.group(name="still")
def color_still() -> None:
    """Still operations."""


@color_still.command(name="grab")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def still_grab_cmd(ctx: click.Context, clip_index: int, dry_run: bool) -> None:
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
def version_list_cmd(ctx: click.Context, clip_index: int, version_type: int) -> None:
    """バージョン一覧。"""
    result = color_version_list_impl(clip_index=clip_index, version_type=version_type)
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


@color_version.command(name="load")
@click.argument("clip_index", type=int)
@click.argument("name")
@click.option("--version-type", type=int, default=0, help="0=local, 1=remote")
@dry_run_option
@click.pass_context
def version_load_cmd(
    ctx: click.Context,
    clip_index: int,
    name: str,
    version_type: int,
    dry_run: bool,
) -> None:
    """バージョンをロードする。"""
    result = color_version_load_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color_version.command(name="delete")
@click.argument("clip_index", type=int)
@click.argument("name")
@click.option("--version-type", type=int, default=0, help="0=local, 1=remote")
@dry_run_option
@click.pass_context
def version_delete_cmd(
    ctx: click.Context,
    clip_index: int,
    name: str,
    version_type: int,
    dry_run: bool,
) -> None:
    """バージョンを削除する。"""
    result = color_version_delete_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color_version.command(name="rename")
@click.argument("clip_index", type=int)
@click.argument("old_name")
@click.argument("new_name")
@click.option("--version-type", type=int, default=0, help="0=local, 1=remote")
@dry_run_option
@click.pass_context
def version_rename_cmd(
    ctx: click.Context,
    clip_index: int,
    old_name: str,
    new_name: str,
    version_type: int,
    dry_run: bool,
) -> None:
    """バージョンをリネームする。"""
    result = color_version_rename_impl(
        clip_index=clip_index,
        old_name=old_name,
        new_name=new_name,
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
register_schema(
    "color.version.load",
    output_model=VersionLoadOutput,
    input_model=VersionLoadInput,
)
register_schema(
    "color.version.delete",
    output_model=VersionDeleteOutput,
    input_model=VersionDeleteInput,
)
register_schema(
    "color.version.rename",
    output_model=VersionRenameOutput,
    input_model=VersionRenameInput,
)
register_schema(
    "color.cdl",
    output_model=CdlSetOutput,
    input_model=CdlSetInput,
)
register_schema(
    "color.lut-export",
    output_model=LutExportOutput,
    input_model=LutExportInput,
)
register_schema("color.reset-all", output_model=ResetAllOutput)
register_schema(
    "color.node.lut.set",
    output_model=NodeLutSetOutput,
    input_model=NodeLutSetInput,
)
register_schema(
    "color.node.lut.get",
    output_model=NodeLutGetOutput,
    input_model=NodeLutGetInput,
)
register_schema(
    "color.node.enable",
    output_model=NodeEnableOutput,
    input_model=NodeEnableInput,
)
