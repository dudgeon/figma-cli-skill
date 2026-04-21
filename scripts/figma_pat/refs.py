"""Persistent metadata learned from URLs the user has pointed at.

Lives at <skill_dir>/refs.json next to SKILL.md. Accumulated lazily as
the CLI resolves URLs and fetches resources. Never purged automatically.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import tempfile
from typing import Any

SCHEMA_VERSION = 1


def skill_dir() -> pathlib.Path:
    """Where SKILL.md lives. Overridable via FIGMA_SKILL_DIR for tests."""
    env = os.environ.get("FIGMA_SKILL_DIR")
    if env:
        return pathlib.Path(env).resolve()
    # figma_pat/refs.py -> figma_pat -> scripts -> <skill_dir>
    return pathlib.Path(__file__).resolve().parent.parent.parent


def refs_path() -> pathlib.Path:
    return skill_dir() / "refs.json"


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")


def _empty() -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "last_updated": _now(),
        "teams": {},
        "projects": {},
        "files": {},
        "nodes": {},
    }


def load() -> dict[str, Any]:
    path = refs_path()
    if not path.exists():
        return _empty()
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (json.JSONDecodeError, OSError):
        return _empty()
    # Forward-compat shim
    data.setdefault("version", SCHEMA_VERSION)
    for k in ("teams", "projects", "files", "nodes"):
        data.setdefault(k, {})
    return data


def save(data: dict[str, Any]) -> None:
    data["last_updated"] = _now()
    path = refs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as tmp:
        json.dump(data, tmp, indent=2, sort_keys=False)
        tmp.write("\n")
        tmp_path = pathlib.Path(tmp.name)
    os.replace(tmp_path, path)


def add_team(data: dict, team_id: str, *, name: str | None = None, source_url: str | None = None) -> None:
    entry = data["teams"].setdefault(team_id, {"first_seen_at": _now()})
    if name:
        entry["name"] = name
    if source_url and "first_seen_url" not in entry:
        entry["first_seen_url"] = source_url
    entry["last_seen_at"] = _now()


def add_project(
    data: dict,
    project_id: str,
    *,
    team_id: str | None = None,
    name: str | None = None,
    source_url: str | None = None,
) -> None:
    entry = data["projects"].setdefault(project_id, {"first_seen_at": _now()})
    if team_id:
        entry["team_id"] = team_id
    if name:
        entry["name"] = name
    if source_url and "first_seen_url" not in entry:
        entry["first_seen_url"] = source_url
    entry["last_seen_at"] = _now()


def add_file(
    data: dict,
    file_key: str,
    *,
    name: str | None = None,
    project_id: str | None = None,
    last_modified: str | None = None,
    thumbnail_url: str | None = None,
    pages: list[dict] | None = None,
    source_url: str | None = None,
) -> None:
    entry = data["files"].setdefault(file_key, {"first_seen_at": _now()})
    if name:
        entry["name"] = name
    if project_id:
        entry["project_id"] = project_id
    if last_modified:
        entry["last_modified"] = last_modified
    if thumbnail_url:
        entry["thumbnail_url"] = thumbnail_url
    if pages is not None:
        entry["pages"] = pages
    if source_url and "first_seen_url" not in entry:
        entry["first_seen_url"] = source_url
    entry["last_fetched_at"] = _now()


def add_node(
    data: dict,
    file_key: str,
    node_id: str,
    *,
    name: str | None = None,
    type: str | None = None,
    page_id: str | None = None,
    url: str | None = None,
) -> None:
    key = f"{file_key}:{node_id}"
    entry = data["nodes"].setdefault(key, {"first_seen_at": _now(), "file_key": file_key, "node_id": node_id})
    if name:
        entry["name"] = name
    if type:
        entry["type"] = type
    if page_id:
        entry["page_id"] = page_id
    if url:
        entry["url"] = url
    entry["last_fetched_at"] = _now()


def find(data: dict, *, kind: str | None = None, grep: str | None = None) -> list[dict]:
    """Return a flat list of entries, optionally filtered by kind and a case-insensitive name grep."""
    kinds = [kind] if kind else ["team", "project", "file", "node"]
    out: list[dict] = []
    pat = grep.lower() if grep else None
    for k in kinds:
        bucket = {"team": "teams", "project": "projects", "file": "files", "node": "nodes"}[k]
        for ref_id, entry in data.get(bucket, {}).items():
            name = entry.get("name", "")
            if pat and pat not in name.lower() and pat not in ref_id.lower():
                continue
            item = {"kind": k, "id": ref_id}
            item.update(entry)
            out.append(item)
    return out


def forget(data: dict, identifier: str) -> bool:
    """Remove an entry by id (team_id, project_id, file_key, or '<file_key>:<node_id>'). Returns True if something was removed."""
    for bucket in ("teams", "projects", "files", "nodes"):
        if identifier in data.get(bucket, {}):
            del data[bucket][identifier]
            return True
    return False
