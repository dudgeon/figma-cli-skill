"""figma whoami — sanity-check the PAT.

GET /v1/me — https://www.figma.com/developers/api#get-me-endpoint
"""
from __future__ import annotations

from .. import http, output


def run(_args) -> int:
    try:
        data = http.get("/v1/me")
    except http.FigmaHttpError as e:
        output.die(f"HTTP {e.status}: whoami failed", hint_text=e.hint, url=e.url)
    output.emit({
        "id": data.get("id"),
        "handle": data.get("handle"),
        "email": data.get("email"),
        "img_url": data.get("img_url"),
    })
    return 0
