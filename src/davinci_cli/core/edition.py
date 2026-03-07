"""DaVinci Resolve エディション（Free / Studio）判定。

API正確性に関する注意:
  GetVersion() の返り値はDaVinci Resolveのバージョンによって異なる。

  DaVinci Resolve 20.x (実機確認済み):
    GetVersion()       → [20, 3, 2, 9, '']   (list, 5番目がエディション情報)
    GetVersionString() → "20.3.2.9"

  過去バージョン (19.x 等) では dict を返す可能性がある:
    GetVersion()       → {"product": "DaVinci Resolve Studio", ...}

  Studio 判定は以下の優先順位で行う:
    1. dict の場合: product キーに "Studio" を含むか
    2. list の場合: 文字列要素に "Studio" を含むか
    3. GetVersionString() に "Studio" を含むか
"""

from __future__ import annotations

from typing import Any

from davinci_cli.core.exceptions import EditionError

# エディション定数
EDITION_FREE = "Free"
EDITION_STUDIO = "Studio"

_STUDIO_MARKER = "Studio"


def get_edition(resolve: Any) -> str:
    """Resolve オブジェクトからエディションを検出する。

    GetVersion() の戻り値が dict / list いずれの場合も対応し、
    フォールバックとして GetVersionString() も確認する。
    """
    raw = resolve.GetVersion()

    # dict 形式 (19.x 等): {"product": "DaVinci Resolve Studio", ...}
    if isinstance(raw, dict):
        product: str = raw.get("product", "")
        if _STUDIO_MARKER in product:
            return EDITION_STUDIO

    # list 形式 (20.x): [major, minor, patch, build, edition_suffix]
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and _STUDIO_MARKER in item:
                return EDITION_STUDIO

    # フォールバック: GetVersionString() を確認
    try:
        version_str = resolve.GetVersionString()
        if isinstance(version_str, str) and _STUDIO_MARKER in version_str:
            return EDITION_STUDIO
    except (AttributeError, TypeError):
        pass

    return EDITION_FREE


def require_studio(resolve: Any) -> None:
    """Studio エディションでなければ EditionError を送出する。"""
    edition = get_edition(resolve)
    if edition != EDITION_STUDIO:
        raise EditionError(required=EDITION_STUDIO, actual=edition)
