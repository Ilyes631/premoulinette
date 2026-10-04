"""Demo loader: the MysteryInc subject + a buggy or fixed student project, ready to analyze.

Nothing is copied: the subject record points to ``demo/subject_demo.html`` and the project record
(kind "demo") to ``demo/projects/mysteryinc_<variant>``; each analysis snapshots it like a path project.
Ids are fixed so that reloading the demo keeps its analysis history.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from premoulinette.api.context import AppContext, get_ctx
from premoulinette.api.subject_records import parse_or_400, record_from_parse
from premoulinette.api.views import project_view, subject_view
from premoulinette.engine.snapshots import count_python_files
from premoulinette.store.db import ProjectRecord

router = APIRouter()

DEMO_SUBJECT_ID = "demo-subject"
DEMO_SUBJECT_FILE = "subject_demo.html"


class DemoRequest(BaseModel):
    variant: Literal["buggy", "fixed"] = "buggy"
    reset: bool = False   # re-parse the demo subject (discards edits made to its spec)


@router.post("/demo/load")
def load_demo(body: DemoRequest | None = None, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    body = body or DemoRequest()
    subject_file = ctx.demo_dir / DEMO_SUBJECT_FILE
    project_dir = ctx.demo_dir / "projects" / f"mysteryinc_{body.variant}"
    if not subject_file.is_file() or not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="The demo files are missing from this installation.")

    subject = ctx.store.get_subject(DEMO_SUBJECT_ID)
    if subject is None or body.reset:
        doc, parsed = parse_or_400(ctx.services, subject_file.read_bytes(), subject_file.name)
        subject = record_from_parse(
            DEMO_SUBJECT_ID, subject_file.name, doc, parsed, subject_file.resolve(),
            created_at=subject.created_at if subject else None,
        )
        ctx.store.save_subject(subject)

    project_id = f"demo-{body.variant}"
    existing = ctx.store.get_project(project_id)
    source = project_dir.resolve()
    tree = list(ctx.services.list_tree(source))
    project = ProjectRecord(
        id=project_id, name=project_dir.name, source_kind="demo", source_path=str(source),
        created_at=existing.created_at if existing else datetime.now(timezone.utc),
        snapshot_path=str(source), file_count=sum(1 for e in tree if e.kind == "file"),
        python_files=count_python_files(tree),
    )
    ctx.store.save_project(project)
    return {
        "subject": subject_view(subject, ctx.services).model_dump(mode="json"),
        "project": project_view(project, ctx.services, tree=tree).model_dump(mode="json"),
    }
