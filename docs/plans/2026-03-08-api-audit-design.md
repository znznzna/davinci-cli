# API Audit Design — davinci-cli コマンド整理

> 作成日: 2026-03-08
> ステータス: Draft (承認待ち)

## 1. 背景

davinci-cli は DaVinci Resolve Python API をラップする CLI / MCP サーバーである。現在 45 コマンドが実装されているが、公式 API (DaVinci Resolve Studio v20.3 README.txt) との照合により以下の問題が判明した。

1. **存在しない API を呼ぶコマンドが 4 件ある** — 実行すると常にエラー
2. **CopyGrades() の使い方が間違っている** — 引数なしで呼んでいるが、正しくはターゲットリストを渡す
3. **公式 API に存在するが CLI コマンドが未実装のメソッドが多数ある**

## 2. アプローチ比較

| 観点 | A: 最小限 | B: 中程度 (推奨) | C: 網羅的 |
|------|-----------|-------------------|-----------|
| **削除** | 4 件 | 4 件 | 4 件 |
| **バグ修正** | CopyGrades 1 件 | CopyGrades 1 件 | CopyGrades 1 件 |
| **新規追加** | 0 件 | 約 30 件 | 約 70 件 |
| **工数 (人日)** | 1-2 日 | 7-10 日 | 20-30 日 |
| **リスク** | 低 | 中 | 高 |
| **エージェント有用性** | 現状維持 | 大幅向上 | 最大だが保守コスト大 |

### アプローチ A: 最小限

- 削除 4 件 + CopyGrades バグ修正のみ
- メリット: 最速でリリース可能、デグレリスク最小
- デメリット: エージェントの操作範囲が変わらない。ページ切り替え、トラック管理、バージョン管理など基本的な操作ができないまま

### アプローチ B: 中程度 (推奨)

- 削除 4 件 + バグ修正 + AIエージェントにとって最も有用なコマンドを優先追加
- 選定基準: (1) エージェントワークフローで頻出する操作、(2) 他コマンドとの組み合わせで価値が出る操作、(3) API が安定しているもの
- メリット: エージェントの実用性が大幅に向上。段階的にリリース可能
- デメリット: 全 API はカバーしない（Fusion、MediaStorage 等は対象外）

### アプローチ C: 網羅的

- 公式 API の全メソッドをカバー
- メリット: API の完全なラッパーとなる
- デメリット: 使用頻度の低い API まで実装・テスト・保守する必要がある。Fusion API や MediaStorage のファイルシステム操作など、エージェントユースケースが不明確なものも含む

## 3. 推奨: アプローチ B 詳細設計

### 3.1 削除するコマンド (4 件)

| コマンド | 理由 | 影響範囲 |
|----------|------|----------|
| `color.node.add` | `AddNode()` API が存在しない | CLI, MCP, schema, tests, SKILL.md |
| `color.node.delete` | `DeleteNode()` API が存在しない | CLI, MCP, schema, tests, SKILL.md |
| `color.paste-grade` | `PasteGrades()` API が存在しない。CopyGrades が直接コピーする | CLI, MCP, schema, tests, SKILL.md |
| `color.still.apply` | `ApplyGradeFromStill()` API が存在しない | CLI, MCP, schema, tests, SKILL.md |

#### 削除時の作業チェックリスト (各コマンド共通)

1. `src/davinci_cli/commands/color.py` — `_impl` 関数、CLI コマンド、Pydantic モデルを削除
2. `src/davinci_cli/commands/color.py` — `register_schema()` 呼び出しを削除
3. `src/davinci_cli/mcp_server.py` — 対応する MCP ツール登録を削除 (存在する場合)
4. `tests/unit/test_color.py` — 対応するテストを削除
5. `SKILL.md` — コマンド一覧から削除
6. `CLAUDE.md` — Architecture セクションのコマンド数を更新

### 3.2 バグ修正: CopyGrades() の API 修正

#### 現在の実装 (誤り)

