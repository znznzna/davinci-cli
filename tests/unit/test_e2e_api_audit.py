"""E2E smoke tests for all API audit commands (Tasks 1-23).

CliRunner ベースで CLI コマンドを end-to-end で検証する。
--dry-run コマンドは Resolve モック不要。
読み取り専用コマンドは get_resolve をパッチする。
"""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from davinci_cli.cli import dr

# ---------------------------------------------------------------------------
# Shared patch targets
# ---------------------------------------------------------------------------
SYSTEM_PATCH = "davinci_cli.commands.system.get_resolve"
PROJECT_PATCH = "davinci_cli.commands.project.get_resolve"
TIMELINE_PATCH = "davinci_cli.commands.timeline.get_resolve"
CLIP_PATCH = "davinci_cli.commands.clip.get_resolve"
COLOR_PATCH = "davinci_cli.commands.color.get_resolve"
DELIVER_PATCH = "davinci_cli.commands.deliver.get_resolve"
GALLERY_PATCH = "davinci_cli.commands.gallery.get_resolve"
MEDIA_PATCH = "davinci_cli.commands.media.get_resolve"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_clip_item(name: str = "Clip1") -> MagicMock:
    item = MagicMock()
    item.GetName.return_value = name
    item.GetStart.return_value = 0
    item.GetEnd.return_value = 100
    item.GetDuration.return_value = 100
    item.GetClipEnabled.return_value = True
    item.GetClipColor.return_value = "Orange"
    item.GetFlagList.return_value = ["Blue", "Red"]
    item.GetVersionNameList.return_value = ["Version 1", "Version 2"]
    item.GetCurrentVersion.return_value = {
        "versionName": "Version 1",
        "versionType": 0,
    }
    item.GetNumNodes.return_value = 2
    item.GetNodeLabel.side_effect = lambda i: f"Node {i}"
    item.GetNodeGraph.return_value = MagicMock()
    return item


def _make_resolve(
    *,
    page: str = "edit",
    keyframe_mode: int = 0,
    with_timeline: bool = True,
    with_clips: bool = False,
) -> MagicMock:
    resolve = MagicMock()
    resolve.GetVersionString.return_value = "20.3.2.9"
    resolve.GetVersion.return_value = [20, 3, 2, 9, ""]
    resolve.GetCurrentPage.return_value = page
    resolve.GetKeyframeMode.return_value = keyframe_mode
    resolve.OpenPage.return_value = True
    resolve.SetKeyframeMode.return_value = True

    pm = MagicMock()
    project = MagicMock()
    project.GetName.return_value = "TestProject"
    project.SetName.return_value = True

    timeline = MagicMock()
    timeline.GetName.return_value = "Main Edit"
    timeline.GetSetting.side_effect = lambda k: {
        "timelineFrameRate": "24",
        "timelineResolutionWidth": "1920",
        "timelineResolutionHeight": "1080",
    }.get(k, "")
    timeline.GetStartTimecode.return_value = "00:00:00:00"
    timeline.GetCurrentTimecode.return_value = "01:00:00:00"
    timeline.SetCurrentTimecode.return_value = True
    track_counts = {"video": 2, "audio": 1, "subtitle": 0}
    timeline.GetTrackCount.side_effect = lambda t: track_counts.get(t, 0)
    timeline.GetTrackName.side_effect = lambda t, i: f"{t} {i}"
    timeline.AddTrack.return_value = True
    timeline.DeleteTrack.return_value = True
    timeline.GetIsTrackEnabled.return_value = True
    timeline.SetTrackEnable.return_value = True
    timeline.GetIsTrackLocked.return_value = False
    timeline.SetTrackLock.return_value = True
    timeline.DuplicateTimeline.return_value = MagicMock(
        GetName=MagicMock(return_value="Main Edit copy")
    )
    timeline.DetectSceneCuts.return_value = True
    timeline.CreateSubtitlesFromAudio.return_value = True

    if with_clips:
        clip_item = _make_clip_item()
        timeline.GetItemListInTrack.side_effect = lambda t, i: (
            [clip_item] if t == "video" and i == 1 else []
        )
    else:
        timeline.GetItemListInTrack.return_value = []

    project.GetTimelineCount.return_value = 1
    project.GetTimelineByIndex.side_effect = lambda i: timeline if i == 1 else None
    project.GetCurrentTimeline.return_value = timeline if with_timeline else None
    project.GetMediaPool.return_value = MagicMock()

    # Deliver
    project.GetRenderFormats.return_value = {"mp4": "MP4", "mov": "QuickTime"}
    project.GetRenderCodecs.return_value = {"h264": "H.264", "h265": "H.265"}
    project.DeleteRenderJob.return_value = True
    project.DeleteAllRenderJobs.return_value = True
    project.GetRenderJobStatus.return_value = {
        "JobStatus": "Complete",
        "CompletionPercentage": 100.0,
    }
    project.IsRenderingInProgress.return_value = False
    project.GetRenderJobList.return_value = []

    # Gallery
    gallery = MagicMock()
    album = MagicMock()
    album.GetStills.return_value = [MagicMock(), MagicMock()]
    gallery.GetGalleryStillAlbums.return_value = [album]
    gallery.GetAlbumName.return_value = "Album 1"
    gallery.GetCurrentStillAlbum.return_value = album
    project.GetGallery.return_value = gallery

    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


