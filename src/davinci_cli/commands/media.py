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


class MediaMoveInput(BaseModel):
    clip_names: list[str]
    target_folder: str


class MediaMoveOutput(BaseModel):
    moved_count: int | None = None
    clip_names: list[str] | None = None
    target_folder: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class MediaDeleteInput(BaseModel):
    clip_names: list[str]


class MediaDeleteOutput(BaseModel):
    deleted_count: int | None = None
    clip_names: list[str] | None = None
    dry_run: bool | None = None
    action: str | None = None


class MediaRelinkInput(BaseModel):
    clip_names: list[str]
    folder_path: str


class MediaRelinkOutput(BaseModel):
    relinked_count: int | None = None
    clip_names: list[str] | None = None
    folder_path: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class MediaUnlinkInput(BaseModel):
    clip_names: list[str]


class MediaUnlinkOutput(BaseModel):
    unlinked_count: int
    clip_names: list[str]


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


def _find_clips_by_names(media_pool: Any, clip_names: list[str]) -> list[Any]:
    """現在のフォルダからクリップ名でクリップを検索する。"""
    folder = media_pool.GetCurrentFolder()
    clips = folder.GetClipList() or []
    clip_map = {c.GetName(): c for c in clips}
    found: list[Any] = []
    for name in clip_names:
        if name not in clip_map:
            raise ValidationError(
                field="clip_names",
                reason=f"Clip not found: {name}",
            )
        found.append(clip_map[name])
    return found


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


def media_move_impl(
    clip_names: list[str],
    target_folder: str,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "media_move",
            "clip_names": clip_names,
            "target_folder": target_folder,
        }
    media_pool = _get_media_pool()
    clips = _find_clips_by_names(media_pool, clip_names)
    target = _find_folder_by_name(media_pool.GetRootFolder(), target_folder)
    if not target:
        raise ValidationError(
            field="target_folder",
            reason=f"Folder not found: {target_folder}",
        )
    media_pool.MoveClips(clips, target)
    return {
        "moved_count": len(clips),
        "clip_names": clip_names,
        "target_folder": target_folder,
    }


def media_delete_impl(
    clip_names: list[str],
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "media_delete",
            "clip_names": clip_names,
        }
    media_pool = _get_media_pool()
    clips = _find_clips_by_names(media_pool, clip_names)
    media_pool.DeleteClips(clips)
    return {
        "deleted_count": len(clips),
        "clip_names": clip_names,
    }


def media_relink_impl(
    clip_names: list[str],
    folder_path: str,
    dry_run: bool = False,
) -> dict:
    validated_path = str(validate_path(folder_path))
    if dry_run:
        return {
            "dry_run": True,
            "action": "media_relink",
            "clip_names": clip_names,
            "folder_path": validated_path,
        }
    media_pool = _get_media_pool()
    clips = _find_clips_by_names(media_pool, clip_names)
    media_pool.RelinkClips(clips, validated_path)
    return {
        "relinked_count": len(clips),
        "clip_names": clip_names,
        "folder_path": validated_path,
    }


def media_unlink_impl(clip_names: list[str]) -> dict:
    media_pool = _get_media_pool()
    clips = _find_clips_by_names(media_pool, clip_names)
    media_pool.UnlinkClips(clips)
    return {
        "unlinked_count": len(clips),
        "clip_names": clip_names,
    }


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


@media.command(name="move")
@click.argument("clip_names", nargs=-1, required=True)
@click.option("--target", required=True, help="Target folder name")
@dry_run_option
@click.pass_context
def media_move_cmd(
    ctx: click.Context, clip_names: tuple[str, ...], target: str, dry_run: bool
) -> None:
    """クリップを別フォルダに移動。"""
    result = media_move_impl(
        clip_names=list(clip_names), target_folder=target, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@media.command(name="delete")
@click.argument("clip_names", nargs=-1, required=True)
@dry_run_option
@click.pass_context
def media_delete_cmd(
    ctx: click.Context, clip_names: tuple[str, ...], dry_run: bool
) -> None:
    """クリップを削除。"""
    result = media_delete_impl(clip_names=list(clip_names), dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@media.command(name="relink")
@click.argument("clip_names", nargs=-1, required=True)
@click.option("--folder-path", required=True, help="Folder path to relink to")
@dry_run_option
@click.pass_context
def media_relink_cmd(
    ctx: click.Context,
    clip_names: tuple[str, ...],
    folder_path: str,
    dry_run: bool,
) -> None:
    """クリップのメディアを再リンク。"""
    result = media_relink_impl(
        clip_names=list(clip_names), folder_path=folder_path, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@media.command(name="unlink")
@click.argument("clip_names", nargs=-1, required=True)
@click.pass_context
def media_unlink_cmd(ctx: click.Context, clip_names: tuple[str, ...]) -> None:
    """クリップのメディアリンクを解除。"""
    result = media_unlink_impl(clip_names=list(clip_names))
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
register_schema(
    "media.move",
    output_model=MediaMoveOutput,
    input_model=MediaMoveInput,
)
register_schema(
    "media.delete",
    output_model=MediaDeleteOutput,
    input_model=MediaDeleteInput,
)
register_schema(
    "media.relink",
    output_model=MediaRelinkOutput,
    input_model=MediaRelinkInput,
)
register_schema(
    "media.unlink",
    output_model=MediaUnlinkOutput,
    input_model=MediaUnlinkInput,
)
