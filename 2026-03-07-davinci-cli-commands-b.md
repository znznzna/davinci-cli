# davinci-cli Implementation Plan — Commands B + MCP + SKILL (Task 15-20)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** color/media/deliver/MCP/SKILL/E2Eを構築してdavinci-cliを完成させる
**Architecture:** _impl純粋関数でCLI/MCPを共有。MCPのdescriptionにエージェント指示を埋め込む
**Tech Stack:** Python 3.10+, Click, FastMCP, Pydantic v2, pytest

---

## 前提: 共通パターン（Task 9-14から継続）

Task 9-14と同じ _impl / CLI ラッパーパターンに従う。
セキュリティ関数 `validate_path()` は `src/davinci_cli/security.py` に定義済み想定:

```python
# src/davinci_cli/security.py
import os
from pathlib import Path

def validate_path(path: str, allowed_extensions: list[str] | None = None) -> Path:
    """
    パストラバーサル攻撃を防ぐ。
    - シンボリックリンクを解決して実パスを検証
    - 許可拡張子チェック（指定時）
    """
    p = Path(path).resolve()
    # パストラバーサル: ".." を含むパスは拒絶
    if ".." in Path(path).parts:
        raise ValueError(f"Path traversal detected: {path}")
    if allowed_extensions and p.suffix.lower() not in allowed_extensions:
        raise ValueError(f"Extension {p.suffix} not allowed. Allowed: {allowed_extensions}")
    return p
```

---

### Task 15: commands/color.py — dr color

**Files:**
- Create: `src/davinci_cli/commands/color.py`
- Test: `tests/unit/test_color.py`

**What to implement:**

Pydanticモデル:
```python
class LutApplyInput(BaseModel):
    clip_index: int
    lut_path: str

class NodeInfo(BaseModel):
    index: int
    label: str | None = None
    node_type: str  # "corrector", "layer", "splitter" etc.

class StillInfo(BaseModel):
    index: int
    label: str | None = None
    grabbed_at: str | None = None  # ISO datetime
```

_impl関数群:
```python
def color_apply_lut_impl(clip_index: int, lut_path: str, dry_run: bool = False) -> dict:
    validated = validate_path(lut_path, allowed_extensions=[".cube", ".3dl", ".lut"])
    if dry_run:
        return {"dry_run": True, "action": "apply_lut",
                "clip_index": clip_index, "lut_path": str(validated)}
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    clip = _get_clip_item_by_index(tl, clip_index)
    clip.ApplyArriCdlLut(str(validated))  # or SetLUT()
    return {"applied": str(validated), "clip_index": clip_index}

def color_reset_impl(clip_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "reset", "clip_index": clip_index}
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    clip = _get_clip_item_by_index(tl, clip_index)
    clip.ResetAllGrades()
    return {"reset": True, "clip_index": clip_index}

def color_copy_grade_impl(from_index: int) -> dict:
    # グレードをクリップボードへコピー
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    clip = _get_clip_item_by_index(tl, from_index)
    clip.CopyGrades()
    return {"copied_from": from_index}

def color_paste_grade_impl(to_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "paste_grade", "to_index": to_index}
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    clip = _get_clip_item_by_index(tl, to_index)
    clip.PasteGrades()
    return {"pasted_to": to_index}

# ノード操作
def node_list_impl(clip_index: int) -> list[dict]:
    project = _get_current_project()
    tl = project.GetCurrentTimeline()
    clip = _get_clip_item_by_index(tl, clip_index)
    nodes = clip.GetNodeGraph()
    return [{"index": i, "label": n.GetLabel()} for i, n in enumerate(nodes)]

def node_add_impl(clip_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "node_add", "clip_index": clip_index}
    ...

def node_delete_impl(clip_index: int, node_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "node_delete",
                "clip_index": clip_index, "node_index": node_index}
    ...

# スチル操作
def still_grab_impl(clip_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "still_grab", "clip_index": clip_index}
    ...

def still_list_impl() -> list[dict]: ...

def still_apply_impl(clip_index: int, still_index: int, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "still_apply",
                "clip_index": clip_index, "still_index": still_index}
    ...
```

CLIコマンド構造:
```python
@click.group()
def color():
    """Color grading operations."""

@color.command(name="apply-lut")
@click.argument("clip_index", type=int)
@click.argument("lut_path")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def apply_lut(ctx, clip_index, lut_path, dry_run):
    result = color_apply_lut_impl(clip_index=clip_index, lut_path=lut_path, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))

@color.command(name="reset")
@click.argument("clip_index", type=int)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def color_reset(ctx, clip_index, dry_run):
    result = color_reset_impl(clip_index=clip_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))

@color.command(name="copy-grade")
@click.option("--from", "from_index", type=int, required=True)
@click.pass_context
def copy_grade(ctx, from_index):
    result = color_copy_grade_impl(from_index=from_index)
    output(result, pretty=ctx.obj.get("pretty"))

@color.command(name="paste-grade")
@click.option("--to", "to_index", type=int, required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def paste_grade(ctx, to_index, dry_run):
    result = color_paste_grade_impl(to_index=to_index, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))

# ネストグループ: dr color node list|add|delete
@color.group()
def node():
    """Node graph operations."""

@node.command(name="list")
@click.argument("clip_index", type=int)
@click.pass_context
def node_list(ctx, clip_index): ...

# dr color still grab|list|apply
@color.group()
def still():
    """Still store operations."""
```

スキーマ登録:
```python
register_schema("color.apply_lut", output_model=LutApplyOutput, input_model=LutApplyInput)
register_schema("color.reset", output_model=ColorResetOutput)
register_schema("color.copy_grade", output_model=CopyGradeOutput)
register_schema("color.paste_grade", output_model=PasteGradeOutput)
register_schema("color.node.list", output_model=NodeListOutput)
register_schema("color.node.add", output_model=NodeAddOutput)
register_schema("color.node.delete", output_model=NodeDeleteOutput)
register_schema("color.still.grab", output_model=StillGrabOutput)
register_schema("color.still.list", output_model=StillListOutput)
register_schema("color.still.apply", output_model=StillApplyOutput)
```

**Key tests:**

