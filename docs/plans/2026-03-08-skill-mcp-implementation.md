# SKILL.md & MCP Description Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** SKILL.md を英語で全面改訂し、MCP tool description を英語+メタデータタグに統一し、MCP instructions.py を追加し、CLI↔MCP パリティを修正する
**Architecture:** 既存の _impl 純粋関数パターンを踏襲。MCP ツール追加は mcp_server.py に関数を追加し、テストの EXPECTED_TOOLS を更新。description は英語+メタデータタグ形式に統一。instructions.py で FastMCP の instructions パラメータにエージェント向けガイドを埋め込む。
**Tech Stack:** Python 3.10+, Click, FastMCP, Pydantic v2, Rich, pytest

---

## 前提

- 現在 445 テスト通過
- MCP サーバーは `src/davinci_cli/mcp/mcp_server.py` に 90 ツール登録済み
- テストは `tests/unit/test_mcp_server.py` で EXPECTED_TOOLS リスト + description + dry_run デフォルトを検証
- 全 _impl 関数は `src/davinci_cli/commands/` 配下に実装済み
- description の形式変更時、既存テストの `"AGENT RULES" in desc` アサーションを更新する必要がある

---

### Task 1: CLI↔MCP パリティ修正（12件の MCP ツール追加）

**Files:**
- Modify: `tests/unit/test_mcp_server.py`
- Modify: `src/davinci_cli/mcp/mcp_server.py`

**Step 1: テスト更新 — EXPECTED_TOOLS に12件追加**

`tests/unit/test_mcp_server.py` の `EXPECTED_TOOLS` リストに以下を追加:

```python
# EXPECTED_TOOLS リストの該当箇所に追加:

# project セクション（既存9件の後に追加）:
    "project_settings_get",
    "project_settings_set",

# timeline セクション（既存16件の後に追加）:
    "timeline_export",
    "timeline_marker_list",
    "timeline_marker_add",
    "timeline_marker_delete",

# clip セクション（既存の clip_property_set の次に追加）:
    "clip_property_get",

# media セクション（既存10件の後に追加）:
    "media_folder_list",
    "media_folder_create",
    "media_folder_delete",
```

project セクションのコメントを `# project (11)` に、timeline を `# timeline (20)` に、clip を `# clip (13)` に、media を `# media (13)` に更新する。

`test_total_tool_count` は EXPECTED_TOOLS の長さで自動的に更新される。

**新規テストクラスを追加:**

```python
class TestMCPParityTools:
    """CLI↔MCP パリティ修正で追加されたツールのテスト。"""

    def test_project_settings_tools(self):
        tool_names = _get_tool_names()
        assert "project_settings_get" in tool_names
        assert "project_settings_set" in tool_names

    def test_timeline_export_tool(self):
        tool_names = _get_tool_names()
        assert "timeline_export" in tool_names

    def test_timeline_marker_tools(self):
        tool_names = _get_tool_names()
        assert "timeline_marker_list" in tool_names
        assert "timeline_marker_add" in tool_names
        assert "timeline_marker_delete" in tool_names

    def test_clip_property_get_tool(self):
        tool_names = _get_tool_names()
        assert "clip_property_get" in tool_names

    def test_media_folder_tools(self):
        tool_names = _get_tool_names()
        assert "media_folder_list" in tool_names
        assert "media_folder_create" in tool_names
        assert "media_folder_delete" in tool_names

    def test_parity_tools_dry_run_defaults(self):
        """パリティ修正ツールのdry_runデフォルトがTrueであることを確認する。"""
        dry_run_tools = [
            "project_settings_set",
            "timeline_export",
            "timeline_marker_add",
            "timeline_marker_delete",
            "media_folder_delete",
        ]
        tools = _list_tools()
        for name in dry_run_tools:
            tool = next(t for t in tools if t.name == name)
            sig = inspect.signature(tool.fn)
            assert sig.parameters["dry_run"].default is True, (
                f"{name} dry_run default is not True"
            )
```

**Step 2: テスト実行 — 失敗確認**

```bash
python -m pytest tests/unit/test_mcp_server.py::TestMCPParityTools -v
```

期待: 全テスト FAILED（ツール未登録）

**Step 3: mcp_server.py にインポート追加**

`src/davinci_cli/mcp/mcp_server.py` の既存インポートに以下を追加:

```python
# clip セクションに追加:
from davinci_cli.commands.clip import (
    # ... 既存インポート ...
    clip_property_get_impl,
)

# media セクションに追加:
from davinci_cli.commands.media import (
    # ... 既存インポート ...
    folder_create_impl,
    folder_delete_impl,
    folder_list_impl,
)

# project セクションに追加:
from davinci_cli.commands.project import (
    # ... 既存インポート ...
    project_settings_get_impl,
    project_settings_set_impl,
)

# timeline セクションに追加:
from davinci_cli.commands.timeline import (
    # ... 既存インポート ...
    marker_add_impl,
    marker_delete_impl,
    marker_list_impl,
    timeline_export_impl,
)
```

**Step 4: mcp_server.py に12個のツール関数を追加**

project セクション（`project_info` の後）:

```python
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
```

timeline セクション（`timeline_create_subtitles` の後）:

```python
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
```

clip セクション（`clip_select` の後、`clip_property_set` の前）:

```python
@mcp.tool(
    description="クリップのプロパティを取得する。\n"
    "AGENT RULES:\n- index はclip listで確認した値を使うこと"
)
@mcp_error_handler
def clip_property_get(index: int, key: str) -> dict:
    return clip_property_get_impl(index=index, key=key)
```

