# SKILL.md & MCP Tool Description 再設計

Date: 2026-03-08

## 1. アプローチ比較

| 観点 | A: 最小限の修正 | B: lightroom-cli 準拠 (推奨) | C: Schema-Driven 自動生成 |
|------|----------------|------------------------------|--------------------------|
| **スコープ** | SKILL.md の古い情報を修正 + description を英語化 | SKILL.md 全面改訂 + MCP description 構造化 + instructions.py 追加 | B + schema registry から description を自動生成 |
| **工数** | 小 (1-2h) | 中 (4-6h) | 大 (8-12h) |
| **エージェント体験の改善度** | 低 — 情報は正しくなるが、発見しやすさ・ワークフロー誘導は改善されない | 高 — Agent Quick Contract、Getting Started、Common Workflows、Gotchas で体系的にガイド | 最高 — B の恩恵 + description の一貫性が機械的に保証される |
| **保守コスト** | 低 | 中 — SKILL.md と mcp_server.py の両方を手動更新 | 低 — schema 変更で description が自動反映 |
| **リスク** | なし | 低 — 既存パターンの踏襲 | 中 — schema registry の拡張が必要、動的生成のデバッグが煩雑 |
| **前提条件** | なし | なし | schema_registry.py に risk_level, mutating 等のメタデータ追加が必要 |

### 推奨: アプローチ B (lightroom-cli 準拠)

**理由:**
1. lightroom-cli で実証済みのパターンであり、エージェントの使いやすさが実環境で検証されている
2. davinci-cli は約90ツールあり、手動で description を書くことで DaVinci Resolve 固有の注意点（undo不可、clip_index のタイムライン依存など）を正確に伝えられる
3. アプローチ C の自動生成は将来的に移行可能だが、現時点では schema_registry にメタデータが不足しており、先に B を完成させるほうが ROI が高い

---

## 2. 推奨アプローチの詳細設計

### 2.1 SKILL.md の全体構成

```
# davinci-cli Skill

## Agent Quick Contract          ← 6つの簡潔なルール
## Schema-First Discovery        ← dr schema での動的発見方法
## Getting Started for Agents    ← ステップバイステップの検証→操作フロー
## Module Overview               ← 各モジュールの1行説明
## Common Workflows              ← DaVinci Resolve 特有のユースケース
## Input Options                 ← --dry-run, --json, --fields の使い方
## Output Formats                ← 自動判定の説明
## Gotchas & Limitations         ← エージェントが陥りやすい罠
## Error Handling                ← 構造化エラー + exit code recovery playbook
## MCP Server                   ← MCP 固有の情報
## Environment Variables         ← 環境変数一覧
```

#### 各セクションの内容方針

**Agent Quick Contract:**
1. Always use `--fields` to limit response size
2. Check `dr schema show <command>` for parameter types before calling
3. Use `--dry-run` before mutating commands to preview changes
4. Use `--json` for structured input from agents
5. Exit codes matter: 0=ok, 1=resolve not running, 2=no project, 3=validation, 4=env, 5=edition
6. All Resolve API writes are irreversible (no undo) — always dry-run first

**Schema-First Discovery:**
- `dr schema list` で全コマンド一覧
- `dr schema show <command>` で JSON Schema 取得
- 具体的な出力例を含める

**Getting Started for Agents:**
- Step 1: `dr system ping` で接続確認
- Step 2: `dr system info` でバージョン・エディション・現在プロジェクト確認
- Step 3: `dr project list --fields name` でプロジェクト一覧
- Step 4: `dr project open "ProjectName" --dry-run` → 確認 → 実行
- Step 5: `dr timeline list --fields name` でタイムライン確認
- Step 6: `dr clip list --fields index,name` でクリップ操作

**Module Overview:**
- **system** — Connection check, version/edition info, page/keyframe control
- **project** — List, open, close, create, delete, save, rename, settings
- **timeline** — List, switch, create, delete, tracks, timecode, markers, duplicate, scene cuts, subtitles
- **clip** — List timeline clips, info, select, properties, enable, color labels, flags
- **color** — LUT apply, grade reset/copy, color versions, node LUT, CDL, LUT export, stills
- **media** — Media pool: list, import, move, delete, relink, metadata, transcribe, folders
- **deliver** — Render queue: presets, jobs, start/stop, status, formats/codecs, preset import/export
- **gallery** — Gallery albums, still export/import/delete
- **schema** — Command discovery: list all commands, show JSON Schema for any command

