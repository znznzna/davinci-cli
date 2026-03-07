import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.color import (
    color_apply_lut_impl,
    color_copy_grade_impl,
    color_paste_grade_impl,
    color_reset_impl,
    node_add_impl,
    node_delete_impl,
    node_list_impl,
    still_apply_impl,
    still_grab_impl,
    still_list_impl,
)
from davinci_cli.core.exceptions import ValidationError

RESOLVE_PATCH = "davinci_cli.commands.color.get_resolve"


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
    project.GetGallery.return_value = MagicMock(
        GetCurrentStillAlbum=MagicMock(
            return_value=MagicMock(GetStills=MagicMock(return_value=[]))
        )
    )
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestColorApplyLutImpl:
    def test_path_traversal_rejected(self):
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
