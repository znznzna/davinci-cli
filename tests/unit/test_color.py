import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.color import (
    color_apply_lut_impl,
    color_copy_grade_impl,
    color_reset_impl,
    node_list_impl,
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
    clip.GetNumNodes.return_value = 3
    clip.GetNodeLabel.return_value = ""

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

    def test_dry_run(self, tmp_path):
        lut = tmp_path / "test.cube"
        lut.touch()
        result = color_apply_lut_impl(
            clip_index=0, lut_path=str(lut), dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "apply_lut"

    def test_lut_not_found(self):
        with pytest.raises(ValidationError, match="not found"):
            color_apply_lut_impl(clip_index=0, lut_path="/nonexistent/path.cube")

    def test_apply_lut(self, mock_resolve, tmp_path):
        lut = tmp_path / "rec709.cube"
        lut.touch()
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_apply_lut_impl(
                clip_index=0, lut_path=str(lut)
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
    def test_copy_grade_dry_run(self):
        result = color_copy_grade_impl(from_index=0, to_index=1, dry_run=True)
        assert result == {
            "dry_run": True,
            "action": "copy_grade",
            "from_index": 0,
            "to_index": 1,
        }

    def test_copy_grade(self, mock_resolve):
        # Need two clips for from/to
        src_clip = MagicMock()
        tgt_clip = MagicMock()
        src_clip.CopyGrades.return_value = True
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [src_clip, tgt_clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_copy_grade_impl(from_index=0, to_index=1)
        src_clip.CopyGrades.assert_called_once_with([tgt_clip])
        assert result == {"copied_from": 0, "copied_to": 1}

    def test_copy_grade_cli_dry_run(self):
        result = CliRunner().invoke(
            dr, ["color", "copy-grade", "--from", "0", "--to", "1", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "copy_grade"



class TestNodeImpl:
    def test_node_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = node_list_impl(clip_index=0)
        assert isinstance(result, list)
        assert len(result) == 3



class TestStillImpl:
    def test_still_grab_dry_run(self):
        result = still_grab_impl(clip_index=0, dry_run=True)
        assert result["dry_run"] is True

    def test_still_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = still_list_impl()
        assert isinstance(result, list)



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
