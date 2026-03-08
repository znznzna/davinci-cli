import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.color import (
    color_apply_lut_impl,
    color_copy_grade_impl,
    color_reset_impl,
    color_version_add_impl,
    color_version_current_impl,
    color_version_delete_impl,
    color_version_list_impl,
    color_version_load_impl,
    color_version_rename_impl,
    node_enable_impl,
    node_list_impl,
    node_lut_get_impl,
    node_lut_set_impl,
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



class TestColorVersionImpl:
    def test_version_list(self, mock_resolve):
        clip = MagicMock()
        clip.GetVersionNameList.return_value = ["Version 1", "Version 2"]
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_version_list_impl(clip_index=0)
        clip.GetVersionNameList.assert_called_once_with(0)
        assert result == [
            {"name": "Version 1", "version_type": 0},
            {"name": "Version 2", "version_type": 0},
        ]

    def test_version_current(self, mock_resolve):
        clip = MagicMock()
        clip.GetCurrentVersion.return_value = {"versionName": "V1", "versionType": 0}
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_version_current_impl(clip_index=0)
        assert result == {"versionName": "V1", "versionType": 0}

    def test_version_add_dry_run(self):
        result = color_version_add_impl(
            clip_index=0, name="V2", version_type=0, dry_run=True
        )
        assert result == {
            "dry_run": True,
            "action": "version_add",
            "name": "V2",
            "version_type": 0,
            "clip_index": 0,
        }

    def test_version_add(self, mock_resolve):
        clip = MagicMock()
        clip.AddVersion.return_value = True
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_version_add_impl(clip_index=0, name="V2", version_type=0)
        clip.AddVersion.assert_called_once_with("V2", 0)
        assert result == {
            "added": True,
            "name": "V2",
            "version_type": 0,
            "clip_index": 0,
        }

    def test_version_add_failure(self, mock_resolve):
        clip = MagicMock()
        clip.AddVersion.return_value = False
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to add version"
        ):
            color_version_add_impl(clip_index=0, name="V2", version_type=0)


class TestColorVersionMutateImpl:
    def test_version_load_dry_run(self):
        result = color_version_load_impl(
            clip_index=0, name="V1", version_type=0, dry_run=True
        )
        assert result == {
            "dry_run": True,
            "action": "version_load",
            "name": "V1",
            "version_type": 0,
            "clip_index": 0,
        }

    def test_version_load(self, mock_resolve):
        clip = MagicMock()
        clip.LoadVersionByName.return_value = True
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_version_load_impl(clip_index=0, name="V1", version_type=0)
        clip.LoadVersionByName.assert_called_once_with("V1", 0)
        assert result == {
            "loaded": True,
            "name": "V1",
            "version_type": 0,
            "clip_index": 0,
        }

    def test_version_load_failure(self, mock_resolve):
        clip = MagicMock()
        clip.LoadVersionByName.return_value = False
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to load version"
        ):
            color_version_load_impl(clip_index=0, name="V1", version_type=0)

    def test_version_delete_dry_run(self):
        result = color_version_delete_impl(
            clip_index=0, name="V1", version_type=0, dry_run=True
        )
        assert result == {
            "dry_run": True,
            "action": "version_delete",
            "name": "V1",
            "version_type": 0,
            "clip_index": 0,
        }

    def test_version_delete(self, mock_resolve):
        clip = MagicMock()
        clip.DeleteVersionByName.return_value = True
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_version_delete_impl(clip_index=0, name="V1", version_type=0)
        clip.DeleteVersionByName.assert_called_once_with("V1", 0)
        assert result == {
            "deleted": True,
            "name": "V1",
            "version_type": 0,
            "clip_index": 0,
        }

    def test_version_delete_failure(self, mock_resolve):
        clip = MagicMock()
        clip.DeleteVersionByName.return_value = False
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to delete version"
        ):
            color_version_delete_impl(clip_index=0, name="V1", version_type=0)

    def test_version_rename_dry_run(self):
        result = color_version_rename_impl(
            clip_index=0, old_name="V1", new_name="V2", version_type=0, dry_run=True
        )
        assert result == {
            "dry_run": True,
            "action": "version_rename",
            "old_name": "V1",
            "new_name": "V2",
            "version_type": 0,
            "clip_index": 0,
        }

    def test_version_rename(self, mock_resolve):
        clip = MagicMock()
        clip.RenameVersionByName.return_value = True
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = color_version_rename_impl(
                clip_index=0, old_name="V1", new_name="V2", version_type=0
            )
        clip.RenameVersionByName.assert_called_once_with("V1", "V2", 0)
        assert result == {
            "renamed": True,
            "old_name": "V1",
            "new_name": "V2",
            "version_type": 0,
            "clip_index": 0,
        }

    def test_version_rename_failure(self, mock_resolve):
        clip = MagicMock()
        clip.RenameVersionByName.return_value = False
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]

        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to rename version"
        ):
            color_version_rename_impl(
                clip_index=0, old_name="V1", new_name="V2", version_type=0
            )


