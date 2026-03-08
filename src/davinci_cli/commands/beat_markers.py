"""dr timeline marker beats — BPMベースのマーカー自動配置。

BPM と音価を指定してタイムライン全体に等間隔マーカーを配置する。
"""

from __future__ import annotations

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
