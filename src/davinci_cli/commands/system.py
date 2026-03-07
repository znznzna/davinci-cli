"""dr system — システム情報コマンド。

エディション判定は core/edition.py の get_edition() を使用する。
Resolve 接続は core.connection を使用する。
"""

from __future__ import annotations

import click

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.edition import get_edition
from davinci_cli.output.formatter import output


@click.group()
def system() -> None:
    """System information commands."""


def ping_impl() -> dict:
    """Resolve 接続確認。"""
    resolve = get_resolve()
    version = resolve.GetVersionString()
    return {"status": "ok", "version": version}


def version_impl() -> dict:
    """バージョン情報を返す。"""
    resolve = get_resolve()
    return {
        "version": resolve.GetVersionString(),
        "edition": get_edition(resolve),
    }


def edition_impl() -> dict:
    """エディション情報を返す。"""
    resolve = get_resolve()
    return {
        "edition": get_edition(resolve),
    }


def info_impl() -> dict:
    """総合情報を返す。"""
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    return {
        "version": resolve.GetVersionString(),
        "edition": get_edition(resolve),
        "current_project": project.GetName() if project else None,
    }


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
