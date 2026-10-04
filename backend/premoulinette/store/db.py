"""Local persistence (sqlite3, stdlib): subjects, projects, analyses and settings.

Each table stores the full pydantic model as a JSON blob plus a few indexed columns used for
listing/filtering. One connection (``check_same_thread=False``) is shared and guarded by a lock;
WAL journaling keeps readers from blocking the writer.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from premoulinette.results.models import AnalysisComparison, AnalysisListItem, AnalysisReport
from premoulinette.spec.models import PracticalSpec
from premoulinette.store.compare import compare_reports
from premoulinette.store.models import ProjectRecord, Settings, SubjectRecord, as_utc, utc_now

__all__ = ["Store", "SubjectRecord", "ProjectRecord", "Settings"]

SCHEMA_VERSION = 1
MAX_LIST_LIMIT = 1000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subjects_created ON subjects(created_at);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    subject_title TEXT NOT NULL,
    project_name TEXT NOT NULL,
    readiness REAL NOT NULL,
    mandatory_readiness REAL NOT NULL,
    bonus_completion REAL,
    verdict TEXT NOT NULL,
    mandatory_failures INTEGER NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_pair ON analyses(subject_id, project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
"""

_ANALYSIS_LIST_COLUMNS = (
    "id, number, created_at, subject_id, project_id, subject_title, project_name, "
    "readiness, mandatory_readiness, bonus_completion, verdict, mandatory_failures"
)


