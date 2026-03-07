# davinci-cli Implementation Plan — Phase 1: Core Layer

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** davinci-cliのコア層（接続・環境変数・バリデーション・出力）を構築する
**Architecture:** Environment-Injected Direct Call — DaVinci Python APIに環境変数で直接接続
**Tech Stack:** Python 3.10+, Pydantic v2, Rich, pytest

---

## 前提条件

- Python 3.10+ がインストール済み
- DaVinci Resolve がインストール済み（テスト実行時はモックで代替）
- プロジェクトルートに `pyproject.toml` と `src/` レイアウト

---

### Task 1: プロジェクトセットアップ

**Files:**
- Create: `pyproject.toml`
- Create: `src/davinci_cli/__init__.py`
- Create: `src/davinci_cli/cli.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/mocks/__init__.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_project_setup.py
import importlib
import sys


def test_davinci_cli_importable():
    """パッケージがインポート可能であること"""
    mod = importlib.import_module("davinci_cli")
    assert mod is not None


def test_cli_entry_point_exists():
    """CLIエントリポイント（dr コマンド）が定義されていること"""
    from davinci_cli.cli import cli
    assert callable(cli)


def test_package_version_defined():
    """バージョンが定義されていること"""
    import davinci_cli
    assert hasattr(davinci_cli, "__version__")
    assert isinstance(davinci_cli.__version__, str)
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_project_setup.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: 最小限の実装**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "davinci-cli"
version = "0.1.0"
description = "DaVinci Resolve CLI / MCP — agent-first design"
requires-python = ">=3.10"
dependencies = [
    "click>=8.1",
    "fastmcp>=0.1",
    "pydantic>=2.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
]

[project.scripts]
dr = "davinci_cli.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/davinci_cli"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

```python
# src/davinci_cli/__init__.py
"""davinci-cli — DaVinci Resolve CLI & MCP server, agent-first design."""

__version__ = "0.1.0"
```

```python
# src/davinci_cli/cli.py
"""CLIエントリポイント。"""

import click


@click.group()
@click.version_option()
def cli() -> None:
    """DaVinci Resolve CLI — agent-first."""
```

**Step 4: 通過を確認**

Run:
```bash
pip install -e ".[dev]"
python -m pytest tests/unit/test_project_setup.py -v
```
Expected: PASS

**Step 5: コミット**

```bash
git add pyproject.toml src/davinci_cli/__init__.py src/davinci_cli/cli.py \
        tests/__init__.py tests/unit/__init__.py tests/mocks/__init__.py \
        tests/unit/test_project_setup.py
git commit -m "feat: プロジェクトスケルトンを作成 (Click + pytest + src レイアウト)"
```

---

### Task 2: core/exceptions.py

**Files:**
- Create: `src/davinci_cli/core/__init__.py`
- Create: `src/davinci_cli/core/exceptions.py`
- Test: `tests/unit/test_exceptions.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_exceptions.py
import pytest
from davinci_cli.core.exceptions import (
    DavinciCLIError,
    ResolveNotRunningError,
    ProjectNotOpenError,
    ValidationError,
    EnvironmentError as DavinciEnvError,
    EditionError,
)


def test_base_exception_hierarchy():
    """全例外が DavinciCLIError を継承していること"""
    for exc_class in [
        ResolveNotRunningError,
        ProjectNotOpenError,
        ValidationError,
        DavinciEnvError,
        EditionError,
    ]:
        assert issubclass(exc_class, DavinciCLIError)


def test_resolve_not_running_error_has_exit_code():
    exc = ResolveNotRunningError()
    assert exc.exit_code == 1
    assert "DaVinci Resolve" in str(exc)


def test_project_not_open_error_has_exit_code():
    exc = ProjectNotOpenError()
    assert exc.exit_code == 2


def test_validation_error_captures_field():
    exc = ValidationError(field="path", reason="path traversal detected")
    assert exc.field == "path"
    assert "path traversal" in str(exc)
    assert exc.exit_code == 3


def test_environment_error_has_exit_code():
    exc = DavinciEnvError(detail="RESOLVE_SCRIPT_API not found")
    assert exc.exit_code == 4
    assert "RESOLVE_SCRIPT_API" in str(exc)


