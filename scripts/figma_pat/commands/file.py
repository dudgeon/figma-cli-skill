"""figma file summary|page — Tier 1 and Tier 2."""
from __future__ import annotations

from .. import http, output, urls
from ..tiers import page_index, summary


def run_summary(args) -> int:
    parsed = _require_file(args.url)
    try:
        payload = summary.generate(parsed.file_key, slug=parsed.slug, source_url=parsed.raw)
    except http.FigmaHttpError as e:
        output.die(f"HTTP {e.status}: file summary failed", hint_text=e.hint, url=e.url)
    output.emit(payload)
    return 0


def run_page(args) -> int:
    parsed = _require_file(args.url)
    try:
        payload = page_index.generate(parsed.file_key, page_id=args.page_id, slug=parsed.slug)
    except http.FigmaHttpError as e:
        output.die(f"HTTP {e.status}: file page failed", hint_text=e.hint, url=e.url)
    output.emit(payload)
    return 0


def _require_file(url: str):
    parsed = urls.parse(url)
    if not parsed.file_key:
        output.die(
            f"Expected a file or node URL, got kind={parsed.kind!r}: {url}",
            hint_text="Use a figma.com/design/<key> or figma.com/file/<key> URL.",
        )
    return parsed
