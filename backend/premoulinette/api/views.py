"""Response models (views) built from store records."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from premoulinette.api.context import api_key_of
from premoulinette.api.services import ApiServices
from premoulinette.engine.snapshots import count_python_files, find_git_root, prefix_git_paths, relative_posix
from premoulinette.results.models import GitInfo, TreeEntry
from premoulinette.spec.models import PracticalSpec, SpecStats, spec_stats
from premoulinette.store.db import ProjectRecord, Settings, SubjectRecord

log = logging.getLogger(__name__)


class SubjectView(BaseModel):
    id: str
    title: str
    source_name: str
    created_at: datetime
    updated_at: datetime
    parser: str
    media_type: str
    spec: PracticalSpec
    stats: SpecStats
    warnings: list[str] = Field(default_factory=list)
    validation: list[dict[str, Any]] = Field(default_factory=list)


class ProjectView(BaseModel):
    id: str
    name: str
    source_kind: Literal["path", "zip", "upload", "demo"]
    source_path: str | None
    created_at: datetime
    file_count: int
    python_files: int
    tree: list[TreeEntry] = Field(default_factory=list)
    git: GitInfo | None = None
    language: Literal["python"] = "python"
    warnings: list[str] = Field(default_factory=list)


class ProjectListItem(BaseModel):
    id: str
    name: str
    source_kind: Literal["path", "zip", "upload", "demo"]
    source_path: str | None
    created_at: datetime
    file_count: int
    python_files: int


def _as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, BaseModel):
        return item.model_dump(mode="json")
    if isinstance(item, dict):
        return item
    return {"message": str(item)}


def subject_view(rec: SubjectRecord, services: ApiServices) -> SubjectView:
    return SubjectView(
        id=rec.id, title=rec.title, source_name=rec.source_name, created_at=rec.created_at,
        updated_at=rec.updated_at, parser=rec.parser, media_type=rec.media_type, spec=rec.spec,
        stats=spec_stats(rec.spec), warnings=list(rec.parse_warnings),
        validation=[_as_dict(i) for i in services.validate_spec(rec.spec)],
    )


def project_git_info(root: Path, services: ApiServices) -> GitInfo:
    """Git status of the repository found inside ``root`` (paths relative to ``root``)."""
    git_root = find_git_root(root)
    if git_root is None:
        return GitInfo(is_repo=False)
    info = services.read_git_info(git_root, [])
    return prefix_git_paths(info, relative_posix(git_root, root))


def project_view(
    rec: ProjectRecord, services: ApiServices, warnings: Iterable[str] = (), *, tree: list[TreeEntry] | None = None
) -> ProjectView:
    root = Path(rec.snapshot_path)
    git: GitInfo | None = None
    extra_warnings = list(warnings)
    if root.is_dir():
        tree = list(services.list_tree(root)) if tree is None else tree
        git = project_git_info(root, services)
    else:
        tree = []
        extra_warnings.append("The project snapshot is missing. Import the project again.")
    return ProjectView(
        id=rec.id, name=rec.name, source_kind=rec.source_kind, source_path=rec.source_path,
        created_at=rec.created_at, file_count=rec.file_count,
        python_files=count_python_files(tree) if tree else rec.python_files,
        tree=tree, git=git, warnings=extra_warnings,
    )


def project_list_item(rec: ProjectRecord) -> ProjectListItem:
    return ProjectListItem(**rec.model_dump(include=set(ProjectListItem.model_fields)))


def settings_view(settings: Settings) -> dict[str, Any]:
    """Settings as returned by the API: the API key is never included."""
    data = settings.model_dump(mode="json", exclude={"anthropic_api_key"})
    stored = bool((settings.anthropic_api_key or "").strip())
    data["has_api_key"] = api_key_of(settings) is not None
    data["api_key_source"] = "settings" if stored else ("env" if data["has_api_key"] else None)
    return data
