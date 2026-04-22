"""Rendering helpers backed by Figma's Images API.

GET /v1/images/:key  — https://www.figma.com/developers/api#get-images-endpoint
"""
from __future__ import annotations

import pathlib
import urllib.error
import urllib.request
from typing import Literal

from .. import http, output

Format = Literal["png", "svg", "pdf", "jpg"]


def render_urls(
    file_key: str,
    node_ids: list[str],
    *,
    fmt: Format = "png",
    scale: int = 2,
    svg_outline_text: bool = True,
) -> dict[str, str]:
    """Ask Figma for signed CDN URLs for rendered nodes. Returns {node_id: url}."""
    params: dict[str, object] = {
        "ids": node_ids,
        "format": fmt,
    }
    # PNG/JPG use scale; SVG/PDF don't.
    if fmt in ("png", "jpg"):
        params["scale"] = scale
    if fmt == "svg":
        params["svg_outline_text"] = "true" if svg_outline_text else "false"

    data = http.get(f"/v1/images/{file_key}", params=params)
    if data.get("err"):
        output.die(
            f"Figma render failed: {data['err']}",
            hint_text="Check that node ids exist in this file and that you have access.",
        )
    return {nid: url for nid, url in (data.get("images") or {}).items() if url}


def download(url: str, dest: pathlib.Path) -> int:
    """Download a pre-signed CDN URL to disk. Returns bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": http.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
            total = 0
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                total += len(chunk)
            return total
    except urllib.error.URLError as e:
        output.die(f"Failed to download {url}: {e.reason}", url=url)
        return 0  # unreachable; keep type-checkers happy
