"""dr gallery — ギャラリー・スチルアルバム管理コマンド。"""

from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.commands.color import (
    StillGrabOutput,
    StillInfo,
    still_grab_impl,
    still_list_impl,
)
from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.core.validation import validate_path
from davinci_cli.decorators import dry_run_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema

# --- Pydantic Models ---


class AlbumInfo(BaseModel):
    index: int
    name: str


class AlbumCurrentOutput(BaseModel):
    name: str | None = None


class AlbumSetInput(BaseModel):
    name: str


class AlbumSetOutput(BaseModel):
    set: bool | None = None
    name: str
    dry_run: bool | None = None
    action: str | None = None


class AlbumCreateOutput(BaseModel):
    created: bool | None = None
    name: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class StillExportInput(BaseModel):
    folder_path: str
    file_prefix: str = "still"
    format: str = "dpx"


class StillExportOutput(BaseModel):
    exported: int | None = None
    folder_path: str | None = None
    format: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class StillImportInput(BaseModel):
    paths: list[str]


class StillImportOutput(BaseModel):
    imported: bool | None = None
    paths: list[str] | None = None
    dry_run: bool | None = None
    action: str | None = None


class StillDeleteInput(BaseModel):
    still_indices: list[int]


class StillDeleteOutput(BaseModel):
    deleted: int | None = None
    still_indices: list[int] | None = None
    dry_run: bool | None = None
    action: str | None = None


# --- Helper ---


def _get_gallery() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    gallery = project.GetGallery()
    if not gallery:
        raise ValidationError(field="gallery", reason="Gallery not available")
    return gallery


def _get_current_album() -> tuple[Any, Any]:
    """Returns (gallery, album) tuple."""
    gallery = _get_gallery()
    album = gallery.GetCurrentStillAlbum()
    if not album:
        raise ValidationError(field="album", reason="No current still album")
    return gallery, album


# --- _impl Functions ---


def gallery_album_list_impl() -> list[dict[str, Any]]:
    gallery = _get_gallery()
    albums = gallery.GetGalleryStillAlbums() or []
    result = []
    for i, album in enumerate(albums):
        name = gallery.GetAlbumName(album)
        result.append({"index": i, "name": name or f"Album {i}"})
    return result


def gallery_album_current_impl() -> dict[str, Any]:
    gallery = _get_gallery()
    album = gallery.GetCurrentStillAlbum()
    if not album:
        return {"name": None}
    name = gallery.GetAlbumName(album)
    return {"name": name}


def gallery_album_set_impl(name: str, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "action": "album_set", "name": name}
    gallery = _get_gallery()
    albums = gallery.GetGalleryStillAlbums() or []
    for album in albums:
        if gallery.GetAlbumName(album) == name:
            result = gallery.SetCurrentStillAlbum(album)
            if result is False:
                raise ValidationError(field="name", reason=f"Failed to set album: {name}")
            return {"set": True, "name": name}
    raise ValidationError(field="name", reason=f"Album not found: {name}")


def gallery_album_create_impl(dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "action": "album_create"}
    gallery = _get_gallery()
    album = gallery.CreateGalleryStillAlbum()
    if not album:
        raise ValidationError(field="album", reason="Failed to create album")
    name = gallery.GetAlbumName(album)
    return {"created": True, "name": name}


def gallery_still_export_impl(
    folder_path: str,
    file_prefix: str = "still",
    format: str = "dpx",
    dry_run: bool = False,
) -> dict[str, Any]:
    validated = validate_path(folder_path)
    if dry_run:
        return {
            "dry_run": True,
            "action": "still_export",
            "folder_path": str(validated),
            "format": format,
        }
    _gallery, album = _get_current_album()
    stills = album.GetStills() or []
    if not stills:
        return {"exported": 0, "folder_path": str(validated)}
    result = album.ExportStills(stills, str(validated), file_prefix, format)
    if result is False:
        raise ValidationError(field="folder_path", reason="Failed to export stills")
    return {"exported": len(stills), "folder_path": str(validated), "format": format}


def gallery_still_import_impl(
    paths: list[str],
    dry_run: bool = False,
) -> dict[str, Any]:
    validated_paths = [str(validate_path(p)) for p in paths]
    if dry_run:
        return {"dry_run": True, "action": "still_import", "paths": validated_paths}
    _gallery, album = _get_current_album()
    result = album.ImportStills(validated_paths)
    if result is False:
        raise ValidationError(field="paths", reason="Failed to import stills")
    return {"imported": True, "paths": validated_paths}


