# API 戻り値チェック設計書

**日付**: 2026-03-09
**ステータス**: 設計完了
**対象**: DaVinci Resolve API の戻り値未チェックによる嘘の成功報告バグ 10 件

---

## 1. 問題の概要

共通パターン: `_impl` 関数が DaVinci Resolve API を呼び出した後、戻り値を検証せずに成功レスポンスを返す。API が `False` や `None` を返して失敗を示しても、エージェントには `{"added": true}` 等の嘘の成功が報告される。

---

## 2. アプローチ比較

| 観点 | A: 個別チェック | B: 共通ラッパー関数 | C: デコレータ |
|------|----------------|---------------------|--------------|
| **概要** | 各 `_impl` 関数内で API 戻り値を `if not result` でチェック | `call_resolve_api(obj, method, *args, error_field, error_reason)` ヘルパー | `@check_return` デコレータで自動チェック |
| **変更量** | 小（各箇所 2-4 行追加） | 中（ヘルパー関数 + 各箇所の書き換え） | 大（デコレータ + メタデータ管理） |
| **可読性** | 高 — 何をチェックしているか一目瞭然 | 中 — 抽象化が増える | 低 — マジックが多い |
| **既存テストへの影響** | 最小 — モックの戻り値を設定するだけ | 中 — ヘルパー経由に変わるためテスト構造変更 | 大 — デコレータ対応が必要 |
| **エラーメッセージの柔軟性** | 高 — 各箇所で最適なメッセージ | 低 — 汎用メッセージになりがち | 低 |
| **バッチ操作の対応** | 自然 — ループ内で個別チェック | 不自然 — ラッパーが部分成功を扱えない | 不可能 |
| **YAGNI 準拠** | 最善 | API 呼び出しパターンが統一的でないため過剰 | 明確に過剰 |

### 推奨: アプローチ A（個別チェック）

**理由:**
1. DaVinci Resolve API の戻り値パターンが統一されていない（`bool`, `None`, オブジェクト等）。共通ラッパーは抽象化漏れを起こす
2. バッチ操作の部分成功は個別ループでしか正確にカウントできない
3. 既存テストへの影響が最小（モックの `return_value` 設定追加のみ）
4. 各バグの修正が独立しており、レビューしやすい

---

## 3. 推奨アプローチ詳細設計

### 3.1 修正パターン

全バグに共通する修正テンプレート:

```python
# 変更前（単発操作）
api_object.SomeMethod(args)
return {"success": True, ...}

# 変更後（単発操作）
result = api_object.SomeMethod(args)
if not result:
    raise ValidationError(
        field="<操作対象のフィールド名>",
        reason="<API名> failed: <状況の説明>"
    )
return {"success": True, ...}
```

```python
# 変更前（バッチ操作）
for item in items:
    api_object.SomeMethod(item)
return {"count": len(items)}

# 変更後（バッチ操作）
success_count = 0
for item in items:
    if api_object.SomeMethod(item):
        success_count += 1
return {"added_count": success_count, "requested_count": len(items)}
```

### 3.2 各バグの具体的修正

---

#### Bug #1: deliver start (`deliver.py:258-267`) — HIGH

**問題点 2 つ:**
- (a) `StartRendering()` の戻り値未チェック
- (b) `ValidationError(f"...")` — `field` 引数なしで TypeError

**変更前:**
```python
project = _get_current_project()
if job_ids:
    validated_ids = [j["job_id"] for j in jobs]
    if not validated_ids:
        raise ValidationError(f"No matching jobs found for IDs: {job_ids}")
    for jid in validated_ids:
        project.StartRendering(jid)
else:
    project.StartRendering()
return {"rendering_started": True, "job_count": len(jobs)}
```

**変更後:**
```python
project = _get_current_project()
if job_ids:
    validated_ids = [j["job_id"] for j in jobs]
    if not validated_ids:
        raise ValidationError(
            field="job_ids",
            reason=f"No matching jobs found for IDs: {job_ids}",
        )
    failed_ids = []
    for jid in validated_ids:
        if not project.StartRendering(jid):
            failed_ids.append(jid)
    if failed_ids and len(failed_ids) == len(validated_ids):
        raise ValidationError(
            field="job_ids",
            reason=f"StartRendering failed for all jobs: {failed_ids}",
        )
    return {
        "rendering_started": True,
        "job_count": len(validated_ids) - len(failed_ids),
        "failed_ids": failed_ids if failed_ids else None,
    }
else:
    if not jobs:
        raise ValidationError(
            field="job_ids",
            reason="No render jobs exist. Add jobs before starting.",
        )
    result = project.StartRendering()
    if not result:
        raise ValidationError(
            field="render",
            reason="StartRendering failed. Check render job configuration.",
        )
    return {"rendering_started": True, "job_count": len(jobs)}
```

