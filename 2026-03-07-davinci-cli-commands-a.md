# davinci-cli Implementation Plan — Commands (Task 9-14)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** CLIエントリーポイントとコマンドグループ（system/schema/project/timeline/clip）を構築する
**Architecture:** _impl純粋関数でCLI/MCPを共有。エージェントファースト（--json/--fields/--dry-run）
**Tech Stack:** Python 3.10+, Click, Pydantic v2, pytest

---

## 前提: 共通パターン

全コマンドで以下のパターンに従う。

```python
# _impl関数: CLI/MCP共有の純粋関数
def <command>_impl(**kwargs) -> dict | list:
    ...

# CLIコマンド: _implをラップ
@cli.command()
@common_options
def <command>(**kwargs):
    result = <command>_impl(**kwargs)
    output(result)  # --pretty / NDJSON自動判定
```

共通オプションマクロ（`src/davinci_cli/decorators.py` で定義済み想定）:
- `@json_input_option` → `--json '{...}'`
- `@fields_option` → `--fields name,id`
- `@dry_run_option` → `--dry-run`

エラー終了コード:
- `ResolveNotRunningError` → exit 1
- `EditionError` → exit 2
- `ValidationError` → exit 3

---

### Task 9: cli.py — Clickエントリーポイント

**Files:**
- Create: `src/davinci_cli/cli.py`
- Test: `tests/unit/test_cli.py`

**What to implement:**

```python
import click
from davinci_cli.exceptions import ResolveNotRunningError, EditionError, ValidationError

@click.group()
@click.option("--pretty", is_flag=True, default=False, help="Human-readable JSON output")
@click.pass_context
def dr(ctx: click.Context, pretty: bool) -> None:
    """DaVinci Resolve CLI — agent-first interface."""
    ctx.ensure_object(dict)
    ctx.obj["pretty"] = pretty

# サブグループ登録
from davinci_cli.commands import system, schema, project, timeline, clip
dr.add_command(system.system)
dr.add_command(schema.schema)
dr.add_command(project.project)
dr.add_command(timeline.timeline)
dr.add_command(clip.clip)

# グローバルエラーハンドラ
def handle_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ResolveNotRunningError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        except EditionError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(2)
        except ValidationError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(3)
    return wrapper
```

エントリーポイント設定（`pyproject.toml`）:
```toml
[project.scripts]
dr = "davinci_cli.cli:dr"
```

**Key tests:**

```python
from click.testing import CliRunner
from davinci_cli.cli import dr

def test_dr_help():
    result = CliRunner().invoke(dr, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output

def test_dr_pretty_flag_propagates(monkeypatch):
    # --pretty がコンテキストに格納されること
    runner = CliRunner()
    result = runner.invoke(dr, ["--pretty", "system", "ping"])
    # pretty=True がコンテキストに設定されていること

def test_resolve_not_running_exits_1(monkeypatch):
    monkeypatch.setattr("davinci_cli.commands.system.ping_impl",
                        lambda: (_ for _ in ()).throw(ResolveNotRunningError()))
    result = CliRunner().invoke(dr, ["system", "ping"])
    assert result.exit_code == 1

def test_edition_error_exits_2(monkeypatch): ...
def test_validation_error_exits_3(monkeypatch): ...

def test_subcommands_registered():
    assert "system" in dr.commands
    assert "schema" in dr.commands
    assert "project" in dr.commands
    assert "timeline" in dr.commands
    assert "clip" in dr.commands
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_cli.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_cli.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/cli.py tests/unit/test_cli.py
git commit -m "feat: add CLI entrypoint with global error handlers (exit codes for each error type)"
```

---

### Task 10: commands/system.py — dr system

**Files:**
- Create: `src/davinci_cli/commands/system.py`
- Test: `tests/unit/test_system.py`

**What to implement:**

