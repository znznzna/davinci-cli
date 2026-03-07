"""E2E スモークテスト — MockResolve で全コマンドグループの疎通確認。

パッチパスは davinci_cli.core.connection.get_resolve を使用する。
"""
import asyncio
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from tests.e2e.mock_resolve import build_mock_resolve

RESOLVE_PATCH = "davinci_cli.core.connection.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = build_mock_resolve()
    with patch(RESOLVE_PATCH, return_value=resolve):
        yield resolve


@pytest.fixture
def runner():
    return CliRunner()


class TestSystemSmoke:
    def test_ping(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "ping"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_version(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "version"])
        assert result.exit_code == 0

    def test_info(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "info"])
        assert result.exit_code == 0


class TestProjectSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["project", "list", "--fields", "name"])
        assert result.exit_code == 0

    def test_open_dry_run(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["project", "open", "Demo Project", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_info(self, runner, mock_resolve):
        result = runner.invoke(dr, ["project", "info", "--fields", "name"])
        assert result.exit_code == 0


class TestTimelineSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["timeline", "list", "--fields", "name"])
        assert result.exit_code == 0

    def test_current(self, runner, mock_resolve):
        result = runner.invoke(dr, ["timeline", "current"])
        assert result.exit_code == 0

    def test_switch_dry_run(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["timeline", "switch", "Main Edit", "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestClipSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["clip", "list", "--fields", "index,name"])
        assert result.exit_code == 0

    def test_property_set_dry_run(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["clip", "property", "set", "0", "Pan", "0.5", "--dry-run"]
        )
        assert result.exit_code == 0


class TestColorSmoke:
    def test_apply_lut_dry_run(self, runner, mock_resolve, tmp_path):
        lut_file = tmp_path / "test.cube"
        lut_file.touch()
        result = runner.invoke(
            dr, ["color", "apply-lut", "0", str(lut_file), "--dry-run"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_reset_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["color", "reset", "0", "--dry-run"])
        assert result.exit_code == 0


class TestMediaSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["media", "list", "--fields", "clip_name"]
        )
        assert result.exit_code == 0

    def test_folder_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["media", "folder", "list"])
        assert result.exit_code == 0

    def test_folder_delete_dry_run(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["media", "folder", "delete", "OldFolder", "--dry-run"]
        )
        assert result.exit_code == 0


class TestDeliverSmoke:
    def test_preset_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "preset", "list"])
        assert result.exit_code == 0

    def test_list_jobs(self, runner, mock_resolve):
        result = runner.invoke(
            dr, ["deliver", "list-jobs", "--fields", "job_id,status"]
        )
        assert result.exit_code == 0

    def test_start_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "start", "--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["would_render"] is True
        assert "jobs" in data
        assert "estimated_seconds" in data

    def test_status(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "status"])
        assert result.exit_code == 0


class TestSchemaSmoke:
    def test_schema_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["schema", "list"])
        assert result.exit_code == 0

    def test_schema_show_project_open(self, runner, mock_resolve):
        result = runner.invoke(dr, ["schema", "show", "project.open"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "input_schema" in data


class TestMCPSmoke:
    def test_mcp_server_importable(self):
        from davinci_cli.mcp.mcp_server import mcp
        assert mcp is not None

    def test_mcp_has_deliver_start_tool(self):
        from davinci_cli.mcp.mcp_server import mcp
        tools = asyncio.run(mcp.list_tools())
        tool_names = [t.name for t in tools]
        assert "deliver_start" in tool_names
