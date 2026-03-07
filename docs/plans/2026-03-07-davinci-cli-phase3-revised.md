# davinci-cli Implementation Plan — Phase 3: Color/Media/Deliver + MCP + E2E (Revised)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** color/media/deliver コマンド、MCP サーバー（エラーハンドリングラッパー付き）、SKILL.md、E2E テストを構築して davinci-cli を完成させる
**Architecture:** _impl 純粋関数で CLI/MCP を共有。MCP の description にエージェント指示を埋め込む。MCP の tool 関数では `dry_run=True` がデフォルト。
**Tech Stack:** Python 3.10+, Click, FastMCP, Pydantic v2, Rich, pytest

---

## 前提: Phase 1/2 からの引き継ぎ

- `validate_path()` は `core/validation.py` に統合済み（`security.py` は作らない）
- 共通デコレータ: `@json_input_option`, `@fields_option`, `@dry_run_option`
- 例外はカスタム例外を使用（`ValueError` は使わない）
- `_impl` 関数の `dry_run` デフォルトは `False`
- Resolve 接続は `davinci_cli.core.connection.get_resolve`（`resolve_bridge` ではない）
- グローバルエラーハンドリングは `DavinciCLIGroup.invoke()` で実装済み
- `_impl` 関数は常に flat な `list[dict]` または `dict` を返す

## 修正点サマリ（旧計画からの変更）

1. `security.py` 廃止: `validate_path()` は `core/validation.py` を使用
2. MCP エラーハンドリングラッパー追加: 例外をキャッチして構造化エラーレスポンスを返す
3. `dry_run=True` デフォルト設計を MCP 側に明文化
4. E2E テストのパッチパスを `davinci_cli.core.connection.get_resolve` に修正
5. `ValueError` → カスタム例外に統一
6. Task 18-20 で各コマンド実装時に cli.py に color/media/deliver を登録する
7. Task 20 のタスク名から「--dry-run必須」を削除（CLI の default=False は他コマンドと一貫性を保つ）
8. `color.apply-lut` の `output_model` を `LutApplyOutput` に修正（`LutApplyInput` は誤り）
9. `deliver.preset.list` の `output_model` を `PresetListOutput` に修正（`RenderJobInfo` は誤り）
10. `media_import_impl` で `FileNotFoundError` を `ValidationError` にラップ
11. MCP サーバーのファイル名を `mcp_server.py` に統一（タスク名と一致）
12. 全コマンドの schema 登録を網羅（media import/folder create/delete, deliver preset.load/stop/status 等）
13. schema 登録の `output_model` を各 `_impl` 関数の実際の戻り値と一致するよう修正:
    - `color.copy-grade` → `ColorCopyGradeOutput`（`ColorResetOutput` から変更）
    - `color.paste-grade` → `ColorPasteGradeOutput`（`ColorResetOutput` から変更）
    - `color.node.add` → `NodeAddOutput`（`NodeInfo` から変更）
    - `color.node.delete` → `NodeDeleteOutput`（`NodeInfo` から変更）
    - `color.still.grab` → `StillGrabOutput`（`StillInfo` から変更）
    - `color.still.apply` → `StillApplyOutput`（`StillInfo` から変更）
    - `media.folder.create` → `FolderCreateOutput`（`FolderInfo` から変更）
    - `media.folder.delete` → `FolderDeleteOutput`（`FolderInfo` から変更）
    - `deliver.preset.load` → `PresetLoadOutput`（`PresetListOutput` から変更）
    - `deliver.add-job` → `DeliverAddJobOutput`（`RenderJobInfo` から変更）
14. `deliver.add_job` → `deliver.add-job`、`deliver.list_jobs` → `deliver.list-jobs` に命名規則統一（ハイフン）
15. `deliver.start` に `input_model=DeliverStartInput` を追加（`job_ids` パラメータ対応）
16. `--fields` は表示フィルタ。schema は常にフルレスポンスの型を定義する（`--fields` 適用後の部分出力は schema 対象外）

---

### Task 18: commands/color.py — dr color（core/validation.py の validate_path 使用）

