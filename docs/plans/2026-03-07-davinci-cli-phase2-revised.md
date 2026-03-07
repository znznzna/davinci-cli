# davinci-cli Implementation Plan — Phase 2: Commands (Revised)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** CLIエントリーポイント（`dr`）と共通デコレータ、コマンドグループ（system/schema/project/timeline/clip）を構築する
**Architecture:** _impl 純粋関数で CLI/MCP を共有。共通デコレータで `--json`/`--fields`/`--dry-run` を統一。グローバルエラーハンドリングを `invoke` オーバーライドで実装。
**Tech Stack:** Python 3.10+, Click, Pydantic v2, Rich, pytest

---

## 前提: Phase 1 からの引き継ぎ

- エントリポイント名は `dr`（`cli` は使わない）
- 例外は `DavinciEnvironmentError`（Python組み込み衝突回避済み）
- exit_code は `exceptions.py` が正規定義（1〜5）
- `validate_path()` は `core/validation.py` に統合済み（`security.py` は作らない）
- `get_resolve()` は `davinci_cli.core.connection` モジュール（`resolve_bridge` は使わない）
- `core/edition.py` の `get_edition()` が Free/Studio 判定の唯一の実装
- `core/logging.py` の `setup_logging()` を CLI エントリポイントで呼ぶ
- `_impl` 関数は常に flat な `list[dict]` または `dict` を返す

## 修正点サマリ（旧計画からの変更）

1. `resolve_bridge` → `core.connection` に全て統一
2. `EnvironmentError` → `DavinciEnvironmentError` に統一
3. 共通デコレータ `decorators.py` を cli.py の前に追加（Task 11）
4. `handle_errors` を各コマンドのデコレータではなく `invoke` オーバーライドで一括適用
5. `_detect_edition` 重複排除: system.py は `core/edition.py` の `get_edition()` を使用
6. `ValueError` → `ProjectNotFoundError`/`SchemaNotFoundError` に置き換え
7. `dry_run=False` が全 `_impl` 関数のデフォルト（MCP 側でのみ `True`）
8. `--verbose`/`--debug` フラグを dr コマンドに追加

## 共通パターン

全コマンドで以下のパターンに従う。

```python
# _impl関数: CLI/MCP共有の純粋関数（dry_run=False がデフォルト）
def <command>_impl(**kwargs, dry_run: bool = False) -> dict | list[dict]:
    ...

# CLIコマンド: _impl をラップ、共通デコレータを使用
@<group>.command()
@common_options  # @json_input_option, @fields_option, @dry_run_option
def <command>(**kwargs):
    result = <command>_impl(**kwargs)
    output(result)  # --pretty / NDJSON 自動判定
```

---

### Task 11: decorators.py — 共通デコレータ

**Files:**
- Create: `src/davinci_cli/decorators.py`
- Test: `tests/unit/test_decorators.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_decorators.py
import click
import json
import pytest
from click.testing import CliRunner

from davinci_cli.decorators import json_input_option, fields_option, dry_run_option


@click.command()
@json_input_option
@click.pass_context
def cmd_with_json(ctx, json_input):
    """テスト用コマンド: --json オプション"""
    if json_input:
        click.echo(json.dumps({"received": json_input}))
    else:
        click.echo(json.dumps({"received": None}))


@click.command()
@fields_option
@click.pass_context
def cmd_with_fields(ctx, fields):
    """テスト用コマンド: --fields オプション"""
    click.echo(json.dumps({"fields": fields}))


@click.command()
@dry_run_option
@click.pass_context
def cmd_with_dry_run(ctx, dry_run):
    """テスト用コマンド: --dry-run オプション"""
    click.echo(json.dumps({"dry_run": dry_run}))


class TestJsonInputOption:
    def test_json_input_provided(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_json, ["--json", '{"name": "Test"}'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["received"] == {"name": "Test"}

    def test_json_input_not_provided(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_json, [])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["received"] is None

    def test_json_input_invalid_json(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_json, ["--json", "not-json"])
        assert result.exit_code != 0


class TestFieldsOption:
    def test_fields_provided(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_fields, ["--fields", "name,id,fps"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["fields"] == ["name", "id", "fps"]

    def test_fields_not_provided(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_fields, [])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["fields"] is None


class TestDryRunOption:
    def test_dry_run_flag(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_dry_run, ["--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_dry_run_default_false(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_dry_run, [])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is False
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_decorators.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/decorators.py
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
import functools
from typing import Any, Callable

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


JSON_TYPE = _JsonParamType()


def json_input_option(func: Callable) -> Callable:
    """--json オプションを追加するデコレータ。

    JSON 文字列を dict にパースして json_input 引数に渡す。
    """
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
    """--fields オプションを追加するデコレータ。

    カンマ区切りのフィールド名を list[str] に変換して fields 引数に渡す。
    """
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
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_decorators.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/decorators.py tests/unit/test_decorators.py
git commit -m "feat: decorators.py — @json_input_option, @fields_option, @dry_run_option 共通化"
```

---

### Task 12: cli.py — Click エントリーポイント（グローバルエラーハンドリング、--verbose/--debug）

