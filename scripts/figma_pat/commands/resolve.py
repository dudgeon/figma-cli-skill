"""figma resolve <url> — classify a Figma URL.

Also persists whatever identifiers it can extract to refs.json so later
commands (file summary, node read) can use them without re-pasting URLs.
"""
from __future__ import annotations

from .. import output, refs, urls


def run(args) -> int:
    parsed = urls.parse(args.url)
    if parsed.kind == "unknown":
        output.die(
            f"Not a recognized Figma URL: {args.url}",
            hint_text="Expected figma.com/file/<key>, /design/<key>, /proto/<key>, /board/<key>, /files/team/<id>, or /files/project/<id>.",
        )

    data = refs.load()
    if parsed.team_id:
        refs.add_team(data, parsed.team_id, source_url=parsed.raw)
    if parsed.project_id:
        refs.add_project(data, parsed.project_id, source_url=parsed.raw)
    if parsed.file_key:
        refs.add_file(data, parsed.file_key, source_url=parsed.raw)
    if parsed.file_key and parsed.node_id:
        refs.add_node(data, parsed.file_key, parsed.node_id, url=parsed.raw)
    refs.save(data)

    output.emit(parsed.to_dict())
    return 0
