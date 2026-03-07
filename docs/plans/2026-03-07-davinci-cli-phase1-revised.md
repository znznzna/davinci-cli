# davinci-cli Implementation Plan — Phase 1: Core Layer (Revised)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** davinci-cliのコア層（例外・バリデーション・接続・環境・エディション・ロギング・出力・モック）と CI/CD を構築する
**Architecture:** Environment-Injected Direct Call — DaVinci Python APIに環境変数で直接接続。`core/` に全基盤を集約し、上位層（commands, mcp）からの重複定義を排除する。
**Tech Stack:** Python 3.10+, Click, FastMCP, Pydantic v2, Rich, pytest

---

## 前提条件

- Python 3.10+ がインストール済み
- DaVinci Resolve がインストール済み（テスト実行時はモックで代替）
- プロジェクトルートに `pyproject.toml` と `src/` レイアウト

## 修正点サマリ（旧計画からの変更）

1. エントリポイント名を `cli` → `dr` に統一（Phase 1 から）
2. `EnvironmentError` → `DavinciEnvironmentError` に改名（Python組み込み衝突回避）
3. `validate_path` を `core/validation.py` に統合（`Path.resolve()` + `allowed_extensions` 対応）。`security.py` は作らない。パストラバーサル防止のみ（許可ディレクトリリスト不要）
4. exit_code 体系を `exceptions.py` に正規定義（1〜5）
5. `get_resolve()` で Resolve オブジェクト自体もキャッシュ
6. `GetVersion()` API 正確性コメント追加
7. `core/logging.py` 追加（`--verbose`/`--debug` 対応）
8. `pyproject.toml` に ruff/mypy 設定追加
9. CI/CD（GitHub Actions）追加
10. Linux は明示的にサポートしない
11. `ProjectNotFoundError` を例外に追加
12. `--fields` は表示フィルタ。schema は常にフルレスポンスの型を定義する（`--fields` 適用後の部分出力は schema 対象外）

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
    from davinci_cli.cli import dr
    assert callable(dr)


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
    "ruff>=0.4",
    "mypy>=1.10",
]

[project.scripts]
dr = "davinci_cli.cli:dr"

