
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.media import (
    folder_create_impl,
    folder_delete_impl,
    folder_list_impl,
    media_delete_impl,
    media_import_impl,
    media_list_impl,
    media_move_impl,
    media_relink_impl,
    media_unlink_impl,
)
from davinci_cli.core.exceptions import ValidationError

RESOLVE_PATCH = "davinci_cli.commands.media.get_resolve"


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
    media_pool.GetCurrentFolder.return_value = root_folder
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
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError, match="not found"),
        ):
            media_list_impl(folder_name="NonExistent")


class TestMediaImportImpl:
    def test_path_traversal_rejected(self):
        with pytest.raises(ValidationError, match="path traversal"):
            media_import_impl(paths=["../../../etc/shadow"])

    def test_file_not_found(self):
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


class TestMediaExtendedImpl:
    def test_media_move_dry_run(self):
        result = media_move_impl(
            clip_names=["clip1.mov"], target_folder="VFX", dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "media_move"

    def test_media_move(self, mock_resolve):
        # Add a target subfolder to root
        target = MagicMock()
        target.GetName.return_value = "VFX"
        root = mock_resolve.GetProjectManager().GetCurrentProject().GetMediaPool().GetRootFolder()
        root.GetSubFolderList.return_value = [target]
        media_pool = mock_resolve.GetProjectManager().GetCurrentProject().GetMediaPool()
        media_pool.MoveClips.return_value = True

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = media_move_impl(
                clip_names=["clip1.mov"], target_folder="VFX"
            )
        assert result["moved_count"] == 1
        media_pool.MoveClips.assert_called_once()

    def test_media_move_clip_not_found(self, mock_resolve):
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError, match="not found"),
        ):
            media_move_impl(clip_names=["nonexistent.mov"], target_folder="VFX")

    def test_media_delete_dry_run(self):
        result = media_delete_impl(clip_names=["clip1.mov"], dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "media_delete"

    def test_media_delete(self, mock_resolve):
        media_pool = mock_resolve.GetProjectManager().GetCurrentProject().GetMediaPool()
        media_pool.DeleteClips.return_value = True

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = media_delete_impl(clip_names=["clip1.mov"])
        assert result["deleted_count"] == 1
        media_pool.DeleteClips.assert_called_once()

    def test_media_relink_dry_run(self):
        result = media_relink_impl(
            clip_names=["clip1.mov"], folder_path="/media/new", dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "media_relink"

    def test_media_relink(self, mock_resolve, tmp_path):
        media_pool = mock_resolve.GetProjectManager().GetCurrentProject().GetMediaPool()
        media_pool.RelinkClips.return_value = True

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = media_relink_impl(
                clip_names=["clip1.mov"], folder_path=str(tmp_path)
            )
        assert result["relinked_count"] == 1
        media_pool.RelinkClips.assert_called_once()

    def test_media_relink_path_traversal(self):
        with pytest.raises(ValidationError, match="path traversal"):
            media_relink_impl(
                clip_names=["clip1.mov"], folder_path="../../../etc"
            )

    def test_media_unlink(self, mock_resolve):
        media_pool = mock_resolve.GetProjectManager().GetCurrentProject().GetMediaPool()
        media_pool.UnlinkClips.return_value = True

        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = media_unlink_impl(clip_names=["clip1.mov"])
        assert result["unlinked_count"] == 1
        media_pool.UnlinkClips.assert_called_once()


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
