"""Tier 2 — page index.

GET /v1/files/:key/nodes?ids=<page_id>&depth=3
  https://www.figma.com/developers/api#get-file-nodes-endpoint
  depth=3 gives page -> top-level frames -> their direct children.
"""
from __future__ import annotations

from typing import Any

from .. import http, refs, urls

FRAME_LIKE = {"FRAME", "COMPONENT", "COMPONENT_SET", "SECTION", "GROUP", "INSTANCE"}


def generate(file_key: str, page_id: str | None = None, *, slug: str | None = None) -> dict[str, Any]:
    if page_id is None:
        # Resolve first page via file summary.
        file_meta = http.get(f"/v1/files/{file_key}", params={"depth": 1})
        pages = (file_meta.get("document") or {}).get("children") or []
        if not pages:
            return {"file_key": file_key, "page_id": None, "frames": []}
        page_id = pages[0]["id"]

    data = http.get(f"/v1/files/{file_key}/nodes", params={"ids": page_id, "depth": 3})
    node_envelope = (data.get("nodes") or {}).get(page_id) or {}
    page = node_envelope.get("document") or {}

    frames_out = []
    ref_store = refs.load()
    for child in page.get("children") or []:
        if child.get("type") not in FRAME_LIKE:
            continue
        direct_children = [
            {
                "id": c["id"],
                "name": c.get("name"),
                "type": c.get("type"),
                "bbox": c.get("absoluteBoundingBox"),
            }
            for c in (child.get("children") or [])
        ]
        frame_entry = {
            "id": child["id"],
            "name": child.get("name"),
            "type": child.get("type"),
            "bbox": child.get("absoluteBoundingBox"),
            "layout_mode": child.get("layoutMode"),
            "child_count": len(child.get("children") or []),
            "children_preview": direct_children[:25],
            "_url": urls.deeplink(file_key, child["id"], slug=slug or ""),
        }
        frames_out.append(frame_entry)
        refs.add_node(
            ref_store,
            file_key,
            child["id"],
            name=child.get("name"),
            type=child.get("type"),
            page_id=page_id,
            url=frame_entry["_url"],
        )
    refs.save(ref_store)

    return {
        "file_key": file_key,
        "page_id": page_id,
        "page_name": page.get("name"),
        "frame_count": len(frames_out),
        "frames": frames_out,
    }