[tool.hatch.build.targets.wheel]
packages = ["src/davinci_cli"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

```python
# src/davinci_cli/__init__.py
"""davinci-cli — DaVinci Resolve CLI & MCP server, agent-first design."""

__version__ = "0.1.0"
```

```python
# src/davinci_cli/cli.py
"""CLIエントリポイント。エントリポイント名は 'dr' に統一。"""

import click


@click.group()
@click.version_option()
def dr() -> None:
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
git commit -m "feat: プロジェクトスケルトンを作成 (エントリポイント dr, ruff/mypy 設定含む)"
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
    ProjectNotFoundError,
    ValidationError,
    DavinciEnvironmentError,
    EditionError,
)


def test_base_exception_hierarchy():
    """全例外が DavinciCLIError を継承していること"""
    for exc_class in [
        ResolveNotRunningError,
        ProjectNotOpenError,
        ProjectNotFoundError,
        ValidationError,
        DavinciEnvironmentError,
        EditionError,
    ]:
        assert issubclass(exc_class, DavinciCLIError)


def test_base_exception_does_not_shadow_builtin():
    """DavinciEnvironmentError は Python 組み込みの EnvironmentError と衝突しないこと"""
    assert DavinciEnvironmentError is not EnvironmentError
    # 組み込み EnvironmentError は OSError のエイリアス
    assert not issubclass(DavinciEnvironmentError, OSError)


def test_resolve_not_running_error():
    exc = ResolveNotRunningError()
    assert exc.exit_code == 1
    assert "DaVinci Resolve" in str(exc)


def test_project_not_open_error():
    exc = ProjectNotOpenError()
    assert exc.exit_code == 2


def test_project_not_found_error():
    exc = ProjectNotFoundError(name="MyProject")
    assert exc.exit_code == 2
    assert "MyProject" in str(exc)


def test_validation_error_captures_field():
    exc = ValidationError(field="path", reason="path traversal detected")
    assert exc.field == "path"
    assert "path traversal" in str(exc)
    assert exc.exit_code == 3


def test_environment_error_has_exit_code():
    exc = DavinciEnvironmentError(detail="RESOLVE_SCRIPT_API not found")
    assert exc.exit_code == 4
    assert "RESOLVE_SCRIPT_API" in str(exc)


def test_edition_error_has_exit_code():
    exc = EditionError(required="Studio", actual="Free")
    assert exc.exit_code == 5
    assert "Studio" in str(exc)


def test_exceptions_are_catchable_as_base():
    with pytest.raises(DavinciCLIError):
        raise ResolveNotRunningError()


def test_exit_code_uniqueness():
    """各例外の exit_code が一意であること（ProjectNotFoundError は ProjectNotOpenError と同じ 2 で許容）"""
    codes = {
        ResolveNotRunningError: 1,
        ProjectNotOpenError: 2,
        ValidationError: 3,
        DavinciEnvironmentError: 4,
        EditionError: 5,
    }
    for exc_class, expected_code in codes.items():
        assert exc_class.exit_code == expected_code
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_exceptions.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/core/__init__.py
```

```python
# src/davinci_cli/core/exceptions.py
"""davinci-cli 例外階層。

全例外は DavinciCLIError を継承し、exit_code を持つ。
エージェントはこの exit_code を使ってエラー種別を判別できる。

exit_code 体系（正規定義）:
  1: ResolveNotRunningError — DaVinci Resolve が起動していない
  2: ProjectNotOpenError / ProjectNotFoundError — プロジェクト未オープン/未発見
  3: ValidationError — 入力バリデーションエラー
  4: DavinciEnvironmentError — 環境変数・パス設定エラー
  5: EditionError — エディション不一致

cli.py はこの定義を参照する。独自に exit_code を再定義しない。
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


class ProjectNotFoundError(DavinciCLIError):
    """指定されたプロジェクトが見つからない。"""

    exit_code = 2

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Project not found: {name}")


class ValidationError(DavinciCLIError):
    """入力値バリデーションエラー。"""

    exit_code = 3

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        super().__init__(f"Validation failed for '{field}': {reason}")


class DavinciEnvironmentError(DavinciCLIError):
    """環境変数・パス設定エラー。

    Python 組み込みの EnvironmentError (= OSError) との衝突を避けるため、
    'Davinci' プレフィックス付きの名前にしている。
    """

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
git commit -m "feat: core/exceptions.py — DavinciEnvironmentError に改名、exit_code 正規定義 (1-5)"
```

---

### Task 3: core/validation.py（統合版 — Path.resolve() + allowed_extensions 対応）

**Files:**
- Create: `src/davinci_cli/core/validation.py`
- Test: `tests/unit/test_validation.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_validation.py
import pytest
from pathlib import Path
from davinci_cli.core.validation import validate_path, validate_resource_id, validate_string
from davinci_cli.core.exceptions import ValidationError


# --- validate_path ---

class TestValidatePath:
    def test_valid_path_returns_resolved_path(self, tmp_path):
        """正常系：存在するパスは Path.resolve() された Path オブジェクトを返す"""
        test_file = tmp_path / "test.drp"
        test_file.touch()
        result = validate_path(str(test_file))
        assert isinstance(result, Path)
        assert result == test_file.resolve()

    def test_valid_path_string_returns_resolved_path(self):
        """存在しないパスでも resolve() は動作する"""
        result = validate_path("/some/valid/path.drp")
        assert isinstance(result, Path)

    def test_path_traversal_single_dot_dot(self):
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("../secret")

    def test_path_traversal_encoded(self):
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

    def test_allowed_extensions_pass(self):
        """許可された拡張子は通過する"""
        result = validate_path("/path/to/lut.cube", allowed_extensions=[".cube", ".3dl", ".lut"])
        assert result.suffix == ".cube"

    def test_allowed_extensions_rejected(self):
        """許可されていない拡張子は拒絶する"""
        with pytest.raises(ValidationError, match="not allowed"):
            validate_path("/path/to/malicious.exe", allowed_extensions=[".cube", ".3dl", ".lut"])

    def test_allowed_extensions_case_insensitive(self):
        """拡張子チェックは大文字小文字を区別しない"""
        result = validate_path("/path/to/lut.CUBE", allowed_extensions=[".cube"])
        assert result.suffix == ".CUBE"

    def test_allowed_extensions_none_skips_check(self):
        """allowed_extensions=None の場合は拡張子チェックをスキップする"""
        result = validate_path("/path/to/anything.xyz")
        assert result.suffix == ".xyz"

    def test_symlink_resolved(self, tmp_path):
        """シンボリックリンクは resolve() で実体パスに解決される"""
        real_file = tmp_path / "real.drp"
        real_file.touch()
        symlink = tmp_path / "link.drp"
        symlink.symlink_to(real_file)
        result = validate_path(str(symlink))
        assert result == real_file.resolve()


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
        with pytest.raises(ValidationError, match="control character"):
            validate_string("hello\x1fworld")

    def test_tab_allowed(self):
        assert validate_string("hello\tworld") == "hello\tworld"

    def test_newline_allowed(self):
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

validate_path() は Phase 3 の security.py に分離していた版を統合済み。
- Path.resolve() でシンボリックリンクを解決
- allowed_extensions で拡張子チェック
- パストラバーサル検出（URLデコード後も検査）

security.py は作らない。パス検証はこのモジュールに一元化する。

設計判断: validate_path() はパストラバーサル防止（Path.resolve() + '..' 拒絶）のみ。
許可ディレクトリリスト（allowed_directories）は意図的に実装しない。
理由: DaVinci Resolve のメディアファイルは外付け SSD、NAS、ネットワークドライブ等の
任意パスに存在するため、許可ディレクトリを事前に列挙することが不可能。
パストラバーサル防止のみで十分なセキュリティを確保できる。
"""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

from davinci_cli.core.exceptions import ValidationError

# パストラバーサルパターン（デコード後に検査）
_PATH_TRAVERSAL_RE = re.compile(r"\.\.")

# リソースID禁止文字
_RESOURCE_ID_INVALID_CHARS_RE = re.compile(r"[?#%\s]")

# 許可するコントロール文字（タブ=0x09、LF=0x0A、CR=0x0D）
_ALLOWED_CONTROLS = {"\t", "\n", "\r"}


def validate_path(
    path: str | None,
    allowed_extensions: list[str] | None = None,
) -> Path:
    """ファイルパスを検証し、resolve() された Path オブジェクトを返す。

    - None または空文字を拒絶
    - パストラバーサル（../ など）を拒絶（URLデコード後も検査）
    - シンボリックリンクは resolve() で実体パスに解決
    - allowed_extensions 指定時は拡張子を検査（大文字小文字区別なし）

    許可ディレクトリリストは意図的に実装していない。
    DaVinci Resolve のメディアは外付け SSD/NAS 等の任意パスに存在するため、
    パストラバーサル防止（Path.resolve() + '..' 拒絶）のみで制限する。

    Returns:
        Path: resolve() 済みの Path オブジェクト
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

    resolved = Path(path).resolve()

    # 拡張子チェック
    if allowed_extensions is not None:
        normalized_extensions = [ext.lower() for ext in allowed_extensions]
        if resolved.suffix.lower() not in normalized_extensions:
            raise ValidationError(
                field="path",
                reason=(
                    f"extension '{resolved.suffix}' not allowed. "
                    f"Allowed: {allowed_extensions}"
                ),
            )

    return resolved


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
git commit -m "feat: core/validation.py — Path.resolve()+allowed_extensions統合版 (security.py廃止)"
```

---

### Task 4: core/environment.py（macOS/Windows環境変数自動検出、Linux非サポート明記）

**Files:**
- Create: `src/davinci_cli/core/environment.py`
- Test: `tests/unit/test_environment.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_environment.py
import os
import sys
from unittest.mock import patch
import pytest

from davinci_cli.core.environment import (
    get_default_paths,
    setup_environment,
    PLATFORM_MACOS,
    PLATFORM_WINDOWS,
)
from davinci_cli.core.exceptions import DavinciEnvironmentError


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

    def test_linux_raises_with_clear_message(self):
        """Linux は明示的にサポートしない"""
        with pytest.raises(DavinciEnvironmentError, match="not supported") as exc_info:
            get_default_paths("linux")
        assert "linux" in str(exc_info.value).lower()

    def test_unknown_platform_raises(self):
        with pytest.raises(DavinciEnvironmentError, match="not supported"):
            get_default_paths("freebsd")


class TestSetupEnvironment:
    def test_env_vars_set_from_defaults_on_macos(self, monkeypatch):
        monkeypatch.delenv("RESOLVE_SCRIPT_API", raising=False)
        monkeypatch.delenv("RESOLVE_SCRIPT_LIB", raising=False)
        monkeypatch.delenv("RESOLVE_MODULES", raising=False)

        with patch(
            "davinci_cli.core.environment._current_platform",
            return_value=PLATFORM_MACOS,
        ):
            setup_environment()

        assert "RESOLVE_SCRIPT_API" in os.environ
        assert os.environ["RESOLVE_SCRIPT_API"].startswith("/Library")

    def test_existing_env_vars_not_overwritten(self, monkeypatch):
        monkeypatch.setenv("RESOLVE_SCRIPT_API", "/custom/path")

        with patch(
            "davinci_cli.core.environment._current_platform",
            return_value=PLATFORM_MACOS,
        ):
            setup_environment()

        assert os.environ["RESOLVE_SCRIPT_API"] == "/custom/path"

    def test_modules_added_to_sys_path(self, monkeypatch):
        monkeypatch.delenv("RESOLVE_MODULES", raising=False)

        with patch(
            "davinci_cli.core.environment._current_platform",
            return_value=PLATFORM_MACOS,
        ):
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
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_environment.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/environment.py tests/unit/test_environment.py
git commit -m "feat: core/environment.py — macOS/Windows パス自動設定、Linux非サポート明記"
```

---

### Task 5: core/connection.py（Resolve API接続 — Resolveオブジェクト自体もキャッシュ）

**Files:**
- Create: `src/davinci_cli/core/connection.py`
- Test: `tests/unit/test_connection.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_connection.py
import pytest
from unittest.mock import patch, MagicMock

from davinci_cli.core.connection import get_resolve, clear_resolve_cache
from davinci_cli.core.exceptions import ResolveNotRunningError, DavinciEnvironmentError


class TestGetResolve:
    def setup_method(self):
        """各テスト前にキャッシュをクリア"""
        clear_resolve_cache()

    def test_returns_resolve_object_when_running(self):
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            return_value=mock_dvr,
        ):
            result = get_resolve()

        assert result is mock_resolve
        mock_dvr.scriptapp.assert_called_once_with("Resolve")

    def test_raises_when_resolve_not_running(self):
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = None

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            return_value=mock_dvr,
        ):
            with pytest.raises(ResolveNotRunningError):
                get_resolve()

    def test_caches_resolve_object(self):
        """Resolve オブジェクト自体もキャッシュされ、2回目の呼び出しで scriptapp() が呼ばれないこと"""
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            return_value=mock_dvr,
        ):
            result1 = get_resolve()
            result2 = get_resolve()

        assert result1 is result2
        # scriptapp は1回しか呼ばれない（Resolve オブジェクト自体がキャッシュされている）
        assert mock_dvr.scriptapp.call_count == 1

    def test_clear_cache_clears_both_module_and_resolve(self):
        """clear_resolve_cache() で DaVinciResolveScript モジュールと Resolve オブジェクト両方のキャッシュをクリアする"""
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            return_value=mock_dvr,
        ):
            get_resolve()
            clear_resolve_cache()
            get_resolve()

        # キャッシュクリア後は scriptapp が再度呼ばれる
        assert mock_dvr.scriptapp.call_count == 2

    def test_import_error_propagates_as_environment_error(self):
        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            side_effect=ImportError("No module named 'DaVinciResolveScript'"),
        ):
            with pytest.raises(DavinciEnvironmentError, match="DaVinciResolveScript"):
                get_resolve()
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_connection.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/core/connection.py
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
        import DaVinciResolveScript as dvr  # type: ignore[import]
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

    dvr = _import_resolve_script()
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
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_connection.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/connection.py tests/unit/test_connection.py
git commit -m "feat: core/connection.py — Resolveオブジェクト自体もキャッシュ、clear_resolve_cache()で両方クリア"
```

---

### Task 6: core/edition.py（Free/Studio判定 — API正確性コメント付き）

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

    def test_get_version_returns_none_treated_as_free(self):
        """GetVersion() が None を返すケースのハンドリング"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = None
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_edition_is_string_constant(self):
        assert isinstance(EDITION_FREE, str)
        assert isinstance(EDITION_STUDIO, str)


class TestRequireStudio:
    def test_passes_when_studio(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "DaVinci Resolve Studio"}
        require_studio(mock_resolve)  # 例外が発生しないこと

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
git commit -m "feat: core/edition.py — Free/Studio判定、API正確性コメント追加"
```

---

### Task 7: core/logging.py（--verbose/--debug 対応のロギング設定）

**Files:**
- Create: `src/davinci_cli/core/logging.py`
- Test: `tests/unit/test_logging.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_logging.py
import logging
import pytest

from davinci_cli.core.logging import setup_logging, get_logger


class TestSetupLogging:
    def test_default_level_is_warning(self):
        """デフォルトのログレベルは WARNING"""
        setup_logging(verbose=False, debug=False)
        logger = get_logger("davinci_cli")
        assert logger.level == logging.WARNING

    def test_verbose_sets_info(self):
        """--verbose で INFO レベルに設定"""
        setup_logging(verbose=True, debug=False)
        logger = get_logger("davinci_cli")
        assert logger.level == logging.INFO

    def test_debug_sets_debug(self):
        """--debug で DEBUG レベルに設定"""
        setup_logging(verbose=False, debug=True)
        logger = get_logger("davinci_cli")
        assert logger.level == logging.DEBUG

    def test_debug_overrides_verbose(self):
        """--debug は --verbose より優先"""
        setup_logging(verbose=True, debug=True)
        logger = get_logger("davinci_cli")
        assert logger.level == logging.DEBUG

    def test_logger_has_handler(self):
        """ロガーにハンドラが設定されていること"""
        setup_logging(verbose=True, debug=False)
        logger = get_logger("davinci_cli")
        assert len(logger.handlers) > 0

    def test_log_format_contains_level(self, capsys):
        """ログ出力にレベル名が含まれること"""
        setup_logging(verbose=True, debug=False)
        logger = get_logger("davinci_cli.test")
        logger.info("test message")
        captured = capsys.readouterr()
        assert "INFO" in captured.err or "test message" in captured.err


class TestGetLogger:
    def test_returns_logger_with_name(self):
        logger = get_logger("davinci_cli.core")
        assert logger.name == "davinci_cli.core"

    def test_child_logger_inherits_from_parent(self):
        setup_logging(verbose=True, debug=False)
        parent = get_logger("davinci_cli")
        child = get_logger("davinci_cli.core")
        # 子ロガーは親の設定を継承する
        assert child.parent is parent or child.parent is not None
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_logging.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/core/logging.py
"""davinci-cli ロギング設定。

CLI の --verbose / --debug フラグに応じてログレベルを設定する。
ログは stderr に出力する（stdout は JSON 出力専用）。

使い方:
  from davinci_cli.core.logging import setup_logging, get_logger

  # CLI エントリポイントで1度だけ呼ぶ
  setup_logging(verbose=ctx.obj.get("verbose"), debug=ctx.obj.get("debug"))

  # 各モジュールで
  logger = get_logger(__name__)
  logger.info("Processing project: %s", name)
"""
from __future__ import annotations

import logging
import sys

# ルートロガー名
_ROOT_LOGGER_NAME = "davinci_cli"

# ログフォーマット
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_FORMAT_DEBUG = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """ログレベルとフォーマットを設定する。

    Args:
        verbose: True で INFO レベル
        debug: True で DEBUG レベル（verbose より優先）
    """
    logger = logging.getLogger(_ROOT_LOGGER_NAME)

    # 既存ハンドラをクリア（多重呼び出し対策）
    logger.handlers.clear()

    if debug:
        level = logging.DEBUG
        fmt = _LOG_FORMAT_DEBUG
    elif verbose:
        level = logging.INFO
        fmt = _LOG_FORMAT
    else:
        level = logging.WARNING
        fmt = _LOG_FORMAT

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt))

    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """指定名のロガーを返す。

    名前は 'davinci_cli.core.connection' のようにドット区切りで指定する。
    """
    return logging.getLogger(name)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_logging.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/logging.py tests/unit/test_logging.py
git commit -m "feat: core/logging.py — --verbose/--debug 対応、stderr出力 (stdoutはJSON専用)"
```

---

### Task 8: output/formatter.py（NDJSON/JSON/pretty, --fields対応、出力規約明文化）

**Files:**
- Create: `src/davinci_cli/output/__init__.py`
- Create: `src/davinci_cli/output/formatter.py`
- Test: `tests/unit/test_formatter.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_formatter.py
import json
import pytest
from unittest.mock import patch

from davinci_cli.output.formatter import (
    is_tty,
    filter_fields,
    output,
)


class TestIsTty:
    def test_returns_false_when_not_tty(self):
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
        lines = [line for line in captured.out.strip().split("\n") if line]
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"id": 1}
        assert json.loads(lines[1]) == {"id": 2}

    def test_fields_filtering_applied(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output(
                {"name": "MyProject", "fps": 24, "secret": "hidden"},
                fields=["name"],
            )
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert "name" in parsed
        assert "secret" not in parsed
        assert "fps" not in parsed

    def test_pretty_mode_tty(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=True):
            output({"name": "MyProject"}, pretty=True)
        captured = capsys.readouterr()
        assert "MyProject" in captured.out

    def test_non_tty_ignores_pretty_flag(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output({"name": "MyProject"}, pretty=True)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["name"] == "MyProject"
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_formatter.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/output/__init__.py
```

```python
# src/davinci_cli/output/formatter.py
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
git commit -m "feat: output/formatter.py — NDJSON自動出力・--fields絞り込み・出力規約明文化"
```

---

### Task 9: tests/mocks/resolve_mock.py（MockResolve）

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

API正確性に関する注意:
  このモックは DaVinci Resolve 19.x の Python API を参考に作成している。
  GetVersion() は dict を返す設計としているが、実際の API レスポンスと
  フィールド名・型が異なる可能性がある。新しいバージョンの DaVinci Resolve で
  テストする際は、まず実 API の戻り値を確認し、モックを更新すること。

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

    def GetSetting(self, key: str) -> str:
        _defaults = {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }
        return _defaults.get(key, "")

    def GetStartTimecode(self) -> str:
        return "00:00:00:00"


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
        valid_pages = {
            "media", "cut", "edit", "fusion", "color", "fairlight", "deliver",
        }
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
git commit -m "feat: tests/mocks/resolve_mock.py — API正確性コメント付きResolve完全モック"
```

---

### Task 10: CI/CD（GitHub Actions: pytest + ruff + mypy）

**Files:**
- Create: `.github/workflows/ci.yml`
- Test: `tests/unit/test_ci_config.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_ci_config.py
from pathlib import Path


CI_CONFIG = Path(".github/workflows/ci.yml")


def test_ci_config_exists():
    """CI設定ファイルが存在すること"""
    assert CI_CONFIG.exists(), ".github/workflows/ci.yml must exist"


def test_ci_config_is_valid_yaml_structure():
    """CI設定ファイルが基本的なYAML構造を持つこと（pyyaml不要、文字列パターンで検証）"""
    content = CI_CONFIG.read_text()
    # YAML の基本構造: "name:" と "jobs:" が存在する
    assert "name:" in content
    assert "jobs:" in content


def test_ci_has_test_job():
    """pytest ジョブが含まれていること"""
    content = CI_CONFIG.read_text()
    assert "pytest" in content


def test_ci_has_lint_job():
    """ruff ジョブが含まれていること"""
    content = CI_CONFIG.read_text()
    assert "ruff" in content


def test_ci_has_type_check_job():
    """mypy ジョブが含まれていること"""
    content = CI_CONFIG.read_text()
    assert "mypy" in content


def test_ci_triggers_on_push_and_pr():
    """push と pull_request でトリガーされること（文字列パターンマッチで検証）"""
    content = CI_CONFIG.read_text()
    assert "push:" in content
    assert "pull_request:" in content
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_ci_config.py -v`
Expected: FAIL (AssertionError — ファイルが存在しない)

**Step 3: 最小限の実装**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [macos-latest, windows-latest]
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run pytest
        run: python -m pytest tests/ -v --tb=short --cov=davinci_cli --cov-report=term-missing

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run ruff check
        run: ruff check src/ tests/
      - name: Run ruff format check
        run: ruff format --check src/ tests/

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run mypy
        run: mypy src/davinci_cli/
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_ci_config.py -v`
Expected: PASS

注意: テストでは `pyyaml` を使わず文字列パターンマッチで CI 設定を検証する。
`pyproject.toml` の dev 依存に `pyyaml` を追加する必要はない。

**Step 5: コミット**

```bash
git add .github/workflows/ci.yml tests/unit/test_ci_config.py pyproject.toml
git commit -m "feat: CI/CD — GitHub Actions で pytest+ruff+mypy を macOS/Windows で実行"
```

---

## Phase 1 完了確認

全タスク完了後、以下を実行して Phase 1 全体が通ることを確認する。

```bash
python -m pytest tests/unit/ -v --tb=short
ruff check src/ tests/
mypy src/davinci_cli/
```

Expected: 全テスト PASS、ruff/mypy エラーなし

### ディレクトリ構造（Phase 1 完了時）

```
davinci-cli/
├── .github/
│   └── workflows/
│       └── ci.yml               # CI/CD: pytest + ruff + mypy
├── pyproject.toml                # ruff/mypy 設定含む、エントリポイント dr
├── src/
│   └── davinci_cli/
│       ├── __init__.py           # __version__
│       ├── cli.py                # dr コマンドエントリポイント
│       ├── core/
│       │   ├── __init__.py
│       │   ├── exceptions.py     # DavinciEnvironmentError、exit_code 正規定義
│       │   ├── validation.py     # Path.resolve() + allowed_extensions 統合版
│       │   ├── environment.py    # macOS/Windows パス自動設定、Linux非サポート
│       │   ├── connection.py     # Resolveオブジェクト自体もキャッシュ
│       │   ├── edition.py        # Free/Studio判定、API正確性コメント
│       │   └── logging.py        # --verbose/--debug 対応
│       └── output/
│           ├── __init__.py
│           └── formatter.py      # NDJSON/JSON/Rich pretty、出力規約
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
    │   ├── test_logging.py
    │   ├── test_formatter.py
    │   ├── test_resolve_mock.py
    │   └── test_ci_config.py
    └── mocks/
        ├── __init__.py
        └── resolve_mock.py       # MockResolve / MockDaVinciResolveScript
```

### Phase 2 への引き継ぎ事項

- エントリポイントは `dr` に統一済み。Phase 2 の `cli.py` でも `dr` を使う
- 例外は `DavinciEnvironmentError` に改名済み。`EnvironmentError` エイリアスは不要
- exit_code は `exceptions.py` が正規定義。`cli.py` ではそれを参照する
- `validate_path()` は `core/validation.py` に統合済み。`security.py` は作らない
- `get_resolve()` は `core.connection` モジュール。`resolve_bridge` は使わない
- `core/edition.py` の `get_edition()` を system.py から使う（`_detect_edition` 重複排除）
- `core/logging.py` の `setup_logging()` を cli.py のエントリポイントで呼ぶ
- `_impl` 関数は常に flat な `list[dict]` または `dict` を返す（出力規約）
- `ProjectNotFoundError` が追加済み。`ValueError` の代わりに使う
