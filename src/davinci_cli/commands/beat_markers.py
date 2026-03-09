"""dr timeline marker beats — BPMベースのマーカー自動配置。

BPM と音価を指定して、指定クリップの範囲に等間隔マーカーを配置する。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

import click

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.decorators import dry_run_option, json_input_option
from davinci_cli.output.formatter import output

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
    clip_index: int
    note_value: str = "1/4"
    color: str = "Blue"
    name: str = ""
    duration: int = 1


class BeatMarkerOutput(BaseModel):
    added_count: int | None = None
    bpm: float | None = None
    note_value: str | None = None
    color: str | None = None
    clip_name: str | None = None
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


def _collect_clips(tl: Any) -> list[tuple[dict, Any]]:
    """タイムラインから全クリップを収集する。"""
    clips: list[tuple[dict, Any]] = []
    for track_type in ["video", "audio"]:
        track_count = tl.GetTrackCount(track_type)
        for track_idx in range(1, track_count + 1):
            track_clips = tl.GetItemListInTrack(track_type, track_idx) or []
            for clip_item in track_clips:
                info = {
                    "index": len(clips),
                    "name": clip_item.GetName(),
                    "start": clip_item.GetStart(),
                    "end": clip_item.GetEnd(),
                    "type": track_type,
                    "track": track_idx,
                }
                clips.append((info, clip_item))
    return clips


# --- _impl Function ---


def beat_marker_impl(
    bpm: float,
    clip_index: int,
    note_value: str = "1/4",
    color: str = "Blue",
    name: str = "",
    duration: int = 1,
    dry_run: bool = False,
) -> dict:
    """BPM と音価を指定して、指定クリップの範囲にマーカーを配置する。"""
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

    # 3. クリップ取得
    clips = _collect_clips(tl)
    if clip_index < 0 or clip_index >= len(clips):
        raise ValidationError(
            field="clip_index",
            reason=f"Clip index {clip_index} out of range (0..{len(clips) - 1})",
        )
    clip_info, _clip_item = clips[clip_index]
    start_frame = clip_info["start"]
    end_frame = clip_info["end"]
    clip_name = clip_info["name"]

    # 4. フレーム計算（クリップの start〜end 範囲）
    frames = _calculate_beat_frames(bpm, note_value, fps, start_frame, end_frame)

    # 5. dry-run
    if dry_run:
        return {
            "dry_run": True,
            "action": "marker_beats",
            "bpm": bpm,
            "note_value": note_value,
            "color": color,
            "clip_name": clip_name,
            "count": len(frames),
            "frames": frames,
        }

    # 6. マーカー追加（マーカーAPIは相対フレームを要求）
    from davinci_cli.commands.timeline import _get_start_frame_offset

    offset = _get_start_frame_offset(tl)
    for frame_abs in frames:
        rel_frame = frame_abs - offset
        tl.AddMarker(rel_frame, color, name, "", duration)

    return {
        "added_count": len(frames),
        "bpm": bpm,
        "note_value": note_value,
        "color": color,
        "clip_name": clip_name,
        "frames": frames,
    }


# --- CLI Command ---


@click.command(name="beats")
@json_input_option
@dry_run_option
@click.pass_context
def beat_marker_cmd(
    ctx: click.Context,
    json_input: dict | None,
    dry_run: bool,
) -> None:
    """BPMベースのマーカー自動配置。"""
    if not json_input:
        raise click.UsageError("--json is required")
    data = BeatMarkerInput.model_validate(json_input)
    result = beat_marker_impl(
        bpm=data.bpm,
        clip_index=data.clip_index,
        note_value=data.note_value,
        color=data.color,
        name=data.name,
        duration=data.duration,
        dry_run=dry_run,
    )
    output(result, pretty=ctx.obj.get("pretty"))


from davinci_cli.schema_registry import register_schema

# --- Schema Registration ---

register_schema(
    "timeline.marker.beats",
    output_model=BeatMarkerOutput,
    input_model=BeatMarkerInput,
)