**Common Workflows:** (後述 2.4 で詳細)

**Gotchas & Limitations:** (後述 2.5 で詳細)

### 2.2 MCP tool description テンプレート

#### テンプレート形式

```
<1行の英語説明>
[risk_level: read|write|destroy] [mutating: true|false] [supports_dry_run: true|false]
<パラメータの制約・列挙値>
<事前確認すべき内容>
```

#### 具体例 1: 読み取り系 (system_ping)

```python
@mcp.tool(
    description=(
        "Check connection to DaVinci Resolve. Returns status and version.\n"
        "[risk_level: read] [mutating: false]\n"
        "No parameters required. Call this first to verify Resolve is running."
    )
)
```

#### 具体例 2: 書き込み系 (project_open)

```python
@mcp.tool(
    description=(
        "Open a project by name. Closes the current project as a side effect.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True).\n"
        "IMPORTANT: Call project_list first to verify the project name exists.\n"
        "Unsaved changes in the current project will be lost."
    )
)
```

#### 具体例 3: 破壊的操作 (project_delete)

```python
@mcp.tool(
    description=(
        "Permanently delete a project. This action is irreversible.\n"
        "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
        "Params: name (str, required), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first, present the result to the user,\n"
        "and obtain explicit approval before executing with dry_run=False.\n"
        "The Resolve API has no undo — deleted projects cannot be recovered."
    )
)
```

#### 具体例 4: フィールド絞り込み系 (clip_list)

```python
@mcp.tool(
    description=(
        "List all clips in the current timeline.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: fields (str, optional) — comma-separated field names to include.\n"
        "IMPORTANT: Always specify fields (e.g., 'index,name') to minimize response size.\n"
        "clip_index values are timeline-dependent — they change when switching timelines."
    )
)
```

#### 具体例 5: LUT 操作 (color_apply_lut)

```python
@mcp.tool(
    description=(
        "Apply a LUT file to a clip's color grade.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: clip_index (int), lut_path (str, absolute path), dry_run (bool, default=True).\n"
        "Allowed extensions: .cube, .3dl, .lut, .mga, .m3d.\n"
        "Path traversal ('..') is rejected for security.\n"
        "IMPORTANT: Get clip_index from clip_list first. Node index is 1-based."
    )
)
```

#### 具体例 6: deliver_start

```python
@mcp.tool(
    description=(
        "Start rendering jobs in the deliver queue.\n"
        "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
        "Params: job_ids (list[str], optional — None renders all), dry_run (bool, default=True).\n"
        "IMPORTANT: Always dry_run=True first. Rendering consumes significant CPU/GPU resources.\n"
        "Present the dry-run result to the user and obtain explicit approval.\n"
        "Monitor progress with deliver_status (poll interval >= 5s)."
    )
)
```

#### 具体例 7: color_version_list

```python
@mcp.tool(
    description=(
        "List color grading versions for a clip.\n"
        "[risk_level: read] [mutating: false]\n"
        "Params: clip_index (int), version_type (int, 0=local, 1=remote, default=0).\n"
        "Get clip_index from clip_list first."
    )
)
```

### 2.3 MCP instructions の内容

`src/davinci_cli/mcp/instructions.py` として新規作成:

```python
"""MCP Server instructions for AI agents (Claude Desktop / Cowork).

Equivalent to SKILL.md but adapted for MCP tool naming conventions.
"""

INSTRUCTIONS = """\
# davinci-cli — MCP Server Guide

You are interacting with DaVinci Resolve through MCP tools.
All tool names use snake_case (e.g., system_ping, project_list, clip_list).

## Getting Started

1. **Verify connection:** Call `system_ping`. If it fails, DaVinci Resolve may not be running.
2. **Get context:** Call `system_info` for version, edition, and current project.
3. **List projects:** Call `project_list(fields="name")` to see available projects.
4. **Open a project:** Call `project_open(name="...", dry_run=True)` first, then confirm with the user.

## Safety Rules

- **All Resolve API writes are irreversible** — there is no undo.
- **Mutating tools default to `dry_run=True`** — preview changes before applying.
- **[risk_level: destroy] tools** require explicit user approval before `dry_run=False`.
- **Always use `fields` parameter** on list tools to minimize response size.
- **clip_index is timeline-dependent** — verify after switching timelines.
- **node_index is 1-based** (not 0-based).

## Error Recovery

| Error Type | exit_code | Recovery |
|------------|-----------|----------|
| ResolveNotRunningError | 1 | Ensure DaVinci Resolve is running, then retry system_ping. |
| ProjectNotOpenError | 2 | Open a project with project_open first. |
| ValidationError | 3 | Check parameter types/values. Use schema tools for reference. |
| EnvironmentError | 4 | Check RESOLVE_SCRIPT_API/LIB/MODULES environment variables. |
| EditionError | 5 | Feature requires DaVinci Resolve Studio (paid version). |

## Key Workflows

### Color Grading
1. `clip_list(fields="index,name")` — Get clip indices
2. `color_version_add(clip_index=N, name="before-edit")` — Save checkpoint (no undo!)
3. `color_apply_lut(clip_index=N, lut_path="...", dry_run=True)` — Preview LUT
4. Apply with `dry_run=False` after user approval

### Render / Deliver
1. `deliver_preset_list()` — List available presets
2. `deliver_preset_load(name="...")` — Load a preset
3. `deliver_add_job(job_data={...}, dry_run=True)` — Preview job
4. `deliver_start(dry_run=True)` — Preview render start
5. `deliver_status()` — Monitor progress (poll >= 5s interval)

### Media Import
1. `media_list(fields="clip_name")` — Check existing media
2. `media_import(paths=[...])` — Import files (absolute paths only)
3. `media_move(clip_names=[...], target_folder="...", dry_run=True)` — Organize

## Tips

- Use `system_page_get()` / `system_page_set()` to navigate Resolve pages.
- `timeline_current_item()` returns the clip at the playhead position.
- `color_copy_grade(from_index, to_index)` copies directly (no separate paste step).
- `gallery_still_grab()` captures a still for the current album.
- Studio-only features return EditionError (exit_code=5) on Free edition.
"""
```

### 2.4 Common Workflows（SKILL.md 用）

#### Workflow 1: Color Grading Pipeline

```bash
# 1. Get clip indices
dr clip list --fields index,name

# 2. Save a checkpoint (Resolve API has NO undo!)
dr color version add 1 "before-edit" --dry-run
dr color version add 1 "before-edit"

# 3. Apply LUT
dr color apply-lut 1 /path/to/lut.cube --dry-run
dr color apply-lut 1 /path/to/lut.cube

# 4. Copy grade to another clip
dr color copy-grade --from 1 --to 2 --dry-run
dr color copy-grade --from 1 --to 2

# 5. If unhappy, load the saved version
dr color version load 1 "before-edit"
```

> **Note:** `copy-grade` copies directly from source to destination. There is no separate paste step.

#### Workflow 2: Render / Deliver Pipeline

```bash
# 1. Check available presets
dr deliver preset list

# 2. Load a preset
dr deliver preset load "YouTube 1080p"

# 3. Add a render job
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}' --dry-run
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}'

# 4. Start rendering (always dry-run first!)
dr deliver start --dry-run
dr deliver start

# 5. Monitor progress (poll interval >= 5s)
dr deliver status
```

#### Workflow 3: Media Organization

```bash
# 1. List current media pool
dr media list --fields clip_name,file_path

# 2. Create a folder
dr media folder create "B-Roll"

# 3. Import files
dr media import /path/to/file1.mov /path/to/file2.mp4

# 4. Move to folder
dr media move --clip-names "file1.mov,file2.mp4" --target-folder "B-Roll" --dry-run
dr media move --clip-names "file1.mov,file2.mp4" --target-folder "B-Roll"
```

#### Workflow 4: Timeline Management

```bash
# 1. List timelines
dr timeline list --fields name

# 2. Switch to a timeline
dr timeline switch "Main Edit" --dry-run
dr timeline switch "Main Edit"

# 3. Duplicate for safety
dr timeline duplicate --name "Main Edit - Copy" --dry-run
dr timeline duplicate --name "Main Edit - Copy"

# 4. List clips in the timeline
dr clip list --fields index,name

# 5. Get current timecode
dr timeline timecode get
```