**Files:**
- Modify: `src/davinci_cli/cli.py`
- Test: `tests/unit/test_cli.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_cli.py
import json
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from davinci_cli.cli import dr, DavinciCLIGroup
from davinci_cli.core.exceptions import (
    DavinciCLIError,
    ResolveNotRunningError,
    ProjectNotOpenError,
    ValidationError,
    DavinciEnvironmentError,
    EditionError,
)


class TestDrCommand:
    def test_dr_help(self):
        result = CliRunner().invoke(dr, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_dr_version(self):
        result = CliRunner().invoke(dr, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_dr_has_verbose_flag(self):
        result = CliRunner().invoke(dr, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_dr_has_debug_flag(self):
        result = CliRunner().invoke(dr, ["--debug", "--help"])
        assert result.exit_code == 0


class TestDavinciCLIGroup:
    """invoke オーバーライドによるグローバルエラーハンドリングのテスト"""

    def test_resolve_not_running_exits_1(self):
        @dr.command(name="_test_resolve_err")
        def _test_cmd():
            raise ResolveNotRunningError()

        result = CliRunner().invoke(dr, ["_test_resolve_err"])
        assert result.exit_code == 1
        assert "DaVinci Resolve" in result.output

    def test_project_not_open_exits_2(self):
        @dr.command(name="_test_project_err")
        def _test_cmd():
            raise ProjectNotOpenError()

        result = CliRunner().invoke(dr, ["_test_project_err"])
        assert result.exit_code == 2

    def test_validation_error_exits_3(self):
        @dr.command(name="_test_validation_err")
        def _test_cmd():
            raise ValidationError(field="name", reason="too long")

        result = CliRunner().invoke(dr, ["_test_validation_err"])
        assert result.exit_code == 3

    def test_environment_error_exits_4(self):
        @dr.command(name="_test_env_err")
        def _test_cmd():
            raise DavinciEnvironmentError(detail="missing var")

        result = CliRunner().invoke(dr, ["_test_env_err"])
        assert result.exit_code == 4

    def test_edition_error_exits_5(self):
        @dr.command(name="_test_edition_err")
        def _test_cmd():
            raise EditionError(required="Studio", actual="Free")

        result = CliRunner().invoke(dr, ["_test_edition_err"])
        assert result.exit_code == 5

    def test_error_output_is_json(self):
        """エラー出力が JSON 形式であること（エージェントがパースしやすい）"""
        @dr.command(name="_test_json_err")
        def _test_cmd():
            raise ResolveNotRunningError()

        result = CliRunner().invoke(dr, ["_test_json_err"])
        parsed = json.loads(result.output)
        assert "error" in parsed
        assert "exit_code" in parsed


class TestSubcommandRegistration:
    def test_system_registered(self):
        assert "system" in [cmd for cmd in dr.commands]

    def test_schema_registered(self):
        assert "schema" in [cmd for cmd in dr.commands]

    def test_project_registered(self):
        assert "project" in [cmd for cmd in dr.commands]

    def test_timeline_registered(self):
        assert "timeline" in [cmd for cmd in dr.commands]

    def test_clip_registered(self):
        assert "clip" in [cmd for cmd in dr.commands]
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_cli.py -v`
Expected: FAIL (ImportError — DavinciCLIGroup 未定義)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/cli.py
"""CLI エントリポイント。

エントリポイント名は 'dr' に統一。'cli' は使わない。
グローバルエラーハンドリングは DavinciCLIGroup.invoke() オーバーライドで実装。
各コマンドに手動でデコレータを付ける必要はない。

exit_code は core/exceptions.py の定義を参照する:
  1: ResolveNotRunningError
  2: ProjectNotOpenError / ProjectNotFoundError
  3: ValidationError
  4: DavinciEnvironmentError
  5: EditionError
"""
from __future__ import annotations

import json
import sys

import click

from davinci_cli.core.exceptions import DavinciCLIError
from davinci_cli.core.logging import setup_logging


class DavinciCLIGroup(click.Group):
    """カスタム Click Group — invoke をオーバーライドしてグローバルエラーハンドリングを行う。

    DavinciCLIError のサブクラスをキャッチし、JSON形式でエラーを出力して
    例外の exit_code で終了する。各コマンドに個別のエラーハンドラは不要。
    """

    def invoke(self, ctx: click.Context) -> None:
        try:
            super().invoke(ctx)
        except DavinciCLIError as exc:
            error_response = {
                "error": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": exc.exit_code,
            }
            click.echo(json.dumps(error_response, ensure_ascii=False))
            ctx.exit(exc.exit_code)


@click.group(cls=DavinciCLIGroup)
@click.version_option()
@click.option(
    "--pretty",
    is_flag=True,
    default=False,
    help="Human-readable output (TTY only)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging (INFO level)",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug logging (DEBUG level)",
)
@click.pass_context
def dr(ctx: click.Context, pretty: bool, verbose: bool, debug: bool) -> None:
    """DaVinci Resolve CLI — agent-first interface."""
    ctx.ensure_object(dict)
    ctx.obj["pretty"] = pretty
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug

    setup_logging(verbose=verbose, debug=debug)


# サブコマンド登録（遅延インポートでサーキュラーインポートを回避）
def _register_commands() -> None:
    from davinci_cli.commands import system, schema, project, timeline, clip
    dr.add_command(system.system)
    dr.add_command(schema.schema)
    dr.add_command(project.project)
    dr.add_command(timeline.timeline)
    dr.add_command(clip.clip)


_register_commands()
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_cli.py -v`
Expected: PASS

注意: このタスクの時点では commands/ 配下のモジュールが未作成のため、
`_register_commands()` は Task 13〜17 で各コマンドモジュールを作成した後に有効化する。
テスト時は `_register_commands()` をモックするか、空のコマンドモジュールを先に作成する。

空のコマンドモジュール（スタブ）:
```python
# src/davinci_cli/commands/__init__.py
```

```python
# src/davinci_cli/commands/system.py
import click

@click.group()
def system():
    """System information commands."""
```

```python
# src/davinci_cli/commands/schema.py
import click

@click.group()
def schema():
    """Runtime schema resolution."""
```

```python
# src/davinci_cli/commands/project.py
import click

@click.group()
def project():
    """Project operations."""
```

```python
# src/davinci_cli/commands/timeline.py
import click

@click.group()
def timeline():
    """Timeline operations."""
```

```python
# src/davinci_cli/commands/clip.py
import click

@click.group()
def clip():
    """Clip operations."""
```

**Step 5: コミット**

```bash
git add src/davinci_cli/cli.py src/davinci_cli/commands/__init__.py \
        src/davinci_cli/commands/system.py src/davinci_cli/commands/schema.py \
        src/davinci_cli/commands/project.py src/davinci_cli/commands/timeline.py \
        src/davinci_cli/commands/clip.py tests/unit/test_cli.py
git commit -m "feat: cli.py — DavinciCLIGroup invoke オーバーライドでグローバルエラーハンドリング"
```

---

### Task 13: commands/system.py — dr system（core/edition.py 使用、resolve_bridge 不使用）

**Files:**
- Modify: `src/davinci_cli/commands/system.py`
- Test: `tests/unit/test_system.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_system.py
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.system import ping_impl, version_impl, edition_impl, info_impl
from davinci_cli.core.exceptions import ResolveNotRunningError


