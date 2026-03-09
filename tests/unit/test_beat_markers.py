"""Beat markers — _calculate_beat_frames() 純粋関数テスト。"""

from unittest.mock import MagicMock, patch

import pytest

from davinci_cli.commands.beat_markers import _calculate_beat_frames, beat_marker_impl
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError

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

    # クリップモック: video 1トラック, audio 1トラック
    video_clip = MagicMock()
    video_clip.GetName.return_value = "A001.mov"
    video_clip.GetStart.return_value = 86400
    video_clip.GetEnd.return_value = 86640  # 240フレーム
    audio_clip = MagicMock()
    audio_clip.GetName.return_value = "BGM.wav"
    audio_clip.GetStart.return_value = 86400
    audio_clip.GetEnd.return_value = 86640
    timeline.GetTrackCount.side_effect = lambda t: {"video": 1, "audio": 1}.get(t, 0)
    timeline.GetItemListInTrack.side_effect = lambda t, i: {
        ("video", 1): [video_clip],
        ("audio", 1): [audio_clip],
    }.get((t, i), [])

    project.GetCurrentTimeline.return_value = timeline
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


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


class TestBeatMarkerImplDryRun:
    def test_dry_run_returns_preview(self, mock_resolve):
        """dry-run でフレーム一覧が返る"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=120, clip_index=1, note_value="1/4", dry_run=True)
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
            result = beat_marker_impl(bpm=120, clip_index=1, note_value="1/4", dry_run=True)
        # offset=86400, end_frame_abs=86400+240=86640
        # 12フレーム間隔: 86400, 86412, ..., 86640
        assert result["frames"][0] == 86400
        assert result["frames"][1] == 86412
        assert result["count"] == 21


class TestBeatMarkerImplExecute:
    def test_adds_markers_to_timeline(self, mock_resolve):
        """マーカーが実際に追加される"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=120, clip_index=1, note_value="1/4")
        assert result["added_count"] == 21
        assert result["bpm"] == 120
        assert result["note_value"] == "1/4"
        assert result["color"] == "Blue"
        assert len(result["frames"]) == 21
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        assert timeline.AddMarker.call_count == 21

    def test_adds_markers_with_relative_frames(self, mock_resolve):
        """AddMarker は相対フレームで呼ばれる"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            beat_marker_impl(bpm=120, clip_index=1, note_value="1/4")
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        first_call = timeline.AddMarker.call_args_list[0]
        assert first_call[0][0] == 0  # rel_frame
        assert first_call[0][1] == "Blue"
        second_call = timeline.AddMarker.call_args_list[1]
        assert second_call[0][0] == 12

    def test_custom_color_and_name(self, mock_resolve):
        """カスタム色・名前が AddMarker に渡る"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=120, clip_index=1, note_value="1/4", color="Red", name="Beat")
        assert result["color"] == "Red"
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        first_call = timeline.AddMarker.call_args_list[0]
        assert first_call[0][1] == "Red"
        assert first_call[0][2] == "Beat"

    def test_custom_duration(self, mock_resolve):
        """カスタム duration が AddMarker に渡る"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            beat_marker_impl(bpm=120, clip_index=1, note_value="1/4", duration=5)
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        first_call = timeline.AddMarker.call_args_list[0]
        assert first_call[0][4] == 5


class TestBeatMarkerImplValidation:
    def test_invalid_note_value_raises(self, mock_resolve):
        """不正な音価で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="note_value"):
                beat_marker_impl(bpm=120, clip_index=1, note_value="1/3")

    def test_bpm_too_low_raises(self, mock_resolve):
        """BPM が下限未満で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="bpm"):
                beat_marker_impl(bpm=10, clip_index=1)

    def test_bpm_too_high_raises(self, mock_resolve):
        """BPM が上限超で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="bpm"):
                beat_marker_impl(bpm=400, clip_index=1)

    def test_bpm_zero_raises(self, mock_resolve):
        """BPM 0 で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="bpm"):
                beat_marker_impl(bpm=0, clip_index=1)

    def test_bpm_boundary_low_valid(self, mock_resolve):
        """BPM 20.0（下限）は有効"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=20.0, clip_index=1, dry_run=True)
        assert result["bpm"] == 20.0

    def test_bpm_boundary_high_valid(self, mock_resolve):
        """BPM 300.0（上限）は有効"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = beat_marker_impl(bpm=300.0, clip_index=1, dry_run=True)
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
                beat_marker_impl(bpm=120, clip_index=0)

    def test_no_project_raises(self):
        """プロジェクトなしで ProjectNotOpenError"""
        resolve = MagicMock()
        pm = MagicMock()
        pm.GetCurrentProject.return_value = None
        resolve.GetProjectManager.return_value = pm
        with patch(RESOLVE_PATCH, return_value=resolve):
            with pytest.raises(ProjectNotOpenError):
                beat_marker_impl(bpm=120, clip_index=0)

    def test_clip_index_out_of_range_raises(self, mock_resolve):
        """clip_index が範囲外で ValidationError"""
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            with pytest.raises(ValidationError, match="clip_index"):
                beat_marker_impl(bpm=120, clip_index=99)


# --- CLI Tests ---

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
                "--json", '{"bpm": 120, "clip_index": 1}',
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
                    "--json", '{"bpm": 120, "clip_index": 1, "note_value": "1/8"}',
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
                    "--json", '{"bpm": 90, "clip_index": 1, "note_value": "1/2", "color": "Red", "name": "Beat"}',
                    "--dry-run",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["color"] == "Red"


# --- MCP Tests ---


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

    def test_input_schema_has_bpm_and_clip_index(self):
        """入力スキーマに bpm と clip_index フィールドがある"""
        input_model, _ = SCHEMA_REGISTRY["timeline.marker.beats"]
        schema = input_model.model_json_schema()
        assert "bpm" in schema["properties"]
        assert "clip_index" in schema["properties"]
        assert "bpm" in schema["required"]
        assert "clip_index" in schema["required"]

    def test_output_schema_has_added_count(self):
        """出力スキーマに added_count フィールドがある"""
        _, output_model = SCHEMA_REGISTRY["timeline.marker.beats"]
        schema = output_model.model_json_schema()
        assert "added_count" in schema["properties"]


class TestBeatMarkerMCP:
    def test_mcp_tool_registered(self):
        """MCP ツールとして timeline_marker_beats が登録されている"""
        import asyncio

        from davinci_cli.mcp.mcp_server import mcp

        tools = asyncio.run(mcp.list_tools())
        tool_names = [t.name for t in tools]
        assert "timeline_marker_beats" in tool_names