media セクション（`media_transcribe` の後）:

```python
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
```

**Step 5: TestMCPDryRunDefaults に新ツール追加**

`test_new_destructive_tools_default_dry_run_true` の `dry_run_tools` リストに追加:

```python
            "project_settings_set",
            "timeline_export",
            "timeline_marker_add",
            "timeline_marker_delete",
            "media_folder_delete",
```

**Step 6: テスト実行 — 通過確認**

```bash
python -m pytest tests/unit/test_mcp_server.py -v
```

期待: 全テスト PASSED

**Step 7: 全テスト実行**

```bash
python -m pytest tests/unit/ -v
```

期待: 全テスト PASSED（445 + 新規テスト数）

**Step 8: コミット**

```bash
git add src/davinci_cli/mcp/mcp_server.py tests/unit/test_mcp_server.py
git commit -m "feat: add 12 MCP parity tools (project settings, timeline export/markers, clip property get, media folders)"
```

---

### Task 2: MCP instructions.py 作成 + mcp_server.py に接続

**Files:**
- Create: `src/davinci_cli/mcp/instructions.py`
- Modify: `src/davinci_cli/mcp/mcp_server.py`
- Modify: `tests/unit/test_mcp_server.py`

**Step 1: テスト追加**

`tests/unit/test_mcp_server.py` に以下を追加:

```python
class TestMCPInstructions:
    def test_mcp_has_instructions(self):
        """MCP サーバーに instructions が設定されていることを確認する。"""
        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0

    def test_instructions_contains_key_sections(self):
        """instructions に必須セクションが含まれていることを確認する。"""
        instructions = mcp.instructions
        assert "Getting Started" in instructions
        assert "Safety Rules" in instructions
        assert "Error Recovery" in instructions
        assert "Key Workflows" in instructions
        assert "Tips" in instructions

    def test_instructions_mentions_system_ping(self):
        """instructions が system_ping を最初のステップとして言及していることを確認する。"""
        assert "system_ping" in mcp.instructions
```

**Step 2: テスト実行 — 失敗確認**

```bash
python -m pytest tests/unit/test_mcp_server.py::TestMCPInstructions -v
```

期待: FAILED（instructions 未設定）

**Step 3: instructions.py を作成**

`src/davinci_cli/mcp/instructions.py`:

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

**Step 4: mcp_server.py に instructions を接続**

`src/davinci_cli/mcp/mcp_server.py` の `FastMCP` 初期化を変更:

変更前:
```python
mcp = FastMCP("davinci-cli")
```

変更後:
```python
from davinci_cli.mcp.instructions import INSTRUCTIONS

mcp = FastMCP("davinci-cli", instructions=INSTRUCTIONS)
```

**Step 5: テスト実行 — 通過確認**

```bash
python -m pytest tests/unit/test_mcp_server.py::TestMCPInstructions -v
```

期待: 全テスト PASSED

**Step 6: 全テスト実行**

```bash
python -m pytest tests/unit/ -v
```

期待: 全テスト PASSED

**Step 7: コミット**

```bash
git add src/davinci_cli/mcp/instructions.py src/davinci_cli/mcp/mcp_server.py tests/unit/test_mcp_server.py
git commit -m "feat: add MCP instructions.py with agent guide (Getting Started, Safety Rules, Error Recovery, Workflows)"
```

---

### Task 3: MCP tool description 全面改訂（英語化 + メタデータタグ）

このタスクは mcp_server.py の全90+ツールの description を英語+メタデータタグ形式に書き換える。1コミットにまとめる。

**Files:**
- Modify: `src/davinci_cli/mcp/mcp_server.py`
- Modify: `tests/unit/test_mcp_server.py`

**Step 1: テストの description アサーション更新**

`tests/unit/test_mcp_server.py` の `TestMCPDescriptions` クラスを書き換える:

