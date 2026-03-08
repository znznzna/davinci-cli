# API Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** davinci-cli のコマンドを DaVinci Resolve 公式 API に合わせて整理し、不要コマンド削除・バグ修正・新規コマンド約50件追加を行う
**Architecture:** _impl パターンに従い CLI + MCP 両対応。Gallery は新規モジュール。Graph 操作はヘルパー経由。
**Tech Stack:** Python 3.10+, Click, FastMCP, Pydantic v2, pytest

---

## Batch 1: クリーンアップ（削除 + バグ修正 + project.rename）

### Task 1: 存在しないAPI呼び出しの削除（4件）

**Files:**
- Modify: `src/davinci_cli/commands/color.py`
- Modify: `tests/unit/test_color.py`
- Modify: `src/davinci_cli/mcp/mcp_server.py`

**Step 1: テストを修正**
- `test_color.py` から以下のテストクラス/メソッドを削除:
  - `TestNodeImpl.test_node_add_*` (2件)
  - `TestNodeImpl.test_node_delete_*` (2件)
  - `TestStillImpl.test_still_apply_*` (2件)
  - `TestColorGradeImpl.test_paste_grade_*` (2件)
- 削除対象コマンドが存在しないことを確認するテストを追加:
  - `test_node_add_command_removed`, `test_node_delete_command_removed`
  - `test_paste_grade_command_removed`, `test_still_apply_command_removed`
  - CliRunner で呼び出し、exit_code != 0 を確認

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_color.py -v`
Expected: FAIL（削除対象のimportがまだ存在）

**Step 3: 最小限の実装**
- `color.py` から削除:
  - `node_add_impl()`, `node_delete_impl()`, `color_paste_grade_impl()`, `still_apply_impl()`
  - `NodeAddOutput`, `NodeDeleteOutput`, `ColorPasteGradeOutput`, `StillApplyOutput` モデル
  - `node_add_cmd`, `node_delete_cmd`, `paste_grade`, `still_apply_cmd` CLI コマンド
  - 対応する `register_schema()` 呼び出し（4件）
- `mcp_server.py` から削除対象のimport/ツール登録を削除（paste_gradeはMCPに未登録のため不要）

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_color.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "fix: remove 4 commands with non-existent API methods (API audit cleanup)"
```

---

### Task 2: color.copy-grade バグ修正

**Files:**
- Modify: `src/davinci_cli/commands/color.py`
- Modify: `tests/unit/test_color.py`

**Step 1: 失敗するテストを書く**
- `TestColorGradeImpl` に追加:
  - `test_copy_grade_requires_to_argument`: `--to` 引数でターゲットクリップを指定
  - `test_copy_grade_calls_correct_api`: `CopyGrades([tgtTimelineItems])` を正しい引数で呼ぶことを検証
  - `test_copy_grade_dry_run`: `dry_run=True` で実行確認

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_color.py::TestColorGradeImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `color_copy_grade_impl(from_index, to_index, dry_run=False)` に変更:
  - `dry_run=True` → `{"dry_run": True, "action": "copy_grade", "from_index": from_index, "to_index": to_index}`
  - from_index のクリップで `CopyGrades([tgt_clip_item])` を呼び出し（tgt_clip_item は to_index で取得）
- CLI の `copy-grade` コマンドに `--to` オプション追加、`--dry-run` 追加
- `ColorCopyGradeOutput` モデルに `to_index`, `dry_run`, `action` フィールド追加
- schema 更新

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_color.py::TestColorGradeImpl -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "fix: correct copy-grade to use CopyGrades([tgtItems]) with --to arg (API audit)"
```

---

### Task 3: project.rename 追加

**Files:**
- Modify: `src/davinci_cli/commands/project.py`
- Modify: `tests/unit/test_project.py`

**Step 1: 失敗するテストを書く**
- `TestProjectRenameImpl`:
  - `test_rename_dry_run`: `dry_run=True` で `{"dry_run": True, "action": "rename", ...}` 返却
  - `test_rename_success`: mock resolve で `SetName()` 呼び出し、`{"renamed": "new_name"}` 返却
  - `test_rename_cli`: CliRunner で `dr project rename NewName --dry-run`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_project.py::TestProjectRenameImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `project_rename_impl(name: str, dry_run: bool = False) -> dict`:
  - `Project.SetName(name)` 呼び出し
- `ProjectRenameOutput` / `ProjectRenameInput` Pydantic モデル追加
- CLI: `@project.command(name="rename")` + `@click.argument("name")` + `@dry_run_option`
- `register_schema("project.rename", ...)` 追加

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_project.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add project.rename command with Project.SetName() (API audit)"
```