**ポイント:**
- `ValidationError` の TypeError バグを修正（`field=`, `reason=` を明示）
- ジョブ 0 件で開始しようとした場合のガード追加
- 個別 job_id 指定時の部分成功レポート

---

#### Bug #2: marker add (`timeline.py:421`) — HIGH

**変更前:**
```python
tl.AddMarker(rel_frame, color, name, note or "", duration)
return {"added": True, "frame_id": frame_id}
```

**変更後:**
```python
result = tl.AddMarker(rel_frame, color, name, note or "", duration)
if not result:
    raise ValidationError(
        field="frame_id",
        reason=f"AddMarker failed at frame {frame_id}. "
        "Possible causes: duplicate frame, empty name, or invalid color.",
    )
return {"added": True, "frame_id": frame_id}
```

---

#### Bug #3: marker delete (`timeline.py:438`) — HIGH

**変更前:**
```python
tl.DeleteMarkerAtFrame(rel_frame)
return {"deleted": True, "frame_id": frame_id}
```

**変更後:**
```python
result = tl.DeleteMarkerAtFrame(rel_frame)
if not result:
    raise ValidationError(
        field="frame_id",
        reason=f"No marker found at frame {frame_id}.",
    )
return {"deleted": True, "frame_id": frame_id}
```

---

#### Bug #4: beat marker (`beat_markers.py:179-190`) — HIGH

**変更前:**
```python
for frame_abs in frames:
    rel_frame = frame_abs - offset
    tl.AddMarker(rel_frame, color, marker_name, "", duration)

return {
    "added_count": len(frames),
    ...
}
```

**変更後:**
```python
added_count = 0
failed_frames = []
for frame_abs in frames:
    rel_frame = frame_abs - offset
    if tl.AddMarker(rel_frame, color, marker_name, "", duration):
        added_count += 1
    else:
        failed_frames.append(frame_abs)

result = {
    "added_count": added_count,
    "requested_count": len(frames),
    ...
}
if failed_frames:
    result["failed_frames"] = failed_frames
return result
```

**ポイント:** バッチ操作なので例外ではなく部分成功レポート。`added_count` は実際の成功数を反映。

---

#### Bug #5: project close (`project.py:152`) — MEDIUM

**変更前:**
```python
pm.CloseProject(pm.GetCurrentProject())
return {"closed": True}
```

**変更後:**
```python
current = pm.GetCurrentProject()
if not current:
    raise ProjectNotOpenError()
result = pm.CloseProject(current)
if not result:
    raise ValidationError(
        field="project",
        reason="CloseProject failed. The project may have unsaved changes.",
    )
return {"closed": True}
```

---

#### Bug #6: project settings set (`project.py:229`) — MEDIUM

**変更前:**
```python
project.SetSetting(key, value)
return {"set": True, "key": key, "value": value}
```

**変更後:**
```python
result = project.SetSetting(key, value)
if not result:
    raise ValidationError(
        field="key",
        reason=f"SetSetting failed for key '{key}'. "
        "The key may be invalid or the value may be out of range.",
    )
return {"set": True, "key": key, "value": value}
```

---

#### Bug #7: media metadata set (`media.py:388`) — MEDIUM

**変更前:**
```python
clip.SetMetadata(key, value)
return {
    "clip_name": clip_name,
    "key": key,
    "value": value,
}
```

**変更後:**
```python
result = clip.SetMetadata(key, value)
if not result:
    raise ValidationError(
        field="key",
        reason=f"SetMetadata failed for key '{key}' on clip '{clip_name}'. "
        "The metadata key may be read-only or invalid.",
    )
return {
    "clip_name": clip_name,
    "key": key,
    "value": value,
}
```

---

#### Bug #8: color still grab (`color.py:352`) — LOW

**変更前:**
```python
tl.GrabStill()
return {"grabbed": True, "clip_index": clip_index}
```

