import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.deliver import (
    deliver_add_job_impl,
    deliver_delete_all_jobs_impl,
    deliver_delete_job_impl,
    deliver_is_rendering_impl,
    deliver_job_status_impl,
    deliver_list_jobs_impl,
    deliver_preset_list_impl,
    deliver_preset_load_impl,
    deliver_start_impl,
)
from davinci_cli.core.exceptions import ValidationError

RESOLVE_PATCH = "davinci_cli.commands.deliver.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()
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
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestDeliverPresetImpl:
    def test_list_presets(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = deliver_preset_list_impl()
        assert len(result) == 2
        assert result[0]["name"] == "H.264 Master"

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
        assert result["JobStatus"] == "Complete"
        assert result["CompletionPercentage"] == 100

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