```python
def test_apply_lut_path_traversal_rejected():
    with pytest.raises(ValueError, match="Path traversal"):
        color_apply_lut_impl(clip_index=0, lut_path="../../../etc/passwd")

def test_apply_lut_invalid_extension():
    with pytest.raises(ValueError, match="Extension"):
        color_apply_lut_impl(clip_index=0, lut_path="/tmp/malicious.exe")

def test_apply_lut_dry_run():
    result = color_apply_lut_impl(clip_index=0, lut_path="/valid/path.cube", dry_run=True)
    assert result["dry_run"] is True
    assert result["action"] == "apply_lut"

def test_apply_lut_impl(mock_timeline):
    # mock_timeline のクリップ0にLUT適用
    result = color_apply_lut_impl(clip_index=0, lut_path="/luts/rec709.cube")
    assert result["applied"].endswith("rec709.cube")

def test_color_reset_dry_run():
    result = color_reset_impl(clip_index=2, dry_run=True)
    assert result == {"dry_run": True, "action": "reset", "clip_index": 2}

def test_color_reset_impl(mock_timeline):
    result = color_reset_impl(clip_index=0)
    assert result["reset"] is True

def test_copy_paste_grade_roundtrip(mock_timeline):
    copy_result = color_copy_grade_impl(from_index=0)
    assert copy_result["copied_from"] == 0
    paste_result = color_paste_grade_impl(to_index=1)
    assert paste_result["pasted_to"] == 1

def test_paste_grade_dry_run():
    result = color_paste_grade_impl(to_index=3, dry_run=True)
    assert result["dry_run"] is True

def test_node_list_impl(mock_timeline):
    result = node_list_impl(clip_index=0)
    assert isinstance(result, list)
    assert all("index" in n for n in result)

def test_still_grab_dry_run():
    result = still_grab_impl(clip_index=0, dry_run=True)
    assert result["dry_run"] is True

def test_still_apply_dry_run():
    result = still_apply_impl(clip_index=0, still_index=1, dry_run=True)
    assert result["dry_run"] is True

def test_dr_color_apply_lut_cli_dry_run():
    result = CliRunner().invoke(dr, ["color", "apply-lut", "0", "/luts/film.cube", "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is True
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_color.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_color.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/commands/color.py tests/unit/test_color.py
git commit -m "feat: add dr color commands with LUT path validation and dry-run support"
```

---

### Task 16: commands/media.py — dr media

**Files:**
- Create: `src/davinci_cli/commands/media.py`
- Test: `tests/unit/test_media.py`

**What to implement:**

Pydanticモデル:
```python
class MediaItem(BaseModel):
    clip_name: str
    file_path: str | None = None
    duration: str | None = None
    fps: float | None = None
    width: int | None = None
    height: int | None = None

class FolderInfo(BaseModel):
    name: str
    clip_count: int | None = None
```

_impl関数群:
```python
def media_list_impl(folder_name: str | None = None,
                    fields: list[str] | None = None) -> list[dict]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    media_pool = project.GetMediaPool()

    if folder_name:
        folder = _find_folder_by_name(media_pool.GetRootFolder(), folder_name)
        if not folder:
            raise ValueError(f"Folder not found: {folder_name}")
    else:
        folder = media_pool.GetRootFolder()

    clips = folder.GetClipList()
    items = []
    for clip in clips:
        info = {
            "clip_name": clip.GetName(),
            "file_path": clip.GetClipProperty("File Path"),
            "duration": clip.GetClipProperty("Duration"),
            "fps": clip.GetClipProperty("FPS"),
        }
        if fields:
            info = {k: v for k, v in info.items() if k in fields}
        items.append(info)
    return items

def media_import_impl(paths: list[str]) -> dict:
    # 全パスをvalidate_pathで検証してからインポート
    validated = []
    for p in paths:
        vp = validate_path(p)  # パストラバーサル防止
        if not vp.exists():
            raise FileNotFoundError(f"File not found: {p}")
        validated.append(str(vp))

    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    media_pool = project.GetMediaPool()
    imported = media_pool.ImportMedia(validated)
    return {
        "imported_count": len(imported) if imported else 0,
        "paths": validated,
    }

def folder_list_impl() -> list[dict]:
    media_pool = _get_media_pool()
    root = media_pool.GetRootFolder()
    return _collect_folders(root)

def folder_create_impl(name: str) -> dict:
    media_pool = _get_media_pool()
    folder = media_pool.AddSubFolder(media_pool.GetRootFolder(), name)
    if not folder:
        raise ValueError(f"Failed to create folder: {name}")
    return {"created": name}

def folder_delete_impl(name: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "folder_delete", "name": name}
    media_pool = _get_media_pool()
    folder = _find_folder_by_name(media_pool.GetRootFolder(), name)
    if not folder:
        raise ValueError(f"Folder not found: {name}")
    media_pool.DeleteFolders([folder])
    return {"deleted": name}
```

CLIコマンド構造:
```python
@click.group()
def media():
    """Media pool operations."""

@media.command(name="list")
@click.option("--folder", default=None, help="Folder name to list")
@click.option("--fields", default=None, help="Comma-separated field list")
@click.pass_context
def media_list(ctx, folder, fields):
    field_list = fields.split(",") if fields else None
    result = media_list_impl(folder_name=folder, fields=field_list)
    output(result, pretty=ctx.obj.get("pretty"))

@media.command(name="import")
@click.argument("paths", nargs=-1, required=True)
@click.pass_context
def media_import(ctx, paths):
    result = media_import_impl(paths=list(paths))
    output(result, pretty=ctx.obj.get("pretty"))

@media.group(name="folder")
def media_folder():
    """Media folder operations."""

@media_folder.command(name="list")
@click.pass_context
def folder_list(ctx):
    result = folder_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))

@media_folder.command(name="create")
@click.argument("name")
@click.pass_context
def folder_create(ctx, name):
    result = folder_create_impl(name=name)
    output(result, pretty=ctx.obj.get("pretty"))

@media_folder.command(name="delete")
@click.argument("name")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def folder_delete(ctx, name, dry_run):
    result = folder_delete_impl(name=name, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))
```

**Key tests:**