```python
class TestMCPDescriptions:
    def _get_tool_desc(self, name: str) -> str:
        tools = _list_tools()
        tool = next(t for t in tools if t.name == name)
        return tool.description or ""

    def test_all_tools_have_risk_level(self):
        """全ツールが [risk_level: ...] タグを含むことを確認する。"""
        tools = _list_tools()
        for tool in tools:
            desc = tool.description or ""
            assert "[risk_level:" in desc, (
                f"{tool.name} missing [risk_level:] in description"
            )

    def test_all_tools_have_mutating_tag(self):
        """全ツールが [mutating: ...] タグを含むことを確認する。"""
        tools = _list_tools()
        for tool in tools:
            desc = tool.description or ""
            assert "[mutating:" in desc, (
                f"{tool.name} missing [mutating:] in description"
            )

    def test_read_tools_not_mutating(self):
        """読み取り専用ツールが mutating: false であることを確認する。"""
        read_tools = [
            "system_ping", "system_version", "system_edition", "system_info",
            "system_page_get", "system_keyframe_mode_get",
            "project_list", "project_info", "project_settings_get",
            "timeline_list", "timeline_current", "timeline_timecode_get",
            "timeline_current_item", "timeline_track_list",
            "timeline_marker_list",
            "clip_list", "clip_info", "clip_property_get",
            "clip_color_get", "clip_flag_list",
            "color_version_list", "color_version_current",
            "color_node_lut_get", "color_still_list",
            "media_list", "media_metadata_get", "media_folder_list",
            "deliver_preset_list", "deliver_list_jobs", "deliver_status",
            "deliver_job_status", "deliver_is_rendering",
            "deliver_format_list", "deliver_codec_list",
            "gallery_album_list", "gallery_album_current",
        ]
        for name in read_tools:
            desc = self._get_tool_desc(name)
            assert "[mutating: false]" in desc, (
                f"{name} should be [mutating: false]"
            )

    def test_destroy_tools_have_destroy_risk(self):
        """破壊的ツールが risk_level: destroy であることを確認する。"""
        destroy_tools = [
            "project_delete",
            "timeline_delete",
            "media_delete",
            "media_folder_delete",
            "deliver_delete_job",
            "deliver_delete_all_jobs",
            "color_version_delete",
            "gallery_still_delete",
        ]
        for name in destroy_tools:
            desc = self._get_tool_desc(name)
            assert "[risk_level: destroy]" in desc, (
                f"{name} should be [risk_level: destroy]"
            )

    def test_dry_run_tools_have_supports_dry_run_tag(self):
        """dry_run パラメータを持つツールが supports_dry_run タグを含むことを確認する。"""
        tools = _list_tools()
        for tool in tools:
            sig = inspect.signature(tool.fn)
            if "dry_run" in sig.parameters:
                desc = tool.description or ""
                assert "[supports_dry_run: true]" in desc, (
                    f"{tool.name} has dry_run param but missing [supports_dry_run: true]"
                )

    def test_descriptions_are_english(self):
        """全 description が英語であることを確認する（日本語文字を含まない）。"""
        import re
        tools = _list_tools()
        japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
        for tool in tools:
            desc = tool.description or ""
            match = japanese_pattern.search(desc)
            assert match is None, (
                f"{tool.name} contains Japanese characters in description: '{match.group()}'"
            )

    def test_deliver_start_description(self):
        desc = self._get_tool_desc("deliver_start")
        assert "[risk_level: write]" in desc
        assert "[mutating: true]" in desc
        assert "[supports_dry_run: true]" in desc

    def test_color_apply_lut_description(self):
        desc = self._get_tool_desc("color_apply_lut")
        assert ".cube" in desc
        assert "[risk_level: write]" in desc
```

**Step 2: テスト実行 — 失敗確認**

```bash
python -m pytest tests/unit/test_mcp_server.py::TestMCPDescriptions -v
```

期待: 多数 FAILED（日本語 description、タグなし）

**Step 3: mcp_server.py の全 description を英語+メタデータタグに書き換え**

以下のテンプレートに従って全ツールの description を書き換える:

```
<1行の英語説明>
[risk_level: read|write|destroy] [mutating: true|false] [supports_dry_run: true|false]
<パラメータの制約・列挙値>（必要な場合）
<事前確認すべき内容>（必要な場合）
```

#### system ツール（8件）

```python
# system_ping
description=(
    "Check connection to DaVinci Resolve. Returns status and version.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required. Call this first to verify Resolve is running."
)

# system_version
description=(
    "Return DaVinci Resolve version string.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# system_edition
description=(
    "Return DaVinci Resolve edition (Free or Studio).\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# system_info
description=(
    "Return combined info: version, edition, and current project.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# system_page_get
description=(
    "Get the current Resolve UI page.\n"
    "[risk_level: read] [mutating: false]\n"
    "Returns one of: media, cut, edit, fusion, color, fairlight, deliver."
)

# system_page_set
description=(
    "Switch the Resolve UI page.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: page (str) — media, cut, edit, fusion, color, fairlight, deliver.\n"
    "IMPORTANT: Always dry_run=True first to preview."
)

# system_keyframe_mode_get
description=(
    "Get the current keyframe mode.\n"
    "[risk_level: read] [mutating: false]\n"
    "Returns mode: 0=all, 1=color, 2=sizing."
)

# system_keyframe_mode_set
description=(
    "Set the keyframe mode.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: mode (int) — 0=all, 1=color, 2=sizing.\n"
    "IMPORTANT: Always dry_run=True first to preview."
)
```

#### project ツール（11件）

```python
# project_list
description=(
    "List all projects in the current database.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: fields (str, optional) — comma-separated field names.\n"
    "IMPORTANT: Always specify fields (e.g., 'name') to minimize response size."
)

# project_open
description=(
    "Open a project by name. Closes the current project as a side effect.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str, required), dry_run (bool, default=True).\n"
    "IMPORTANT: Call project_list first to verify the project name exists.\n"
    "Unsaved changes in the current project will be lost."
)

# project_close
description=(
    "Close the current project.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: dry_run (bool, default=True).\n"
    "Unsaved changes will be lost."
)

# project_create
description=(
    "Create a new project.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str, required), dry_run (bool, default=True)."
)

# project_delete
description=(
    "Permanently delete a project. This action is irreversible.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str, required), dry_run (bool, default=True).\n"
    "IMPORTANT: Always dry_run=True first, present the result to the user,\n"
    "and obtain explicit approval before executing with dry_run=False.\n"
    "The Resolve API has no undo — deleted projects cannot be recovered."
)

# project_rename
description=(
    "Rename the current project.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str, required), dry_run (bool, default=True)."
)

# project_save
description=(
    "Save the current project.\n"
    "[risk_level: write] [mutating: true]\n"
    "No parameters required."
)

# project_info
description=(
    "Return current project information.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: fields (str, optional) — comma-separated field names.\n"
    "IMPORTANT: Always specify fields to minimize response size."
)

# project_settings_get
description=(
    "Get project settings. Returns a specific setting by key or all settings.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: key (str, optional) — setting key. Omit to get all settings.\n"
    "IMPORTANT: Specify a key when possible to minimize response size."
)

# project_settings_set
description=(
    "Set a project setting value.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: key (str, required), value (str, required), dry_run (bool, default=True).\n"
    "IMPORTANT: Call project_settings_get(key) first to check the current value."
)
```

