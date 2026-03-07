import os
import sys
from unittest.mock import patch

import pytest

from davinci_cli.core.environment import (
    PLATFORM_MACOS,
    PLATFORM_WINDOWS,
    get_default_paths,
    setup_environment,
)
from davinci_cli.core.exceptions import DavinciEnvironmentError


class TestGetDefaultPaths:
    def test_macos_paths(self):
        paths = get_default_paths(PLATFORM_MACOS)
        assert paths["RESOLVE_SCRIPT_API"].startswith("/Library/Application Support")
        assert paths["RESOLVE_SCRIPT_LIB"].startswith("/Applications")
        assert paths["RESOLVE_MODULES"].startswith("/Library/Application Support")

    def test_windows_paths(self):
        paths = get_default_paths(PLATFORM_WINDOWS)
        assert "ProgramData" in paths["RESOLVE_SCRIPT_API"]
        assert "Program Files" in paths["RESOLVE_SCRIPT_LIB"]
        assert "Modules" in paths["RESOLVE_MODULES"]

    def test_linux_raises_with_clear_message(self):
        """Linux は明示的にサポートしない"""
        with pytest.raises(DavinciEnvironmentError, match="not supported") as exc_info:
            get_default_paths("linux")
        assert "linux" in str(exc_info.value).lower()

    def test_unknown_platform_raises(self):
        with pytest.raises(DavinciEnvironmentError, match="not supported"):
            get_default_paths("freebsd")


class TestSetupEnvironment:
    def test_env_vars_set_from_defaults_on_macos(self, monkeypatch):
        monkeypatch.delenv("RESOLVE_SCRIPT_API", raising=False)
        monkeypatch.delenv("RESOLVE_SCRIPT_LIB", raising=False)
        monkeypatch.delenv("RESOLVE_MODULES", raising=False)

        with patch(
            "davinci_cli.core.environment._current_platform",
            return_value=PLATFORM_MACOS,
        ):
            setup_environment()

        assert "RESOLVE_SCRIPT_API" in os.environ
        assert os.environ["RESOLVE_SCRIPT_API"].startswith("/Library")

    def test_existing_env_vars_not_overwritten(self, monkeypatch):
        monkeypatch.setenv("RESOLVE_SCRIPT_API", "/custom/path")

        with patch(
            "davinci_cli.core.environment._current_platform",
            return_value=PLATFORM_MACOS,
        ):
            setup_environment()

        assert os.environ["RESOLVE_SCRIPT_API"] == "/custom/path"

    def test_modules_added_to_sys_path(self, monkeypatch):
        monkeypatch.delenv("RESOLVE_MODULES", raising=False)

        with patch(
            "davinci_cli.core.environment._current_platform",
            return_value=PLATFORM_MACOS,
        ):
            setup_environment()

        modules_path = os.environ["RESOLVE_MODULES"]
        assert modules_path in sys.path

    def test_manual_env_skips_platform_check(self, monkeypatch):
        """全環境変数が手動設定済みの場合、プラットフォームチェックをスキップする（Linux対応）"""
        monkeypatch.setenv("RESOLVE_SCRIPT_API", "/opt/resolve/scripting")
        monkeypatch.setenv("RESOLVE_SCRIPT_LIB", "/opt/resolve/libs")
        monkeypatch.setenv("RESOLVE_MODULES", "/opt/resolve/modules")

        with patch(
            "davinci_cli.core.environment._current_platform",
            return_value="linux",
        ):
            setup_environment()  # DavinciEnvironmentError が発生しないこと

        assert os.environ["RESOLVE_SCRIPT_API"] == "/opt/resolve/scripting"
        assert "/opt/resolve/modules" in sys.path
