"""Figma REST client (stdlib only).

Handles auth, JSON encoding, 429 honoring of Retry-After, exponential
backoff on network and 5xx errors, and structured error emission.

Figma REST API docs: https://www.figma.com/developers/api
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from . import output

API_BASE = "https://api.figma.com"
RETRY_DELAYS = (2, 4, 8, 16)  # seconds
USER_AGENT = "figma-cli-skill/0.1 (+https://github.com/dudgeon/figma-cli-skill)"


class FigmaHttpError(Exception):
    def __init__(self, status: int, url: str, body: str, *, hint: str | None = None):
        super().__init__(f"HTTP {status} from {url}")
        self.status = status
        self.url = url
        self.body = body
        self.hint = hint


@dataclass
class Response:
    status: int
    data: Any
    headers: dict[str, str]
    url: str


def _token() -> str:
    tok = os.environ.get("FIGMA_TOKEN")
    if not tok:
        output.die(
            "FIGMA_TOKEN is not set",
            hint_text="export FIGMA_TOKEN=figd_... (get one from Figma Settings > Security > Personal access tokens)",
        )
    return tok


def _hint_for_status(status: int) -> str | None:
    if status == 401:
        return "Token is invalid or expired. Generate a new one in Figma Settings > Security."
    if status == 403:
        return (
            "Token owner doesn't have access. For files: confirm the file is shared with the user "
            "who owns the token. For variables/library endpoints: Enterprise plan may be required."
        )
    if status == 404:
        return "Wrong key/ID, or the resource has been deleted. Double-check the URL you pasted."
    if status == 429:
        return "Rate limited. The CLI retries automatically; if this persists, reduce request volume."
    if 500 <= status < 600:
        return "Figma server error. The CLI retries automatically; try again shortly if it persists."
    return None


def _build_url(path: str, params: dict[str, Any] | None = None) -> str:
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{API_BASE}/{path}"
    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        # Lists become comma-separated (Figma convention for ?ids=a,b,c)
        encoded = {
            k: ",".join(str(x) for x in v) if isinstance(v, (list, tuple)) else str(v)
            for k, v in filtered.items()
        }
        if encoded:
            url = f"{url}?{urllib.parse.urlencode(encoded, safe=':,')}"
    return url


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: Any = None,
    expect_json: bool = True,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    """Perform a Figma REST request with retries. Returns Response or raises FigmaHttpError."""
    url = _build_url(path, params)
    headers = {
        "X-Figma-Token": _token(),
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if extra_headers:
        headers.update(extra_headers)

    data_bytes: bytes | None = None
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last_err: Exception | None = None
    for attempt in range(len(RETRY_DELAYS) + 1):
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                if expect_json and raw:
                    try:
                        data = json.loads(raw.decode("utf-8"))
                    except json.JSONDecodeError as e:
                        raise FigmaHttpError(
                            resp.status,
                            url,
                            raw[:500].decode("utf-8", "replace"),
                            hint=f"Expected JSON, got: {e}",
                        ) from e
                else:
                    data = raw
                return Response(status=resp.status, data=data, headers=resp_headers, url=url)

        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", "replace") if e.fp else ""
            status = e.code
            if status == 429 and attempt < len(RETRY_DELAYS):
                ra = e.headers.get("Retry-After")
                delay = _parse_retry_after(ra) if ra else RETRY_DELAYS[attempt]
                output.hint(f"429 rate limited, retrying in {delay}s (attempt {attempt + 1}/{len(RETRY_DELAYS)})")
                time.sleep(delay)
                continue
            if 500 <= status < 600 and attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                output.hint(f"{status} from Figma, retrying in {delay}s (attempt {attempt + 1}/{len(RETRY_DELAYS)})")
                time.sleep(delay)
                continue
            raise FigmaHttpError(status, url, body_text, hint=_hint_for_status(status)) from e

        except urllib.error.URLError as e:
            last_err = e
            if attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                output.hint(f"network error ({e.reason}), retrying in {delay}s (attempt {attempt + 1}/{len(RETRY_DELAYS)})")
                time.sleep(delay)
                continue
            output.die(f"Network error after retries: {e.reason}", url=url)

    # Unreachable, but keep type-checkers happy.
    raise last_err or RuntimeError("request failed without raising")


def _parse_retry_after(value: str) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return RETRY_DELAYS[0]


def get(path: str, **kw: Any) -> Any:
    return request("GET", path, **kw).data


def post(path: str, body: Any, **kw: Any) -> Any:
    return request("POST", path, body=body, **kw).data


def delete(path: str, **kw: Any) -> Any:
    return request("DELETE", path, **kw).data