```python
import click
from davinci_cli.output import output
from davinci_cli.resolve_bridge import get_resolve  # DaVinci Resolve接続

@click.group()
def system():
    """System information commands."""

def ping_impl() -> dict:
    resolve = get_resolve()  # 接続失敗時 ResolveNotRunningError
    version = resolve.GetVersionString()
    return {"status": "ok", "version": version}

@system.command()
@click.pass_context
def ping(ctx):
    """Resolve接続確認。"""
    result = ping_impl()
    output(result, pretty=ctx.obj.get("pretty"))

def version_impl() -> dict:
    resolve = get_resolve()
    return {
        "version": resolve.GetVersionString(),
        "edition": _detect_edition(resolve),
    }

def edition_impl() -> dict:
    resolve = get_resolve()
    return {
        "edition": _detect_edition(resolve),
        "product_name": resolve.GetProductName(),
    }

def info_impl() -> dict:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    return {
        "version": resolve.GetVersionString(),
        "edition": _detect_edition(resolve),
        "product_name": resolve.GetProductName(),
        "current_project": project.GetName() if project else None,
    }

def _detect_edition(resolve) -> str:
    # Studio版はGetActiveLicense等で判別
    return "studio" if _has_studio_features(resolve) else "free"
```

**Key tests:**

```python
# Resolveをモックして各_impl関数をユニットテスト

def test_ping_impl_ok(mock_resolve):
    mock_resolve.GetVersionString.return_value = "18.6.4"
    result = ping_impl()
    assert result == {"status": "ok", "version": "18.6.4"}

def test_ping_impl_resolve_not_running(monkeypatch):
    monkeypatch.setattr("davinci_cli.resolve_bridge.get_resolve",
                        lambda: (_ for _ in ()).throw(ResolveNotRunningError()))
    with pytest.raises(ResolveNotRunningError):
        ping_impl()

def test_version_impl_returns_edition(mock_resolve): ...
def test_edition_impl_returns_product_name(mock_resolve): ...
def test_info_impl_includes_current_project(mock_resolve): ...

# CLIレベルのテスト
def test_dr_system_ping_cli(mock_resolve):
    result = CliRunner().invoke(dr, ["system", "ping"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_system.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_system.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/commands/system.py tests/unit/test_system.py
git commit -m "feat: add dr system commands (ping/version/edition/info)"
```

---

### Task 11: commands/schema.py — dr schema

**Files:**
- Create: `src/davinci_cli/commands/schema.py`
- Test: `tests/unit/test_schema.py`

**What to implement:**

スキーマレジストリ設計:
```python
# src/davinci_cli/schema_registry.py
from typing import Type
from pydantic import BaseModel

# コマンドパス → (InputModel | None, OutputModel) のマッピング
SCHEMA_REGISTRY: dict[str, tuple[type[BaseModel] | None, type[BaseModel]]] = {}

def register_schema(command_path: str,
                    output_model: type[BaseModel],
                    input_model: type[BaseModel] | None = None):
    SCHEMA_REGISTRY[command_path] = (input_model, output_model)
```

各コマンドファイルで登録:
```python
# commands/project.py 内
register_schema("project.list", output_model=ProjectListOutput)
register_schema("project.open", output_model=ProjectOpenOutput, input_model=ProjectOpenInput)
```

schema コマンド本体:
```python
import click, json
from davinci_cli.schema_registry import SCHEMA_REGISTRY

@click.group()
def schema():
    """Runtime schema resolution for agent use."""

def schema_impl(command_path: str) -> dict:
    if command_path not in SCHEMA_REGISTRY:
        available = list(SCHEMA_REGISTRY.keys())
        raise ValueError(f"Unknown command: {command_path}. Available: {available}")
    input_model, output_model = SCHEMA_REGISTRY[command_path]
    result = {"command": command_path, "output_schema": output_model.model_json_schema()}
    if input_model:
        result["input_schema"] = input_model.model_json_schema()
    return result

@schema.command(name="show")
@click.argument("command_path")  # e.g. "project.list"
@click.pass_context
def show(ctx, command_path: str):
    """コマンドのJSON Schemaを出力する。"""
    result = schema_impl(command_path)
    output(result, pretty=ctx.obj.get("pretty"))

@schema.command(name="list")
@click.pass_context
def list_schemas(ctx):
    """登録済み全コマンドのスキーマ一覧を出力。"""
    result = [{"command": k} for k in sorted(SCHEMA_REGISTRY.keys())]
    output(result, pretty=ctx.obj.get("pretty"))
```

