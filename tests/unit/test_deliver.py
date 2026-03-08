import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.deliver import (
    deliver_add_job_impl,
    deliver_codec_list_impl,
    deliver_delete_all_jobs_impl,
    deliver_delete_job_impl,
    deliver_format_list_impl,
    deliver_is_rendering_impl,
    deliver_job_status_impl,
    deliver_list_jobs_impl,
    deliver_preset_export_impl,
    deliver_preset_import_impl,
    deliver_preset_list_impl,
    deliver_preset_load_impl,
    deliver_start_impl,
    deliver_status_impl,
)
from davinci_cli.core.exceptions import ValidationError

RESOLVE_PATCH = "davinci_cli.commands.deliver.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()
    project.GetRenderPresetList.return_value = ["H.264 Master", "YouTube 1080p"]
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
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestDeliverPresetImpl:
    def test_list_presets(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_preset_list_impl()
        assert len(result) == 2
        assert result[0]["name"] == "H.264 Master"

    def test_list_presets_calls_get_render_preset_list(self, mock_resolve):
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.GetRenderPresetList.return_value = ["H.264 Master", "YouTube 1080p"]
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_preset_list_impl()
        assert len(result) == 2
        assert result[0]["name"] == "H.264 Master"
        project.GetRenderPresetList.assert_called_once()

    def test_load_not_found(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().LoadRenderPreset.return_value = (
            False
        )
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError, match="not found"),
        ):
            deliver_preset_load_impl(name="NonExistent")