class TestGraphOperationsImpl:
    @pytest.fixture
    def mock_resolve_with_graph(self, mock_resolve):
        graph = MagicMock()
        graph.SetLUT.return_value = True
        graph.GetLUT.return_value = "rec709.cube"
        graph.SetNodeEnabled.return_value = True

        clip = MagicMock()
        clip.GetNodeGraph.return_value = graph
        pm = mock_resolve.GetProjectManager()
        tl = pm.GetCurrentProject().GetCurrentTimeline()
        tl.GetItemListInTrack.return_value = [clip]
        return mock_resolve, graph

    def test_node_lut_set_dry_run(self, tmp_path):
        lut = tmp_path / "test.cube"
        lut.touch()
        result = node_lut_set_impl(
            clip_index=0, node_index=1, lut_path=str(lut), dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "node_lut_set"
        assert result["clip_index"] == 0
        assert result["node_index"] == 1

    def test_node_lut_set(self, mock_resolve_with_graph, tmp_path):
        mock_resolve, graph = mock_resolve_with_graph
        lut = tmp_path / "rec709.cube"
        lut.touch()
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = node_lut_set_impl(
                clip_index=0, node_index=1, lut_path=str(lut)
            )
        graph.SetLUT.assert_called_once_with(1, str(lut))
        assert result["set"] is True
        assert result["node_index"] == 1
        assert result["lut_path"] == str(lut)

    def test_node_lut_get(self, mock_resolve_with_graph):
        mock_resolve, graph = mock_resolve_with_graph
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = node_lut_get_impl(clip_index=0, node_index=1)
        graph.GetLUT.assert_called_once_with(1)
        assert result["lut_path"] == "rec709.cube"
        assert result["node_index"] == 1

    def test_node_enable_dry_run(self):
        result = node_enable_impl(
            clip_index=0, node_index=1, enabled=True, dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "node_enable"
        assert result["node_index"] == 1
        assert result["enabled"] is True

    def test_node_enable(self, mock_resolve_with_graph):
        mock_resolve, graph = mock_resolve_with_graph
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = node_enable_impl(clip_index=0, node_index=1, enabled=True)
        graph.SetNodeEnabled.assert_called_once_with(1, True)
        assert result["set"] is True
        assert result["node_index"] == 1
        assert result["enabled"] is True


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

    def test_version_add_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["color", "version", "add", "0", "V2", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "version_add"
        assert data["name"] == "V2"

    def test_reset_dry_run(self):
        result = CliRunner().invoke(dr, ["color", "reset", "0", "--dry-run"])
        assert result.exit_code == 0

    def test_version_load_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["color", "version", "load", "0", "V1", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "version_load"

    def test_version_delete_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["color", "version", "delete", "0", "V1", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "version_delete"

    def test_version_rename_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["color", "version", "rename", "0", "V1", "V2", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "version_rename"