---

## Batch 2: ナビゲーション（7件）

### Task 4: system.page.get / system.page.set

**Files:**
- Modify: `src/davinci_cli/commands/system.py`
- Modify: `tests/unit/test_system.py`

**Step 1: 失敗するテストを書く**
- `TestPageImpl`:
  - `test_page_get`: mock `Resolve.GetCurrentPage()` → `{"page": "color"}`
  - `test_page_set_dry_run`: `dry_run=True` → `{"dry_run": True, "action": "page_set", "page": "edit"}`
  - `test_page_set`: mock `Resolve.OpenPage("edit")` → `{"set": True, "page": "edit"}`
  - `test_page_set_invalid`: 無効なページ名で `ValidationError`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_system.py::TestPageImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `page_get_impl() -> dict`: `Resolve.GetCurrentPage()` → `{"page": page_name}`
- `page_set_impl(page: str, dry_run=False) -> dict`: `Resolve.OpenPage(page)`
  - ページ名バリデーション: `{"media", "cut", "edit", "fusion", "color", "fairlight", "deliver"}`
- CLI: `@system.group(name="page")` → `get`, `set` サブコマンド
- Pydantic: `PageGetOutput`, `PageSetOutput`, `PageSetInput`
- schema 登録: `system.page.get`, `system.page.set`

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_system.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add system.page.get/set for page navigation (API audit)"
```

---

### Task 5: system.keyframe-mode.get / system.keyframe-mode.set

**Files:**
- Modify: `src/davinci_cli/commands/system.py`
- Modify: `tests/unit/test_system.py`

**Step 1: 失敗するテストを書く**
- `TestKeyframeModeImpl`:
  - `test_keyframe_mode_get`: `Resolve.GetKeyframeMode()` → `{"mode": <int>}`
  - `test_keyframe_mode_set_dry_run`
  - `test_keyframe_mode_set`: `Resolve.SetKeyframeMode(mode)` → `{"set": True, "mode": mode}`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_system.py::TestKeyframeModeImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `keyframe_mode_get_impl()`: `Resolve.GetKeyframeMode()`
- `keyframe_mode_set_impl(mode: int, dry_run=False)`: `Resolve.SetKeyframeMode(mode)`
- CLI: `@system.group(name="keyframe-mode")` → `get`, `set`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_system.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add system.keyframe-mode.get/set (API audit)"
```

---

### Task 6: timeline.timecode.get / timeline.timecode.set / timeline.current-item

**Files:**
- Modify: `src/davinci_cli/commands/timeline.py`
- Modify: `tests/unit/test_timeline.py`

**Step 1: 失敗するテストを書く**
- `TestTimecodeImpl`:
  - `test_timecode_get`: `Timeline.GetCurrentTimecode()` → `{"timecode": "01:00:00:00"}`
  - `test_timecode_set_dry_run`
  - `test_timecode_set`: `Timeline.SetCurrentTimecode(tc)` → `{"set": True, "timecode": tc}`
