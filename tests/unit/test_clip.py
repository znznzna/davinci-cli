import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.clip import (
    clip_info_impl,
    clip_list_impl,
    clip_property_get_impl,
    clip_property_set_impl,
)
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError

RESOLVE_PATCH = "davinci_cli.commands.clip.get_resolve"


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
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.GetCurrentTimeline.return_value = None
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ProjectNotOpenError),
        ):
            clip_list_impl()


class TestClipInfoImpl:
    def test_returns_clip_info(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = clip_info_impl(index=0)
        assert result["index"] == 0
        assert "name" in result

    def test_out_of_range_raises(self, mock_resolve):
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError),
        ):
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
            dr,
            ["clip", "property", "set", "0", "Pan", "0.5", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