#### timeline ツール（20件）

```python
# timeline_list
description=(
    "List all timelines in the current project.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: fields (str, optional) — comma-separated field names.\n"
    "IMPORTANT: Always specify fields (e.g., 'name') to minimize response size."
)

# timeline_current
description=(
    "Return current timeline information.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: fields (str, optional) — comma-separated field names.\n"
    "IMPORTANT: Always specify fields to minimize response size."
)

# timeline_switch
description=(
    "Switch to a different timeline by name.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str, required), dry_run (bool, default=True).\n"
    "IMPORTANT: After switching, all previously obtained clip_index values become invalid.\n"
    "Always re-fetch clip_list after switching timelines."
)

# timeline_create
description=(
    "Create a new empty timeline.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str, required), dry_run (bool, default=True)."
)

# timeline_delete
description=(
    "Delete a timeline. This action is irreversible.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str, required), dry_run (bool, default=True).\n"
    "IMPORTANT: Always dry_run=True first and obtain user approval."
)

# timeline_timecode_get
description=(
    "Get the current playhead timecode.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required. Returns timecode in HH:MM:SS:FF format."
)

# timeline_timecode_set
description=(
    "Set the playhead timecode position.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: timecode (str, HH:MM:SS:FF format, e.g., '01:00:00:00'), dry_run (bool, default=True)."
)

# timeline_current_item
description=(
    "Get the clip at the current playhead position.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# timeline_track_list
description=(
    "List all tracks (video, audio, subtitle) in the current timeline.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# timeline_track_add
description=(
    "Add a new track to the current timeline.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: track_type (str) — video, audio, or subtitle."
)

# timeline_track_delete
description=(
    "Delete a track from the current timeline.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: track_type (str) — video, audio, subtitle; track_index (int).\n"
    "IMPORTANT: Get track_index from timeline_track_list first."
)

# timeline_track_enable
description=(
    "Get or set track enabled state.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: track_type (str) — video, audio, subtitle; track_index (int); enabled (bool|None).\n"
    "Set enabled=None to get current state, True/False to set."
)

# timeline_track_lock
description=(
    "Get or set track lock state.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: track_type (str) — video, audio, subtitle; track_index (int); locked (bool|None).\n"
    "Set locked=None to get current state, True/False to set."
)

# timeline_duplicate
description=(
    "Duplicate the current timeline.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str, optional — auto-named if omitted), dry_run (bool, default=True)."
)

# timeline_detect_scene_cuts
description=(
    "Detect scene cuts in the current timeline.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required.\n"
    "WARNING: This operation can take significant time on long timelines."
)

# timeline_create_subtitles
description=(
    "Auto-generate subtitles from audio in the current timeline.\n"
    "[risk_level: write] [mutating: true]\n"
    "No parameters required.\n"
    "WARNING: This operation can take significant time."
)

# timeline_export
description=(
    "Export a timeline to a file.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: format (str — AAF, EDL, FCPXML, etc.), output_path (str, absolute path),\n"
    "timeline_name (str, optional — current if omitted), dry_run (bool, default=True).\n"
    "Path traversal ('..') is rejected for security."
)

# timeline_marker_list
description=(
    "List all markers in a timeline.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: timeline_name (str, optional — current timeline if omitted)."
)

# timeline_marker_add
description=(
    "Add a marker to the current timeline.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: frame_id (int), color (str), name (str), note (str, optional), duration (int, default=1).\n"
    "Colors: Blue, Cyan, Green, Yellow, Red, Pink, Purple, Fuchsia, Rose, Lavender, Sky, Mint, Lemon, Sand, Cocoa, Cream."
)

# timeline_marker_delete
description=(
    "Delete a marker from the current timeline.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: frame_id (int), dry_run (bool, default=True).\n"
    "IMPORTANT: Get frame_id from timeline_marker_list first."
)
```

#### clip ツール（13件）

```python
# clip_list
description=(
    "List all clips in the current timeline.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: fields (str, optional) — comma-separated field names.\n"
    "IMPORTANT: Always specify fields (e.g., 'index,name') to minimize response size.\n"
    "clip_index values are timeline-dependent — they change when switching timelines."
)

# clip_info
description=(
    "Return detailed information about a clip.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: index (int) — clip index from clip_list.\n"
    "IMPORTANT: Get index from clip_list first."
)

# clip_select
description=(
    "Select a clip in the current timeline.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: index (int) — clip index from clip_list.\n"
    "IMPORTANT: Get index from clip_list first."
)

# clip_property_get
description=(
    "Get a property value of a clip.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: index (int) — clip index from clip_list; key (str) — property name.\n"
    "IMPORTANT: Get index from clip_list first."
)

# clip_property_set
description=(
    "Set a property value on a clip.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: index (int), key (str), value (str), dry_run (bool, default=True).\n"
    "IMPORTANT: Get index from clip_list first."
)

# clip_enable
description=(
    "Get or set clip enabled state.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: index (int), enabled (bool|None).\n"
    "Set enabled=None to get current state, True/False to set.\n"
    "IMPORTANT: Get index from clip_list first."
)

# clip_color_get
description=(
    "Get the color label of a clip.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: index (int) — clip index from clip_list."
)

# clip_color_set
description=(
    "Set the color label of a clip.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: index (int), color (str).\n"
    "Colors: Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy,\n"
    "Blue, Purple, Violet, Pink, Tan, Beige, Brown, Chocolate."
)

# clip_color_clear
description=(
    "Clear the color label of a clip.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: index (int) — clip index from clip_list."
)

# clip_flag_add
description=(
    "Add a flag to a clip.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: index (int), color (str) — flag color."
)

# clip_flag_list
description=(
    "List all flags on a clip.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: index (int) — clip index from clip_list."
)

# clip_flag_clear
description=(
    "Clear flags from a clip.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: index (int), color (str, default='All') — specific color or 'All' to clear all."
)
```

