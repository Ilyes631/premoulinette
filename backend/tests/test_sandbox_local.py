"""LocalSandbox end-to-end tests: REAL execution of student code through run_plan.py + child.py.

One plan with every scenario runs once per module (parallel jobs) to keep the suite fast.
"""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest

from premoulinette.runner.models import FunctionJob, ImportJob, JobResult, RunPlan, ScriptJob
from premoulinette.sandbox.base import get_sandbox
from premoulinette.sandbox.local import LocalSandbox, minimal_env

FUNCS = textwrap.dedent(
    '''\
    from helper import double


    def str_true():
        return "True"


    def bool_true():
        return True


    def to_kelvin(celsius):
        return celsius + 273.15


    def shout(word):
        print("Hello", word)


    def boom(x):
        values = [1, 2]
        return values[x]  # BOOM-LINE


    def spin():
        while True:  # SPIN-LINE
            pass


    def flood():
        while True:
            print("x" * 200)


    def use_double(n):
        return double(n)


    def net():
        import socket
        socket.create_connection(("127.0.0.1", 9), timeout=2)
        return "connected"


    def spawn():
        import subprocess
        subprocess.run(["whoami"])
        return "spawned"


    def system():
        import os
        return os.system("echo hi")


    def write_outside(path):
        with open(path, "w") as fh:
            fh.write("pwned")
        return "written"


    def write_inside():
        with open("inside.txt", "w") as fh:
            fh.write("ok")
        with open("inside.txt") as fh:
            return fh.read()


    def env_keys():
        import os
        return sorted(os.environ)


    def secret():
        import os
        return [os.environ.get("PM_SECRET_TEST"), os.environ.get("ANTHROPIC_API_KEY")]


    def square(n):
        return n * n


    def big_alloc():
        data = bytearray(700 * 1024 * 1024)
        return len(data)


    def native():
        import ctypes
        import os
        if os.name == "nt":
            return ctypes.windll.kernel32.GetCurrentProcessId()
        return ctypes.CDLL(None).getpid()


    def c_loop():
        return sum(range(10 ** 12))  # C loop holding the GIL: only the parent's hard kill can stop it
    '''
)

INTERACTIVE = textwrap.dedent(
    '''\
    name = input("Pilot name: ")  # PROMPT-1
    fuel = int(input("Starting fuel: "))  # PROMPT-2
    print(f"Hello {name}, fuel={fuel}")  # PRINT-LINE
    '''
)

FILES = {
    "funcs.py": FUNCS,
    "helper.py": "def double(x):\n    return 2 * x\n",
    "interactive.py": INTERACTIVE,
    "utf8_io.py": 'x = input("Nom : ")\nprint(f"Bonjour {x} ✓")\n',
    "exit3.py": "import sys\nprint('bye')\nsys.exit(3)\n",
    "waits_input.py": 'name = input("Name? ")\nprint(name)\n',
    "pkg/tool.py": "from helper2 import triple\nprint(triple(14))\n",
    "pkg/helper2.py": "def triple(x):\n    return 3 * x\n",
}


def line_of(source: str, marker: str) -> int:
    for number, line in enumerate(source.splitlines(), start=1):
        if marker in line:
            return number
    raise AssertionError(marker)