**Files:**
- Create: `src/davinci_cli/commands/color.py`
- Modify: `src/davinci_cli/cli.py`（color コマンドを `_register_commands()` に追加）
- Test: `tests/unit/test_color.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_color.py
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.color import (
    color_apply_lut_impl,
    color_reset_impl,
    color_copy_grade_impl,
    color_paste_grade_impl,
    node_list_impl,
    node_add_impl,
    node_delete_impl,
    still_grab_impl,
    still_list_impl,
    still_apply_impl,
)
from davinci_cli.core.exceptions import ValidationError, ProjectNotOpenError


RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()
    timeline = MagicMock()

    clip = MagicMock()
    clip.GetName.return_value = "A001_C001.mov"
    clip.GetProperty.return_value = "0.0"
    clip.GetNodeCount.return_value = 3

    timeline.GetTrackCount.return_value = 1
    timeline.GetItemListInTrack.return_value = [clip]
    project.GetCurrentTimeline.return_value = timeline
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestColorApplyLutImpl:
    def test_path_traversal_rejected(self):
        """core/validation.py の validate_path が拒絶すること"""
        with pytest.raises(ValidationError, match="path traversal"):
            color_apply_lut_impl(clip_index=0, lut_path="../../../etc/passwd")

    def test_invalid_extension_rejected(self):
        with pytest.raises(ValidationError, match="not allowed"):
            color_apply_lut_impl(clip_index=0, lut_path="/tmp/malicious.exe")

    def test_dry_run(self):
        result = color_apply_lut_impl(
            clip_index=0, lut_path="/valid/path.cube", dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "apply_lut"

    def test_apply_lut(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_apply_lut_impl(
                clip_index=0, lut_path="/luts/rec709.cube"
            )
        assert "applied" in result


class TestColorResetImpl:
    def test_dry_run(self):
        result = color_reset_impl(clip_index=2, dry_run=True)
        assert result == {"dry_run": True, "action": "reset", "clip_index": 2}

    def test_reset(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_reset_impl(clip_index=0)
        assert result["reset"] is True


class TestColorGradeImpl:
    def test_copy_grade(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_copy_grade_impl(from_index=0)
        assert result["copied_from"] == 0

    def test_paste_grade_dry_run(self):
        result = color_paste_grade_impl(to_index=3, dry_run=True)
        assert result["dry_run"] is True


class TestNodeImpl:
    def test_node_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = node_list_impl(clip_index=0)
        assert isinstance(result, list)

    def test_node_add_dry_run(self):
        result = node_add_impl(clip_index=0, dry_run=True)
        assert result["dry_run"] is True

    def test_node_delete_dry_run(self):
        result = node_delete_impl(clip_index=0, node_index=1, dry_run=True)
        assert result["dry_run"] is True


class TestStillImpl:
    def test_still_grab_dry_run(self):
        result = still_grab_impl(clip_index=0, dry_run=True)
        assert result["dry_run"] is True

    def test_still_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = still_list_impl()
        assert isinstance(result, list)

    def test_still_apply_dry_run(self):
        result = still_apply_impl(clip_index=0, still_index=0, dry_run=True)
        assert result["dry_run"] is True


class TestColorCLI:
    def test_apply_lut_dry_run(self, tmp_path):
        lut_file = tmp_path / "test.cube"
        lut_file.touch()
        result = CliRunner().invoke(
            dr, ["color", "apply-lut", "0", str(lut_file), "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_reset_dry_run(self):
        result = CliRunner().invoke(dr, ["color", "reset", "0", "--dry-run"])
        assert result.exit_code == 0
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_color.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/commands/color.py
"""dr color — カラーグレーディングコマンド。

パス検証は core/validation.py の validate_path() を使用する。
security.py は作らない。allowed_extensions で LUT ファイルの拡張子を制限する。
"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.core.validation import validate_path
from davinci_cli.decorators import dry_run_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema


# LUT 許可拡張子
_LUT_EXTENSIONS = [".cube", ".3dl", ".lut", ".mga", ".m3d"]


# --- Pydantic Models ---

class LutApplyInput(BaseModel):
    clip_index: int
    lut_path: str

class LutApplyOutput(BaseModel):
    applied: str | None = None
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None
    lut_path: str | None = None

class ColorResetOutput(BaseModel):
    reset: bool | None = None
    clip_index: int
    dry_run: bool | None = None
    action: str | None = None

class ColorCopyGradeOutput(BaseModel):
    """color.copy-grade の戻り値。"""
    copied_from: int

class ColorPasteGradeOutput(BaseModel):
    """color.paste-grade の戻り値。"""
    pasted_to: int | None = None
    dry_run: bool | None = None
    action: str | None = None
    to_index: int | None = None

class NodeInfo(BaseModel):
    """color.node.list の戻り値の各要素。"""
    index: int
    label: str | None = None

class NodeAddOutput(BaseModel):
    """color.node.add の戻り値。"""
    added: bool | None = None
    clip_index: int | None = None
    dry_run: bool | None = None
    action: str | None = None

class NodeDeleteOutput(BaseModel):
    """color.node.delete の戻り値。"""
    deleted: bool | None = None
    clip_index: int | None = None
    node_index: int | None = None
    dry_run: bool | None = None
    action: str | None = None

class StillInfo(BaseModel):
    """color.still.list の戻り値の各要素。"""
    index: int
    label: str | None = None

class StillGrabOutput(BaseModel):
    """color.still.grab の戻り値。"""
    grabbed: bool | None = None
    clip_index: int | None = None
    dry_run: bool | None = None
    action: str | None = None

class StillApplyOutput(BaseModel):
    """color.still.apply の戻り値。"""
    applied: bool | None = None
    clip_index: int | None = None
    still_index: int | None = None
    dry_run: bool | None = None
    action: str | None = None


# --- Helper ---

def _get_clip_item_by_index(tl: Any, index: int) -> Any:
    """タイムラインからインデックス指定でクリップアイテムを取得する。"""
    clips: list[Any] = []
    for track_type in ["video", "audio"]:
        track_count = tl.GetTrackCount(track_type)
        for track_idx in range(1, track_count + 1):
            track_clips = tl.GetItemListInTrack(track_type, track_idx) or []
            clips.extend(track_clips)
    if index < 0 or index >= len(clips):
        raise ValidationError(
            field="clip_index",
            reason=f"Clip index {index} out of range (0..{len(clips) - 1})",
        )
    return clips[index]


def _get_current_timeline() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    return tl


# --- _impl Functions ---

def color_apply_lut_impl(
    clip_index: int,
    lut_path: str,
    dry_run: bool = False,
) -> dict:
    # core/validation.py の統合版 validate_path を使用（Path.resolve() + allowed_extensions）
    validated = validate_path(lut_path, allowed_extensions=_LUT_EXTENSIONS)
    if dry_run:
        return {
            "dry_run": True,
            "action": "apply_lut",
            "clip_index": clip_index,
            "lut_path": str(validated),
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    clip_item.SetLUT(1, str(validated))  # node index 1 にLUT適用
    return {"applied": str(validated), "clip_index": clip_index}


def color_reset_impl(clip_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "reset", "clip_index": clip_index}
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    clip_item.ResetAllGrades()
    return {"reset": True, "clip_index": clip_index}


def color_copy_grade_impl(from_index: int) -> dict:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, from_index)
    clip_item.CopyGrades()
    return {"copied_from": from_index}


def color_paste_grade_impl(to_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "paste_grade", "to_index": to_index}
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, to_index)
    clip_item.PasteGrades()
    return {"pasted_to": to_index}


def node_list_impl(clip_index: int) -> list[dict]:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    node_count = clip_item.GetNodeCount()
    return [
        {"index": i, "label": f"Node {i}"} for i in range(1, node_count + 1)
    ]


def node_add_impl(clip_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "node_add", "clip_index": clip_index}
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    clip_item.AddNode()
    return {"added": True, "clip_index": clip_index}


def node_delete_impl(clip_index: int, node_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "node_delete",
            "clip_index": clip_index,
            "node_index": node_index,
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    clip_item.DeleteNode(node_index)
    return {"deleted": True, "clip_index": clip_index, "node_index": node_index}


def still_grab_impl(clip_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "still_grab", "clip_index": clip_index}
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    clip_item.GrabStill()
    return {"grabbed": True, "clip_index": clip_index}


def still_list_impl() -> list[dict]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    gallery = project.GetGallery()
    if not gallery:
        return []
    album = gallery.GetCurrentStillAlbum()
    if not album:
        return []
    stills = album.GetStills() or []
    return [
        {"index": i, "label": getattr(s, "GetLabel", lambda: f"Still {i}")()}
        for i, s in enumerate(stills)
    ]


def still_apply_impl(
    clip_index: int,
    still_index: int,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "still_apply",
            "clip_index": clip_index,
            "still_index": still_index,
        }
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, clip_index)
    resolve = get_resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    gallery = project.GetGallery()
    album = gallery.GetCurrentStillAlbum()
    stills = album.GetStills()
    if still_index < 0 or still_index >= len(stills):
        raise ValidationError(
            field="still_index",
            reason=f"Still index {still_index} out of range",
        )
    clip_item.ApplyGradeFromStill(stills[still_index])
    return {"applied": True, "clip_index": clip_index, "still_index": still_index}


# --- CLI Commands ---

@click.group()
def color() -> None:
    """Color grading operations."""


@color.command(name="apply-lut")
@click.argument("clip_index", type=int)
@click.argument("lut_path")
@dry_run_option
@click.pass_context
def apply_lut(ctx: click.Context, clip_index: int, lut_path: str, dry_run: bool) -> None:
    """LUT をクリップに適用する。"""
    result = color_apply_lut_impl(clip_index=clip_index, lut_path=lut_path, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="reset")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def color_reset(ctx: click.Context, clip_index: int, dry_run: bool) -> None:
    """グレードをリセットする。"""
    result = color_reset_impl(clip_index=clip_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="copy-grade")
@click.option("--from", "from_index", type=int, required=True)
@click.pass_context
def copy_grade(ctx: click.Context, from_index: int) -> None:
    """グレードをコピーする。"""
    result = color_copy_grade_impl(from_index=from_index)
    output(result, pretty=ctx.obj.get("pretty"))


@color.command(name="paste-grade")
@click.option("--to", "to_index", type=int, required=True)
@dry_run_option
@click.pass_context
def paste_grade(ctx: click.Context, to_index: int, dry_run: bool) -> None:
    """グレードをペーストする。"""
    result = color_paste_grade_impl(to_index=to_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color.group(name="node")
def color_node() -> None:
    """Node operations."""


@color_node.command(name="list")
@click.argument("clip_index", type=int)
@click.pass_context
def node_list_cmd(ctx: click.Context, clip_index: int) -> None:
    """ノード一覧。"""
    result = node_list_impl(clip_index=clip_index)
    output(result, pretty=ctx.obj.get("pretty"))


@color_node.command(name="add")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def node_add_cmd(ctx: click.Context, clip_index: int, dry_run: bool) -> None:
    """ノード追加。"""
    result = node_add_impl(clip_index=clip_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color_node.command(name="delete")
@click.argument("clip_index", type=int)
@click.argument("node_index", type=int)
@dry_run_option
@click.pass_context
def node_delete_cmd(
    ctx: click.Context, clip_index: int, node_index: int, dry_run: bool
) -> None:
    """ノード削除。"""
    result = node_delete_impl(
        clip_index=clip_index, node_index=node_index, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


@color.group(name="still")
def color_still() -> None:
    """Still operations."""


@color_still.command(name="grab")
@click.argument("clip_index", type=int)
@dry_run_option
@click.pass_context
def still_grab_cmd(ctx: click.Context, clip_index: int, dry_run: bool) -> None:
    """スチルを取得する。"""
    result = still_grab_impl(clip_index=clip_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@color_still.command(name="list")
@click.pass_context
def still_list_cmd(ctx: click.Context) -> None:
    """スチル一覧。"""
    result = still_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@color_still.command(name="apply")
@click.argument("clip_index", type=int)
@click.argument("still_index", type=int)
@dry_run_option
@click.pass_context
def still_apply_cmd(
    ctx: click.Context, clip_index: int, still_index: int, dry_run: bool
) -> None:
    """スチルを適用する。"""
    result = still_apply_impl(
        clip_index=clip_index, still_index=still_index, dry_run=dry_run
    )
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("color.apply-lut", output_model=LutApplyOutput, input_model=LutApplyInput)
register_schema("color.reset", output_model=ColorResetOutput)
register_schema("color.copy-grade", output_model=ColorCopyGradeOutput)
register_schema("color.paste-grade", output_model=ColorPasteGradeOutput)
register_schema("color.node.list", output_model=NodeInfo)
register_schema("color.node.add", output_model=NodeAddOutput)
register_schema("color.node.delete", output_model=NodeDeleteOutput)
register_schema("color.still.list", output_model=StillInfo)
register_schema("color.still.grab", output_model=StillGrabOutput)
register_schema("color.still.apply", output_model=StillApplyOutput)
```

