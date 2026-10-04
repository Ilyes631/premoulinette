"""Analyses: start (background job), poll, history, comparison, export, explanations."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from premoulinette.api.context import AppContext, get_ctx, require_ai
from premoulinette.engine.jobs import JobState, ProgressFn
from premoulinette.engine.pipeline import STAGES
from premoulinette.results.models import AnalysisListItem, AnalysisReport, CheckResult

router = APIRouter()

_EXPORTS = {
    "json": ("to_json", "application/json"),
    "md": ("to_markdown", "text/markdown; charset=utf-8"),
    "html": ("to_html", "text/html; charset=utf-8"),
}


class AnalysisRequest(BaseModel):
    subject_id: str
    project_id: str


class ExplainRequest(BaseModel):
    mode: Literal["explain", "fix", "expected"] = "explain"
    provider: Literal["template", "ai"] = "template"
    lang: Literal["fr", "en"] | None = None


def _report_or_404(ctx: AppContext, analysis_id: str) -> AnalysisReport:
    report = ctx.store.get_analysis(analysis_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Unknown analysis {analysis_id!r}")
    return report


def _check_or_404(report: AnalysisReport, check_id: str) -> CheckResult:
    for check in report.checks:
        if check.id == check_id:
            return check
    raise HTTPException(status_code=404, detail=f"Unknown check {check_id!r} in analysis {report.id!r}")


def _json(model: BaseModel) -> Response:
    return Response(model.model_dump_json(), media_type="application/json")


@router.post("/analyses")
def start_analysis(body: AnalysisRequest, ctx: AppContext = Depends(get_ctx)) -> dict[str, str]:
    subject = ctx.subject_or_404(body.subject_id)
    project = ctx.project_or_404(body.project_id)
    settings = ctx.store.get_settings()
    run_analysis, store, snapshots_dir = ctx.services.run_analysis, ctx.store, ctx.paths.snapshots

    def job(progress: ProgressFn) -> str:
        report = run_analysis(subject, project, settings, store, progress, snapshots_dir=snapshots_dir)
        return report.id

    state = ctx.jobs.submit("analysis", STAGES, job)
    return {"job_id": state.id}


@router.get("/jobs/{job_id}", response_model=JobState)
def get_job(job_id: str, ctx: AppContext = Depends(get_ctx)) -> JobState:
    state = ctx.jobs.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown job {job_id!r}")
    return state


@router.get("/analyses", response_model=list[AnalysisListItem])
def list_analyses(
    subject_id: str | None = None, project_id: str | None = None,
    limit: int = Query(50, ge=1, le=1000), ctx: AppContext = Depends(get_ctx),
) -> list[AnalysisListItem]:
    return ctx.store.list_analyses(subject_id=subject_id, project_id=project_id, limit=limit)


@router.get("/analyses/{analysis_id}", response_class=Response)
def get_analysis(analysis_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    return _json(_report_or_404(ctx, analysis_id))


@router.get("/analyses/{analysis_id}/compare/{base_id}", response_class=Response)
def compare_analyses(analysis_id: str, base_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    try:
        return _json(ctx.store.compare(base_id, analysis_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown analysis {exc.args[0]!r}") from exc


@router.get("/analyses/{analysis_id}/export", response_class=Response)
def export_analysis(
    analysis_id: str, format: Literal["json", "md", "html"] = Query("json"), ctx: AppContext = Depends(get_ctx)
) -> Response:
    report = _report_or_404(ctx, analysis_id)
    renderer, media_type = _EXPORTS[format]
    content = getattr(ctx.services, renderer)(report)
    filename = f"premoulinette-report-{report.number}.{format}"
    return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/analyses/{analysis_id}/checks/{check_id:path}/explain", response_model=None)
def explain_check(
    analysis_id: str, check_id: str, body: ExplainRequest | None = None, ctx: AppContext = Depends(get_ctx)
) -> Any:
    """Explain one deterministic result. Check ids contain ':', '/' and '#': clients must URL-encode them."""
    body = body or ExplainRequest()
    report = _report_or_404(ctx, analysis_id)
    check = _check_or_404(report, check_id)
    settings = ctx.store.get_settings()
    lang = body.lang or settings.explanation_language
    services = ctx.services
    if body.mode == "expected":
        return services.expected_behavior(check, report.spec, lang)
    if body.provider == "ai":
        api_key = require_ai(settings, consent="code")
        return services.explain_with_ai(check, body.mode, lang, api_key, model=settings.ai_model)
    if body.mode == "fix":
        return services.how_to_fix(check, lang)
    return services.explain(check, lang)


@router.get("/analyses/{analysis_id}/checks/{check_id:path}/ai-payload", response_model=None)
def ai_payload(
    analysis_id: str, check_id: str, mode: Literal["explain", "fix"] = "explain",
    lang: Literal["fr", "en"] | None = None, ctx: AppContext = Depends(get_ctx),
) -> Any:
    """The exact minimal payload an AI explanation WOULD send (consent preview; nothing is sent)."""
    report = _report_or_404(ctx, analysis_id)
    check = _check_or_404(report, check_id)
    return ctx.services.build_ai_payload(check, mode, lang or ctx.store.get_settings().explanation_language)