```python
def color_copy_grade_impl(from_index: int) -> dict:
    tl = _get_current_timeline()
    clip_item = _get_clip_item_by_index(tl, from_index)
    clip_item.CopyGrades()  # ← 引数なし (誤り)
    return {"copied_from": from_index}
```

#### 正しい API

```
TimelineItem.CopyGrades([tgtTimelineItems])
```

ソースクリップからターゲットクリップリストへ直接グレードをコピーする。paste-grade は不要。

#### 修正設計

```python
# 新しいシグネチャ
def color_copy_grade_impl(
    from_index: int,
    to_indices: list[int],
    dry_run: bool = False,
) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "action": "copy_grade",
            "from_index": from_index,
            "to_indices": to_indices,
        }
    tl = _get_current_timeline()
    src_clip = _get_clip_item_by_index(tl, from_index)
    tgt_clips = [_get_clip_item_by_index(tl, i) for i in to_indices]
    result = src_clip.CopyGrades(tgt_clips)
    if result is False:
        raise ValidationError(
            field="copy_grade",
            reason="CopyGrades failed",
        )
    return {
        "copied_from": from_index,
        "copied_to": to_indices,
    }
```

#### CLI インターフェース変更

```bash
# 旧: dr color copy-grade --from 0
# 新: dr color copy-grade --from 0 --to 1,2,3 [--dry-run]
```

#### 互換性

- `--from` はそのまま
- `--to` を必須引数として追加 (カンマ区切り)
- `--dry-run` を追加 (破壊的操作のため)
- **破壊的変更**: 旧 CLI の `--from` のみの呼び出しはエラーになる

### 3.3 追加するコマンド一覧と優先度

#### Priority 1: ナビゲーション・状態確認 (エージェント必須)

| コマンド | API メソッド | 理由 |
|----------|-------------|------|
| `system.page` | `Resolve.OpenPage(pageName)` / `GetCurrentPage()` | ページ切り替えはエージェントワークフローの基本。Edit/Color/Deliver 間の遷移に必須 |
| `timeline.timecode.get` | `Timeline.GetCurrentTimecode()` | プレイヘッド位置の取得。クリップ特定に必要 |
| `timeline.timecode.set` | `Timeline.SetCurrentTimecode(timecode)` | プレイヘッド移動。特定フレームへの移動に必要 |
| `timeline.current-item` | `Timeline.GetCurrentVideoItem()` | 現在選択中のビデオアイテム取得 |

#### Priority 2: トラック管理 (タイムライン操作の拡張)

| コマンド | API メソッド | 理由 |
|----------|-------------|------|
| `timeline.track.list` | `GetTrackCount(trackType)` + `GetTrackName(trackType, idx)` | トラック一覧。クリップ操作の前提情報 |
| `timeline.track.add` | `AddTrack(trackType, subTrackType)` | トラック追加 |
| `timeline.track.delete` | `DeleteTrack(trackType, idx)` | トラック削除 |
| `timeline.track.enable` | `SetTrackEnable(trackType, idx, enabled)` / `GetIsTrackEnabled(trackType, idx)` | トラック有効/無効 |
| `timeline.track.lock` | `SetTrackLock(trackType, idx, locked)` / `GetIsTrackLocked(trackType, idx)` | トラックロック |
| `timeline.duplicate` | `DuplicateTimeline(name)` | タイムライン複製 |

#### Priority 3: カラーバージョン管理 (カラリスト向け中核機能)

| コマンド | API メソッド | 理由 |
|----------|-------------|------|
| `color.version.list` | `TimelineItem.GetVersionNameList(versionType)` | バージョン一覧 |
| `color.version.current` | `TimelineItem.GetCurrentVersion()` | 現在のバージョン取得 |
| `color.version.add` | `TimelineItem.AddVersion(versionName, versionType)` | バージョン追加 |
| `color.version.load` | `TimelineItem.LoadVersionByName(versionName, versionType)` | バージョン切り替え |
| `color.version.delete` | `TimelineItem.DeleteVersionByName(versionName, versionType)` | バージョン削除 |
| `color.version.rename` | `TimelineItem.RenameVersionByName(oldName, newName, versionType)` | バージョンリネーム |

