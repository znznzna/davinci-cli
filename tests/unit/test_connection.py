import pytest
from unittest.mock import patch, MagicMock

from davinci_cli.core.connection import get_resolve, clear_resolve_cache
from davinci_cli.core.exceptions import ResolveNotRunningError, DavinciEnvironmentError


class TestGetResolve:
    def setup_method(self):
        """各テスト前にキャッシュをクリア"""
        clear_resolve_cache()

    def test_returns_resolve_object_when_running(self):
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            return_value=mock_dvr,
        ):
            result = get_resolve()

        assert result is mock_resolve
        mock_dvr.scriptapp.assert_called_once_with("Resolve")

    def test_raises_when_resolve_not_running(self):
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = None

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            return_value=mock_dvr,
        ):
            with pytest.raises(ResolveNotRunningError):
                get_resolve()

    def test_caches_resolve_object(self):
        """Resolve オブジェクト自体もキャッシュされ、2回目の呼び出しで scriptapp() が呼ばれないこと"""
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            return_value=mock_dvr,
        ):
            result1 = get_resolve()
            result2 = get_resolve()

        assert result1 is result2
        # scriptapp は1回しか呼ばれない（Resolve オブジェクト自体がキャッシュされている）
        assert mock_dvr.scriptapp.call_count == 1

    def test_clear_cache_clears_both_module_and_resolve(self):
        """clear_resolve_cache() で DaVinciResolveScript モジュールと Resolve オブジェクト両方のキャッシュをクリアする"""
        mock_resolve = MagicMock(name="MockResolve")
        mock_dvr = MagicMock()
        mock_dvr.scriptapp.return_value = mock_resolve

        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            return_value=mock_dvr,
        ):
            get_resolve()
            clear_resolve_cache()
            get_resolve()

        # キャッシュクリア後は scriptapp が再度呼ばれる
        assert mock_dvr.scriptapp.call_count == 2

    def test_import_error_propagates_as_environment_error(self):
        with patch(
            "davinci_cli.core.connection._import_resolve_script",
            side_effect=ImportError("No module named 'DaVinciResolveScript'"),
        ):
            with pytest.raises(DavinciEnvironmentError, match="DaVinciResolveScript"):
                get_resolve()
