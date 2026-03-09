"""Tests for dr mcp install/uninstall/status/test commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.commands.mcp_cmd import (
    SERVER_KEY,
    install_impl,
    status_impl,
    uninstall_impl,
)
from davinci_cli.commands.mcp_cmd import (
    test_impl as mcp_test_impl,
)


class TestInstallImpl:
    def test_install_creates_entry(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        with (
            patch(
                "davinci_cli.commands.mcp_cmd._get_claude_config_path",
                return_value=config_path,
            ),
            patch(
                "davinci_cli.commands.mcp_cmd.shutil.which",
                return_value="/usr/local/bin/dr-mcp",
            ),
        ):
            result = install_impl()

        assert result["installed"] is True
        assert result["command"] == "/usr/local/bin/dr-mcp"

        config = json.loads(config_path.read_text())
        assert SERVER_KEY in config["mcpServers"]
        assert config["mcpServers"][SERVER_KEY]["command"] == "/usr/local/bin/dr-mcp"
        assert config["mcpServers"][SERVER_KEY]["args"] == []

    def test_install_preserves_existing_servers(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {"other-server": {"command": "/usr/bin/other", "args": []}}}
        config_path.write_text(json.dumps(existing))

        with (
            patch(
                "davinci_cli.commands.mcp_cmd._get_claude_config_path",
                return_value=config_path,
            ),
            patch(
                "davinci_cli.commands.mcp_cmd.shutil.which",
                return_value="/usr/local/bin/dr-mcp",
            ),
        ):
            result = install_impl()

        assert result["installed"] is True
        config = json.loads(config_path.read_text())
        assert "other-server" in config["mcpServers"]
        assert SERVER_KEY in config["mcpServers"]

    def test_install_already_exists_no_force(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {SERVER_KEY: {"command": "/old/path/dr-mcp", "args": []}}}
        config_path.write_text(json.dumps(existing))

        with patch(
            "davinci_cli.commands.mcp_cmd._get_claude_config_path",
            return_value=config_path,
        ):
            result = install_impl(force=False)

        assert result["installed"] is False
        assert result["reason"] == "already_installed"
        # Original entry preserved
        config = json.loads(config_path.read_text())
        assert config["mcpServers"][SERVER_KEY]["command"] == "/old/path/dr-mcp"

    def test_install_force_overwrites(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {SERVER_KEY: {"command": "/old/path/dr-mcp", "args": []}}}
        config_path.write_text(json.dumps(existing))

        with (
            patch(
                "davinci_cli.commands.mcp_cmd._get_claude_config_path",
                return_value=config_path,
            ),
            patch(
                "davinci_cli.commands.mcp_cmd.shutil.which",
                return_value="/new/path/dr-mcp",
            ),
        ):
            result = install_impl(force=True)

        assert result["installed"] is True
        config = json.loads(config_path.read_text())
        assert config["mcpServers"][SERVER_KEY]["command"] == "/new/path/dr-mcp"

    def test_install_creates_parent_dirs(self, tmp_path: Path) -> None:
        config_path = tmp_path / "deep" / "nested" / "claude_desktop_config.json"

        with (
            patch(
                "davinci_cli.commands.mcp_cmd._get_claude_config_path",
                return_value=config_path,
            ),
            patch(
                "davinci_cli.commands.mcp_cmd.shutil.which",
                return_value="/usr/local/bin/dr-mcp",
            ),
        ):
            result = install_impl()

        assert result["installed"] is True
        assert config_path.exists()

    def test_install_dr_mcp_not_found(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        with (
            patch(
                "davinci_cli.commands.mcp_cmd._get_claude_config_path",
                return_value=config_path,
            ),
            patch(
                "davinci_cli.commands.mcp_cmd.shutil.which",
                return_value=None,
            ),
        ):
            import click
            import pytest

            with pytest.raises(click.ClickException, match="dr-mcp"):
                install_impl()


class TestUninstallImpl:
    def test_uninstall_removes_entry(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {
            "mcpServers": {
                SERVER_KEY: {"command": "/usr/local/bin/dr-mcp", "args": []},
                "other": {"command": "/other", "args": []},
            }
        }
        config_path.write_text(json.dumps(existing))

        with patch(
            "davinci_cli.commands.mcp_cmd._get_claude_config_path",
            return_value=config_path,
        ):
            result = uninstall_impl()

        assert result["uninstalled"] is True
        config = json.loads(config_path.read_text())
        assert SERVER_KEY not in config["mcpServers"]
        assert "other" in config["mcpServers"]

    def test_uninstall_not_installed(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text(json.dumps({"mcpServers": {}}))

        with patch(
            "davinci_cli.commands.mcp_cmd._get_claude_config_path",
            return_value=config_path,
        ):
            result = uninstall_impl()

        assert result["uninstalled"] is False
        assert result["reason"] == "not_installed"

    def test_uninstall_no_config_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "nonexistent.json"

        with patch(
            "davinci_cli.commands.mcp_cmd._get_claude_config_path",
            return_value=config_path,
        ):
            result = uninstall_impl()

        assert result["uninstalled"] is False


class TestStatusImpl:
    def test_status_installed(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        existing = {"mcpServers": {SERVER_KEY: {"command": "/usr/local/bin/dr-mcp", "args": []}}}
        config_path.write_text(json.dumps(existing))

        with patch(
            "davinci_cli.commands.mcp_cmd._get_claude_config_path",
            return_value=config_path,
        ):
            result = status_impl()

        assert result["status"] == "installed"
        assert result["command"] == "/usr/local/bin/dr-mcp"

    def test_status_not_installed(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text(json.dumps({}))

        with patch(
            "davinci_cli.commands.mcp_cmd._get_claude_config_path",
            return_value=config_path,
        ):
            result = status_impl()

        assert result["status"] == "not_installed"


class TestTestImpl:
    def test_test_calls_ping_impl(self) -> None:
        with patch(
            "davinci_cli.commands.system.ping_impl",
            return_value={"status": "ok", "version": "20.3.2"},
        ):
            result = mcp_test_impl()

        assert result["status"] == "ok"


class TestMCPCLI:
    def test_mcp_help(self) -> None:
        result = CliRunner().invoke(dr, ["mcp", "--help"])
        # DavinciCLIGroup catches SystemExit from --help, exit_code may be 0 or 1
        assert "install" in result.output
        assert "uninstall" in result.output
        assert "status" in result.output
        assert "test" in result.output

    def test_mcp_install_cli(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        with (
            patch(
                "davinci_cli.commands.mcp_cmd._get_claude_config_path",
                return_value=config_path,
            ),
            patch(
                "davinci_cli.commands.mcp_cmd.shutil.which",
                return_value="/usr/local/bin/dr-mcp",
            ),
        ):
            result = CliRunner().invoke(dr, ["mcp", "install"])

        assert result.exit_code == 0
        # Output contains JSON + restart message (stderr mixed in)
        assert '"installed": true' in result.output
        assert "Restart" in result.output

    def test_mcp_status_cli(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text(json.dumps({}))

        with patch(
            "davinci_cli.commands.mcp_cmd._get_claude_config_path",
            return_value=config_path,
        ):
            result = CliRunner().invoke(dr, ["mcp", "status"])

        assert result.exit_code == 0
        output_data = json.loads(result.output.strip())
        assert output_data["status"] == "not_installed"

    def test_mcp_uninstall_cli(self, tmp_path: Path) -> None:
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text(json.dumps({}))

        with patch(
            "davinci_cli.commands.mcp_cmd._get_claude_config_path",
            return_value=config_path,
        ):
            result = CliRunner().invoke(dr, ["mcp", "uninstall"])

        assert result.exit_code == 0

    def test_mcp_test_cli(self) -> None:
        with patch(
            "davinci_cli.commands.system.ping_impl",
            return_value={"status": "ok", "version": "20.3.2"},
        ):
            result = CliRunner().invoke(dr, ["mcp", "test"])

        assert result.exit_code == 0
        output_data = json.loads(result.output.strip())
        assert output_data["status"] == "ok"
