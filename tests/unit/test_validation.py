import pytest
from pathlib import Path
from davinci_cli.core.validation import validate_path, validate_resource_id, validate_string
from davinci_cli.core.exceptions import ValidationError


# --- validate_path ---

class TestValidatePath:
    def test_valid_path_returns_resolved_path(self, tmp_path):
        """正常系：存在するパスは Path.resolve() された Path オブジェクトを返す"""
        test_file = tmp_path / "test.drp"
        test_file.touch()
        result = validate_path(str(test_file))
        assert isinstance(result, Path)
        assert result == test_file.resolve()

    def test_valid_path_string_returns_resolved_path(self):
        """存在しないパスでも resolve() は動作する"""
        result = validate_path("/some/valid/path.drp")
        assert isinstance(result, Path)

    def test_path_traversal_single_dot_dot(self):
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("../secret")

    def test_path_traversal_encoded(self):
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("..%2Fsecret")

    def test_path_traversal_double_encoded(self):
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("%2e%2e%2fsecret")

    def test_path_traversal_mixed(self):
        with pytest.raises(ValidationError, match="path traversal"):
            validate_path("foo/../../etc/passwd")

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_path("")

    def test_none_rejected(self):
        with pytest.raises(ValidationError):
            validate_path(None)  # type: ignore

    def test_allowed_extensions_pass(self):
        """許可された拡張子は通過する"""
        result = validate_path("/path/to/lut.cube", allowed_extensions=[".cube", ".3dl", ".lut"])
        assert result.suffix == ".cube"

    def test_allowed_extensions_rejected(self):
        """許可されていない拡張子は拒絶する"""
        with pytest.raises(ValidationError, match="not allowed"):
            validate_path("/path/to/malicious.exe", allowed_extensions=[".cube", ".3dl", ".lut"])

    def test_allowed_extensions_case_insensitive(self):
        """拡張子チェックは大文字小文字を区別しない"""
        result = validate_path("/path/to/lut.CUBE", allowed_extensions=[".cube"])
        assert result.suffix == ".CUBE"

    def test_allowed_extensions_none_skips_check(self):
        """allowed_extensions=None の場合は拡張子チェックをスキップする"""
        result = validate_path("/path/to/anything.xyz")
        assert result.suffix == ".xyz"

    def test_symlink_resolved(self, tmp_path):
        """シンボリックリンクは resolve() で実体パスに解決される"""
        real_file = tmp_path / "real.drp"
        real_file.touch()
        symlink = tmp_path / "link.drp"
        symlink.symlink_to(real_file)
        result = validate_path(str(symlink))
        assert result == real_file.resolve()


# --- validate_resource_id ---

class TestValidateResourceId:
    def test_valid_id_passes(self):
        assert validate_resource_id("proj-abc123") == "proj-abc123"

    def test_query_param_injection(self):
        with pytest.raises(ValidationError, match="invalid character"):
            validate_resource_id("proj?admin=true")

    def test_fragment_injection(self):
        with pytest.raises(ValidationError, match="invalid character"):
            validate_resource_id("proj#fragment")

    def test_percent_encoding_injection(self):
        with pytest.raises(ValidationError, match="invalid character"):
            validate_resource_id("proj%20id")

    def test_empty_id_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_resource_id("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            validate_resource_id("   ")


# --- validate_string ---

class TestValidateString:
    def test_valid_string_passes(self):
        assert validate_string("Hello, World!") == "Hello, World!"

    def test_null_byte_rejected(self):
        with pytest.raises(ValidationError, match="control character"):
            validate_string("hello\x00world")

    def test_control_character_rejected(self):
        with pytest.raises(ValidationError, match="control character"):
            validate_string("hello\x1fworld")

    def test_tab_allowed(self):
        assert validate_string("hello\tworld") == "hello\tworld"

    def test_newline_allowed(self):
        assert validate_string("hello\nworld") == "hello\nworld"

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_string("")
