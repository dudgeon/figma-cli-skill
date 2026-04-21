"""Tier 4 — binary assets on demand.

Writes rendered asset bytes to $CLAUDE_PROJECT_DIR/.figma-cache/<file>/<node>/
and, optionally, the raw image-fill bytes into fills/.

GET /v1/images/:key  — export-ready render
GET /v1/files/:key/images  — image-fill bytes
"""
from __future__ import annotations

from typing import Any

from .. import cache
from ..render import image_fills, images


def generate(
    file_key: str,
    node_id: str,
    *,
    fmt: str = "png",
    scale: int = 2,
    download_image_fills: bool = True,
) -> dict[str, Any]:
    cache_dir = cache.ensure_node_dir(file_key, node_id)

    if fmt in ("png", "jpg"):
        render_map = images.render_urls(file_key, [node_id], fmt=fmt, scale=scale)  # type: ignore[arg-type]
        out_path = cache_dir / f"render@{scale}x.{fmt}"
    else:
        render_map = images.render_urls(file_key, [node_id], fmt=fmt)  # type: ignore[arg-type]
        out_path = cache_dir / f"render.{fmt}"

    render_bytes = 0
    if node_id in render_map:
        render_bytes = images.download(render_map[node_id], out_path)

    fills_out: dict[str, str] = {}
    if download_image_fills:
        # Fills require walking the tree. Callers that want fills should run
        # `node read` first (which writes tree.json); we read that for refs.
        tree_path = cache_dir / "tree.json"
        if tree_path.exists():
            import json as _json
            tree = _json.loads(tree_path.read_text(encoding="utf-8"))
            refs = image_fills.collect_refs(tree)
            if refs:
                fills_out = image_fills.download_all(file_key, refs, cache_dir / "fills")

    return {
        "file_key": file_key,
        "node_id": node_id,
        "render": {
            "format": fmt,
            "scale": scale if fmt in ("png", "jpg") else None,
            "path": str(out_path) if out_path.exists() else None,
            "bytes": render_bytes,
        },
        "fills": {
            "count": len(fills_out),
            "dir": str(cache_dir / "fills") if fills_out else None,
            "paths": fills_out,
        },
    }
