"""Image-fill bytes: the raw PNG/JPG behind `IMAGE` paints.

GET /v1/files/:key/images  — https://www.figma.com/developers/api#get-images-endpoint
  (the "Get image fills" variant under the same docs section)
"""
from __future__ import annotations

import pathlib

from .. import http
from . import images


def fetch_map(file_key: str) -> dict[str, str]:
    """Return {image_ref: signed_s3_url} for every IMAGE paint in the file."""
    data = http.get(f"/v1/files/{file_key}/images")
    meta = data.get("meta") or data  # tolerate both response shapes
    return dict(meta.get("images") or {})


def collect_refs(node: dict) -> set[str]:
    """Walk a node tree and return every imageRef referenced by IMAGE paints."""
    found: set[str] = set()

    def visit(n: dict) -> None:
        for paint_key in ("fills", "strokes", "background"):
            for paint in n.get(paint_key) or []:
                if isinstance(paint, dict) and paint.get("type") == "IMAGE":
                    ref = paint.get("imageRef")
                    if ref:
                        found.add(ref)
        for child in n.get("children") or []:
            visit(child)

    visit(node)
    return found


def download_all(file_key: str, refs: set[str], dest_dir: pathlib.Path) -> dict[str, str]:
    """Download each referenced fill to dest_dir. Returns {ref: local_path}."""
    if not refs:
        return {}
    url_map = fetch_map(file_key)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}
    for ref in sorted(refs):
        url = url_map.get(ref)
        if not url:
            continue
        # Signed URLs typically end with a filename; otherwise default to .png.
        suffix = ".png"
        path = url.split("?", 1)[0]
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            if path.lower().endswith(ext):
                suffix = ext
                break
        target = dest_dir / f"{ref}{suffix}"
        images.download(url, target)
        out[ref] = str(target)
    return out