**Key tests:**

```python
def test_schema_impl_project_list():
    result = schema_impl("project.list")
    assert result["command"] == "project.list"
    assert "output_schema" in result
    assert result["output_schema"]["type"] == "array"

def test_schema_impl_project_open_has_input():
    result = schema_impl("project.open")
    assert "input_schema" in result
    assert "name" in result["input_schema"]["properties"]

def test_schema_impl_unknown_command():
    with pytest.raises(ValueError, match="Unknown command"):
        schema_impl("nonexistent.command")

def test_schema_list_all_commands():
    result = schema_list_impl()
    commands = [r["command"] for r in result]
    assert "project.list" in commands
    assert "timeline.list" in commands
    assert "clip.list" in commands

def test_dr_schema_show_cli():
    result = CliRunner().invoke(dr, ["schema", "show", "project.list"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "output_schema" in data
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_schema.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_schema.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/commands/schema.py src/davinci_cli/schema_registry.py tests/unit/test_schema.py
git commit -m "feat: add dr schema command for runtime self-resolution by agents"
```

---

### Task 12: commands/project.py — dr project

**Files:**
- Create: `src/davinci_cli/commands/project.py`
- Test: `tests/unit/test_project.py`

**What to implement:**

Pydanticモデル:
```python
class ProjectInfo(BaseModel):
    name: str
    id: str | None = None

class ProjectListOutput(BaseModel):
    projects: list[ProjectInfo]

class ProjectOpenInput(BaseModel):
    name: str

class ProjectSettingsGetOutput(BaseModel):
    key: str
    value: str | int | float | bool | None
```

_impl関数群:
```python
def project_list_impl(fields: list[str] | None = None) -> list[dict]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    names = pm.GetProjectListInCurrentFolder()
    projects = [{"name": n} for n in names]
    if fields:
        projects = [{k: p[k] for k in fields if k in p} for p in projects]
    return projects

def project_open_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "open", "name": name}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.LoadProject(name)
    if not project:
        raise ValueError(f"Project not found: {name}")
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
    ...

def project_delete_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "delete", "name": name}
    # 破壊的操作: 確認済みのみ実行
    ...

def project_save_impl() -> dict:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    pm.GetCurrentProject().SaveProject()
    return {"saved": True}

def project_info_impl(fields: list[str] | None = None) -> dict:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    info = {
        "name": project.GetName(),
        "timeline_count": project.GetTimelineCount(),
        "fps": project.GetSetting("timelineFrameRate"),
    }
    if fields:
        info = {k: v for k, v in info.items() if k in fields}
    return info

def project_settings_get_impl(key: str | None = None) -> dict:
    ...

def project_settings_set_impl(key: str, value: str, dry_run: bool = False) -> dict:
    ...
```

CLIコマンド（`--json`入力パターン）:
```python
@project.command(name="open")
@click.argument("name", required=False)
@click.option("--json", "json_input", default=None, help='JSON input e.g. \'{"name": "MyProject"}\'')
@click.option("--dry-run", is_flag=True)
@click.pass_context
def project_open(ctx, name, json_input, dry_run):
    if json_input:
        data = ProjectOpenInput.model_validate_json(json_input)
        name = data.name
    if not name:
        raise click.UsageError("name is required (or use --json)")
    result = project_open_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))
```

スキーマ登録（ファイル末尾）:
```python
register_schema("project.list", output_model=ProjectListOutput)
register_schema("project.open", output_model=ProjectOpenOutput, input_model=ProjectOpenInput)
register_schema("project.create", output_model=ProjectCreateOutput, input_model=ProjectCreateInput)
register_schema("project.delete", output_model=ProjectDeleteOutput, input_model=ProjectDeleteInput)
register_schema("project.info", output_model=ProjectInfo)
register_schema("project.settings.get", output_model=ProjectSettingsGetOutput)
register_schema("project.settings.set", output_model=ProjectSettingsSetOutput, input_model=ProjectSettingsSetInput)
```

**Key tests:**