#### Priority 4: クリップ属性操作 (エージェントの判断材料拡充)

| コマンド | API メソッド | 理由 |
|----------|-------------|------|
| `clip.enable` | `TimelineItem.SetClipEnabled(enabled)` / `GetClipEnabled()` | クリップ有効/無効 |
| `clip.color.set` | `TimelineItem.SetClipColor(color)` / `GetClipColor()` | クリップカラー設定 |
| `clip.color.clear` | `TimelineItem.ClearClipColor()` | クリップカラークリア |
| `clip.flag.add` | `TimelineItem.AddFlag(color)` | フラグ追加 |
| `clip.flag.list` | `TimelineItem.GetFlagList()` | フラグ一覧 |
| `clip.flag.clear` | `TimelineItem.ClearFlags()` | フラグクリア |

#### Priority 5: Graph オブジェクト操作 (高度なカラー操作)

| コマンド | API メソッド | 理由 |
|----------|-------------|------|
| `color.node.lut.set` | `Graph.SetLUT(nodeIndex, lutPath)` | ノード単位の LUT 設定 |
| `color.node.lut.get` | `Graph.GetLUT(nodeIndex)` | ノードの LUT パス取得 |
| `color.node.enable` | `Graph.SetNodeEnabled(nodeIndex, isEnabled)` | ノード有効/無効 |
| `color.cdl.set` | `TimelineItem.SetCDL({...})` | CDL 値設定 |
| `color.lut.export` | `TimelineItem.ExportLUT(exportType, path)` | LUT エクスポート |
| `color.reset-all` | `Graph.ResetAllGrades()` | 全グレードリセット (既存 reset より徹底的) |

#### Priority 6: レンダリング拡張

| コマンド | API メソッド | 理由 |
|----------|-------------|------|
| `deliver.delete-job` | `Project.DeleteRenderJob(jobId)` | ジョブ削除 |
| `deliver.delete-all-jobs` | `Project.DeleteAllRenderJobs()` | 全ジョブ削除 |
| `deliver.job-status` | `Project.GetRenderJobStatus(jobId)` | 個別ジョブステータス |
| `deliver.is-rendering` | `Project.IsRenderingInProgress()` | レンダリング中判定 |
| `deliver.format.list` | `Project.GetRenderFormats()` | レンダーフォーマット一覧 |
| `deliver.codec.list` | `Project.GetRenderCodecs(format)` | コーデック一覧 |

#### 対象外 (アプローチ C でのみ実装)

以下はエージェントのユースケースが不明確、または API の安定性に懸念があるため今回は対象外とする。

- **Fusion オブジェクト** — Fusion コンポジション操作は専用 UI が前提
- **MediaStorage** — ファイルシステムブラウズはエージェントが直接行える
- **Gallery アルバム管理** — Gallery.CreateGalleryStillAlbum 等。スチル操作の基本 (list/grab) は既存
- **MediaPoolItem のマーカー** — Timeline マーカーと混同しやすい。必要性が出たら追加
- **MediaPoolItem のプロキシ** — LinkProxyMedia/UnlinkProxyMedia。ワークフロー依存が強い
- **音声文字起こし** — TranscribeAudio/ClearTranscription。非同期処理の制御が複雑
- **字幕自動生成** — CreateSubtitlesFromAudio。同上
- **シーンカット検出** — DetectSceneCuts。非同期・長時間処理
- **キーフレームモード** — GetKeyframeMode/SetKeyframeMode。UI 操作寄り
- **レンダープリセット I/O** — ImportRenderPreset/ExportRenderPreset。ファイルベースでエージェントが直接扱いにくい

### 3.4 既存コマンドの Graph オブジェクト対応方針

#### 現状

- `color.apply-lut` — `clip_item.SetLUT(1, path)` を使用 (TimelineItem の undocumented メソッド)
- `color.node.list` — `clip_item.GetNumNodes()` / `clip_item.GetNodeLabel(i)` を使用 (同上)
- `color.reset` — `clip_item.ResetAllNodeColors()` を使用

