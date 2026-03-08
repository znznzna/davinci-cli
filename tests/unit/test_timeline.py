import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.timeline import (
    _get_start_frame_offset,
    current_item_impl,
    marker_add_impl,
    marker_delete_impl,
    marker_list_impl,
    timecode_get_impl,
    timecode_set_impl,
    timeline_create_impl,
    timeline_create_subtitles_impl,
    timeline_current_impl,
    timeline_delete_impl,
    timeline_detect_scene_cuts_impl,
    timeline_duplicate_impl,
    timeline_export_impl,
    timeline_list_impl,
    timeline_switch_impl,
    track_add_impl,
    track_delete_impl,
    track_enable_impl,
    track_list_impl,
    track_lock_impl,
)
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError

RESOLVE_PATCH = "davinci_cli.commands.timeline.get_resolve"


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
    track_counts = {"video": 2, "audio": 1, "subtitle": 0}
    timeline1.GetTrackCount.side_effect = lambda t: track_counts.get(t, 0)
    timeline1.GetTrackName.side_effect = lambda t, i: f"{t} {i}"
    timeline1.AddTrack.return_value = True
    timeline1.DeleteTrack.return_value = True
    timeline1.GetIsTrackEnabled.return_value = True
    timeline1.SetTrackEnable.return_value = True
    timeline1.GetIsTrackLocked.return_value = False
    timeline1.SetTrackLock.return_value = True

    timeline1.GetMarkers.return_value = {
        100: {"color": "Blue", "name": "VFX", "note": "", "duration": 1},
    }

    timeline2 = MagicMock()
    timeline2.GetName.return_value = "VFX Timeline"
    timeline2.GetSetting.return_value = "24"

    project.GetTimelineCount.return_value = 2
    project.GetTimelineByIndex.side_effect = lambda i: {
        1: timeline1,
        2: timeline2,
    }.get(i)
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
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.GetCurrentTimeline.return_value = None
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ProjectNotOpenError),
        ):
            timeline_current_impl()


class TestTimelineSwitchImpl:
    def test_dry_run(self):
        result = timeline_switch_impl(name="Edit", dry_run=True)
        assert result == {"dry_run": True, "action": "switch", "name": "Edit"}

    def test_switch_not_found(self, mock_resolve):
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.GetTimelineCount.return_value = 0
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError),
        ):
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


class TestGetStartFrameOffset:
    """_get_start_frame_offset のユニットテスト。"""

    def test_zero_offset(self):
        tl = MagicMock()
        tl.GetStartTimecode.return_value = "00:00:00:00"
        tl.GetSetting.return_value = "24"
        assert _get_start_frame_offset(tl) == 0

    def test_one_hour_at_24fps(self):
        tl = MagicMock()
        tl.GetStartTimecode.return_value = "01:00:00:00"
        tl.GetSetting.return_value = "24"
        assert _get_start_frame_offset(tl) == 86400  # 1*3600*24

    def test_one_hour_at_30fps(self):
        tl = MagicMock()
        tl.GetStartTimecode.return_value = "01:00:00:00"
        tl.GetSetting.return_value = "30"
        assert _get_start_frame_offset(tl) == 108000  # 1*3600*30

    def test_complex_timecode(self):
        tl = MagicMock()
        tl.GetStartTimecode.return_value = "01:02:03:04"
        tl.GetSetting.return_value = "24"
        # 1*3600*24 + 2*60*24 + 3*24 + 4 = 86400 + 2880 + 72 + 4 = 89356
        assert _get_start_frame_offset(tl) == 89356

    def test_drop_frame_semicolon(self):
        tl = MagicMock()
        tl.GetStartTimecode.return_value = "01:00:00;00"
        tl.GetSetting.return_value = "30"
        assert _get_start_frame_offset(tl) == 108000

    def test_none_timecode_defaults_zero(self):
        tl = MagicMock()
        tl.GetStartTimecode.return_value = None
        tl.GetSetting.return_value = "24"
        assert _get_start_frame_offset(tl) == 0

    def test_none_fps_defaults_24(self):
        tl = MagicMock()
        tl.GetStartTimecode.return_value = "01:00:00:00"
        tl.GetSetting.return_value = None
        assert _get_start_frame_offset(tl) == 86400  # default 24fps


