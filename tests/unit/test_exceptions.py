import pytest
from davinci_cli.core.exceptions import (
    DavinciCLIError,
    ResolveNotRunningError,
    ProjectNotOpenError,
    ProjectNotFoundError,
    ValidationError,
    DavinciEnvironmentError,
    EditionError,
)


def test_base_exception_hierarchy():
    """全例外が DavinciCLIError を継承していること"""
    for exc_class in [
        ResolveNotRunningError,
        ProjectNotOpenError,
        ProjectNotFoundError,
        ValidationError,
        DavinciEnvironmentError,
        EditionError,
    ]:
        assert issubclass(exc_class, DavinciCLIError)


def test_base_exception_does_not_shadow_builtin():
    """DavinciEnvironmentError は Python 組み込みの EnvironmentError と衝突しないこと"""
    assert DavinciEnvironmentError is not EnvironmentError
    # 組み込み EnvironmentError は OSError のエイリアス
    assert not issubclass(DavinciEnvironmentError, OSError)


def test_resolve_not_running_error():
    exc = ResolveNotRunningError()
    assert exc.exit_code == 1
    assert "DaVinci Resolve" in str(exc)


def test_project_not_open_error():
    exc = ProjectNotOpenError()
    assert exc.exit_code == 2


def test_project_not_found_error():
    exc = ProjectNotFoundError(name="MyProject")
    assert exc.exit_code == 2
    assert "MyProject" in str(exc)


def test_validation_error_captures_field():
    exc = ValidationError(field="path", reason="path traversal detected")
    assert exc.field == "path"
    assert "path traversal" in str(exc)
    assert exc.exit_code == 3


def test_environment_error_has_exit_code():
    exc = DavinciEnvironmentError(detail="RESOLVE_SCRIPT_API not found")
    assert exc.exit_code == 4
    assert "RESOLVE_SCRIPT_API" in str(exc)


def test_edition_error_has_exit_code():
    exc = EditionError(required="Studio", actual="Free")
    assert exc.exit_code == 5
    assert "Studio" in str(exc)


def test_exceptions_are_catchable_as_base():
    with pytest.raises(DavinciCLIError):
        raise ResolveNotRunningError()


def test_exit_code_uniqueness():
    """各例外の exit_code が一意であること（ProjectNotFoundError は ProjectNotOpenError と同じ 2 で許容）"""
    codes = {
        ResolveNotRunningError: 1,
        ProjectNotOpenError: 2,
        ValidationError: 3,
        DavinciEnvironmentError: 4,
        EditionError: 5,
    }
    for exc_class, expected_code in codes.items():
        assert exc_class.exit_code == expected_code