# パッチ対象は core.connection（resolve_bridge ではない）
RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    resolve.GetVersionString.return_value = "19.0.0b0"
    resolve.GetVersion.return_value = {
        "product": "DaVinci Resolve Studio",
        "major": 19,
        "minor": 0,
    }
    pm = MagicMock()
    project = MagicMock()
    project.GetName.return_value = "TestProject"
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestPingImpl:
    def test_returns_ok_when_running(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = ping_impl()
        assert result == {"status": "ok", "version": "19.0.0b0"}

    def test_raises_when_not_running(self):
        with patch(RESOLVE_PATCH, side_effect=ResolveNotRunningError()):
            with pytest.raises(ResolveNotRunningError):
                ping_impl()


class TestVersionImpl:
    def test_returns_version_and_edition(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = version_impl()
        assert "version" in result
        assert result["edition"] == "Studio"


class TestEditionImpl:
    def test_returns_edition(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = edition_impl()
        assert result["edition"] == "Studio"


class TestInfoImpl:
    def test_returns_comprehensive_info(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = info_impl()
        assert "version" in result
        assert "edition" in result
        assert result["current_project"] == "TestProject"

    def test_no_project_open(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject.return_value = None
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = info_impl()
        assert result["current_project"] is None


class TestSystemCLI:
    def test_dr_system_ping(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["system", "ping"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_dr_system_version(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["system", "version"])
        assert result.exit_code == 0

    def test_dr_system_info(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["system", "info"])
        assert result.exit_code == 0
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_system.py -v`
Expected: FAIL (ping_impl 未定義)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/commands/system.py
"""dr system — システム情報コマンド。

エディション判定は core/edition.py の get_edition() を使用する。
_detect_edition() のようなローカル関数は定義しない（重複排除）。
Resolve 接続は core.connection を使用する（resolve_bridge は使わない）。
"""
from __future__ import annotations

from typing import Any

import click

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.edition import get_edition
from davinci_cli.output.formatter import output


@click.group()
def system() -> None:
    """System information commands."""


def ping_impl() -> dict:
    """Resolve 接続確認。"""
    resolve = get_resolve()
    version = resolve.GetVersionString()
    return {"status": "ok", "version": version}


def version_impl() -> dict:
    """バージョン情報を返す。"""
    resolve = get_resolve()
    return {
        "version": resolve.GetVersionString(),
        "edition": get_edition(resolve),
    }


def edition_impl() -> dict:
    """エディション情報を返す。"""
    resolve = get_resolve()
    return {
        "edition": get_edition(resolve),
    }


def info_impl() -> dict:
    """総合情報を返す。"""
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    return {
        "version": resolve.GetVersionString(),
        "edition": get_edition(resolve),
        "current_project": project.GetName() if project else None,
    }


@system.command()
@click.pass_context
def ping(ctx: click.Context) -> None:
    """Resolve 接続確認。"""
    result = ping_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@system.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """バージョン情報。"""
    result = version_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@system.command()
@click.pass_context
def edition(ctx: click.Context) -> None:
    """エディション（Free/Studio）確認。"""
    result = edition_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@system.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """総合情報（バージョン+エディション+現在プロジェクト）。"""
    result = info_impl()
    output(result, pretty=ctx.obj.get("pretty"))
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_system.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/system.py tests/unit/test_system.py
git commit -m "feat: commands/system.py — core/edition.py使用、resolve_bridge不使用 (重複排除)"
```

---

### Task 14: commands/schema.py — dr schema（SchemaNotFoundError 追加）

**Files:**
- Create: `src/davinci_cli/schema_registry.py`
- Modify: `src/davinci_cli/commands/schema.py`
- Modify: `src/davinci_cli/core/exceptions.py`（SchemaNotFoundError 追加）
- Test: `tests/unit/test_schema.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_schema.py
import json
import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.schema import schema_show_impl, schema_list_impl
from davinci_cli.core.exceptions import SchemaNotFoundError
from davinci_cli.schema_registry import SCHEMA_REGISTRY, register_schema

from pydantic import BaseModel


# テスト用モデル
class _TestOutput(BaseModel):
    name: str
    value: int


class _TestInput(BaseModel):
    name: str


@pytest.fixture(autouse=True)
def _register_test_schemas():
    """テスト用スキーマを登録し、テスト後にクリアする"""
    original = dict(SCHEMA_REGISTRY)
    register_schema("test.command", output_model=_TestOutput)
    register_schema("test.with_input", output_model=_TestOutput, input_model=_TestInput)
    yield
    SCHEMA_REGISTRY.clear()
    SCHEMA_REGISTRY.update(original)


class TestSchemaShowImpl:
    def test_returns_output_schema(self):
        result = schema_show_impl("test.command")
        assert result["command"] == "test.command"
        assert "output_schema" in result
        assert result["output_schema"]["type"] == "object"

    def test_returns_input_schema_when_present(self):
        result = schema_show_impl("test.with_input")
        assert "input_schema" in result
        assert "name" in result["input_schema"]["properties"]

    def test_unknown_command_raises_schema_not_found(self):
        """ValueError ではなく SchemaNotFoundError を送出する"""
        with pytest.raises(SchemaNotFoundError):
            schema_show_impl("nonexistent.command")


class TestSchemaListImpl:
    def test_lists_registered_commands(self):
        result = schema_list_impl()
        commands = [r["command"] for r in result]
        assert "test.command" in commands
        assert "test.with_input" in commands


class TestSchemaCLI:
    def test_dr_schema_show(self):
        result = CliRunner().invoke(dr, ["schema", "show", "test.command"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "output_schema" in data

    def test_dr_schema_list(self):
        result = CliRunner().invoke(dr, ["schema", "list"])
        assert result.exit_code == 0

    def test_dr_schema_show_not_found(self):
        result = CliRunner().invoke(dr, ["schema", "show", "nonexistent"])
        # SchemaNotFoundError → exit_code 3 (ValidationError系)
        assert result.exit_code == 3
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_schema.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

まず `SchemaNotFoundError` を exceptions.py に追加:

```python
# src/davinci_cli/core/exceptions.py に追加
class SchemaNotFoundError(DavinciCLIError):
    """指定されたスキーマが見つからない。"""

    exit_code = 3  # ValidationError と同系統

    def __init__(self, command: str, available: list[str]) -> None:
        self.command = command
        self.available = available
        super().__init__(
            f"Unknown command: {command}. Available: {', '.join(available)}"
        )
```

スキーマレジストリ:

```python
# src/davinci_cli/schema_registry.py
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
```

schema コマンド:

```python
# src/davinci_cli/commands/schema.py
"""dr schema — ランタイムスキーマ解決コマンド。

エージェントが dr schema show <command> でコマンドの JSON Schema を取得し、
正しい入力を構築できるようにする。
"""
from __future__ import annotations

import click

from davinci_cli.core.exceptions import SchemaNotFoundError
from davinci_cli.schema_registry import SCHEMA_REGISTRY
from davinci_cli.output.formatter import output


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
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_schema.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/core/exceptions.py src/davinci_cli/schema_registry.py \
        src/davinci_cli/commands/schema.py tests/unit/test_schema.py
git commit -m "feat: commands/schema.py — SchemaNotFoundError追加、ValueError不使用"
```

---

### Task 15: commands/project.py — dr project（共通デコレータ使用、ProjectNotFoundError）

**Files:**
- Modify: `src/davinci_cli/commands/project.py`
- Test: `tests/unit/test_project.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_project.py
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.project import (
    project_list_impl,
    project_open_impl,
    project_close_impl,
    project_create_impl,
    project_delete_impl,
    project_save_impl,
    project_info_impl,
    project_settings_get_impl,
    project_settings_set_impl,
)
from davinci_cli.core.exceptions import (
    ProjectNotFoundError,
    ProjectNotOpenError,
    ResolveNotRunningError,
)


RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()
    project.GetName.return_value = "TestProject"
    project.GetTimelineCount.return_value = 3
    project.GetSetting.side_effect = lambda k: {
        "timelineFrameRate": "24",
        "timelineResolutionWidth": "1920",
        "timelineResolutionHeight": "1080",
    }.get(k, "")
    pm.GetCurrentProject.return_value = project
    pm.GetProjectListInCurrentFolder.return_value = ["TestProject", "Demo"]
    pm.LoadProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestProjectListImpl:
    def test_returns_list_of_projects(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_list_impl()
        assert len(result) == 2
        assert result[0]["name"] == "TestProject"

    def test_fields_filter(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_list_impl(fields=["name"])
        assert all("name" in p for p in result)


class TestProjectOpenImpl:
    def test_dry_run(self):
        result = project_open_impl(name="MyProject", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "open"
        assert result["name"] == "MyProject"

    def test_open_existing_project(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_open_impl(name="TestProject")
        assert result["opened"] == "TestProject"

    def test_open_not_found_raises_project_not_found(self, mock_resolve):
        """ValueError ではなく ProjectNotFoundError を使用"""
        mock_resolve.GetProjectManager().LoadProject.return_value = None
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ProjectNotFoundError, match="NonExistent"):
                project_open_impl(name="NonExistent")


class TestProjectCloseImpl:
    def test_dry_run(self):
        result = project_close_impl(dry_run=True)
        assert result["dry_run"] is True

    def test_close_project(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_close_impl()
        assert result["closed"] is True


class TestProjectCreateImpl:
    def test_dry_run(self):
        result = project_create_impl(name="NewProject", dry_run=True)
        assert result["dry_run"] is True
        assert result["name"] == "NewProject"


class TestProjectDeleteImpl:
    def test_dry_run(self):
        result = project_delete_impl(name="OldProject", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "delete"


class TestProjectInfoImpl:
    def test_returns_project_info(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_info_impl()
        assert result["name"] == "TestProject"
        assert result["timeline_count"] == 3

    def test_fields_filter(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_info_impl(fields=["name"])
        assert "name" in result
        assert "fps" not in result


class TestProjectCLI:
    def test_project_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["project", "list"])
        assert result.exit_code == 0

    def test_project_open_dry_run(self):
        result = CliRunner().invoke(
            dr, ["project", "open", "Test", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_project_open_json_input(self):
        result = CliRunner().invoke(
            dr, ["project", "open", "--json", '{"name": "Test"}', "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_project_open_no_name_error(self):
        result = CliRunner().invoke(dr, ["project", "open"])
        assert result.exit_code != 0

    def test_project_info_with_fields(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(
                dr, ["project", "info", "--fields", "name"]
            )
        assert result.exit_code == 0
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_project.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/commands/project.py
"""dr project — プロジェクト操作コマンド。

共通デコレータ（@json_input_option, @fields_option, @dry_run_option）を使用。
プロジェクトが見つからない場合は ProjectNotFoundError を送出する（ValueError は使わない）。
Resolve 接続は core.connection を使用する（resolve_bridge は使わない）。

_impl 関数の dry_run デフォルト値は False。
MCP 側でのみ dry_run=True がデフォルトになる。
"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotFoundError, ProjectNotOpenError
from davinci_cli.decorators import json_input_option, fields_option, dry_run_option
from davinci_cli.output.formatter import output, filter_fields
from davinci_cli.schema_registry import register_schema


# --- Pydantic Models ---

class ProjectInfo(BaseModel):
    name: str
    timeline_count: int | None = None
    fps: str | None = None

class ProjectOpenInput(BaseModel):
    name: str

class ProjectCreateInput(BaseModel):
    name: str

class ProjectDeleteInput(BaseModel):
    name: str

class ProjectSettingsSetInput(BaseModel):
    key: str
    value: str


# --- Helper ---

def _get_current_project() -> Any:
    """現在のプロジェクトを取得。開いていなければ ProjectNotOpenError。"""
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise ProjectNotOpenError()
    return project


# --- _impl Functions ---

def project_list_impl(fields: list[str] | None = None) -> list[dict]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    names = pm.GetProjectListInCurrentFolder()
    projects: list[dict] = [{"name": n} for n in names]
    if fields:
        projects = [
            {k: p[k] for k in fields if k in p} for p in projects
        ]
    return projects


def project_open_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "open", "name": name}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.LoadProject(name)
    if not project:
        raise ProjectNotFoundError(name=name)
    return {"opened": name}


def project_close_impl(dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "close"}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    pm.CloseProject(pm.GetCurrentProject())
    return {"closed": True}


def project_create_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "create", "name": name}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.CreateProject(name)
    if not project:
        raise ProjectNotFoundError(name=name)
    return {"created": name}


def project_delete_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "delete", "name": name}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    success = pm.DeleteProject(name)
    if not success:
        raise ProjectNotFoundError(name=name)
    return {"deleted": name}


def project_save_impl() -> dict:
    project = _get_current_project()
    project.SaveProject()
    return {"saved": True}


def project_info_impl(fields: list[str] | None = None) -> dict:
    project = _get_current_project()
    info = {
        "name": project.GetName(),
        "timeline_count": project.GetTimelineCount(),
        "fps": project.GetSetting("timelineFrameRate"),
    }
    if fields:
        info = {k: v for k, v in info.items() if k in fields}
    return info


def project_settings_get_impl(key: str | None = None) -> dict:
    project = _get_current_project()
    if key:
        value = project.GetSetting(key)
        return {"key": key, "value": value}
    # key 未指定時は全設定を返す（DaVinci APIの仕様に依存）
    return {"settings": "all settings retrieval not implemented yet"}


def project_settings_set_impl(key: str, value: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "settings_set", "key": key, "value": value}
    project = _get_current_project()
    project.SetSetting(key, value)
    return {"set": True, "key": key, "value": value}


# --- CLI Commands ---

@click.group()
def project() -> None:
    """Project operations."""


@project.command(name="list")
@fields_option
@click.pass_context
def project_list(ctx: click.Context, fields: list[str] | None) -> None:
    """プロジェクト一覧。"""
    result = project_list_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="open")
@click.argument("name", required=False)
@json_input_option
@dry_run_option
@click.pass_context
def project_open(
    ctx: click.Context,
    name: str | None,
    json_input: dict | None,
    dry_run: bool,
) -> None:
    """プロジェクトを開く。"""
    if json_input:
        data = ProjectOpenInput.model_validate(json_input)
        name = data.name
    if not name:
        raise click.UsageError("name is required (positional argument or --json)")
    result = project_open_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="close")
@dry_run_option
@click.pass_context
def project_close(ctx: click.Context, dry_run: bool) -> None:
    """現在のプロジェクトを閉じる。"""
    result = project_close_impl(dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="create")
@click.argument("name")
@dry_run_option
@click.pass_context
def project_create_cmd(ctx: click.Context, name: str, dry_run: bool) -> None:
    """新規プロジェクト作成。"""
    result = project_create_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="delete")
@click.argument("name")
@dry_run_option
@click.pass_context
def project_delete_cmd(ctx: click.Context, name: str, dry_run: bool) -> None:
    """プロジェクト削除（破壊的操作）。"""
    result = project_delete_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="save")
@click.pass_context
def project_save_cmd(ctx: click.Context) -> None:
    """プロジェクト保存。"""
    result = project_save_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@project.command(name="info")
@fields_option
@click.pass_context
def project_info(ctx: click.Context, fields: list[str] | None) -> None:
    """現在のプロジェクト情報。"""
    result = project_info_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@project.group(name="settings")
def project_settings() -> None:
    """Project settings operations."""


@project_settings.command(name="get")
@click.argument("key", required=False)
@click.pass_context
def settings_get(ctx: click.Context, key: str | None) -> None:
    """設定値取得。"""
    result = project_settings_get_impl(key=key)
    output(result, pretty=ctx.obj.get("pretty"))


@project_settings.command(name="set")
@click.argument("key")
@click.argument("value")
@dry_run_option
@click.pass_context
def settings_set(ctx: click.Context, key: str, value: str, dry_run: bool) -> None:
    """設定値変更。"""
    result = project_settings_set_impl(key=key, value=value, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("project.list", output_model=ProjectInfo)
register_schema("project.open", output_model=ProjectInfo, input_model=ProjectOpenInput)
register_schema("project.create", output_model=ProjectInfo, input_model=ProjectCreateInput)
register_schema("project.delete", output_model=ProjectInfo, input_model=ProjectDeleteInput)
register_schema("project.info", output_model=ProjectInfo)
register_schema("project.settings.set", output_model=ProjectInfo, input_model=ProjectSettingsSetInput)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_project.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/project.py tests/unit/test_project.py
git commit -m "feat: commands/project.py — 共通デコレータ使用、ProjectNotFoundError追加"
```

---

### Task 16: commands/timeline.py — dr timeline（共通デコレータ使用）

**Files:**
- Modify: `src/davinci_cli/commands/timeline.py`
- Test: `tests/unit/test_timeline.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_timeline.py
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.timeline import (
    timeline_list_impl,
    timeline_current_impl,
    timeline_switch_impl,
    timeline_create_impl,
    timeline_delete_impl,
    timeline_export_impl,
    marker_list_impl,
    marker_add_impl,
    marker_delete_impl,
)
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError


RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()

    timeline1 = MagicMock()
    timeline1.GetName.return_value = "Main Edit"
    timeline1.GetSetting.side_effect = lambda k: {
        "timelineFrameRate": "24",
        "timelineResolutionWidth": "1920",
        "timelineResolutionHeight": "1080",
    }.get(k, "")
    timeline1.GetStartTimecode.return_value = "00:00:00:00"
    timeline1.GetMarkers.return_value = {
        100: {"color": "Blue", "name": "VFX", "note": "", "duration": 1},
    }

    timeline2 = MagicMock()
    timeline2.GetName.return_value = "VFX Timeline"
    timeline2.GetSetting.return_value = "24"

    project.GetTimelineCount.return_value = 2
    project.GetTimelineByIndex.side_effect = lambda i: {1: timeline1, 2: timeline2}.get(i)
    project.GetCurrentTimeline.return_value = timeline1
    project.GetMediaPool.return_value = MagicMock()

    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestTimelineListImpl:
    def test_returns_timeline_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_list_impl()
        assert len(result) == 2
        assert result[0]["name"] == "Main Edit"

    def test_fields_filter(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_list_impl(fields=["name"])
        assert all(list(t.keys()) == ["name"] for t in result)


class TestTimelineCurrentImpl:
    def test_returns_current_timeline(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_current_impl()
        assert result["name"] == "Main Edit"
        assert "fps" in result

    def test_no_current_timeline_raises(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline.return_value = None
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ProjectNotOpenError):
                timeline_current_impl()


class TestTimelineSwitchImpl:
    def test_dry_run(self):
        result = timeline_switch_impl(name="Edit", dry_run=True)
        assert result == {"dry_run": True, "action": "switch", "name": "Edit"}

    def test_switch_not_found(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().GetTimelineCount.return_value = 0
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError):
                timeline_switch_impl(name="NonExistent")


class TestTimelineCreateImpl:
    def test_dry_run(self):
        result = timeline_create_impl(name="NewTimeline", dry_run=True)
        assert result["dry_run"] is True
        assert result["name"] == "NewTimeline"


class TestTimelineDeleteImpl:
    def test_dry_run(self):
        result = timeline_delete_impl(name="OldTimeline", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "delete"


class TestTimelineExportImpl:
    def test_dry_run(self):
        result = timeline_export_impl(
            format="xml", output_path="/tmp/out.xml", dry_run=True
        )
        assert result["dry_run"] is True
        assert result["format"] == "xml"


class TestMarkerImpl:
    def test_marker_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = marker_list_impl()
        assert isinstance(result, list)

    def test_marker_add_dry_run(self):
        result = marker_add_impl(
            frame_id=100, color="Blue", name="VFX", dry_run=True
        )
        assert result["dry_run"] is True

    def test_marker_delete_dry_run(self):
        result = marker_delete_impl(frame_id=100, dry_run=True)
        assert result["dry_run"] is True


class TestTimelineCLI:
    def test_timeline_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["timeline", "list"])
        assert result.exit_code == 0

    def test_timeline_create_json(self):
        result = CliRunner().invoke(
            dr,
            ["timeline", "create", "--json", '{"name": "New"}', "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_timeline.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/commands/timeline.py
"""dr timeline — タイムライン操作コマンド。

共通デコレータ使用。Resolve接続は core.connection を使用。
"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.decorators import json_input_option, fields_option, dry_run_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema


# --- Pydantic Models ---

class TimelineInfo(BaseModel):
    name: str
    fps: float | None = None
    width: int | None = None
    height: int | None = None
    start_timecode: str | None = None

class TimelineCreateInput(BaseModel):
    name: str
    fps: float | None = None
    width: int | None = None
    height: int | None = None

class TimelineSwitchInput(BaseModel):
    name: str

class TimelineDeleteInput(BaseModel):
    name: str

class TimelineExportInput(BaseModel):
    format: str
    output: str
    timeline: str | None = None

class MarkerAddInput(BaseModel):
    frame_id: int
    color: str
    name: str
    note: str | None = None
    duration: int = 1


# --- Helper ---

def _get_current_project() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise ProjectNotOpenError()
    return project


def _get_timeline_by_name(project: Any, name: str) -> Any:
    count = project.GetTimelineCount()
    for i in range(1, count + 1):
        tl = project.GetTimelineByIndex(i)
        if tl and tl.GetName() == name:
            return tl
    raise ValidationError(field="timeline", reason=f"Timeline not found: {name}")


# --- _impl Functions ---

def timeline_list_impl(fields: list[str] | None = None) -> list[dict]:
    project = _get_current_project()
    count = project.GetTimelineCount()
    timelines: list[dict] = []
    for i in range(1, count + 1):
        tl = project.GetTimelineByIndex(i)
        if tl is None:
            continue
        info: dict = {"name": tl.GetName()}
        if fields is None or "fps" in fields:
            try:
                info["fps"] = float(tl.GetSetting("timelineFrameRate"))
            except (ValueError, TypeError):
                info["fps"] = None
        timelines.append(info)
    if fields:
        timelines = [{k: v for k, v in t.items() if k in fields} for t in timelines]
    return timelines


def timeline_current_impl(fields: list[str] | None = None) -> dict:
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    info = {
        "name": tl.GetName(),
        "fps": float(tl.GetSetting("timelineFrameRate") or 0),
        "width": int(tl.GetSetting("timelineResolutionWidth") or 0),
        "height": int(tl.GetSetting("timelineResolutionHeight") or 0),
        "start_timecode": tl.GetStartTimecode(),
    }
    if fields:
        info = {k: v for k, v in info.items() if k in fields}
    return info


def timeline_switch_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "switch", "name": name}
    project = _get_current_project()
    tl = _get_timeline_by_name(project, name)
    project.SetCurrentTimeline(tl)
    return {"switched": name}


def timeline_create_impl(
    name: str,
    fps: float | None = None,
    width: int | None = None,
    height: int | None = None,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "create", "name": name}
    project = _get_current_project()
    media_pool = project.GetMediaPool()
    tl = media_pool.CreateEmptyTimeline(name)
    if not tl:
        raise ValidationError(field="name", reason=f"Failed to create timeline: {name}")
    return {"created": name}


def timeline_delete_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "delete", "name": name}
    project = _get_current_project()
    tl = _get_timeline_by_name(project, name)
    media_pool = project.GetMediaPool()
    media_pool.DeleteTimelines([tl])
    return {"deleted": name}


def timeline_export_impl(
    format: str,
    output_path: str,
    timeline_name: str | None = None,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "export",
            "format": format,
            "output": output_path,
        }
    project = _get_current_project()
    tl = (
        _get_timeline_by_name(project, timeline_name)
        if timeline_name
        else project.GetCurrentTimeline()
    )
    if not tl:
        raise ProjectNotOpenError()
    tl.Export(output_path, format)
    return {"exported": output_path, "format": format}


def marker_list_impl(timeline_name: str | None = None) -> list[dict]:
    project = _get_current_project()
    tl = (
        _get_timeline_by_name(project, timeline_name)
        if timeline_name
        else project.GetCurrentTimeline()
    )
    if not tl:
        raise ProjectNotOpenError()
    markers = tl.GetMarkers() or {}
    return [
        {
            "frame_id": frame_id,
            "color": info.get("color", ""),
            "name": info.get("name", ""),
            "note": info.get("note", ""),
            "duration": info.get("duration", 1),
        }
        for frame_id, info in markers.items()
    ]


def marker_add_impl(
    frame_id: int,
    color: str,
    name: str,
    note: str | None = None,
    duration: int = 1,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "marker_add",
            "frame_id": frame_id,
            "color": color,
            "name": name,
        }
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    tl.AddMarker(frame_id, color, name, note or "", duration)
    return {"added": True, "frame_id": frame_id}


def marker_delete_impl(frame_id: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "marker_delete", "frame_id": frame_id}
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    tl.DeleteMarkerAtFrame(frame_id)
    return {"deleted": True, "frame_id": frame_id}


# --- CLI Commands ---

@click.group()
def timeline() -> None:
    """Timeline operations."""


@timeline.command(name="list")
@fields_option
@click.pass_context
def timeline_list(ctx: click.Context, fields: list[str] | None) -> None:
    """タイムライン一覧。"""
    result = timeline_list_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="current")
@fields_option
@click.pass_context
def timeline_current(ctx: click.Context, fields: list[str] | None) -> None:
    """現在のタイムライン情報。"""
    result = timeline_current_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="switch")
@click.argument("name")
@dry_run_option
@click.pass_context
def timeline_switch(ctx: click.Context, name: str, dry_run: bool) -> None:
    """タイムライン切り替え。"""
    result = timeline_switch_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="create")
@click.option("--name", default=None)
@json_input_option
@dry_run_option
@click.pass_context
def timeline_create(
    ctx: click.Context,
    name: str | None,
    json_input: dict | None,
    dry_run: bool,
) -> None:
    """新規タイムライン作成。"""
    fps = width = height = None
    if json_input:
        data = TimelineCreateInput.model_validate(json_input)
        name = data.name
        fps = data.fps
        width = data.width
        height = data.height
    if not name:
        raise click.UsageError("--name or --json is required")
    result = timeline_create_impl(
        name=name, fps=fps, width=width, height=height, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="delete")
@click.argument("name")
@dry_run_option
@click.pass_context
def timeline_delete(ctx: click.Context, name: str, dry_run: bool) -> None:
    """タイムライン削除（破壊的操作）。"""
    result = timeline_delete_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.command(name="export")
@json_input_option
@dry_run_option
@click.pass_context
def timeline_export(ctx: click.Context, json_input: dict | None, dry_run: bool) -> None:
    """タイムラインエクスポート（XML/AAF/EDL）。"""
    if not json_input:
        raise click.UsageError("--json is required for export")
    data = TimelineExportInput.model_validate(json_input)
    result = timeline_export_impl(
        format=data.format,
        output_path=data.output,
        timeline_name=data.timeline,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@timeline.group(name="marker")
def timeline_marker() -> None:
    """Marker operations."""


@timeline_marker.command(name="list")
@click.option("--timeline", "timeline_name", default=None)
@click.pass_context
def marker_list_cmd(ctx: click.Context, timeline_name: str | None) -> None:
    """マーカー一覧。"""
    result = marker_list_impl(timeline_name=timeline_name)
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_marker.command(name="add")
@json_input_option
@dry_run_option
@click.pass_context
def marker_add_cmd(ctx: click.Context, json_input: dict | None, dry_run: bool) -> None:
    """マーカー追加。"""
    if not json_input:
        raise click.UsageError("--json is required")
    data = MarkerAddInput.model_validate(json_input)
    result = marker_add_impl(
        frame_id=data.frame_id,
        color=data.color,
        name=data.name,
        note=data.note,
        duration=data.duration,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


@timeline_marker.command(name="delete")
@click.argument("frame_id", type=int)
@dry_run_option
@click.pass_context
def marker_delete_cmd(ctx: click.Context, frame_id: int, dry_run: bool) -> None:
    """マーカー削除。"""
    result = marker_delete_impl(frame_id=frame_id, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("timeline.list", output_model=TimelineInfo)
register_schema("timeline.current", output_model=TimelineInfo)
register_schema("timeline.switch", output_model=TimelineInfo, input_model=TimelineSwitchInput)
register_schema("timeline.create", output_model=TimelineInfo, input_model=TimelineCreateInput)
register_schema("timeline.delete", output_model=TimelineInfo, input_model=TimelineDeleteInput)
register_schema("timeline.export", output_model=TimelineInfo, input_model=TimelineExportInput)
register_schema("timeline.marker.add", output_model=TimelineInfo, input_model=MarkerAddInput)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_timeline.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/timeline.py tests/unit/test_timeline.py
git commit -m "feat: commands/timeline.py — 共通デコレータ使用、マーカー操作含む"
```

---

### Task 17: commands/clip.py — dr clip（共通デコレータ使用）

**Files:**
- Modify: `src/davinci_cli/commands/clip.py`
- Test: `tests/unit/test_clip.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_clip.py
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.clip import (
    clip_list_impl,
    clip_info_impl,
    clip_select_impl,
    clip_property_get_impl,
    clip_property_set_impl,
)
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError


RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()

    timeline = MagicMock()
    clip1 = MagicMock()
    clip1.GetName.return_value = "A001_C001.mov"
    clip1.GetStart.return_value = 0
    clip1.GetEnd.return_value = 240
    clip1.GetDuration.return_value = 240
    clip1.GetProperty.return_value = "0.0"

    clip2 = MagicMock()
    clip2.GetName.return_value = "A001_C002.mov"
    clip2.GetStart.return_value = 240
    clip2.GetEnd.return_value = 480
    clip2.GetDuration.return_value = 240
    clip2.GetProperty.return_value = "1.0"

    timeline.GetTrackCount.return_value = 1
    timeline.GetItemListInTrack.return_value = [clip1, clip2]
    timeline.GetName.return_value = "Main Edit"
    project.GetCurrentTimeline.return_value = timeline
    project.GetTimelineCount.return_value = 1
    project.GetTimelineByIndex.return_value = timeline

    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestClipListImpl:
    def test_returns_indexed_clips(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = clip_list_impl()
        assert len(result) >= 2
        assert result[0]["index"] == 0
        assert "name" in result[0]

    def test_fields_filter(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = clip_list_impl(fields=["index", "name"])
        assert all(set(c.keys()) == {"index", "name"} for c in result)

    def test_no_current_timeline_raises(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline.return_value = None
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ProjectNotOpenError):
                clip_list_impl()


class TestClipInfoImpl:
    def test_returns_clip_info(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = clip_info_impl(index=0)
        assert result["index"] == 0
        assert "name" in result

    def test_out_of_range_raises(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError):
                clip_info_impl(index=9999)


class TestClipPropertyImpl:
    def test_property_get(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = clip_property_get_impl(index=0, key="Pan")
        assert result["key"] == "Pan"
        assert "value" in result

    def test_property_set_dry_run(self):
        result = clip_property_set_impl(
            index=0, key="Pan", value="0.5", dry_run=True
        )
        assert result["dry_run"] is True
        assert result["key"] == "Pan"


class TestClipCLI:
    def test_clip_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["clip", "list"])
        assert result.exit_code == 0

    def test_clip_property_set_dry_run(self):
        result = CliRunner().invoke(
            dr, ["clip", "property", "set", "0", "Pan", "0.5", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_clip.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/commands/clip.py
"""dr clip — クリップ操作コマンド。

共通デコレータ使用。Resolve接続は core.connection を使用。
"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.decorators import fields_option, dry_run_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema


# --- Pydantic Models ---

class ClipInfo(BaseModel):
    index: int
    name: str
    start: int | str | None = None
    end: int | str | None = None
    duration: int | str | None = None
    type: str | None = None
    track: int | None = None

class ClipPropertySetInput(BaseModel):
    index: int
    key: str
    value: str


# --- Helper ---

def _get_current_timeline() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise ProjectNotOpenError()
    tl = project.GetCurrentTimeline()
    if tl is None:
        raise ProjectNotOpenError()
    return tl


def _collect_clips(tl: Any) -> list[tuple[dict, Any]]:
    """タイムラインから全クリップを収集する。(info_dict, clip_item) のリスト。"""
    clips: list[tuple[dict, Any]] = []
    for track_type in ["video", "audio"]:
        track_count = tl.GetTrackCount(track_type)
        for track_idx in range(1, track_count + 1):
            track_clips = tl.GetItemListInTrack(track_type, track_idx) or []
            for clip_item in track_clips:
                info = {
                    "index": len(clips),
                    "name": clip_item.GetName(),
                    "start": clip_item.GetStart(),
                    "end": clip_item.GetEnd(),
                    "duration": clip_item.GetDuration(),
                    "type": track_type,
                    "track": track_idx,
                }
                clips.append((info, clip_item))
    return clips


# --- _impl Functions ---

def clip_list_impl(
    timeline_name: str | None = None,
    fields: list[str] | None = None,
) -> list[dict]:
    if timeline_name:
        resolve = get_resolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        if not project:
            raise ProjectNotOpenError()
        count = project.GetTimelineCount()
        tl = None
        for i in range(1, count + 1):
            t = project.GetTimelineByIndex(i)
            if t and t.GetName() == timeline_name:
                tl = t
                break
        if not tl:
            raise ValidationError(field="timeline", reason=f"Timeline not found: {timeline_name}")
    else:
        tl = _get_current_timeline()

    clips = _collect_clips(tl)
    result = [info for info, _ in clips]
    if fields:
        result = [{k: v for k, v in c.items() if k in fields} for c in result]
    return result


def clip_info_impl(index: int, fields: list[str] | None = None) -> dict:
    tl = _get_current_timeline()
    clips = _collect_clips(tl)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="index",
            reason=f"Clip index {index} out of range (0..{len(clips) - 1})",
        )
    info = clips[index][0]
    if fields:
        info = {k: v for k, v in info.items() if k in fields}
    return info


def clip_select_impl(index: int) -> dict:
    tl = _get_current_timeline()
    clips = _collect_clips(tl)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="index",
            reason=f"Clip index {index} out of range",
        )
    return {"selected": index, "name": clips[index][0]["name"]}


def clip_property_get_impl(index: int, key: str) -> dict:
    tl = _get_current_timeline()
    clips = _collect_clips(tl)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="index",
            reason=f"Clip index {index} out of range",
        )
    _, clip_item = clips[index]
    value = clip_item.GetProperty(key)
    return {"index": index, "key": key, "value": value}


def clip_property_set_impl(
    index: int,
    key: str,
    value: str,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "property_set",
            "index": index,
            "key": key,
            "value": value,
        }
    tl = _get_current_timeline()
    clips = _collect_clips(tl)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="index",
            reason=f"Clip index {index} out of range",
        )
    _, clip_item = clips[index]
    clip_item.SetProperty(key, value)
    return {"set": True, "index": index, "key": key, "value": value}


# --- CLI Commands ---

@click.group()
def clip() -> None:
    """Clip operations."""


@clip.command(name="list")
@click.option("--timeline", default=None, help="Timeline name (default: current)")
@fields_option
@click.pass_context
def clip_list(
    ctx: click.Context,
    timeline: str | None,
    fields: list[str] | None,
) -> None:
    """クリップ一覧（NDJSON対応）。"""
    result = clip_list_impl(timeline_name=timeline, fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@clip.command(name="info")
@click.argument("index", type=int)
@fields_option
@click.pass_context
def clip_info(ctx: click.Context, index: int, fields: list[str] | None) -> None:
    """クリップ詳細。"""
    result = clip_info_impl(index=index, fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@clip.command(name="select")
@click.argument("index", type=int)
@click.pass_context
def clip_select(ctx: click.Context, index: int) -> None:
    """クリップ選択。"""
    result = clip_select_impl(index=index)
    output(result, pretty=ctx.obj.get("pretty"))


@clip.group(name="property")
def clip_property() -> None:
    """Clip property operations."""


@clip_property.command(name="get")
@click.argument("index", type=int)
@click.argument("key")
@click.pass_context
def property_get(ctx: click.Context, index: int, key: str) -> None:
    """プロパティ取得。"""
    result = clip_property_get_impl(index=index, key=key)
    output(result, pretty=ctx.obj.get("pretty"))


@clip_property.command(name="set")
@click.argument("index", type=int)
@click.argument("key")
@click.argument("value")
@dry_run_option
@click.pass_context
def property_set(
    ctx: click.Context,
    index: int,
    key: str,
    value: str,
    dry_run: bool,
) -> None:
    """プロパティ設定。"""
    result = clip_property_set_impl(index=index, key=key, value=value, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("clip.list", output_model=ClipInfo)
register_schema("clip.info", output_model=ClipInfo)
register_schema("clip.property.set", output_model=ClipInfo, input_model=ClipPropertySetInput)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_clip.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/clip.py tests/unit/test_clip.py
git commit -m "feat: commands/clip.py — 共通デコレータ使用、NDJSON出力対応"
```

---

## Phase 2 完了確認

```bash
python -m pytest tests/unit/ -v --tb=short
```

Expected: 全テスト PASS

### ディレクトリ構造（Phase 2 完了時の追加分）

```
src/davinci_cli/
├── decorators.py                 # Task 11: 共通デコレータ
├── schema_registry.py            # Task 14: スキーマレジストリ
├── cli.py                        # Task 12: DavinciCLIGroup, --verbose/--debug
└── commands/
    ├── __init__.py
    ├── system.py                 # Task 13: core/edition.py 使用
    ├── schema.py                 # Task 14: SchemaNotFoundError
    ├── project.py                # Task 15: ProjectNotFoundError, 共通デコレータ
    ├── timeline.py               # Task 16: マーカー操作含む
    └── clip.py                   # Task 17: NDJSON対応

tests/unit/
├── test_decorators.py
├── test_cli.py
├── test_system.py
├── test_schema.py
├── test_project.py
├── test_timeline.py
└── test_clip.py
```

### Phase 3 への引き継ぎ事項

- 共通デコレータ `@json_input_option`, `@fields_option`, `@dry_run_option` を使用すること
- パス検証は `core/validation.py` の `validate_path()` を使用（`security.py` は作らない）
- 例外は `ProjectNotFoundError`, `SchemaNotFoundError` などカスタム例外を使う（`ValueError` は使わない）
- `_impl` 関数の `dry_run` デフォルトは `False`。MCP の tool 関数でのみ `True` にする
- E2E テストのパッチパスは `davinci_cli.core.connection.get_resolve`（`resolve_bridge` ではない）
- グローバルエラーハンドリングは `DavinciCLIGroup.invoke()` で実装済み
