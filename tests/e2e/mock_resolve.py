from unittest.mock import MagicMock


def build_mock_resolve():
    """E2Eテスト用の完全なResolveモック。"""
    resolve = MagicMock()
    resolve.GetVersionString.return_value = "19.0.0"
    resolve.GetProductName.return_value = "DaVinci Resolve Studio"
    resolve.GetVersion.return_value = {
        "product": "DaVinci Resolve Studio",
        "major": 19,
        "minor": 0,
    }

    pm = MagicMock()
    resolve.GetProjectManager.return_value = pm

    project = MagicMock()
    pm.GetCurrentProject.return_value = project
    pm.GetProjectListInCurrentFolder.return_value = ["Demo Project", "Test Project"]
    pm.LoadProject.return_value = project
    project.GetName.return_value = "Demo Project"
    project.GetTimelineCount.return_value = 2
    project.GetSetting.return_value = "24"
    project.GetRenderPresets.return_value = ["H.264 Master", "YouTube 1080p"]
    project.LoadRenderPreset.return_value = True
    project.GetRenderJobList.return_value = [
        {
            "JobId": "job-001",
            "TimelineName": "Edit",
            "JobStatus": "Queued",
            "CompletionPercentage": 0,
        }
    ]
    project.AddRenderJob.return_value = "job-002"
    pm.SaveProject.return_value = True

    timeline = MagicMock()
    project.GetCurrentTimeline.return_value = timeline
    project.GetTimelineByIndex.return_value = timeline
    timeline.GetName.return_value = "Main Edit"
    timeline.GetSetting.return_value = "24"
    timeline.GetStartTimecode.return_value = "00:00:00:00"
    timeline.GetTrackCount.return_value = 1
    timeline.GetMarkers.return_value = {}

    clip = MagicMock()
    clip.GetName.return_value = "A001_C001.mov"
    clip.GetStart.return_value = 0
    clip.GetEnd.return_value = 240
    clip.GetDuration.return_value = 240
    clip.GetProperty.return_value = "0.0"
    clip.GetNumNodes.return_value = 3
    clip.GetNodeLabel.return_value = ""
    clip.GetClipProperty.side_effect = lambda k: {
        "File Path": "/media/clip1.mov",
        "Duration": "00:00:10:00",
        "FPS": "24.0",
    }.get(k, "")
    timeline.GetItemListInTrack.return_value = [clip]

    media_pool = MagicMock()
    project.GetMediaPool.return_value = media_pool
    root_folder = MagicMock()
    root_folder.GetClipList.return_value = [clip]
    root_folder.GetSubFolderList.return_value = []
    media_pool.GetRootFolder.return_value = root_folder
    media_pool.ImportMedia.return_value = [clip]

    gallery = MagicMock()
    project.GetGallery.return_value = gallery
    album = MagicMock()
    gallery.GetCurrentStillAlbum.return_value = album
    album.GetStills.return_value = []

    return resolve
