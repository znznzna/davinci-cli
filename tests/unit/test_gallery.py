import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands import color as color_module
from davinci_cli.commands import gallery as gallery_module
from davinci_cli.commands.gallery import (
    gallery_album_create_impl,
    gallery_album_current_impl,
    gallery_album_list_impl,
    gallery_album_set_impl,
    gallery_still_delete_impl,
    gallery_still_export_impl,
    gallery_still_import_impl,
)
from davinci_cli.core.exceptions import ValidationError

RESOLVE_PATCH = "davinci_cli.commands.gallery.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()

    album1 = MagicMock(name="album1_obj")
    album2 = MagicMock(name="album2_obj")
    gallery = MagicMock()
    gallery.GetGalleryStillAlbums.return_value = [album1, album2]
    gallery.GetCurrentStillAlbum.return_value = album1
    gallery.GetAlbumName.side_effect = lambda a: {
        id(album1): "Album 1",
        id(album2): "Album 2",
    }[id(a)]
    gallery.SetCurrentStillAlbum.return_value = True
    new_album = MagicMock(name="new_album_obj")
    gallery.CreateGalleryStillAlbum.return_value = new_album
    # Register new_album name
    _original_side_effect = gallery.GetAlbumName.side_effect
    gallery.GetAlbumName.side_effect = lambda a: {
        id(album1): "Album 1",
        id(album2): "Album 2",
        id(new_album): "Album 3",
    }.get(id(a), "Unknown")

    # Stills
    still1 = MagicMock(name="still1_obj")
    still1.GetLabel.return_value = "Still 0"
    still2 = MagicMock(name="still2_obj")
    still2.GetLabel.return_value = "Still 1"
    album1.GetStills.return_value = [still1, still2]
    album1.ExportStills.return_value = True
    album1.ImportStills.return_value = True
    album1.DeleteStills.return_value = True

    project.GetGallery.return_value = gallery
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm

    # Expose for assertions
    resolve._gallery = gallery
    resolve._album1 = album1
    resolve._album2 = album2
    resolve._new_album = new_album
    resolve._still1 = still1
    resolve._still2 = still2
    return resolve


class TestGalleryAlbumListImpl:
    def test_album_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_album_list_impl()
        assert len(result) == 2
        assert result[0] == {"index": 0, "name": "Album 1"}
        assert result[1] == {"index": 1, "name": "Album 2"}

    def test_album_list_empty(self, mock_resolve):
        mock_resolve._gallery.GetGalleryStillAlbums.return_value = []
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_album_list_impl()
        assert result == []