- `TestCurrentItemImpl`:
  - `test_current_item`: `Timeline.GetCurrentVideoItem()` → `{"name": "clip", "index": 0}`
  - `test_current_item_none`: 未選択時は空/null応答

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_timeline.py::TestTimecodeImpl tests/unit/test_timeline.py::TestCurrentItemImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `timecode_get_impl()`: `project.GetCurrentTimeline().GetCurrentTimecode()`
- `timecode_set_impl(timecode: str, dry_run=False)`: `Timeline.SetCurrentTimecode(timecode)`
- `current_item_impl()`: `Timeline.GetCurrentVideoItem()` → クリップ名・インデックス返却
- CLI: `@timeline.group(name="timecode")` → `get`, `set`; `@timeline.command(name="current-item")`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_timeline.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add timeline.timecode.get/set and timeline.current-item (API audit)"
```

---

## Batch 3: トラック管理（8件）

### Task 7: timeline.track.list / timeline.track.add / timeline.track.delete

**Files:**
- Modify: `src/davinci_cli/commands/timeline.py`
- Modify: `tests/unit/test_timeline.py`

**Step 1: 失敗するテストを書く**
- `TestTrackImpl`:
  - `test_track_list`: `GetTrackCount("video")` + `GetTrackName("video", i)` → リスト返却
  - `test_track_add_dry_run`: `{"dry_run": True, ...}`
  - `test_track_add`: `AddTrack("video", "mono")` → `{"added": True, ...}`
  - `test_track_delete_dry_run`
  - `test_track_delete`: `DeleteTrack("video", 2)` → `{"deleted": True, ...}`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_timeline.py::TestTrackImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `track_list_impl()`: video/audio/subtitle の各タイプで `GetTrackCount` + `GetTrackName` をループ
- `track_add_impl(track_type, sub_track_type=None, dry_run=False)`: `Timeline.AddTrack(trackType, subTrackType)`
- `track_delete_impl(track_type, index, dry_run=False)`: `Timeline.DeleteTrack(trackType, index)`
- CLI: `@timeline.group(name="track")` → `list`, `add`, `delete`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_timeline.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add timeline.track.list/add/delete (API audit)"
```

---

### Task 8: timeline.track.enable / timeline.track.lock

**Files:**
- Modify: `src/davinci_cli/commands/timeline.py`
- Modify: `tests/unit/test_timeline.py`

**Step 1: 失敗するテストを書く**
- `TestTrackEnableLockImpl`:
  - `test_track_enable_get`: `GetIsTrackEnabled` → `{"enabled": True, ...}`
  - `test_track_enable_set`: `SetTrackEnable("video", 1, True)` → `{"set": True, ...}`
  - `test_track_lock_get`: `GetIsTrackLocked` → `{"locked": False, ...}`
  - `test_track_lock_set`: `SetTrackLock("video", 1, True)` → `{"set": True, ...}`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_timeline.py::TestTrackEnableLockImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `track_enable_impl(track_type, index, enabled=None)`: get/set 兼用。`enabled` 省略時はget
- `track_lock_impl(track_type, index, locked=None)`: get/set 兼用
- CLI: `@track.command(name="enable")`, `@track.command(name="lock")`
  - `--track-type` + `--index` + `--value` (bool/省略)

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_timeline.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add timeline.track.enable/lock (API audit)"
```

---

### Task 9: timeline.duplicate / timeline.detect-scene-cuts / timeline.create-subtitles

**Files:**
- Modify: `src/davinci_cli/commands/timeline.py`
- Modify: `tests/unit/test_timeline.py`

**Step 1: 失敗するテストを書く**
- `TestTimelineExtendedImpl`:
  - `test_duplicate_dry_run` / `test_duplicate`: `DuplicateTimeline(name)` → `{"duplicated": name}`
  - `test_detect_scene_cuts`: `DetectSceneCuts()` → `{"detected": True}`
  - `test_create_subtitles`: `CreateSubtitlesFromAudio()` → `{"created": True}`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_timeline.py::TestTimelineExtendedImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `timeline_duplicate_impl(name=None, dry_run=False)`: `Timeline.DuplicateTimeline(name)`
- `timeline_detect_scene_cuts_impl()`: `Timeline.DetectSceneCuts()`
- `timeline_create_subtitles_impl()`: `Timeline.CreateSubtitlesFromAudio()`
- CLI コマンド3件追加 + Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_timeline.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add timeline.duplicate/detect-scene-cuts/create-subtitles (API audit)"
```

---

## Batch 4: カラーバージョン + クリップ属性（12件）

### Task 10: color.version.list / color.version.current / color.version.add

**Files:**
- Modify: `src/davinci_cli/commands/color.py`
- Modify: `tests/unit/test_color.py`

