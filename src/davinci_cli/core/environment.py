"""DaVinci Resolve Python API 接続のための環境変数自動設定。

優先順位:
  1. 既存の環境変数（ユーザー設定を尊重）
  2. プラットフォーム別のデフォルトパス

サポート対象: macOS (darwin), Windows (win32)
Linux は明示的にサポートしない。DaVinci Resolve の Linux 向け Python API パスが
バージョン・ディストリビューションによって異なるため、環境変数を手動設定することを推奨する。
"""
from __future__ import annotations

import os
import sys

from davinci_cli.core.exceptions import DavinciEnvironmentError

PLATFORM_MACOS = "darwin"
PLATFORM_WINDOWS = "win32"

_MACOS_DEFAULTS: dict[str, str] = {
    "RESOLVE_SCRIPT_API": (
        "/Library/Application Support/Blackmagic Design/"
        "DaVinci Resolve/Developer/Scripting/"
    ),
    "RESOLVE_SCRIPT_LIB": (
        "/Applications/DaVinci Resolve/DaVinci Resolve.app/"
        "Contents/Libraries/Fusion/"
    ),
    "RESOLVE_MODULES": (
        "/Library/Application Support/Blackmagic Design/"
        "DaVinci Resolve/Developer/Scripting/Modules/"
    ),
}

_WINDOWS_DEFAULTS: dict[str, str] = {
    "RESOLVE_SCRIPT_API": (
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve"
        r"\Support\Developer\Scripting\\"
    ),
    "RESOLVE_SCRIPT_LIB": (
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve\\"
    ),
    "RESOLVE_MODULES": (
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve"
        r"\Support\Developer\Scripting\Modules\\"
    ),
}


def _current_platform() -> str:
    """現在のプラットフォーム識別子を返す。テスト時にモック可能。"""
    return sys.platform


def get_default_paths(platform: str) -> dict[str, str]:
    """指定プラットフォームのデフォルトパスを返す。

    Raises:
        DavinciEnvironmentError: サポート対象外のプラットフォームの場合
    """
    if platform == PLATFORM_MACOS:
        return dict(_MACOS_DEFAULTS)
    if platform == PLATFORM_WINDOWS:
        return dict(_WINDOWS_DEFAULTS)
    raise DavinciEnvironmentError(
        f"Platform '{platform}' is not supported. "
        f"Supported platforms: darwin (macOS), win32 (Windows). "
        f"For other platforms, set RESOLVE_SCRIPT_API, RESOLVE_SCRIPT_LIB, "
        f"and RESOLVE_MODULES environment variables manually."
    )


def setup_environment() -> None:
    """環境変数を設定し、Modules ディレクトリを sys.path に追加する。

    既存の環境変数がある場合は上書きしない。
    """
    platform = _current_platform()
    defaults = get_default_paths(platform)

    for key, default_value in defaults.items():
        if key not in os.environ:
            os.environ[key] = default_value

    modules_path = os.environ["RESOLVE_MODULES"]
    if modules_path not in sys.path:
        sys.path.insert(0, modules_path)