def test_edition_error_has_exit_code():
    exc = EditionError(required="Studio", actual="Free")
    assert exc.exit_code == 5
    assert "Studio" in str(exc)


def test_exceptions_are_catchable_as_base():
    with pytest.raises(DavinciCLIError):
        raise ResolveNotRunningError()
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_exceptions.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/core/exceptions.py
"""davinci-cli 例外階層。

全例外は DavinciCLIError を継承し、exit_code を持つ。
エージェントはこの exit_code を使ってエラー種別を判別できる。
"""
from __future__ import annotations


class DavinciCLIError(Exception):
    """基底例外。"""

    exit_code: int = 1

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class ResolveNotRunningError(DavinciCLIError):
    """DaVinci Resolve が起動していない。"""

    exit_code = 1

    def __init__(self) -> None:
        super().__init__(
            "DaVinci Resolve is not running. Please launch DaVinci Resolve first."
        )


class ProjectNotOpenError(DavinciCLIError):
    """プロジェクトが開かれていない。"""

    exit_code = 2

    def __init__(self) -> None:
        super().__init__("No project is currently open in DaVinci Resolve.")


class ValidationError(DavinciCLIError):
    """入力値バリデーションエラー。"""

    exit_code = 3

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        super().__init__(f"Validation failed for '{field}': {reason}")


class EnvironmentError(DavinciCLIError):
    """環境変数・パス設定エラー。"""

    exit_code = 4

    def __init__(self, detail: str) -> None:
        super().__init__(f"Environment configuration error: {detail}")


class EditionError(DavinciCLIError):
    """DaVinci Resolve エディション不一致エラー。"""

    exit_code = 5

    def __init__(self, required: str, actual: str) -> None:
        self.required = required
        self.actual = actual
        super().__init__(
            f"This feature requires DaVinci Resolve {required}, "
            f"but {actual} edition is running."
        )
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_exceptions.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/__init__.py src/davinci_cli/core/exceptions.py \
        tests/unit/test_exceptions.py
git commit -m "feat: core/exceptions.py — 型付き例外階層と exit_code 定義"
```

---

### Task 3: core/validation.py（入力ハードニング）

**Files:**
- Create: `src/davinci_cli/core/validation.py`
- Test: `tests/unit/test_validation.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_validation.py
import pytest
from davinci_cli.core.validation import validate_path, validate_resource_id, validate_string
from davinci_cli.core.exceptions import ValidationError


# --- validate_path ---

class TestValidatePath:
    def test_valid_path_passes(self):
        # 正常系：問題のないパスは通過する
        assert validate_path("MyProject/timeline.drp") == "MyProject/timeline.drp"

    def test_path_traversal_single_dot_dot(self):
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("../secret")

    def test_path_traversal_encoded(self):
        # URLエンコードされたパストラバーサルを拒絶
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("..%2Fsecret")

    def test_path_traversal_double_encoded(self):
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("%2e%2e%2fsecret")

    def test_path_traversal_mixed(self):
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("foo/../../etc/passwd")

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_path("")

    def test_none_rejected(self):
        with pytest.raises(ValidationError):
            validate_path(None)  # type: ignore


# --- validate_resource_id ---