#### color ツール（16件）

```python
# color_apply_lut
description=(
    "Apply a LUT file to a clip's color grade.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), lut_path (str, absolute path), dry_run (bool, default=True).\n"
    "Allowed extensions: .cube, .3dl, .lut, .mga, .m3d.\n"
    "Path traversal ('..') is rejected for security.\n"
    "IMPORTANT: Get clip_index from clip_list first. Node index is 1-based."
)

# color_reset
description=(
    "Reset the color grade on a clip.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), dry_run (bool, default=True).\n"
    "IMPORTANT: No undo — consider creating a color version checkpoint first."
)

# color_copy_grade
description=(
    "Copy a color grade from one clip to another.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: from_index (int), to_index (int), dry_run (bool, default=True).\n"
    "This is a direct copy — there is no separate paste step."
)

# color_version_list
description=(
    "List color grading versions for a clip.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: clip_index (int), version_type (int, 0=local, 1=remote, default=0).\n"
    "Get clip_index from clip_list first."
)

# color_version_current
description=(
    "Get the current color version name for a clip.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: clip_index (int).\n"
    "Get clip_index from clip_list first."
)

# color_version_add
description=(
    "Add a new color version to a clip.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), name (str), version_type (int, 0=local, 1=remote, default=0),\n"
    "dry_run (bool, default=True).\n"
    "Use this to create checkpoints before destructive color operations."
)

# color_version_load
description=(
    "Load a color version by name.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), name (str), version_type (int, 0=local, 1=remote, default=0),\n"
    "dry_run (bool, default=True)."
)

# color_version_delete
description=(
    "Delete a color version. This action is irreversible.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), name (str), version_type (int, 0=local, 1=remote, default=0),\n"
    "dry_run (bool, default=True).\n"
    "IMPORTANT: Always dry_run=True first and obtain user approval."
)

# color_version_rename
description=(
    "Rename a color version.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), old_name (str), new_name (str),\n"
    "version_type (int, 0=local, 1=remote, default=0), dry_run (bool, default=True)."
)

# color_node_lut_set
description=(
    "Set a LUT on a specific node.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), node_index (int, 1-based), lut_path (str, absolute path),\n"
    "dry_run (bool, default=True).\n"
    "Allowed extensions: .cube, .3dl, .lut, .mga, .m3d.\n"
    "Path traversal ('..') is rejected for security.\n"
    "IMPORTANT: node_index is 1-based (first node = 1)."
)

# color_node_lut_get
description=(
    "Get the LUT path set on a specific node.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: clip_index (int), node_index (int, 1-based).\n"
    "IMPORTANT: node_index is 1-based (first node = 1)."
)

# color_node_enable
description=(
    "Set a node's enabled/disabled state.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), node_index (int, 1-based), enabled (bool),\n"
    "dry_run (bool, default=True).\n"
    "IMPORTANT: node_index is 1-based (first node = 1)."
)

# color_cdl_set
description=(
    "Set CDL (Color Decision List) values on a node.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), node_index (int, 1-based),\n"
    "slope (str, RGB space-separated, e.g., '1.0 1.0 1.0'),\n"
    "offset (str, RGB), power (str, RGB), saturation (str, RGB),\n"
    "dry_run (bool, default=True)."
)

# color_lut_export
description=(
    "Export a LUT from a clip's grade to a file.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), export_type (int), path (str, absolute path),\n"
    "dry_run (bool, default=True).\n"
    "Path traversal ('..') is rejected for security."
)

# color_reset_all
description=(
    "Reset the entire node graph on a clip. More destructive than color_reset.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), dry_run (bool, default=True).\n"
    "IMPORTANT: This resets the full node graph, not just individual node values.\n"
    "No undo — consider creating a color version checkpoint first."
)

# color_still_grab
description=(
    "Grab (capture) a still from a clip into the current gallery album.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_index (int), dry_run (bool, default=True)."
)

# color_still_list
description=(
    "List stills in the current gallery album.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)
```

#### media ツール（13件）

