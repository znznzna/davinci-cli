"""Beat markers — _calculate_beat_frames() 純粋関数テスト。"""

from unittest.mock import MagicMock, patch

import pytest

from davinci_cli.commands.beat_markers import _calculate_beat_frames, beat_marker_impl

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