**Step 3.5: cli.py に color コマンドを登録**

`src/davinci_cli/cli.py` の `_register_commands()` に color を追加:
```python
def _register_commands() -> None:
    from davinci_cli.commands import system, schema, project, timeline, clip, color
    dr.add_command(system.system)
    dr.add_command(schema.schema)
    dr.add_command(project.project)
    dr.add_command(timeline.timeline)
    dr.add_command(clip.clip)
    dr.add_command(color.color)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_color.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/color.py src/davinci_cli/cli.py tests/unit/test_color.py
git commit -m "feat: commands/color.py — core/validation.py使用、security.py不使用、cli.py登録"
```

---

### Task 19: commands/media.py — dr media

**Files:**
- Create: `src/davinci_cli/commands/media.py`
- Modify: `src/davinci_cli/cli.py`（media コマンドを `_register_commands()` に追加）
- Test: `tests/unit/test_media.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_media.py
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.media import (
    media_list_impl,
    media_import_impl,
    folder_list_impl,
    folder_create_impl,
    folder_delete_impl,
)
from davinci_cli.core.exceptions import ValidationError, ProjectNotOpenError


RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()

    clip = MagicMock()
    clip.GetName.return_value = "clip1.mov"
    clip.GetClipProperty.side_effect = lambda k: {
        "File Path": "/media/clip1.mov",
        "Duration": "00:00:10:00",
        "FPS": "24.0",
    }.get(k, "")

    root_folder = MagicMock()
    root_folder.GetClipList.return_value = [clip]
    root_folder.GetSubFolderList.return_value = []

    media_pool = MagicMock()
    media_pool.GetRootFolder.return_value = root_folder
    media_pool.ImportMedia.return_value = [clip]

    project.GetMediaPool.return_value = media_pool
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestMediaListImpl:
    def test_returns_media_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = media_list_impl()
        assert len(result) == 1
        assert result[0]["clip_name"] == "clip1.mov"

    def test_fields_filter(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = media_list_impl(fields=["clip_name"])
        assert all(set(r.keys()) == {"clip_name"} for r in result)

    def test_folder_not_found(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="not found"):
                media_list_impl(folder_name="NonExistent")


class TestMediaImportImpl:
    def test_path_traversal_rejected(self):
        """core/validation.py が拒絶すること"""
        with pytest.raises(ValidationError, match="path traversal"):
            media_import_impl(paths=["../../../etc/shadow"])

    def test_file_not_found(self):
        """FileNotFoundError ではなく ValidationError にラップされること"""
        with pytest.raises(ValidationError, match="not found"):
            media_import_impl(paths=["/nonexistent/file.mp4"])

    def test_import_success(self, mock_resolve, tmp_path):
        test_file = tmp_path / "video.mp4"
        test_file.touch()
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = media_import_impl(paths=[str(test_file)])
        assert result["imported_count"] == 1


class TestFolderImpl:
    def test_folder_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = folder_list_impl()
        assert isinstance(result, list)

    def test_folder_create(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = folder_create_impl(name="VFX Shots")
        assert result["created"] == "VFX Shots"

    def test_folder_delete_dry_run(self):
        result = folder_delete_impl(name="old_folder", dry_run=True)
        assert result["dry_run"] is True


class TestMediaCLI:
    def test_media_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(
                dr, ["media", "list", "--fields", "clip_name"]
            )
        assert result.exit_code == 0

    def test_media_folder_delete_dry_run(self):
        result = CliRunner().invoke(
            dr, ["media", "folder", "delete", "old", "--dry-run"]
        )
        assert result.exit_code == 0
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_media.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/commands/media.py
"""dr media — メディアプール操作コマンド。

パス検証は core/validation.py の validate_path() を使用する。
"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.core.validation import validate_path
from davinci_cli.decorators import fields_option, dry_run_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema


# --- Pydantic Models ---

class MediaItem(BaseModel):
    clip_name: str
    file_path: str | None = None
    duration: str | None = None
    fps: str | None = None

class MediaImportInput(BaseModel):
    paths: list[str]

class MediaImportOutput(BaseModel):
    imported_count: int
    paths: list[str]

class FolderInfo(BaseModel):
    """media.folder.list の戻り値の各要素。"""
    name: str
    clip_count: int | None = None

class FolderCreateOutput(BaseModel):
    """media.folder.create の戻り値。"""
    created: str

class FolderCreateInput(BaseModel):
    name: str

class FolderDeleteOutput(BaseModel):
    """media.folder.delete の戻り値。"""
    deleted: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    name: str | None = None

class FolderDeleteInput(BaseModel):
    name: str


# --- Helper ---

def _get_media_pool() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    return project.GetMediaPool()


def _find_folder_by_name(root_folder: Any, name: str) -> Any:
    """フォルダを再帰的に探す。"""
    for sub in root_folder.GetSubFolderList() or []:
        if sub.GetName() == name:
            return sub
        found = _find_folder_by_name(sub, name)
        if found:
            return found
    return None


# --- _impl Functions ---

def media_list_impl(
    folder_name: str | None = None,
    fields: list[str] | None = None,
) -> list[dict]:
    media_pool = _get_media_pool()

    if folder_name:
        folder = _find_folder_by_name(media_pool.GetRootFolder(), folder_name)
        if not folder:
            raise ValidationError(
                field="folder",
                reason=f"Folder not found: {folder_name}",
            )
    else:
        folder = media_pool.GetRootFolder()

    clips = folder.GetClipList() or []
    items: list[dict] = []
    for clip in clips:
        info = {
            "clip_name": clip.GetName(),
            "file_path": clip.GetClipProperty("File Path"),
            "duration": clip.GetClipProperty("Duration"),
            "fps": clip.GetClipProperty("FPS"),
        }
        if fields:
            info = {k: v for k, v in info.items() if k in fields}
        items.append(info)
    return items


def media_import_impl(paths: list[str]) -> dict:
    # 全パスを core/validation.py の validate_path で検証
    # FileNotFoundError は ValidationError にラップする
    # （CLIのグローバルハンドラは DavinciCLIError を構造化出力する。
    #   FileNotFoundError をそのまま送出するとフォールバック捕捉になるが、
    #   ValidationError にラップすることで exit_code=3 と明確なエラー種別を提供する）
    validated: list[str] = []
    for p in paths:
        vp = validate_path(p)
        if not vp.exists():
            raise ValidationError(
                field="path",
                reason=f"File not found: {p}",
            )
        validated.append(str(vp))

    media_pool = _get_media_pool()
    imported = media_pool.ImportMedia(validated)
    return {
        "imported_count": len(imported) if imported else 0,
        "paths": validated,
    }


def folder_list_impl() -> list[dict]:
    media_pool = _get_media_pool()
    root = media_pool.GetRootFolder()
    folders: list[dict] = []
    for sub in root.GetSubFolderList() or []:
        clips = sub.GetClipList() or []
        folders.append({
            "name": sub.GetName(),
            "clip_count": len(clips),
        })
    return folders


def folder_create_impl(name: str) -> dict:
    media_pool = _get_media_pool()
    folder = media_pool.AddSubFolder(media_pool.GetRootFolder(), name)
    if not folder:
        raise ValidationError(
            field="name",
            reason=f"Failed to create folder: {name}",
        )
    return {"created": name}


def folder_delete_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "folder_delete", "name": name}
    media_pool = _get_media_pool()
    folder = _find_folder_by_name(media_pool.GetRootFolder(), name)
    if not folder:
        raise ValidationError(field="name", reason=f"Folder not found: {name}")
    media_pool.DeleteFolders([folder])
    return {"deleted": name}


# --- CLI Commands ---

@click.group()
def media() -> None:
    """Media pool operations."""


@media.command(name="list")
@click.option("--folder", default=None, help="Folder name")
@fields_option
@click.pass_context
def media_list(
    ctx: click.Context, folder: str | None, fields: list[str] | None
) -> None:
    """メディア一覧。"""
    result = media_list_impl(folder_name=folder, fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@media.command(name="import")
@click.argument("paths", nargs=-1, required=True)
@click.pass_context
def media_import(ctx: click.Context, paths: tuple[str, ...]) -> None:
    """メディアインポート（パス検証付き）。"""
    result = media_import_impl(paths=list(paths))
    output(result, pretty=ctx.obj.get("pretty"))


@media.group(name="folder")
def media_folder() -> None:
    """Media folder operations."""


@media_folder.command(name="list")
@click.pass_context
def folder_list_cmd(ctx: click.Context) -> None:
    """フォルダ一覧。"""
    result = folder_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@media_folder.command(name="create")
@click.argument("name")
@click.pass_context
def folder_create_cmd(ctx: click.Context, name: str) -> None:
    """フォルダ作成。"""
    result = folder_create_impl(name=name)
    output(result, pretty=ctx.obj.get("pretty"))


@media_folder.command(name="delete")
@click.argument("name")
@dry_run_option
@click.pass_context
def folder_delete_cmd(ctx: click.Context, name: str, dry_run: bool) -> None:
    """フォルダ削除。"""
    result = folder_delete_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("media.list", output_model=MediaItem)
register_schema("media.import", output_model=MediaImportOutput, input_model=MediaImportInput)
register_schema("media.folder.list", output_model=FolderInfo)
register_schema("media.folder.create", output_model=FolderCreateOutput, input_model=FolderCreateInput)
register_schema("media.folder.delete", output_model=FolderDeleteOutput, input_model=FolderDeleteInput)
```