**Step 1: 失敗するテストを書く**
- `TestColorVersionImpl`:
  - `test_version_list`: `GetVersionNameList(versionType)` → リスト
  - `test_version_current`: `GetCurrentVersion()` → `{"name": "...", "type": "..."}`
  - `test_version_add_dry_run` / `test_version_add`: `AddVersion(name, versionType)`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_color.py::TestColorVersionImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `color_version_list_impl(clip_index, version_type=0)`: `clip_item.GetVersionNameList(versionType)`
- `color_version_current_impl(clip_index)`: `clip_item.GetCurrentVersion()`
- `color_version_add_impl(clip_index, name, version_type=0, dry_run=False)`: `clip_item.AddVersion(name, versionType)`
- CLI: `@color.group(name="version")` → `list`, `current`, `add`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_color.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add color.version.list/current/add (API audit)"
```

---

### Task 11: color.version.load / color.version.delete / color.version.rename

**Files:**
- Modify: `src/davinci_cli/commands/color.py`
- Modify: `tests/unit/test_color.py`

**Step 1: 失敗するテストを書く**
- `TestColorVersionMutateImpl`:
  - `test_version_load_dry_run` / `test_version_load`: `LoadVersionByName(name, vType)`
  - `test_version_delete_dry_run` / `test_version_delete`: `DeleteVersionByName(name, vType)`
  - `test_version_rename_dry_run` / `test_version_rename`: `RenameVersionByName(old, new, vType)`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_color.py::TestColorVersionMutateImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `color_version_load_impl(clip_index, name, version_type=0, dry_run=False)`
- `color_version_delete_impl(clip_index, name, version_type=0, dry_run=False)`
- `color_version_rename_impl(clip_index, old_name, new_name, version_type=0, dry_run=False)`
- CLI: version グループに `load`, `delete`, `rename` 追加
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_color.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add color.version.load/delete/rename (API audit)"
```

---

### Task 12: clip.enable / clip.color.set / clip.color.clear / clip.flag.add / clip.flag.list / clip.flag.clear

**Files:**
- Modify: `src/davinci_cli/commands/clip.py`
- Modify: `tests/unit/test_clip.py`

**Step 1: 失敗するテストを書く**
- `TestClipAttributesImpl`:
  - `test_clip_enable_get`: `GetClipEnabled()` → `{"enabled": True, ...}`
  - `test_clip_enable_set`: `SetClipEnabled(True)` → `{"set": True, ...}`
  - `test_clip_color_set`: `SetClipColor("Orange")` → `{"set": True, "color": "Orange"}`
  - `test_clip_color_clear`: `ClearClipColor()` → `{"cleared": True}`
  - `test_clip_flag_add`: `AddFlag("Blue")` → `{"added": True, "color": "Blue"}`
  - `test_clip_flag_list`: `GetFlagList()` → リスト
  - `test_clip_flag_clear`: `ClearFlags("Blue")` → `{"cleared": True}`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_clip.py::TestClipAttributesImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `clip_enable_impl(index, enabled=None)`: get/set 兼用
- `clip_color_set_impl(index, color)`: `SetClipColor(color)`
- `clip_color_clear_impl(index)`: `ClearClipColor()`
- `clip_flag_add_impl(index, color)`: `AddFlag(color)`
- `clip_flag_list_impl(index)`: `GetFlagList()`
- `clip_flag_clear_impl(index, color=None)`: `ClearFlags(color)`
- CLI: `@clip.command(name="enable")`, `@clip.group(name="color")` → `set`/`clear`, `@clip.group(name="flag")` → `add`/`list`/`clear`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_clip.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add clip.enable/color/flag attribute commands (API audit)"
```

---

## Batch 5: Graph 操作（6件）

### Task 13: _get_node_graph ヘルパー + color.node.lut.set / color.node.lut.get / color.node.enable

**Files:**
- Modify: `src/davinci_cli/commands/color.py`
- Modify: `tests/unit/test_color.py`

**Step 1: 失敗するテストを書く**
- `TestGraphOperationsImpl`:
  - `test_get_node_graph_helper`: ヘルパーが `TimelineItem.GetNodeGraph()` を呼ぶことを検証
  - `test_node_lut_set_dry_run` / `test_node_lut_set`: `Graph.SetLUT(nodeIndex, lutPath)`
  - `test_node_lut_get`: `Graph.GetLUT(nodeIndex)` → `{"lut_path": "..."}`
  - `test_node_enable_set`: `Graph.SetNodeEnabled(nodeIndex, True)` → `{"set": True, ...}`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_color.py::TestGraphOperationsImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `_get_node_graph(tl, clip_index)` ヘルパー: `_get_clip_item_by_index` → `item.GetNodeGraph()`
- `node_lut_set_impl(clip_index, node_index, lut_path, dry_run=False)`:
  - `validate_path(lut_path, allowed_extensions=_LUT_EXTENSIONS)` + `Graph.SetLUT(nodeIndex, lutPath)`
- `node_lut_get_impl(clip_index, node_index)`: `Graph.GetLUT(nodeIndex)`
- `node_enable_impl(clip_index, node_index, enabled, dry_run=False)`: `Graph.SetNodeEnabled(nodeIndex, enabled)`
- CLI: `@color_node.group(name="lut")` → `set`/`get`; `@color_node.command(name="enable")`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_color.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add Graph-based node.lut.set/get and node.enable (API audit)"
```

