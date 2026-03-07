"""DaVinci Resolve エディション（Free / Studio）判定。

API正確性に関する注意:
  GetVersion() の返り値はDaVinci Resolveのバージョンによって異なる可能性がある。
  現在の実装は GetVersion() が {"product": "DaVinci Resolve Studio"} を返すことを
  前提としている。実際のAPIレスポンスが変更された場合、このモジュールの更新が必要。

  テスト時は MockResolve で dict を返す設計を採用しているが、
  実環境での GetVersion() 出力は以下のような形式であることが確認されている:
    {"product": "DaVinci Resolve Studio", "major": 19, "minor": 0, ...}

  新しいバージョンの DaVinci Resolve で動作確認する際は、
  まず実際の GetVersion() の戻り値を確認し、必要に応じて判定ロジックを修正すること。
"""
from __future__ import annotations

from typing import Any

from davinci_cli.core.exceptions import EditionError

# エディション定数
EDITION_FREE = "Free"
EDITION_STUDIO = "Studio"


def get_edition(resolve: Any) -> str:
    """Resolve オブジェクトからエディションを検出する。

    GetVersion() が {"product": "DaVinci Resolve Studio"} を返す場合は Studio、
    それ以外は Free として扱う。
    """
    raw = resolve.GetVersion()
    version_info: dict[str, Any] = raw if isinstance(raw, dict) else {}
    product: str = version_info.get("product", "")
    if "Studio" in product:
        return EDITION_STUDIO
    return EDITION_FREE


def require_studio(resolve: Any) -> None:
    """Studio エディションでなければ EditionError を送出する。"""
    edition = get_edition(resolve)
    if edition != EDITION_STUDIO:
        raise EditionError(required=EDITION_STUDIO, actual=edition)
