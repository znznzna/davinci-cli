import asyncio
import inspect

from davinci_cli.mcp.mcp_server import mcp, mcp_error_handler


def _list_tools():
    return asyncio.run(mcp.list_tools())


def _get_tool_names():
    return [t.name for t in _list_tools()]


# All expected tool names in the MCP server
EXPECTED_TOOLS = [
    # system (8)
    "system_ping",
    "system_version",
    "system_edition",
    "system_info",
    "system_page_get",
    "system_page_set",
    "system_keyframe_mode_get",
    "system_keyframe_mode_set",
    # project (11)
    "project_list",
    "project_open",
    "project_close",
    "project_create",
    "project_delete",
    "project_rename",
    "project_save",
    "project_info",
    "project_settings_get",
    "project_settings_set",
    # timeline (20)
    "timeline_list",
    "timeline_current",
    "timeline_switch",
    "timeline_create",
    "timeline_delete",
    "timeline_timecode_get",
    "timeline_timecode_set",
    "timeline_current_item",
    "timeline_track_list",
    "timeline_track_add",
    "timeline_track_delete",
    "timeline_track_enable",
    "timeline_track_lock",
    "timeline_duplicate",
    "timeline_detect_scene_cuts",
    "timeline_create_subtitles",
    "timeline_export",
    "timeline_marker_list",
    "timeline_marker_add",
    "timeline_marker_delete",
    # clip (13)
    "clip_list",
    "clip_info",
    "clip_select",
    "clip_property_get",
    "clip_property_set",
    "clip_enable",
    "clip_color_get",
    "clip_color_set",
    "clip_color_clear",
    "clip_flag_add",
    "clip_flag_list",
    "clip_flag_clear",
    # color (16)
    "color_apply_lut",
    "color_reset",
    "color_copy_grade",
    "color_version_list",
    "color_version_current",
    "color_version_add",
    "color_version_load",
    "color_version_delete",
    "color_version_rename",
    "color_node_lut_set",
    "color_node_lut_get",
    "color_node_enable",
    "color_cdl_set",
    "color_lut_export",
    "color_reset_all",
    "color_still_grab",
    "color_still_list",
    # media (13)
    "media_list",
    "media_import",
    "media_move",
    "media_delete",
    "media_relink",
    "media_unlink",
    "media_metadata_get",
    "media_metadata_set",
    "media_export_metadata",
    "media_transcribe",
    "media_folder_list",
    "media_folder_create",
    "media_folder_delete",
    # deliver (15)
    "deliver_preset_list",
    "deliver_preset_load",
    "deliver_add_job",
    "deliver_list_jobs",
    "deliver_start",
    "deliver_stop",
    "deliver_status",
    "deliver_delete_job",
    "deliver_delete_all_jobs",
    "deliver_job_status",
    "deliver_is_rendering",
    "deliver_format_list",
    "deliver_codec_list",
    "deliver_preset_import",
    "deliver_preset_export",
    # gallery (7)
    "gallery_album_list",
    "gallery_album_current",
    "gallery_album_set",
    "gallery_album_create",
    "gallery_still_export",
    "gallery_still_import",
    "gallery_still_delete",
]


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

    def test_all_expected_tools_registered(self):
        """全ツールが登録されていることを確認する。"""
        tool_names = _get_tool_names()
        missing = [name for name in EXPECTED_TOOLS if name not in tool_names]
        assert missing == [], f"Missing tools: {missing}"

    def test_no_unexpected_tools(self):
        """想定外のツールが登録されていないことを確認する。"""
        tool_names = _get_tool_names()
        unexpected = [name for name in tool_names if name not in EXPECTED_TOOLS]
        assert unexpected == [], f"Unexpected tools: {unexpected}"

    def test_total_tool_count(self):
        """ツール総数が一致することを確認する。"""
        tool_names = _get_tool_names()
        assert len(tool_names) == len(EXPECTED_TOOLS)


class TestMCPNewToolsRegistered:
    """新規追加ツールが正しく登録されていることを確認する。"""

    def test_system_new_tools(self):
        tool_names = _get_tool_names()
        assert "system_page_get" in tool_names
        assert "system_page_set" in tool_names
        assert "system_keyframe_mode_get" in tool_names
        assert "system_keyframe_mode_set" in tool_names

    def test_project_rename(self):
        tool_names = _get_tool_names()
        assert "project_rename" in tool_names

    def test_timeline_new_tools(self):
        tool_names = _get_tool_names()
        for name in [
            "timeline_timecode_get",
            "timeline_timecode_set",
            "timeline_current_item",
            "timeline_track_list",
            "timeline_track_add",
            "timeline_track_delete",
            "timeline_track_enable",
            "timeline_track_lock",
            "timeline_duplicate",
            "timeline_detect_scene_cuts",
            "timeline_create_subtitles",
        ]:
            assert name in tool_names, f"{name} not found"

    def test_clip_new_tools(self):
        tool_names = _get_tool_names()
        for name in [
            "clip_enable",
            "clip_color_get",
            "clip_color_set",
            "clip_color_clear",
            "clip_flag_add",
            "clip_flag_list",
            "clip_flag_clear",
        ]:
            assert name in tool_names, f"{name} not found"

    def test_color_new_tools(self):
        tool_names = _get_tool_names()
        for name in [
            "color_copy_grade",
            "color_version_list",
            "color_version_current",
            "color_version_add",
            "color_version_load",
            "color_version_delete",
            "color_version_rename",
            "color_node_lut_set",
            "color_node_lut_get",
            "color_node_enable",
            "color_cdl_set",
            "color_lut_export",
            "color_reset_all",
            "color_still_grab",
            "color_still_list",
        ]:
            assert name in tool_names, f"{name} not found"

    def test_deliver_new_tools(self):
        tool_names = _get_tool_names()
        for name in [
            "deliver_delete_job",
            "deliver_delete_all_jobs",
            "deliver_job_status",
            "deliver_is_rendering",
            "deliver_format_list",
            "deliver_codec_list",
            "deliver_preset_import",
            "deliver_preset_export",
        ]:
            assert name in tool_names, f"{name} not found"

    def test_gallery_tools(self):
        tool_names = _get_tool_names()
        for name in [
            "gallery_album_list",
            "gallery_album_current",
            "gallery_album_set",
            "gallery_album_create",
            "gallery_still_export",
            "gallery_still_import",
            "gallery_still_delete",
        ]:
            assert name in tool_names, f"{name} not found"

    def test_media_new_tools(self):
        tool_names = _get_tool_names()
        for name in [
            "media_move",
            "media_delete",
            "media_relink",
            "media_unlink",
            "media_metadata_get",
            "media_metadata_set",
            "media_export_metadata",
            "media_transcribe",
        ]:
            assert name in tool_names, f"{name} not found"