```python
def test_media_import_path_traversal_rejected():
    with pytest.raises(ValueError, match="Path traversal"):
        media_import_impl(paths=["../../../etc/shadow"])

def test_media_import_file_not_found():
    with pytest.raises(FileNotFoundError):
        media_import_impl(paths=["/nonexistent/file.mp4"])

def test_media_list_impl(mock_media_pool):
    mock_media_pool.GetRootFolder().GetClipList.return_value = [mock_clip("clip1"), mock_clip("clip2")]
    result = media_list_impl()
    assert len(result) == 2
    assert result[0]["clip_name"] == "clip1"

def test_media_list_fields_filter(mock_media_pool):
    result = media_list_impl(fields=["clip_name"])
    assert all(set(r.keys()) == {"clip_name"} for r in result)

def test_media_list_folder_not_found(mock_media_pool):
    with pytest.raises(ValueError, match="Folder not found"):
        media_list_impl(folder_name="NonExistentFolder")

def test_media_import_impl(mock_media_pool, tmp_path):
    test_file = tmp_path / "video.mp4"
    test_file.touch()
    mock_media_pool.ImportMedia.return_value = [object()]
    result = media_import_impl(paths=[str(test_file)])
    assert result["imported_count"] == 1

def test_folder_list_impl(mock_media_pool):
    result = folder_list_impl()
    assert isinstance(result, list)

def test_folder_create_impl(mock_media_pool):
    result = folder_create_impl(name="VFX Shots")
    assert result["created"] == "VFX Shots"

def test_folder_delete_dry_run():
    result = folder_delete_impl(name="old_folder", dry_run=True)
    assert result["dry_run"] is True
    assert result["action"] == "folder_delete"

def test_dr_media_import_cli_path_traversal():
    result = CliRunner().invoke(dr, ["media", "import", "../secret.mp4"])
    assert result.exit_code == 3  # ValidationError → exit 3
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_media.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_media.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/commands/media.py tests/unit/test_media.py
git commit -m "feat: add dr media commands with path validation on import"
```

---

### Task 17: commands/deliver.py — dr deliver（最重要、--dry-run必須）

**Files:**
- Create: `src/davinci_cli/commands/deliver.py`
- Test: `tests/unit/test_deliver.py`

**What to implement:**

Pydanticモデル:
```python
class RenderPreset(BaseModel):
    name: str

class RenderJobInput(BaseModel):
    preset_name: str | None = None
    timeline_name: str | None = None  # None=現在のタイムライン
    output_dir: str
    filename: str

class RenderJobInfo(BaseModel):
    job_id: str
    timeline_name: str
    preset_name: str | None = None
    status: str
    progress: float | None = None  # 0.0〜100.0
    eta_seconds: int | None = None

class RenderStatusOutput(BaseModel):
    jobs: list[RenderJobInfo]
    overall_progress: float | None = None
```

_impl関数群:
```python
def deliver_preset_list_impl() -> list[dict]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    presets = project.GetRenderPresets()
    return [{"name": p} for p in presets]

def deliver_preset_load_impl(name: str) -> dict:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    success = project.LoadRenderPreset(name)
    if not success:
        raise ValueError(f"Preset not found: {name}")
    return {"loaded": name}

def deliver_add_job_impl(job_data: dict, dry_run: bool = False) -> dict:
    validated = RenderJobInput.model_validate(job_data)
    if dry_run:
        return {"dry_run": True, "action": "add_job", "job": validated.model_dump()}
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    # レンダー設定を適用
    project.SetRenderSettings({
        "SelectAllFrames": True,
        "TargetDir": validated.output_dir,
        "CustomName": validated.filename,
    })
    job_id = project.AddRenderJob()
    if not job_id:
        raise RuntimeError("Failed to add render job")
    return {"job_id": job_id, "output_dir": validated.output_dir}

def deliver_list_jobs_impl(fields: list[str] | None = None) -> list[dict]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    jobs = project.GetRenderJobList()
    result = []
    for job in jobs:
        info = {
            "job_id": job.get("JobId", ""),
            "timeline_name": job.get("TimelineName", ""),
            "status": job.get("JobStatus", "Queued"),
            "progress": job.get("CompletionPercentage"),
        }
        if fields:
            info = {k: v for k, v in info.items() if k in fields}
        result.append(info)
    return result

def deliver_start_impl(job_ids: list[str] | None = None,
                        dry_run: bool = False) -> dict:
    """
    レンダー開始。--dry-runなしでは実行しない。
    dry_run=True時: {"would_render": true, "jobs": [...], "estimated_seconds": N}
    """
    jobs = deliver_list_jobs_impl()
    if job_ids:
        jobs = [j for j in jobs if j["job_id"] in job_ids]

    if dry_run:
        return {
            "would_render": True,
            "jobs": jobs,
            "estimated_seconds": len(jobs) * 60,  # 仮の見積もり
        }

    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if job_ids:
        for jid in job_ids:
            project.StartRendering(jid)
    else:
        project.StartRendering()
    return {"rendering_started": True, "job_count": len(jobs)}

def deliver_stop_impl() -> dict:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    project.StopRendering()
    return {"stopped": True}

def deliver_status_impl() -> dict:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    jobs = project.GetRenderJobList()
    statuses = []
    for job in jobs:
        statuses.append({
            "job_id": job.get("JobId"),
            "status": job.get("JobStatus"),
            "percent": job.get("CompletionPercentage", 0),
            "eta": job.get("EstimatedTimeRemainingInMs", 0) // 1000,
        })
    return {"jobs": statuses}
```

CLIコマンド構造:
```python
@click.group()
def deliver():
    """Render & delivery operations."""

@deliver.group(name="preset")
def deliver_preset():
    """Render preset operations."""

@deliver_preset.command(name="list")
@click.pass_context
def preset_list(ctx):
    result = deliver_preset_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))

@deliver_preset.command(name="load")
@click.argument("name")
@click.pass_context
def preset_load(ctx, name):
    result = deliver_preset_load_impl(name=name)
    output(result, pretty=ctx.obj.get("pretty"))

@deliver.command(name="add-job")
@click.option("--json", "json_input", required=True, help='Job params as JSON')
@click.option("--dry-run", is_flag=True)
@click.pass_context
def add_job(ctx, json_input, dry_run):
    job_data = json.loads(json_input)
    result = deliver_add_job_impl(job_data=job_data, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))

@deliver.command(name="list-jobs")
@click.option("--fields", default=None)
@click.pass_context
def list_jobs(ctx, fields):
    field_list = fields.split(",") if fields else None
    result = deliver_list_jobs_impl(fields=field_list)
    output(result, pretty=ctx.obj.get("pretty"))

@deliver.command(name="start")
@click.option("--job-ids", default=None, help="Comma-separated job IDs")
@click.option("--dry-run", is_flag=True,
              help="[REQUIRED] Confirm render plan before execution")
@click.pass_context
def start(ctx, job_ids, dry_run):
    ids = job_ids.split(",") if job_ids else None
    result = deliver_start_impl(job_ids=ids, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))

@deliver.command(name="stop")
@click.pass_context
def stop(ctx):
    result = deliver_stop_impl()
    output(result, pretty=ctx.obj.get("pretty"))

@deliver.command(name="status")
@click.pass_context
def status(ctx):
    result = deliver_status_impl()
    output(result, pretty=ctx.obj.get("pretty"))
```