---

### Task 14: color.cdl.set / color.lut.export / color.reset-all

**Files:**
- Modify: `src/davinci_cli/commands/color.py`
- Modify: `tests/unit/test_color.py`

**Step 1: 失敗するテストを書く**
- `TestColorExtendedImpl`:
  - `test_cdl_set_dry_run` / `test_cdl_set`: `TimelineItem.SetCDL({"NodeIndex": ..., "Slope": ..., "Offset": ..., "Power": ..., "Saturation": ...})`
  - `test_lut_export_dry_run` / `test_lut_export`: `TimelineItem.ExportLUT(exportType, path)` → `{"exported": path}`
  - `test_reset_all_dry_run` / `test_reset_all`: `Graph.ResetAllGrades()` → `{"reset": True}`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_color.py::TestColorExtendedImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `color_cdl_set_impl(clip_index, node_index, slope, offset, power, saturation, dry_run=False)`:
  - `TimelineItem.SetCDL({"NodeIndex": node_index, "Slope": slope, "Offset": offset, "Power": power, "Saturation": saturation})`
- `color_lut_export_impl(clip_index, export_type, path, dry_run=False)`:
  - `validate_path(path)` + `TimelineItem.ExportLUT(exportType, path)`
- `color_reset_all_impl(clip_index, dry_run=False)`:
  - `_get_node_graph()` → `Graph.ResetAllGrades()`
- CLI: `@color.command(name="cdl")`, `@color.command(name="lut-export")`, `@color.command(name="reset-all")`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_color.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add color.cdl.set, color.lut-export, color.reset-all (API audit)"
```

---

## Batch 6: レンダリング拡張（8件）

### Task 15: deliver.delete-job / deliver.delete-all-jobs / deliver.job-status / deliver.is-rendering

**Files:**
- Modify: `src/davinci_cli/commands/deliver.py`
- Modify: `tests/unit/test_deliver.py`

**Step 1: 失敗するテストを書く**
- `TestDeliverExtendedImpl`:
  - `test_delete_job_dry_run` / `test_delete_job`: `Project.DeleteRenderJob(jobId)`
  - `test_delete_all_jobs_dry_run` / `test_delete_all_jobs`: `Project.DeleteAllRenderJobs()`
  - `test_job_status`: `Project.GetRenderJobStatus(jobId)` → `{"status": "...", ...}`
  - `test_is_rendering`: `Project.IsRenderingInProgress()` → `{"rendering": True/False}`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_deliver.py::TestDeliverExtendedImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `deliver_delete_job_impl(job_id, dry_run=False)`: `Project.DeleteRenderJob(jobId)`
- `deliver_delete_all_jobs_impl(dry_run=False)`: `Project.DeleteAllRenderJobs()`
- `deliver_job_status_impl(job_id)`: `Project.GetRenderJobStatus(jobId)`
- `deliver_is_rendering_impl()`: `Project.IsRenderingInProgress()`
- CLI: 4コマンド追加 + Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_deliver.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add deliver.delete-job/delete-all-jobs/job-status/is-rendering (API audit)"
```

