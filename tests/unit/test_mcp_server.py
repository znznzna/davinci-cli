import asyncio
import inspect

from davinci_cli.mcp.mcp_server import mcp, mcp_error_handler


def _list_tools():
    return asyncio.run(mcp.list_tools())


def _get_tool_names():
    return [t.name for t in _list_tools()]


class TestMCPServerSetup:
    def test_mcp_server_instantiated(self):
        assert mcp is not None
        assert mcp.name == "davinci-cli"

    def test_mcp_tools_registered(self):
        tool_names = _get_tool_names()
        assert "system_ping" in tool_names
        assert "project_list" in tool_names
        assert "project_open" in tool_names
        assert "deliver_start" in tool_names
        assert "color_apply_lut" in tool_names
        assert "media_list" in tool_names


class TestMCPDryRunDefaults:
    def _get_tool_fn(self, name: str):
        tools = _list_tools()
        tool = next(t for t in tools if t.name == name)
        return tool.fn

    def test_project_open_default_dry_run_true(self):
        fn = self._get_tool_fn("project_open")
        sig = inspect.signature(fn)
        assert sig.parameters["dry_run"].default is True

    def test_deliver_start_default_dry_run_true(self):
        fn = self._get_tool_fn("deliver_start")
        sig = inspect.signature(fn)
        assert sig.parameters["dry_run"].default is True

    def test_deliver_add_job_default_dry_run_true(self):
        fn = self._get_tool_fn("deliver_add_job")
        sig = inspect.signature(fn)
        assert sig.parameters["dry_run"].default is True


class TestMCPDescriptions:
    def _get_tool_desc(self, name: str) -> str:
        tools = _list_tools()
        tool = next(t for t in tools if t.name == name)
        return tool.description or ""

    def test_deliver_start_has_agent_rules(self):
        desc = self._get_tool_desc("deliver_start")
        assert "AGENT RULES" in desc
        assert "dry_run=True" in desc

    def test_project_list_has_fields_rule(self):
        desc = self._get_tool_desc("project_list")
        assert "fields" in desc
        assert "AGENT RULES" in desc

    def test_color_apply_lut_has_path_warning(self):
        desc = self._get_tool_desc("color_apply_lut")
        assert ".." in desc


class TestMCPErrorHandler:
    def test_error_handler_returns_structured_error(self):
        from davinci_cli.core.exceptions import ResolveNotRunningError

        @mcp_error_handler
        def failing_fn():
            raise ResolveNotRunningError()

        result = failing_fn()
        assert result["error"] is True
        assert "DaVinci Resolve" in result["message"]
        assert result["error_type"] == "ResolveNotRunningError"
        assert result["exit_code"] == 1

    def test_error_handler_passes_through_on_success(self):
        @mcp_error_handler
        def success_fn():
            return {"status": "ok"}

        result = success_fn()
        assert result == {"status": "ok"}
