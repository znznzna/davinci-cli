"""スキーマレジストリ — コマンドの入出力 JSON Schema を管理する。

各コマンドモジュールの末尾で register_schema() を呼んでスキーマを登録する。
エージェントは dr schema show <command> でスキーマを取得できる。
"""

from __future__ import annotations

from pydantic import BaseModel

# コマンドパス → (InputModel | None, OutputModel)
SCHEMA_REGISTRY: dict[str, tuple[type[BaseModel] | None, type[BaseModel]]] = {}


def register_schema(
    command_path: str,
    output_model: type[BaseModel],
    input_model: type[BaseModel] | None = None,
) -> None:
    """スキーマをレジストリに登録する。"""
    SCHEMA_REGISTRY[command_path] = (input_model, output_model)