---

### Task 16: deliver.format.list / deliver.codec.list / deliver.preset.import / deliver.preset.export

**Files:**
- Modify: `src/davinci_cli/commands/deliver.py`
- Modify: `tests/unit/test_deliver.py`

**Step 1: 失敗するテストを書く**
- `TestDeliverFormatsImpl`:
  - `test_format_list`: `Project.GetRenderFormats()` → リスト
  - `test_codec_list`: `Project.GetRenderCodecs(format)` → リスト
  - `test_preset_import_dry_run` / `test_preset_import`: `Resolve.ImportRenderPreset(path)`
  - `test_preset_export_dry_run` / `test_preset_export`: `Resolve.ExportRenderPreset(name, path)`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_deliver.py::TestDeliverFormatsImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `deliver_format_list_impl()`: `Project.GetRenderFormats()`
- `deliver_codec_list_impl(format_name)`: `Project.GetRenderCodecs(format_name)`
- `deliver_preset_import_impl(path, dry_run=False)`: `validate_path(path)` + `Resolve.ImportRenderPreset(path)`
- `deliver_preset_export_impl(name, path, dry_run=False)`: `Resolve.ExportRenderPreset(name, path)`
- CLI: `@deliver.group(name="format")` → `list`; `@deliver.group(name="codec")` → `list`
- preset グループに `import`/`export` 追加
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_deliver.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add deliver.format.list/codec.list/preset.import/export (API audit)"
```

---

## Batch 7: Gallery + MediaPool 拡張（15件）

### Task 17: gallery.py モジュール作成 + gallery.album.list / gallery.album.current / gallery.album.set / gallery.album.create

**Files:**
- Create: `src/davinci_cli/commands/gallery.py`
- Create: `tests/unit/test_gallery.py`
- Modify: `src/davinci_cli/cli.py` (gallery コマンド登録)
- Modify: `src/davinci_cli/commands/__init__.py`

**Step 1: 失敗するテストを書く**
- `TestGalleryAlbumImpl`:
  - `test_album_list`: `Gallery.GetGalleryStillAlbums()` → アルバムリスト（各 `GetAlbumName()` を呼ぶ）
  - `test_album_current`: `Gallery.GetCurrentStillAlbum()` + `GetAlbumName()` → `{"name": "..."}`
  - `test_album_set_dry_run` / `test_album_set`: `Gallery.SetCurrentStillAlbum(album)`
  - `test_album_create_dry_run` / `test_album_create`: `Gallery.CreateGalleryStillAlbum()`
- mock: `Gallery`, `GalleryStillAlbum` のモックを構築

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_gallery.py -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `gallery.py` 新規作成:
  - `_get_gallery()` ヘルパー: `Project.GetGallery()`
  - `gallery_album_list_impl()`, `gallery_album_current_impl()`
  - `gallery_album_set_impl(name, dry_run=False)`, `gallery_album_create_impl(name=None, dry_run=False)`
  - CLI: `@click.group() def gallery`, `@gallery.group(name="album")` → `list`, `current`, `set`, `create`
  - Pydantic モデル + schema 登録
- `cli.py`: `from davinci_cli.commands import gallery` + `dr.add_command(gallery.gallery)`
- `commands/__init__.py` に gallery を追加

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_gallery.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add gallery module with album.list/current/set/create (API audit)"
```

---

### Task 18: gallery.still.export / gallery.still.import / gallery.still.delete

**Files:**
- Modify: `src/davinci_cli/commands/gallery.py`
- Modify: `tests/unit/test_gallery.py`

**Step 1: 失敗するテストを書く**
- `TestGalleryStillImpl`:
  - `test_still_export_dry_run` / `test_still_export`: `GalleryStillAlbum.ExportStills(stills, path, ...)`
  - `test_still_import_dry_run` / `test_still_import`: `GalleryStillAlbum.ImportStills([paths])`
  - `test_still_delete_dry_run` / `test_still_delete`: `GalleryStillAlbum.DeleteStills([stills])`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_gallery.py::TestGalleryStillImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `gallery_still_export_impl(path, format="dpx", dry_run=False)`: 現在のアルバムの全スチルをエクスポート
