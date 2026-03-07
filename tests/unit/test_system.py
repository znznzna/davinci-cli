import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.system import edition_impl, info_impl, ping_impl, version_impl
from davinci_cli.core.exceptions import ResolveNotRunningError

RESOLVE_PATCH = "davinci_cli.commands.system.get_resolve"


@pytest.fixture
def mock_resolve():
    resolve = MagicMock()
    resolve.GetVersionString.return_value = "20.3.2.9"
    resolve.GetVersion.return_value = [20, 3, 2, 9, "Studio"]
    pm = MagicMock()
    project = MagicMock()
    project.GetName.return_value = "TestProject"
    pm.GetCurrentProject.return_value = project
    resolve.GetProjectManager.return_value = pm
    return resolve


class TestPingImpl:
    def test_returns_ok_when_running(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = ping_impl()
        assert result == {"status": "ok", "version": "20.3.2.9"}

    def test_raises_when_not_running(self):
        with (
            patch(RESOLVE_PATCH, side_effect=ResolveNotRunningError()),
            pytest.raises(ResolveNotRunningError),
        ):
            ping_impl()


class TestVersionImpl:
    def test_returns_version_and_edition(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = version_impl()
        assert "version" in result
        assert result["edition"] == "Studio"


class TestEditionImpl:
    def test_returns_edition(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = edition_impl()
        assert result["edition"] == "Studio"


class TestInfoImpl:
    def test_returns_comprehensive_info(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = info_impl()
        assert "version" in result
        assert "edition" in result
        assert result["current_project"] == "TestProject"

    def test_no_project_open(self, mock_resolve):
        mock_resolve.GetProjectManager().GetCurrentProject.return_value = None
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = info_impl()
        assert result["current_project"] is None


class TestSystemCLI:
    def test_dr_system_ping(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["system", "ping"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_dr_system_version(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["system", "version"])
        assert result.exit_code == 0

    def test_dr_system_info(self, mock_resolve):
        with patch(RESOLVE_PATCH, return_value=mock_resolve):
            result = CliRunner().invoke(dr, ["system", "info"])
        assert result.exit_code == 0