class TestMarkerImpl:
    def test_marker_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = marker_list_impl()
        assert isinstance(result, list)

    def test_marker_list_frame_offset_applied(self, mock_resolve):
        """開始TC=01:00:00:00のとき、marker_listのframe_idにオフセットが加算される。"""
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.GetStartTimecode.return_value = "01:00:00:00"
        timeline.GetMarkers.return_value = {
            0: {"color": "Blue", "name": "Start", "note": "", "duration": 1},
            100: {"color": "Red", "name": "Cut", "note": "", "duration": 1},
        }
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = marker_list_impl()
        assert result[0]["frame_id"] == 86400  # 0 + 86400
        assert result[1]["frame_id"] == 86500  # 100 + 86400

    def test_marker_add_converts_absolute_to_relative(self, mock_resolve):
        """marker_addは絶対フレーム→相対フレームに変換してAPIを呼ぶ。"""
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.GetStartTimecode.return_value = "01:00:00:00"
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = marker_add_impl(frame_id=86500, color="Blue", name="Test")
        # API should receive relative frame: 86500 - 86400 = 100
        timeline.AddMarker.assert_called_once_with(100, "Blue", "Test", "", 1)
        assert result["frame_id"] == 86500

    def test_marker_delete_converts_absolute_to_relative(self, mock_resolve):
        """marker_deleteは絶対フレーム→相対フレームに変換してAPIを呼ぶ。"""
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.GetStartTimecode.return_value = "01:00:00:00"
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            marker_delete_impl(frame_id=86500)
        # API should receive relative frame: 86500 - 86400 = 100
        timeline.DeleteMarkerAtFrame.assert_called_once_with(100)

    def test_marker_add_dry_run(self):
        result = marker_add_impl(
            frame_id=100, color="Blue", name="VFX", dry_run=True
        )
        assert result["dry_run"] is True

    def test_marker_delete_dry_run(self):
        result = marker_delete_impl(frame_id=100, dry_run=True)
        assert result["dry_run"] is True


