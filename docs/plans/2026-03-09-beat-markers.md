# Beat Markers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** BPM と音価を指定してタイムライン全体に等間隔マーカーを自動配置する `dr timeline marker beats` コマンドを実装する
**Architecture:** `commands/beat_markers.py` に純粋関数 `_calculate_beat_frames()` + `beat_marker_impl()` + Click コマンドを配置し、`timeline.py` の `timeline_marker` グループに `add_command()` で登録。MCP ツールとスキーマレジストリも追加。
**Tech Stack:** Python 3.10+, Click, Pydantic v2, FastMCP, pytest

---

### Task 1: `_calculate_beat_frames()` 純粋関数

**Files:**
- Create: `src/davinci_cli/commands/beat_markers.py`
- Test: `tests/unit/test_beat_markers.py`

**Step 1: 失敗するテストを書く**

```python
# tests/unit/test_beat_markers.py
"""Beat markers — _calculate_beat_frames() 純粋関数テスト。"""

from davinci_cli.commands.beat_markers import _calculate_beat_frames


class TestCalculateBeatFrames:
    def test_quarter_note_120bpm_24fps(self):
        """BPM 120, 4分音符, 24fps → 12フレーム間隔"""
        frames = _calculate_beat_frames(
            bpm=120, note_value="1/4", fps=24.0,
            start_frame=86400, end_frame=86400 + 240,
        )
        assert frames[0] == 86400
        assert frames[1] == 86412
        assert frames[2] == 86424
        assert len(frames) == 21  # 0〜240, 12刻み

    def test_eighth_note_100bpm_24fps_rounding(self):
        """BPM 100, 8分音符, 24fps → 7.2フレーム間隔（丸め確認）"""
        frames = _calculate_beat_frames(
            bpm=100, note_value="1/8", fps=24.0,
            start_frame=0, end_frame=100,
        )
        assert frames[0] == 0
        assert frames[1] == 7
        assert frames[2] == 14
        assert frames[3] == 22  # round(3 * 7.2) = round(21.6) = 22

    def test_whole_note_60bpm_30fps(self):
        """BPM 60, 全音符, 30fps → 120フレーム間隔"""
        frames = _calculate_beat_frames(
            bpm=60, note_value="1/1", fps=30.0,
            start_frame=0, end_frame=360,
        )
        assert frames == [0, 120, 240, 360]

    def test_start_frame_equals_end_frame(self):
        """開始と終了が同じ → 1個だけ返る"""
        frames = _calculate_beat_frames(
            bpm=120, note_value="1/4", fps=24.0,
            start_frame=100, end_frame=100,
        )
        assert frames == [100]

    def test_very_short_timeline(self):
        """1フレームのタイムライン"""
        frames = _calculate_beat_frames(
            bpm=120, note_value="1/4", fps=24.0,
            start_frame=86400, end_frame=86401,
        )
        assert frames == [86400]

    def test_sixteenth_note_high_bpm(self):
        """BPM 200, 16分音符, 24fps → 1.8フレーム間隔"""
        frames = _calculate_beat_frames(
            bpm=200, note_value="1/16", fps=24.0,
            start_frame=0, end_frame=20,
        )
        assert frames[0] == 0
        assert frames[1] == 2   # round(1.8)
        assert frames[2] == 4   # round(3.6)
        assert frames[3] == 5   # round(5.4)

    def test_no_cumulative_error(self):
        """100ビート後の累積誤差がないことを確認"""
        frames = _calculate_beat_frames(
            bpm=100, note_value="1/8", fps=24.0,
            start_frame=0, end_frame=10000,
        )
        # 100番目のビート: round(100 * 7.2) = 720
        assert frames[100] == 720

    def test_half_note_90bpm_24fps(self):
        """BPM 90, 2分音符, 24fps → 32フレーム間隔"""
        frames = _calculate_beat_frames(
            bpm=90, note_value="1/2", fps=24.0,
            start_frame=0, end_frame=96,
        )
        # seconds_per_beat = (60/90) * 2.0 = 1.333...
        # frames_per_beat = 1.333... * 24 = 32.0
        assert frames == [0, 32, 64, 96]
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py -v`
Expected: FAIL (ImportError — モジュールが存在しない)