**Key tests:**

```python
def test_deliver_preset_list_impl(mock_project):
    mock_project.GetRenderPresets.return_value = ["H.264 Master", "YouTube 1080p"]
    result = deliver_preset_list_impl()
    assert len(result) == 2
    assert result[0]["name"] == "H.264 Master"

def test_deliver_preset_load_not_found(mock_project):
    mock_project.LoadRenderPreset.return_value = False
    with pytest.raises(ValueError, match="Preset not found"):
        deliver_preset_load_impl(name="NonExistent")

def test_deliver_add_job_dry_run():
    result = deliver_add_job_impl(
        job_data={"output_dir": "/tmp", "filename": "output"},
        dry_run=True
    )
    assert result["dry_run"] is True
    assert result["action"] == "add_job"

def test_deliver_add_job_validation_error():
    # 必須フィールド欠落
    with pytest.raises(Exception):  # Pydantic ValidationError
        deliver_add_job_impl(job_data={"filename": "output"})  # output_dir欠落

def test_deliver_start_dry_run_returns_plan(mock_project):
    mock_project.GetRenderJobList.return_value = [
        {"JobId": "job1", "TimelineName": "Edit", "JobStatus": "Queued"}
    ]
    result = deliver_start_impl(dry_run=True)
    assert result["would_render"] is True
    assert isinstance(result["jobs"], list)
    assert "estimated_seconds" in result

def test_deliver_start_dry_run_with_job_ids(mock_project):
    mock_project.GetRenderJobList.return_value = [
        {"JobId": "job1", "TimelineName": "Edit", "JobStatus": "Queued"},
        {"JobId": "job2", "TimelineName": "VFX", "JobStatus": "Queued"},
    ]
    result = deliver_start_impl(job_ids=["job1"], dry_run=True)
    assert result["would_render"] is True
    assert len(result["jobs"]) == 1

def test_deliver_start_without_dry_run(mock_project):
    # dry_run=False で実際にレンダー開始
    mock_project.GetRenderJobList.return_value = []
    result = deliver_start_impl(dry_run=False)
    assert result["rendering_started"] is True

def test_deliver_list_jobs_fields(mock_project):
    mock_project.GetRenderJobList.return_value = [
        {"JobId": "j1", "TimelineName": "Edit", "JobStatus": "Queued", "CompletionPercentage": 0}
    ]
    result = deliver_list_jobs_impl(fields=["job_id", "status"])
    assert all(set(r.keys()) == {"job_id", "status"} for r in result)

def test_deliver_status_impl(mock_project):
    result = deliver_status_impl()
    assert "jobs" in result

def test_dr_deliver_start_cli_dry_run():
    result = CliRunner().invoke(dr, ["deliver", "start", "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["would_render"] is True

def test_dr_deliver_add_job_cli_json():
    result = CliRunner().invoke(dr, [
        "deliver", "add-job",
        "--json", '{"output_dir": "/tmp", "filename": "output"}',
        "--dry-run"
    ])
    assert result.exit_code == 0
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_deliver.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_deliver.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/commands/deliver.py tests/unit/test_deliver.py
git commit -m "feat: add dr deliver commands with mandatory dry-run workflow for render start"
```

---

### Task 18: mcp/server.py — FastMCPサーバー

**Files:**
- Create: `src/davinci_cli/mcp/server.py`
- Create: `src/davinci_cli/mcp/__init__.py`
- Test: `tests/unit/test_mcp_server.py`

**What to implement:**

