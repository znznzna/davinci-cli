"""FastMCP サーバー — davinci-cli の全 _impl 関数を MCP tool として公開する。

設計方針:
  - MCP の tool 関数では dry_run=True がデフォルト（CLI側は False）
  - 各 tool の description に AGENT RULES を埋め込む
  - mcp_error_handler で例外をキャッチし、構造化エラーレスポンスを返す
"""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from davinci_cli.commands.clip import (
    clip_info_impl,
    clip_list_impl,
    clip_property_set_impl,
    clip_select_impl,
)
from davinci_cli.commands.color import (
    color_apply_lut_impl,
    color_reset_impl,
)
from davinci_cli.commands.deliver import (
    deliver_add_job_impl,
    deliver_list_jobs_impl,
    deliver_preset_list_impl,
    deliver_preset_load_impl,
    deliver_start_impl,
    deliver_status_impl,
    deliver_stop_impl,
)
from davinci_cli.commands.media import (
    media_import_impl,
    media_list_impl,
)
from davinci_cli.commands.project import (
    project_close_impl,
    project_create_impl,
    project_delete_impl,
    project_info_impl,
    project_list_impl,
    project_open_impl,
    project_save_impl,
)
from davinci_cli.commands.system import (
    edition_impl,
    info_impl,
    ping_impl,
    version_impl,
)
from davinci_cli.commands.timeline import (
    timeline_create_impl,
    timeline_current_impl,
    timeline_delete_impl,
    timeline_list_impl,
    timeline_switch_impl,
)
from davinci_cli.core.exceptions import DavinciCLIError

# --- Error Handler ---