**Step 3.5: cli.py に media コマンドを登録**

`src/davinci_cli/cli.py` の `_register_commands()` に media を追加:
```python
def _register_commands() -> None:
    from davinci_cli.commands import system, schema, project, timeline, clip, color, media
    dr.add_command(system.system)
    dr.add_command(schema.schema)
    dr.add_command(project.project)
    dr.add_command(timeline.timeline)
    dr.add_command(clip.clip)
    dr.add_command(color.color)
    dr.add_command(media.media)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_media.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/media.py src/davinci_cli/cli.py tests/unit/test_media.py
git commit -m "feat: commands/media.py — core/validation.py使用、FileNotFoundError→ValidationError、cli.py登録"
```

---

### Task 20: commands/deliver.py — dr deliver（--dry-run 推奨）

**Files:**
- Create: `src/davinci_cli/commands/deliver.py`
- Modify: `src/davinci_cli/cli.py`（deliver コマンドを `_register_commands()` に追加）
- Test: `tests/unit/test_deliver.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_deliver.py
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.deliver import (
    deliver_preset_list_impl,
    deliver_preset_load_impl,
    deliver_add_job_impl,
    deliver_list_jobs_impl,
    deliver_start_impl,
    deliver_stop_impl,
    deliver_status_impl,
)
from davinci_cli.core.exceptions import ValidationError


RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()
    project.GetRenderPresets.return_value = ["H.264 Master", "YouTube 1080p"]
    project.LoadRenderPreset.return_value = True
    project.GetRenderJobList.return_value = [
        {
            "JobId": "job-001",
            "TimelineName": "Edit",
            "JobStatus": "Queued",
            "CompletionPercentage": 0,
        }
    ]
    project.AddRenderJob.return_value = "job-002"
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestDeliverPresetImpl:
    def test_list_presets(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_preset_list_impl()
        assert len(result) == 2
        assert result[0]["name"] == "H.264 Master"

    def test_load_not_found(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().LoadRenderPreset.return_value = False
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="not found"):
                deliver_preset_load_impl(name="NonExistent")


class TestDeliverJobImpl:
    def test_add_job_dry_run(self):
        result = deliver_add_job_impl(
            job_data={"output_dir": "/tmp", "filename": "output"},
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert result["action"] == "add_job"

    def test_add_job_validation_error(self):
        with pytest.raises(Exception):  # Pydantic ValidationError
            deliver_add_job_impl(job_data={"filename": "output"})

    def test_list_jobs(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_list_jobs_impl()
        assert len(result) == 1

    def test_list_jobs_fields(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_list_jobs_impl(fields=["job_id", "status"])
        assert all(set(r.keys()) == {"job_id", "status"} for r in result)


class TestDeliverStartImpl:
    def test_start_dry_run_returns_plan(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_start_impl(dry_run=True)
        assert result["would_render"] is True
        assert isinstance(result["jobs"], list)
        assert "estimated_seconds" in result

    def test_start_dry_run_with_job_ids(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_start_impl(job_ids=["job-001"], dry_run=True)
        assert result["would_render"] is True
        assert len(result["jobs"]) == 1


class TestDeliverCLI:
    def test_deliver_start_dry_run(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["deliver", "start", "--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["would_render"] is True

    def test_deliver_add_job_json(self):
        result = CliRunner().invoke(
            dr,
            [
                "deliver",
                "add-job",
                "--json",
                '{"output_dir": "/tmp", "filename": "output"}',
                "--dry-run",
            ],
        )
        assert result.exit_code == 0

    def test_deliver_preset_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["deliver", "preset", "list"])
        assert result.exit_code == 0
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_deliver.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/commands/deliver.py
"""dr deliver — レンダリング＆デリバリーコマンド。

deliver start は --dry-run による事前確認を推奨する。
_impl 関数の dry_run デフォルトは False（他コマンドと一貫性を保つ）。
MCP 側では dry_run=True がデフォルト（破壊的操作の安全性確保）。
"""
from __future__ import annotations

import json as json_module
from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.decorators import json_input_option, fields_option, dry_run_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema


# --- Pydantic Models ---

class RenderJobInput(BaseModel):
    preset_name: str | None = None
    timeline_name: str | None = None
    output_dir: str
    filename: str

class RenderJobInfo(BaseModel):
    job_id: str
    timeline_name: str | None = None
    status: str | None = None
    progress: float | None = None

class PresetListOutput(BaseModel):
    """deliver.preset.list の戻り値。プリセット名のリスト。"""
    name: str

class PresetLoadOutput(BaseModel):
    """deliver.preset.load の戻り値。"""
    loaded: str

class PresetLoadInput(BaseModel):
    name: str

class DeliverAddJobOutput(BaseModel):
    """deliver.add-job の戻り値。"""
    job_id: str | None = None
    output_dir: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    job: dict | None = None

class DeliverStartInput(BaseModel):
    """deliver.start の入力パラメータ。"""
    job_ids: list[str] | None = None

class DeliverStartOutput(BaseModel):
    """deliver.start の戻り値。"""
    would_render: bool | None = None
    rendering_started: bool | None = None
    jobs: list[dict] | None = None
    job_count: int | None = None
    estimated_seconds: int | None = None

class DeliverStatusOutput(BaseModel):
    """deliver.status の戻り値。"""
    jobs: list[dict]

class DeliverStopOutput(BaseModel):
    """deliver.stop の戻り値。"""
    stopped: bool


# --- Helper ---

def _get_current_project() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    return project


# --- _impl Functions ---

def deliver_preset_list_impl() -> list[dict]:
    project = _get_current_project()
    presets = project.GetRenderPresets() or []
    return [{"name": p} for p in presets]


def deliver_preset_load_impl(name: str) -> dict:
    project = _get_current_project()
    success = project.LoadRenderPreset(name)
    if not success:
        raise ValidationError(field="preset", reason=f"Preset not found: {name}")
    return {"loaded": name}


def deliver_add_job_impl(job_data: dict, dry_run: bool = False) -> dict:
    validated = RenderJobInput.model_validate(job_data)
    if dry_run:
        return {"dry_run": True, "action": "add_job", "job": validated.model_dump()}
    project = _get_current_project()
    project.SetRenderSettings({
        "SelectAllFrames": True,
        "TargetDir": validated.output_dir,
        "CustomName": validated.filename,
    })
    job_id = project.AddRenderJob()
    if not job_id:
        raise ValidationError(
            field="render_job",
            reason="Failed to add render job",
        )
    return {"job_id": job_id, "output_dir": validated.output_dir}


def deliver_list_jobs_impl(fields: list[str] | None = None) -> list[dict]:
    project = _get_current_project()
    jobs = project.GetRenderJobList() or []
    result: list[dict] = []
    for job in jobs:
        info = {
            "job_id": job.get("JobId", ""),
            "timeline_name": job.get("TimelineName", ""),
            "status": job.get("JobStatus", "Queued"),
            "progress": job.get("CompletionPercentage"),
        }
        if fields:
            info = {k: v for k, v in info.items() if k in fields}
        result.append(info)
    return result


def deliver_start_impl(
    job_ids: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    jobs = deliver_list_jobs_impl()
    if job_ids:
        jobs = [j for j in jobs if j["job_id"] in job_ids]

    if dry_run:
        return {
            "would_render": True,
            "jobs": jobs,
            "estimated_seconds": len(jobs) * 60,
        }

    project = _get_current_project()
    if job_ids:
        for jid in job_ids:
            project.StartRendering(jid)
    else:
        project.StartRendering()
    return {"rendering_started": True, "job_count": len(jobs)}


def deliver_stop_impl() -> dict:
    project = _get_current_project()
    project.StopRendering()
    return {"stopped": True}


def deliver_status_impl() -> dict:
    project = _get_current_project()
    jobs = project.GetRenderJobList() or []
    statuses: list[dict] = []
    for job in jobs:
        statuses.append({
            "job_id": job.get("JobId"),
            "status": job.get("JobStatus"),
            "percent": job.get("CompletionPercentage", 0),
            "eta": (job.get("EstimatedTimeRemainingInMs", 0) or 0) // 1000,
        })
    return {"jobs": statuses}


# --- CLI Commands ---

@click.group()
def deliver() -> None:
    """Render & delivery operations."""


@deliver.group(name="preset")
def deliver_preset() -> None:
    """Render preset operations."""


@deliver_preset.command(name="list")
@click.pass_context
def preset_list(ctx: click.Context) -> None:
    """レンダープリセット一覧。"""
    result = deliver_preset_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@deliver_preset.command(name="load")
@click.argument("name")
@click.pass_context
def preset_load(ctx: click.Context, name: str) -> None:
    """プリセット読み込み。"""
    result = deliver_preset_load_impl(name=name)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="add-job")
@json_input_option
@dry_run_option
@click.pass_context
def add_job(ctx: click.Context, json_input: dict | None, dry_run: bool) -> None:
    """レンダージョブ追加。"""
    if not json_input:
        raise click.UsageError("--json is required")
    result = deliver_add_job_impl(job_data=json_input, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="list-jobs")
@fields_option
@click.pass_context
def list_jobs(ctx: click.Context, fields: list[str] | None) -> None:
    """レンダージョブ一覧。"""
    result = deliver_list_jobs_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="start")
@click.option("--job-ids", default=None, help="Comma-separated job IDs")
@dry_run_option
@click.pass_context
def start(ctx: click.Context, job_ids: str | None, dry_run: bool) -> None:
    """レンダー開始（--dry-run 推奨）。"""
    ids = job_ids.split(",") if job_ids else None
    result = deliver_start_impl(job_ids=ids, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="stop")
@click.pass_context
def stop(ctx: click.Context) -> None:
    """レンダー停止。"""
    result = deliver_stop_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """レンダー進捗確認。"""
    result = deliver_status_impl()
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("deliver.preset.list", output_model=PresetListOutput)
register_schema("deliver.preset.load", output_model=PresetLoadOutput, input_model=PresetLoadInput)
register_schema("deliver.add-job", output_model=DeliverAddJobOutput, input_model=RenderJobInput)
register_schema("deliver.list-jobs", output_model=RenderJobInfo)
register_schema("deliver.start", output_model=DeliverStartOutput, input_model=DeliverStartInput)
register_schema("deliver.stop", output_model=DeliverStopOutput)
register_schema("deliver.status", output_model=DeliverStatusOutput)
```