```python
# src/davinci_cli/mcp/server.py
from fastmcp import FastMCP
from davinci_cli.commands.system import ping_impl, version_impl, edition_impl, info_impl
from davinci_cli.commands.project import (
    project_list_impl, project_open_impl, project_close_impl,
    project_create_impl, project_delete_impl, project_save_impl, project_info_impl,
)
from davinci_cli.commands.timeline import (
    timeline_list_impl, timeline_current_impl, timeline_switch_impl,
    timeline_create_impl, timeline_delete_impl, timeline_export_impl,
    marker_list_impl, marker_add_impl, marker_delete_impl,
)
from davinci_cli.commands.clip import (
    clip_list_impl, clip_info_impl, clip_select_impl,
    clip_property_get_impl, clip_property_set_impl,
)
from davinci_cli.commands.color import (
    color_apply_lut_impl, color_reset_impl,
    color_copy_grade_impl, color_paste_grade_impl,
    node_list_impl, node_add_impl, node_delete_impl,
    still_grab_impl, still_list_impl, still_apply_impl,
)
from davinci_cli.commands.media import (
    media_list_impl, media_import_impl,
    folder_list_impl, folder_create_impl, folder_delete_impl,
)
from davinci_cli.commands.deliver import (
    deliver_preset_list_impl, deliver_preset_load_impl,
    deliver_add_job_impl, deliver_list_jobs_impl,
    deliver_start_impl, deliver_stop_impl, deliver_status_impl,
)

mcp = FastMCP("davinci-cli")

# ---- system ----
@mcp.tool(description="""
Resolve接続確認を行う。
AGENT RULES:
- 接続確認のみ。引数不要。
""")
def system_ping() -> dict:
    return ping_impl()

@mcp.tool(description="""
DaVinci Resolveのバージョン情報を返す。
AGENT RULES:
- 引数不要。バージョン確認に使う。
""")
def system_version() -> dict:
    return version_impl()

# ---- project ----
@mcp.tool(description="""
プロジェクト一覧を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること（例: fields="name,id"）
- 全フィールド取得はコンテキストウィンドウを消費する
""")
def project_list(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return project_list_impl(fields=field_list)

@mcp.tool(description="""
プロジェクトを開く。
AGENT RULES:
- 必ずdry_run=Trueで事前確認し、ユーザーに結果を提示してから実行すること
- dry_run=Falseは現在のプロジェクトを閉じる副作用がある
""")
def project_open(name: str, dry_run: bool = True) -> dict:
    return project_open_impl(name=name, dry_run=dry_run)

@mcp.tool(description="""
現在のプロジェクトを閉じる。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
- 未保存の変更は失われる
""")
def project_close(dry_run: bool = True) -> dict:
    return project_close_impl(dry_run=dry_run)

@mcp.tool(description="""
新規プロジェクトを作成する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
""")
def project_create(name: str, dry_run: bool = True) -> dict:
    return project_create_impl(name=name, dry_run=dry_run)

@mcp.tool(description="""
プロジェクトを削除する（破壊的操作）。
AGENT RULES:
- 必ずdry_run=Trueで事前確認し、ユーザーの明示的な承認を得てから実行
- 削除したプロジェクトは復元できない
""")
def project_delete(name: str, dry_run: bool = True) -> dict:
    return project_delete_impl(name=name, dry_run=dry_run)

# ---- deliver（特別警告） ----
@mcp.tool(description="""
レンダージョブを追加する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
- job_dataはJSON文字列で渡す: {"output_dir": "...", "filename": "..."}
""")
def deliver_add_job(job_data: dict, dry_run: bool = True) -> dict:
    return deliver_add_job_impl(job_data=job_data, dry_run=dry_run)

@mcp.tool(description="""
レンダーキューのジョブ一覧を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること（例: fields="job_id,status,percent"）
""")
def deliver_list_jobs(fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return deliver_list_jobs_impl(fields=field_list)

@mcp.tool(description="""
レンダーを開始する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること（"would_render": true と jobs一覧が返る）
- ユーザーに確認結果を提示し、明示的な承認を得てからdry_run=Falseで実行すること
- この操作はDaVinci Resolveのエンコードリソースを大量消費する
""")
def deliver_start(job_ids: list[str] | None = None, dry_run: bool = True) -> dict:
    return deliver_start_impl(job_ids=job_ids, dry_run=dry_run)

@mcp.tool(description="""
レンダーを停止する。
AGENT RULES:
- 実行中のレンダーを即座に停止する
- 途中のファイルは不完全な状態で残る
""")
def deliver_stop() -> dict:
    return deliver_stop_impl()

@mcp.tool(description="""
レンダー進捗を返す（percent, status, eta）。
AGENT RULES:
- 引数不要。ポーリング間隔は最低5秒空けること。
""")
def deliver_status() -> dict:
    return deliver_status_impl()

# ---- color ----
@mcp.tool(description="""
クリップにLUTを適用する。
AGENT RULES:
- 必ずdry_run=Trueで事前確認すること
- lut_pathはシステム上の絶対パス（".."を含むパスは拒絶される）
""")
def color_apply_lut(clip_index: int, lut_path: str, dry_run: bool = True) -> dict:
    return color_apply_lut_impl(clip_index=clip_index, lut_path=lut_path, dry_run=dry_run)

# ---- media ----
@mcp.tool(description="""
メディアプールのクリップ一覧を返す。
AGENT RULES:
- 必ずfields引数でフィールドを絞ること（例: fields="clip_name,file_path"）
- folder引数でフォルダを絞り込むこと
""")
def media_list(folder: str | None = None, fields: str | None = None) -> list[dict]:
    field_list = fields.split(",") if fields else None
    return media_list_impl(folder_name=folder, fields=field_list)

@mcp.tool(description="""
メディアをインポートする。
AGENT RULES:
- pathsには絶対パスのリストを渡すこと
- ".."を含むパスはセキュリティ上の理由で拒絶される
""")
def media_import(paths: list[str]) -> dict:
    return media_import_impl(paths=paths)

if __name__ == "__main__":
    mcp.run()
```

エントリーポイント設定（`pyproject.toml`）:
```toml
[project.scripts]
dr = "davinci_cli.cli:dr"
dr-mcp = "davinci_cli.mcp.server:mcp.run"
```

**Key tests:**

```python
# tests/unit/test_mcp_server.py
import pytest
from davinci_cli.mcp.server import mcp

def test_mcp_server_instantiated():
    assert mcp is not None
    assert mcp.name == "davinci-cli"

def test_mcp_tools_registered():
    tool_names = [t.name for t in mcp.tools]
    assert "system_ping" in tool_names
    assert "project_list" in tool_names
    assert "project_open" in tool_names
    assert "deliver_start" in tool_names
    assert "deliver_add_job" in tool_names
    assert "color_apply_lut" in tool_names
    assert "media_list" in tool_names

def test_deliver_start_description_contains_warning():
    tool = next(t for t in mcp.tools if t.name == "deliver_start")
    assert "dry_run=True" in tool.description
    assert "AGENT RULES" in tool.description

def test_deliver_add_job_description_contains_dry_run():
    tool = next(t for t in mcp.tools if t.name == "deliver_add_job")
    assert "dry_run=True" in tool.description

def test_project_list_description_contains_fields_rule():
    tool = next(t for t in mcp.tools if t.name == "project_list")
    assert "fields" in tool.description
    assert "AGENT RULES" in tool.description

def test_color_apply_lut_description_contains_path_warning():
    tool = next(t for t in mcp.tools if t.name == "color_apply_lut")
    assert ".." in tool.description

def test_mcp_tool_deliver_start_dry_run_default(monkeypatch, mock_project):
    # デフォルトはdry_run=True
    mock_project.GetRenderJobList.return_value = []
    tool = next(t for t in mcp.tools if t.name == "deliver_start")
    sig = inspect.signature(tool.fn)
    assert sig.parameters["dry_run"].default is True

def test_mcp_tool_project_open_dry_run_default():
    tool = next(t for t in mcp.tools if t.name == "project_open")
    sig = inspect.signature(tool.fn)
    assert sig.parameters["dry_run"].default is True
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_mcp_server.py -v` → FAIL確認
**Step 2:** 実装 → `python -m pytest tests/unit/test_mcp_server.py -v` → PASS確認
**Step 3:**
```bash
git add src/davinci_cli/mcp/ tests/unit/test_mcp_server.py pyproject.toml
git commit -m "feat: add FastMCP server exposing all _impl functions with agent instructions in descriptions"
```

---

### Task 19: SKILL.md — Claude Code用スキルファイル

**Files:**
- Create: `SKILL.md`（プロジェクトルート）

**What to implement:**

完全な `SKILL.md` の内容:

