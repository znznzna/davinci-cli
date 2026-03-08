"""dr gallery — ギャラリー・スチルアルバム管理コマンド。"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
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


# --- _impl Functions ---


def gallery_album_list_impl() -> list[dict]:
    gallery = _get_gallery()
    albums = gallery.GetGalleryStillAlbums() or []
    result = []
    for i, album in enumerate(albums):
        name = gallery.GetAlbumName(album)
        result.append({"index": i, "name": name or f"Album {i}"})
    return result


def gallery_album_current_impl() -> dict:
    gallery = _get_gallery()
    album = gallery.GetCurrentStillAlbum()
    if not album:
        return {"name": None}
    name = gallery.GetAlbumName(album)
    return {"name": name}


def gallery_album_set_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "album_set", "name": name}
    gallery = _get_gallery()
    albums = gallery.GetGalleryStillAlbums() or []
    for album in albums:
        if gallery.GetAlbumName(album) == name:
            result = gallery.SetCurrentStillAlbum(album)
            if result is False:
                raise ValidationError(
                    field="name", reason=f"Failed to set album: {name}"
                )
            return {"set": True, "name": name}
    raise ValidationError(field="name", reason=f"Album not found: {name}")


def gallery_album_create_impl(dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "album_create"}
    gallery = _get_gallery()
    album = gallery.CreateGalleryStillAlbum()
    if not album:
        raise ValidationError(field="album", reason="Failed to create album")
    name = gallery.GetAlbumName(album)
    return {"created": True, "name": name}


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


# --- Schema Registration ---

register_schema("gallery.album.list", output_model=AlbumInfo)
register_schema("gallery.album.current", output_model=AlbumCurrentOutput)
register_schema(
    "gallery.album.set",
    output_model=AlbumSetOutput,
    input_model=AlbumSetInput,
)
register_schema("gallery.album.create", output_model=AlbumCreateOutput)
