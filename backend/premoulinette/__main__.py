"""``python -m premoulinette [--port N] [--host H] [--reload] [--open] [--data-dir DIR]``

Serves the API (and the built SPA when ``frontend/dist`` exists) on 127.0.0.1 by default.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

from premoulinette import config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m premoulinette", description="PréMoulinette local server")
    parser.add_argument("--port", type=int, default=config.PORT, help=f"TCP port (default {config.PORT})")
    parser.add_argument(
        "--host", default=config.HOST,
        help="Bind address (default 127.0.0.1). Anything else exposes student code execution to the network.",
    )
    parser.add_argument("--reload", action="store_true", help="Auto-reload on backend code changes (development)")
    parser.add_argument("--open", action="store_true", help="Open the app in the default browser")
    parser.add_argument("--data-dir", type=Path, default=None, help="Data directory (default: PREMOULINETTE_DATA or <repo>/.data)")
    parser.add_argument("--log-level", default="info", choices=["critical", "error", "warning", "info", "debug"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 0 < args.port < 65536:
        print(f"Invalid port: {args.port}", file=sys.stderr)
        return 2
    if args.data_dir is not None:
        # Environment (not an argument) so that --reload worker processes see it too.
        os.environ["PREMOULINETTE_DATA"] = str(args.data_dir.expanduser().resolve())
    if args.host not in config.LOOPBACK_HOSTS:
        print(
            f"WARNING: binding to {args.host}. PréMoulinette runs student code and is meant for localhost only.",
            file=sys.stderr,
        )

    import uvicorn  # imported late: keeps --help fast

    url = f"http://{'localhost' if args.host in config.LOOPBACK_HOSTS else args.host}:{args.port}"
    print(f"PréMoulinette API on {url}  (data: {config.resolve_data_dir()})", flush=True)
    if args.open:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    uvicorn.run(
        "premoulinette.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(Path(__file__).resolve().parent)] if args.reload else None,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
