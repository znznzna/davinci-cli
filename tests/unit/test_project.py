import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.project import (
    project_close_impl,
    project_create_impl,
    project_delete_impl,
    project_info_impl,
    project_list_impl,
    project_open_impl,
    project_rename_impl,
)
from davinci_cli.core.exceptions import ProjectNotFoundError, ValidationError

RESOLVE_PATCH = "davinci_cli.commands.project.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    pm = MagicMock()
    project = MagicMock()
    project.GetName.return_value = "TestProject"
    project.GetTimelineCount.return_value = 3
    project.GetSetting.side_effect = lambda k: {
        "timelineFrameRate": "24",
        "timelineResolutionWidth": "1920",
        "timelineResolutionHeight": "1080",
    }.get(k, "")
    pm.GetCurrentProject.return_value = project
    pm.GetProjectListInCurrentFolder.return_value = ["TestProject", "Demo"]
    pm.LoadProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestProjectListImpl:
    def test_returns_list_of_projects(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_list_impl()
        assert len(result) == 2
        assert result[0]["name"] == "TestProject"

    def test_fields_filter(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_list_impl(fields=["name"])
        assert all("name" in p for p in result)


class TestProjectOpenImpl:
    def test_dry_run(self):
        result = project_open_impl(name="MyProject", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "open"
        assert result["name"] == "MyProject"

    def test_open_existing_project(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_open_impl(name="TestProject")
        assert result["opened"] == "TestProject"

    def test_open_not_found_raises_project_not_found(self, mock_resolve):
        mock_resolve.GetProjectManager().LoadProject.return_value = None
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ProjectNotFoundError, match="NonExistent"),
        ):
            project_open_impl(name="NonExistent")


class TestProjectCloseImpl:
    def test_dry_run(self):
        result = project_close_impl(dry_run=True)
        assert result["dry_run"] is True

    def test_close_project(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_close_impl()
        assert result["closed"] is True


class TestProjectCreateImpl:
    def test_dry_run(self):
        result = project_create_impl(name="NewProject", dry_run=True)
        assert result["dry_run"] is True
        assert result["name"] == "NewProject"


class TestProjectDeleteImpl:
    def test_dry_run(self):
        result = project_delete_impl(name="OldProject", dry_run=True)
        assert result["dry_run"] is True
        assert result["action"] == "delete"


class TestProjectInfoImpl:
    def test_returns_project_info(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_info_impl()
        assert result["name"] == "TestProject"
        assert result["timeline_count"] == 3

    def test_fields_filter(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_info_impl(fields=["name"])
        assert "name" in result
        assert "fps" not in result


class TestProjectRenameImpl:
    def test_rename_dry_run(self):
        result = project_rename_impl("NewName", dry_run=True)
        assert result == {"dry_run": True, "action": "rename", "name": "NewName"}

    def test_rename_success(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().SetName.return_value = (
            True
        )
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = project_rename_impl("NewName")
        assert result == {"renamed": True, "name": "NewName"}
        mock_resolve.GetProjectManager().GetCurrentProject().SetName.assert_called_with(
            "NewName"
        )

    def test_rename_failure(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject().SetName.return_value = (
            False
        )
        with (
            patch(RESOLVE_PATCH, return_value=mock_resolve),
            pytest.raises(ValidationError, match="Failed to rename"),
        ):
            project_rename_impl("NewName")

    def test_rename_cli_dry_run(self):
        result = CliRunner().invoke(
            dr, ["project", "rename", "NewName", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "rename"
        assert data["name"] == "NewName"


class TestProjectCLI:
    def test_project_list(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["project", "list"])
        assert result.exit_code == 0

    def test_project_open_dry_run(self):
        result = CliRunner().invoke(
            dr, ["project", "open", "Test", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_project_open_json_input(self):
        result = CliRunner().invoke(
            dr, ["project", "open", "--json", '{"name": "Test"}', "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_project_open_no_name_error(self):
        result = CliRunner().invoke(dr, ["project", "open"])
        assert result.exit_code != 0

    def test_project_info_with_fields(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(
                dr, ["project", "info", "--fields", "name"]
            )
        assert result.exit_code == 0