def _ts(value: datetime) -> str:
    """Fixed-width UTC ISO timestamp: lexicographic order == chronological order."""
    return as_utc(value).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        if str(db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            self._conn.commit()

    # ---- lifecycle ---------------------------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Serialized transaction: commit on success, rollback on error."""
        with self._lock, self._conn:
            yield self._conn

    def _one(self, sql: str, params: tuple[object, ...]) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def _all(self, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # ---- subjects ----------------------------------------------------------------------------
    def save_subject(self, rec: SubjectRecord) -> SubjectRecord:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO subjects (id, title, source_name, created_at, updated_at, data)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET title=excluded.title, source_name=excluded.source_name,
                       created_at=excluded.created_at, updated_at=excluded.updated_at, data=excluded.data""",
                (rec.id, rec.title, rec.source_name, _ts(rec.created_at), _ts(rec.updated_at), rec.model_dump_json()),
            )
        return rec

    def get_subject(self, subject_id: str) -> SubjectRecord | None:
        row = self._one("SELECT data FROM subjects WHERE id = ?", (subject_id,))
        return SubjectRecord.model_validate_json(row["data"]) if row else None

    def list_subjects(self) -> list[SubjectRecord]:
        rows = self._all("SELECT data FROM subjects ORDER BY created_at DESC, rowid DESC")
        return [SubjectRecord.model_validate_json(r["data"]) for r in rows]

    def update_spec(self, subject_id: str, spec: PracticalSpec) -> SubjectRecord | None:
        """Replace the spec of a subject (user review/edit); keeps the title in sync. None if unknown."""
        with self._lock:  # read-modify-write must not interleave with another writer
            rec = self.get_subject(subject_id)
            if rec is None:
                return None
            updated = rec.model_copy(
                update={"spec": spec, "title": spec.metadata.title or rec.title, "updated_at": utc_now()}
            )
            self.save_subject(updated)
        return updated

    # ---- projects ----------------------------------------------------------------------------
    def save_project(self, rec: ProjectRecord) -> ProjectRecord:
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO projects (id, name, source_kind, created_at, data) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, source_kind=excluded.source_kind,
                       created_at=excluded.created_at, data=excluded.data""",
                (rec.id, rec.name, rec.source_kind, _ts(rec.created_at), rec.model_dump_json()),
            )
        return rec

    def get_project(self, project_id: str) -> ProjectRecord | None:
        row = self._one("SELECT data FROM projects WHERE id = ?", (project_id,))
        return ProjectRecord.model_validate_json(row["data"]) if row else None

    def list_projects(self) -> list[ProjectRecord]:
        rows = self._all("SELECT data FROM projects ORDER BY created_at DESC, rowid DESC")
        return [ProjectRecord.model_validate_json(r["data"]) for r in rows]

    # ---- analyses ----------------------------------------------------------------------------
    def save_analysis(self, report: AnalysisReport) -> AnalysisReport:
        s = report.score
        with self._tx() as conn:
            conn.execute(
                """INSERT INTO analyses (id, subject_id, project_id, number, created_at, subject_title, project_name,
                       readiness, mandatory_readiness, bonus_completion, verdict, mandatory_failures, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET subject_id=excluded.subject_id, project_id=excluded.project_id,
                       number=excluded.number, created_at=excluded.created_at, subject_title=excluded.subject_title,
                       project_name=excluded.project_name, readiness=excluded.readiness,
                       mandatory_readiness=excluded.mandatory_readiness, bonus_completion=excluded.bonus_completion,
                       verdict=excluded.verdict, mandatory_failures=excluded.mandatory_failures, data=excluded.data""",
                (
                    report.id, report.subject.id, report.project.id, report.number, _ts(report.created_at),
                    report.subject.title, report.project.name, s.readiness, s.mandatory_readiness,
                    s.bonus_completion, s.verdict, s.mandatory_failures, report.model_dump_json(),
                ),
            )
        return report

    def get_analysis(self, analysis_id: str) -> AnalysisReport | None:
        row = self._one("SELECT data FROM analyses WHERE id = ?", (analysis_id,))
        return AnalysisReport.model_validate_json(row["data"]) if row else None

    def delete_analysis(self, analysis_id: str) -> bool:
        with self._tx() as conn:
            cur = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        return cur.rowcount > 0

    def list_analyses(
        self, subject_id: str | None = None, project_id: str | None = None, limit: int = 50
    ) -> list[AnalysisListItem]:
        """Newest first."""
        where: list[str] = []
        params: list[object] = []
        if subject_id is not None:
            where.append("subject_id = ?")
            params.append(subject_id)
        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)
        sql = f"SELECT {_ANALYSIS_LIST_COLUMNS} FROM analyses"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC, number DESC, rowid DESC LIMIT ?"
        params.append(max(1, min(int(limit), MAX_LIST_LIMIT)))
        return [_list_item(r) for r in self._all(sql, tuple(params))]

    def next_number(self, subject_id: str, project_id: str) -> int:
        """1 + number of analyses of this (subject, project) pair (never reuses a number after a delete)."""
        row = self._one(
            "SELECT COUNT(*) AS n, COALESCE(MAX(number), 0) AS m FROM analyses WHERE subject_id = ? AND project_id = ?",
            (subject_id, project_id),
        )
        assert row is not None
        return max(int(row["n"]), int(row["m"])) + 1

    def compare(self, base_id: str, head_id: str) -> AnalysisComparison:
        """Raises KeyError if either analysis does not exist."""
        base = self.get_analysis(base_id)
        head = self.get_analysis(head_id)
        if base is None:
            raise KeyError(base_id)
        if head is None:
            raise KeyError(head_id)
        return compare_reports(base, head)

    # ---- settings ----------------------------------------------------------------------------
    def get_settings(self) -> Settings:
        row = self._one("SELECT data FROM settings WHERE id = 1", ())
        if row is None:
            return Settings()
        try:
            return Settings.model_validate_json(row["data"])
        except ValidationError:
            return Settings()  # unreadable blob (e.g. older schema): fall back to defaults

    def save_settings(self, settings: Settings) -> Settings:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO settings (id, data) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (settings.model_dump_json(),),
            )
        return settings


def _list_item(row: sqlite3.Row) -> AnalysisListItem:
    return AnalysisListItem(
        id=row["id"],
        number=row["number"],
        created_at=datetime.fromisoformat(row["created_at"]),
        subject_id=row["subject_id"],
        project_id=row["project_id"],
        subject_title=row["subject_title"],
        project_name=row["project_name"],
        readiness=row["readiness"],
        mandatory_readiness=row["mandatory_readiness"],
        bonus_completion=row["bonus_completion"],
        verdict=row["verdict"],
        mandatory_failures=row["mandatory_failures"],
    )