- `gallery_still_import_impl(paths: list[str], dry_run=False)`: `validate_path` 後 `ImportStills`
- `gallery_still_delete_impl(still_indices: list[int], dry_run=False)`: インデックスでスチル取得 → `DeleteStills`
- CLI: `@gallery.group(name="still")` → `export`, `import`, `delete`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_gallery.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add gallery.still.export/import/delete (API audit)"
```

---

### Task 19: media.move / media.delete / media.relink / media.unlink

**Files:**
- Modify: `src/davinci_cli/commands/media.py`
- Modify: `tests/unit/test_media.py`

**Step 1: 失敗するテストを書く**
- `TestMediaExtendedImpl`:
  - `test_media_move_dry_run` / `test_media_move`: `MediaPool.MoveClips([clips], targetFolder)`
  - `test_media_delete_dry_run` / `test_media_delete`: `MediaPool.DeleteClips([clips])`
  - `test_media_relink_dry_run` / `test_media_relink`: `MediaPool.RelinkClips([items], folderPath)`
  - `test_media_unlink`: `MediaPool.UnlinkClips([items])`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_media.py::TestMediaExtendedImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `media_move_impl(clip_names: list[str], target_folder: str, dry_run=False)`:
  - クリップ名でクリップを検索 → `MediaPool.MoveClips([clips], folder)`
- `media_delete_impl(clip_names: list[str], dry_run=False)`: `MediaPool.DeleteClips([clips])`
- `media_relink_impl(clip_names: list[str], folder_path: str, dry_run=False)`:
  - `validate_path(folder_path)` + `MediaPool.RelinkClips([items], folderPath)`
- `media_unlink_impl(clip_names: list[str])`: `MediaPool.UnlinkClips([items])`
- CLI: `@media.command(name="move")`, `delete`, `relink`, `unlink` + `--dry-run` (move/delete/relink)
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_media.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add media.move/delete/relink/unlink (API audit)"
```

---

### Task 20: media.metadata.get / media.metadata.set / media.export-metadata / media.transcribe

**Files:**
- Modify: `src/davinci_cli/commands/media.py`
- Modify: `tests/unit/test_media.py`

**Step 1: 失敗するテストを書く**
- `TestMediaMetadataImpl`:
  - `test_metadata_get`: `MediaPoolItem.GetMetadata()` → dict
  - `test_metadata_get_with_key`: `MediaPoolItem.GetMetadata(key)` → `{"key": ..., "value": ...}`
  - `test_metadata_set`: `MediaPoolItem.SetMetadata(key, value)` → `{"set": True, ...}`
  - `test_export_metadata_dry_run` / `test_export_metadata`: `MediaPool.ExportMetadata(fileName)`
  - `test_transcribe`: `MediaPoolItem.TranscribeAudio()` or `Folder.TranscribeAudio()`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_media.py::TestMediaMetadataImpl -v`
Expected: FAIL

**Step 3: 最小限の実装**
- `media_metadata_get_impl(clip_name, key=None)`: クリップ検索 → `GetMetadata()` or `GetMetadata(key)`
- `media_metadata_set_impl(clip_name, key, value, dry_run=False)`: `SetMetadata(key, value)`
- `media_export_metadata_impl(file_name, dry_run=False)`: `validate_path` + `MediaPool.ExportMetadata(fileName)`
- `media_transcribe_impl(clip_name=None, folder_name=None)`: クリップまたはフォルダの `TranscribeAudio()`
- CLI: `@media.group(name="metadata")` → `get`/`set`; `@media.command(name="export-metadata")`; `@media.command(name="transcribe")`
- Pydantic モデル + schema 登録

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_media.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: add media.metadata.get/set, export-metadata, transcribe (API audit)"
```

---

## Batch 8: MCP サーバー全更新 + CLAUDE.md + E2E テスト

### Task 21: color.still.list/grab を gallery に移行整理

**Files:**
- Modify: `src/davinci_cli/commands/color.py` (still_list/grab の _impl をキープし、deprecation warning 追加 or gallery から呼び出し)
- Modify: `src/davinci_cli/commands/gallery.py` (still.list を統合)