**変更後:**
```python
result = tl.GrabStill()
if not result:
    raise ValidationError(
        field="clip_index",
        reason=f"GrabStill failed for clip at index {clip_index}. "
        "Ensure the Color page is active.",
    )
return {"grabbed": True, "clip_index": clip_index}
```

---

#### Bug #9: gallery still export (`gallery.py:179`) — LOW

**現状:** 既に `if result is False` チェックがある。ただし `ExportStills` API が常に失敗する問題は API 引数の調査が必要。

**対応:** 実機調査タスクとして別途追跡。現状のエラーハンドリングコードは正しいため、コード変更は不要。調査結果に応じて API 呼び出し引数を修正する。

---

#### Bug #10: media 系バッチ操作 (`media.py` 複数箇所) — LOW

対象メソッド: `DeleteFolders`, `MoveClips`, `DeleteClips`, `RelinkClips`, `UnlinkClips`

**共通パターン — 変更後:**

```python
# DeleteFolders (media_folder_delete_impl)
result = media_pool.DeleteFolders([folder])
if not result:
    raise ValidationError(
        field="name",
        reason=f"DeleteFolders failed for folder: {name}",
    )
return {"deleted": name}

# MoveClips (media_move_impl)
result = media_pool.MoveClips(clips, target)
if not result:
    raise ValidationError(
        field="clip_names",
        reason=f"MoveClips failed. Some clips may not have been moved.",
    )
return {"moved_count": len(clips), ...}

# DeleteClips (media_delete_impl)
result = media_pool.DeleteClips(clips)
if not result:
    raise ValidationError(
        field="clip_names",
        reason="DeleteClips failed. Some clips may be in use on a timeline.",
    )
return {"deleted_count": len(clips), ...}

# RelinkClips (media_relink_impl)
result = media_pool.RelinkClips(clips, validated_path)
if not result:
    raise ValidationError(
        field="folder_path",
        reason=f"RelinkClips failed. Check that the path exists and contains matching media.",
    )
return {"relinked_count": len(clips), ...}

# UnlinkClips (media_unlink_impl)
result = media_pool.UnlinkClips(clips)
if not result:
    raise ValidationError(
        field="clip_names",
        reason="UnlinkClips failed.",
    )
return {"unlinked_count": len(clips), ...}
```

**注意:** これらの API はバッチ操作だが、DaVinci Resolve API は全体で `True/False` を返す（個別結果ではない）。よって部分成功の詳細は取得不可。全体成功/失敗のみ報告する。

---

### 3.3 エラーメッセージ統一フォーマット

```
ValidationError(
    field="<操作対象のフィールド名>",
    reason="<API名> failed [for <対象>]. <原因のヒント>."
)
```

**フィールド名の規約:**
- 入力パラメータ名を使用（`frame_id`, `key`, `clip_names`, `job_ids` 等）
- 入力に対応しない場合は操作名（`render`, `project`）

**reason の規約:**
- 先頭は API メソッド名 or 動作（`AddMarker failed`, `CloseProject failed`）
- 可能な原因のヒントを付加（エージェントが次のアクションを判断できるように）
- 英語で統一（既存パターンに準拠）

---

### 3.4 テスト戦略

#### テスト追加方針

各バグ修正に対して以下の 2 パターンのテストを追加:

1. **API 成功時** — モックが `True` を返す → 既存の成功レスポンスが返る（既存テストの一部を修正）
2. **API 失敗時** — モックが `False` を返す → `ValidationError` が raise される

#### モック設計

既存テストはほとんどがモックの `return_value` を設定していない（デフォルトは `MagicMock()` で truthy）。よって:

- **既存テストはそのまま通る** — `MagicMock()` は truthy なので `if not result` は `False` → 成功パス
- **失敗テストを追加** — `mock.SomeMethod.return_value = False` を設定

#### テストファイル配置

既存のテストファイルに追加（新規ファイルは作らない）:

