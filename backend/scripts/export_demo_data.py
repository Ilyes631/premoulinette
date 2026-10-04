"""Export the static data of the read-only online demo (``frontend/public/demo-data``).

The online demo (``npm run build:demo``, hosted on Netlify) has no backend: the SPA answers its API
calls from JSON files written by this script. Every file is the exact response of the REAL API,
driven in-process (``fastapi.testclient.TestClient`` on ``create_app``) with a temporary data
directory and the local sandbox, on the bundled MysteryInc demo:

* the demo subject + the demo project ``demo-buggy`` analyzed twice:
  Analysis #1 on ``demo/projects/mysteryinc_buggy``, then the student "fixes" the project
  (its source folder is switched to ``demo/projects/mysteryinc_fixed``, same project id) and
  Analysis #2 runs: History shows #1 -> #2 with a real comparison;
* the "Load fixed demo" project ``demo-fixed`` analyzed once.

Only three things differ from a raw run, all deterministic:

* analysis ids are fixed (``demo-1``, ``demo-2``, ``demo-fixed``) so deep links survive a re-export;
* absolute local paths are rewritten (``demo/projects/mysteryinc_buggy``, ``<tmp>``, ``~``...): the
  data is published, it must not leak the machine layout;
* ``/api/health`` gets ``"demo": true`` and reports Docker as unavailable.

``manifest.json`` maps request keys to files. A key is ``"<METHOD> <decoded path>"`` plus the sorted,
decoded, non-empty query parameters (``?k=v&k2=v2``); for ``POST /api/demo/load`` the JSON body
fields play the role of the query. A route value is a file path, an error ``{"status", "detail"}``,
or a list of ``{"after": <analysis id | null>, ...}`` entries for responses that change once an
analysis exists (the project snapshot after Analysis #2). Explanations (POST .../explain) are
bundled per analysis and language under ``explain``; report exports are static files under
``exports``.

Usage (from the repository root)::

    backend\\.venv\\Scripts\\python.exe backend/scripts/export_demo_data.py

Re-runnable: the output folder is replaced, file names are deterministic.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# The AI layer must never be configured in the exported data (and no key may leak into it).
os.environ.pop("ANTHROPIC_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

import premoulinette.engine.pipeline as pipeline_module  # noqa: E402
from premoulinette.api.app import create_app  # noqa: E402
from premoulinette.api.services import ApiServices  # noqa: E402
from premoulinette.sandbox.detect import DockerStatus  # noqa: E402

DEFAULT_OUT = REPO / "frontend" / "public" / "demo-data"
DEMO_DIR = REPO / "demo"
BASE_URL = "http://127.0.0.1:8765"
HEADERS = {"X-PreMoulinette": "1"}

SUBJECT_ID = "demo-subject"
BUGGY_PROJECT = "demo-buggy"
FIXED_PROJECT = "demo-fixed"
RUN_1, RUN_2, RUN_FIXED = "demo-1", "demo-2", "demo-fixed"
RUNS = {BUGGY_PROJECT: [RUN_1, RUN_2], FIXED_PROJECT: [RUN_FIXED]}
EXPLAIN_MODES = ("explain", "fix", "expected")
LANGS = ("fr", "en")
EXPORT_FORMATS = ("json", "md", "html")
# The list queries the UI sends (RecentAnalyses, HistoryPage, results History tab) + the full list.
LIST_LIMITS = (5, 50, 100, 1000)
PAIR_LIST_LIMIT = 50
MAX_TOTAL_BYTES = 15 * 1024 * 1024
JOB_TIMEOUT_S = 300.0


# ---- request keys ------------------------------------------------------------------------------


def request_key(method: str, path: str, query: dict[str, Any] | None = None) -> str:
    """``"GET /api/x?a=1&b=2"``: decoded path, sorted non-empty query (same rule as the SPA)."""
    key = f"{method.upper()} {path}"
    items = sorted((k, str(v)) for k, v in (query or {}).items() if v is not None and str(v) != "")
    if items:
        key += "?" + "&".join(f"{k}={v}" for k, v in items)
    return key


def enc(segment: str) -> str:
    return quote(segment, safe="")


# ---- path scrubbing ----------------------------------------------------------------------------


_TAIL = r"(?P<tail>(?:[\\/][^\s\"'<>|*?:,;()\[\]{}]*)?)"


class Scrubber:
    """Rewrites absolute local paths into stable, anonymous ones (longest prefix first)."""

    def __init__(self, data_dir: Path) -> None:
        rules: list[tuple[Path, str]] = [
            (DEMO_DIR / "projects" / "mysteryinc_buggy", "demo/projects/mysteryinc_buggy"),
            (DEMO_DIR / "projects" / "mysteryinc_fixed", "demo/projects/mysteryinc_fixed"),
            (DEMO_DIR, "demo"),
            (data_dir, "<data>"),
            (REPO, "<repo>"),
            (Path(tempfile.gettempdir()), "<tmp>"),
            (Path.home(), "~"),
        ]
        self.forbidden = [str(Path.home()), Path.home().as_posix(), str(data_dir), str(REPO)]
        self._rules: list[tuple[re.Pattern[str], str]] = []
        seen: set[str] = set()
        for path, replacement in rules:
            for variant in sorted(_variants(path), key=len, reverse=True):
                if variant.lower() in seen:
                    continue
                seen.add(variant.lower())
                pattern = re.compile(_flexible_separators(variant) + _TAIL, re.IGNORECASE)
                self._rules.append((pattern, replacement))
        self._rules.sort(key=lambda r: len(r[0].pattern), reverse=True)

    def text(self, value: str) -> str:
        for pattern, replacement in self._rules:
            if pattern.search(value):
                value = pattern.sub(lambda m, r=replacement: r + m.group("tail").replace("\\", "/"), value)
        return value

    def data(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.data(v) for v in value]
        if isinstance(value, dict):
            return {k: self.data(v) for k, v in value.items()}
        return value


def _variants(path: Path) -> set[str]:
    raw = {str(path), str(path.resolve())}
    return {v for r in raw for v in (r, r.replace("\\", "/"))}


def _flexible_separators(path: str) -> str:
    parts = re.split(r"[\\/]+", path)
    return r"[\\/]+".join(re.escape(p) for p in parts)


# ---- output ------------------------------------------------------------------------------------


class Output:
    def __init__(self, root: Path, scrubber: Scrubber) -> None:
        self.root = root
        self.scrubber = scrubber
        self.routes: dict[str, Any] = {}
        self.written: dict[str, bytes] = {}

    def write_json(self, rel: str, data: Any) -> str:
        payload = json.dumps(self.scrubber.data(data), ensure_ascii=False, separators=(",", ":"))
        return self._write(rel, payload.encode("utf-8"))

    def write_text(self, rel: str, text: str) -> str:
        return self._write(rel, self.scrubber.text(text).encode("utf-8"))

    def _write(self, rel: str, data: bytes) -> str:
        previous = self.written.get(rel)
        if previous is not None and previous != data:
            raise RuntimeError(f"Two different responses for the same file {rel}")
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.written[rel] = data
        return rel

    def route(self, key: str, value: Any) -> None:
        if key in self.routes and self.routes[key] != value:
            raise RuntimeError(f"Route {key} exported twice with different values")
        self.routes[key] = value


# ---- API driver --------------------------------------------------------------------------------


class Api:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        res = self.client.get(path, params=query)
        if res.status_code != 200:
            raise RuntimeError(f"GET {path} {query or ''} -> {res.status_code}: {res.text[:300]}")
        return res.json()

    def get_raw(self, path: str, query: dict[str, Any] | None = None) -> tuple[int, Any]:
        res = self.client.get(path, params=query)
        try:
            body = res.json()
        except ValueError:
            body = res.text
        return res.status_code, body

    def post(self, path: str, body: Any = None) -> Any:
        res = self.client.post(path, json=body)
        if res.status_code != 200:
            raise RuntimeError(f"POST {path} -> {res.status_code}: {res.text[:300]}")
        return res.json()

    def put(self, path: str, body: Any) -> Any:
        res = self.client.put(path, json=body)
        if res.status_code != 200:
            raise RuntimeError(f"PUT {path} -> {res.status_code}: {res.text[:300]}")
        return res.json()

    def wait_job(self, job_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + JOB_TIMEOUT_S
        while True:
            state = self.get(f"/api/jobs/{enc(job_id)}")
            if state["status"] in ("done", "error"):
                return state
            if time.monotonic() > deadline:
                raise RuntimeError(f"Job {job_id} did not finish in {JOB_TIMEOUT_S:.0f} s: {state}")
            time.sleep(0.1)


class FixedAnalysisIds:
    """Stands in for ``uuid`` in the pipeline module: the next analysis gets the queued id."""

    def __init__(self) -> None:
        self.queue: list[str] = []

    def uuid4(self) -> SimpleNamespace:
        if not self.queue:
            raise RuntimeError("No analysis id queued")
        return SimpleNamespace(hex=self.queue.pop(0))


def _docker_unavailable(image: str = "python:3.12-slim", *_: Any, **__: Any) -> DockerStatus:
    return DockerStatus(available=False, version=None, image=image, image_ready=False, error=None)


# ---- export ------------------------------------------------------------------------------------


class Exporter:
    def __init__(self, api: Api, out: Output, ids: FixedAnalysisIds, store: Any) -> None:
        self.api = api
        self.out = out
        self.ids = ids
        self.store = store
        self.reports: dict[str, dict[str, Any]] = {}
        # project id -> list of (after, {path: response entry}) snapshots of the file viewer
        self.file_states: dict[str, list[tuple[str | None, str, dict[str, Any]]]] = {}

    def get_route(self, path: str, rel: str, query: dict[str, Any] | None = None) -> Any:
        data = self.api.get(path, query)
        self.out.route(request_key("GET", path, query), self.out.write_json(rel, data))
        return data

    def run(self) -> None:
        api, out = self.api, self.out
        api.put("/api/settings", {"sandbox_mode": "local", "local_mode_acknowledged": True})

        health = api.get("/api/health")
        health["docker"] = {**health["docker"], "available": False, "version": None, "image_ready": False, "error": None}
        health["ai"] = {"configured": False, "enabled": False}
        health["demo"] = True
        if health.get("sandbox_mode_effective") != "local":
            raise RuntimeError(f"Expected the local sandbox, got {health.get('sandbox_mode_effective')!r}")
        out.route(request_key("GET", "/api/health"), out.write_json("health.json", health))
        self.get_route("/api/settings", "settings.json")

        for variant in ("buggy", "fixed"):
            loaded = api.post("/api/demo/load", {"variant": variant})
            out.route(request_key("POST", "/api/demo/load", {"variant": variant}),
                      out.write_json(f"demo-load/{variant}.json", loaded))

        subject_path = f"/api/subjects/{SUBJECT_ID}"
        self.get_route(subject_path, f"subjects/{SUBJECT_ID}.json")
        self.get_route(f"{subject_path}/tests", f"subjects/{SUBJECT_ID}.tests.json")
        self.get_route(f"{subject_path}/document", f"subjects/{SUBJECT_ID}.document.json")
        self.get_route("/api/subjects", "subjects/list.json")
        self.get_route("/api/spec/schema", "spec-schema.json")

        # Analysis #1: the buggy project as loaded by "Load demo project".
        self.analyze(BUGGY_PROJECT, RUN_1)
        buggy_view = self.api.get(f"/api/projects/{BUGGY_PROJECT}")
        self.capture_files(BUGGY_PROJECT, None, "buggy", buggy_view)

        # Re-analyze: the SAME unchanged code again. Same code => same result (68%), as in the real app;
        # switching to the fixed code here made visitors believe the tool gives random scores.
        self.analyze(BUGGY_PROJECT, RUN_2)
        again_view = self.api.get(f"/api/projects/{BUGGY_PROJECT}")
        self.capture_files(BUGGY_PROJECT, RUN_2, "buggy", again_view)
        out.route(request_key("GET", f"/api/projects/{BUGGY_PROJECT}"), [
            {"after": None, "file": out.write_json(f"projects/{BUGGY_PROJECT}.json", buggy_view)},
            {"after": RUN_2, "file": out.write_json(f"projects/{BUGGY_PROJECT}.after-{RUN_2}.json", again_view)},
        ])

        # "Load fixed demo" + Analyze.
        self.analyze(FIXED_PROJECT, RUN_FIXED)
        view = self.get_route(f"/api/projects/{FIXED_PROJECT}", f"projects/{FIXED_PROJECT}.json")
        self.capture_files(FIXED_PROJECT, None, "fixed", view)
        self.write_file_routes()

        self.get_route("/api/projects", "projects/list.json")
        self.get_route("/api/analyses", "analyses/list.json")
        for limit in LIST_LIMITS:
            self.get_route("/api/analyses", f"analyses/list.limit-{limit}.json", {"limit": limit})
        for project_id in RUNS:
            query = {"subject_id": SUBJECT_ID, "project_id": project_id, "limit": PAIR_LIST_LIMIT}
            self.get_route("/api/analyses", f"analyses/list.{project_id}.json", query)

        for runs in RUNS.values():
            for head in runs:
                for base in runs:
                    if head != base:
                        self.get_route(f"/api/analyses/{head}/compare/{base}", f"analyses/{head}.compare.{base}.json")

        self.export_reports()
        self.export_explanations()

    # ---- analyses ----
    def analyze(self, project_id: str, analysis_id: str) -> None:
        self.ids.queue.append(analysis_id)
        job = self.api.post("/api/analyses", {"subject_id": SUBJECT_ID, "project_id": project_id})
        state = self.api.wait_job(job["job_id"])
        if state["status"] != "done" or state["result_id"] != analysis_id:
            raise RuntimeError(f"Analysis {analysis_id} failed: {state}")
        report = self.get_route(f"/api/analyses/{analysis_id}", f"analyses/{analysis_id}.json")
        self.reports[analysis_id] = report
        score = report["score"]
        print(f"  #{report['number']} {analysis_id:<11} {project_id:<11} readiness {score['readiness']:.1f}% "
              f"{score['verdict_title']} ({len(report['checks'])} checks, {report['duration_ms'] / 1000:.1f} s)")

    def export_reports(self) -> None:
        exports: dict[str, dict[str, str]] = {}
        for analysis_id in self.reports:
            files: dict[str, str] = {}
            for fmt in EXPORT_FORMATS:
                res = self.api.client.get(f"/api/analyses/{analysis_id}/export", params={"format": fmt})
                if res.status_code != 200:
                    raise RuntimeError(f"export {analysis_id} {fmt} -> {res.status_code}")
                files[fmt] = self.out.write_text(f"exports/premoulinette-report-{analysis_id}.{fmt}", res.text)
            exports[analysis_id] = files
        self.exports = exports

    def export_explanations(self) -> None:
        bundles: dict[str, dict[str, str]] = {}
        for analysis_id, report in self.reports.items():
            bundles[analysis_id] = {}
            for lang in LANGS:
                bundle: dict[str, dict[str, Any]] = {}
                for check in report["checks"]:
                    path = f"/api/analyses/{enc(analysis_id)}/checks/{enc(check['id'])}/explain"
                    bundle[check["id"]] = {
                        mode: self.api.post(path, {"mode": mode, "provider": "template", "lang": lang})
                        for mode in EXPLAIN_MODES
                    }
                bundles[analysis_id][lang] = self.out.write_json(f"explain/{analysis_id}.{lang}.json", bundle)
        self.explain = bundles

    # ---- project file viewer ----
    def capture_files(self, project_id: str, after: str | None, label: str, view: dict[str, Any]) -> None:
        entries: dict[str, Any] = {}
        for entry in view["tree"]:
            if entry["kind"] != "file":
                continue
            path = entry["path"]
            status, body = self.api.get_raw(f"/api/projects/{project_id}/file", {"path": path})
            if status == 200:
                digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
                name = re.sub(r"[^A-Za-z0-9._-]+", "_", PurePosixPath(path).name) or "file"
                entries[path] = {"file": self.out.write_json(f"files/{label}/{digest}-{name}.json", body)}
            else:
                detail = body.get("detail") if isinstance(body, dict) else body
                entries[path] = {"status": status, "detail": self.out.scrubber.data(detail)}
        self.file_states.setdefault(project_id, []).append((after, label, entries))

    def write_file_routes(self) -> None:
        for project_id, states in self.file_states.items():
            paths = sorted({p for _, _, entries in states for p in entries})
            for path in paths:
                variants = [{"after": after, **entries[path]} for after, _, entries in states if path in entries]
                # A file that only exists in a later snapshot is shown whatever the state (no 404 flip-flop).
                variants[0]["after"] = None
                key = request_key("GET", f"/api/projects/{project_id}/file", {"path": path})
                if len(variants) == 1:
                    single = {k: v for k, v in variants[0].items() if k != "after"}
                    self.out.route(key, single["file"] if set(single) == {"file"} else single)
                else:
                    self.out.route(key, variants)

    # ---- manifest ----
    def manifest(self) -> dict[str, Any]:
        analyses = {
            analysis_id: {
                "number": r["number"], "subject_id": r["subject"]["id"], "project_id": r["project"]["id"],
                "created_at": r["created_at"], "readiness": r["score"]["readiness"], "verdict": r["score"]["verdict"],
            }
            for analysis_id, r in self.reports.items()
        }
        return {
            "version": 1,
            "generated_by": "backend/scripts/export_demo_data.py",
            "app_version": self.api.get("/api/health")["version"],
            "subject_id": SUBJECT_ID,
            "runs": RUNS,
            "analyses": analyses,
            "routes": dict(sorted(self.out.routes.items())),
            "explain": self.explain,
            "exports": self.exports,
        }


# ---- checks ------------------------------------------------------------------------------------


def verify(out_dir: Path, scrubber: Scrubber) -> int:
    total = 0
    leaks: list[str] = []
    needles = {n for f in scrubber.forbidden for n in (f, f.replace("\\", "/"), json.dumps(f)[1:-1])}
    for file in sorted(out_dir.rglob("*")):
        if not file.is_file():
            continue
        total += file.stat().st_size
        text = file.read_text(encoding="utf-8").lower()
        for needle in needles:
            if needle and needle.lower() in text:
                leaks.append(f"{file.relative_to(out_dir)}: contains {needle!r}")
    if leaks:
        raise RuntimeError("Local paths leaked into the demo data:\n  " + "\n  ".join(leaks[:20]))
    if total > MAX_TOTAL_BYTES:
        raise RuntimeError(f"The demo data is too large: {total / 1e6:.1f} MB (limit {MAX_TOTAL_BYTES / 1e6:.0f} MB)")
    return total


def check_not_gitignored(out_dir: Path) -> None:
    """Netlify does not run Python: the data must be committed, so git must not ignore any of it."""
    files = [str(p.relative_to(REPO)).replace("\\", "/") for p in out_dir.rglob("*") if p.is_file()]
    try:
        res = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin"], input="\n".join(files), cwd=REPO,
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  (git check-ignore skipped: {exc})")
        return
    ignored = [line for line in res.stdout.splitlines() if line.strip()]
    if ignored:
        raise RuntimeError("These demo files are ignored by git:\n  " + "\n  ".join(ignored[:20]))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output folder (default: {DEFAULT_OUT})")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    out_dir: Path = args.out.resolve()
    data_dir = Path(tempfile.mkdtemp(prefix="premoulinette-demo-export-"))
    staging = out_dir.with_name(out_dir.name + ".tmp")
    shutil.rmtree(staging, ignore_errors=True)
    scrubber = Scrubber(data_dir)
    ids = FixedAnalysisIds()
    original_uuid = pipeline_module.uuid
    pipeline_module.uuid = ids  # type: ignore[assignment]
    started = time.perf_counter()
    try:
        services = dataclasses.replace(ApiServices(), detect_docker=_docker_unavailable)
        app = create_app(data_dir / "data", services=services, frontend_dist=data_dir / "no-dist")
        out = Output(staging, scrubber)
        print(f"Exporting the demo data (temporary data dir {data_dir})")
        with TestClient(app, base_url=BASE_URL, headers=HEADERS) as client:
            exporter = Exporter(Api(client), out, ids, app.state.ctx.store)
            exporter.run()
            manifest = exporter.manifest()
        out._write("manifest.json", json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        app.state.ctx.store.close()
        total = verify(staging, scrubber)
        if out_dir.exists():
            shutil.rmtree(out_dir)
        staging.rename(out_dir)
        check_not_gitignored(out_dir)
    finally:
        pipeline_module.uuid = original_uuid  # type: ignore[assignment]
        shutil.rmtree(data_dir, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
    count = sum(1 for p in out_dir.rglob("*") if p.is_file())
    print(f"Wrote {count} files, {total / 1e6:.2f} MB, to {out_dir.relative_to(REPO)} "
          f"in {time.perf_counter() - started:.1f} s ({len(manifest['routes'])} routes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