def gallery_still_delete_impl(
    still_indices: list[int],
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "action": "still_delete",
            "still_indices": still_indices,
        }
    _gallery, album = _get_current_album()
    stills = album.GetStills() or []
    targets = []
    for idx in still_indices:
        if idx < 0 or idx >= len(stills):
            raise ValidationError(
                field="still_indices",
                reason=f"Still index {idx} out of range (0..{len(stills) - 1})",
            )
        targets.append(stills[idx])
    result = album.DeleteStills(targets)
    if result is False:
        raise ValidationError(field="still_indices", reason="Failed to delete stills")
    return {"deleted": len(targets), "still_indices": still_indices}


# --- CLI Commands ---


@click.group()
def gallery() -> None:
    """Gallery and still operations."""


@gallery.group(name="album")
def gallery_album() -> None:
    """Album operations."""


@gallery_album.command(name="list")
@click.pass_context
def album_list_cmd(ctx: click.Context) -> None:
    """アルバム一覧。"""
    result = gallery_album_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@gallery_album.command(name="current")
@click.pass_context
def album_current_cmd(ctx: click.Context) -> None:
    """現在のアルバムを取得する。"""
    result = gallery_album_current_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@gallery_album.command(name="set")
@click.argument("name")
@dry_run_option
@click.pass_context
def album_set_cmd(ctx: click.Context, name: str, dry_run: bool) -> None:
    """アルバムを切り替える。"""
    result = gallery_album_set_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@gallery_album.command(name="create")
@dry_run_option
@click.pass_context
def album_create_cmd(ctx: click.Context, dry_run: bool) -> None:
    """アルバムを作成する。"""
    result = gallery_album_create_impl(dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@gallery.group(name="still")
def gallery_still() -> None:
    """Still operations."""


@gallery_still.command(name="export")
@click.argument("folder_path")
@click.option("--file-prefix", default="still", help="File name prefix.")
@click.option(
    "--format",
    "fmt",
    default="dpx",
    help="Export format (dpx, cin, tif, jpg, png, ppm, bmp, xpm, drx).",
)
@dry_run_option
@click.pass_context
def still_export_cmd(
    ctx: click.Context,
    folder_path: str,
    file_prefix: str,
    fmt: str,
    dry_run: bool,
) -> None:
    """スチルをエクスポートする。"""
    result = gallery_still_export_impl(
        folder_path=folder_path, file_prefix=file_prefix, format=fmt, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@gallery_still.command(name="import")
@click.argument("paths", nargs=-1, required=True)
@dry_run_option
@click.pass_context
def still_import_cmd(ctx: click.Context, paths: tuple[str, ...], dry_run: bool) -> None:
    """スチルをインポートする。"""
    result = gallery_still_import_impl(paths=list(paths), dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@gallery_still.command(name="delete")
@click.argument("still_indices", nargs=-1, required=True, type=int)
@dry_run_option
@click.pass_context
def still_delete_cmd(ctx: click.Context, still_indices: tuple[int, ...], dry_run: bool) -> None:
    """スチルを削除する。"""
    result = gallery_still_delete_impl(still_indices=list(still_indices), dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@gallery_still.command(name="list")
@click.pass_context
def gallery_still_list_cmd(ctx: click.Context) -> None:
    """スチル一覧。"""
    result = still_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@gallery_still.command(name="grab")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def gallery_still_grab_cmd(ctx: click.Context, clip_index: int, dry_run: bool) -> None:
    """スチルを取得する。"""
    result = still_grab_impl(clip_index=clip_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("gallery.album.list", output_model=AlbumInfo)
register_schema("gallery.album.current", output_model=AlbumCurrentOutput)
register_schema(
    "gallery.album.set",
    output_model=AlbumSetOutput,
    input_model=AlbumSetInput,
)
register_schema("gallery.album.create", output_model=AlbumCreateOutput)
register_schema(
    "gallery.still.export",
    output_model=StillExportOutput,
    input_model=StillExportInput,
)
register_schema(
    "gallery.still.import",
    output_model=StillImportOutput,
    input_model=StillImportInput,
)
register_schema(
    "gallery.still.delete",
    output_model=StillDeleteOutput,
    input_model=StillDeleteInput,
)
register_schema("gallery.still.list", output_model=StillInfo)
register_schema("gallery.still.grab", output_model=StillGrabOutput)