def _make_media_resolve() -> MagicMock:
    """media コマンド用の Resolve モック。"""
    resolve = _make_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()

    media_pool = MagicMock()
    folder = MagicMock()
    clip = MagicMock()
    clip.GetName.return_value = "clip1.mov"
    clip.GetMetadata.side_effect = lambda *args: (
        args[0] if len(args) == 1 and isinstance(args[0], str)
        else {"Description": "test", "Comments": "none"}
    )
    folder.GetClipList.return_value = [clip]
    media_pool.GetCurrentFolder.return_value = folder
    media_pool.GetRootFolder.return_value = folder
    folder.GetSubFolderList.return_value = []
    project.GetMediaPool.return_value = media_pool
    return resolve


# ===========================================================================
# 1. TestE2ESystemPage
# ===========================================================================


class TestE2ESystemPage:
    def test_page_get(self):
        resolve = _make_resolve(page="color")
        with patch(SYSTEM_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["system", "page", "get"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["page"] == "color"

    def test_page_set_dry_run(self):
        result = CliRunner().invoke(
            dr, ["system", "page", "set", "edit", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["page"] == "edit"


# ===========================================================================
# 2. TestE2ESystemKeyframeMode
# ===========================================================================


class TestE2ESystemKeyframeMode:
    def test_keyframe_mode_get(self):
        resolve = _make_resolve(keyframe_mode=1)
        with patch(SYSTEM_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["system", "keyframe-mode", "get"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["mode"] == 1
        assert data["label"] == "color"

    def test_keyframe_mode_set_dry_run(self):
        result = CliRunner().invoke(
            dr, ["system", "keyframe-mode", "set", "2", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["mode"] == 2


# ===========================================================================
# 3. TestE2EProjectRename
# ===========================================================================


class TestE2EProjectRename:
    def test_rename_dry_run(self):
        result = CliRunner().invoke(
            dr, ["project", "rename", "NewName", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["name"] == "NewName"

    def test_rename(self):
        resolve = _make_resolve()
        with patch(PROJECT_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["project", "rename", "Renamed"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["renamed"] is True
        assert data["name"] == "Renamed"


# ===========================================================================
# 4. TestE2ETimelineTimecode
# ===========================================================================


class TestE2ETimelineTimecode:
    def test_timecode_get(self):
        resolve = _make_resolve()
        with patch(TIMELINE_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["timeline", "timecode", "get"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["timecode"] == "01:00:00:00"

    def test_timecode_set_dry_run(self):
        result = CliRunner().invoke(
            dr, ["timeline", "timecode", "set", "01:00:05:00", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["timecode"] == "01:00:05:00"


# ===========================================================================
# 5. TestE2ETimelineTrack
# ===========================================================================


class TestE2ETimelineTrack:
    def test_track_list(self):
        resolve = _make_resolve()
        with patch(TIMELINE_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["timeline", "track", "list"])
        assert result.exit_code == 0
        # NDJSON output: one JSON per line
        lines = [ln for ln in result.output.strip().splitlines() if ln.strip()]
        assert len(lines) == 3  # 2 video + 1 audio

    def test_track_add_dry_run(self):
        result = CliRunner().invoke(
            dr,
            ["timeline", "track", "add", "--track-type", "video", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["track_type"] == "video"

    def test_track_delete_dry_run(self):
        result = CliRunner().invoke(
            dr,
            [
                "timeline",
                "track",
                "delete",
                "--track-type",
                "video",
                "--index",
                "2",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["index"] == 2

    def test_track_enable_get(self):
        resolve = _make_resolve()
        with patch(TIMELINE_PATCH, return_value=resolve):
            result = CliRunner().invoke(
                dr,
                [
                    "timeline",
                    "track",
                    "enable",
                    "--track-type",
                    "video",
                    "--index",
                    "1",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["enabled"] is True

    def test_track_lock_get(self):
        resolve = _make_resolve()
        with patch(TIMELINE_PATCH, return_value=resolve):
            result = CliRunner().invoke(
                dr,
                [
                    "timeline",
                    "track",
                    "lock",
                    "--track-type",
                    "video",
                    "--index",
                    "1",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["locked"] is False


# ===========================================================================
# 6. TestE2ETimelineOps
# ===========================================================================


class TestE2ETimelineOps:
    def test_duplicate_dry_run(self):
        result = CliRunner().invoke(
            dr,
            ["timeline", "duplicate", "--name", "copy", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["name"] == "copy"

    def test_detect_scene_cuts(self):
        resolve = _make_resolve()
        with patch(TIMELINE_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["timeline", "detect-scene-cuts"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["detected"] is True

    def test_create_subtitles(self):
        resolve = _make_resolve()
        with patch(TIMELINE_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["timeline", "create-subtitles"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True


# ===========================================================================
# 7. TestE2EClipAttributes
# ===========================================================================


class TestE2EClipAttributes:
    def test_clip_enable_get(self):
        resolve = _make_resolve(with_clips=True)
        with patch(CLIP_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["clip", "enable", "0"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["enabled"] is True

    def test_clip_color_get(self):
        resolve = _make_resolve(with_clips=True)
        with patch(CLIP_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["clip", "color", "get", "0"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["color"] == "Orange"

    def test_clip_color_set(self):
        resolve = _make_resolve(with_clips=True)
        clip_item = (
            resolve.GetProjectManager()
            .GetCurrentProject()
            .GetCurrentTimeline()
            .GetItemListInTrack("video", 1)[0]
        )
        clip_item.SetClipColor.return_value = True
        with patch(CLIP_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["clip", "color", "set", "0", "Blue"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["set"] is True
        assert data["color"] == "Blue"

    def test_clip_flag_list(self):
        resolve = _make_resolve(with_clips=True)
        with patch(CLIP_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["clip", "flag", "list", "0"])
        assert result.exit_code == 0
        # NDJSON output: one JSON string per line
        lines = [ln.strip() for ln in result.output.strip().splitlines() if ln.strip()]
        values = [json.loads(ln) for ln in lines]
        assert "Blue" in values
        assert "Red" in values

    def test_clip_flag_add(self):
        resolve = _make_resolve(with_clips=True)
        clip_item = (
            resolve.GetProjectManager()
            .GetCurrentProject()
            .GetCurrentTimeline()
            .GetItemListInTrack("video", 1)[0]
        )
        clip_item.AddFlag.return_value = True
        with patch(CLIP_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["clip", "flag", "add", "0", "Green"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True


# ===========================================================================
# 8. TestE2EColorVersion
# ===========================================================================


class TestE2EColorVersion:
    def test_version_list(self):
        resolve = _make_resolve(with_clips=True)
        with patch(COLOR_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["color", "version", "list", "0"])
        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().splitlines() if ln.strip()]
        assert len(lines) == 2

    def test_version_current(self):
        resolve = _make_resolve(with_clips=True)
        with patch(COLOR_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["color", "version", "current", "0"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["versionName"] == "Version 1"

    def test_version_add_dry_run(self):
        result = CliRunner().invoke(
            dr,
            ["color", "version", "add", "0", "NewVersion", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["name"] == "NewVersion"

    def test_version_load_dry_run(self):
        result = CliRunner().invoke(
            dr,
            ["color", "version", "load", "0", "Version 1", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "version_load"

    def test_version_delete_dry_run(self):
        result = CliRunner().invoke(
            dr,
            ["color", "version", "delete", "0", "OldVersion", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "version_delete"

    def test_version_rename_dry_run(self):
        result = CliRunner().invoke(
            dr,
            [
                "color",
                "version",
                "rename",
                "0",
                "OldName",
                "NewName",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "version_rename"


# ===========================================================================
# 9. TestE2EColorOps
# ===========================================================================


class TestE2EColorOps:
    def test_copy_grade_dry_run(self):
        result = CliRunner().invoke(
            dr,
            ["color", "copy-grade", "--from", "0", "--to", "1", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "copy_grade"

    def test_reset_all_dry_run(self):
        result = CliRunner().invoke(
            dr, ["color", "reset-all", "0", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "reset_all"

    def test_cdl_set_dry_run(self):
        result = CliRunner().invoke(
            dr,
            [
                "color",
                "cdl",
                "0",
                "--node-index",
                "1",
                "--slope",
                "0.5 0.4 0.2",
                "--offset",
                "0.4 0.3 0.2",
                "--power",
                "0.6 0.7 0.8",
                "--saturation",
                "0.65",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "cdl_set"

    def test_lut_export_dry_run(self):
        result = CliRunner().invoke(
            dr,
            [
                "color",
                "lut-export",
                "0",
                "--export-type",
                "0",
                "--path",
                "/tmp/test.cube",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "lut_export"


# ===========================================================================
# 10. TestE2ENodeOps
# ===========================================================================


class TestE2ENodeOps:
    def test_node_lut_get(self):
        resolve = _make_resolve(with_clips=True)
        graph = (
            resolve.GetProjectManager()
            .GetCurrentProject()
            .GetCurrentTimeline()
            .GetItemListInTrack("video", 1)[0]
            .GetNodeGraph()
        )
        graph.GetLUT.return_value = "/path/to/lut.cube"
        with patch(COLOR_PATCH, return_value=resolve):
            result = CliRunner().invoke(
                dr, ["color", "node", "lut", "get", "0", "1"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["lut_path"] == "/path/to/lut.cube"

    def test_node_enable_dry_run(self):
        result = CliRunner().invoke(
            dr,
            ["color", "node", "enable", "0", "1", "True", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "node_enable"
        assert data["enabled"] is True


# ===========================================================================
# 11. TestE2EDeliverExtended
# ===========================================================================


class TestE2EDeliverExtended:
    def test_delete_job_dry_run(self):
        result = CliRunner().invoke(
            dr, ["deliver", "delete-job", "abc-123", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["job_id"] == "abc-123"

    def test_delete_all_jobs_dry_run(self):
        result = CliRunner().invoke(
            dr, ["deliver", "delete-all-jobs", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "delete_all_jobs"

    def test_format_list(self):
        resolve = _make_resolve()
        with patch(DELIVER_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["deliver", "format", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "formats" in data
        assert "mp4" in data["formats"]

    def test_codec_list(self):
        resolve = _make_resolve()
        with patch(DELIVER_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["deliver", "codec", "list", "mp4"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["format"] == "mp4"
        assert "codecs" in data

    def test_preset_import_dry_run(self):
        # preset import requires file to exist for non-dry-run,
        # but dry_run check happens after validate_path + exists check
        # so we patch Path.exists
        with patch("davinci_cli.commands.deliver.validate_path") as mock_vp:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda self: "/tmp/preset.drx"
            mock_vp.return_value = mock_path
            result = CliRunner().invoke(
                dr,
                ["deliver", "preset", "import", "/tmp/preset.drx", "--dry-run"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "preset_import"

    def test_preset_export_dry_run(self):
        result = CliRunner().invoke(
            dr,
            [
                "deliver",
                "preset",
                "export",
                "MyPreset",
                "/tmp/export.drx",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "preset_export"
        assert data["name"] == "MyPreset"


# ===========================================================================
# 12. TestE2EGallery
# ===========================================================================


class TestE2EGallery:
    def test_album_list(self):
        resolve = _make_resolve()
        with patch(GALLERY_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["gallery", "album", "list"])
        assert result.exit_code == 0

    def test_album_current(self):
        resolve = _make_resolve()
        with patch(GALLERY_PATCH, return_value=resolve):
            result = CliRunner().invoke(dr, ["gallery", "album", "current"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Album 1"

    def test_album_set_dry_run(self):
        result = CliRunner().invoke(
            dr, ["gallery", "album", "set", "Album 2", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "album_set"

    def test_album_create_dry_run(self):
        result = CliRunner().invoke(
            dr, ["gallery", "album", "create", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "album_create"

    def test_still_export_dry_run(self):
        result = CliRunner().invoke(
            dr, ["gallery", "still", "export", "/tmp/stills", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "still_export"

    def test_still_import_dry_run(self):
        with patch("davinci_cli.commands.gallery.validate_path") as mock_vp:
            mock_path = MagicMock()
            mock_path.__str__ = lambda self: "/tmp/still.dpx"
            mock_vp.return_value = mock_path
            result = CliRunner().invoke(
                dr,
                ["gallery", "still", "import", "/tmp/still.dpx", "--dry-run"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "still_import"

    def test_still_delete_dry_run(self):
        result = CliRunner().invoke(
            dr, ["gallery", "still", "delete", "0", "1", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "still_delete"
        assert data["still_indices"] == [0, 1]


# ===========================================================================
# 13. TestE2EMediaExtended
# ===========================================================================


class TestE2EMediaExtended:
    def test_move_dry_run(self):
        result = CliRunner().invoke(
            dr,
            [
                "media",
                "move",
                "clip1.mov",
                "--target",
                "FolderA",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "media_move"

    def test_delete_dry_run(self):
        result = CliRunner().invoke(
            dr, ["media", "delete", "clip1.mov", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "media_delete"

    def test_relink_dry_run(self):
        result = CliRunner().invoke(
            dr,
            [
                "media",
                "relink",
                "clip1.mov",
                "--folder-path",
                "/new/path",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "media_relink"

    def test_metadata_get(self):
        resolve = _make_media_resolve()
        with patch(MEDIA_PATCH, return_value=resolve):
            result = CliRunner().invoke(
                dr,
                ["media", "metadata", "get", "clip1.mov", "--key", "Description"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["key"] == "Description"

    def test_metadata_set_dry_run(self):
        result = CliRunner().invoke(
            dr,
            [
                "media",
                "metadata",
                "set",
                "clip1.mov",
                "--key",
                "Description",
                "--value",
                "Updated",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "media_metadata_set"

    def test_export_metadata_dry_run(self):
        result = CliRunner().invoke(
            dr,
            ["media", "export-metadata", "/tmp/metadata.csv", "--dry-run"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "media_export_metadata"
