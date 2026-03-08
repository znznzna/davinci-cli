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
    clip_color_clear_impl,
    clip_color_get_impl,
    clip_color_set_impl,
    clip_enable_impl,
    clip_flag_add_impl,
    clip_flag_clear_impl,
    clip_flag_list_impl,
    clip_info_impl,
    clip_list_impl,
    clip_property_get_impl,
    clip_property_set_impl,
    clip_select_impl,
)
from davinci_cli.commands.color import (
    color_apply_lut_impl,
    color_cdl_set_impl,
    color_copy_grade_impl,
    color_lut_export_impl,
    color_reset_all_impl,
    color_reset_impl,
    color_version_add_impl,
    color_version_current_impl,
    color_version_delete_impl,
    color_version_list_impl,
    color_version_load_impl,
    color_version_rename_impl,
    node_enable_impl,
    node_lut_get_impl,
    node_lut_set_impl,
    still_grab_impl,
    still_list_impl,
)
from davinci_cli.commands.deliver import (
    deliver_add_job_impl,
    deliver_codec_list_impl,
    deliver_delete_all_jobs_impl,
    deliver_delete_job_impl,
    deliver_format_list_impl,
    deliver_is_rendering_impl,
    deliver_job_status_impl,
    deliver_list_jobs_impl,
    deliver_preset_export_impl,
    deliver_preset_import_impl,
    deliver_preset_list_impl,
    deliver_preset_load_impl,
    deliver_start_impl,
    deliver_status_impl,
    deliver_stop_impl,
)
from davinci_cli.commands.gallery import (
    gallery_album_create_impl,
    gallery_album_current_impl,
    gallery_album_list_impl,
    gallery_album_set_impl,
    gallery_still_delete_impl,
    gallery_still_export_impl,
    gallery_still_import_impl,
)
from davinci_cli.commands.media import (
    folder_create_impl,
    folder_delete_impl,
    folder_list_impl,
    media_delete_impl,
    media_export_metadata_impl,
    media_import_impl,
    media_list_impl,
    media_metadata_get_impl,
    media_metadata_set_impl,
    media_move_impl,
    media_relink_impl,
    media_transcribe_impl,
    media_unlink_impl,
)
from davinci_cli.commands.project import (
    project_close_impl,
    project_create_impl,
    project_delete_impl,
    project_info_impl,
    project_list_impl,
    project_open_impl,
    project_rename_impl,
    project_save_impl,
    project_settings_get_impl,
    project_settings_set_impl,
)
from davinci_cli.commands.system import (
    edition_impl,
    info_impl,
    keyframe_mode_get_impl,
    keyframe_mode_set_impl,
    page_get_impl,
    page_set_impl,
    ping_impl,
    version_impl,
)
from davinci_cli.commands.timeline import (
    current_item_impl,
    marker_add_impl,
    marker_delete_impl,
    marker_list_impl,
    timecode_get_impl,
    timecode_set_impl,
    timeline_create_impl,
    timeline_create_subtitles_impl,
    timeline_current_impl,
    timeline_delete_impl,
    timeline_detect_scene_cuts_impl,
    timeline_duplicate_impl,
    timeline_export_impl,
    timeline_list_impl,
    timeline_switch_impl,
    track_add_impl,
    track_delete_impl,
    track_enable_impl,
    track_list_impl,
    track_lock_impl,
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


@mcp.tool(
    description="現在のページを取得する。\n"
    "AGENT RULES:\n- 引数不要。media/edit/fusion/color/fairlight/deliverのいずれかを返す。"
)
@mcp_error_handler
def system_page_get() -> dict:
    return page_get_impl()


@mcp.tool(
    description="ページを切り替える。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- 有効なページ: media, cut, edit, fusion, color, fairlight, deliver"
)
@mcp_error_handler
def system_page_set(page: str, dry_run: bool = True) -> dict:
    return page_set_impl(page=page, dry_run=dry_run)


@mcp.tool(
    description="現在のキーフレームモードを取得する。\n"
    "AGENT RULES:\n- 引数不要。0=all, 1=color, 2=sizingを返す。"
)
@mcp_error_handler
def system_keyframe_mode_get() -> dict:
    return keyframe_mode_get_impl()


@mcp.tool(
    description="キーフレームモードを設定する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- mode: 0=all, 1=color, 2=sizing"
)
@mcp_error_handler
def system_keyframe_mode_set(mode: int, dry_run: bool = True) -> dict:
    return keyframe_mode_set_impl(mode=mode, dry_run=dry_run)


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
    description="現在のプロジェクトをリネームする。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def project_rename(name: str, dry_run: bool = True) -> dict:
    return project_rename_impl(name=name, dry_run=dry_run)


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


@mcp.tool(
    description="プロジェクト設定を取得する。\n"
    "AGENT RULES:\n- key省略で全設定取得（コンテキストを消費する）"
)
@mcp_error_handler
def project_settings_get(key: str | None = None) -> dict:
    return project_settings_get_impl(key=key)


@mcp.tool(
    description="プロジェクト設定を変更する。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def project_settings_set(key: str, value: str, dry_run: bool = True) -> dict:
    return project_settings_set_impl(key=key, value=value, dry_run=dry_run)


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


@mcp.tool(
    description="現在のタイムコードを取得する。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def timeline_timecode_get() -> dict:
    return timecode_get_impl()


@mcp.tool(
    description="タイムコードを設定する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- timecodeはHH:MM:SS:FF形式（例: "01:00:00:00"）'
)
@mcp_error_handler
def timeline_timecode_set(timecode: str, dry_run: bool = True) -> dict:
    return timecode_set_impl(timecode=timecode, dry_run=dry_run)


@mcp.tool(
    description="現在のビデオアイテム（再生ヘッド位置のクリップ）を取得する。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def timeline_current_item() -> dict:
    return current_item_impl()


@mcp.tool(
    description="全トラック一覧を返す。\n"
    "AGENT RULES:\n- 引数不要。video/audio/subtitleトラックを全て返す。"
)
@mcp_error_handler
def timeline_track_list() -> list[dict]:
    return track_list_impl()


@mcp.tool(
    description="トラックを追加する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- track_type: video, audio, subtitle"
)
@mcp_error_handler
def timeline_track_add(track_type: str, dry_run: bool = True) -> dict:
    return track_add_impl(track_type=track_type, dry_run=dry_run)


@mcp.tool(
    description="トラックを削除する（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- track_type: video, audio, subtitle\n"
    "- track_indexはtrack_listで確認した値を使うこと"
)
@mcp_error_handler
def timeline_track_delete(
    track_type: str, track_index: int, dry_run: bool = True
) -> dict:
    return track_delete_impl(
        track_type=track_type, index=track_index, dry_run=dry_run
    )


@mcp.tool(
    description="トラックの有効/無効を取得または設定する。\n"
    "AGENT RULES:\n"
    "- enabled=Noneで現在値を取得、True/Falseで設定\n"
    "- track_type: video, audio, subtitle"
)
@mcp_error_handler
def timeline_track_enable(
    track_type: str, track_index: int, enabled: bool | None = None
) -> dict:
    return track_enable_impl(
        track_type=track_type, index=track_index, enabled=enabled
    )


@mcp.tool(
    description="トラックのロック状態を取得または設定する。\n"
    "AGENT RULES:\n"
    "- locked=Noneで現在値を取得、True/Falseで設定\n"
    "- track_type: video, audio, subtitle"
)
@mcp_error_handler
def timeline_track_lock(
    track_type: str, track_index: int, locked: bool | None = None
) -> dict:
    return track_lock_impl(
        track_type=track_type, index=track_index, locked=locked
    )


@mcp.tool(
    description="現在のタイムラインを複製する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- nameを省略すると自動命名される"
)
@mcp_error_handler
def timeline_duplicate(name: str | None = None, dry_run: bool = True) -> dict:
    return timeline_duplicate_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description="タイムラインのシーンカットを検出する。\n"
    "AGENT RULES:\n- 処理に時間がかかる場合がある。"
)
@mcp_error_handler
def timeline_detect_scene_cuts() -> dict:
    return timeline_detect_scene_cuts_impl()


@mcp.tool(
    description="音声から字幕を自動生成する。\n"
    "AGENT RULES:\n- 処理に時間がかかる場合がある。"
)
@mcp_error_handler
def timeline_create_subtitles() -> dict:
    return timeline_create_subtitles_impl()


@mcp.tool(
    description="タイムラインをファイルにエクスポートする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- format: AAF, EDL, FCPXML 等\n"
    '- output_pathはシステム上の絶対パス（".."を含むパスは拒絶される）'
)
@mcp_error_handler
def timeline_export(
    format: str,
    output_path: str,
    timeline_name: str | None = None,
    dry_run: bool = True,
) -> dict:
    return timeline_export_impl(
        format=format,
        output_path=output_path,
        timeline_name=timeline_name,
        dry_run=dry_run,
    )


@mcp.tool(
    description="タイムラインのマーカー一覧を返す。\n"
    "AGENT RULES:\n- timeline_name省略で現在のタイムラインを使用"
)
@mcp_error_handler
def timeline_marker_list(timeline_name: str | None = None) -> list[dict]:
    return marker_list_impl(timeline_name=timeline_name)


@mcp.tool(
    description="タイムラインにマーカーを追加する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- color: Blue, Cyan, Green, Yellow, Red, Pink, Purple, Fuchsia, Rose, Lavender, Sky, Mint, Lemon, Sand, Cocoa, Cream"
)
@mcp_error_handler
def timeline_marker_add(
    frame_id: int,
    color: str,
    name: str,
    note: str | None = None,
    duration: int = 1,
    dry_run: bool = True,
) -> dict:
    return marker_add_impl(
        frame_id=frame_id,
        color=color,
        name=name,
        note=note,
        duration=duration,
        dry_run=dry_run,
    )


@mcp.tool(
    description="タイムラインのマーカーを削除する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- frame_idはtimeline_marker_listで確認した値を使うこと"
)
@mcp_error_handler
def timeline_marker_delete(frame_id: int, dry_run: bool = True) -> dict:
    return marker_delete_impl(frame_id=frame_id, dry_run=dry_run)


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
    description="クリップのプロパティを取得する。\n"
    "AGENT RULES:\n- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_property_get(index: int, key: str) -> dict:
    return clip_property_get_impl(index=index, key=key)


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


@mcp.tool(
    description="クリップの有効/無効を取得または設定する。\n"
    "AGENT RULES:\n"
    "- enabled=Noneで現在値を取得、True/Falseで設定\n"
    "- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_enable(index: int, enabled: bool | None = None) -> dict:
    return clip_enable_impl(index=index, enabled=enabled)


@mcp.tool(
    description="クリップのカラーを取得する。\n"
    "AGENT RULES:\n- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_color_get(index: int) -> dict:
    return clip_color_get_impl(index=index)


@mcp.tool(
    description="クリップのカラーを設定する。\n"
    "AGENT RULES:\n"
    "- index はclip listで確認した値を使うこと\n"
    "- color: Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy,\n"
    "  Blue, Purple, Violet, Pink, Tan, Beige, Brown, Chocolate"
)
@mcp_error_handler
def clip_color_set(index: int, color: str) -> dict:
    return clip_color_set_impl(index=index, color=color)


@mcp.tool(
    description="クリップのカラーをクリアする。\n"
    "AGENT RULES:\n- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_color_clear(index: int) -> dict:
    return clip_color_clear_impl(index=index)


@mcp.tool(
    description="クリップにフラグを追加する。\n"
    "AGENT RULES:\n- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_flag_add(index: int, color: str) -> dict:
    return clip_flag_add_impl(index=index, color=color)


@mcp.tool(
    description="クリップのフラグ一覧を返す。\n"
    "AGENT RULES:\n- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_flag_list(index: int) -> list:
    return clip_flag_list_impl(index=index)


@mcp.tool(
    description="クリップのフラグをクリアする。\n"
    "AGENT RULES:\n"
    "- index はclip listで確認した値を使うこと\n"
    '- color: 特定色またはデフォルト"All"で全クリア'
)
@mcp_error_handler
def clip_flag_clear(index: int, color: str = "All") -> dict:
    return clip_flag_clear_impl(index=index, color=color)


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


@mcp.tool(
    description="グレードを別クリップにコピーする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- from_index: コピー元クリップインデックス\n"
    "- to_index: コピー先クリップインデックス"
)
@mcp_error_handler
def color_copy_grade(
    from_index: int, to_index: int, dry_run: bool = True
) -> dict:
    return color_copy_grade_impl(
        from_index=from_index, to_index=to_index, dry_run=dry_run
    )


@mcp.tool(
    description="カラーバージョン一覧を返す。\n"
    "AGENT RULES:\n- version_type: 0=local, 1=remote"
)
@mcp_error_handler
def color_version_list(clip_index: int, version_type: int = 0) -> list[dict]:
    return color_version_list_impl(
        clip_index=clip_index, version_type=version_type
    )


@mcp.tool(
    description="現在のカラーバージョンを取得する。\n"
    "AGENT RULES:\n- clip_indexはclip listで確認した値を使うこと"
)
@mcp_error_handler
def color_version_current(clip_index: int) -> dict:
    return color_version_current_impl(clip_index=clip_index)


@mcp.tool(
    description="カラーバージョンを追加する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- version_type: 0=local, 1=remote"
)
@mcp_error_handler
def color_version_add(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = True,
) -> dict:
    return color_version_add_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )


@mcp.tool(
    description="カラーバージョンをロードする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- version_type: 0=local, 1=remote"
)
@mcp_error_handler
def color_version_load(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = True,
) -> dict:
    return color_version_load_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )


@mcp.tool(
    description="カラーバージョンを削除する（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- version_type: 0=local, 1=remote"
)
@mcp_error_handler
def color_version_delete(
    clip_index: int,
    name: str,
    version_type: int = 0,
    dry_run: bool = True,
) -> dict:
    return color_version_delete_impl(
        clip_index=clip_index,
        name=name,
        version_type=version_type,
        dry_run=dry_run,
    )


@mcp.tool(
    description="カラーバージョンをリネームする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- version_type: 0=local, 1=remote"
)
@mcp_error_handler
def color_version_rename(
    clip_index: int,
    old_name: str,
    new_name: str,
    version_type: int = 0,
    dry_run: bool = True,
) -> dict:
    return color_version_rename_impl(
        clip_index=clip_index,
        old_name=old_name,
        new_name=new_name,
        version_type=version_type,
        dry_run=dry_run,
    )


@mcp.tool(
    description="ノードにLUTを設定する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- lut_pathはシステム上の絶対パス（".."を含むパスは拒絶される）\n'
    "- 許可拡張子: .cube, .3dl, .lut, .mga, .m3d"
)
@mcp_error_handler
def color_node_lut_set(
    clip_index: int, node_index: int, lut_path: str, dry_run: bool = True
) -> dict:
    return node_lut_set_impl(
        clip_index=clip_index,
        node_index=node_index,
        lut_path=lut_path,
        dry_run=dry_run,
    )


@mcp.tool(
    description="ノードのLUTパスを取得する。\n"
    "AGENT RULES:\n- clip_index, node_indexはそれぞれclip list, node listで確認した値を使うこと"
)
@mcp_error_handler
def color_node_lut_get(clip_index: int, node_index: int) -> dict:
    return node_lut_get_impl(clip_index=clip_index, node_index=node_index)


@mcp.tool(
    description="ノードの有効/無効を設定する。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def color_node_enable(
    clip_index: int, node_index: int, enabled: bool, dry_run: bool = True
) -> dict:
    return node_enable_impl(
        clip_index=clip_index,
        node_index=node_index,
        enabled=enabled,
        dry_run=dry_run,
    )


@mcp.tool(
    description="CDL値を設定する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- slope/offset/power/saturationはスペース区切りのRGB値（例: "1.0 1.0 1.0"）'
)
@mcp_error_handler
def color_cdl_set(
    clip_index: int,
    node_index: int,
    slope: str,
    offset: str,
    power: str,
    saturation: str,
    dry_run: bool = True,
) -> dict:
    return color_cdl_set_impl(
        clip_index=clip_index,
        node_index=node_index,
        slope=slope,
        offset=offset,
        power=power,
        saturation=saturation,
        dry_run=dry_run,
    )


@mcp.tool(
    description="LUTをファイルにエクスポートする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- pathはシステム上の絶対パス（".."を含むパスは拒絶される）'
)
@mcp_error_handler
def color_lut_export(
    clip_index: int, export_type: int, path: str, dry_run: bool = True
) -> dict:
    return color_lut_export_impl(
        clip_index=clip_index,
        export_type=export_type,
        path=path,
        dry_run=dry_run,
    )


@mcp.tool(
    description="全グレードをリセットする（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- color_resetとは異なり、ノードグラフ全体をリセットする"
)
@mcp_error_handler
def color_reset_all(clip_index: int, dry_run: bool = True) -> dict:
    return color_reset_all_impl(clip_index=clip_index, dry_run=dry_run)


@mcp.tool(
    description="スチルをグラブ（キャプチャ）する。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def color_still_grab(clip_index: int, dry_run: bool = True) -> dict:
    return still_grab_impl(clip_index=clip_index, dry_run=dry_run)


@mcp.tool(
    description="現在のアルバムのスチル一覧を返す。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def color_still_list() -> list[dict]:
    return still_list_impl()


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


@mcp.tool(
    description="メディアクリップを別フォルダに移動する。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- clip_namesはmedia listで確認したクリップ名のリスト"
)
@mcp_error_handler
def media_move(
    clip_names: list[str], target_folder: str, dry_run: bool = True
) -> dict:
    return media_move_impl(
        clip_names=clip_names, target_folder=target_folder, dry_run=dry_run
    )


@mcp.tool(
    description="メディアクリップを削除する（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認し、ユーザーの明示的な承認を得てから実行\n"
    "- clip_namesはmedia listで確認したクリップ名のリスト"
)
@mcp_error_handler
def media_delete(clip_names: list[str], dry_run: bool = True) -> dict:
    return media_delete_impl(clip_names=clip_names, dry_run=dry_run)


@mcp.tool(
    description="メディアクリップを再リンクする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- folder_pathはシステム上の絶対パス（".."を含むパスは拒絶される）'
)
@mcp_error_handler
def media_relink(
    clip_names: list[str], folder_path: str, dry_run: bool = True
) -> dict:
    return media_relink_impl(
        clip_names=clip_names, folder_path=folder_path, dry_run=dry_run
    )


@mcp.tool(
    description="メディアクリップのリンクを解除する。\n"
    "AGENT RULES:\n- clip_namesはmedia listで確認したクリップ名のリスト"
)
@mcp_error_handler
def media_unlink(clip_names: list[str]) -> dict:
    return media_unlink_impl(clip_names=clip_names)


@mcp.tool(
    description="メディアクリップのメタデータを取得する。\n"
    "AGENT RULES:\n"
    "- clip_nameはmedia listで確認したクリップ名\n"
    "- key省略で全メタデータ取得（コンテキストを消費する）"
)
@mcp_error_handler
def media_metadata_get(clip_name: str, key: str | None = None) -> dict:
    return media_metadata_get_impl(clip_name=clip_name, key=key)


@mcp.tool(
    description="メディアクリップのメタデータを設定する。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def media_metadata_set(
    clip_name: str, key: str, value: str, dry_run: bool = True
) -> dict:
    return media_metadata_set_impl(
        clip_name=clip_name, key=key, value=value, dry_run=dry_run
    )


@mcp.tool(
    description="メディアプールのメタデータをCSVにエクスポートする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- file_nameはシステム上の絶対パス（".."を含むパスは拒絶される）'
)
@mcp_error_handler
def media_export_metadata(file_name: str, dry_run: bool = True) -> dict:
    return media_export_metadata_impl(file_name=file_name, dry_run=dry_run)


@mcp.tool(
    description="メディアクリップの音声をトランスクライブする。\n"
    "AGENT RULES:\n"
    "- clip_nameはmedia listで確認したクリップ名\n"
    "- 処理に時間がかかる場合がある"
)
@mcp_error_handler
def media_transcribe(clip_name: str) -> dict:
    return media_transcribe_impl(clip_name=clip_name)


@mcp.tool(
    description="メディアプールのフォルダ一覧を返す。\n"
    "AGENT RULES:\n- 引数不要。ルートフォルダ直下のサブフォルダを返す。"
)
@mcp_error_handler
def media_folder_list() -> list[dict]:
    return folder_list_impl()


@mcp.tool(
    description="メディアプールにフォルダを作成する。\n"
    "AGENT RULES:\n- nameはフォルダ名"
)
@mcp_error_handler
def media_folder_create(name: str) -> dict:
    return folder_create_impl(name=name)


@mcp.tool(
    description="メディアプールのフォルダを削除する（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認し、ユーザーの明示的な承認を得てから実行\n"
    "- フォルダ内のクリップも全て削除される"
)
@mcp_error_handler
def media_folder_delete(name: str, dry_run: bool = True) -> dict:
    return folder_delete_impl(name=name, dry_run=dry_run)


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


@mcp.tool(
    description="レンダージョブを削除する（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- job_idはdeliver_list_jobsで確認した値を使うこと"
)
@mcp_error_handler
def deliver_delete_job(job_id: str, dry_run: bool = True) -> dict:
    return deliver_delete_job_impl(job_id=job_id, dry_run=dry_run)


@mcp.tool(
    description="全レンダージョブを削除する（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認し、ユーザーの明示的な承認を得てから実行\n"
    "- 復元不可"
)
@mcp_error_handler
def deliver_delete_all_jobs(dry_run: bool = True) -> dict:
    return deliver_delete_all_jobs_impl(dry_run=dry_run)


@mcp.tool(
    description="特定レンダージョブのステータスを返す。\n"
    "AGENT RULES:\n- job_idはdeliver_list_jobsで確認した値を使うこと"
)
@mcp_error_handler
def deliver_job_status(job_id: str) -> dict:
    return deliver_job_status_impl(job_id=job_id)


@mcp.tool(
    description="レンダー中かどうかを返す。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def deliver_is_rendering() -> dict:
    return deliver_is_rendering_impl()


@mcp.tool(
    description="レンダーフォーマット一覧を返す。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def deliver_format_list() -> dict:
    return deliver_format_list_impl()


@mcp.tool(
    description="指定フォーマットのコーデック一覧を返す。\n"
    "AGENT RULES:\n- format_nameはdeliver_format_listで確認した値を使うこと"
)
@mcp_error_handler
def deliver_codec_list(format_name: str) -> dict:
    return deliver_codec_list_impl(format_name=format_name)


@mcp.tool(
    description="レンダープリセットをインポートする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- pathはシステム上の絶対パス（".."を含むパスは拒絶される）'
)
@mcp_error_handler
def deliver_preset_import(path: str, dry_run: bool = True) -> dict:
    return deliver_preset_import_impl(path=path, dry_run=dry_run)


@mcp.tool(
    description="レンダープリセットをエクスポートする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- pathはシステム上の絶対パス（".."を含むパスは拒絶される）'
)
@mcp_error_handler
def deliver_preset_export(
    name: str, path: str, dry_run: bool = True
) -> dict:
    return deliver_preset_export_impl(name=name, path=path, dry_run=dry_run)


# ---- gallery ----


@mcp.tool(
    description="ギャラリーアルバム一覧を返す。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def gallery_album_list() -> list[dict]:
    return gallery_album_list_impl()


@mcp.tool(
    description="現在のギャラリーアルバムを取得する。\n"
    "AGENT RULES:\n- 引数不要。"
)
@mcp_error_handler
def gallery_album_current() -> dict:
    return gallery_album_current_impl()


@mcp.tool(
    description="ギャラリーアルバムを切り替える。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- nameはgallery_album_listで確認した値を使うこと"
)
@mcp_error_handler
def gallery_album_set(name: str, dry_run: bool = True) -> dict:
    return gallery_album_set_impl(name=name, dry_run=dry_run)


@mcp.tool(
    description="新規ギャラリーアルバムを作成する。\n"
    "AGENT RULES:\n- 必ずdry_run=Trueで事前確認すること"
)
@mcp_error_handler
def gallery_album_create(dry_run: bool = True) -> dict:
    return gallery_album_create_impl(dry_run=dry_run)


@mcp.tool(
    description="スチルをファイルにエクスポートする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- folder_pathはシステム上の絶対パス（".."を含むパスは拒絶される）\n'
    '- format: dpx, cin, tif, jpg, png, tga, bmp, exr'
)
@mcp_error_handler
def gallery_still_export(
    folder_path: str,
    file_prefix: str = "still",
    format: str = "dpx",
    dry_run: bool = True,
) -> dict:
    return gallery_still_export_impl(
        folder_path=folder_path,
        file_prefix=file_prefix,
        format=format,
        dry_run=dry_run,
    )


@mcp.tool(
    description="スチルをインポートする。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    '- pathsには絶対パスのリストを渡すこと（".."を含むパスは拒絶される）'
)
@mcp_error_handler
def gallery_still_import(paths: list[str], dry_run: bool = True) -> dict:
    return gallery_still_import_impl(paths=paths, dry_run=dry_run)


@mcp.tool(
    description="スチルを削除する（破壊的操作）。\n"
    "AGENT RULES:\n"
    "- 必ずdry_run=Trueで事前確認すること\n"
    "- still_indicesはcolor_still_listで確認したインデックスのリスト"
)
@mcp_error_handler
def gallery_still_delete(
    still_indices: list[int], dry_run: bool = True
) -> dict:
    return gallery_still_delete_impl(
        still_indices=still_indices, dry_run=dry_run
    )


if __name__ == "__main__":
    mcp.run()