**Step 3.5: cli.py に deliver コマンドを登録（最終形）**

`src/davinci_cli/cli.py` の `_register_commands()` に deliver を追加:
```python
def _register_commands() -> None:
    from davinci_cli.commands import (
        system, schema, project, timeline, clip, color, media, deliver,
    )
    dr.add_command(system.system)
    dr.add_command(schema.schema)
    dr.add_command(project.project)
    dr.add_command(timeline.timeline)
    dr.add_command(clip.clip)
    dr.add_command(color.color)
    dr.add_command(media.media)
    dr.add_command(deliver.deliver)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_deliver.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/deliver.py src/davinci_cli/cli.py tests/unit/test_deliver.py
git commit -m "feat: commands/deliver.py — dry-run推奨ワークフロー、schema戻り値修正、cli.py登録"
```

---

### Task 21: mcp_server.py — FastMCP サーバー（エラーハンドリングラッパー付き、dry_run=True デフォルト）

**Files:**
- Create: `src/davinci_cli/mcp/__init__.py`
- Create: `src/davinci_cli/mcp/mcp_server.py`（ファイル名をタスク名と一致させる）
- Test: `tests/unit/test_mcp_server.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_mcp_server.py
import inspect
import pytest
from unittest.mock import patch, MagicMock

from davinci_cli.mcp.mcp_server import mcp, mcp_error_handler


class TestMCPServerSetup:
    def test_mcp_server_instantiated(self):
        assert mcp is not None
        assert mcp.name == "davinci-cli"

    def test_mcp_tools_registered(self):
        tool_names = [t.name for t in mcp.tools]
        assert "system_ping" in tool_names
        assert "project_list" in tool_names
        assert "project_open" in tool_names
        assert "deliver_start" in tool_names
        assert "color_apply_lut" in tool_names
        assert "media_list" in tool_names


class TestMCPDryRunDefaults:
    """MCP の tool 関数では dry_run=True がデフォルトであること"""

    def test_project_open_default_dry_run_true(self):
        tool = next(t for t in mcp.tools if t.name == "project_open")
        sig = inspect.signature(tool.fn)
        assert sig.parameters["dry_run"].default is True

    def test_deliver_start_default_dry_run_true(self):
        tool = next(t for t in mcp.tools if t.name == "deliver_start")
        sig = inspect.signature(tool.fn)
        assert sig.parameters["dry_run"].default is True

    def test_deliver_add_job_default_dry_run_true(self):
        tool = next(t for t in mcp.tools if t.name == "deliver_add_job")
        sig = inspect.signature(tool.fn)
        assert sig.parameters["dry_run"].default is True


class TestMCPDescriptions:
    def test_deliver_start_has_agent_rules(self):
        tool = next(t for t in mcp.tools if t.name == "deliver_start")
        assert "AGENT RULES" in tool.description
        assert "dry_run=True" in tool.description

    def test_project_list_has_fields_rule(self):
        tool = next(t for t in mcp.tools if t.name == "project_list")
        assert "fields" in tool.description
        assert "AGENT RULES" in tool.description

    def test_color_apply_lut_has_path_warning(self):
        tool = next(t for t in mcp.tools if t.name == "color_apply_lut")
        assert ".." in tool.description


class TestMCPErrorHandler:
    def test_error_handler_returns_structured_error(self):
        """例外をキャッチして構造化エラーレスポンスを返すこと"""
        from davinci_cli.core.exceptions import ResolveNotRunningError

        @mcp_error_handler
        def failing_fn():
            raise ResolveNotRunningError()

        result = failing_fn()
        assert result["error"] is True
        assert "DaVinci Resolve" in result["message"]
        assert result["error_type"] == "ResolveNotRunningError"
        assert result["exit_code"] == 1

    def test_error_handler_passes_through_on_success(self):
        @mcp_error_handler
        def success_fn():
            return {"status": "ok"}

        result = success_fn()
        assert result == {"status": "ok"}
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_mcp_server.py -v`
Expected: FAIL (ImportError)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/mcp/__init__.py
```

```python
# src/davinci_cli/mcp/mcp_server.py
"""FastMCP サーバー — davinci-cli の全 _impl 関数を MCP tool として公開する。

設計方針:
  - MCP の tool 関数では dry_run=True がデフォルト（CLI側は False）
  - 各 tool の description に AGENT RULES を埋め込む
  - mcp_error_handler で例外をキャッチし、構造化エラーレスポンスを返す
    （MCP server が未ハンドル例外でクラッシュすることを防ぐ）
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from fastmcp import FastMCP

from davinci_cli.core.exceptions import DavinciCLIError

# --- Import all _impl functions ---
from davinci_cli.commands.system import ping_impl, version_impl, edition_impl, info_impl
from davinci_cli.commands.project import (
    project_list_impl, project_open_impl, project_close_impl,
    project_create_impl, project_delete_impl, project_save_impl, project_info_impl,
)
from davinci_cli.commands.timeline import (
    timeline_list_impl, timeline_current_impl, timeline_switch_impl,
    timeline_create_impl, timeline_delete_impl, timeline_export_impl,
    marker_list_impl, marker_add_impl, marker_delete_impl,
)
from davinci_cli.commands.clip import (
    clip_list_impl, clip_info_impl, clip_select_impl,
    clip_property_get_impl, clip_property_set_impl,
)
from davinci_cli.commands.color import (
    color_apply_lut_impl, color_reset_impl,
    color_copy_grade_impl, color_paste_grade_impl,
    node_list_impl, node_add_impl, node_delete_impl,
    still_grab_impl, still_list_impl, still_apply_impl,
)
from davinci_cli.commands.media import (
    media_list_impl, media_import_impl,
    folder_list_impl, folder_create_impl, folder_delete_impl,
)
from davinci_cli.commands.deliver import (
    deliver_preset_list_impl, deliver_preset_load_impl,
    deliver_add_job_impl, deliver_list_jobs_impl,
    deliver_start_impl, deliver_stop_impl, deliver_status_impl,
)


# --- Error Handler ---

def mcp_error_handler(func: Callable) -> Callable:
    """MCP tool 用エラーハンドリングラッパー。

    DavinciCLIError をキャッチして構造化エラーレスポンスを返す。
    MCP server が未ハンドル例外でクラッシュすることを防ぐ。
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except DavinciCLIError as exc:
            return {
                "error": True,
                "message": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": exc.exit_code,
            }
        except Exception as exc:
            return {
                "error": True,
                "message": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": 99,
            }
    return wrapper


