import importlib
import sys


def test_davinci_cli_importable():
    """パッケージがインポート可能であること"""
    mod = importlib.import_module("davinci_cli")
    assert mod is not None


def test_cli_entry_point_exists():
    """CLIエントリポイント（dr コマンド）が定義されていること"""
    from davinci_cli.cli import dr
    assert callable(dr)


def test_package_version_defined():
    """バージョンが定義されていること"""
    import davinci_cli
    assert hasattr(davinci_cli, "__version__")
    assert isinstance(davinci_cli.__version__, str)
