"""MCP サーバー管理コマンド (install / uninstall / status / test)。

Claude Desktop / Cowork の設定ファイルに dr-mcp を登録・管理する。
lightroom-cli の lr mcp コマンドと同等の UX を提供する。
"""

from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path
from typing import Any

import click

from davinci_cli.output.formatter import output


def _get_claude_config_path() -> Path:
    """Claude Desktop / Cowork 設定ファイルのパスを返す。"""
    system = platform.system()
    config_name = "claude_desktop_config.json"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / config_name
    elif system == "Windows":
        appdata = Path.home() / "AppData" / "Roaming"
        return appdata / "Claude" / config_name
    else:
        return Path.home() / ".config" / "Claude" / config_name


def _read_config(config_path: Path) -> dict[str, Any]:
    """設定ファイルを読み込む。存在しない場合は空 dict。"""
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _write_config(config_path: Path, config: dict[str, Any]) -> None:
    """設定ファイルを書き込む。親ディレクトリも作成。"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _build_mcp_server_entry() -> dict[str, Any]:
    """MCP サーバーエントリを生成する。"""
    dr_mcp_path = shutil.which("dr-mcp")
    if dr_mcp_path is None:
        raise click.ClickException(
            "dr-mcp command not found in PATH. "
            "Ensure davinci-cli is installed: pip install davinci-cli"
        )
    return {"command": dr_mcp_path, "args": []}


SERVER_KEY = "davinci-cli"


# --- _impl functions ---


def install_impl(force: bool = False) -> dict[str, Any]:
    """Claude Desktop 設定に dr-mcp を登録する。"""
    config_path = _get_claude_config_path()
    config = _read_config(config_path)

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    if SERVER_KEY in config["mcpServers"] and not force:
        return {
            "installed": False,
            "reason": "already_installed",
            "config_path": str(config_path),
            "hint": "Use --force to overwrite the existing entry.",
        }

    entry = _build_mcp_server_entry()
    config["mcpServers"][SERVER_KEY] = entry
    _write_config(config_path, config)

    return {
        "installed": True,
        "config_path": str(config_path),
        "command": entry["command"],
    }


def uninstall_impl() -> dict[str, Any]:
    """Claude Desktop 設定から dr-mcp を削除する。"""
    config_path = _get_claude_config_path()
    config = _read_config(config_path)

    servers = config.get("mcpServers", {})
    if SERVER_KEY not in servers:
        return {
            "uninstalled": False,
            "reason": "not_installed",
            "config_path": str(config_path),
        }

    del servers[SERVER_KEY]
    _write_config(config_path, config)

    return {
        "uninstalled": True,
        "config_path": str(config_path),
    }


def status_impl() -> dict[str, Any]:
    """MCP サーバーの登録状態を返す。"""
    config_path = _get_claude_config_path()
    config = _read_config(config_path)

    servers = config.get("mcpServers", {})
    if SERVER_KEY in servers:
        entry = servers[SERVER_KEY]
        return {
            "status": "installed",
            "config_path": str(config_path),
            "command": entry.get("command", "N/A"),
        }

    return {
        "status": "not_installed",
        "config_path": str(config_path),
    }


def test_impl() -> dict[str, Any]:
    """Resolve API 接続テスト（ping_impl を再利用）。"""
    from davinci_cli.commands.system import ping_impl as _ping_impl

    return _ping_impl()


# --- Click commands ---


@click.group()
def mcp() -> None:
    """MCP server management."""


@mcp.command()
@click.option("--force", is_flag=True, help="Overwrite existing MCP server entry")
@click.pass_context
def install(ctx: click.Context, force: bool) -> None:
    """Install MCP server into Claude Desktop / Cowork config."""
    result = install_impl(force=force)
    output(result, pretty=ctx.obj.get("pretty"))

    if result.get("installed"):
        click.echo("Restart Claude Desktop / Cowork to activate.", err=True)


@mcp.command()
@click.pass_context
def uninstall(ctx: click.Context) -> None:
    """Remove MCP server from Claude Desktop / Cowork config."""
    result = uninstall_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@mcp.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show MCP server installation status."""
    result = status_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@mcp.command()
@click.pass_context
def test(ctx: click.Context) -> None:
    """Test connection to DaVinci Resolve."""
    result = test_impl()
    output(result, pretty=ctx.obj.get("pretty"))
