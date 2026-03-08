"""dr deliver — レンダリング＆デリバリーコマンド。

deliver start は --dry-run による事前確認を推奨する。
_impl 関数の dry_run デフォルトは False（他コマンドと一貫性を保つ）。
MCP 側では dry_run=True がデフォルト（破壊的操作の安全性確保）。
"""
from __future__ import annotations

from typing import Any

import click
from pydantic import BaseModel

from davinci_cli.core.connection import get_resolve
from davinci_cli.core.exceptions import ProjectNotOpenError, ValidationError
from davinci_cli.core.validation import validate_path
from davinci_cli.decorators import dry_run_option, fields_option, json_input_option
from davinci_cli.output.formatter import output
from davinci_cli.schema_registry import register_schema

# --- Pydantic Models ---


class RenderJobInput(BaseModel):
    preset_name: str | None = None
    timeline_name: str | None = None
    output_dir: str
    filename: str


class RenderJobInfo(BaseModel):
    job_id: str
    timeline_name: str | None = None
    status: str | None = None
    progress: float | None = None


class PresetListOutput(BaseModel):
    name: str


class PresetLoadOutput(BaseModel):
    loaded: str


class PresetLoadInput(BaseModel):
    name: str


class DeliverAddJobOutput(BaseModel):
    job_id: str | None = None
    output_dir: str | None = None
    dry_run: bool | None = None
    action: str | None = None
    job: dict | None = None


class DeliverStartInput(BaseModel):
    job_ids: list[str] | None = None


class DeliverStartOutput(BaseModel):
    would_render: bool | None = None
    rendering_started: bool | None = None
    jobs: list[dict] | None = None
    job_count: int | None = None
    estimated_seconds: int | None = None


class DeliverStatusOutput(BaseModel):
    jobs: list[dict]


class DeliverStopOutput(BaseModel):
    stopped: bool


class DeliverDeleteJobInput(BaseModel):
    job_id: str


class DeliverDeleteJobOutput(BaseModel):
    deleted: bool | None = None
    job_id: str
    dry_run: bool | None = None
    action: str | None = None


class DeliverDeleteAllJobsOutput(BaseModel):
    deleted_all: bool | None = None
    dry_run: bool | None = None
    action: str | None = None


class DeliverJobStatusInput(BaseModel):
    job_id: str


class DeliverJobStatusOutput(BaseModel):
    job_id: str
    JobStatus: str | None = None
    CompletionPercentage: float | None = None


class DeliverIsRenderingOutput(BaseModel):
    rendering: bool


class FormatListOutput(BaseModel):
    formats: dict[str, str]


class CodecListOutput(BaseModel):
    format: str
    codecs: dict[str, str]


class CodecListInput(BaseModel):
    format_name: str


class PresetImportInput(BaseModel):
    path: str
    dry_run: bool = False


class PresetImportOutput(BaseModel):
    imported: bool | None = None
    path: str | None = None
    dry_run: bool | None = None
    action: str | None = None


class PresetExportInput(BaseModel):
    name: str
    path: str
    dry_run: bool = False


class PresetExportOutput(BaseModel):
    exported: bool | None = None
    name: str | None = None
    path: str | None = None
    dry_run: bool | None = None
    action: str | None = None


# --- Helper ---


def _get_current_project() -> Any:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise ProjectNotOpenError()
    return project


# --- _impl Functions ---


def deliver_preset_list_impl() -> list[dict]:
    project = _get_current_project()
    presets = project.GetRenderPresetList() or []
    return [{"name": p} for p in presets]


def deliver_preset_load_impl(name: str) -> dict:
    project = _get_current_project()
    success = project.LoadRenderPreset(name)
    if not success:
        raise ValidationError(
            field="preset", reason=f"Preset not found: {name}"
        )
    return {"loaded": name}


def deliver_add_job_impl(job_data: dict, dry_run: bool = False) -> dict:
    validated = RenderJobInput.model_validate(job_data)
    if dry_run:
        return {
            "dry_run": True,
            "action": "add_job",
            "job": validated.model_dump(),
        }
    project = _get_current_project()
    if validated.preset_name:
        success = project.LoadRenderPreset(validated.preset_name)
        if not success:
            raise ValidationError(
                field="preset_name",
                reason=f"Preset not found: {validated.preset_name}",
            )
    if validated.timeline_name:
        count = project.GetTimelineCount()
        found = False
        for i in range(1, count + 1):
            tl = project.GetTimelineByIndex(i)
            if tl and tl.GetName() == validated.timeline_name:
                project.SetCurrentTimeline(tl)
                found = True
                break
        if not found:
            raise ValidationError(
                field="timeline_name",
                reason=f"Timeline not found: {validated.timeline_name}",
            )
    project.SetRenderSettings({
        "SelectAllFrames": True,
        "TargetDir": validated.output_dir,
        "CustomName": validated.filename,
    })
    job_id = project.AddRenderJob()
    if not job_id:
        raise ValidationError(
            field="render_job",
            reason="Failed to add render job",
        )
    return {"job_id": job_id, "output_dir": validated.output_dir}