```python
def test_project_list_impl_returns_list(mock_resolve):
    mock_resolve.GetProjectManager().GetProjectListInCurrentFolder.return_value = ["Proj1", "Proj2"]
    result = project_list_impl()
    assert len(result) == 2
    assert result[0]["name"] == "Proj1"

def test_project_list_fields_filter(mock_resolve):
    result = project_list_impl(fields=["name"])
    assert all("name" in p for p in result)
    assert all("id" not in p for p in result)  # id未取得なら存在しない

def test_project_open_dry_run():
    result = project_open_impl(name="MyProject", dry_run=True)
    assert result["dry_run"] is True
    assert result["action"] == "open"
    assert result["name"] == "MyProject"

def test_project_open_impl_not_found(mock_resolve):
    mock_resolve.GetProjectManager().LoadProject.return_value = None
    with pytest.raises(ValueError, match="Project not found"):
        project_open_impl(name="NonExistent")

def test_project_delete_dry_run():
    result = project_delete_impl(name="OldProject", dry_run=True)
    assert result["dry_run"] is True
    assert result["action"] == "delete"

def test_project_open_json_input():
    result = CliRunner().invoke(dr, ["project", "open", "--json", '{"name": "Test"}', "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is True

def test_project_open_no_name_error():
    result = CliRunner().invoke(dr, ["project", "open"])
    assert result.exit_code != 0

def test_project_info_fields(mock_resolve):
    result = project_info_impl(fields=["name"])
    assert "name" in result
    assert "fps" not in result
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_project.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_project.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/commands/project.py tests/unit/test_project.py
git commit -m "feat: add dr project commands with --json/--fields/--dry-run support"
```

---

### Task 13: commands/timeline.py — dr timeline

**Files:**
- Create: `src/davinci_cli/commands/timeline.py`
- Test: `tests/unit/test_timeline.py`

**What to implement:**

Pydanticモデル:
```python
class TimelineInfo(BaseModel):
    name: str
    fps: float | None = None
    width: int | None = None
    height: int | None = None
    start_timecode: str | None = None
    track_count: int | None = None

class TimelineCreateInput(BaseModel):
    name: str
    fps: float | None = None
    width: int | None = None
    height: int | None = None

class MarkerInfo(BaseModel):
    frame_id: int
    color: str
    name: str
    note: str | None = None
    duration: int = 1

class TimelineExportInput(BaseModel):
    format: Literal["xml", "aaf", "edl"]
    output: str  # ファイルパス
    timeline: str | None = None  # None=現在のタイムライン
```

_impl関数群:
```python
def timeline_list_impl(fields: list[str] | None = None) -> list[dict]:
    project = _get_current_project()
    count = project.GetTimelineCount()
    timelines = []
    for i in range(1, count + 1):
        tl = project.GetTimelineByIndex(i)
        info = {"name": tl.GetName()}
        if fields is None or "fps" in fields:
            info["fps"] = float(tl.GetSetting("timelineFrameRate"))
        timelines.append(info)
    if fields:
        timelines = [{k: v for k, v in t.items() if k in fields} for t in timelines]
    return timelines

def timeline_current_impl(fields: list[str] | None = None) -> dict:
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ValueError("No current timeline")
    info = {
        "name": tl.GetName(),
        "fps": float(tl.GetSetting("timelineFrameRate")),
        "width": int(tl.GetSetting("timelineResolutionWidth")),
        "height": int(tl.GetSetting("timelineResolutionHeight")),
        "start_timecode": tl.GetStartTimecode(),
    }
    if fields:
        info = {k: v for k, v in info.items() if k in fields}
    return info

def timeline_switch_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "switch", "name": name}
    project = _get_current_project()
    count = project.GetTimelineCount()
    for i in range(1, count + 1):
        tl = project.GetTimelineByIndex(i)
        if tl.GetName() == name:
            project.SetCurrentTimeline(tl)
            return {"switched": name}
    raise ValueError(f"Timeline not found: {name}")

def timeline_create_impl(name: str, fps: float | None = None,
                          width: int | None = None, height: int | None = None,
                          dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "create", "name": name}
    project = _get_current_project()
    media_pool = project.GetMediaPool()
    tl = media_pool.CreateEmptyTimeline(name)
    if not tl:
        raise ValueError(f"Failed to create timeline: {name}")
    return {"created": name}

def timeline_delete_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "delete", "name": name}
    ...

def timeline_export_impl(format: str, output: str,
                          timeline_name: str | None = None,
                          dry_run: bool = False) -> dict:
    FORMAT_MAP = {"xml": ExportType.FCPXML_1_9, "aaf": ExportType.AAF, "edl": ExportType.EDL_CDL}
    if dry_run:
        return {"dry_run": True, "action": "export", "format": format, "output": output}
    project = _get_current_project()
    tl = _get_timeline_by_name(project, timeline_name) if timeline_name else project.GetCurrentTimeline()
    tl.Export(output, FORMAT_MAP[format])
    return {"exported": output, "format": format}

# マーカー操作
def marker_list_impl(timeline_name: str | None = None) -> list[dict]: ...
def marker_add_impl(frame_id: int, color: str, name: str,
                     note: str | None = None, dry_run: bool = False) -> dict: ...
def marker_delete_impl(frame_id: int, dry_run: bool = False) -> dict: ...
```