#### Workflow 5: Gallery Still Management

```bash
# 1. List gallery albums
dr gallery album list

# 2. Set current album
dr gallery album set "Stills" --dry-run
dr gallery album set "Stills"

# 3. Grab a still from current clip
dr color still grab 1 --dry-run
dr color still grab 1

# 4. Export stills
dr gallery still export --folder-path /output/stills --format png --dry-run
dr gallery still export --folder-path /output/stills --format png
```

### 2.5 Gotchas & Limitations

#### No Undo / No Redo

The DaVinci Resolve API provides **no undo mechanism**. Every write operation is permanent.
**Always** use `--dry-run` first. For color grading, create a color version before editing:

```bash
dr color version add <clip_index> "checkpoint-name"
```

#### clip_index is timeline-dependent

`clip_index` values belong to the current timeline. When you switch timelines, all previously obtained clip indices become invalid. **Always re-fetch** `clip list` after `timeline switch`.

#### node_index is 1-based

Node indices start from 1, not 0. The first node in a clip's node graph is `node_index=1`.

#### CopyGrade is a direct operation

`color copy-grade --from X --to Y` copies the grade directly. There is no separate "paste" step (unlike the Resolve GUI's copy/paste workflow).

#### Graph object required for node operations

Node operations internally require `TimelineItem.GetNodeGraph()`. This is handled automatically, but it means node operations only work on timeline items (not media pool clips).

#### MediaStorage and Fusion are not supported

The CLI does not wrap `MediaStorage` or `Fusion` APIs. Media operations go through the MediaPool API.

#### Studio-only features

Some operations require DaVinci Resolve Studio (paid). If called on Free edition, they return `EditionError` (exit_code=5). Check edition with `dr system edition` before attempting.

#### Path security

All file path parameters reject path traversal sequences (`..`). Only absolute paths are accepted. Allowed LUT extensions: `.cube`, `.3dl`, `.lut`, `.mga`, `.m3d`.

#### Long-running operations

Scene cut detection (`timeline detect-scene-cuts`), subtitle creation (`timeline create-subtitles`), and transcription (`media transcribe`) can take significant time. Do not timeout prematurely.

#### Render resource consumption

`deliver start` consumes significant CPU/GPU resources. Always preview with `--dry-run` and obtain user approval. Monitor with `deliver status` at intervals >= 5 seconds.

---

## 3. 実装タスクリスト

### Task 1: SKILL.md 全面改訂
- 現在の SKILL.md を上記 2.1 の構成に全面書き換え
- 古い情報（paste-grade, node add/delete, still apply）を削除
- Common Workflows と Gotchas を追加
- 英語で記述（DaVinci Resolve の国際的なユーザーベースを考慮）

### Task 2: MCP tool description の構造化
- mcp_server.py の全 description を英語化
- メタデータタグ追加: `[risk_level: read|write|destroy]`, `[mutating: true|false]`, `[supports_dry_run: true|false]`
- パラメータ制約・列挙値を明記
- 事前確認すべき内容を description に含める

### Task 3: MCP instructions.py 追加
- `src/davinci_cli/mcp/instructions.py` を新規作成
- FastMCP の `instructions` パラメータに渡す
- mcp_server.py の `FastMCP("davinci-cli")` を `FastMCP("davinci-cli", instructions=INSTRUCTIONS)` に変更

### Task 4: テスト
- 既存テストが通ることを確認
- description の形式が一貫していることを目視確認

---

## 4. 要確認事項

1. **SKILL.md の言語**: 英語で統一するか、日本語を維持するか？ → lightroom-cli に合わせて英語を推奨
2. **media folder コマンド**: SKILL.md には `media folder list/create/delete` が記載されているが、MCP server には対応ツールがない。MCP にも追加するか？
3. **timeline marker コマンド**: SKILL.md には記載されているが、MCP server には対応ツールがない。同様に追加するか？
4. **project settings コマンド**: SKILL.md には `project settings get/set` が記載されているが、MCP server には対応ツールがない。同様に追加するか？
5. **schema_registry へのメタデータ追加**: 将来アプローチ C に移行するため、`risk_level`, `mutating`, `supports_dry_run` を schema_registry に追加するか？ → Phase 2 として検討
