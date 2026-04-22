"""Tier 1 — file summary.

GET /v1/files/:key?depth=2  — https://www.figma.com/developers/api#get-files-endpoint
  depth=1 returns pages, depth=2 returns pages + their top-level frames.
"""
from __future__ import annotations

from typing import Any

from .. import http, refs, urls

FRAME_LIKE = {"FRAME", "COMPONENT", "COMPONENT_SET", "SECTION", "GROUP"}
MAX_TOP_FRAMES_PER_PAGE = 50


def generate(file_key: str, *, slug: str | None = None, source_url: str | None = None) -> dict[str, Any]:
    data = http.get(f"/v1/files/{file_key}", params={"depth": 2})
    doc = data.get("document") or {}
    pages_out = []
    ref_pages = []
    for page in doc.get("children") or []:
        frames = []
        for child in page.get("children") or []:
            if child.get("type") in FRAME_LIKE:
                frames.append({
                    "id": child["id"],
                    "name": child.get("name"),
                    "type": child.get("type"),
                    "bbox": child.get("absoluteBoundingBox"),
                    "_url": urls.deeplink(file_key, child["id"], slug=slug or ""),
                })
        pages_out.append({
            "id": page["id"],
            "name": page.get("name"),
            "frame_count": len(frames),
            "top_frames": frames[:MAX_TOP_FRAMES_PER_PAGE],
            "truncated": len(frames) > MAX_TOP_FRAMES_PER_PAGE,
        })
        ref_pages.append({"id": page["id"], "name": page.get("name")})

    _update_refs(file_key, data, ref_pages, source_url=source_url)

    return {
        "file_key": file_key,
        "name": data.get("name"),
        "last_modified": data.get("lastModified"),
        "thumbnail_url": data.get("thumbnailUrl"),
        "role": data.get("role"),
        "editor_type": data.get("editorType"),
        "version": data.get("version"),
        "url": urls.deeplink(file_key, slug=slug or ""),
        "pages": pages_out,
        "counts": {
            "components": len(data.get("components") or {}),
            "component_sets": len(data.get("componentSets") or {}),
            "styles": len(data.get("styles") or {}),
        },
    }


def _update_refs(file_key: str, data: dict, pages: list[dict], *, source_url: str | None) -> None:
    store = refs.load()
    refs.add_file(
        store,
        file_key,
        name=data.get("name"),
        last_modified=data.get("lastModified"),
        thumbnail_url=data.get("thumbnailUrl"),
        pages=pages,
        source_url=source_url,
    )
    refs.save(store)
