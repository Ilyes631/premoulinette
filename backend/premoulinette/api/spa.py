"""Serve the built frontend (``frontend/dist``) with an ``index.html`` fallback for client routes.

Registered after the API routers, and never answers under ``/api`` (unknown API paths stay 404 JSON).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_spa(app: FastAPI, dist: Path) -> bool:
    index = dist / "index.html"
    if not index.is_file():
        return False
    root = dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        if full_path:
            candidate = (root / full_path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                return FileResponse(candidate)
            if "." in full_path.rsplit("/", 1)[-1]:
                raise HTTPException(status_code=404, detail="Not found")  # missing asset, not a client route
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True