class TestDeliverJobImpl:
    def test_add_job_dry_run(self):
        result = deliver_add_job_impl(
            job_data={"output_dir": "/tmp", "filename": "output"},
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert result["action"] == "add_job"

    def test_add_job_missing_output_dir(self):
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            deliver_add_job_impl(job_data={"filename": "output"})

    def test_list_jobs(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_list_jobs_impl()
        assert len(result) == 1

    def test_list_jobs_fields(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_list_jobs_impl(fields=["job_id", "status"])
        assert all(set(r.keys()) == {"job_id", "status"} for r in result)


class TestDeliverStartImpl:
    def test_start_dry_run_returns_plan(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_start_impl(dry_run=True)
        assert result["would_render"] is True
        assert isinstance(result["jobs"], list)
        assert "estimated_seconds" in result

    def test_start_dry_run_with_job_ids(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_start_impl(job_ids=["job-001"], dry_run=True)
        assert result["would_render"] is True
        assert len(result["jobs"]) == 1


class TestDeliverExtendedImpl:
    def test_delete_job_dry_run(self):
        result = deliver_delete_job_impl(job_id="job-001", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "delete_job"
        assert result["job_id"] == "job-001"

    def test_delete_job(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().DeleteRenderJob.return_value = True
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_delete_job_impl(job_id="job-001")
        assert result["deleted"] is True
        assert result["job_id"] == "job-001"

    def test_delete_all_jobs_dry_run(self):
        result = deliver_delete_all_jobs_impl(dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "delete_all_jobs"

    def test_delete_all_jobs(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().DeleteAllRenderJobs.return_value = True
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_delete_all_jobs_impl()
        assert result["deleted_all"] is True

    def test_job_status(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().GetRenderJobStatus.return_value = {
            "JobStatus": "Complete",
            "CompletionPercentage": 100,
        }
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_job_status_impl(job_id="job-001")
        assert result["job_id"] == "job-001"
        assert result["status"] == "Complete"
        assert result["percent"] == 100

    def test_job_status_normalized_keys(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().GetRenderJobStatus.return_value = {
            "JobStatus": "Rendering",
            "CompletionPercentage": 75,
            "EstimatedTimeRemainingInMs": 60000,
        }
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_job_status_impl(job_id="job-001")
        assert result["job_id"] == "job-001"
        assert result["status"] == "Rendering"
        assert result["percent"] == 75
        assert result["eta"] == 60
        # PascalCase キーが存在しないことを確認
        assert "JobStatus" not in result
        assert "CompletionPercentage" not in result
        assert "EstimatedTimeRemainingInMs" not in result

    def test_is_rendering(self, mock_resolve):
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.IsRenderingInProgress.return_value = True
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_is_rendering_impl()
        assert result["rendering"] is True


class TestDeliverCLI:
    def test_deliver_start_dry_run(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["deliver", "start", "--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["would_render"] is True

    def test_deliver_add_job_json(self):
        result = CliRunner().invoke(
            dr,
            [
                "deliver",
                "add-job",
                "--json",
                '{"output_dir": "/tmp", "filename": "output"}',
                "--dry-run",
            ],
        )
        assert result.exit_code == 0

    def test_deliver_preset_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["deliver", "preset", "list"])
        assert result.exit_code == 0


class TestDeliverStatusImpl:
    def test_status_calls_get_render_job_status_per_job(self, mock_resolve):
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.GetRenderJobList.return_value = [
            {"JobId": "job-001"},
            {"JobId": "job-002"},
        ]

        def mock_job_status(job_id):
            statuses = {
                "job-001": {"JobStatus": "Complete", "CompletionPercentage": 100, "EstimatedTimeRemainingInMs": 0},
                "job-002": {"JobStatus": "Rendering", "CompletionPercentage": 50, "EstimatedTimeRemainingInMs": 30000},
            }
            return statuses.get(job_id, {})

        project.GetRenderJobStatus.side_effect = mock_job_status
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_status_impl()
        assert len(result["jobs"]) == 2
        assert result["jobs"][0]["job_id"] == "job-001"
        assert result["jobs"][0]["status"] == "Complete"
        assert result["jobs"][0]["percent"] == 100
        assert result["jobs"][0]["eta"] == 0
        assert result["jobs"][1]["status"] == "Rendering"
        assert result["jobs"][1]["percent"] == 50
        assert result["jobs"][1]["eta"] == 30
        assert project.GetRenderJobStatus.call_count == 2

    def test_status_empty_job_list(self, mock_resolve):
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.GetRenderJobList.return_value = []
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_status_impl()
        assert result == {"jobs": []}


class TestDeliverFormatsImpl:
    def test_format_list(self, mock_resolve):
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.GetRenderFormats.return_value = {
            "QuickTime": ".mov",
            "MP4": ".mp4",
        }
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_format_list_impl()
        assert result == {"formats": {"QuickTime": ".mov", "MP4": ".mp4"}}

    def test_codec_list(self, mock_resolve):
        project = mock_resolve.GetProjectManager().GetCurrentProject()
        project.GetRenderCodecs.return_value = {
            "Apple ProRes 422 HQ": "ap4h",
        }
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_codec_list_impl(format_name="QuickTime")
        assert result["format"] == "QuickTime"
        assert result["codecs"] == {"Apple ProRes 422 HQ": "ap4h"}
        project.GetRenderCodecs.assert_called_once_with("QuickTime")

    def test_preset_import_dry_run(self, tmp_path):
        preset_file = tmp_path / "my_preset.xml"
        preset_file.write_text("<preset/>")
        result = deliver_preset_import_impl(path=str(preset_file), dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "preset_import"

    def test_preset_import(self, mock_resolve, tmp_path):
        preset_file = tmp_path / "my_preset.xml"
        preset_file.write_text("<preset/>")
        mock_resolve.ImportRenderPreset.return_value = True
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_preset_import_impl(path=str(preset_file))
        assert result["imported"] is True
        mock_resolve.ImportRenderPreset.assert_called_once_with(
            str(preset_file.resolve())
        )

    def test_preset_import_file_not_found(self):
        with pytest.raises(ValidationError, match="not found"):
            deliver_preset_import_impl(path="/nonexistent/preset.xml")

    def test_preset_export_dry_run(self, tmp_path):
        export_path = str(tmp_path / "exported.xml")
        result = deliver_preset_export_impl(
            name="MyPreset", path=export_path, dry_run=True
        )
        assert result["dry_run"] is True
        assert result["action"] == "preset_export"
        assert result["name"] == "MyPreset"

    def test_preset_export(self, mock_resolve, tmp_path):
        export_path = str(tmp_path / "exported.xml")
        mock_resolve.ExportRenderPreset.return_value = True
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_preset_export_impl(name="MyPreset", path=export_path)
        assert result["exported"] is True
        assert result["name"] == "MyPreset"
        mock_resolve.ExportRenderPreset.assert_called_once()
