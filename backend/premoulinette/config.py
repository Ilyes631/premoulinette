"""Runtime configuration: filesystem locations, network binding and upload limits.

Environment overrides:
* ``PREMOULINETTE_DATA`` — data directory (default ``<repo>/.data``)
* ``PREMOULINETTE_PORT`` — API port (default 8765)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MB = 1024 * 1024

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "demo"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

HOST = "127.0.0.1"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# Upload / viewer limits
SUBJECT_MAX_BYTES = 10 * MB
ZIP_MAX_BYTES = 50 * MB
FOLDER_UPLOAD_MAX_BYTES = 50 * MB
FOLDER_UPLOAD_MAX_FILES = 5000
FILE_VIEW_MAX_BYTES = 1 * MB

# Snapshots kept per path/demo project (each analysis takes a fresh copy).
SNAPSHOTS_KEPT_PER_PROJECT = 3


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if not 0 < value < 65536:
        raise ValueError(f"{name} must be a TCP port (1-65535), got {value}")
    return value


def resolve_data_dir() -> Path:
    """Data directory, re-read from the environment on every call."""
    raw = os.environ.get("PREMOULINETTE_DATA", "").strip()
    return Path(raw).expanduser().resolve() if raw else (REPO_ROOT / ".data")


DATA_DIR = resolve_data_dir()
PORT = _int_env("PREMOULINETTE_PORT", 8765)


@dataclass(frozen=True)
class DataPaths:
    """Layout of the data directory."""

    root: Path

    @property
    def db(self) -> Path:
        return self.root / "premoulinette.db"

    @property
    def subjects(self) -> Path:
        return self.root / "subjects"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots"


def ensure_dirs(data_dir: Path | None = None) -> DataPaths:
    """Create the data directory layout (idempotent) and return it."""
    paths = DataPaths(Path(data_dir).resolve() if data_dir is not None else resolve_data_dir())
    for d in (paths.root, paths.subjects, paths.snapshots):
        d.mkdir(parents=True, exist_ok=True)
    return paths
