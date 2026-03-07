"""dr schema — ランタイムスキーマ解決コマンド。

エージェントが dr schema show <command> でコマンドの JSON Schema を取得し、
正しい入力を構築できるようにする。
"""

from __future__ import annotations

import click

from davinci_cli.core.exceptions import SchemaNotFoundError
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import SCHEMA_REGISTRY


def schema_show_impl(command_path: str) -> dict:
    """指定コマンドの JSON Schema を返す。"""
    if command_path not in SCHEMA_REGISTRY:
        available = sorted(SCHEMA_REGISTRY.keys())
        raise SchemaNotFoundError(command=command_path, available=available)

    input_model, output_model = SCHEMA_REGISTRY[command_path]
    result: dict = {
        "command": command_path,
        "output_schema": output_model.model_json_schema(),
    }
    if input_model:
        result["input_schema"] = input_model.model_json_schema()
    return result


def schema_list_impl() -> list[dict]:
    """登録済み全コマンドのスキーマ一覧を返す。"""
    return [{"command": k} for k in sorted(SCHEMA_REGISTRY.keys())]


@click.group()
def schema() -> None:
    """Runtime schema resolution for agent use."""


@schema.command(name="show")
@click.argument("command_path")
@click.pass_context
def show(ctx: click.Context, command_path: str) -> None:
    """コマンドの JSON Schema を出力する。"""
    result = schema_show_impl(command_path)
    output(result, pretty=ctx.obj.get("pretty"))


@schema.command(name="list")
@click.pass_context
def list_schemas(ctx: click.Context) -> None:
    """登録済み全コマンドのスキーマ一覧を出力。"""
    result = schema_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))
