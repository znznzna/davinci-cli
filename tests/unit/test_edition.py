from unittest.mock import MagicMock

import pytest

from davinci_cli.core.edition import (
    EDITION_FREE,
    EDITION_STUDIO,
    get_edition,
    require_studio,
)
from davinci_cli.core.exceptions import EditionError


class TestGetEdition:
    # --- dict 形式 (19.x 互換) ---

    def test_detects_studio_from_dict(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "DaVinci Resolve Studio"}
        assert get_edition(mock_resolve) == EDITION_STUDIO

    def test_detects_free_from_dict(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "DaVinci Resolve"}
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_unknown_product_treated_as_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "Unknown"}
        mock_resolve.GetVersionString.return_value = "20.3.2.9"
        assert get_edition(mock_resolve) == EDITION_FREE

    # --- list 形式 (20.x 実機確認済み) ---

    def test_detects_studio_from_list(self):
        """GetVersion() が list で Studio suffix を含む場合"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = [20, 3, 2, 9, "Studio"]
        assert get_edition(mock_resolve) == EDITION_STUDIO

    def test_detects_free_from_list(self):
        """GetVersion() が list で空 suffix の場合 (実機確認済み形式)"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = [20, 3, 2, 9, ""]
        mock_resolve.GetVersionString.return_value = "20.3.2.9"
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_detects_free_from_list_no_string_elements(self):
        """GetVersion() が数値のみの list の場合"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = [19, 0, 0]
        mock_resolve.GetVersionString.return_value = "19.0.0"
        assert get_edition(mock_resolve) == EDITION_FREE

    # --- GetVersionString フォールバック ---

    def test_detects_studio_from_version_string_fallback(self):
        """GetVersion() で判定できない場合、GetVersionString() で検出"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = None
        mock_resolve.GetVersionString.return_value = "DaVinci Resolve Studio 20.3"
        assert get_edition(mock_resolve) == EDITION_STUDIO

    # --- エッジケース ---

    def test_get_version_returns_none_treated_as_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = None
        mock_resolve.GetVersionString.return_value = "20.3.2.9"
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_get_version_returns_string_treated_as_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = "19.0.0"
        mock_resolve.GetVersionString.return_value = "19.0.0"
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_get_version_string_not_available(self):
        """GetVersionString() が存在しない場合も安全に Free を返す"""
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = None
        mock_resolve.GetVersionString.side_effect = AttributeError
        assert get_edition(mock_resolve) == EDITION_FREE

    def test_edition_is_string_constant(self):
        assert isinstance(EDITION_FREE, str)
        assert isinstance(EDITION_STUDIO, str)


class TestRequireStudio:
    def test_passes_when_studio_dict(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = {"product": "DaVinci Resolve Studio"}
        require_studio(mock_resolve)

    def test_passes_when_studio_list(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = [20, 3, 2, 9, "Studio"]
        require_studio(mock_resolve)

    def test_raises_when_free(self):
        mock_resolve = MagicMock()
        mock_resolve.GetVersion.return_value = [20, 3, 2, 9, ""]
        mock_resolve.GetVersionString.return_value = "20.3.2.9"
        with pytest.raises(EditionError) as exc_info:
            require_studio(mock_resolve)
        assert "Studio" in str(exc_info.value)
        assert "Free" in str(exc_info.value)