def fn(job_id: str, function: str, *args: str, timeout_s: float = 5.0) -> FunctionJob:
    return FunctionJob(id=job_id, module_path="funcs.py", function=function, args=list(args), timeout_s=timeout_s)


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("project")
    for rel, content in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def outside(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("outside") / "pwned.txt"


@pytest.fixture(scope="module")
def run(project: Path, outside: Path):
    jobs = [
        fn("str_true", "str_true"),
        fn("bool_true", "bool_true"),
        fn("kelvin", "to_kelvin", "0"),
        fn("shout", "shout", "'world'"),
        fn("boom", "boom", "5"),
        fn("spin", "spin", timeout_s=1),
        fn("flood", "flood"),
        fn("sibling", "use_double", "21"),
        fn("net", "net"),
        fn("spawn", "spawn"),
        fn("system", "system"),
        fn("write_outside", "write_outside", repr(str(outside))),
        fn("write_inside", "write_inside"),
        fn("env_keys", "env_keys"),
        fn("secret", "secret"),
        fn("big_alloc", "big_alloc"),
        fn("native", "native"),
        fn("c_loop", "c_loop", timeout_s=1),
        ScriptJob(id="interactive", script_path="interactive.py", stdin="Camille\n400\n"),
        ScriptJob(id="interactive_crlf", script_path="interactive.py", stdin="Camille\r\n400\r\n"),
        ScriptJob(id="utf8", script_path="utf8_io.py", stdin="é🙂\n"),
        ScriptJob(id="eof", script_path="interactive.py", stdin="Camille\n"),
        ScriptJob(id="exit3", script_path="exit3.py"),
        ScriptJob(id="pkg_script", script_path="pkg/tool.py"),
        ScriptJob(id="escape", script_path="../outside.py"),
        ImportJob(id="import_waits", module_path="waits_input.py"),
        ImportJob(id="import_ok", module_path="helper.py"),
    ]
    jobs += [fn(f"par{i}", "square", str(i)) for i in range(12)]
    plan = RunPlan(jobs=jobs, max_parallel=8)
    sandbox = LocalSandbox()
    previous = os.environ.get("PM_SECRET_TEST")
    os.environ["PM_SECRET_TEST"] = "x-very-secret"
    try:
        results = sandbox.run(plan, project)
    finally:
        if previous is None:
            os.environ.pop("PM_SECRET_TEST", None)
        else:
            os.environ["PM_SECRET_TEST"] = previous
    return sandbox, plan, results


@pytest.fixture(scope="module")
def by_id(run) -> dict[str, JobResult]:
    return {r.id: r for r in run[2].results}


# ---------------------------------------------------------------------------------------------


def test_one_result_per_job_in_plan_order(run):
    _sandbox, plan, results = run
    assert [r.id for r in results.results] == [j.id for j in plan.jobs]
    assert results.sandbox_mode == "local"
    assert results.python_version == "%d.%d.%d" % sys.version_info[:3]
    assert results.errors == []


def test_str_true_is_not_bool_true(by_id):
    s, b = by_id["str_true"], by_id["bool_true"]
    assert (s.status, s.return_repr, s.return_type, s.return_literal) == ("ok", "'True'", "str", True)
    assert (b.status, b.return_repr, b.return_type, b.return_literal) == ("ok", "True", "bool", True)


def test_float_return(by_id):
    r = by_id["kelvin"]
    assert (r.status, r.return_repr, r.return_type) == ("ok", "273.15", "float")
    assert r.stdout == "" and r.import_stdout == ""


def test_print_and_return_none(by_id):
    r = by_id["shout"]
    assert r.status == "ok"
    assert r.return_repr == "None" and r.return_type == "NoneType"
    assert r.stdout == "Hello world\n"
    assert [(e.kind, e.text, e.file, e.line) for e in r.events] == [
        ("output", "Hello world\n", "funcs.py", line_of(FUNCS, 'print("Hello", word)'))
    ]


def test_exception_reports_student_file_and_line(by_id):
    r = by_id["boom"]
    assert r.status == "exception"
    assert r.exception is not None
    assert r.exception.type == "IndexError"
    assert r.exception.file == "funcs.py"
    assert r.exception.line == line_of(FUNCS, "BOOM-LINE")
    assert "child.py" not in r.exception.traceback and "run_plan" not in r.exception.traceback
    assert 'File "funcs.py"' in r.exception.traceback


def test_infinite_loop_times_out(by_id):
    r = by_id["spin"]
    assert r.status == "timeout"
    assert r.exception is not None and r.exception.type == "TimeoutError"
    assert r.exception.file == "funcs.py"
    assert line_of(FUNCS, "SPIN-LINE") <= (r.exception.line or 0) <= line_of(FUNCS, "SPIN-LINE") + 1
    assert r.duration_ms < 4000


def test_print_flood_hits_output_limit(by_id):
    r = by_id["flood"]
    assert r.status == "output_limit"
    assert r.truncated is True
    assert 0 < len(r.stdout.encode("utf-8")) <= 65536


def test_sibling_import_in_function_job(by_id):
    r = by_id["sibling"]
    assert (r.status, r.return_repr) == ("ok", "42")


def test_network_is_blocked(by_id):
    r = by_id["net"]
    assert r.status == "exception"
    assert r.exception is not None and r.exception.type == "PermissionError"
    assert "socket.connect" in r.blocked_syscalls


def test_process_creation_is_blocked(by_id):
    for job_id, event in (("spawn", "subprocess.Popen"), ("system", "os.system")):
        r = by_id[job_id]
        assert r.status == "exception", job_id
        assert r.exception is not None and r.exception.type == "PermissionError"
        assert event in r.blocked_syscalls


def test_native_calls_are_blocked(by_id):
    r = by_id["native"]
    assert r.status == "exception"
    assert r.exception is not None and r.exception.type == "PermissionError"
    assert {"ctypes.call_function", "ctypes.dlopen"} & set(r.blocked_syscalls)


def test_c_level_loop_is_hard_killed(by_id):
    r = by_id["c_loop"]
    assert r.status == "timeout"
    assert r.exit_code is None
    assert r.duration_ms < 8000


def test_write_outside_allowed_roots_is_blocked(by_id, outside: Path):
    r = by_id["write_outside"]
    assert r.status == "exception"
    assert r.exception is not None and r.exception.type == "PermissionError"
    assert "open" in r.blocked_syscalls
    assert not outside.exists()


def test_write_inside_the_copy_is_allowed_and_never_touches_the_snapshot(by_id, project: Path):
    r = by_id["write_inside"]
    assert (r.status, r.return_repr) == ("ok", "'ok'")
    assert not (project / "inside.txt").exists()


def test_environment_is_minimal_and_secrets_do_not_leak(by_id):
    r = by_id["secret"]
    assert (r.status, r.return_repr) == ("ok", "[None, None]")
    keys = eval(by_id["env_keys"].return_repr)  # noqa: S307 - our own list of str literals
    allowed = {"PATH", "TEMP", "TMP", "TMPDIR", "PYTHONIOENCODING", "PYTHONUTF8", "SYSTEMROOT"}
    assert {k.upper() for k in keys if not k.startswith("=")} <= allowed
    assert "PM_SECRET_TEST" not in keys


def test_minimal_env_contents(tmp_path: Path):
    env = minimal_env(sys.executable, tmp_path)
    assert env["TEMP"] == env["TMP"] == str(tmp_path)
    assert env["PATH"] == os.path.dirname(os.path.abspath(sys.executable))
    assert env["PYTHONIOENCODING"] == "utf-8" and env["PYTHONUTF8"] == "1"
    extra = set(env) - {"PATH", "TEMP", "TMP", "PYTHONIOENCODING", "PYTHONUTF8", "SYSTEMROOT", "TMPDIR"}
    assert extra == set()


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object memory limit")
def test_job_object_memory_limit(by_id):
    r = by_id["big_alloc"]
    assert r.status == "exception"
    assert r.exception is not None and r.exception.type == "MemoryError"


def test_interactive_script_events_and_raw_stdout(by_id):
    r = by_id["interactive"]
    assert r.status == "ok" and r.exit_code == 0
    expected = "Pilot name: Starting fuel: Hello Camille, fuel=400\n"
    assert r.stdout == expected  # no echo of the typed text
    assert "\r" not in r.stdout
    p1, p2, out = line_of(INTERACTIVE, "PROMPT-1"), line_of(INTERACTIVE, "PROMPT-2"), line_of(INTERACTIVE, "PRINT-LINE")
    assert [(e.kind, e.text, e.file, e.line) for e in r.events] == [
        ("output", "Pilot name: ", "interactive.py", p1),
        ("input", "Camille", "interactive.py", p1),
        ("output", "Starting fuel: ", "interactive.py", p2),
        ("input", "400", "interactive.py", p2),
        ("output", "Hello Camille, fuel=400\n", "interactive.py", out),
    ]
    assert r.stderr == ""


def test_crlf_stdin_is_read_like_lf(by_id):
    r = by_id["interactive_crlf"]
    assert r.stdout == "Pilot name: Starting fuel: Hello Camille, fuel=400\n"
    assert [e.text for e in r.events if e.kind == "input"] == ["Camille", "400"]


def test_utf8_is_byte_exact(by_id):
    r = by_id["utf8"]
    assert r.status == "ok"
    assert r.stdout.encode("utf-8") == "Nom : Bonjour é🙂 ✓\n".encode("utf-8")
    assert [e.text for e in r.events if e.kind == "input"] == ["é🙂"]


def test_eof_when_stdin_is_exhausted(by_id):
    r = by_id["eof"]
    assert r.status == "exception"
    assert r.exit_code == 1
    assert r.exception is not None and r.exception.type == "EOFError"
    assert r.exception.file == "interactive.py" and r.exception.line == line_of(INTERACTIVE, "PROMPT-2")
    assert r.stdout == "Pilot name: Starting fuel: "
    assert [e.kind for e in r.events] == ["output", "input", "output"]  # no input event for the EOF
    assert "EOFError" in r.stderr and "Traceback" in r.stderr
    assert "child.py" not in r.stderr


def test_sys_exit_code(by_id):
    r = by_id["exit3"]
    assert (r.status, r.exit_code, r.stdout) == ("ok", 3, "bye\n")


def test_script_sibling_import_in_subdirectory(by_id):
    r = by_id["pkg_script"]
    assert (r.status, r.exit_code, r.stdout) == ("ok", 0, "42\n")


def test_path_escaping_the_project_is_rejected(by_id):
    r = by_id["escape"]
    assert r.status == "harness_error"
    assert r.harness_error and "escapes" in r.harness_error


def test_import_job_with_top_level_input(by_id):
    r = by_id["import_waits"]
    assert r.status == "import_error"
    assert r.exception is not None and r.exception.type == "EOFError"
    assert r.exception.file == "waits_input.py" and r.exception.line == 1
    assert r.import_stdout == "Name? " and r.stdout == "Name? "
    ok = by_id["import_ok"]
    assert (ok.status, ok.exit_code, ok.stdout) == ("ok", 0, "")


def test_many_jobs_in_parallel(by_id):
    for i in range(12):
        r = by_id[f"par{i}"]
        assert (r.status, r.return_repr, r.return_type) == ("ok", str(i * i), "int")


def test_temp_dir_is_removed(run):
    sandbox = run[0]
    assert sandbox.last_dir is not None
    assert not sandbox.last_dir.exists()


def test_info_is_honest():
    info = get_sandbox("local").info()
    assert info.mode == "local" and info.network is False
    text = " ".join(info.warnings).lower()
    assert "not a security boundary" in text and "docker" in text
    if os.name == "nt":
        assert "job object" in text


def test_empty_plan_runs_nothing(tmp_path: Path):
    results = LocalSandbox().run(RunPlan(jobs=[]), tmp_path)
    assert results.results == [] and results.sandbox_mode == "local"
