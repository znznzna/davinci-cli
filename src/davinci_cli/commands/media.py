"""dr media — メディアプール操作コマンド。

パス検証は core/validation.py の validate_path() を使用する。
"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.core.validation import validate_path
from davinci_cli.decorators import dry_run_option, fields_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema

# --- Pydantic Models ---


class MediaItem(BaseModel):
    clip_name: str
    file_path: str | None = None
    duration: str | None = None
    fps: str | None = None


class MediaImportInput(BaseModel):
    paths: list[str]


class MediaImportOutput(BaseModel):
    imported_count: int
    paths: list[str]


class FolderInfo(BaseModel):
    name: str
    clip_count: int | None = None


class FolderCreateOutput(BaseModel):
    created: str


class FolderCreateInput(BaseModel):
    name: str


class FolderDeleteOutput(BaseModel):
    deleted: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    name: str | None = None


class FolderDeleteInput(BaseModel):
    name: str


# --- Helper ---


def _get_media_pool() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    return project.GetMediaPool()


def _find_folder_by_name(root_folder: Any, name: str) -> Any:
    for sub in root_folder.GetSubFolderList() or []:
        if sub.GetName() == name:
            return sub
        found = _find_folder_by_name(sub, name)
        if found:
            return found
    return None


# --- _impl Functions ---


def media_list_impl(
    folder_name: str | None = None,
    fields: list[str] | None = None,
) -> list[dict]:
    media_pool = _get_media_pool()

    if folder_name:
        folder = _find_folder_by_name(media_pool.GetRootFolder(), folder_name)
        if not folder:
            raise ValidationError(
                field="folder",
                reason=f"Folder not found: {folder_name}",
            )
    else:
        folder = media_pool.GetRootFolder()

    clips = folder.GetClipList() or []
    items: list[dict] = []
    for clip in clips:
        info = {
            "clip_name": clip.GetName(),
            "file_path": clip.GetClipProperty("File Path"),
            "duration": clip.GetClipProperty("Duration"),
            "fps": clip.GetClipProperty("FPS"),
        }
        if fields:
            info = {k: v for k, v in info.items() if k in fields}
        items.append(info)
    return items


def media_import_impl(paths: list[str]) -> dict:
    validated: list[str] = []
    for p in paths:
        vp = validate_path(p)
        if not vp.exists():
            raise ValidationError(
                field="path",
                reason=f"File not found: {p}",
            )
        validated.append(str(vp))

    media_pool = _get_media_pool()
    imported = media_pool.ImportMedia(validated)
    return {
        "imported_count": len(imported) if imported else 0,
        "paths": validated,
    }


def folder_list_impl() -> list[dict]:
    media_pool = _get_media_pool()
    root = media_pool.GetRootFolder()
    folders: list[dict] = []
    for sub in root.GetSubFolderList() or []:
        clips = sub.GetClipList() or []
        folders.append({
            "name": sub.GetName(),
            "clip_count": len(clips),
        })
    return folders


def folder_create_impl(name: str) -> dict:
    media_pool = _get_media_pool()
    folder = media_pool.AddSubFolder(media_pool.GetRootFolder(), name)
    if not folder:
        raise ValidationError(
            field="name",
            reason=f"Failed to create folder: {name}",
        )
    return {"created": name}


def folder_delete_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "folder_delete", "name": name}
    media_pool = _get_media_pool()
    folder = _find_folder_by_name(media_pool.GetRootFolder(), name)
    if not folder:
        raise ValidationError(
            field="name", reason=f"Folder not found: {name}"
        )
    media_pool.DeleteFolders([folder])
    return {"deleted": name}


# --- CLI Commands ---


@click.group()
def media() -> None:
    """Media pool operations."""


@media.command(name="list")
@click.option("--folder", default=None, help="Folder name")
@fields_option
@click.pass_context
def media_list(
    ctx: click.Context, folder: str | None, fields: list[str] | None
) -> None:
    """メディア一覧。"""
    result = media_list_impl(folder_name=folder, fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@media.command(name="import")
@click.argument("paths", nargs=-1, required=True)
@click.pass_context
def media_import(ctx: click.Context, paths: tuple[str, ...]) -> None:
    """メディアインポート（パス検証付き）。"""
    result = media_import_impl(paths=list(paths))
    output(result, pretty=ctx.obj.get("pretty"))


@media.group(name="folder")
def media_folder() -> None:
    """Media folder operations."""


@media_folder.command(name="list")
@click.pass_context
def folder_list_cmd(ctx: click.Context) -> None:
    """フォルダ一覧。"""
    result = folder_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@media_folder.command(name="create")
@click.argument("name")
@click.pass_context
def folder_create_cmd(ctx: click.Context, name: str) -> None:
    """フォルダ作成。"""
    result = folder_create_impl(name=name)
    output(result, pretty=ctx.obj.get("pretty"))


@media_folder.command(name="delete")
@click.argument("name")
@dry_run_option
@click.pass_context
def folder_delete_cmd(
    ctx: click.Context, name: str, dry_run: bool
) -> None:
    """フォルダ削除。"""
    result = folder_delete_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("media.list", output_model=MediaItem)
register_schema(
    "media.import",
    output_model=MediaImportOutput,
    input_model=MediaImportInput,
)
register_schema("media.folder.list", output_model=FolderInfo)
register_schema(
    "media.folder.create",
    output_model=FolderCreateOutput,
    input_model=FolderCreateInput,
)
register_schema(
    "media.folder.delete",
    output_model=FolderDeleteOutput,
    input_model=FolderDeleteInput,
)
