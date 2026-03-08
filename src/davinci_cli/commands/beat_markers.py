"""dr timeline marker beats — BPMベースのマーカー自動配置。

BPM と音価を指定してタイムライン全体に等間隔マーカーを配置する。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError

# 音価 → 1拍あたりの倍率マッピング
NOTE_VALUE_MAP: dict[str, float] = {
    "1/1": 4.0,    # 全音符 = 4拍
    "1/2": 2.0,    # 2分音符 = 2拍
    "1/4": 1.0,    # 4分音符 = 1拍
    "1/8": 0.5,    # 8分音符 = 0.5拍
    "1/16": 0.25,  # 16分音符 = 0.25拍
}


def _calculate_beat_frames(
    bpm: float,
    note_value: str,
    fps: float,
    start_frame: int,
    end_frame: int,
) -> list[int]:
    """BPM・音価・FPSからマーカーを打つべきフレーム一覧を計算する。

    誤差蓄積防止: 各フレームは start_frame + round(i * interval) で計算。
    累積加算（frame += interval）は使わない。
    """
    beats_per_note = NOTE_VALUE_MAP[note_value]
    # 1音価あたりの秒数
    seconds_per_beat = (60.0 / bpm) * beats_per_note
    # 1音価あたりのフレーム数（浮動小数点）
    frames_per_beat = seconds_per_beat * fps

    frames: list[int] = []
    i = 0
    while True:
        frame = start_frame + round(i * frames_per_beat)
        if frame > end_frame:
            break
        frames.append(frame)
        i += 1
    return frames


# --- Pydantic Models ---


class BeatMarkerInput(BaseModel):
    bpm: float
    note_value: str = "1/4"
    color: str = "Blue"
    name: str = ""
    duration: int = 1


class BeatMarkerOutput(BaseModel):
    added_count: int | None = None
    bpm: float | None = None
    note_value: str | None = None
    color: str | None = None
    frames: list[int] | None = None
    dry_run: bool | None = None
    action: str | None = None
    count: int | None = None


# --- Helper ---


def _get_current_project() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise ProjectNotOpenError()
    return project


def _get_start_frame_offset(tl: Any) -> int:
    """タイムラインの開始タイムコードをフレーム数に変換して返す。"""
    tc = tl.GetStartTimecode() or "00:00:00:00"
    parts = tc.replace(";", ":").split(":")
    if len(parts) != 4:
        return 0
    h, m, s, f = (int(p) for p in parts)
    fps_str = tl.GetSetting("timelineFrameRate") or "24"
    fps = int(float(fps_str))
    return h * 3600 * fps + m * 60 * fps + s * fps + f


# --- _impl Function ---


def beat_marker_impl(
    bpm: float,
    note_value: str = "1/4",
    color: str = "Blue",
    name: str = "",
    duration: int = 1,
    dry_run: bool = False,
) -> dict:
    """BPM と音価を指定してタイムライン全体にマーカーを配置する。"""
    # 1. バリデーション
    if note_value not in NOTE_VALUE_MAP:
        raise ValidationError(
            field="note_value",
            reason=f"Invalid note_value: '{note_value}'. Must be one of: {', '.join(NOTE_VALUE_MAP)}",
        )
    if not (20.0 <= bpm <= 300.0):
        raise ValidationError(
            field="bpm",
            reason=f"BPM must be between 20.0 and 300.0, got {bpm}",
        )

    # 2. タイムライン情報取得
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    if not tl:
        raise ProjectNotOpenError()
    fps = float(tl.GetSetting("timelineFrameRate") or "24")
    offset = _get_start_frame_offset(tl)
    end_frame_rel = tl.GetEndFrame()
    end_frame_abs = end_frame_rel + offset

    # 3. フレーム計算
    frames = _calculate_beat_frames(bpm, note_value, fps, offset, end_frame_abs)

    # 4. dry-run
    if dry_run:
        return {
            "dry_run": True,
            "action": "marker_beats",
            "bpm": bpm,
            "note_value": note_value,
            "color": color,
            "count": len(frames),
            "frames": frames,
        }

    # 5. マーカー追加
    for frame_abs in frames:
        rel_frame = frame_abs - offset
        tl.AddMarker(rel_frame, color, name, "", duration)

    return {
        "added_count": len(frames),
        "bpm": bpm,
        "note_value": note_value,
        "color": color,
        "frames": frames,
    }
