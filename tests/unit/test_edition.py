import pytest
from unittest.mock import MagicMock

from davinci_cli.core.edition import (
    get_edition,
    require_studio,
    EDITION_FREE,
    EDITION_STUDIO,
)
from davinci_cli.core.exceptions import EditionError


class TestGetEdition:
    def test_detects_studio(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {
            "product": "DaVinci Resolve Studio"
        }
        assert get_edition(mock_resolve) == EDITION_STUDIO

    def test_detects_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {
            "product": "DaVinci Resolve"
        }
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_unknown_product_treated_as_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "Unknown"}
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_get_version_returns_none_treated_as_free(self):
        """GetVersion() が None を返すケースのハンドリング"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = None
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_get_version_returns_string_treated_as_free(self):
        """GetVersion() が文字列を返すケースのハンドリング"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = "19.0.0"
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_get_version_returns_list_treated_as_free(self):
        """GetVersion() がリストを返すケースのハンドリング"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = [19, 0, 0]
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_edition_is_string_constant(self):
        assert isinstance(EDITION_FREE, str)
        assert isinstance(EDITION_STUDIO, str)


class TestRequireStudio:
    def test_passes_when_studio(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "DaVinci Resolve Studio"}
        require_studio(mock_resolve)  # 例外が発生しないこと

    def test_raises_when_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "DaVinci Resolve"}
        with pytest.raises(EditionError) as exc_info:
            require_studio(mock_resolve)
        assert "Studio" in str(exc_info.value)
        assert "Free" in str(exc_info.value)