#### 方針

1. **既存コマンドは現行の TimelineItem メソッドを維持する** — 実機テストで動作確認済みであり、Graph 経由に切り替えると互換性リスクがある
2. **新規追加コマンド (Priority 5) は Graph オブジェクト経由で実装する** — `TimelineItem.GetNodeGraph()` から Graph を取得し、Graph のメソッドを呼ぶ
3. **将来的な移行**: 全ノード操作を Graph 経由に統一する計画は立てるが、本フェーズでは着手しない

#### Graph 取得ヘルパー

```python
def _get_node_graph(clip_item: Any) -> Any:
    """TimelineItem から Graph オブジェクトを取得する。"""
    graph = clip_item.GetNodeGraph()
    if not graph:
        raise ValidationError(
            field="graph",
            reason="Failed to get node graph for clip",
        )
    return graph
```

### 3.5 テスト戦略

#### モック拡張

`tests/mocks/resolve_mock.py` に以下を追加:

1. **Graph モック** — `MockGraph` クラス (`SetLUT`, `GetLUT`, `SetNodeEnabled`, `ResetAllGrades` 等)
2. **TimelineItem モック拡張** — `GetNodeGraph()`, `CopyGrades(targets)`, `AddVersion()`, `GetVersionNameList()` 等
3. **Timeline モック拡張** — `GetCurrentTimecode()`, `SetCurrentTimecode()`, `GetCurrentVideoItem()`, `AddTrack()`, `DeleteTrack()` 等
4. **Resolve モック拡張** — `OpenPage()`, `GetCurrentPage()`

#### テスト方針

- 各新規 `_impl` 関数に対して最低 3 テスト: 正常系、エラー系 (バリデーション)、dry-run
- 削除コマンドのテストは完全に除去 (死コードを残さない)
- CopyGrades 修正のテストは旧テストを書き換え

### 3.6 実装の段階分け

#### Batch 1: クリーンアップ (1-2 日)

| # | 作業 | 詳細 |
|---|------|------|
| 1 | 4 コマンド削除 | color.node.add, color.node.delete, color.paste-grade, color.still.apply |
| 2 | CopyGrades バグ修正 | `--to` 引数追加、`--dry-run` 追加 |
| 3 | SKILL.md 更新 | 削除コマンド除去、copy-grade の新シグネチャ反映 |
| 4 | テスト修正 | 削除コマンドのテスト除去、CopyGrades テスト書き換え |

#### Batch 2: ナビゲーション + トラック管理 (2-3 日)

| # | 作業 | 詳細 |
|---|------|------|
| 5 | system.page 追加 | OpenPage / GetCurrentPage |
| 6 | timeline.timecode.get/set 追加 | GetCurrentTimecode / SetCurrentTimecode |
| 7 | timeline.current-item 追加 | GetCurrentVideoItem |
| 8 | timeline.track.* 追加 (5 コマンド) | list/add/delete/enable/lock |
| 9 | timeline.duplicate 追加 | DuplicateTimeline |
| 10 | モック拡張 + テスト | 上記全コマンド |

#### Batch 3: カラーバージョン + クリップ属性 (2-3 日)

| # | 作業 | 詳細 |
|---|------|------|
| 11 | color.version.* 追加 (6 コマンド) | list/current/add/load/delete/rename |
| 12 | clip.enable 追加 | SetClipEnabled / GetClipEnabled |
| 13 | clip.color.* 追加 (2 コマンド) | set/clear (get は set に含む) |
| 14 | clip.flag.* 追加 (3 コマンド) | add/list/clear |
| 15 | モック拡張 + テスト | 上記全コマンド |

#### Batch 4: Graph 操作 + レンダリング拡張 (2-3 日)

