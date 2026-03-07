import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.timeline import (
    marker_add_impl,
    marker_delete_impl,
    marker_list_impl,
    timeline_create_impl,
    timeline_current_impl,
    timeline_delete_impl,
    timeline_export_impl,
    timeline_list_impl,
    timeline_switch_impl,
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
