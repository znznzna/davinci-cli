"""dr system — システム情報コマンド。

エディション判定は core/edition.py の get_edition() を使用する。
Resolve 接続は core.connection を使用する。
"""

from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.edition import get_edition
from davinci_cli.core.exceptions import ValidationError
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema

_VALID_PAGES = {"media", "cut", "edit", "fusion", "color", "fairlight", "deliver"}

_KEYFRAME_MODES = {0: "all", 1: "color", 2: "sizing"}


@click.group()
def system() -> None:
    """System information commands."""


def ping_impl() -> dict[str, Any]:
    """Resolve 接続確認。"""
    resolve = get_resolve()
    version = resolve.GetVersionString()
    return {"status": "ok", "version": version}


def version_impl() -> dict[str, Any]:
    """バージョン情報を返す。"""
    resolve = get_resolve()
    return {
        "version": resolve.GetVersionString(),
        "edition": get_edition(resolve),
    }


def edition_impl() -> dict[str, Any]:
    """エディション情報を返す。"""
    resolve = get_resolve()
    return {
        "edition": get_edition(resolve),
    }


def info_impl() -> dict[str, Any]:
    """総合情報を返す。"""
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    return {
        "version": resolve.GetVersionString(),
        "edition": get_edition(resolve),
        "current_project": project.GetName() if project else None,
    }


def page_get_impl() -> dict[str, Any]:
    """現在のページを取得する。"""
    resolve = get_resolve()
    return {"page": resolve.GetCurrentPage()}


def page_set_impl(page: str, dry_run: bool = False) -> dict[str, Any]:
    """ページを切り替える。"""
    if page not in _VALID_PAGES:
        raise ValidationError(
            field="page",
            reason=f"Invalid page: {page}. Valid: {', '.join(sorted(_VALID_PAGES))}",
        )
    if dry_run:
        return {"dry_run": True, "action": "page_set", "page": page}
    resolve = get_resolve()
    result = resolve.OpenPage(page)
    if result is False:
        raise ValidationError(field="page", reason=f"Failed to switch to page: {page}")
    return {"set": True, "page": page}


def keyframe_mode_get_impl() -> dict[str, Any]:
    """現在のキーフレームモードを取得する。"""
    resolve = get_resolve()
    mode = resolve.GetKeyframeMode()
    return {"mode": mode, "label": _KEYFRAME_MODES.get(mode, "unknown")}


def keyframe_mode_set_impl(mode: int, dry_run: bool = False) -> dict[str, Any]:
    """キーフレームモードを設定する。"""
    if mode not in _KEYFRAME_MODES:
        raise ValidationError(
            field="mode",
            reason=f"Invalid mode: {mode}. Valid: 0=all, 1=color, 2=sizing",
        )
    if dry_run:
        return {"dry_run": True, "action": "keyframe_mode_set", "mode": mode}
    resolve = get_resolve()
    result = resolve.SetKeyframeMode(mode)
    if result is False:
        current_page = resolve.GetCurrentPage()
        raise ValidationError(
            field="mode",
            reason=(
                f"Failed to set keyframe mode to {mode}. "
                f"Current page: {current_page}. "
                "This function is only available on the Color page."
            ),
        )
    return {"set": True, "mode": mode, "label": _KEYFRAME_MODES[mode]}


@system.command()
@click.pass_context
def ping(ctx: click.Context) -> None:
    """Resolve 接続確認。"""
    result = ping_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@system.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """バージョン情報。"""
    result = version_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@system.command()
@click.pass_context
def edition(ctx: click.Context) -> None:
    """エディション（Free/Studio）確認。"""
    result = edition_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@system.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """総合情報（バージョン+エディション+現在プロジェクト）。"""
    result = info_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@system.group()
def page() -> None:
    """ページナビゲーション。"""


@page.command(name="get")
@click.pass_context
def page_get(ctx: click.Context) -> None:
    """現在のページを取得。"""
    result = page_get_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@page.command(name="set")
@click.argument("page_name")
@click.option("--dry-run", is_flag=True, default=False)
@click.pass_context
def page_set(ctx: click.Context, page_name: str, dry_run: bool) -> None:
    """ページを切り替える。"""
    result = page_set_impl(page_name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@system.group("keyframe-mode")
def keyframe_mode() -> None:
    """キーフレームモード操作。"""


@keyframe_mode.command(name="get")
@click.pass_context
def keyframe_mode_get(ctx: click.Context) -> None:
    """現在のキーフレームモードを取得。"""
    result = keyframe_mode_get_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@keyframe_mode.command(name="set")
@click.argument("mode", type=int)
@click.option("--dry-run", is_flag=True, default=False)
@click.pass_context
def keyframe_mode_set(ctx: click.Context, mode: int, dry_run: bool) -> None:
    """キーフレームモードを設定（0=all, 1=color, 2=sizing）。"""
    result = keyframe_mode_set_impl(mode, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Pydantic models for schema registration ---


class PageGetOutput(BaseModel):
    page: str | None


class PageSetOutput(BaseModel):
    set: bool | None = None
    page: str
    dry_run: bool | None = None
    action: str | None = None


class KeyframeModeGetOutput(BaseModel):
    mode: int
    label: str


class KeyframeModeSetOutput(BaseModel):
    set: bool | None = None
    mode: int
    label: str | None = None
    dry_run: bool | None = None
    action: str | None = None


# --- Schema registration ---

register_schema("system.page.get", output_model=PageGetOutput)
register_schema("system.page.set", output_model=PageSetOutput)
register_schema("system.keyframe-mode.get", output_model=KeyframeModeGetOutput)
register_schema("system.keyframe-mode.set", output_model=KeyframeModeSetOutput)
