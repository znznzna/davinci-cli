"""共通 Click デコレータ。

全コマンドで統一的に使う --json, --fields, --dry-run オプションを定義する。
各コマンドファイルで個別にオプションを定義するのではなく、
このモジュールのデコレータを使って統一する。

使い方:
    @project.command(name="open")
    @json_input_option
    @dry_run_option
    @click.pass_context
    def project_open(ctx, json_input, dry_run):
        ...
"""

from __future__ import annotations

import json as json_module
from collections.abc import Callable
from typing import Any

import click


class _JsonParamType(click.ParamType):
    """JSON 文字列をパースする Click パラメータ型。"""

    name = "JSON"

    def convert(self, value: Any, param: Any, ctx: Any) -> dict | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        try:
            parsed = json_module.loads(value)
            if not isinstance(parsed, dict):
                self.fail(f"Expected JSON object, got {type(parsed).__name__}", param, ctx)
            return parsed
        except json_module.JSONDecodeError as e:
            self.fail(f"Invalid JSON: {e}", param, ctx)
        return None  # unreachable, for type checker


JSON_TYPE = _JsonParamType()


def json_input_option(func: Callable) -> Callable:
    """--json オプションを追加するデコレータ。"""
    return click.option(
        "--json",
        "json_input",
        type=JSON_TYPE,
        default=None,
        help='JSON input (e.g. \'{"name": "value"}\')',
    )(func)


def _parse_fields(ctx: Any, param: Any, value: str | None) -> list[str] | None:
    """カンマ区切りのフィールド文字列をリストに変換するコールバック。"""
    if value is None:
        return None
    return [f.strip() for f in value.split(",") if f.strip()]


def fields_option(func: Callable) -> Callable:
    """--fields オプションを追加するデコレータ。"""
    return click.option(
        "--fields",
        default=None,
        callback=_parse_fields,
        expose_value=True,
        is_eager=False,
        help="Comma-separated field names (e.g. name,id,fps)",
    )(func)


def dry_run_option(func: Callable) -> Callable:
    """--dry-run オプションを追加するデコレータ。"""
    return click.option(
        "--dry-run",
        "dry_run",
        is_flag=True,
        default=False,
        help="Preview the action without executing it",
    )(func)
