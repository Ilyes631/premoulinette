"""Docker sandbox ("Safe mode"): the harness runs in a locked-down, throw-away container.

``docker run --rm --network none --read-only --tmpfs /tmp:rw,size=64m,exec --memory 256m --memory-swap 256m
--cpus 1 --pids-limit 128 --cap-drop ALL --security-opt no-new-privileges --user 65534:65534
-v <snapshot>:/work:ro -v <harness>:/harness:ro -v <plan dir>:/plan:ro -w /work <image>
python /harness/run_plan.py /plan/plan.json``

The project, harness and plan are copied to a temporary directory first (``.git``/``__pycache__``
skipped, world-readable for the unprivileged container user), which is always removed afterwards.
A global timeout kills the container by name (``docker kill``).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from premoulinette.results.models import SandboxInfo
from premoulinette.runner.models import RunPlan, RunResults
from premoulinette.sandbox import common
from premoulinette.sandbox.base import copy_harness, copy_project, make_world_readable, write_plan
from premoulinette.sandbox.detect import find_docker
from premoulinette.sandbox.procutil import collect, kill_tree, no_window_flags

DEFAULT_IMAGE = "python:3.12-slim"
GLOBAL_SLACK_S = 20.0
COLLECT_TIMEOUT_S = 15.0
DOCKER_KILL_TIMEOUT_S = 15.0
CONTAINER_PREFIX = "premoulinette-"

LIMITS = {
    "memory": "256m",
    "memory_swap": "256m",
    "cpus": "1",
    "pids_limit": "128",
    "tmpfs": "/tmp:rw,size=64m,exec",
    "user": "65534:65534",
}

# registry/namespace/name[:tag][@digest] — and never something that docker would parse as an option
_IMAGE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@+-]{0,254}")
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def validate_image(image: str) -> str:
    if not isinstance(image, str) or not _IMAGE_RE.fullmatch(image) or ".." in image:
        raise ValueError(f"invalid Docker image reference: {image!r}")
    return image


def new_container_name() -> str:
    return CONTAINER_PREFIX + uuid.uuid4().hex[:16]


def build_docker_command(snapshot: Path, harness_dir: Path, plan_dir: Path, image: str, name: str,
                         *, docker: str = "docker") -> list[str]:
    """The full ``docker run`` command line (no shell involved: a list of arguments)."""
    validate_image(image)
    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"invalid container name: {name!r}")
    return [
        docker, "run",
        "--rm",
        "--name", name,
        "--network", "none",
        "--read-only",
        "--tmpfs", LIMITS["tmpfs"],
        "--memory", LIMITS["memory"],
        "--memory-swap", LIMITS["memory_swap"],
        "--cpus", LIMITS["cpus"],
        "--pids-limit", LIMITS["pids_limit"],
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", LIMITS["user"],
        "--env", "PYTHONUTF8=1",
        "--env", "PYTHONIOENCODING=utf-8",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{Path(snapshot)}:/work:ro",
        "-v", f"{Path(harness_dir)}:/harness:ro",
        "-v", f"{Path(plan_dir)}:/plan:ro",
        "-w", "/work",
        image,
        "python", "/harness/run_plan.py", "/plan/plan.json",
    ]


class DockerSandbox:
    """Safe mode sandbox (see module docstring)."""

    mode = "docker"

    def __init__(self, image: str = DEFAULT_IMAGE, *, docker: str | None = None) -> None:
        self.image = image  # validated in run(): an invalid image yields harness errors, not a crash
        self.docker = docker
        self._python_version: str | None = None

    def info(self) -> SandboxInfo:
        return SandboxInfo(
            mode="docker",
            image=self.image,
            python_version=self._python_version,
            network=False,
            limits={
                "memory": LIMITS["memory"],
                "cpus": int(LIMITS["cpus"]),
                "pids": int(LIMITS["pids_limit"]),
                "read_only_root": True,
                "tmpfs": LIMITS["tmpfs"],
                "user": LIMITS["user"],
                "capabilities": "all dropped",
                "network": "none",
            },
            warnings=[],
        )

    def run(self, plan: RunPlan, project_root: Path) -> RunResults:
        start = time.perf_counter()
        if not plan.jobs:
            return RunResults(sandbox_mode="docker", python_version=self._python_version)
        try:
            validate_image(self.image)
        except ValueError as exc:
            return common.failed_results(plan, "docker", str(exc))
        docker = self.docker or find_docker()
        if docker is None:
            return common.failed_results(plan, "docker", "Docker is not installed (docker command not found)")
        tmp = Path(tempfile.mkdtemp(prefix="pm-docker-"))
        try:
            try:
                work = tmp / "work"
                copy_project(Path(project_root), work)
                harness = copy_harness(tmp / "harness")
                plan_dir = tmp / "plan"
                write_plan(plan, plan_dir)
                make_world_readable(tmp)
            except OSError as exc:
                return common.failed_results(plan, "docker", f"could not prepare the sandbox directory: {exc}",
                                             total_ms=_ms(start))
            name = new_container_name()
            cmd = build_docker_command(work, harness, plan_dir, self.image, name, docker=docker)
            results = self._execute(cmd, docker, name, plan, start)
        finally:
            common.remove_tree(tmp)
        if results.python_version:
            self._python_version = results.python_version
        return results

    def _execute(self, cmd: list[str], docker: str, name: str, plan: RunPlan, start: float) -> RunResults:
        budget = common.global_timeout(plan, GLOBAL_SLACK_S)
        try:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=no_window_flags(),
            )
        except OSError as exc:
            return common.failed_results(plan, "docker", f"could not run docker: {exc}", total_ms=_ms(start))
        try:
            out, err = proc.communicate(timeout=budget)
        except subprocess.TimeoutExpired:
            _docker_kill(docker, name)
            kill_tree(proc)
            collect(proc, COLLECT_TIMEOUT_S)
            return common.failed_results(
                plan, "docker", f"global time limit exceeded ({budget:.0f} s): the container was killed",
                total_ms=_ms(start),
            )
        finally:
            if proc.poll() is None:
                _docker_kill(docker, name)
                kill_tree(proc)
        process_error = None
        if proc.returncode != 0:
            process_error = f"docker run exited with code {proc.returncode}"
            tail = common.tail(err)
            if tail:
                process_error += f": {tail}"
        return common.parse_results(out.decode("utf-8", "replace"), plan, "docker",
                                    process_error=process_error, total_ms=_ms(start))


def _docker_kill(docker: str, name: str) -> None:
    for args in ([docker, "kill", name], [docker, "rm", "-f", name]):
        try:
            subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=DOCKER_KILL_TIMEOUT_S, creationflags=no_window_flags())
        except (OSError, subprocess.SubprocessError):
            pass


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)