CLIコマンド（`timeline create`の`--json`入力例）:
```python
@timeline.command(name="create")
@click.option("--json", "json_input", default=None)
@click.option("--name", default=None)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def timeline_create(ctx, json_input, name, dry_run):
    if json_input:
        data = TimelineCreateInput.model_validate_json(json_input)
        name, fps, width, height = data.name, data.fps, data.width, data.height
    result = timeline_create_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))
```

スキーマ登録:
```python
register_schema("timeline.list", output_model=TimelineListOutput)
register_schema("timeline.current", output_model=TimelineInfo)
register_schema("timeline.switch", output_model=TimelineSwitchOutput, input_model=TimelineSwitchInput)
register_schema("timeline.create", output_model=TimelineCreateOutput, input_model=TimelineCreateInput)
register_schema("timeline.delete", output_model=TimelineDeleteOutput, input_model=TimelineDeleteInput)
register_schema("timeline.export", output_model=TimelineExportOutput, input_model=TimelineExportInput)
register_schema("timeline.marker.list", output_model=MarkerListOutput)
register_schema("timeline.marker.add", output_model=MarkerAddOutput, input_model=MarkerAddInput)
register_schema("timeline.marker.delete", output_model=MarkerDeleteOutput, input_model=MarkerDeleteInput)
```

**Key tests:**

```python
def test_timeline_list_impl(mock_project):
    mock_project.GetTimelineCount.return_value = 2
    # index 1,2 それぞれモック設定
    result = timeline_list_impl()
    assert len(result) == 2
    assert "name" in result[0]

def test_timeline_list_fields(mock_project):
    result = timeline_list_impl(fields=["name"])
    assert all(list(t.keys()) == ["name"] for t in result)

def test_timeline_current_impl(mock_project):
    result = timeline_current_impl()
    assert "name" in result
    assert "fps" in result

def test_timeline_current_no_timeline(mock_project):
    mock_project.GetCurrentTimeline.return_value = None
    with pytest.raises(ValueError, match="No current timeline"):
        timeline_current_impl()

def test_timeline_switch_dry_run():
    result = timeline_switch_impl(name="Edit", dry_run=True)
    assert result == {"dry_run": True, "action": "switch", "name": "Edit"}

def test_timeline_switch_not_found(mock_project):
    mock_project.GetTimelineCount.return_value = 0
    with pytest.raises(ValueError, match="Timeline not found"):
        timeline_switch_impl(name="NonExistent")

def test_timeline_create_json_input():
    result = CliRunner().invoke(dr, [
        "timeline", "create",
        "--json", '{"name": "NewTimeline", "fps": 24.0}',
        "--dry-run"
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is True

def test_timeline_export_dry_run():
    result = timeline_export_impl(format="xml", output="/tmp/out.xml", dry_run=True)
    assert result["dry_run"] is True
    assert result["format"] == "xml"

def test_marker_add_dry_run():
    result = marker_add_impl(frame_id=100, color="Blue", name="VFX", dry_run=True)
    assert result["dry_run"] is True
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_timeline.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_timeline.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/commands/timeline.py tests/unit/test_timeline.py
git commit -m "feat: add dr timeline commands including marker operations and export"
```