**Step 1: テストを書く**
- `color.still.list` と `gallery.still.*` の整合性テスト
- `color.still.grab` が gallery 側からも利用可能なことを確認

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_color.py tests/unit/test_gallery.py -v`
Expected: FAIL

**Step 3: 実装**
- `gallery.py` に `still_list_impl`/`still_grab_impl` を移動（or color から再エクスポート）
- `color.py` の `still.list`/`still.grab` は維持（後方互換）
- gallery に `still list`/`still grab` コマンドも追加

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_color.py tests/unit/test_gallery.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "refactor: consolidate still operations in gallery module (API audit)"
```

---

### Task 22: MCP サーバー全更新

**Files:**
- Modify: `src/davinci_cli/mcp/mcp_server.py`
- Modify: `tests/unit/test_mcp_server.py`

**Step 1: テストを書く**
- 全新規コマンドの MCP ツール登録テスト:
  - ツール名が `mcp.tools` に含まれることを確認
  - 各ツールが `mcp_error_handler` でラップされていることを確認
  - 破壊的操作は `dry_run=True` がデフォルトであることを確認
- バッチごとにグループ化: system(4), project(1), timeline(11), clip(6), color(9), deliver(8), gallery(7), media(8)

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_mcp_server.py -v`
Expected: FAIL

**Step 3: 最小限の実装**
- 全新規 `_impl` 関数を import
- 各コマンドに対して `@mcp.tool()` + `@mcp_error_handler` でラップ
- description に AGENT RULES を埋め込む
- 破壊的操作は `dry_run: bool = True` デフォルト
- 削除済みコマンド（node.add/delete, paste-grade, still.apply）のMCPツールが存在しないことも確認

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_mcp_server.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "feat: update MCP server with all new API audit commands"
```

---

### Task 23: CLAUDE.md 更新

**Files:**
- Modify: `CLAUDE.md`

**Step 1: テストを書く**
- `test_skill_md.py` に CLAUDE.md のコマンド一覧が実際の CLI コマンドと一致するテスト追加（既存パターンがあれば拡張）

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_skill_md.py -v`
Expected: FAIL

**Step 3: 最小限の実装**
- CLAUDE.md のコマンド一覧セクションを更新:
  - 削除した4コマンドを除去
  - 新規追加コマンド（約50件）を追加
  - gallery グループを追加
  - コマンド総数を更新（51 - 4 + ~50 = ~97コマンド）
- Architecture セクションの commands 一覧に `gallery.py` を追加

**Step 4: 通過を確認**
Run: `python -m pytest tests/unit/test_skill_md.py -v`
Expected: PASS

**Step 5: コミット**
```
git commit -m "docs: update CLAUDE.md with API audit command changes"
```

---

### Task 24: E2E テスト（MockResolve ベース）

**Files:**
- Modify: `tests/unit/test_cli.py` (または新規 `tests/e2e/test_e2e_api_audit.py`)

**Step 1: テストを書く**
- CliRunner で全新規コマンドの基本動作を検証:
  - 各コマンドの `--dry-run` が exit_code=0 で動作
  - 出力が valid JSON であること
  - 必須引数欠落時の適切なエラー
- グループ別にテストクラスを分割:
  - `TestE2ESystemPage`, `TestE2ETimelineTrack`, `TestE2EColorVersion`,
  - `TestE2EClipAttributes`, `TestE2EGraphOps`, `TestE2EDeliverExtended`,
  - `TestE2EGallery`, `TestE2EMediaExtended`

**Step 2: 失敗を確認**
Run: `python -m pytest tests/unit/test_cli.py -v` (新規テストクラスのみ)
Expected: PASS（全コマンドは既に実装済み）

**Step 3: テスト実行で全て通過を確認**
Run: `python -m pytest tests/unit/ -v`
Expected: ALL PASS

**Step 4: コミット**
```
git commit -m "test: E2E smoke tests for all API audit commands"
```

---

## 全体回帰テスト

全バッチ完了後:

```bash
python -m pytest tests/unit/ -v --tb=short
```

全テストが PASS であることを確認してから完了とする。
