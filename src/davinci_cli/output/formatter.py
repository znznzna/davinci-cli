"""出力フォーマッタ — エージェントファースト出力設計。

出力規約:
  - _impl 関数は常に flat な list[dict] または dict を返す
  - ネストした構造は避ける（エージェントのパースが複雑になる）
  - 非TTY / pretty=False: NDJSON（list）または JSON（dict）
  - TTY + pretty=True: Rich を使った人間可読形式
  - --fields: 任意の Read コマンドでフィールド絞り込み
"""
from __future__ import annotations

import json
import sys
from typing import Any

from rich import print as rich_print
from rich.pretty import Pretty


def is_tty() -> bool:
    """stdout が TTY かどうかを返す。"""
    return sys.stdout.isatty()


def filter_fields(
    data: dict[str, Any] | list[dict[str, Any]],
    fields: list[str] | None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """指定フィールドのみを残す。fields が None の場合は無変換で返す。"""
    if fields is None:
        return data

    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in fields}

    if isinstance(data, list):
        return [{k: v for k, v in item.items() if k in fields} for item in data]

    return data


def output(
    data: dict[str, Any] | list[dict[str, Any]],
    fields: list[str] | None = None,
    pretty: bool = False,
) -> None:
    """データを標準出力へ書き出す。

    Args:
        data: 出力するデータ（dict または list of dict）
        fields: 絞り込むフィールド名リスト。None で全フィールド出力。
        pretty: True かつ TTY の場合は Rich 形式で出力。
    """
    if fields:
        data = filter_fields(data, fields)

    if is_tty() and pretty:
        rich_print(Pretty(data))
        return

    # 非TTY または pretty=False: NDJSON / JSON
    if isinstance(data, list):
        for item in data:
            print(json.dumps(item, ensure_ascii=False))
    else:
        print(json.dumps(data, ensure_ascii=False))
