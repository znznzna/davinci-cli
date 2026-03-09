import json

from click.testing import CliRunner

from davinci_cli.cli import dr
from davinci_cli.core.exceptions import (
    DavinciEnvironmentError,
    EditionError,
    ProjectNotOpenError,
    ResolveNotRunningError,
    ValidationError,
)


class TestDrCommand:
    def test_dr_help(self):
        result = CliRunner().invoke(dr, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_dr_version(self):
        result = CliRunner().invoke(dr, ["--version"])
        assert result.exit_code == 0
        from davinci_cli import __version__

        assert __version__ in result.output

    def test_dr_has_verbose_flag(self):
        result = CliRunner().invoke(dr, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_dr_has_debug_flag(self):
        result = CliRunner().invoke(dr, ["--debug", "--help"])
        assert result.exit_code == 0


class TestDavinciCLIGroup:
    """invoke オーバーライドによるグローバルエラーハンドリングのテスト"""

    def test_resolve_not_running_exits_1(self):
        @dr.command(name="_test_resolve_err")
        def _test_cmd():
            raise ResolveNotRunningError()

        result = CliRunner().invoke(dr, ["_test_resolve_err"])
        assert result.exit_code == 1
        assert "DaVinci Resolve" in result.output

    def test_project_not_open_exits_2(self):
        @dr.command(name="_test_project_err")
        def _test_cmd():
            raise ProjectNotOpenError()

        result = CliRunner().invoke(dr, ["_test_project_err"])
        assert result.exit_code == 2

    def test_validation_error_exits_3(self):
        @dr.command(name="_test_validation_err")
        def _test_cmd():
            raise ValidationError(field="name", reason="too long")

        result = CliRunner().invoke(dr, ["_test_validation_err"])
        assert result.exit_code == 3

    def test_environment_error_exits_4(self):
        @dr.command(name="_test_env_err")
        def _test_cmd():
            raise DavinciEnvironmentError(detail="missing var")

        result = CliRunner().invoke(dr, ["_test_env_err"])
        assert result.exit_code == 4

    def test_edition_error_exits_5(self):
        @dr.command(name="_test_edition_err")
        def _test_cmd():
            raise EditionError(required="Studio", actual="Free")

        result = CliRunner().invoke(dr, ["_test_edition_err"])
        assert result.exit_code == 5

    def test_error_output_is_json(self):
        @dr.command(name="_test_json_err")
        def _test_cmd():
            raise ResolveNotRunningError()

        result = CliRunner().invoke(dr, ["_test_json_err"])
        parsed = json.loads(result.output)
        assert "error" in parsed
        assert "exit_code" in parsed

    def test_generic_exception_fallback(self):
        @dr.command(name="_test_generic_err")
        def _test_cmd():
            raise FileNotFoundError("File not found: /missing/file.mp4")

        result = CliRunner().invoke(dr, ["_test_generic_err"])
        assert result.exit_code == 1
        parsed = json.loads(result.output)
        assert "error" in parsed
        assert parsed["error_type"] == "FileNotFoundError"

    def test_generic_exception_no_traceback(self):
        @dr.command(name="_test_no_tb_err")
        def _test_cmd():
            raise RuntimeError("unexpected")

        result = CliRunner().invoke(dr, ["_test_no_tb_err"])
        assert "Traceback" not in result.output

    def test_click_usage_error_not_swallowed(self):
        """Click の UsageError は JSON エラーではなく通常の Click エラー表示"""
        result = CliRunner().invoke(dr, ["nosuch_command_xyz"])
        assert result.exit_code == 2


class TestSubcommandRegistration:
    def test_system_registered(self):
        assert "system" in [cmd for cmd in dr.commands]

    def test_schema_registered(self):
        assert "schema" in [cmd for cmd in dr.commands]