def deliver_list_jobs_impl(fields: list[str] | None = None) -> list[dict]:
    project = _get_current_project()
    jobs = project.GetRenderJobList() or []
    result: list[dict] = []
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


def deliver_start_impl(
    job_ids: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    jobs = deliver_list_jobs_impl()
    if job_ids:
        jobs = [j for j in jobs if j["job_id"] in job_ids]

    if dry_run:
        return {
            "would_render": True,
            "jobs": jobs,
            "estimated_seconds": len(jobs) * 60,
        }

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


def deliver_stop_impl() -> dict:
    project = _get_current_project()
    project.StopRendering()
    return {"stopped": True}


def deliver_status_impl() -> dict:
    project = _get_current_project()
    jobs = project.GetRenderJobList() or []
    statuses: list[dict] = []
    for job in jobs:
        job_id = job.get("JobId")
        if not job_id:
            continue
        status_info = project.GetRenderJobStatus(job_id) or {}
        statuses.append({
            "job_id": job_id,
            "status": status_info.get("JobStatus"),
            "percent": status_info.get("CompletionPercentage", 0),
            "eta": (status_info.get("EstimatedTimeRemainingInMs", 0) or 0) // 1000,
        })
    return {"jobs": statuses}


def deliver_delete_job_impl(job_id: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "delete_job", "job_id": job_id}
    project = _get_current_project()
    result = project.DeleteRenderJob(job_id)
    if result is False:
        raise ValidationError(
            field="job_id", reason=f"Failed to delete render job: {job_id}"
        )
    return {"deleted": True, "job_id": job_id}


def deliver_delete_all_jobs_impl(dry_run: bool = False) -> dict:
    if dry_run:
        return {"dry_run": True, "action": "delete_all_jobs"}
    project = _get_current_project()
    result = project.DeleteAllRenderJobs()
    if result is False:
        raise ValidationError(
            field="jobs", reason="Failed to delete all render jobs"
        )
    return {"deleted_all": True}


def deliver_job_status_impl(job_id: str) -> dict:
    project = _get_current_project()
    status = project.GetRenderJobStatus(job_id)
    if not status:
        raise ValidationError(
            field="job_id", reason=f"No status for job: {job_id}"
        )
    return {"job_id": job_id, **status}


def deliver_is_rendering_impl() -> dict:
    project = _get_current_project()
    return {"rendering": project.IsRenderingInProgress()}


def deliver_format_list_impl() -> dict:
    """レンダーフォーマット一覧を返す。"""
    project = _get_current_project()
    formats = project.GetRenderFormats()
    return {"formats": formats or {}}


def deliver_codec_list_impl(format_name: str) -> dict:
    """指定フォーマットのコーデック一覧を返す。"""
    project = _get_current_project()
    codecs = project.GetRenderCodecs(format_name)
    return {"format": format_name, "codecs": codecs or {}}


def deliver_preset_import_impl(path: str, dry_run: bool = False) -> dict:
    """レンダープリセットをインポートする。"""
    validated = validate_path(path)
    if not validated.exists():
        raise ValidationError(field="path", reason=f"Preset file not found: {path}")
    if dry_run:
        return {"dry_run": True, "action": "preset_import", "path": str(validated)}
    resolve = get_resolve()
    result = resolve.ImportRenderPreset(str(validated))
    if result is False:
        raise ValidationError(
            field="path", reason=f"Failed to import preset: {path}"
        )
    return {"imported": True, "path": str(validated)}


def deliver_preset_export_impl(
    name: str, path: str, dry_run: bool = False
) -> dict:
    """レンダープリセットをエクスポートする。"""
    validated = validate_path(path)
    if dry_run:
        return {
            "dry_run": True,
            "action": "preset_export",
            "name": name,
            "path": str(validated),
        }
    resolve = get_resolve()
    result = resolve.ExportRenderPreset(name, str(validated))
    if result is False:
        raise ValidationError(
            field="name", reason=f"Failed to export preset: {name}"
        )
    return {"exported": True, "name": name, "path": str(validated)}


# --- CLI Commands ---


@click.group()
def deliver() -> None:
    """Render & delivery operations."""


@deliver.group(name="preset")
def deliver_preset() -> None:
    """Render preset operations."""


@deliver_preset.command(name="list")
@click.pass_context
def preset_list(ctx: click.Context) -> None:
    """レンダープリセット一覧。"""
    result = deliver_preset_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@deliver_preset.command(name="load")
@click.argument("name")
@click.pass_context
def preset_load(ctx: click.Context, name: str) -> None:
    """プリセット読み込み。"""
    result = deliver_preset_load_impl(name=name)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="add-job")
