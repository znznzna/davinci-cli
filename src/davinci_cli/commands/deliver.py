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
    presets = project.GetRenderPresets() or []
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
        for jid in job_ids:
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
        statuses.append({
            "job_id": job.get("JobId"),
            "status": job.get("JobStatus"),
            "percent": job.get("CompletionPercentage", 0),
            "eta": (job.get("EstimatedTimeRemainingInMs", 0) or 0) // 1000,
        })
    return {"jobs": statuses}


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