```markdown
---
name: davinci-cli
version: 1.0.0
description: DaVinci Resolve CLI for AI agents
---

# davinci-cli SKILL

DaVinci Resolve を CLI/MCP経由で操作するエージェントスキル。

## AGENT RULES（必須）

### 1. Write/Delete前は必ずdry-runで確認
破壊的操作（project open/close/delete, deliver start, color apply-lut等）は、
**必ず `--dry-run` を付けて実行結果をユーザーに提示し、承認を得てから** 本実行すること。

```bash
# NG: いきなり実行
dr project delete "OldProject"

# OK: 事前確認 → ユーザー承認 → 本実行
dr project delete "OldProject" --dry-run
# → {"dry_run": true, "action": "delete", "name": "OldProject"}
# ユーザー: 「OK」
dr project delete "OldProject"
```

### 2. list系は必ず--fieldsで絞り込む

```bash
# NG: 全フィールド取得（コンテキストウィンドウ浪費）
dr project list

# OK: 必要なフィールドのみ取得
dr project list --fields name,id
dr clip list --fields index,name,duration
dr media list --fields clip_name,file_path
```

### 3. 入力は--jsonで渡す

```bash
# NG: 位置引数での渡し方（エラーが出やすい）
dr deliver add-job ...

# OK: --json でPydanticバリデーション付きで渡す
dr deliver add-job --json '{"output_dir": "/renders", "filename": "final_v1"}' --dry-run
dr timeline create --json '{"name": "Assembly Cut", "fps": 24.0}' --dry-run
```

### 4. 不明なパラメータはdr schema で確認

```bash
# コマンドの入出力スキーマをリアルタイム確認
dr schema show project.open
dr schema show deliver.add_job
dr schema show clip.property.set
dr schema list  # 全コマンド一覧
```

---

## コマンド体系

### dr system — システム情報
| コマンド | 説明 |
|---|---|
| `dr system ping` | Resolve接続確認 |
| `dr system version` | バージョン情報 |
| `dr system edition` | エディション（Free/Studio）確認 |
| `dr system info` | 総合情報（バージョン+エディション+現在プロジェクト） |

### dr schema — スキーマ自己解決
| コマンド | 説明 |
|---|---|
| `dr schema show <command>` | 指定コマンドのJSON Schema |
| `dr schema list` | 全登録コマンド一覧 |

### dr project — プロジェクト操作
| コマンド | dry-run | 説明 |
|---|---|---|
| `dr project list [--fields]` | - | プロジェクト一覧 |
| `dr project open <name> [--dry-run]` | 必須 | プロジェクトを開く |
| `dr project close [--dry-run]` | 必須 | 現在のプロジェクトを閉じる |
| `dr project create <name> [--dry-run]` | 必須 | 新規作成 |
| `dr project delete <name> [--dry-run]` | 必須 | 削除（破壊的） |
| `dr project save` | - | 保存 |
| `dr project info [--fields]` | - | 現在のプロジェクト情報 |
| `dr project settings get [<key>]` | - | 設定値取得 |
| `dr project settings set <key> <value> [--dry-run]` | 必須 | 設定値変更 |

### dr timeline — タイムライン操作
| コマンド | dry-run | 説明 |
|---|---|---|
| `dr timeline list [--fields]` | - | タイムライン一覧 |
| `dr timeline current [--fields]` | - | 現在のタイムライン情報 |
| `dr timeline switch <name> [--dry-run]` | 必須 | タイムライン切り替え |
| `dr timeline create [--json] [--dry-run]` | 必須 | 新規タイムライン |
| `dr timeline delete <name> [--dry-run]` | 必須 | 削除（破壊的） |
| `dr timeline export [--json] [--dry-run]` | 必須 | XML/AAF/EDLエクスポート |
| `dr timeline marker list` | - | マーカー一覧 |
| `dr timeline marker add [--json] [--dry-run]` | 必須 | マーカー追加 |
| `dr timeline marker delete <frame> [--dry-run]` | 必須 | マーカー削除 |

### dr clip — クリップ操作
| コマンド | dry-run | 説明 |
|---|---|---|
| `dr clip list [--fields] [--timeline]` | - | クリップ一覧（NDJSON対応） |
| `dr clip info <index> [--fields]` | - | クリップ詳細 |
| `dr clip select <index>` | - | クリップ選択 |
| `dr clip property get <index> <key>` | - | プロパティ取得 |
| `dr clip property set <index> <key> <value> [--dry-run]` | 必須 | プロパティ設定 |

### dr color — カラーグレーディング
| コマンド | dry-run | 説明 |
|---|---|---|
| `dr color apply-lut <index> <path> [--dry-run]` | 必須 | LUT適用 |
| `dr color reset <index> [--dry-run]` | 必須 | グレードリセット |
| `dr color copy-grade --from <index>` | - | グレードコピー |
| `dr color paste-grade --to <index> [--dry-run]` | 必須 | グレードペースト |
| `dr color node list <index>` | - | ノード一覧 |
| `dr color node add <index> [--dry-run]` | 必須 | ノード追加 |
| `dr color node delete <index> <node> [--dry-run]` | 必須 | ノード削除 |
| `dr color still grab <index> [--dry-run]` | 必須 | スチル取得 |
| `dr color still list` | - | スチル一覧 |
| `dr color still apply <clip> <still> [--dry-run]` | 必須 | スチル適用 |

### dr media — メディアプール
| コマンド | dry-run | 説明 |
|---|---|---|
| `dr media list [--folder] [--fields]` | - | メディア一覧 |
| `dr media import <path...>` | - | メディアインポート（パス検証付き） |
| `dr media folder list` | - | フォルダ一覧 |
| `dr media folder create <name>` | - | フォルダ作成 |
| `dr media folder delete <name> [--dry-run]` | 必須 | フォルダ削除 |

### dr deliver — レンダリング（最重要: dry-run必須）
| コマンド | dry-run | 説明 |
|---|---|---|
| `dr deliver preset list` | - | レンダープリセット一覧 |
| `dr deliver preset load <name>` | - | プリセット読み込み |
| `dr deliver add-job --json '{...}' [--dry-run]` | 必須 | ジョブ追加 |
| `dr deliver list-jobs [--fields]` | - | ジョブ一覧 |
| `dr deliver start [--job-ids] [--dry-run]` | **強制** | レンダー開始 |
| `dr deliver stop` | - | レンダー停止 |
| `dr deliver status` | - | 進捗確認 |

---

## よくある使用パターン

### パターン1: プロジェクト確認からオープンまで
```bash
# 1. 利用可能プロジェクト確認
dr project list --fields name