# --- MCP Server ---

mcp = FastMCP("davinci-cli")


# ---- system ----

@mcp.tool(description="""
Resolve接続確認を行う。
AGENT RULES:
- 接続確認のみ。引数不要。
""")
@mcp_error_handler
def system_ping() -> dict:
    return ping_impl()


@mcp.tool(description="""
DaVinci Resolveのバージョン情報を返す。
AGENT RULES:
- 引数不要。バージョン確認に使う。
""")
@mcp_error_handler
def system_version() -> dict:
    return version_impl()


@mcp.tool(description="""
DaVinci Resolveのエディション（Free/Studio）を返す。
AGENT RULES:
- 引数不要。
""")
@mcp_error_handler
def system_edition() -> dict:
    return edition_impl()


@mcp.tool(description="""
総合情報（バージョン+エディション+現在プロジェクト）を返す。
AGENT RULES:
- 引数不要。
""")
@mcp_error_handler
def system_info() -> dict:
    return info_impl()


# ---- project ----

@mcp.tool(description="""
プロジェクト一覧を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること（例: fields="name,id"）
- 全フィールド取得はコンテキストウィンドウを消費する
""")
@mcp_error_handler
def project_list(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return project_list_impl(fields=field_list)


@mcp.tool(description="""
プロジェクトを開く。
AGENT RULES:
- 必ずdry_run=Trueで事前確認し、ユーザーに結果を提示してから実行すること
- dry_run=Falseは現在のプロジェクトを閉じる副作用がある
""")
@mcp_error_handler
def project_open(name: str, dry_run: bool = True) -> dict:
    return project_open_impl(name=name, dry_run=dry_run)


@mcp.tool(description="""
現在のプロジェクトを閉じる。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
- 未保存の変更は失われる
""")
@mcp_error_handler
def project_close(dry_run: bool = True) -> dict:
    return project_close_impl(dry_run=dry_run)


@mcp.tool(description="""
新規プロジェクトを作成する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
""")
@mcp_error_handler
def project_create(name: str, dry_run: bool = True) -> dict:
    return project_create_impl(name=name, dry_run=dry_run)


@mcp.tool(description="""
プロジェクトを削除する（破壊的操作）。
AGENT RULES:
- 必ずdry_run=Trueで事前確認し、ユーザーの明示的な承認を得てから実行
- 削除したプロジェクトは復元できない
""")
@mcp_error_handler
def project_delete(name: str, dry_run: bool = True) -> dict:
    return project_delete_impl(name=name, dry_run=dry_run)


@mcp.tool(description="""
プロジェクトを保存する。
AGENT RULES:
- 引数不要。
""")
@mcp_error_handler
def project_save() -> dict:
    return project_save_impl()


@mcp.tool(description="""
現在のプロジェクト情報を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること
""")
@mcp_error_handler
def project_info(fields: str | None = None) -> dict:
    field_list = fields.split(",") if fields else None
    return project_info_impl(fields=field_list)


# ---- timeline ----

@mcp.tool(description="""
タイムライン一覧を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること
""")
@mcp_error_handler
def timeline_list(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return timeline_list_impl(fields=field_list)


@mcp.tool(description="""
現在のタイムライン情報を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること
""")
@mcp_error_handler
def timeline_current(fields: str | None = None) -> dict:
    field_list = fields.split(",") if fields else None
    return timeline_current_impl(fields=field_list)


@mcp.tool(description="""
タイムラインを切り替える。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
""")
@mcp_error_handler
def timeline_switch(name: str, dry_run: bool = True) -> dict:
    return timeline_switch_impl(name=name, dry_run=dry_run)


@mcp.tool(description="""
新規タイムラインを作成する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
""")
@mcp_error_handler
def timeline_create(name: str, dry_run: bool = True) -> dict:
    return timeline_create_impl(name=name, dry_run=dry_run)


@mcp.tool(description="""
タイムラインを削除する（破壊的操作）。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
""")
@mcp_error_handler
def timeline_delete(name: str, dry_run: bool = True) -> dict:
    return timeline_delete_impl(name=name, dry_run=dry_run)


# ---- clip ----

@mcp.tool(description="""
クリップ一覧を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること（例: fields="index,name"）
""")
@mcp_error_handler
def clip_list(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return clip_list_impl(fields=field_list)


@mcp.tool(description="""
クリップ詳細を返す。
AGENT RULES:
- index はclip listで確認した値を使うこと
""")
@mcp_error_handler
def clip_info(index: int) -> dict:
    return clip_info_impl(index=index)


@mcp.tool(description="""
クリップのプロパティを設定する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
""")
@mcp_error_handler
def clip_property_set(index: int, key: str, value: str, dry_run: bool = True) -> dict:
    return clip_property_set_impl(index=index, key=key, value=value, dry_run=dry_run)


# ---- color ----

@mcp.tool(description="""
クリップにLUTを適用する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
- lut_pathはシステム上の絶対パス（".."を含むパスは拒絶される）
- 許可拡張子: .cube, .3dl, .lut, .mga, .m3d
""")
@mcp_error_handler
def color_apply_lut(clip_index: int, lut_path: str, dry_run: bool = True) -> dict:
    return color_apply_lut_impl(clip_index=clip_index, lut_path=lut_path, dry_run=dry_run)


@mcp.tool(description="""
グレードをリセットする。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
""")
@mcp_error_handler
def color_reset(clip_index: int, dry_run: bool = True) -> dict:
    return color_reset_impl(clip_index=clip_index, dry_run=dry_run)


# ---- media ----

@mcp.tool(description="""
メディアプールのクリップ一覧を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること（例: fields="clip_name,file_path"）
- folder引数でフォルダを絞り込むこと
""")
@mcp_error_handler
def media_list(folder: str | None = None, fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return media_list_impl(folder_name=folder, fields=field_list)


@mcp.tool(description="""
メディアをインポートする。
AGENT RULES:
- pathsには絶対パスのリストを渡すこと
- ".."を含むパスはセキュリティ上の理由で拒絶される
""")
@mcp_error_handler
def media_import(paths: list[str]) -> dict:
    return media_import_impl(paths=paths)


# ---- deliver（特別警告） ----

@mcp.tool(description="""
レンダープリセット一覧を返す。
AGENT RULES:
- 引数不要。
""")
@mcp_error_handler
def deliver_preset_list() -> list[dict]:
    return deliver_preset_list_impl()


@mcp.tool(description="""
レンダープリセットを読み込む。
AGENT RULES:
- preset listで確認した名前を使うこと
""")
@mcp_error_handler
def deliver_preset_load(name: str) -> dict:
    return deliver_preset_load_impl(name=name)


@mcp.tool(description="""
レンダージョブを追加する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
- job_dataはdict: {"output_dir": "...", "filename": "..."}
""")
@mcp_error_handler
def deliver_add_job(job_data: dict, dry_run: bool = True) -> dict:
    return deliver_add_job_impl(job_data=job_data, dry_run=dry_run)


@mcp.tool(description="""
レンダーキューのジョブ一覧を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること（例: fields="job_id,status,percent"）
""")
@mcp_error_handler
def deliver_list_jobs(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return deliver_list_jobs_impl(fields=field_list)


@mcp.tool(description="""
レンダーを開始する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること（"would_render": true と jobs一覧が返る）
- ユーザーに確認結果を提示し、明示的な承認を得てからdry_run=Falseで実行すること
- この操作はDaVinci Resolveのエンコードリソースを大量消費する
""")
@mcp_error_handler
def deliver_start(job_ids: list[str] | None = None, dry_run: bool = True) -> dict:
    return deliver_start_impl(job_ids=job_ids, dry_run=dry_run)


@mcp.tool(description="""
レンダーを停止する。
AGENT RULES:
- 実行中のレンダーを即座に停止する
- 途中のファイルは不完全な状態で残る
""")
@mcp_error_handler
def deliver_stop() -> dict:
    return deliver_stop_impl()


@mcp.tool(description="""
レンダー進捗を返す（percent, status, eta）。
AGENT RULES:
- 引数不要。ポーリング間隔は最低5秒空けること。
""")
@mcp_error_handler
def deliver_status() -> dict:
    return deliver_status_impl()


if __name__ == "__main__":
    mcp.run()
```

エントリーポイント設定（`pyproject.toml` に追加）:
```toml
[project.scripts]
dr = "davinci_cli.cli:dr"
dr-mcp = "davinci_cli.mcp.mcp_server:mcp.run"
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_mcp_server.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add src/davinci_cli/mcp/ tests/unit/test_mcp_server.py pyproject.toml
git commit -m "feat: mcp_server.py — エラーハンドリングラッパー追加、dry_run=Trueデフォルト、ファイル名統一"
```

---

### Task 22: SKILL.md — Claude Code 用スキルファイル

**Files:**
- Create: `SKILL.md`（プロジェクトルート）
- Test: `tests/unit/test_skill_md.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_skill_md.py
from pathlib import Path


SKILL_MD = Path("SKILL.md")


def test_skill_md_exists():
    assert SKILL_MD.exists(), "SKILL.md must exist in project root"


def test_skill_md_has_frontmatter():
    content = SKILL_MD.read_text()
    assert content.startswith("---"), "Must have YAML frontmatter"
    assert "name: davinci-cli" in content
    assert "version: 1.0.0" in content


def test_skill_md_has_agent_rules():
    content = SKILL_MD.read_text()
    assert "AGENT RULES" in content
    assert "--dry-run" in content


def test_skill_md_has_all_command_groups():
    content = SKILL_MD.read_text()
    for group in [
        "dr system",
        "dr schema",
        "dr project",
        "dr timeline",
        "dr clip",
        "dr color",
        "dr media",
        "dr deliver",
    ]:
        assert group in content, f"Missing command group: {group}"


def test_skill_md_has_usage_patterns():
    content = SKILL_MD.read_text()
    assert "パターン" in content or "Pattern" in content


def test_skill_md_deliver_has_mandatory_dry_run():
    content = SKILL_MD.read_text()
    deliver_section_start = content.find("dr deliver")
    assert deliver_section_start != -1
    deliver_section = content[deliver_section_start:]
    assert "必須" in deliver_section or "required" in deliver_section.lower()
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_skill_md.py -v`
Expected: FAIL (SKILL.md が存在しない)

**Step 3: 最小限の実装**

SKILL.md の内容は旧計画 (Task 19) の SKILL.md と同一。変更なし。

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_skill_md.py -v`
Expected: PASS

**Step 5: コミット**

```bash
git add SKILL.md tests/unit/test_skill_md.py
git commit -m "docs: SKILL.md — Claude Code用スキルファイル、dry-run必須ルール明記"
```

---

### Task 23: E2E テスト — MockResolve で全グループ疎通確認（パッチパス修正済み）

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/mock_resolve.py`
- Create: `tests/e2e/test_smoke.py`

**Step 1: 失敗するテストを書く**

```python
# tests/e2e/mock_resolve.py
from unittest.mock import MagicMock


def build_mock_resolve():
    """E2Eテスト用の完全なResolveモック。"""
    resolve = MagicMock()
    resolve.GetVersionString.return_value = "19.0.0"
    resolve.GetVersion.return_value = {
        "product": "DaVinci Resolve Studio",
        "major": 19,
        "minor": 0,
    }

    pm = MagicMock()
    resolve.GetProjectManager.return_value = pm

    project = MagicMock()
    pm.GetCurrentProject.return_value = project
    pm.GetProjectListInCurrentFolder.return_value = ["Demo Project", "Test Project"]
    pm.LoadProject.return_value = project
    project.GetName.return_value = "Demo Project"
    project.GetTimelineCount.return_value = 2
    project.GetSetting.return_value = "24"
    project.GetRenderPresets.return_value = ["H.264 Master", "YouTube 1080p"]
    project.LoadRenderPreset.return_value = True
    project.GetRenderJobList.return_value = [
        {
            "JobId": "job-001",
            "TimelineName": "Edit",
            "JobStatus": "Queued",
            "CompletionPercentage": 0,
        }
    ]
    project.AddRenderJob.return_value = "job-002"
    project.SaveProject.return_value = True

    timeline = MagicMock()
    project.GetCurrentTimeline.return_value = timeline
    project.GetTimelineByIndex.return_value = timeline
    timeline.GetName.return_value = "Main Edit"
    timeline.GetSetting.return_value = "24"
    timeline.GetStartTimecode.return_value = "00:00:00:00"
    timeline.GetTrackCount.return_value = 1
    timeline.GetMarkers.return_value = {}

    clip = MagicMock()
    clip.GetName.return_value = "A001_C001.mov"
    clip.GetStart.return_value = 0
    clip.GetEnd.return_value = 240
    clip.GetDuration.return_value = 240
    clip.GetProperty.return_value = "0.0"
    clip.GetNodeCount.return_value = 3
    clip.GetClipProperty.side_effect = lambda k: {
        "File Path": "/media/clip1.mov",
        "Duration": "00:00:10:00",
        "FPS": "24.0",
    }.get(k, "")
    timeline.GetItemListInTrack.return_value = [clip]

    media_pool = MagicMock()
    project.GetMediaPool.return_value = media_pool
    root_folder = MagicMock()
    root_folder.GetClipList.return_value = [clip]
    root_folder.GetSubFolderList.return_value = []
    media_pool.GetRootFolder.return_value = root_folder
    media_pool.ImportMedia.return_value = [clip]

    gallery = MagicMock()
    project.GetGallery.return_value = gallery
    album = MagicMock()
    gallery.GetCurrentStillAlbum.return_value = album
    album.GetStills.return_value = []

    return resolve
```

```python
# tests/e2e/test_smoke.py
"""E2E スモークテスト — MockResolve で全コマンドグループの疎通確認。

パッチパスは davinci_cli.core.connection.get_resolve を使用する。
resolve_bridge は使わない。
"""
import json
import pytest
from click.testing import CliRunner
from unittest.mock import patch

from davinci_cli.cli import dr
from tests.e2e.mock_resolve import build_mock_resolve

# パッチパス: core.connection を使用（resolve_bridge ではない）
RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = build_mock_resolve()
    with patch(RESOLVE_PATCH, return_value=resolve):
        yield resolve


@pytest.fixture
def runner():
    return CliRunner()


class TestSystemSmoke:
    def test_ping(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "ping"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_version(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "version"])
        assert result.exit_code == 0

    def test_info(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "info"])
        assert result.exit_code == 0


class TestProjectSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["project", "list", "--fields", "name"])
        assert result.exit_code == 0

    def test_open_dry_run(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["project", "open", "Demo Project", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_info(self, runner, mock_resolve):
        result = runner.invoke(dr, ["project", "info", "--fields", "name"])
        assert result.exit_code == 0


class TestTimelineSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["timeline", "list", "--fields", "name"])
        assert result.exit_code == 0

    def test_current(self, runner, mock_resolve):
        result = runner.invoke(dr, ["timeline", "current"])
        assert result.exit_code == 0

    def test_switch_dry_run(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["timeline", "switch", "Main Edit", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestClipSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["clip", "list", "--fields", "index,name"])
        assert result.exit_code == 0

    def test_property_set_dry_run(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["clip", "property", "set", "0", "Pan", "0.5", "--dry-run"]
        )
        assert result.exit_code == 0


class TestColorSmoke:
    def test_apply_lut_dry_run(self, runner, mock_resolve, tmp_path):
        lut_file = tmp_path / "test.cube"
        lut_file.touch()
        result = runner.invoke(
            dr, ["color", "apply-lut", "0", str(lut_file), "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_reset_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["color", "reset", "0", "--dry-run"])
        assert result.exit_code == 0


class TestMediaSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["media", "list", "--fields", "clip_name"]
        )
        assert result.exit_code == 0

    def test_folder_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["media", "folder", "list"])
        assert result.exit_code == 0

    def test_folder_delete_dry_run(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["media", "folder", "delete", "OldFolder", "--dry-run"]
        )
        assert result.exit_code == 0


class TestDeliverSmoke:
    def test_preset_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "preset", "list"])
        assert result.exit_code == 0

    def test_list_jobs(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["deliver", "list-jobs", "--fields", "job_id,status"]
        )
        assert result.exit_code == 0

    def test_start_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "start", "--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["would_render"] is True
        assert "jobs" in data
        assert "estimated_seconds" in data

    def test_status(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "status"])
        assert result.exit_code == 0


class TestSchemaSmoke:
    def test_schema_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["schema", "list"])
        assert result.exit_code == 0

    def test_schema_show_project_open(self, runner, mock_resolve):
        result = runner.invoke(dr, ["schema", "show", "project.open"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "input_schema" in data


class TestMCPSmoke:
    def test_mcp_server_importable(self):
        from davinci_cli.mcp.mcp_server import mcp
        assert mcp is not None

    def test_mcp_has_deliver_start_tool(self):
        from davinci_cli.mcp.mcp_server import mcp
        tool_names = [t.name for t in mcp.tools]
        assert "deliver_start" in tool_names
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/e2e/test_smoke.py -v`
Expected: FAIL（E2E モックファイルが存在しない）

**Step 3: 最小限の実装**

上記のテストコードとモックがそのまま実装。全 Phase 1〜3 の実装が完了していれば PASS する。

**Step 4: 通過を確認**

Run:
```bash
python -m pytest tests/e2e/test_smoke.py -v
python -m pytest tests/ -v --tb=short
```
Expected: 全テスト PASS

**Step 5: コミット**

```bash
git add tests/e2e/
git commit -m "test: E2E スモークテスト — パッチパス core.connection.get_resolve に統一"
```

---

## Phase 3 完了確認

```bash
# 全テスト
python -m pytest tests/ -v --tb=short

# カバレッジ
python -m pytest tests/ --cov=davinci_cli --cov-report=term-missing --cov-fail-under=80

# Lint + Type check
ruff check src/ tests/
mypy src/davinci_cli/

# CLI 動作確認
dr --help
dr schema list
dr deliver start --dry-run

# MCP サーバー起動確認
dr-mcp --help
```

### ディレクトリ構造（Phase 3 完了時の追加分）

```
src/davinci_cli/
├── commands/
│   ├── color.py              # Task 18: core/validation.py使用
│   ├── media.py              # Task 19: パス検証付きインポート
│   └── deliver.py            # Task 20: dry-run推奨ワークフロー
└── mcp/
    ├── __init__.py
    └── mcp_server.py         # Task 21: エラーハンドリングラッパー、dry_run=True

SKILL.md                      # Task 22: Claude Code用スキルファイル

tests/
├── unit/
│   ├── test_color.py
│   ├── test_media.py
│   ├── test_deliver.py
│   ├── test_mcp_server.py
│   └── test_skill_md.py
└── e2e/
    ├── __init__.py
    ├── mock_resolve.py       # パッチパス: core.connection.get_resolve
    └── test_smoke.py
```

### 最終ファイル構造（全 Phase 完了時）

```
davinci-cli/
├── .github/workflows/ci.yml
├── pyproject.toml
├── SKILL.md
├── src/davinci_cli/
│   ├── __init__.py
│   ├── cli.py
│   ├── decorators.py
│   ├── schema_registry.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exceptions.py
│   │   ├── validation.py      # security.py は存在しない
│   │   ├── environment.py
│   │   ├── connection.py
│   │   ├── edition.py
│   │   └── logging.py
│   ├── output/
│   │   ├── __init__.py
│   │   └── formatter.py
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── system.py
│   │   ├── schema.py
│   │   ├── project.py
│   │   ├── timeline.py
│   │   ├── clip.py
│   │   ├── color.py
│   │   ├── media.py
│   │   └── deliver.py
│   └── mcp/
│       ├── __init__.py
│       └── mcp_server.py
└── tests/
    ├── __init__.py
    ├── mocks/
    │   ├── __init__.py
    │   └── resolve_mock.py
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
    │   ├── test_ci_config.py
    │   ├── test_decorators.py
    │   ├── test_cli.py
    │   ├── test_system.py
    │   ├── test_schema.py
    │   ├── test_project.py
    │   ├── test_timeline.py
    │   ├── test_clip.py
    │   ├── test_color.py
    │   ├── test_media.py
    │   ├── test_deliver.py
    │   ├── test_mcp_server.py
    │   └── test_skill_md.py
    └── e2e/
        ├── __init__.py
        ├── mock_resolve.py
        └── test_smoke.py
```