**Step 3: 最小限の実装**

```python
# src/davinci_cli/commands/beat_markers.py
"""dr timeline marker beats — BPMベースのマーカー自動配置。

BPM と音価を指定してタイムライン全体に等間隔マーカーを配置する。
"""

from __future__ import annotations

# 音価 → 1拍あたりの倍率マッピング
NOTE_VALUE_MAP: dict[str, float] = {
    "1/1": 4.0,    # 全音符 = 4拍
    "1/2": 2.0,    # 2分音符 = 2拍
    "1/4": 1.0,    # 4分音符 = 1拍
    "1/8": 0.5,    # 8分音符 = 0.5拍
    "1/16": 0.25,  # 16分音符 = 0.25拍
}


def _calculate_beat_frames(
    bpm: float,
    note_value: str,
    fps: float,
    start_frame: int,
    end_frame: int,
) -> list[int]:
    """BPM・音価・FPSからマーカーを打つべきフレーム一覧を計算する。

    誤差蓄積防止: 各フレームは start_frame + round(i * interval) で計算。
    累積加算（frame += interval）は使わない。
    """
    beats_per_note = NOTE_VALUE_MAP[note_value]
    # 1音価あたりの秒数
    seconds_per_beat = (60.0 / bpm) * beats_per_note
    # 1音価あたりのフレーム数（浮動小数点）
    frames_per_beat = seconds_per_beat * fps

    frames: list[int] = []
    i = 0
    while True:
        frame = start_frame + round(i * frames_per_beat)
        if frame > end_frame:
            break
        frames.append(frame)
        i += 1
    return frames
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestCalculateBeatFrames -v`
Expected: PASS (8 tests)

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/beat_markers.py tests/unit/test_beat_markers.py
git commit -m "feat: add _calculate_beat_frames() pure function (BPM→frame list calculation)"
```

---

### Task 2: Pydantic モデル + `beat_marker_impl()` dry-run パス

**Files:**
- Modify: `src/davinci_cli/commands/beat_markers.py`
- Modify: `tests/unit/test_beat_markers.py`

**Step 1: 失敗するテストを書く**

以下を `tests/unit/test_beat_markers.py` に追加:

```python
from unittest.mock import MagicMock, patch

from davinci_cli.commands.beat_markers import beat_marker_impl

RESOLVE_PATCH = "davinci_cli.commands.beat_markers.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()

    timeline = MagicMock()
    timeline.GetName.return_value = "Main Edit"
    timeline.GetSetting.side_effect = lambda k: {
        "timelineFrameRate": "24",
    }.get(k, "")
    timeline.GetStartTimecode.return_value = "01:00:00:00"
    timeline.GetEndFrame.return_value = 240  # 相対フレーム

    project.GetCurrentTimeline.return_value = timeline
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestBeatMarkerImplDryRun:
    def test_dry_run_returns_preview(self, mock_resolve):
        """dry-run でフレーム一覧が返る"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=120, note_value="1/4", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "marker_beats"
        assert result["bpm"] == 120
        assert result["note_value"] == "1/4"
        assert result["color"] == "Blue"
        assert isinstance(result["frames"], list)
        assert result["count"] == len(result["frames"])

    def test_dry_run_frame_values(self, mock_resolve):
        """dry-run のフレーム値が正しい（開始TC=01:00:00:00, offset=86400）"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=120, note_value="1/4", dry_run=True)
        # offset=86400, end_frame_abs=86400+240=86640
        # 12フレーム間隔: 86400, 86412, ..., 86640
        assert result["frames"][0] == 86400
        assert result["frames"][1] == 86412
        assert result["count"] == 21
```

ファイル冒頭に `import pytest` を追加。

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerImplDryRun -v`
Expected: FAIL (ImportError — `beat_marker_impl` が存在しない)

**Step 3: 最小限の実装**

以下を `src/davinci_cli/commands/beat_markers.py` に追加:

```python
from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError


# --- Pydantic Models ---


class BeatMarkerInput(BaseModel):
    bpm: float
    note_value: str = "1/4"
    color: str = "Blue"
    name: str = ""
    duration: int = 1


class BeatMarkerOutput(BaseModel):
    added_count: int | None = None
    bpm: float | None = None
    note_value: str | None = None
    color: str | None = None
    frames: list[int] | None = None
    dry_run: bool | None = None
    action: str | None = None
    count: int | None = None


# --- Helper ---


def _get_current_project() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise ProjectNotOpenError()
    return project


def _get_start_frame_offset(tl: Any) -> int:
    """タイムラインの開始タイムコードをフレーム数に変換して返す。"""
    tc = tl.GetStartTimecode() or "00:00:00:00"
    parts = tc.replace(";", ":").split(":")
    if len(parts) != 4:
        return 0
    h, m, s, f = (int(p) for p in parts)
    fps_str = tl.GetSetting("timelineFrameRate") or "24"
    fps = int(float(fps_str))
    return h * 3600 * fps + m * 60 * fps + s * fps + f


# --- _impl Function ---


def beat_marker_impl(
    bpm: float,
    note_value: str = "1/4",
    color: str = "Blue",
    name: str = "",
    duration: int = 1,
    dry_run: bool = False,
) -> dict:
    """BPM と音価を指定してタイムライン全体にマーカーを配置する。"""
    # 1. バリデーション
    if note_value not in NOTE_VALUE_MAP:
        raise ValidationError(
            field="note_value",
            reason=f"Invalid note_value: '{note_value}'. Must be one of: {', '.join(NOTE_VALUE_MAP)}",
        )
    if not (20.0 <= bpm <= 300.0):
        raise ValidationError(
            field="bpm",
            reason=f"BPM must be between 20.0 and 300.0, got {bpm}",
        )

    # 2. タイムライン情報取得
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    fps = float(tl.GetSetting("timelineFrameRate") or "24")
    offset = _get_start_frame_offset(tl)
    end_frame_rel = tl.GetEndFrame()
    end_frame_abs = end_frame_rel + offset

    # 3. フレーム計算
    frames = _calculate_beat_frames(bpm, note_value, fps, offset, end_frame_abs)

    # 4. dry-run
    if dry_run:
        return {
            "dry_run": True,
            "action": "marker_beats",
            "bpm": bpm,
            "note_value": note_value,
            "color": color,
            "count": len(frames),
            "frames": frames,
        }

    # 5. マーカー追加
    for frame_abs in frames:
        rel_frame = frame_abs - offset
        tl.AddMarker(rel_frame, color, name, "", duration)

    return {
        "added_count": len(frames),
        "bpm": bpm,
        "note_value": note_value,
        "color": color,
        "frames": frames,
    }
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerImplDryRun -v`
Expected: PASS (2 tests)

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/beat_markers.py tests/unit/test_beat_markers.py
git commit -m "feat: add beat_marker_impl() with Pydantic models and dry-run support"
```

---

### Task 3: `beat_marker_impl()` 実行パス（マーカー追加）

**Files:**
- Modify: `tests/unit/test_beat_markers.py`

**Step 1: 失敗するテストを書く**

以下を `tests/unit/test_beat_markers.py` に追加:

```python
class TestBeatMarkerImplExecute:
    def test_adds_markers_to_timeline(self, mock_resolve):
        """マーカーが実際に追加される"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=120, note_value="1/4")
        assert result["added_count"] == 21
        assert result["bpm"] == 120
        assert result["note_value"] == "1/4"
        assert result["color"] == "Blue"
        assert len(result["frames"]) == 21
        # AddMarker が 21 回呼ばれることを確認
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        assert timeline.AddMarker.call_count == 21

    def test_adds_markers_with_relative_frames(self, mock_resolve):
        """AddMarker は相対フレームで呼ばれる"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            beat_marker_impl(bpm=120, note_value="1/4")
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        # 最初の呼び出し: 相対フレーム = 86400 - 86400 = 0
        first_call = timeline.AddMarker.call_args_list[0]
        assert first_call[0][0] == 0  # rel_frame
        assert first_call[0][1] == "Blue"  # color
        # 2番目の呼び出し: 相対フレーム = 86412 - 86400 = 12
        second_call = timeline.AddMarker.call_args_list[1]
        assert second_call[0][0] == 12

    def test_custom_color_and_name(self, mock_resolve):
        """カスタム色・名前が AddMarker に渡る"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(
                bpm=120, note_value="1/4", color="Red", name="Beat"
            )
        assert result["color"] == "Red"
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        first_call = timeline.AddMarker.call_args_list[0]
        assert first_call[0][1] == "Red"
        assert first_call[0][2] == "Beat"

    def test_custom_duration(self, mock_resolve):
        """カスタム duration が AddMarker に渡る"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            beat_marker_impl(bpm=120, note_value="1/4", duration=5)
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        first_call = timeline.AddMarker.call_args_list[0]
        assert first_call[0][4] == 5  # duration
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerImplExecute -v`
Expected: PASS (Task 2 の実装で既に実行パスが実装済み)

> Note: 実行パスは Task 2 で既に実装されているため、テストが即座に通る可能性がある。その場合はそのままコミットに進む。

**Step 3: 通過を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerImplExecute -v`
Expected: PASS (4 tests)

