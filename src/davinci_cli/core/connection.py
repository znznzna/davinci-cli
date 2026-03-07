"""DaVinci Resolve Python API への接続管理。

キャッシュ戦略:
  - _import_resolve_script: DaVinciResolveScript モジュールを lru_cache でキャッシュ
  - _cached_resolve: Resolve オブジェクト自体もキャッシュ（scriptapp() 呼び出しを1回に）
  - clear_resolve_cache(): 両方のキャッシュをクリア（テスト・再接続用）

全コマンドは 'davinci_cli.core.connection.get_resolve' を使用する。
旧名 'resolve_bridge' は使わない。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from davinci_cli.core.environment import setup_environment
from davinci_cli.core.exceptions import (
    DavinciEnvironmentError,
    ResolveNotRunningError,
)

# Resolve オブジェクトのキャッシュ
_cached_resolve: Any | None = None


@lru_cache(maxsize=1)
def _import_resolve_script() -> Any:
    """DaVinciResolveScript モジュールをインポートしてキャッシュする。

    環境変数のセットアップは初回インポート時に1度だけ実行する。
    """
    setup_environment()
    try:
        import DaVinciResolveScript as dvr  # type: ignore[import-not-found]

        return dvr
    except ImportError as exc:
        raise DavinciEnvironmentError(
            f"Could not import DaVinciResolveScript: {exc}. "
            "Ensure DaVinci Resolve is installed and RESOLVE_MODULES is set correctly."
        ) from exc


def get_resolve() -> Any:
    """Resolve オブジェクトを返す。

    DaVinciResolveScript モジュールと Resolve オブジェクトの両方をキャッシュする。
    DaVinci Resolve が起動していない場合は ResolveNotRunningError を送出する。
    """
    global _cached_resolve

    if _cached_resolve is not None:
        return _cached_resolve

    try:
        dvr = _import_resolve_script()
    except ImportError as exc:
        raise DavinciEnvironmentError(
            f"Could not import DaVinciResolveScript: {exc}. "
            "Ensure DaVinci Resolve is installed and RESOLVE_MODULES is set correctly."
        ) from exc
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise ResolveNotRunningError()

    _cached_resolve = resolve
    return resolve


def clear_resolve_cache() -> None:
    """接続キャッシュをクリアする（テスト・再接続用）。

    DaVinciResolveScript モジュールのキャッシュと
    Resolve オブジェクトのキャッシュの両方をクリアする。
    """
    global _cached_resolve
    _cached_resolve = None
    _import_resolve_script.cache_clear()