---

### Task 14: commands/clip.py — dr clip

**Files:**
- Create: `src/davinci_cli/commands/clip.py`
- Test: `tests/unit/test_clip.py`

**What to implement:**

Pydanticモデル:
```python
class ClipInfo(BaseModel):
    index: int
    name: str
    start: str | None = None   # タイムコード文字列
    end: str | None = None
    duration: str | None = None
    type: str | None = None    # "Video", "Audio", "Subtitle" etc.
    track: int | None = None

class ClipPropertyGetOutput(BaseModel):
    index: int
    key: str
    value: str | int | float | bool | None

class ClipPropertySetInput(BaseModel):
    index: int
    key: str
    value: str
```

_impl関数群:
```python
def clip_list_impl(timeline_name: str | None = None,
                    fields: list[str] | None = None) -> list[dict]:
    project = _get_current_project()
    if timeline_name:
        tl = _get_timeline_by_name(project, timeline_name)
    else:
        tl = project.GetCurrentTimeline()
        if not tl:
            raise ValueError("No current timeline")

    clips = []
    # 全トラック（video/audio）からクリップ収集
    for track_type in ["video", "audio"]:
        track_count = tl.GetTrackCount(track_type)
        for track_idx in range(1, track_count + 1):
            track_clips = tl.GetItemListInTrack(track_type, track_idx)
            for i, c in enumerate(track_clips):
                info = {
                    "index": len(clips),
                    "name": c.GetName(),
                    "start": c.GetStart(),
                    "end": c.GetEnd(),
                    "duration": c.GetDuration(),
                    "type": track_type,
                    "track": track_idx,
                }
                if fields:
                    info = {k: v for k, v in info.items() if k in fields}
                clips.append(info)
    return clips

def clip_info_impl(index: int, fields: list[str] | None = None) -> dict:
    clips = clip_list_impl()
    if index < 0 or index >= len(clips):
        raise IndexError(f"Clip index {index} out of range (0..{len(clips)-1})")
    clip = clips[index]
    if fields:
        clip = {k: v for k, v in clip.items() if k in fields}
    return clip

def clip_select_impl(index: int) -> dict:
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    clips = clip_list_impl()
    if index < 0 or index >= len(clips):
        raise IndexError(f"Clip index {index} out of range")
    # SetCurrentVideoItem等でクリップ選択
    return {"selected": index, "name": clips[index]["name"]}

def clip_property_get_impl(index: int, key: str) -> dict:
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    clip_item = _get_clip_item_by_index(tl, index)
    value = clip_item.GetProperty(key)
    return {"index": index, "key": key, "value": value}

def clip_property_set_impl(index: int, key: str, value: str,
                             dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "property_set",
                "index": index, "key": key, "value": value}
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    clip_item = _get_clip_item_by_index(tl, index)
    clip_item.SetProperty(key, value)
    return {"set": True, "index": index, "key": key, "value": value}
```

CLIコマンド:
```python
@click.group()
def clip():
    """Clip operations."""

@clip.command(name="list")
@click.option("--timeline", default=None, help="Timeline name (default: current)")
@click.option("--fields", default=None, help="Comma-separated field list")
@click.pass_context
def clip_list(ctx, timeline, fields):
    field_list = fields.split(",") if fields else None
    result = clip_list_impl(timeline_name=timeline, fields=field_list)
    output(result, pretty=ctx.obj.get("pretty"), ndjson=not sys.stdout.isatty())

@clip.command(name="info")
@click.argument("index", type=int)
@click.option("--fields", default=None)
@click.pass_context
def clip_info(ctx, index, fields):
    field_list = fields.split(",") if fields else None
    result = clip_info_impl(index=index, fields=field_list)
    output(result, pretty=ctx.obj.get("pretty"))

@clip.group(name="property")
def clip_property():
    """Clip property operations."""

@clip_property.command(name="get")
@click.argument("index", type=int)
@click.argument("key")
@click.pass_context
def property_get(ctx, index, key):
    result = clip_property_get_impl(index=index, key=key)
    output(result, pretty=ctx.obj.get("pretty"))

@clip_property.command(name="set")
@click.argument("index", type=int)
@click.argument("key")
@click.argument("value")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def property_set(ctx, index, key, value, dry_run):
    result = clip_property_set_impl(index=index, key=key, value=value, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))
```