**Step 4: コミット**

```bash
git add tests/unit/test_beat_markers.py
git commit -m "test: add execution path tests for beat_marker_impl()"
```

---

### Task 4: バリデーション（不正な音価、BPM 範囲外、タイムラインなし）

**Files:**
- Modify: `tests/unit/test_beat_markers.py`

**Step 1: 失敗するテストを書く**

以下を `tests/unit/test_beat_markers.py` に追加:

```python
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError


class TestBeatMarkerImplValidation:
    def test_invalid_note_value_raises(self, mock_resolve):
        """不正な音価で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="note_value"):
                beat_marker_impl(bpm=120, note_value="1/3")

    def test_bpm_too_low_raises(self, mock_resolve):
        """BPM が下限未満で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="bpm"):
                beat_marker_impl(bpm=10)

    def test_bpm_too_high_raises(self, mock_resolve):
        """BPM が上限超で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="bpm"):
                beat_marker_impl(bpm=400)

    def test_bpm_zero_raises(self, mock_resolve):
        """BPM 0 で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="bpm"):
                beat_marker_impl(bpm=0)

    def test_bpm_boundary_low_valid(self, mock_resolve):
        """BPM 20.0（下限）は有効"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=20.0, dry_run=True)
        assert result["bpm"] == 20.0

    def test_bpm_boundary_high_valid(self, mock_resolve):
        """BPM 300.0（上限）は有効"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=300.0, dry_run=True)
        assert result["bpm"] == 300.0

    def test_no_timeline_raises(self):
        """タイムラインなしで ProjectNotOpenError"""
        resolve = MagicMock()
        pm = MagicMock()
        project = MagicMock()
        project.GetCurrentTimeline.return_value = None
        pm.GetCurrentProject.return_value = project
        resolve.GetProjectManager.return_value = pm
        with patch(RESOLVE_PATCH, return_value=resolve):
            with pytest.raises(ProjectNotOpenError):
                beat_marker_impl(bpm=120)

    def test_no_project_raises(self):
        """プロジェクトなしで ProjectNotOpenError"""
        resolve = MagicMock()
        pm = MagicMock()
        pm.GetCurrentProject.return_value = None
        resolve.GetProjectManager.return_value = pm
        with patch(RESOLVE_PATCH, return_value=resolve):
            with pytest.raises(ProjectNotOpenError):
                beat_marker_impl(bpm=120)
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerImplValidation -v`
Expected: PASS (Task 2 の実装でバリデーションは既に実装済み)

> Note: バリデーションは Task 2 で既に実装されているため、テストが即座に通る可能性がある。