```python
# media_list
description=(
    "List clips in the media pool.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: folder (str, optional), fields (str, optional) — comma-separated.\n"
    "IMPORTANT: Always specify fields (e.g., 'clip_name,file_path') to minimize response size."
)

# media_import
description=(
    "Import media files into the media pool.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: paths (list[str]) — absolute file paths.\n"
    "Path traversal ('..') is rejected for security."
)

# media_move
description=(
    "Move media clips to a different folder in the media pool.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_names (list[str]), target_folder (str), dry_run (bool, default=True).\n"
    "IMPORTANT: Get clip_names from media_list first."
)

# media_delete
description=(
    "Delete media clips from the media pool. This action is irreversible.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_names (list[str]), dry_run (bool, default=True).\n"
    "IMPORTANT: Always dry_run=True first, present result, obtain user approval.\n"
    "Get clip_names from media_list first."
)

# media_relink
description=(
    "Relink media clips to a new folder path.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_names (list[str]), folder_path (str, absolute), dry_run (bool, default=True).\n"
    "Path traversal ('..') is rejected for security."
)

# media_unlink
description=(
    "Unlink media clips from their source files.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: clip_names (list[str]).\n"
    "Get clip_names from media_list first."
)

# media_metadata_get
description=(
    "Get metadata for a media clip.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: clip_name (str), key (str, optional — omit for all metadata).\n"
    "IMPORTANT: Specify a key when possible to minimize response size."
)

# media_metadata_set
description=(
    "Set a metadata value on a media clip.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: clip_name (str), key (str), value (str), dry_run (bool, default=True)."
)

# media_export_metadata
description=(
    "Export media pool metadata to a CSV file.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: file_name (str, absolute path), dry_run (bool, default=True).\n"
    "Path traversal ('..') is rejected for security."
)

# media_transcribe
description=(
    "Transcribe audio from a media clip.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: clip_name (str).\n"
    "WARNING: This operation can take significant time."
)

# media_folder_list
description=(
    "List folders in the media pool (root level).\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required. Returns sub-folders of the root folder."
)

# media_folder_create
description=(
    "Create a new folder in the media pool.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: name (str) — folder name."
)

# media_folder_delete
description=(
    "Delete a folder from the media pool. This action is irreversible.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str), dry_run (bool, default=True).\n"
    "IMPORTANT: Always dry_run=True first and obtain user approval.\n"
    "All clips inside the folder will also be deleted."
)
```

#### deliver ツール（15件）

```python
# deliver_preset_list
description=(
    "List available render presets.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# deliver_preset_load
description=(
    "Load a render preset by name.\n"
    "[risk_level: write] [mutating: true]\n"
    "Params: name (str) — preset name from deliver_preset_list.\n"
    "IMPORTANT: Call deliver_preset_list first to verify the name."
)

# deliver_add_job
description=(
    "Add a render job to the queue.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: job_data (dict — keys: output_dir, filename, etc.), dry_run (bool, default=True)."
)

# deliver_list_jobs
description=(
    "List render jobs in the queue.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: fields (str, optional) — comma-separated field names.\n"
    "IMPORTANT: Always specify fields (e.g., 'job_id,status') to minimize response size."
)

# deliver_start
description=(
    "Start rendering jobs in the deliver queue.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: job_ids (list[str], optional — None renders all), dry_run (bool, default=True).\n"
    "IMPORTANT: Always dry_run=True first. Rendering consumes significant CPU/GPU resources.\n"
    "Present the dry-run result to the user and obtain explicit approval.\n"
    "Monitor progress with deliver_status (poll interval >= 5s)."
)

# deliver_stop
description=(
    "Stop all rendering immediately.\n"
    "[risk_level: write] [mutating: true]\n"
    "No parameters required. Partially rendered files may be incomplete."
)

# deliver_status
description=(
    "Get overall render progress (percent, status, ETA).\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required. Use a poll interval of >= 5 seconds."
)

# deliver_delete_job
description=(
    "Delete a render job from the queue.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: job_id (str), dry_run (bool, default=True).\n"
    "IMPORTANT: Get job_id from deliver_list_jobs first."
)

# deliver_delete_all_jobs
description=(
    "Delete all render jobs from the queue. This action is irreversible.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: dry_run (bool, default=True).\n"
    "IMPORTANT: Always dry_run=True first and obtain explicit user approval."
)

# deliver_job_status
description=(
    "Get the status of a specific render job.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: job_id (str) — from deliver_list_jobs."
)

# deliver_is_rendering
description=(
    "Check if rendering is currently in progress.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# deliver_format_list
description=(
    "List available render output formats.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# deliver_codec_list
description=(
    "List available codecs for a given render format.\n"
    "[risk_level: read] [mutating: false]\n"
    "Params: format_name (str) — from deliver_format_list."
)

# deliver_preset_import
description=(
    "Import a render preset from a file.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: path (str, absolute), dry_run (bool, default=True).\n"
    "Path traversal ('..') is rejected for security."
)

# deliver_preset_export
description=(
    "Export a render preset to a file.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str), path (str, absolute), dry_run (bool, default=True).\n"
    "Path traversal ('..') is rejected for security."
)
```

#### gallery ツール（7件）

```python
# gallery_album_list
description=(
    "List all gallery albums.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# gallery_album_current
description=(
    "Get the current gallery album.\n"
    "[risk_level: read] [mutating: false]\n"
    "No parameters required."
)

# gallery_album_set
description=(
    "Switch to a different gallery album.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: name (str) — album name from gallery_album_list, dry_run (bool, default=True)."
)

# gallery_album_create
description=(
    "Create a new gallery album.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: dry_run (bool, default=True)."
)

# gallery_still_export
description=(
    "Export stills from the current album to files.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: folder_path (str, absolute), file_prefix (str, default='still'),\n"
    "format (str, default='dpx') — dpx, cin, tif, jpg, png, tga, bmp, exr.\n"
    "dry_run (bool, default=True).\n"
    "Path traversal ('..') is rejected for security."
)

# gallery_still_import
description=(
    "Import stills into the current gallery album.\n"
    "[risk_level: write] [mutating: true] [supports_dry_run: true]\n"
    "Params: paths (list[str], absolute paths), dry_run (bool, default=True).\n"
    "Path traversal ('..') is rejected for security."
)

# gallery_still_delete
description=(
    "Delete stills from the current gallery album. This action is irreversible.\n"
    "[risk_level: destroy] [mutating: true] [supports_dry_run: true]\n"
    "Params: still_indices (list[int]) — from color_still_list, dry_run (bool, default=True).\n"
    "IMPORTANT: Always dry_run=True first and obtain user approval."
)
```

