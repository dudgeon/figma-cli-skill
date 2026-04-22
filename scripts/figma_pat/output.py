"""JSON stdout / human-hint stderr helpers.

Every command emits machine-readable JSON on stdout. Human-oriented
progress and hints go to stderr. Errors are JSON on stderr with a
non-zero exit code.
"""
from __future__ import annotations

import json
import sys
from typing import Any, NoReturn

_quiet = False


def set_quiet(quiet: bool) -> None:
    global _quiet
    _quiet = quiet


def emit(payload: Any) -> None:
    """Write a JSON result to stdout."""
    json.dump(payload, sys.stdout, indent=2, sort_keys=False, default=str)
    sys.stdout.write("\n")
    sys.stdout.flush()


def hint(msg: str) -> None:
    """Write a human-readable hint to stderr (suppressed by --quiet)."""
    if _quiet:
        return
    sys.stderr.write(msg.rstrip() + "\n")
    sys.stderr.flush()


def die(error: str, *, hint_text: str | None = None, url: str | None = None, code: int = 1) -> NoReturn:
    """Emit a structured error on stderr and exit non-zero."""
    payload: dict[str, Any] = {"error": error}
    if hint_text:
        payload["hint"] = hint_text
    if url:
        payload["url"] = url
    json.dump(payload, sys.stderr, indent=2)
    sys.stderr.write("\n")
    sys.stderr.flush()
    sys.exit(code)