class TestValidateResourceId:
    def test_valid_id_passes(self):
        assert validate_resource_id("proj-abc123") == "proj-abc123"

    def test_query_param_injection(self):
        with pytest.raises(ValidationError, match="invalid character"):
            validate_resource_id("proj?admin=true")

    def test_fragment_injection(self):
        with pytest.raises(ValidationError, match="invalid character"):
            validate_resource_id("proj#fragment")

    def test_percent_encoding_injection(self):
        with pytest.raises(ValidationError, match="invalid character"):
            validate_resource_id("proj%20id")

    def test_empty_id_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_resource_id("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            validate_resource_id("   ")


# --- validate_string ---

class TestValidateString:
    def test_valid_string_passes(self):
        assert validate_string("Hello, World!") == "Hello, World!"

    def test_null_byte_rejected(self):
        with pytest.raises(ValidationError, match="control character"):
            validate_string("hello\x00world")

    def test_control_character_rejected(self):
        # 0x1F (Unit Separator) など 0x20未満のコントロール文字
        with pytest.raises(ValidationError, match="control character"):
            validate_string("hello\x1fworld")

    def test_tab_allowed(self):
        # タブ（0x09）は許可
        assert validate_string("hello\tworld") == "hello\tworld"

    def test_newline_allowed(self):
        # 改行（0x0A）は許可
        assert validate_string("hello\nworld") == "hello\nworld"

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_string("")
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_validation.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/core/validation.py
"""入力バリデーション — エージェントが生成する典型的な誤りを拒絶する。

検証関数はすべて値をそのまま返す（型変換は行わない）。
バリデーション失敗時は ValidationError を送出する。
"""
from __future__ import annotations

import re
import urllib.parse

from davinci_cli.core.exceptions import ValidationError

# パストラバーサルパターン（デコード後に検査）
_PATH_TRAVERSAL_RE = re.compile(r"\.\.")

# リソースID禁止文字
_RESOURCE_ID_INVALID_CHARS_RE = re.compile(r"[?#%\s]")

# 許可するコントロール文字（タブ=0x09、LF=0x0A、CR=0x0D）
_ALLOWED_CONTROLS = {"\t", "\n", "\r"}


def validate_path(path: str | None) -> str:
    """ファイルパスを検証する。

    - None または空文字を拒絶
    - パストラバーサル（../ など）を拒絶（URLデコード後も検査）
    """
    if path is None or not isinstance(path, str):
        raise ValidationError(field="path", reason="must be a non-null string")
    if not path.strip():
        raise ValidationError(field="path", reason="empty path is not allowed")

    # URLデコードを最大2回施してから検査（ダブルエンコード対策）
    decoded = path
    for _ in range(2):
        decoded = urllib.parse.unquote(decoded)

    if _PATH_TRAVERSAL_RE.search(decoded):
        raise ValidationError(field="path", reason="path traversal detected")

    return path


def validate_resource_id(resource_id: str | None) -> str:
    """リソースIDを検証する。

    - None または空文字を拒絶
    - ?、#、%、空白を含む値を拒絶（クエリパラム混入・エンコードインジェクション対策）
    """
    if resource_id is None or not isinstance(resource_id, str):
        raise ValidationError(field="resource_id", reason="must be a non-null string")
    if not resource_id.strip():
        raise ValidationError(field="resource_id", reason="empty resource ID is not allowed")
    if _RESOURCE_ID_INVALID_CHARS_RE.search(resource_id):
        raise ValidationError(
            field="resource_id",
            reason="invalid character detected (?, #, %, or whitespace)",
        )
    return resource_id


def validate_string(value: str | None) -> str:
    """汎用文字列を検証する。

    - None または空文字を拒絶
    - 0x20未満のコントロール文字（タブ・LF・CR を除く）を拒絶
    """
    if value is None or not isinstance(value, str):
        raise ValidationError(field="value", reason="must be a non-null string")
    if not value:
        raise ValidationError(field="value", reason="empty string is not allowed")

    for ch in value:
        code = ord(ch)
        if code < 0x20 and ch not in _ALLOWED_CONTROLS:
            raise ValidationError(
                field="value",
                reason=f"control character detected (U+{code:04X})",
            )
    return value
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_validation.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/validation.py tests/unit/test_validation.py
git commit -m "feat: core/validation.py — パストラバーサル・コントロール文字・インジェクション拒絶"
```

---

### Task 4: core/environment.py（macOS/Windows環境変数自動検出）

**Files:**
- Create: `src/davinci_cli/core/environment.py`
- Test: `tests/unit/test_environment.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_environment.py
import os
import sys
import importlib
from unittest.mock import patch
import pytest

from davinci_cli.core.environment import (
    get_default_paths,
    setup_environment,
    PLATFORM_MACOS,
    PLATFORM_WINDOWS,
)
from davinci_cli.core.exceptions import EnvironmentError as DavinciEnvError


class TestGetDefaultPaths:
    def test_macos_paths(self):
        paths = get_default_paths(PLATFORM_MACOS)
        assert paths["RESOLVE_SCRIPT_API"].startswith("/Library/Application Support")
        assert paths["RESOLVE_SCRIPT_LIB"].startswith("/Applications")
        assert paths["RESOLVE_MODULES"].startswith("/Library/Application Support")

    def test_windows_paths(self):
        paths = get_default_paths(PLATFORM_WINDOWS)
        assert "ProgramData" in paths["RESOLVE_SCRIPT_API"]
        assert "Program Files" in paths["RESOLVE_SCRIPT_LIB"]
        assert "Modules" in paths["RESOLVE_MODULES"]

    def test_unknown_platform_raises(self):
        with pytest.raises(DavinciEnvError, match="Unsupported platform"):
            get_default_paths("linux")


class TestSetupEnvironment:
    def test_env_vars_set_from_defaults_on_macos(self, monkeypatch):
        monkeypatch.delenv("RESOLVE_SCRIPT_API", raising=False)
        monkeypatch.delenv("RESOLVE_SCRIPT_LIB", raising=False)
        monkeypatch.delenv("RESOLVE_MODULES", raising=False)

        with patch("davinci_cli.core.environment._current_platform", return_value=PLATFORM_MACOS):
            setup_environment()

        assert "RESOLVE_SCRIPT_API" in os.environ
        assert os.environ["RESOLVE_SCRIPT_API"].startswith("/Library")

    def test_existing_env_vars_not_overwritten(self, monkeypatch):
        monkeypatch.setenv("RESOLVE_SCRIPT_API", "/custom/path")

        with patch("davinci_cli.core.environment._current_platform", return_value=PLATFORM_MACOS):
            setup_environment()

        assert os.environ["RESOLVE_SCRIPT_API"] == "/custom/path"

    def test_modules_added_to_sys_path(self, monkeypatch):
        monkeypatch.delenv("RESOLVE_MODULES", raising=False)

        with patch("davinci_cli.core.environment._current_platform", return_value=PLATFORM_MACOS):
            setup_environment()

        modules_path = os.environ["RESOLVE_MODULES"]
        assert modules_path in sys.path
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_environment.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/core/environment.py
"""DaVinci Resolve Python API 接続のための環境変数自動設定。

優先順位:
  1. 既存の環境変数（ユーザー設定を尊重）
  2. プラットフォーム別のデフォルトパス
"""
from __future__ import annotations

import os
import sys
from typing import Literal

from davinci_cli.core.exceptions import EnvironmentError as DavinciEnvError

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
    """指定プラットフォームのデフォルトパスを返す。"""
    if platform == PLATFORM_MACOS:
        return dict(_MACOS_DEFAULTS)
    if platform == PLATFORM_WINDOWS:
        return dict(_WINDOWS_DEFAULTS)
    raise DavinciEnvError(f"Unsupported platform: {platform!r}. Supported: darwin, win32")


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
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_environment.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/environment.py tests/unit/test_environment.py
git commit -m "feat: core/environment.py — macOS/Windows デフォルトパス自動設定、既存env尊重"
```

---

### Task 5: core/connection.py（Resolve API接続）

**Files:**
- Create: `src/davinci_cli/core/connection.py`
- Create: `tests/mocks/resolve_mock.py`
- Test: `tests/unit/test_connection.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_connection.py
import pytest
from unittest.mock import patch, MagicMock

from davinci_cli.core.connection import get_resolve, clear_resolve_cache
from davinci_cli.core.exceptions import ResolveNotRunningError


class TestGetResolve:
    def setup_method(self):
        """各テスト前にキャッシュをクリア"""
        clear_resolve_cache()

    def test_returns_resolve_object_when_running(self):
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch("davinci_cli.core.connection._import_resolve_script", return_value=mock_dvr):
            result = get_resolve()

        assert result is mock_resolve
        mock_dvr.scriptapp.assert_called_once_with("Resolve")

    def test_raises_when_resolve_not_running(self):
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = None  # Resolve未起動時はNoneを返す

        with patch("davinci_cli.core.connection._import_resolve_script", return_value=mock_dvr):
            with pytest.raises(ResolveNotRunningError):
                get_resolve()

    def test_caches_resolve_object(self):
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch("davinci_cli.core.connection._import_resolve_script", return_value=mock_dvr):
            result1 = get_resolve()
            result2 = get_resolve()

        assert result1 is result2
        # scriptappは1回しか呼ばれない（キャッシュが効いている）
        assert mock_dvr.scriptapp.call_count == 1

    def test_clear_cache_allows_reconnect(self):
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch("davinci_cli.core.connection._import_resolve_script", return_value=mock_dvr):
            get_resolve()
            clear_resolve_cache()
            get_resolve()

        assert mock_dvr.scriptapp.call_count == 2

    def test_import_error_propagates_as_environment_error(self):
        from davinci_cli.core.exceptions import EnvironmentError as DavinciEnvError

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            side_effect=ImportError("No module named 'DaVinciResolveScript'"),
        ):
            with pytest.raises(DavinciEnvError, match="DaVinciResolveScript"):
                get_resolve()
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_connection.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/core/connection.py
"""DaVinci Resolve Python API への接続管理。

_import_resolve_script は lru_cache でキャッシュされるが、
テスト時は clear_resolve_cache() でリセット可能。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from davinci_cli.core.environment import setup_environment
from davinci_cli.core.exceptions import (
    EnvironmentError as DavinciEnvError,
    ResolveNotRunningError,
)


@lru_cache(maxsize=1)
def _import_resolve_script() -> Any:
    """DaVinciResolveScript モジュールをインポートしてキャッシュする。

    環境変数のセットアップは初回インポート時に1度だけ実行する。
    """
    setup_environment()
    try:
        import DaVinciResolveScript as dvr  # type: ignore[import]
        return dvr
    except ImportError as exc:
        raise DavinciEnvError(
            f"Could not import DaVinciResolveScript: {exc}. "
            "Ensure DaVinci Resolve is installed and RESOLVE_MODULES is set correctly."
        ) from exc


def get_resolve() -> Any:
    """Resolve オブジェクトを返す。

    DaVinci Resolve が起動していない場合は ResolveNotRunningError を送出する。
    """
    dvr = _import_resolve_script()
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise ResolveNotRunningError()
    return resolve


def clear_resolve_cache() -> None:
    """接続キャッシュをクリアする（テスト・再接続用）。"""
    _import_resolve_script.cache_clear()
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_connection.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/connection.py tests/unit/test_connection.py
git commit -m "feat: core/connection.py — lru_cache付きResolve接続、未起動時に明示的エラー"
```

---

### Task 6: core/edition.py（Free/Studio判定）

**Files:**
- Create: `src/davinci_cli/core/edition.py`
- Test: `tests/unit/test_edition.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_edition.py
import pytest
from unittest.mock import MagicMock

from davinci_cli.core.edition import (
    get_edition,
    require_studio,
    Edition,
    EDITION_FREE,
    EDITION_STUDIO,
)
from davinci_cli.core.exceptions import EditionError


class TestGetEdition:
    def test_detects_studio(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {
            "product": "DaVinci Resolve Studio"
        }
        assert get_edition(mock_resolve) == EDITION_STUDIO

    def test_detects_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {
            "product": "DaVinci Resolve"
        }
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_unknown_product_treated_as_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "Unknown"}
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_edition_is_string_constant(self):
        assert isinstance(EDITION_FREE, str)
        assert isinstance(EDITION_STUDIO, str)


class TestRequireStudio:
    def test_passes_when_studio(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "DaVinci Resolve Studio"}
        # 例外が発生しないこと
        require_studio(mock_resolve)

    def test_raises_when_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "DaVinci Resolve"}
        with pytest.raises(EditionError) as exc_info:
            require_studio(mock_resolve)
        assert "Studio" in str(exc_info.value)
        assert "Free" in str(exc_info.value)
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_edition.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/core/edition.py
"""DaVinci Resolve エディション（Free / Studio）判定。"""
from __future__ import annotations

from typing import Any

from davinci_cli.core.exceptions import EditionError

# エディション定数
EDITION_FREE = "Free"
EDITION_STUDIO = "Studio"

# 型エイリアス
Edition = str


def get_edition(resolve: Any) -> Edition:
    """Resolve オブジェクトからエディションを検出する。

    GetVersion() が {"product": "DaVinci Resolve Studio"} を返す場合は Studio、
    それ以外は Free として扱う。
    """
    version_info: dict = resolve.GetVersion() or {}
    product: str = version_info.get("product", "")
    if "Studio" in product:
        return EDITION_STUDIO
    return EDITION_FREE


def require_studio(resolve: Any) -> None:
    """Studio エディションでなければ EditionError を送出する。"""
    edition = get_edition(resolve)
    if edition != EDITION_STUDIO:
        raise EditionError(required=EDITION_STUDIO, actual=edition)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_edition.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/edition.py tests/unit/test_edition.py
git commit -m "feat: core/edition.py — Free/Studio判定とrequire_studio guard"
```

---

### Task 7: output/formatter.py（NDJSON/JSON/pretty, --fields対応）

**Files:**
- Create: `src/davinci_cli/output/__init__.py`
- Create: `src/davinci_cli/output/formatter.py`
- Test: `tests/unit/test_formatter.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_formatter.py
import json
import sys
import io
import pytest
from unittest.mock import patch

from davinci_cli.output.formatter import (
    is_tty,
    filter_fields,
    output,
)


class TestIsTty:
    def test_returns_false_when_not_tty(self, capsys):
        # pytest実行中はTTYではない
        assert is_tty() is False

    def test_returns_true_when_tty(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            assert is_tty() is True


class TestFilterFields:
    def test_filters_dict(self):
        data = {"name": "MyProject", "fps": 24, "secret": "hidden"}
        result = filter_fields(data, ["name", "fps"])
        assert result == {"name": "MyProject", "fps": 24}
        assert "secret" not in result

    def test_filters_list_of_dicts(self):
        data = [
            {"id": 1, "name": "A", "extra": "x"},
            {"id": 2, "name": "B", "extra": "y"},
        ]
        result = filter_fields(data, ["id", "name"])
        assert result == [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]

    def test_missing_fields_skipped(self):
        data = {"name": "MyProject"}
        result = filter_fields(data, ["name", "nonexistent"])
        assert result == {"name": "MyProject"}
        assert "nonexistent" not in result

    def test_none_fields_returns_original(self):
        data = {"name": "MyProject", "fps": 24}
        result = filter_fields(data, None)
        assert result == data


class TestOutput:
    def test_dict_outputs_json_line(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output({"name": "MyProject", "fps": 24})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed == {"name": "MyProject", "fps": 24}

    def test_list_outputs_ndjson(self, capsys):
        data = [{"id": 1}, {"id": 2}]
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output(data)
        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().split("\n") if l]
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"id": 1}
        assert json.loads(lines[1]) == {"id": 2}

    def test_fields_filtering_applied(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output({"name": "MyProject", "fps": 24, "secret": "hidden"}, fields=["name"])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert "name" in parsed
        assert "secret" not in parsed
        assert "fps" not in parsed

    def test_pretty_mode_tty(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=True):
            output({"name": "MyProject"}, pretty=True)
        captured = capsys.readouterr()
        # Rich を使うため JSON より人間が読みやすい形式になる（改行等が含まれる）
        assert "MyProject" in captured.out

    def test_non_tty_ignores_pretty_flag(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output({"name": "MyProject"}, pretty=True)
        captured = capsys.readouterr()
        # 非TTYでは pretty=True でも JSON 出力
        parsed = json.loads(captured.out.strip())
        assert parsed["name"] == "MyProject"
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_formatter.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/output/formatter.py
"""出力フォーマッタ — エージェントファースト出力設計。

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
    data: dict | list,
    fields: list[str] | None,
) -> dict | list:
    """指定フィールドのみを残す。fields が None の場合は無変換で返す。"""
    if fields is None:
        return data

    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in fields}

    if isinstance(data, list):
        return [{k: v for k, v in item.items() if k in fields} for item in data]

    return data