class TestMCPParityTools:
    """CLI↔MCP パリティ修正で追加されたツールのテスト。"""

    def test_project_settings_tools(self):
        tool_names = _get_tool_names()
        assert "project_settings_get" in tool_names
        assert "project_settings_set" in tool_names

    def test_timeline_export_tool(self):
        tool_names = _get_tool_names()
        assert "timeline_export" in tool_names

    def test_timeline_marker_tools(self):
        tool_names = _get_tool_names()
        assert "timeline_marker_list" in tool_names
        assert "timeline_marker_add" in tool_names
        assert "timeline_marker_delete" in tool_names

    def test_clip_property_get_tool(self):
        tool_names = _get_tool_names()
        assert "clip_property_get" in tool_names

    def test_media_folder_tools(self):
        tool_names = _get_tool_names()
        assert "media_folder_list" in tool_names
        assert "media_folder_create" in tool_names
        assert "media_folder_delete" in tool_names

    def test_parity_tools_dry_run_defaults(self):
        """パリティ修正ツールのdry_runデフォルトがTrueであることを確認する。"""
        dry_run_tools = [
            "project_settings_set",
            "timeline_export",
            "timeline_marker_add",
            "timeline_marker_delete",
            "media_folder_delete",
        ]
        tools = _list_tools()
        for name in dry_run_tools:
            tool = next(t for t in tools if t.name == name)
            sig = inspect.signature(tool.fn)
            assert sig.parameters["dry_run"].default is True, (
                f"{name} dry_run default is not True"
            )


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

    def test_new_destructive_tools_default_dry_run_true(self):
        """新規追加の破壊的操作ツールがdry_run=Trueデフォルトであることを確認する。"""
        dry_run_tools = [
            "system_page_set",
            "system_keyframe_mode_set",
            "project_rename",
            "timeline_timecode_set",
            "timeline_track_add",
            "timeline_track_delete",
            "timeline_duplicate",
            "color_copy_grade",
            "color_version_add",
            "color_version_load",
            "color_version_delete",
            "color_version_rename",
            "color_node_lut_set",
            "color_node_enable",
            "color_cdl_set",
            "color_lut_export",
            "color_reset_all",
            "color_still_grab",
            "media_move",
            "media_delete",
            "media_relink",
            "media_metadata_set",
            "media_export_metadata",
            "deliver_delete_job",
            "deliver_delete_all_jobs",
            "deliver_preset_import",
            "deliver_preset_export",
            "gallery_album_set",
            "gallery_album_create",
            "gallery_still_export",
            "gallery_still_import",
            "gallery_still_delete",
            "project_settings_set",
            "timeline_export",
            "timeline_marker_add",
            "timeline_marker_delete",
            "media_folder_delete",
        ]
        for name in dry_run_tools:
            fn = self._get_tool_fn(name)
            sig = inspect.signature(fn)
            assert sig.parameters["dry_run"].default is True, (
                f"{name} dry_run default is not True"
            )


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

    def test_all_tools_have_agent_rules(self):
        """全ツールがAGENT RULESを含むことを確認する。"""
        tools = _list_tools()
        for tool in tools:
            desc = tool.description or ""
            assert "AGENT RULES" in desc, (
                f"{tool.name} missing AGENT RULES in description"
            )


class TestMCPInstructions:
    def test_mcp_has_instructions(self):
        """MCP サーバーに instructions が設定されていることを確認する。"""
        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0

    def test_instructions_contains_key_sections(self):
        """instructions に必須セクションが含まれていることを確認する。"""
        instructions = mcp.instructions
        assert "Getting Started" in instructions
        assert "Safety Rules" in instructions
        assert "Error Recovery" in instructions
        assert "Key Workflows" in instructions
        assert "Tips" in instructions

    def test_instructions_mentions_system_ping(self):
        """instructions が system_ping を最初のステップとして言及していることを確認する。"""
        assert "system_ping" in mcp.instructions


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
