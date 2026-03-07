"""実機スモークテスト — DaVinci Resolve 起動中に実行する。

使い方:
  1. DaVinci Resolve を起動する
  2. python tests/smoke_test_real.py を実行する

このファイルは CI では実行しない（tests/unit/ 配下ではない）。
"""

from __future__ import annotations

import sys
from pathlib import Path


def test_default_paths_exist():
    """macOS デフォルトパスが実在するか確認"""
    from davinci_cli.core.environment import PLATFORM_MACOS, get_default_paths

    if sys.platform != "darwin":
        print("SKIP: macOS 以外では実行しない")
        return

    paths = get_default_paths(PLATFORM_MACOS)
    for key, path in paths.items():
        exists = Path(path).exists()
        status = "OK" if exists else "MISSING"
        print(f"  {key}: {path} [{status}]")
        if not exists:
            print(
                f"    WARNING: {key} が存在しません。"
                "DaVinci Resolve がインストールされているか確認してください。"
            )


def test_connection():
    """DaVinci Resolve に接続できるか確認"""
    from davinci_cli.core.connection import clear_resolve_cache, get_resolve

    clear_resolve_cache()
    try:
        resolve = get_resolve()
        print(f"  接続成功: {resolve}")
        return resolve
    except Exception as e:
        print(f"  接続失敗: {e}")
        return None


def test_get_version(resolve):
    """GetVersion() の実際の戻り値を確認（モックとの整合性検証）"""
    raw = resolve.GetVersion()
    print(f"  GetVersion() 型: {type(raw).__name__}")
    print(f"  GetVersion() 値: {raw}")

    # モックとの整合性チェック
    if isinstance(raw, list):
        print(f"  -> list で返却: OK（モックと整合、要素数={len(raw)}）")
        if len(raw) >= 5:
            print(f"  -> エディション suffix: '{raw[4]}'")
    elif isinstance(raw, dict):
        print("  -> dict で返却（19.x 互換形式）")
        if "product" in raw:
            print(f"  -> product: {raw['product']}")
    else:
        print(f"  -> WARNING: 予期しない型 {type(raw).__name__} で返却！モック要更新")

    version_str = resolve.GetVersionString()
    print(f"  GetVersionString(): {version_str}")


def test_edition(resolve):
    """エディション判定の実環境確認"""
    from davinci_cli.core.edition import get_edition

    edition = get_edition(resolve)
    print(f"  検出エディション: {edition}")


def test_project_manager(resolve):
    """ProjectManager の基本動作確認"""
    pm = resolve.GetProjectManager()
    print(f"  ProjectManager: {pm}")

    project = pm.GetCurrentProject()
    if project:
        print(f"  現在のプロジェクト: {project.GetName()}")
        print(f"  タイムライン数: {project.GetTimelineCount()}")
    else:
        print("  プロジェクト未オープン（正常）")

    projects = pm.GetProjectListInCurrentFolder()
    print(f"  プロジェクト一覧: {projects}")


def main():
    print("=" * 60)
    print("davinci-cli 実機スモークテスト")
    print("=" * 60)

    print("\n[1] デフォルトパスの存在確認")
    test_default_paths_exist()

    print("\n[2] DaVinci Resolve 接続テスト")
    resolve = test_connection()

    if resolve is None:
        print("\n接続できなかったため、以降のテストをスキップします。")
        print("DaVinci Resolve を起動してから再実行してください。")
        sys.exit(1)

    print("\n[3] GetVersion() 実値確認")
    test_get_version(resolve)

    print("\n[4] エディション判定")
    test_edition(resolve)

    print("\n[5] ProjectManager 基本動作")
    test_project_manager(resolve)

    print("\n" + "=" * 60)
    print("スモークテスト完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