| バグ | テストファイル | 追加テストクラス/メソッド |
|------|---------------|------------------------|
| #1 | `test_deliver.py` | `TestDeliverStartImpl.test_start_fails_when_no_jobs`, `test_start_rendering_returns_false`, `test_start_validation_error_has_field` |
| #2 | `test_timeline.py` | `TestMarkerImpl.test_marker_add_fails_returns_validation_error` |
| #3 | `test_timeline.py` | `TestMarkerImpl.test_marker_delete_fails_returns_validation_error` |
| #4 | `test_beat_markers.py` | `TestBeatMarkerImpl.test_partial_success_reports_actual_count` |
| #5 | `test_project.py` | `TestProjectCloseImpl.test_close_no_project_raises`, `test_close_api_fails_raises` |
| #6 | `test_project.py` | `TestProjectSettingsImpl.test_set_invalid_key_raises` (新クラス) |
| #7 | `test_media.py` | `TestMediaMetadata.test_set_returns_false_raises` |
| #8 | `test_color.py` | `TestStillGrab.test_grab_fails_raises` (新クラス) |
| #9 | — | 調査タスク（テスト追加なし） |
| #10 | `test_media.py` | `TestMediaBatchOps.test_delete_clips_fails`, `test_move_clips_fails`, 等 (新クラス) |

#### 既存テストへの影響

- `test_marker_add_converts_absolute_to_relative`: モックの `AddMarker` は `MagicMock()` を返すため **変更不要**（truthy）
- `test_marker_delete_converts_absolute_to_relative`: 同上、**変更不要**
- `test_close_project`: モックの `CloseProject` は `MagicMock()` を返すため **変更不要**
  - ただし `GetCurrentProject()` が `None` を返すケースの新テストが必要
- `test_metadata_set`: モックで `SetMetadata.return_value = True` を既に設定済み → **変更不要**
- `test_deliver_start_dry_run`: dry_run パスなので **変更不要**

**結論: 既存テストへのデグレなし。**

---

## 4. バッチ分割計画（実装順序）

### Batch 1: HIGH — deliver start + ValidationError TypeError 修正
**ファイル:** `deliver.py`
**コミットメッセージ:** `fix: deliver start の戻り値チェック追加と ValidationError の TypeError 修正`
**理由:** TypeError は実行時クラッシュなので最優先。deliver start のロジック修正と一体。

### Batch 2: HIGH — marker add / delete 戻り値チェック
**ファイル:** `timeline.py`
**コミットメッセージ:** `fix: marker add/delete の API 戻り値チェック追加`
**理由:** 同一ファイル・同一パターン。まとめて修正。

### Batch 3: HIGH — beat marker 部分成功カウント
**ファイル:** `beat_markers.py`
**コミットメッセージ:** `fix: beat marker の added_count を実際の成功数に修正`
**理由:** marker 系の修正後に着手（marker add の挙動理解が前提）。

### Batch 4: MEDIUM — project close / settings set
**ファイル:** `project.py`
**コミットメッセージ:** `fix: project close/settings set の API 戻り値チェック追加`
**理由:** 同一ファイル。

### Batch 5: MEDIUM + LOW — media metadata set + バッチ操作
**ファイル:** `media.py`
**コミットメッセージ:** `fix: media 系 API の戻り値チェック追加`
**理由:** 同一ファイル内の全修正をまとめる。

### Batch 6: LOW — color still grab
**ファイル:** `color.py`
**コミットメッセージ:** `fix: GrabStill の戻り値チェック追加`

### 各 Batch の作業手順（TDD サイクル）

1. 失敗テストを書く（API が `False` を返す → `ValidationError` を期待）
2. テスト実行 → Red 確認
3. `_impl` 関数を修正
4. テスト実行 → Green 確認
5. 既存テスト全実行 → デグレなし確認
6. コミット

---

## 5. 不確実な点・要確認事項

| # | 項目 | 影響 | 対応案 |
|---|------|------|--------|
| 1 | `StartRendering(job_id)` の戻り値の型 | HIGH — `bool` か `None` か不明 | 実機確認。`not result` で両方カバーできるが、ドキュメント化する |
| 2 | `ExportStills` が常に失敗する件 (Bug #9) | LOW — 別タスク | API 引数調査を別イシューで追跡。現コードのエラーハンドリングは正しい |
| 3 | バッチ API (`MoveClips` 等) が部分成功時に何を返すか | MEDIUM — `True/False` のみか、成功数か | 実機確認。現設計は `True/False` 前提。部分成功の詳細が取れるなら拡張可能 |
| 4 | `CloseProject` が `False` を返す条件 | LOW | 未保存変更時？ 実機確認して reason メッセージを改善 |
| 5 | 既存の MCP テスト (`test_mcp_server.py`) への影響 | LOW | MCP ラッパーは `_impl` を呼ぶだけなので、`_impl` のモックが正しければ影響なし |