# 2. dry-runで確認
dr project open "Feature_Film_v3" --dry-run
# → {"dry_run": true, "action": "open", "name": "Feature_Film_v3"}

# 3. ユーザー承認後に実行
dr project open "Feature_Film_v3"
```

### パターン2: レンダーワークフロー（必須手順）
```bash
# 1. レンダープリセット確認
dr deliver preset list

# 2. ジョブ追加（dry-run）
dr deliver add-job --json '{"preset_name": "H.264 Master", "output_dir": "/renders/v1", "filename": "film_v1"}' --dry-run

# 3. ジョブ追加（本実行）
dr deliver add-job --json '{"preset_name": "H.264 Master", "output_dir": "/renders/v1", "filename": "film_v1"}'

# 4. キュー確認
dr deliver list-jobs --fields job_id,status

# 5. レンダー開始前の確認（必須）
dr deliver start --dry-run
# → {"would_render": true, "jobs": [...], "estimated_seconds": 3600}

# 6. ユーザー承認後に実行
dr deliver start

# 7. 進捗確認（5秒以上間隔）
dr deliver status
```

### パターン3: LUT一括適用
```bash
# 1. クリップ一覧（インデックス確認）
dr clip list --fields index,name

# 2. dry-runで確認
dr color apply-lut 0 /luts/FilmLook_v2.cube --dry-run
# → {"dry_run": true, "action": "apply_lut", "clip_index": 0, "lut_path": "..."}

# 3. 承認後に実行
dr color apply-lut 0 /luts/FilmLook_v2.cube
```

### パターン4: スキーマ不明時
```bash
# 使い方が不明なコマンドはスキーマで確認
dr schema show deliver.add_job
dr schema show timeline.create
dr schema list  # 全コマンド確認
```
```

**Key tests:**（ファイル存在・必須セクション確認）

```python
# tests/unit/test_skill_md.py
from pathlib import Path

SKILL_MD = Path("SKILL.md")

def test_skill_md_exists():
    assert SKILL_MD.exists(), "SKILL.md must exist in project root"

def test_skill_md_has_frontmatter():
    content = SKILL_MD.read_text()
    assert content.startswith("---"), "Must have YAML frontmatter"
    assert "name: davinci-cli" in content
    assert "version: 1.0.0" in content

def test_skill_md_has_agent_rules():
    content = SKILL_MD.read_text()
    assert "AGENT RULES" in content
    assert "dry-run" in content.lower() or "--dry-run" in content

def test_skill_md_has_all_command_groups():
    content = SKILL_MD.read_text()
    for group in ["dr system", "dr schema", "dr project", "dr timeline",
                  "dr clip", "dr color", "dr media", "dr deliver"]:
        assert group in content, f"Missing command group: {group}"

def test_skill_md_has_usage_patterns():
    content = SKILL_MD.read_text()
    assert "パターン" in content or "Pattern" in content

def test_skill_md_deliver_has_mandatory_dry_run():
    content = SKILL_MD.read_text()
    # deliverセクションにdry-run必須の記載
    deliver_section_start = content.find("dr deliver")
    assert deliver_section_start != -1
    deliver_section = content[deliver_section_start:]
    assert "必須" in deliver_section or "required" in deliver_section.lower()
```

**Step 1:** テストを書く → `python -m pytest tests/unit/test_skill_md.py -v` → FAIL確認
**Step 2:** SKILL.md作成 → `python -m pytest tests/unit/test_skill_md.py -v` → PASS確認
**Step 3:**
```bash
git add SKILL.md tests/unit/test_skill_md.py
git commit -m "docs: add SKILL.md for Claude Code integration with mandatory dry-run rules"
```

---

### Task 20: E2Eスモークテスト — MockResolveで全グループ疎通確認

**Files:**
- Create: `tests/e2e/test_smoke.py`
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/mock_resolve.py`（MockResolve定義）

**What to implement:**

MockResolve（DaVinci Resolve APIの最小限モック）:
```python
# tests/e2e/mock_resolve.py
from unittest.mock import MagicMock

def build_mock_resolve():
    """E2Eテスト用の完全なResolveモック。"""
    resolve = MagicMock()
    resolve.GetVersionString.return_value = "19.0.0"
    resolve.GetProductName.return_value = "DaVinci Resolve Studio"

    # ProjectManager
    pm = MagicMock()
    resolve.GetProjectManager.return_value = pm

    # Project
    project = MagicMock()
    pm.GetCurrentProject.return_value = project
    pm.GetProjectListInCurrentFolder.return_value = ["Demo Project", "Test Project"]
    pm.LoadProject.return_value = project
    project.GetName.return_value = "Demo Project"
    project.GetTimelineCount.return_value = 2
    project.GetSetting.return_value = "24"
    project.GetRenderPresets.return_value = ["H.264 Master", "YouTube 1080p"]
    project.LoadRenderPreset.return_value = True
    project.GetRenderJobList.return_value = [
        {"JobId": "job-001", "TimelineName": "Edit", "JobStatus": "Queued",
         "CompletionPercentage": 0}
    ]
    project.AddRenderJob.return_value = "job-002"
    project.SaveProject.return_value = True

    # Timeline
    timeline = MagicMock()
    project.GetCurrentTimeline.return_value = timeline
    project.GetTimelineByIndex.return_value = timeline
    timeline.GetName.return_value = "Main Edit"
    timeline.GetSetting.return_value = "24"
    timeline.GetStartTimecode.return_value = "00:00:00:00"
    timeline.GetTrackCount.return_value = 1

    # Clip
    clip = MagicMock()
    clip.GetName.return_value = "A001_C001.mov"
    clip.GetStart.return_value = 0
    clip.GetEnd.return_value = 240
    clip.GetDuration.return_value = 240
    clip.GetProperty.return_value = "0.0"
    timeline.GetItemListInTrack.return_value = [clip]

    # MediaPool
    media_pool = MagicMock()
    project.GetMediaPool.return_value = media_pool
    root_folder = MagicMock()
    root_folder.GetClipList.return_value = [clip]
    root_folder.GetSubFolderList.return_value = []
    media_pool.GetRootFolder.return_value = root_folder
    media_pool.ImportMedia.return_value = [clip]

    return resolve