**Step 3: 通過を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerImplValidation -v`
Expected: PASS (8 tests)

**Step 4: コミット**

```bash
git add tests/unit/test_beat_markers.py
git commit -m "test: add validation tests for beat_marker_impl() (BPM range, note_value, no timeline)"
```

---

### Task 5: Click CLI コマンド + `timeline_marker` グループへの登録

**Files:**
- Modify: `src/davinci_cli/commands/beat_markers.py`
- Modify: `src/davinci_cli/commands/timeline.py`
- Modify: `tests/unit/test_beat_markers.py`

**Step 1: 失敗するテストを書く**

以下を `tests/unit/test_beat_markers.py` に追加:

```python
import json

from click.testing import CliRunner

from davinci_cli.cli import dr


class TestBeatMarkerCLI:
    def test_beats_dry_run_json_input(self):
        """dr timeline marker beats --json '{"bpm": 120}' --dry-run"""
        result = CliRunner().invoke(
            dr,
            [
                "timeline", "marker", "beats",
                "--json", '{"bpm": 120}',
                "--dry-run",
            ],
        )
        # dry-run のバリデーションは通るが、Resolve 接続でエラーになる可能性がある
        # ただし mock_resolve を使うテストは別に用意する
        assert result.exit_code == 0 or "not running" in result.output.lower()

    def test_beats_dry_run_with_mock(self, mock_resolve):
        """mock付きで dry-run が正しく動作"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(
                dr,
                [
                    "timeline", "marker", "beats",
                    "--json", '{"bpm": 120, "note_value": "1/8"}',
                    "--dry-run",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["bpm"] == 120
        assert data["note_value"] == "1/8"

    def test_beats_requires_json(self):
        """--json なしでエラー"""
        result = CliRunner().invoke(
            dr, ["timeline", "marker", "beats"]
        )
        assert result.exit_code != 0

    def test_beats_custom_options(self, mock_resolve):
        """カスタムオプション付き dry-run"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(
                dr,
                [
                    "timeline", "marker", "beats",
                    "--json", '{"bpm": 90, "note_value": "1/2", "color": "Red", "name": "Beat"}',
                    "--dry-run",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["color"] == "Red"
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerCLI -v`
Expected: FAIL (Click コマンドが未登録)

**Step 3: 最小限の実装**

`src/davinci_cli/commands/beat_markers.py` に以下を追加:

```python
from davinci_cli.decorators import dry_run_option, json_input_option
from davinci_cli.output.formatter import output


# --- CLI Command ---


@click.command(name="beats")
@json_input_option
@dry_run_option
@click.pass_context
def beat_marker_cmd(
    ctx: click.Context,
    json_input: dict | None,
    dry_run: bool,
) -> None:
    """BPMベースのマーカー自動配置。"""
    if not json_input:
        raise click.UsageError("--json is required")
    data = BeatMarkerInput.model_validate(json_input)
    result = beat_marker_impl(
        bpm=data.bpm,
        note_value=data.note_value,
        color=data.color,
        name=data.name,
        duration=data.duration,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))
```

`src/davinci_cli/commands/timeline.py` に以下を追加（ファイル末尾のスキーマ登録の直前）:

```python
# --- Beat Markers Registration ---
from davinci_cli.commands.beat_markers import beat_marker_cmd

timeline_marker.add_command(beat_marker_cmd)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerCLI -v`
Expected: PASS (4 tests)

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/beat_markers.py src/davinci_cli/commands/timeline.py tests/unit/test_beat_markers.py
git commit -m "feat: add 'dr timeline marker beats' CLI command (BPM-based marker placement)"
```

---

### Task 6: MCP ツール登録

**Files:**
- Modify: `src/davinci_cli/mcp/mcp_server.py`
- Modify: `tests/unit/test_beat_markers.py`

**Step 1: 失敗するテストを書く**

以下を `tests/unit/test_beat_markers.py` に追加:

```python
class TestBeatMarkerMCP:
    def test_mcp_tool_registered(self):
        """MCP ツールとして timeline_marker_beats が登録されている"""
        from davinci_cli.mcp.mcp_server import mcp

        tool_names = [t.name for t in mcp._tool_manager.list_tools()]
        assert "timeline_marker_beats" in tool_names
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerMCP -v`
Expected: FAIL (`timeline_marker_beats` がまだ登録されていない)