@json_input_option
@dry_run_option
@click.pass_context
def add_job(
    ctx: click.Context, json_input: dict | None, dry_run: bool
) -> None:
    """レンダージョブ追加。"""
    if not json_input:
        raise click.UsageError("--json is required")
    result = deliver_add_job_impl(job_data=json_input, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="list-jobs")
@fields_option
@click.pass_context
def list_jobs(ctx: click.Context, fields: list[str] | None) -> None:
    """レンダージョブ一覧。"""
    result = deliver_list_jobs_impl(fields=fields)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="start")
@click.option("--job-ids", default=None, help="Comma-separated job IDs")
@dry_run_option
@click.pass_context
def start(ctx: click.Context, job_ids: str | None, dry_run: bool) -> None:
    """レンダー開始（--dry-run 推奨）。"""
    ids = job_ids.split(",") if job_ids else None
    result = deliver_start_impl(job_ids=ids, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="stop")
@click.pass_context
def stop(ctx: click.Context) -> None:
    """レンダー停止。"""
    result = deliver_stop_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """レンダー進捗確認。"""
    result = deliver_status_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="delete-job")
@click.argument("job_id")
@dry_run_option
@click.pass_context
def delete_job(ctx: click.Context, job_id: str, dry_run: bool) -> None:
    """レンダージョブ削除。"""
    result = deliver_delete_job_impl(job_id=job_id, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="delete-all-jobs")
@dry_run_option
@click.pass_context
def delete_all_jobs(ctx: click.Context, dry_run: bool) -> None:
    """全レンダージョブ削除。"""
    result = deliver_delete_all_jobs_impl(dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="job-status")
@click.argument("job_id")
@click.pass_context
def job_status(ctx: click.Context, job_id: str) -> None:
    """レンダージョブのステータス確認。"""
    result = deliver_job_status_impl(job_id=job_id)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.command(name="is-rendering")
@click.pass_context
def is_rendering(ctx: click.Context) -> None:
    """レンダリング中かどうか確認。"""
    result = deliver_is_rendering_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.group(name="format")
def deliver_format() -> None:
    """Render format operations."""


@deliver_format.command(name="list")
@click.pass_context
def format_list(ctx: click.Context) -> None:
    """レンダーフォーマット一覧。"""
    result = deliver_format_list_impl()
    output(result, pretty=ctx.obj.get("pretty"))


@deliver.group(name="codec")
def deliver_codec() -> None:
    """Render codec operations."""


@deliver_codec.command(name="list")
@click.argument("format_name")
@click.pass_context
def codec_list(ctx: click.Context, format_name: str) -> None:
    """指定フォーマットのコーデック一覧。"""
    result = deliver_codec_list_impl(format_name=format_name)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver_preset.command(name="import")
@click.argument("path")
@dry_run_option
@click.pass_context
def preset_import(ctx: click.Context, path: str, dry_run: bool) -> None:
    """レンダープリセットをインポート。"""
    result = deliver_preset_import_impl(path=path, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


@deliver_preset.command(name="export")
@click.argument("name")
@click.argument("path")
@dry_run_option
@click.pass_context
def preset_export(ctx: click.Context, name: str, path: str, dry_run: bool) -> None:
    """レンダープリセットをエクスポート。"""
    result = deliver_preset_export_impl(name=name, path=path, dry_run=dry_run)
    output(result, pretty=ctx.obj.get("pretty"))


# --- Schema Registration ---

register_schema("deliver.preset.list", output_model=PresetListOutput)
register_schema(
    "deliver.preset.load",
    output_model=PresetLoadOutput,
    input_model=PresetLoadInput,
)
register_schema(
    "deliver.add-job",
    output_model=DeliverAddJobOutput,
    input_model=RenderJobInput,
)
register_schema("deliver.list-jobs", output_model=RenderJobInfo)
register_schema(
    "deliver.start",
    output_model=DeliverStartOutput,
    input_model=DeliverStartInput,
)
register_schema("deliver.stop", output_model=DeliverStopOutput)
register_schema("deliver.status", output_model=DeliverStatusOutput)
register_schema(
    "deliver.delete-job",
    output_model=DeliverDeleteJobOutput,
    input_model=DeliverDeleteJobInput,
)
register_schema("deliver.delete-all-jobs", output_model=DeliverDeleteAllJobsOutput)
register_schema(
    "deliver.job-status",
    output_model=DeliverJobStatusOutput,
    input_model=DeliverJobStatusInput,
)
register_schema("deliver.is-rendering", output_model=DeliverIsRenderingOutput)
register_schema("deliver.format.list", output_model=FormatListOutput)
register_schema(
    "deliver.codec.list",
    output_model=CodecListOutput,
    input_model=CodecListInput,
)
register_schema(
    "deliver.preset.import",
    output_model=PresetImportOutput,
    input_model=PresetImportInput,
)
register_schema(
    "deliver.preset.export",
    output_model=PresetExportOutput,
    input_model=PresetExportInput,
)