**Step 4: テスト実行 — 通過確認**

```bash
python -m pytest tests/unit/test_mcp_server.py::TestMCPDescriptions -v
```

期待: 全テスト PASSED

**Step 5: 全テスト実行**

```bash
python -m pytest tests/unit/ -v
```

期待: 全テスト PASSED

**Step 6: lint 確認**

```bash
ruff check src/davinci_cli/mcp/mcp_server.py
```

**Step 7: コミット**

```bash
git add src/davinci_cli/mcp/mcp_server.py tests/unit/test_mcp_server.py
git commit -m "refactor: rewrite all MCP tool descriptions to English with metadata tags ([risk_level], [mutating], [supports_dry_run])"
```

---

### Task 4: SKILL.md 全面改訂

**Files:**
- Modify: `SKILL.md`

**Step 1: SKILL.md を全面書き換え**

以下の内容で `SKILL.md` を上書きする（英語、11セクション構成）:

```markdown
---
name: davinci-cli
version: 1.0.0
description: DaVinci Resolve CLI / MCP — agent-first interface
---

# davinci-cli Skill

CLI and MCP server for controlling DaVinci Resolve. Designed for AI agents.

## Agent Quick Contract

1. **Always use `--fields`** to limit response size (e.g., `--fields name,fps`).
2. **Check `dr schema show <command>`** for parameter types before calling.
3. **Use `--dry-run`** before mutating commands to preview changes.
4. **Use `--json`** for structured input (e.g., `--json '{"name": "MyProject"}'`).
5. **Exit codes matter:** 0=ok, 1=resolve not running, 2=no project, 3=validation, 4=env, 5=edition.
6. **All Resolve API writes are irreversible** (no undo) — always dry-run first.

## Schema-First Discovery

```bash
# List all registered commands
dr schema list

# Get JSON Schema for a specific command
dr schema show project.open
```

Output includes `input_schema` (parameters) and `output_schema` (return type).

## Getting Started for Agents

```bash
# Step 1: Verify connection
dr system ping

# Step 2: Get version, edition, current project
dr system info

# Step 3: List projects
dr project list --fields name

# Step 4: Open a project (dry-run first!)
dr project open "ProjectName" --dry-run
# → Confirm with user → then:
dr project open "ProjectName"

# Step 5: List timelines
dr timeline list --fields name