| # | 作業 | 詳細 |
|---|------|------|
| 16 | color.node.lut.set/get 追加 | Graph.SetLUT / GetLUT |
| 17 | color.node.enable 追加 | Graph.SetNodeEnabled |
| 18 | color.cdl.set 追加 | TimelineItem.SetCDL |
| 19 | color.lut.export 追加 | TimelineItem.ExportLUT |
| 20 | color.reset-all 追加 | Graph.ResetAllGrades |
| 21 | deliver.delete-job/delete-all-jobs 追加 | Project.DeleteRenderJob / DeleteAllRenderJobs |
| 22 | deliver.job-status/is-rendering 追加 | GetRenderJobStatus / IsRenderingInProgress |
| 23 | deliver.format.list/codec.list 追加 | GetRenderFormats / GetRenderCodecs |
| 24 | モック拡張 + テスト | 上記全コマンド |

#### Batch 5: MCP サーバー + ドキュメント (1-2 日)

| # | 作業 | 詳細 |
|---|------|------|
| 25 | MCP サーバー更新 | 全新規コマンドの MCP ツール登録 |
| 26 | SKILL.md 全面更新 | 新コマンド一覧、使用パターン追加 |
| 27 | CLAUDE.md 更新 | Architecture セクション更新 |
| 28 | E2E テスト追加 | 新コマンド群の E2E スモークテスト |

### 3.7 完了後のコマンド数

| グループ | 現在 | 削除 | 追加 | 完了後 |
|----------|------|------|------|--------|
| system | 4 | 0 | 1 (page) | 5 |
| project | 9 | 0 | 0 | 9 |
| timeline | 9 | 0 | 9 (timecode x2, current-item, track x5, duplicate) | 18 |
| clip | 5 | 0 | 6 (enable, color x2, flag x3) | 11 |
| color | 10 | 4 | 12 (version x6, node.lut x2, node.enable, cdl.set, lut.export, reset-all) | 18 |
| media | 5 | 0 | 0 | 5 |
| deliver | 7 | 0 | 6 (delete-job, delete-all-jobs, job-status, is-rendering, format.list, codec.list) | 13 |
| schema | 2 | 0 | 0 | 2 |
| **合計** | **51** | **-4** | **+34** | **81** |

> 注: 現在のコマンド数は CLAUDE.md の 45 ではなく実コード上 51 (サブコマンド含むカウント方法の差異)。上記は leaf コマンド (実際に実行可能なコマンド) のカウント。

## 4. 不確実な点・要確認事項

### 4.1 実機テストが必要な API

以下の API は公式ドキュメントに記載があるが、実機での動作確認が必要:

1. **Graph.SetNodeEnabled()** — v20.3 で追加された比較的新しい API
2. **Timeline.GetCurrentVideoItem()** — 戻り値の型 (TimelineItem | None) を確認
3. **TimelineItem.AddVersion()** — versionType パラメータの取りうる値 ("local" / "remote" ?)
4. **Project.GetRenderFormats()** — 戻り値のフォーマット (dict? list?)

### 4.2 設計判断の保留事項

1. **`system.page` のサブコマンド分割**: `system.page.get` / `system.page.set` に分けるか、`system.page` に `--set` オプションを持たせるか → 他コマンドとの一貫性から get/set サブコマンドを推奨
2. **`color.reset` vs `color.reset-all`**: 既存の `color.reset` (ResetAllNodeColors) と新規 `color.reset-all` (Graph.ResetAllGrades) の関係。名前の混乱を避けるため `color.reset` を `color.reset-nodes` にリネームするか → 破壊的変更になるため、`color.reset-all` を追加するのみとし、help テキストで違いを明記する方針を推奨
3. **コマンド数の肥大化**: 81 コマンドは多いが、エージェントファースト設計では `dr schema list` で一覧取得可能なので問題ないと判断

### 4.3 project.rename の扱い

`Project.SetName(name)` は公式 API に存在するが、今回のスコープからは除外した。理由:

- プロジェクトリネームは頻度が低い
- `project.settings.set` で代替可能かの確認が必要
- Priority が低い

必要であれば Batch 1 に含めることも可能 (実装コスト低)。

## 5. 次のステップ

1. 本設計書のレビューと承認
2. 承認後、`writing-plans` skill で Batch ごとの実装計画を作成
3. Batch 1 から TDD サイクルで実装開始