def output(
    data: dict | list,
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
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_formatter.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/output/__init__.py src/davinci_cli/output/formatter.py \
        tests/unit/test_formatter.py
git commit -m "feat: output/formatter.py — NDJSON自動出力・--fields絞り込み・Rich pretty"
```

---

### Task 8: tests/mocks/resolve_mock.py（MockResolve）

**Files:**
- Create: `tests/mocks/resolve_mock.py`
- Test: `tests/unit/test_resolve_mock.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_resolve_mock.py
import pytest
from tests.mocks.resolve_mock import MockResolve, MockProjectManager, MockProject


class TestMockResolve:
    def test_get_version_returns_dict(self):
        resolve = MockResolve()
        version = resolve.GetVersion()
        assert isinstance(version, dict)
        assert "product" in version
        assert "DaVinci Resolve" in version["product"]

    def test_get_project_manager_returns_mock(self):
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        assert isinstance(pm, MockProjectManager)

    def test_studio_edition(self):
        resolve = MockResolve(studio=True)
        assert "Studio" in resolve.GetVersion()["product"]

    def test_free_edition(self):
        resolve = MockResolve(studio=False)
        assert "Studio" not in resolve.GetVersion()["product"]


class TestMockProjectManager:
    def test_get_current_project_returns_mock(self):
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        assert isinstance(project, MockProject)

    def test_get_current_project_returns_none_when_no_project(self):
        resolve = MockResolve(has_project=False)
        pm = resolve.GetProjectManager()
        assert pm.GetCurrentProject() is None

    def test_get_project_list_returns_list(self):
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        projects = pm.GetProjectListInCurrentFolder()
        assert isinstance(projects, list)


class TestMockProject:
    def test_get_name(self):
        project = MockProject(name="MyProject")
        assert project.GetName() == "MyProject"

    def test_get_timeline_count(self):
        project = MockProject(timeline_count=3)
        assert project.GetTimelineCount() == 3

    def test_get_current_timeline_returns_none_when_no_timeline(self):
        project = MockProject(timeline_count=0)
        assert project.GetCurrentTimeline() is None

    def test_scriptapp_returns_resolve(self):
        """DaVinciResolveScript.scriptapp() のモック"""
        from tests.mocks.resolve_mock import MockDaVinciResolveScript
        dvr = MockDaVinciResolveScript()
        resolve = dvr.scriptapp("Resolve")
        assert isinstance(resolve, MockResolve)
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_resolve_mock.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# tests/mocks/resolve_mock.py
"""DaVinci Resolve Python API の軽量モック実装。

実際の DaVinci Resolve や DaVinciResolveScript が不要な状態で
unit test を実行できるようにするための純粋 Python 実装。

使用例:
    from tests.mocks.resolve_mock import MockDaVinciResolveScript
    dvr = MockDaVinciResolveScript()
    resolve = dvr.scriptapp("Resolve")
"""
from __future__ import annotations

from typing import Optional


class MockTimeline:
    """タイムラインのモック。"""

    def __init__(self, name: str = "Timeline 1") -> None:
        self._name = name

    def GetName(self) -> str:
        return self._name

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return 240

    def GetTrackCount(self, track_type: str) -> int:
        return 2


class MockProject:
    """プロジェクトのモック。"""

    def __init__(
        self,
        name: str = "Untitled Project",
        timeline_count: int = 1,
    ) -> None:
        self._name = name
        self._timeline_count = timeline_count
        self._timelines = [
            MockTimeline(f"Timeline {i + 1}") for i in range(timeline_count)
        ]

    def GetName(self) -> str:
        return self._name

    def GetTimelineCount(self) -> int:
        return self._timeline_count

    def GetCurrentTimeline(self) -> Optional[MockTimeline]:
        if not self._timelines:
            return None
        return self._timelines[0]

    def GetTimelineByIndex(self, index: int) -> Optional[MockTimeline]:
        try:
            return self._timelines[index - 1]  # DaVinci API は 1-indexed
        except IndexError:
            return None

    def GetSetting(self, key: str) -> str:
        _defaults = {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }
        return _defaults.get(key, "")


class MockProjectManager:
    """プロジェクトマネージャーのモック。"""

    def __init__(
        self,
        has_project: bool = True,
        project_name: str = "Untitled Project",
    ) -> None:
        self._current_project = MockProject(project_name) if has_project else None
        self._project_names = [project_name] if has_project else []

    def GetCurrentProject(self) -> Optional[MockProject]:
        return self._current_project

    def GetProjectListInCurrentFolder(self) -> list[str]:
        return list(self._project_names)

    def CreateProject(self, name: str) -> Optional[MockProject]:
        project = MockProject(name)
        self._project_names.append(name)
        return project


class MockResolve:
    """DaVinci Resolve アプリケーションオブジェクトのモック。"""

    def __init__(
        self,
        studio: bool = False,
        has_project: bool = True,
        project_name: str = "Untitled Project",
    ) -> None:
        self._studio = studio
        self._project_manager = MockProjectManager(
            has_project=has_project,
            project_name=project_name,
        )

    def GetVersion(self) -> dict:
        product = "DaVinci Resolve Studio" if self._studio else "DaVinci Resolve"
        return {
            "product": product,
            "major": 19,
            "minor": 0,
            "patch": 0,
            "build": 0,
            "suffix": "",
        }

    def GetVersionString(self) -> str:
        product = "DaVinci Resolve Studio" if self._studio else "DaVinci Resolve"
        return f"{product} 19.0.0b0"

    def GetProjectManager(self) -> MockProjectManager:
        return self._project_manager

    def OpenPage(self, page_name: str) -> bool:
        valid_pages = {"media", "cut", "edit", "fusion", "color", "fairlight", "deliver"}
        return page_name in valid_pages

    def GetCurrentPage(self) -> str:
        return "edit"

    def Quit(self) -> None:
        pass


class MockDaVinciResolveScript:
    """DaVinciResolveScript モジュールのモック。

    テスト内で以下のようにパッチして使用する:
        with patch("davinci_cli.core.connection._import_resolve_script",
                   return_value=MockDaVinciResolveScript()):
            resolve = get_resolve()
    """

    def __init__(self, studio: bool = False, has_project: bool = True) -> None:
        self._resolve = MockResolve(studio=studio, has_project=has_project)

    def scriptapp(self, app_name: str) -> Optional[MockResolve]:
        if app_name == "Resolve":
            return self._resolve
        return None
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_resolve_mock.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add tests/mocks/resolve_mock.py tests/unit/test_resolve_mock.py
git commit -m "feat: tests/mocks/resolve_mock.py — Resolve API完全モック、実Resolve不要でテスト可能"
```

---

## Phase 1 完了確認

全タスク完了後、以下を実行して Phase 1 全体が通ることを確認する。

```bash
python -m pytest tests/unit/ -v --tb=short
```

Expected: 全テスト PASS（ImportError / AssertionError なし）

### ディレクトリ構造（Phase 1 完了時）

```
davinci-cli/
├── pyproject.toml
├── src/
│   └── davinci_cli/
│       ├── __init__.py          # __version__
│       ├── cli.py               # dr コマンドエントリポイント
│       ├── core/
│       │   ├── __init__.py
│       │   ├── exceptions.py    # 例外階層 + exit_code
│       │   ├── validation.py    # パストラバーサル・コントロール文字拒絶
│       │   ├── environment.py   # macOS/Windows パス自動設定
│       │   ├── connection.py    # lru_cache付きResolve接続
│       │   └── edition.py       # Free/Studio判定
│       └── output/
│           ├── __init__.py
│           └── formatter.py     # NDJSON/JSON/Rich pretty
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── __init__.py
    │   ├── test_project_setup.py
    │   ├── test_exceptions.py
    │   ├── test_validation.py
    │   ├── test_environment.py
    │   ├── test_connection.py
    │   ├── test_edition.py
    │   ├── test_formatter.py
    │   └── test_resolve_mock.py
    └── mocks/
        ├── __init__.py
        └── resolve_mock.py      # MockResolve / MockDaVinciResolveScript
```

### Phase 2 への引き継ぎ事項

- Phase 2 では `commands/` 層（project・timeline・media pool サブコマンド）を構築する
- `dr schema <command>` の自己解決機能は Phase 2 で追加
- MCP サーバー（`dr-mcp`）は Phase 3
- `--dry-run` グローバルフラグは Phase 2 のコマンド層で実装
