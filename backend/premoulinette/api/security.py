"""Local-only API hardening.

* Host header must be ``localhost``, ``127.0.0.1`` or ``[::1]`` (any port): blocks DNS rebinding.
* Mutating methods require ``X-PreMoulinette: 1`` (a custom header forces a CORS preflight, so a
  foreign web page cannot forge it) and, when an ``Origin`` is sent, an allowed or same origin.
* CORS is open only to the Vite dev server origins.
"""
from __future__ import annotations

from fastapi import FastAPI
from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})
ALLOWED_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
CSRF_HEADER = "X-PreMoulinette"
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def host_name(host_header: str) -> str | None:
    """Host part of a ``Host`` header (lower-cased), or None if malformed."""
    value = host_header.strip().lower()
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            return None
        name, port = value[: end + 1], value[end + 1:]
    else:
        name, sep, rest = value.partition(":")
        port = sep + rest
    if port and not (port.startswith(":") and port[1:].isdigit()):
        return None
    return name or None


def host_allowed(host_header: str | None) -> bool:
    return host_header is not None and host_name(host_header) in ALLOWED_HOSTS


def origin_allowed(origin: str, host_header: str) -> bool:
    origin = origin.strip().lower()
    return origin in ALLOWED_ORIGINS or origin in (f"http://{host_header.lower()}", f"https://{host_header.lower()}")


class LocalOnlyMiddleware:
    """Pure ASGI middleware enforcing the Host / custom header / Origin rules."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        host = headers.get("host")
        if not host_allowed(host):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await _deny(scope, receive, send, "Forbidden host: PréMoulinette only answers requests sent to localhost.")
            return
        if scope["type"] == "http" and scope["method"] in MUTATING_METHODS:
            if headers.get(CSRF_HEADER) != "1":
                await _deny(scope, receive, send, f"Missing required header {CSRF_HEADER}: 1.")
                return
            origin = headers.get("origin")
            if origin is not None and not origin_allowed(origin, host or ""):
                await _deny(scope, receive, send, "Forbidden origin.")
                return
        await self.app(scope, receive, send)


async def _deny(scope: Scope, receive: Receive, send: Send, message: str) -> None:
    await JSONResponse({"detail": message}, status_code=403)(scope, receive, send)


def install_security(app: FastAPI) -> None:
    # Added last = outermost: CORS headers are present even on 403 answers (debuggable from Vite).
    app.add_middleware(LocalOnlyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_ORIGINS),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", CSRF_HEADER],
        expose_headers=["Content-Disposition"],
        allow_credentials=False,
        max_age=600,
    )
