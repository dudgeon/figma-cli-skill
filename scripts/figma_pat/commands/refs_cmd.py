"""figma refs list|show|forget — browse the persistent ref file."""
from __future__ import annotations

from .. import output, refs, urls


def _identifier_from_input(value: str) -> str:
    """Accept a Figma URL or a bare id. Returns the ref-file key."""
    if "figma.com" in value or value.startswith("http"):
        parsed = urls.parse(value)
        if parsed.file_key and parsed.node_id:
            return f"{parsed.file_key}:{parsed.node_id}"
        for candidate in (parsed.file_key, parsed.project_id, parsed.team_id):
            if candidate:
                return candidate
    return value


def run_list(args) -> int:
    data = refs.load()
    items = refs.find(data, kind=args.kind, grep=args.grep)
    output.emit({"count": len(items), "items": items})
    return 0


def run_show(args) -> int:
    data = refs.load()
    ident = _identifier_from_input(args.identifier)
    for bucket_kind, bucket_key in (
        ("team", "teams"),
        ("project", "projects"),
        ("file", "files"),
        ("node", "nodes"),
    ):
        entry = data.get(bucket_key, {}).get(ident)
        if entry:
            output.emit({"kind": bucket_kind, "id": ident, **entry})
            return 0
    output.die(f"No ref found for {ident}", hint_text="Try `figma refs list --grep <term>`.")


def run_forget(args) -> int:
    data = refs.load()
    ident = _identifier_from_input(args.identifier)
    removed = refs.forget(data, ident)
    if not removed:
        output.die(f"No ref found for {ident}")
    refs.save(data)
    output.emit({"forgotten": ident})
    return 0
