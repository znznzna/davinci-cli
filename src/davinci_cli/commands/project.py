"""dr project — プロジェクト操作コマンド。

共通デコレータ（@json_input_option, @fields_option, @dry_run_option）を使用。
プロジェクトが見つからない場合は ProjectNotFoundError を送出する。
"""

from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import (
    ProjectNotFoundError,
    ProjectNotOpenError,
    ValidationError,
)
from davinci_cli.decorators import dry_run_option, fields_option, json_input_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema

# --- Pydantic Models ---


class ProjectListItem(BaseModel):
    name: str


class ProjectOpenOutput(BaseModel):
    opened: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    name: str | None = None


class ProjectOpenInput(BaseModel):
    name: str


class ProjectCloseOutput(BaseModel):
    closed: bool | None = None
    dry_run: bool | None = None
    action: str | None = None


class ProjectCreateOutput(BaseModel):
    created: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    name: str | None = None


class ProjectCreateInput(BaseModel):
    name: str


class ProjectDeleteOutput(BaseModel):
    deleted: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    name: str | None = None


class ProjectDeleteInput(BaseModel):
    name: str


class ProjectRenameInput(BaseModel):
    name: str


class ProjectRenameOutput(BaseModel):
    renamed: bool | None = None
    name: str
    dry_run: bool | None = None
    action: str | None = None


class ProjectSaveOutput(BaseModel):
    saved: bool


class ProjectInfoOutput(BaseModel):
    name: str
    timeline_count: int | None = None
    fps: str | None = None


class ProjectSettingsGetOutput(BaseModel):
    key: str | None = None
    value: str | None = None
    settings: str | None = None


class ProjectSettingsSetOutput(BaseModel):
    set: bool | None = None
    key: str | None = None
    value: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class ProjectSettingsSetInput(BaseModel):
    key: str
    value: str


# --- Helper ---


def _get_current_project() -> Any:
    """現在のプロジェクトを取得。開いていなければ ProjectNotOpenError。"""
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise ProjectNotOpenError()
    return project


# --- _impl Functions ---


def project_list_impl(fields: list[str] | None = None) -> list[dict[str, Any]]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    names = pm.GetProjectListInCurrentFolder()
    projects: list[dict[str, Any]] = [{"name": n} for n in names]
    if fields:
        projects = [{k: p[k] for k in fields if k in p} for p in projects]
    return projects


def project_open_impl(name: str, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "action": "open", "name": name}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.LoadProject(name)
    if not project:
        raise ProjectNotFoundError(name=name)
    return {"opened": name}


def project_close_impl(dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "action": "close"}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    current = pm.GetCurrentProject()
    if not current:
        raise ProjectNotOpenError()
    result = pm.CloseProject(current)
    if not result:
        raise ValidationError(
            field="project",
            reason="CloseProject failed. The project may have unsaved changes.",
        )
    return {"closed": True}


def project_create_impl(name: str, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "action": "create", "name": name}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.CreateProject(name)
    if not project:
        raise ProjectNotFoundError(name=name)
    return {"created": name}


def project_delete_impl(name: str, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "action": "delete", "name": name}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    success = pm.DeleteProject(name)
    if not success:
        raise ProjectNotFoundError(name=name)
    return {"deleted": name}


def project_rename_impl(name: str, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "action": "rename", "name": name}
    project = _get_current_project()
    result = project.SetName(name)
    if result is False:
        raise ValidationError(
            field="name", reason=f"Failed to rename project to: {name}"
        )
    return {"renamed": True, "name": name}


def project_save_impl() -> dict[str, Any]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    if not pm.SaveProject():
        raise ValidationError(field="save", reason="SaveProject failed")
    return {"saved": True}


def project_info_impl(fields: list[str] | None = None) -> dict[str, Any]:
    project = _get_current_project()
    info = {
        "name": project.GetName(),
        "timeline_count": project.GetTimelineCount(),
        "fps": project.GetSetting("timelineFrameRate"),
    }
    if fields:
        info = {k: v for k, v in info.items() if k in fields}
    return info


def project_settings_get_impl(key: str | None = None) -> dict[str, Any]:
    project = _get_current_project()
    if key:
        value = project.GetSetting(key)
        return {"key": key, "value": value}
    return {"settings": "all settings retrieval not implemented yet"}