def mcp_error_handler(func: Callable) -> Callable:
    """MCP tool 用エラーハンドリングラッパー。"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except DavinciCLIError as exc:
            return {
                "error": True,
                "message": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": exc.exit_code,
            }
        except Exception as exc:
            return {
                "error": True,
                "message": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": 99,
            }

    return wrapper


# --- MCP Server ---

mcp = FastMCP("davinci-cli")


# ---- system ----


@mcp.tool(
    description="Resolve接続確認を行う。\n"
    "AGENT RULES:\n- 接続確認のみ。引数不要。"
)
@mcp_error_handler
def system_ping() -> dict:
    return ping_impl()


@mcp.tool(
    description="DaVinci Resolveのバージョン情報を返す。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def system_version() -> dict:
    return version_impl()


@mcp.tool(
    description="DaVinci Resolveのエディション（Free/Studio）を返す。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def system_edition() -> dict:
    return edition_impl()


@mcp.tool(
    description="総合情報（バージョン+エディション+現在プロジェクト）を返す。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def system_info() -> dict:
    return info_impl()


# ---- project ----


@mcp.tool(
    description="プロジェクト一覧を返す。\n"
    "AGENT RULES:\n"
    '- 必ずfields引数でフィールドを絞ること（例: fields="name"）\n'
    "- 全フィールド取得はコンテキストウィンドウを消費する"
)
@mcp_error_handler
def project_list(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return project_list_impl(fields=field_list)


@mcp.tool(
    description="プロジェクトを開く。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認し、ユーザーに結果を提示してから実行すること\n"
    "- dry_run=Falseは現在のプロジェクトを閉じる副作用がある"
)
@mcp_error_handler
def project_open(name: str, dry_run: bool = True) -> dict:
    return project_open_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description="現在のプロジェクトを閉じる。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- 未保存の変更は失われる"
)
@mcp_error_handler
def project_close(dry_run: bool = True) -> dict:
    return project_close_impl(dry_run=dry_run)


@mcp.tool(
    description="新規プロジェクトを作成する。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def project_create(name: str, dry_run: bool = True) -> dict:
    return project_create_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description="プロジェクトを削除する（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認し、ユーザーの明示的な承認を得てから実行\n"
    "- 削除したプロジェクトは復元できない"
)
@mcp_error_handler
def project_delete(name: str, dry_run: bool = True) -> dict:
    return project_delete_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description="プロジェクトを保存する。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def project_save() -> dict:
    return project_save_impl()


@mcp.tool(
    description="現在のプロジェクト情報を返す。\n"
    "AGENT RULES:\n- 必ずfields引数でフィールドを絞ること"
)
@mcp_error_handler
def project_info(fields: str | None = None) -> dict:
    field_list = fields.split(",") if fields else None
    return project_info_impl(fields=field_list)


# ---- timeline ----


@mcp.tool(
    description="タイムライン一覧を返す。\n"
    "AGENT RULES:\n- 必ずfields引数でフィールドを絞ること"
)
@mcp_error_handler
def timeline_list(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return timeline_list_impl(fields=field_list)


@mcp.tool(
    description="現在のタイムライン情報を返す。\n"
    "AGENT RULES:\n- 必ずfields引数でフィールドを絞ること"
)
@mcp_error_handler
def timeline_current(fields: str | None = None) -> dict:
    field_list = fields.split(",") if fields else None
    return timeline_current_impl(fields=field_list)


@mcp.tool(
    description="タイムラインを切り替える。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def timeline_switch(name: str, dry_run: bool = True) -> dict:
    return timeline_switch_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description="新規タイムラインを作成する。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def timeline_create(name: str, dry_run: bool = True) -> dict:
    return timeline_create_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description="タイムラインを削除する（破壊的操作）。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def timeline_delete(name: str, dry_run: bool = True) -> dict:
    return timeline_delete_impl(name=name, dry_run=dry_run)


# ---- clip ----


@mcp.tool(
    description="クリップ一覧を返す。\n"
    "AGENT RULES:\n"
    '- 必ずfields引数でフィールドを絞ること（例: fields="index,name"）'
)
@mcp_error_handler
def clip_list(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return clip_list_impl(fields=field_list)


@mcp.tool(
    description="クリップ詳細を返す。\n"
    "AGENT RULES:\n- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_info(index: int) -> dict:
    return clip_info_impl(index=index)


@mcp.tool(
    description="クリップを選択する。\n"
    "AGENT RULES:\n- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_select(index: int) -> dict:
    return clip_select_impl(index=index)


@mcp.tool(
    description="クリップのプロパティを設定する。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def clip_property_set(
    index: int, key: str, value: str, dry_run: bool = True
) -> dict:
    return clip_property_set_impl(
        index=index, key=key, value=value, dry_run=dry_run
    )


# ---- color ----


@mcp.tool(
    description="クリップにLUTを適用する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- lut_pathはシステム上の絶対パス（".."を含むパスは拒絶される）\n'
    "- 許可拡張子: .cube, .3dl, .lut, .mga, .m3d"
)
@mcp_error_handler
def color_apply_lut(
    clip_index: int, lut_path: str, dry_run: bool = True
) -> dict:
    return color_apply_lut_impl(
        clip_index=clip_index, lut_path=lut_path, dry_run=dry_run
    )


@mcp.tool(
    description="グレードをリセットする。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def color_reset(clip_index: int, dry_run: bool = True) -> dict:
    return color_reset_impl(clip_index=clip_index, dry_run=dry_run)


# ---- media ----


@mcp.tool(
    description="メディアプールのクリップ一覧を返す。\n"
    "AGENT RULES:\n"
    '- 必ずfields引数でフィールドを絞ること（例: fields="clip_name,file_path"）\n'
    "- folder引数でフォルダを絞り込むこと"
)
@mcp_error_handler
def media_list(
    folder: str | None = None, fields: str | None = None
) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return media_list_impl(folder_name=folder, fields=field_list)


@mcp.tool(
    description="メディアをインポートする。\n"
    "AGENT RULES:\n"
    "- pathsには絶対パスのリストを渡すこと\n"
    '- ".."を含むパスはセキュリティ上の理由で拒絶される'
)
@mcp_error_handler
def media_import(paths: list[str]) -> dict:
    return media_import_impl(paths=paths)


# ---- deliver ----


@mcp.tool(
    description="レンダープリセット一覧を返す。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def deliver_preset_list() -> list[dict]:
    return deliver_preset_list_impl()


@mcp.tool(
    description="レンダープリセットを読み込む。\n"
    "AGENT RULES:\n- preset listで確認した名前を使うこと"
)
@mcp_error_handler
def deliver_preset_load(name: str) -> dict:
    return deliver_preset_load_impl(name=name)


@mcp.tool(
    description="レンダージョブを追加する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- job_dataはdict: {"output_dir": "...", "filename": "..."}'
)
@mcp_error_handler
def deliver_add_job(job_data: dict, dry_run: bool = True) -> dict:
    return deliver_add_job_impl(job_data=job_data, dry_run=dry_run)


@mcp.tool(
    description="レンダーキューのジョブ一覧を返す。\n"
    "AGENT RULES:\n"
    '- 必ずfields引数でフィールドを絞ること（例: fields="job_id,status"）'
)
@mcp_error_handler
def deliver_list_jobs(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return deliver_list_jobs_impl(fields=field_list)


@mcp.tool(
    description="レンダーを開始する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- ユーザーに確認結果を提示し、明示的な承認を得てからdry_run=Falseで実行\n"
    "- この操作はDaVinci Resolveのエンコードリソースを大量消費する"
)
@mcp_error_handler
def deliver_start(
    job_ids: list[str] | None = None, dry_run: bool = True
) -> dict:
    return deliver_start_impl(job_ids=job_ids, dry_run=dry_run)


@mcp.tool(
    description="レンダーを停止する。\n"
    "AGENT RULES:\n"
    "- 実行中のレンダーを即座に停止する\n"
    "- 途中のファイルは不完全な状態で残る"
)
@mcp_error_handler
def deliver_stop() -> dict:
    return deliver_stop_impl()


@mcp.tool(
    description="レンダー進捗を返す（percent, status, eta）。\n"
    "AGENT RULES:\n- 引数不要。ポーリング間隔は最低5秒空けること。"
)
@mcp_error_handler
def deliver_status() -> dict:
    return deliver_status_impl()


if __name__ == "__main__":
    mcp.run()