class TestGalleryAlbumCurrentImpl:
    def test_album_current(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_album_current_impl()
        assert result == {"name": "Album 1"}

    def test_album_current_none(self, mock_resolve):
        mock_resolve._gallery.GetCurrentStillAlbum.return_value = None
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_album_current_impl()
        assert result == {"name": None}


class TestGalleryAlbumSetImpl:
    def test_album_set_dry_run(self):
        result = gallery_album_set_impl(name="Album 2", dry_run=True)
        assert result == {
            "dry_run": True,
            "action": "album_set",
            "name": "Album 2",
        }

    def test_album_set(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_album_set_impl(name="Album 2")
        mock_resolve._gallery.SetCurrentStillAlbum.assert_called_once_with(
            mock_resolve._album2
        )
        assert result == {"set": True, "name": "Album 2"}

    def test_album_set_not_found(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Album not found"
        ):
            gallery_album_set_impl(name="Nonexistent")

    def test_album_set_failure(self, mock_resolve):
        mock_resolve._gallery.SetCurrentStillAlbum.return_value = False
        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to set album"
        ):
            gallery_album_set_impl(name="Album 1")


class TestGalleryAlbumCreateImpl:
    def test_album_create_dry_run(self):
        result = gallery_album_create_impl(dry_run=True)
        assert result == {"dry_run": True, "action": "album_create"}

    def test_album_create(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_album_create_impl()
        mock_resolve._gallery.CreateGalleryStillAlbum.assert_called_once()
        assert result == {"created": True, "name": "Album 3"}

    def test_album_create_failure(self, mock_resolve):
        mock_resolve._gallery.CreateGalleryStillAlbum.return_value = None
        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to create album"
        ):
            gallery_album_create_impl()


class TestGalleryStillExportImpl:
    def test_still_export_dry_run(self):
        result = gallery_still_export_impl(
            folder_path="/tmp/stills", file_prefix="still", format="dpx", dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "still_export"
        assert result["format"] == "dpx"

    def test_still_export(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_still_export_impl(folder_path="/tmp/stills")
        mock_resolve._album1.ExportStills.assert_called_once()
        assert result["exported"] == 2
        assert result["format"] == "dpx"

    def test_still_export_empty(self, mock_resolve):
        mock_resolve._album1.GetStills.return_value = []
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_still_export_impl(folder_path="/tmp/stills")
        assert result["exported"] == 0

    def test_still_export_failure(self, mock_resolve):
        mock_resolve._album1.ExportStills.return_value = False
        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to export stills"
        ):
            gallery_still_export_impl(folder_path="/tmp/stills")


class TestGalleryStillImportImpl:
    def test_still_import_dry_run(self):
        result = gallery_still_import_impl(
            paths=["/tmp/still1.dpx", "/tmp/still2.dpx"], dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "still_import"

    def test_still_import(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_still_import_impl(
                paths=["/tmp/still1.dpx", "/tmp/still2.dpx"]
            )
        mock_resolve._album1.ImportStills.assert_called_once()
        assert result["imported"] is True

    def test_still_import_failure(self, mock_resolve):
        mock_resolve._album1.ImportStills.return_value = False
        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to import stills"
        ):
            gallery_still_import_impl(paths=["/tmp/still1.dpx"])


class TestGalleryStillDeleteImpl:
    def test_still_delete_dry_run(self):
        result = gallery_still_delete_impl(still_indices=[0, 1], dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "still_delete"
        assert result["still_indices"] == [0, 1]

    def test_still_delete(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = gallery_still_delete_impl(still_indices=[0])
        mock_resolve._album1.DeleteStills.assert_called_once_with(
            [mock_resolve._still1]
        )
        assert result["deleted"] == 1

    def test_still_delete_out_of_range(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="out of range"
        ):
            gallery_still_delete_impl(still_indices=[5])

    def test_still_delete_failure(self, mock_resolve):
        mock_resolve._album1.DeleteStills.return_value = False
        with patch(RESOLVE_PATCH, return_value=mock_resolve), pytest.raises(
            ValidationError, match="Failed to delete stills"
        ):
            gallery_still_delete_impl(still_indices=[0])


class TestGalleryCLI:
    def test_album_set_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["gallery", "album", "set", "Album 2", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "album_set"
        assert data["name"] == "Album 2"

    def test_album_create_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["gallery", "album", "create", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "album_create"

    def test_still_export_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["gallery", "still", "export", "/tmp/stills", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "still_export"

    def test_still_import_dry_run_cli(self):
        result = CliRunner().invoke(
            dr,
            ["gallery", "still", "import", "/tmp/s1.dpx", "/tmp/s2.dpx", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "still_import"

    def test_still_delete_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["gallery", "still", "delete", "0", "1", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "still_delete"
        assert data["still_indices"] == [0, 1]

    def test_still_grab_dry_run_cli(self):
        result = CliRunner().invoke(
            dr, ["gallery", "still", "grab", "0", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "still_grab"
        assert data["clip_index"] == 0

    def test_still_list_cli(self, mock_resolve):
        with patch(
            "davinci_cli.commands.color.get_resolve", return_value=mock_resolve
        ):
            result = CliRunner().invoke(dr, ["gallery", "still", "list"])
        assert result.exit_code == 0
        # NDJSON output: one line per still
        lines = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(lines) == 2
        assert lines[0]["index"] == 0
        assert lines[1]["index"] == 1


class TestGalleryStillImplReuse:
    """gallery.still.list / gallery.still.grab が color.py の impl を再利用していることを確認。"""

    def test_still_list_impl_is_same(self):
        assert gallery_module.still_list_impl is color_module.still_list_impl

    def test_still_grab_impl_is_same(self):
        assert gallery_module.still_grab_impl is color_module.still_grab_impl