def project_settings_set_impl(
    key: str, value: str, dry_run: bool = False
) -> dict[str, Any]:
    if dry_run:
        return {
            "dry_run": True,
            "action": "settings_set",
            "key": key,
            "value": value,
        }
    project = _get_current_project()
    result = project.SetSetting(key, value)
    if not result:
        raise ValidationError(
            field="key",
            reason=f"SetSetting failed for key '{key}'. "
            "The key may be invalid or the value may be out of range.",
        )
    return {"set": True, "key": key, "value": value}


# --- CLI Commands ---


@click.group()
def project() -> None:
    """Project operations."""


@project.command(name="list")
@fields_option
@click.pass_context
def project_list(ctx: click.Context, fields: list[str] | None) -> None:
    """プロジェクト一覧。"""
    result = project_list_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="open")
@click.argument("name", required=False)
@json_input_option
@dry_run_option
@click.pass_context
def project_open(
    ctx: click.Context,
    name: str | None,
    json_input: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    """プロジェクトを開く。"""
    if json_input:
        data = ProjectOpenInput.model_validate(json_input)
        name = data.name
    if not name:
        raise click.UsageError("name is required (positional argument or --json)")
    result = project_open_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="close")
@dry_run_option
@click.pass_context
def project_close(ctx: click.Context, dry_run: bool) -> None:
    """現在のプロジェクトを閉じる。"""
    result = project_close_impl(dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="create")
@click.argument("name", required=False)
@json_input_option
@dry_run_option
@click.pass_context
def project_create_cmd(
    ctx: click.Context,
    name: str | None,
    json_input: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    """新規プロジェクト作成。"""
    if json_input:
        data = ProjectCreateInput.model_validate(json_input)
        name = data.name
    if not name:
        raise click.UsageError("name is required (positional argument or --json)")
    result = project_create_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="delete")
@click.argument("name", required=False)
@json_input_option
@dry_run_option
@click.pass_context
def project_delete_cmd(
    ctx: click.Context,
    name: str | None,
    json_input: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    """プロジェクト削除（破壊的操作）。"""
    if json_input:
        data = ProjectDeleteInput.model_validate(json_input)
        name = data.name
    if not name:
        raise click.UsageError("name is required (positional argument or --json)")
    result = project_delete_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="rename")
@click.argument("name", required=False)
@json_input_option
@dry_run_option
@click.pass_context
def project_rename(
    ctx: click.Context,
    name: str | None,
    json_input: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    """プロジェクト名を変更する。"""
    if json_input:
        data = ProjectRenameInput.model_validate(json_input)
        name = data.name
    if not name:
        raise click.UsageError("name is required (positional argument or --json)")
    result = project_rename_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="save")
@click.pass_context
def project_save_cmd(ctx: click.Context) -> None:
    """プロジェクト保存。"""
    result = project_save_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="info")
@fields_option
@click.pass_context
def project_info(ctx: click.Context, fields: list[str] | None) -> None:
    """現在のプロジェクト情報。"""
    result = project_info_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@project.group(name="settings")
def project_settings() -> None:
    """Project settings operations."""


@project_settings.command(name="get")
@click.argument("key", required=False)
@click.pass_context
def settings_get(ctx: click.Context, key: str | None) -> None:
    """設定値取得。"""
    result = project_settings_get_impl(key=key)
    output(result, pretty=ctx.obj.get("pretty"))


@project_settings.command(name="set")
@click.argument("key")
@click.argument("value")
@dry_run_option
@click.pass_context
def settings_set(ctx: click.Context, key: str, value: str, dry_run: bool) -> None:
    """設定値変更。"""
    result = project_settings_set_impl(key=key, value=value, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("project.list", output_model=ProjectListItem)
register_schema(
    "project.open", output_model=ProjectOpenOutput, input_model=ProjectOpenInput
)
register_schema("project.close", output_model=ProjectCloseOutput)
register_schema(
    "project.create",
    output_model=ProjectCreateOutput,
    input_model=ProjectCreateInput,
)
register_schema(
    "project.delete",
    output_model=ProjectDeleteOutput,
    input_model=ProjectDeleteInput,
)
register_schema(
    "project.rename",
    output_model=ProjectRenameOutput,
    input_model=ProjectRenameInput,
)
register_schema("project.save", output_model=ProjectSaveOutput)
register_schema("project.info", output_model=ProjectInfoOutput)
register_schema("project.settings.get", output_model=ProjectSettingsGetOutput)
register_schema(
    "project.settings.set",
    output_model=ProjectSettingsSetOutput,
    input_model=ProjectSettingsSetInput,
)