class TestTimecodeImpl:
    def test_timecode_get(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.GetCurrentTimecode.return_value = "01:00:00:00"
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timecode_get_impl()
        assert result == {"timecode": "01:00:00:00"}

    def test_timecode_set_dry_run(self):
        result = timecode_set_impl("01:00:05:00", dry_run=True)
        assert result == {
            "dry_run": True,
            "action": "timecode_set",
            "timecode": "01:00:05:00",
        }

    def test_timecode_set(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.SetCurrentTimecode.return_value = True
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timecode_set_impl("01:00:05:00")
        assert result == {"set": True, "timecode": "01:00:05:00"}
        timeline.SetCurrentTimecode.assert_called_once_with("01:00:05:00")

    def test_timecode_set_failure(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.SetCurrentTimecode.return_value = False
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError),
        ):
            timecode_set_impl("99:99:99:99")


class TestCurrentItemImpl:
    def test_current_item(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        item = MagicMock()
        item.GetName.return_value = "Clip1"
        timeline.GetCurrentVideoItem.return_value = item
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = current_item_impl()
        assert result == {"name": "Clip1"}

    def test_current_item_none(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.GetCurrentVideoItem.return_value = None
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = current_item_impl()
        assert result == {"name": None}


class TestTrackImpl:
    def test_track_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = track_list_impl()
        assert len(result) == 3  # video 2 + audio 1
        assert result[0] == {"type": "video", "index": 1, "name": "video 1"}
        assert result[1] == {"type": "video", "index": 2, "name": "video 2"}
        assert result[2] == {"type": "audio", "index": 1, "name": "audio 1"}

    def test_track_add_dry_run(self):
        result = track_add_impl("video", dry_run=True)
        assert result == {
            "dry_run": True,
            "action": "track_add",
            "track_type": "video",
            "sub_track_type": None,
        }

    def test_track_add(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = track_add_impl("video")
        assert result == {"added": True, "track_type": "video"}
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.AddTrack.assert_called_once_with("video")

    def test_track_add_with_sub_type(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = track_add_impl("audio", sub_track_type="mono")
        assert result == {"added": True, "track_type": "audio"}
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.AddTrack.assert_called_once_with("audio", "mono")

    def test_track_delete_dry_run(self):
        result = track_delete_impl("video", 2, dry_run=True)
        assert result == {
            "dry_run": True,
            "action": "track_delete",
            "track_type": "video",
            "index": 2,
        }

    def test_track_delete(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = track_delete_impl("video", 2)
        assert result == {"deleted": True, "track_type": "video", "index": 2}
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.DeleteTrack.assert_called_once_with("video", 2)

    def test_track_add_invalid_type(self):
        with pytest.raises(ValidationError):
            track_add_impl("invalid")

    def test_track_delete_invalid_type(self):
        with pytest.raises(ValidationError):
            track_delete_impl("invalid", 1)

    def test_track_add_failure(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.AddTrack.return_value = False
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError),
        ):
            track_add_impl("video")

    def test_track_delete_failure(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.DeleteTrack.return_value = False
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError),
        ):
            track_delete_impl("video", 2)


class TestTrackEnableLockImpl:
    def test_track_enable_get(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = track_enable_impl("video", 1)
        assert result == {"enabled": True, "track_type": "video", "index": 1}

    def test_track_enable_set(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = track_enable_impl("video", 1, enabled=False)
        assert result == {"set": True, "enabled": False, "track_type": "video", "index": 1}
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.SetTrackEnable.assert_called_once_with("video", 1, False)

    def test_track_enable_set_failure(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.SetTrackEnable.return_value = False
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError),
        ):
            track_enable_impl("video", 1, enabled=False)

    def test_track_enable_invalid_type(self):
        with pytest.raises(ValidationError):
            track_enable_impl("invalid", 1)

    def test_track_lock_get(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = track_lock_impl("video", 1)
        assert result == {"locked": False, "track_type": "video", "index": 1}

    def test_track_lock_set(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = track_lock_impl("video", 1, locked=True)
        assert result == {"set": True, "locked": True, "track_type": "video", "index": 1}
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.SetTrackLock.assert_called_once_with("video", 1, True)

    def test_track_lock_set_failure(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.SetTrackLock.return_value = False
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError),
        ):
            track_lock_impl("video", 1, locked=True)

    def test_track_lock_invalid_type(self):
        with pytest.raises(ValidationError):
            track_lock_impl("invalid", 1)


class TestTimelineExtendedImpl:
    def test_duplicate_dry_run(self):
        result = timeline_duplicate_impl("copy", dry_run=True)
        assert result == {"dry_run": True, "action": "duplicate", "name": "copy"}

    def test_duplicate(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        new_tl = MagicMock()
        new_tl.GetName.return_value = "copy"
        timeline.DuplicateTimeline.return_value = new_tl
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_duplicate_impl("copy")
        assert result == {"duplicated": True, "name": "copy"}
        timeline.DuplicateTimeline.assert_called_once_with("copy")

    def test_duplicate_no_name(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        new_tl = MagicMock()
        new_tl.GetName.return_value = "Main Edit copy"
        timeline.DuplicateTimeline.return_value = new_tl
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_duplicate_impl()
        assert result == {"duplicated": True, "name": "Main Edit copy"}
        timeline.DuplicateTimeline.assert_called_once_with()

    def test_duplicate_failure(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.DuplicateTimeline.return_value = None
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError),
        ):
            timeline_duplicate_impl("copy")

    def test_detect_scene_cuts(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.DetectSceneCuts.return_value = True
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_detect_scene_cuts_impl()
        assert result == {"detected": True}

    def test_detect_scene_cuts_false(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.DetectSceneCuts.return_value = False
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_detect_scene_cuts_impl()
        assert result == {"detected": False}

    def test_create_subtitles(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.CreateSubtitlesFromAudio.return_value = True
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_create_subtitles_impl()
        assert result == {"created": True}

    def test_create_subtitles_false(self, mock_resolve):
        timeline = mock_resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.CreateSubtitlesFromAudio.return_value = False
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = timeline_create_subtitles_impl()
        assert result == {"created": False}


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

    def test_marker_delete_json_input(self):
        result = CliRunner().invoke(
            dr,
            ["timeline", "marker", "delete", "--json", '{"frame_id": 100}', "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["frame_id"] == 100

    def test_marker_delete_positional_still_works(self):
        result = CliRunner().invoke(
            dr, ["timeline", "marker", "delete", "100", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["frame_id"] == 100

    def test_marker_delete_no_arg_error(self):
        result = CliRunner().invoke(
            dr, ["timeline", "marker", "delete"]
        )
        assert result.exit_code != 0
