
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.media import (
    folder_create_impl,
    folder_delete_impl,
    folder_list_impl,
    media_import_impl,
    media_list_impl,
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