```

スモークテスト本体:
```python
# tests/e2e/test_smoke.py
import json
import pytest
from click.testing import CliRunner
from unittest.mock import patch
from davinci_cli.cli import dr
from tests.e2e.mock_resolve import build_mock_resolve

RESOLVE_PATH = "davinci_cli.resolve_bridge.get_resolve"

@pytest.fixture
def mock_resolve():
    resolve = build_mock_resolve()
    with patch(RESOLVE_PATH, return_value=resolve):
        yield resolve

@pytest.fixture
def runner():
    return CliRunner()

class TestSystemSmoke:
    def test_ping(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "ping"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_version(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "version"])
        assert result.exit_code == 0

    def test_info(self, runner, mock_resolve):
        result = runner.invoke(dr, ["system", "info"])
        assert result.exit_code == 0

class TestProjectSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["project", "list", "--fields", "name"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_open_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["project", "open", "Demo Project", "--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_info(self, runner, mock_resolve):
        result = runner.invoke(dr, ["project", "info", "--fields", "name"])
        assert result.exit_code == 0

class TestTimelineSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["timeline", "list", "--fields", "name"])
        assert result.exit_code == 0

    def test_current(self, runner, mock_resolve):
        result = runner.invoke(dr, ["timeline", "current"])
        assert result.exit_code == 0

    def test_switch_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["timeline", "switch", "Main Edit", "--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

class TestClipSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["clip", "list", "--fields", "index,name"])
        assert result.exit_code == 0

    def test_info(self, runner, mock_resolve):
        result = runner.invoke(dr, ["clip", "info", "0"])
        assert result.exit_code == 0

    def test_property_set_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["clip", "property", "set", "0", "Pan", "0.5", "--dry-run"])
        assert result.exit_code == 0

class TestColorSmoke:
    def test_apply_lut_dry_run(self, runner, mock_resolve, tmp_path):
        lut_file = tmp_path / "test.cube"
        lut_file.touch()
        result = runner.invoke(dr, ["color", "apply-lut", "0", str(lut_file), "--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_reset_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["color", "reset", "0", "--dry-run"])
        assert result.exit_code == 0

    def test_node_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["color", "node", "list", "0"])
        assert result.exit_code == 0

class TestMediaSmoke:
    def test_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["media", "list", "--fields", "clip_name"])
        assert result.exit_code == 0

    def test_folder_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["media", "folder", "list"])
        assert result.exit_code == 0

    def test_folder_delete_dry_run(self, runner, mock_resolve):
        result = runner.invoke(dr, ["media", "folder", "delete", "OldFolder", "--dry-run"])
        assert result.exit_code == 0

class TestDeliverSmoke:
    def test_preset_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "preset", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_list_jobs(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "list-jobs", "--fields", "job_id,status"])
        assert result.exit_code == 0

    def test_start_dry_run_returns_plan(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "start", "--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["would_render"] is True
        assert "jobs" in data
        assert "estimated_seconds" in data

    def test_status(self, runner, mock_resolve):
        result = runner.invoke(dr, ["deliver", "status"])
        assert result.exit_code == 0

class TestSchemaSmoke:
    def test_schema_list(self, runner, mock_resolve):
        result = runner.invoke(dr, ["schema", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        commands = [r["command"] for r in data]
        assert "project.list" in commands
        assert "deliver.add_job" in commands

    def test_schema_show_project_open(self, runner, mock_resolve):
        result = runner.invoke(dr, ["schema", "show", "project.open"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "input_schema" in data

class TestMCPServerSmoke:
    def test_mcp_server_importable(self):
        from davinci_cli.mcp.server import mcp
        assert mcp is not None

    def test_mcp_has_deliver_start_tool(self):
        from davinci_cli.mcp.server import mcp
        tool_names = [t.name for t in mcp.tools]
        assert "deliver_start" in tool_names

    def test_mcp_server_entry_point_exists(self):
        # dr-mcp がエントリーポイントとして登録されていること
        import importlib.metadata
        eps = importlib.metadata.entry_points(group="console_scripts")
        ep_names = [ep.name for ep in eps]
        assert "dr-mcp" in ep_names
```

実行方法:
```bash
# E2Eスモークテスト（MockResolve使用、実Resolve不要）
python -m pytest tests/e2e/test_smoke.py -v

# 全テスト一括実行
python -m pytest tests/ -v

# カバレッジ確認
python -m pytest tests/ --cov=davinci_cli --cov-report=term-missing
```

**Key tests:** 上記のスモークテストクラス全体が該当。
各コマンドグループが `exit_code == 0` で完走することが最低限の確認事項。

**Step 1:** MockResolveと空のテストファイルを作成 → `python -m pytest tests/e2e/test_smoke.py -v` → FAIL確認
**Step 2:** 全実装（Task 15〜19）が完了していれば → PASS確認
**Step 3:**
```bash
git add tests/e2e/
git commit -m "test: add E2E smoke tests covering all command groups with MockResolve (real Resolve not required)"
```

---

## ファイル構造サマリ（Task 15-20追加分）

```
src/davinci_cli/
├── security.py               # validate_path() (前提: 既存)
└── commands/
    ├── color.py              # Task 15: apply-lut/reset/copy-grade/paste-grade/node/still
    ├── media.py              # Task 16: list/import/folder
    └── deliver.py            # Task 17: preset/add-job/list-jobs/start/stop/status
src/davinci_cli/mcp/
├── __init__.py               # Task 18
└── server.py                 # Task 18: FastMCP + AGENT RULES in descriptions

SKILL.md                      # Task 19: Claude Code integration skill

tests/
├── unit/
│   ├── test_color.py         # Task 15
│   ├── test_media.py         # Task 16
│   ├── test_deliver.py       # Task 17
│   ├── test_mcp_server.py    # Task 18
│   └── test_skill_md.py      # Task 19
└── e2e/
    ├── __init__.py           # Task 20
    ├── mock_resolve.py       # Task 20: MockResolve定義
    └── test_smoke.py         # Task 20: 全グループ疎通確認
```

---

## 実装完了後の最終確認

```bash
# 全テスト通過確認
python -m pytest tests/ -v --tb=short

# CLI動作確認（MockResolveなし、実Resolveがあれば）
dr system ping
dr schema list
dr deliver start --dry-run

# MCPサーバー起動確認
dr-mcp --help

# カバレッジ目標: 80%以上
python -m pytest tests/ --cov=davinci_cli --cov-report=term-missing --cov-fail-under=80
```