スキーマ登録:
```python
register_schema("clip.list", output_model=ClipListOutput)
register_schema("clip.info", output_model=ClipInfo)
register_schema("clip.select", output_model=ClipSelectOutput, input_model=ClipSelectInput)
register_schema("clip.property.get", output_model=ClipPropertyGetOutput)
register_schema("clip.property.set", output_model=ClipPropertySetOutput, input_model=ClipPropertySetInput)
```

**Key tests:**

```python
def test_clip_list_impl_returns_indexed(mock_timeline):
    # video track 1 に2クリップ
    result = clip_list_impl()
    assert all("index" in c for c in result)
    assert result[0]["index"] == 0

def test_clip_list_fields_filter(mock_timeline):
    result = clip_list_impl(fields=["index", "name"])
    assert all(set(c.keys()) == {"index", "name"} for c in result)

def test_clip_list_with_timeline_name(mock_project):
    result = clip_list_impl(timeline_name="Edit")
    assert isinstance(result, list)

def test_clip_list_no_current_timeline(mock_project):
    mock_project.GetCurrentTimeline.return_value = None
    with pytest.raises(ValueError, match="No current timeline"):
        clip_list_impl()

def test_clip_info_impl(mock_timeline):
    result = clip_info_impl(index=0)
    assert "name" in result
    assert result["index"] == 0

def test_clip_info_out_of_range(mock_timeline):
    with pytest.raises(IndexError):
        clip_info_impl(index=9999)

def test_clip_property_set_dry_run():
    result = clip_property_set_impl(index=0, key="Pan", value="0.5", dry_run=True)
    assert result["dry_run"] is True
    assert result["key"] == "Pan"

def test_clip_property_get_impl(mock_timeline):
    result = clip_property_get_impl(index=0, key="Pan")
    assert result["key"] == "Pan"
    assert "value" in result

def test_clip_list_ndjson_in_pipe(mock_timeline, monkeypatch):
    # 非TTY環境ではNDJSON出力
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    result = CliRunner().invoke(dr, ["clip", "list"])
    lines = result.output.strip().split("\n")
    assert all(json.loads(line) for line in lines)  # 各行がJSON

def test_dr_clip_property_set_cli():
    result = CliRunner().invoke(dr, ["clip", "property", "set", "0", "Pan", "0.5", "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is True
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_clip.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_clip.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/commands/clip.py tests/unit/test_clip.py
git commit -m "feat: add dr clip commands with property get/set and NDJSON output"
```

---

## 統合テスト (全タスク完了後)

```bash
# 全ユニットテスト
python -m pytest tests/unit/ -v

# 統合テスト: サブコマンド一覧確認
dr --help
dr system --help
dr schema list
dr project --help
dr timeline --help
dr clip --help

# スキーマ自己解決の確認
dr schema show project.list
dr schema show project.open
dr schema show timeline.create
dr schema show clip.property.set
```

期待される `dr schema show project.open` 出力:
```json
{
  "command": "project.open",
  "input_schema": {
    "title": "ProjectOpenInput",
    "type": "object",
    "properties": {
      "name": {"title": "Name", "type": "string"}
    },
    "required": ["name"]
  },
  "output_schema": { ... }
}
```

---

## ファイル構造サマリ

```
src/davinci_cli/
├── cli.py                    # Task 9: @click.group dr
├── schema_registry.py        # Task 11: SCHEMA_REGISTRY + register_schema()
└── commands/
    ├── __init__.py
    ├── system.py             # Task 10: ping/version/edition/info
    ├── schema.py             # Task 11: show/list
    ├── project.py            # Task 12: list/open/close/create/delete/save/info/settings
    ├── timeline.py           # Task 13: list/current/switch/create/delete/export/marker
    └── clip.py               # Task 14: list/info/select/property

tests/unit/
├── test_cli.py
├── test_system.py
├── test_schema.py
├── test_project.py
├── test_timeline.py
└── test_clip.py
```
