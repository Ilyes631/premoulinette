"""Windows Job Objects via ctypes (local sandbox, Windows only).

A job groups the harness process and every child it spawns:
* ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``: closing the job handle kills the whole tree (no orphan survives);
* ``JOB_OBJECT_LIMIT_ACTIVE_PROCESS``: caps the number of live processes (fork bombs);
* ``JOB_OBJECT_LIMIT_JOB_MEMORY``: caps the committed memory of all processes together;
* ``JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION``: no Windows Error Reporting dialog can hang a crashed child;
* basic UI restrictions (clipboard, desktop, system parameters...), best effort.

Every function raises :class:`WinJobError` on failure; nothing here is imported on POSIX by default.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

JobObjectBasicUIRestrictions = 4
JobObjectExtendedLimitInformation = 9

JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

JOB_OBJECT_UILIMIT_HANDLES = 0x0001
JOB_OBJECT_UILIMIT_READCLIPBOARD = 0x0002
JOB_OBJECT_UILIMIT_WRITECLIPBOARD = 0x0004
JOB_OBJECT_UILIMIT_SYSTEMPARAMETERS = 0x0008
JOB_OBJECT_UILIMIT_DISPLAYSETTINGS = 0x0010
JOB_OBJECT_UILIMIT_GLOBALATOMS = 0x0020
JOB_OBJECT_UILIMIT_DESKTOP = 0x0040
JOB_OBJECT_UILIMIT_EXITWINDOWS = 0x0080
UI_RESTRICTIONS = 0x00FF

PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001

DEFAULT_ACTIVE_PROCESSES = 32
DEFAULT_MEMORY_BYTES = 512 * 1024 * 1024


class WinJobError(OSError):
    pass


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):  # noqa: N801 - Win32 name
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):  # noqa: N801
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):  # noqa: N801
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class JOBOBJECT_BASIC_UI_RESTRICTIONS(ctypes.Structure):  # noqa: N801
    _fields_ = [("UIRestrictionsClass", wintypes.DWORD)]


_kernel32 = None


def _k32():
    global _kernel32
    if _kernel32 is None:
        if os.name != "nt":
            raise WinJobError("Windows Job Objects are only available on Windows")
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        k.SetInformationJobObject.restype = wintypes.BOOL
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k.AssignProcessToJobObject.restype = wintypes.BOOL
        k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.TerminateJobObject.restype = wintypes.BOOL
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        _kernel32 = k
    return _kernel32


def _error(what: str) -> WinJobError:
    code = ctypes.get_last_error()
    return WinJobError(f"{what} failed: {ctypes.FormatError(code).strip()} (error {code})")


def create_job(
    *, max_processes: int = DEFAULT_ACTIVE_PROCESSES, memory_bytes: int = DEFAULT_MEMORY_BYTES
) -> int:
    """Create a job object with the sandbox limits; returns its handle (close it with :func:`close`)."""
    k = _k32()
    handle = k.CreateJobObjectW(None, None)
    if not handle:
        raise _error("CreateJobObjectW")
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | JOB_OBJECT_LIMIT_JOB_MEMORY
        | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
    )
    info.BasicLimitInformation.ActiveProcessLimit = max(1, int(max_processes))
    info.JobMemoryLimit = max(16 * 1024 * 1024, int(memory_bytes))
    ok = k.SetInformationJobObject(
        handle, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        err = _error("SetInformationJobObject")
        k.CloseHandle(handle)
        raise err
    ui = JOBOBJECT_BASIC_UI_RESTRICTIONS(UI_RESTRICTIONS)
    k.SetInformationJobObject(handle, JobObjectBasicUIRestrictions, ctypes.byref(ui), ctypes.sizeof(ui))  # best effort
    return int(handle)


def assign(job: int, process_handle: int | None = None, *, pid: int | None = None) -> None:
    """Put a process in the job, by handle (``Popen._handle``) or by pid (OpenProcess)."""
    k = _k32()
    opened = None
    if process_handle is None:
        if pid is None:
            raise WinJobError("assign() needs a process handle or a pid")
        opened = k.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, int(pid))
        if not opened:
            raise _error("OpenProcess")
        process_handle = opened
    try:
        if not k.AssignProcessToJobObject(job, int(process_handle)):
            raise _error("AssignProcessToJobObject")
    finally:
        if opened:
            k.CloseHandle(opened)


def terminate(job: int, exit_code: int = 1) -> bool:
    """Kill every process of the job (the whole tree)."""
    return bool(_k32().TerminateJobObject(job, exit_code))


def close(job: int) -> None:
    """Close the job handle (with KILL_ON_JOB_CLOSE, any surviving process is killed)."""
    if job:
        _k32().CloseHandle(job)