**Step 3: 最小限の実装**

`src/davinci_cli/mcp/mcp_server.py` に以下を追加（`timeline_marker_delete` の後、`# ---- clip ----` の前）:

```python
from davinci_cli.commands.beat_markers import beat_marker_impl


@mcp.tool(
    description=(
        "Add beat markers across the entire current timeline at regular intervals.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: bpm (float, required), note_value (str, default='1/4'),\n"
        "color (str, default='Blue'), name (str, default=''),\n"
        "duration (int, default=1), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first to preview marker count."
    )
)
@mcp_error_handler
def timeline_marker_beats(
    bpm: float,
    note_value: str = "1/4",
    color: str = "Blue",
    name: str = "",
    duration: int = 1,
    dry_run: bool = True,
) -> dict:
    return beat_marker_impl(
        bpm=bpm,
        note_value=note_value,
        color=color,
        name=name,
        duration=duration,
        dry_run=dry_run,
    )
```

import 文は既存の timeline import ブロックの後に追加:

```python
from davinci_cli.commands.beat_markers import beat_marker_impl
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerMCP -v`
Expected: PASS (1 test)

**Step 5: コミット**

```bash
git add src/davinci_cli/mcp/mcp_server.py tests/unit/test_beat_markers.py
git commit -m "feat: register timeline_marker_beats MCP tool"
```

---

### Task 7: スキーマレジストリ登録

**Files:**
- Modify: `src/davinci_cli/commands/beat_markers.py`
- Modify: `tests/unit/test_beat_markers.py`

**Step 1: 失敗するテストを書く**

以下を `tests/unit/test_beat_markers.py` に追加:

```python
from davinci_cli.schema_registry import SCHEMA_REGISTRY


class TestBeatMarkerSchema:
    def test_schema_registered(self):
        """timeline.marker.beats がスキーマレジストリに登録されている"""
        assert "timeline.marker.beats" in SCHEMA_REGISTRY

    def test_schema_has_input_and_output(self):
        """入出力モデルが両方登録されている"""
        input_model, output_model = SCHEMA_REGISTRY["timeline.marker.beats"]
        assert input_model is not None
        assert output_model is not None

    def test_input_schema_has_bpm(self):
        """入力スキーマに bpm フィールドがある"""
        input_model, _ = SCHEMA_REGISTRY["timeline.marker.beats"]
        schema = input_model.model_json_schema()
        assert "bpm" in schema["properties"]
        assert "bpm" in schema["required"]

    def test_output_schema_has_added_count(self):
        """出力スキーマに added_count フィールドがある"""
        _, output_model = SCHEMA_REGISTRY["timeline.marker.beats"]
        schema = output_model.model_json_schema()
        assert "added_count" in schema["properties"]
```

**Step 2: 失敗を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerSchema -v`
Expected: FAIL (`timeline.marker.beats` が未登録)

**Step 3: 最小限の実装**

`src/davinci_cli/commands/beat_markers.py` の末尾に以下を追加:

```python
from davinci_cli.schema_registry import register_schema

# --- Schema Registration ---

register_schema(
    "timeline.marker.beats",
    output_model=BeatMarkerOutput,
    input_model=BeatMarkerInput,
)
```

**Step 4: 通過を確認**

Run: `python -m pytest tests/unit/test_beat_markers.py::TestBeatMarkerSchema -v`
Expected: PASS (4 tests)

**Step 5: コミット**

```bash
git add src/davinci_cli/commands/beat_markers.py tests/unit/test_beat_markers.py
git commit -m "feat: register timeline.marker.beats schema (input/output models)"
```

---

### Task 8: 全テスト通過確認 + 既存テストのデグレチェック

**Files:**
- 変更なし（検証のみ）

**Step 1: 全ユニットテスト実行**

Run: `python -m pytest tests/unit/ -v`
Expected: ALL PASS（既存テストにデグレなし）

**Step 2: beat_markers テストのみ実行**

Run: `python -m pytest tests/unit/test_beat_markers.py -v`
Expected: ALL PASS

**Step 3: コミット**

デグレがあれば修正してコミット。なければスキップ。
