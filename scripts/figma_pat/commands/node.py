"""figma node read|assets — Tier 3 and Tier 4."""
from __future__ import annotations

from .. import http, output, urls
from ..tiers import assets, node_full


def run_read(args) -> int:
    parsed = _require_node(args.url)
    try:
        payload = node_full.generate(
            parsed.file_key,
            parsed.node_id,
            slug=parsed.slug,
            scale=args.scale,
            include_svg=not args.no_svg,
            depth=args.depth,
        )
    except http.FigmaHttpError as e:
        output.die(f"HTTP {e.status}: node read failed", hint_text=e.hint, url=e.url)
    output.emit(payload)
    return 0


def run_assets(args) -> int:
    parsed = _require_node(args.url)
    try:
        payload = assets.generate(parsed.file_key, parsed.node_id, fmt=args.format, scale=args.scale)
    except http.FigmaHttpError as e:
        output.die(f"HTTP {e.status}: node assets failed", hint_text=e.hint, url=e.url)
    output.emit(payload)
    return 0


def _require_node(url: str):
    parsed = urls.parse(url)
    if not (parsed.file_key and parsed.node_id):
        output.die(
            f"Expected a node URL (with ?node-id=...), got kind={parsed.kind!r}: {url}",
            hint_text="Open the frame in Figma, right-click > Copy link, and paste that full URL.",
        )
    return parsed