# Step 6: List clips
dr clip list --fields index,name
```

## Module Overview

| Module | Description |
|--------|-------------|
| **system** | Connection check, version/edition info, page/keyframe control |
| **project** | List, open, close, create, delete, save, rename, settings |
| **timeline** | List, switch, create, delete, export, tracks, timecode, markers, duplicate, scene cuts, subtitles |
| **clip** | List timeline clips, info, select, properties, enable, color labels, flags |
| **color** | LUT apply, grade reset/copy, color versions, node LUT, CDL, LUT export, stills |
| **media** | Media pool: list, import, move, delete, relink, metadata, transcribe, folders |
| **deliver** | Render queue: presets, jobs, start/stop, status, formats/codecs, preset import/export |
| **gallery** | Gallery albums, still export/import/delete |
| **schema** | Command discovery: list all commands, show JSON Schema for any command |

## Common Workflows

### Color Grading Pipeline

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

### Render / Deliver Pipeline

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

### Media Organization

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

### Timeline Management

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

### Gallery Still Management

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

## Input Options

### `--json` (Structured Input)

Pass complex parameters as a JSON object:

```bash
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}'
```

### `--fields` (Output Filtering)

Limit returned fields to reduce response size:

```bash
dr project list --fields name
dr clip list --fields index,name
```

### `--dry-run` (Preview Mode)

Preview destructive operations before executing:

```bash
dr project delete "OldProject" --dry-run
# Returns: {"dry_run": true, "action": "delete", "name": "OldProject"}
```

## Output Formats

Output format is auto-detected:

| Context | Format |
|---------|--------|
| Non-TTY (pipe/agent) | NDJSON (one JSON object per line) or single JSON |
| TTY + `--pretty` | Rich formatted table |

Error responses always use structured JSON:

```json
{"error": "...", "error_type": "ResolveNotRunningError", "exit_code": 1}
```

## Gotchas & Limitations

### No Undo / No Redo

The DaVinci Resolve API provides **no undo mechanism**. Every write operation is permanent.
**Always** use `--dry-run` first. For color grading, create a color version before editing:

```bash
dr color version add <clip_index> "checkpoint-name"
```

### clip_index is timeline-dependent

`clip_index` values belong to the current timeline. When you switch timelines, all previously obtained clip indices become invalid. **Always re-fetch** `clip list` after `timeline switch`.

### node_index is 1-based

Node indices start from 1, not 0. The first node in a clip's node graph is `node_index=1`.

### CopyGrade is a direct operation

`color copy-grade --from X --to Y` copies the grade directly. There is no separate "paste" step (unlike the Resolve GUI's copy/paste workflow).

### Graph object required for node operations

Node operations internally require `TimelineItem.GetNodeGraph()`. This is handled automatically, but it means node operations only work on timeline items (not media pool clips).

### MediaStorage and Fusion are not supported

The CLI does not wrap `MediaStorage` or `Fusion` APIs. Media operations go through the MediaPool API.

### Studio-only features

Some operations require DaVinci Resolve Studio (paid). If called on Free edition, they return `EditionError` (exit_code=5). Check edition with `dr system edition` before attempting.

### Path security

All file path parameters reject path traversal sequences (`..`). Only absolute paths are accepted. Allowed LUT extensions: `.cube`, `.3dl`, `.lut`, `.mga`, `.m3d`.

### Long-running operations

Scene cut detection (`timeline detect-scene-cuts`), subtitle creation (`timeline create-subtitles`), and transcription (`media transcribe`) can take significant time. Do not timeout prematurely.

### Render resource consumption

`deliver start` consumes significant CPU/GPU resources. Always preview with `--dry-run` and obtain user approval. Monitor with `deliver status` at intervals >= 5 seconds.

## Error Handling

All errors return structured JSON with consistent fields:

```json
{
  "error": "Human-readable message",
  "error_type": "ResolveNotRunningError",
  "exit_code": 1
}
```

### Recovery Playbook

| Exit Code | Error Type | Recovery |
|-----------|------------|----------|
| 1 | ResolveNotRunningError | Ensure DaVinci Resolve is running, retry `dr system ping`. |
| 2 | ProjectNotOpenError | Open a project with `dr project open <name>`. |
| 3 | ValidationError | Check parameter types/values. Use `dr schema show <command>`. |
| 4 | EnvironmentError | Check `RESOLVE_SCRIPT_API`, `RESOLVE_SCRIPT_LIB`, `RESOLVE_MODULES`. |
| 5 | EditionError | Feature requires DaVinci Resolve Studio. Check with `dr system edition`. |

## MCP Server

```bash
dr-mcp
```

The MCP server exposes all CLI commands as MCP tools with snake_case naming (e.g., `project_open`, `clip_list`).

**Key differences from CLI:**
- All mutating tools default to `dry_run=True` (CLI defaults to `False`).
- Tool descriptions include metadata tags: `[risk_level]`, `[mutating]`, `[supports_dry_run]`.
- The server includes built-in instructions for agent onboarding.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RESOLVE_SCRIPT_API` | Path to DaVinci Resolve scripting API |
| `RESOLVE_SCRIPT_LIB` | Path to DaVinci Resolve shared library |
| `RESOLVE_MODULES` | Path to DaVinci Resolve Python modules (added to sys.path) |

Auto-detected on macOS and Windows when not set. See `src/davinci_cli/core/environment.py`.
```

**Step 2: 内容確認**

SKILL.md がすべてのセクションを含むことを目視確認:
- Agent Quick Contract (6 rules) ✓
- Schema-First Discovery ✓
- Getting Started for Agents ✓
- Module Overview ✓
- Common Workflows (5 workflows) ✓
- Input Options ✓
- Output Formats ✓
- Gotchas & Limitations (10 items) ✓
- Error Handling ✓
- MCP Server ✓
- Environment Variables ✓

**Step 3: コミット**

```bash
git add SKILL.md
git commit -m "docs: rewrite SKILL.md in English with 11-section agent-first structure (lightroom-cli pattern)"
```

---

### Task 5: 全体テスト + lint 確認

**Files:**
- No files modified (verification only)

**Step 1: 全ユニットテスト実行**

```bash
python -m pytest tests/unit/ -v
```

期待: 全テスト PASSED（テスト数が元の445 + Task 1/2/3 の新規テストを合算）

**Step 2: lint 実行**

```bash
ruff check src/davinci_cli/ tests/
```

期待: エラーなし

**Step 3: MCP ツール数の確認**

```bash
python -c "
import asyncio
from davinci_cli.mcp.mcp_server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'Total MCP tools: {len(tools)}')
for t in sorted(tools, key=lambda x: x.name):
    print(f'  {t.name}')
"
```

期待: Total MCP tools: 102（既存90 + パリティ追加12）

**Step 4: description 形式の一貫性確認**

```bash
python -c "
import asyncio
import re
from davinci_cli.mcp.mcp_server import mcp
tools = asyncio.run(mcp.list_tools())
errors = []
jp = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
for t in tools:
    d = t.description or ''
    if '[risk_level:' not in d:
        errors.append(f'{t.name}: missing [risk_level:]')
    if '[mutating:' not in d:
        errors.append(f'{t.name}: missing [mutating:]')
    if jp.search(d):
        errors.append(f'{t.name}: contains Japanese')
if errors:
    for e in errors:
        print(f'ERROR: {e}')
else:
    print('All descriptions valid.')
"
```

期待: `All descriptions valid.`

**Step 5: instructions 確認**

```bash
python -c "
from davinci_cli.mcp.mcp_server import mcp
print(f'Instructions length: {len(mcp.instructions)} chars')
assert 'Getting Started' in mcp.instructions
assert 'Safety Rules' in mcp.instructions
print('Instructions OK.')
"
```

期待: `Instructions OK.`
