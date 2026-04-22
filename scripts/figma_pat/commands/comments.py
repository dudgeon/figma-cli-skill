"""figma comments list|reply|create|resolve.

Endpoints:
  GET    /v1/files/:key/comments
      https://www.figma.com/developers/api#get-comments-endpoint
  POST   /v1/files/:key/comments
      https://www.figma.com/developers/api#post-comments-endpoint
  DELETE /v1/files/:key/comments/:id
      https://www.figma.com/developers/api#delete-comments-endpoint

Resolving a comment thread is an extended endpoint:
  POST   /v1/files/:key/comments/:id/resolve
      (on some plans this may require Enterprise; the CLI degrades
      gracefully and emits a hint if the endpoint isn't available.)
"""
from __future__ import annotations

import json as _json
import pathlib
from typing import Any

from .. import http, output, refs, urls


def run_list(args) -> int:
    parsed = _require_file(args.url)
    try:
        data = http.get(f"/v1/files/{parsed.file_key}/comments")
    except http.FigmaHttpError as e:
        output.die(f"HTTP {e.status}: comments list failed", hint_text=e.hint, url=e.url)

    all_comments = data.get("comments") or []
    threads = _group_into_threads(all_comments, parsed.file_key, slug=parsed.slug or "")

    # Filters
    if args.unresolved:
        threads = [t for t in threads if not t["resolved"]]
    if args.node_id:
        nid = urls.node_id_to_api_form(args.node_id)
        threads = [t for t in threads if t.get("anchor", {}).get("node_id") == nid]
    if args.author:
        needle = args.author.lower()
        threads = [t for t in threads if needle in (t["author"].get("handle") or "").lower()]

    _record_last_file(parsed.file_key)

    output.emit({
        "file_key": parsed.file_key,
        "count": len(threads),
        "threads": threads,
    })
    return 0


def run_reply(args) -> int:
    file_key = _resolve_file_key(getattr(args, "file_url", None))
    body = {"message": args.text, "comment_id": args.comment_id}
    try:
        created = http.post(f"/v1/files/{file_key}/comments", body=body)
    except http.FigmaHttpError as e:
        output.die(f"HTTP {e.status}: comments reply failed", hint_text=e.hint, url=e.url)
    output.emit(_shape_comment(created, file_key, slug=""))
    return 0


def run_create(args) -> int:
    parsed = urls.parse(args.url)
    if not (parsed.file_key and parsed.node_id):
        output.die(
            "comments create requires a node URL (with ?node-id=...).",
            hint_text="Right-click a frame in Figma > Copy link, and paste that.",
        )
    body = {
        "message": args.text,
        "client_meta": {"node_id": parsed.node_id, "node_offset": {"x": 0, "y": 0}},
    }
    try:
        created = http.post(f"/v1/files/{parsed.file_key}/comments", body=body)
    except http.FigmaHttpError as e:
        output.die(f"HTTP {e.status}: comments create failed", hint_text=e.hint, url=e.url)
    _record_last_file(parsed.file_key)
    output.emit(_shape_comment(created, parsed.file_key, slug=parsed.slug or ""))
    return 0


def run_resolve(args) -> int:
    file_key = _resolve_file_key(getattr(args, "file_url", None))
    path = f"/v1/files/{file_key}/comments/{args.comment_id}/resolve"
    try:
        result = http.post(path, body={})
    except http.FigmaHttpError as e:
        if e.status in (404, 405):
            output.die(
                f"HTTP {e.status}: resolve endpoint not available for this plan",
                hint_text="Your plan may not expose the resolve endpoint via REST. You can resolve the thread manually in Figma.",
                url=e.url,
            )
        output.die(f"HTTP {e.status}: comments resolve failed", hint_text=e.hint, url=e.url)
    output.emit({"resolved": args.comment_id, "file_key": file_key, "response": result})
    return 0


# ---------------- helpers ----------------


def _require_file(url: str):
    parsed = urls.parse(url)
    if not parsed.file_key:
        output.die(
            f"Expected a file or node URL, got kind={parsed.kind!r}: {url}",
            hint_text="Use a figma.com/design/<key> or figma.com/file/<key> URL.",
        )
    return parsed


def _group_into_threads(comments: list[dict], file_key: str, *, slug: str) -> list[dict]:
    """Group top-level comments with their replies, newest thread last."""
    by_id: dict[str, dict] = {c["id"]: c for c in comments}
    threads: dict[str, dict] = {}

    # First pass: find root comments.
    for c in comments:
        if not c.get("parent_id"):
            threads[c["id"]] = _thread_envelope(c, file_key, slug=slug)

    # Second pass: attach replies.
    for c in comments:
        parent = c.get("parent_id")
        if parent and parent in threads:
            threads[parent]["replies"].append(_shape_comment(c, file_key, slug=slug))
        elif parent and parent not in threads and parent in by_id:
            # Orphaned reply (shouldn't happen, but be defensive).
            root = by_id[parent]
            threads[root["id"]] = _thread_envelope(root, file_key, slug=slug)
            threads[root["id"]]["replies"].append(_shape_comment(c, file_key, slug=slug))

    # Sort replies by created_at per thread; sort threads by created_at.
    out = sorted(threads.values(), key=lambda t: t.get("created_at") or "")
    for t in out:
        t["replies"].sort(key=lambda r: r.get("created_at") or "")
    return out


def _thread_envelope(root: dict, file_key: str, *, slug: str) -> dict:
    anchor = _anchor(root, file_key, slug=slug)
    shaped = _shape_comment(root, file_key, slug=slug, anchor=anchor)
    shaped["replies"] = []
    return shaped


def _shape_comment(c: dict, file_key: str, *, slug: str, anchor: dict | None = None) -> dict:
    user = c.get("user") or {}
    out = {
        "id": c.get("id"),
        "file_key": file_key,
        "message": c.get("message"),
        "author": {"handle": user.get("handle"), "id": user.get("id")},
        "created_at": c.get("created_at"),
        "resolved": bool(c.get("resolved_at")),
        "resolved_at": c.get("resolved_at"),
        "parent_id": c.get("parent_id") or None,
        "_url": c.get("_url"),
    }
    if anchor is not None:
        out["anchor"] = anchor
    return out


def _anchor(c: dict, file_key: str, *, slug: str) -> dict:
    cm = c.get("client_meta") or {}
    if isinstance(cm, dict):
        nid = cm.get("node_id")
        if nid:
            store = refs.load()
            node_meta = (store.get("nodes") or {}).get(f"{file_key}:{nid}") or {}
            return {
                "node_id": nid,
                "node_offset": cm.get("node_offset"),
                "node_name": node_meta.get("name"),
                "_url": urls.deeplink(file_key, nid, slug=slug),
            }
        if "x" in cm or "y" in cm:
            return {"canvas": {"x": cm.get("x"), "y": cm.get("y")}}
    return {}


# ---------------- state: last listed file ----------------


def _state_path() -> pathlib.Path:
    return refs.skill_dir() / "comments-state.json"


def _record_last_file(file_key: str) -> None:
    try:
        _state_path().write_text(
            _json.dumps({"last_file_key": file_key}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass  # non-fatal; reply/resolve can still use --file explicitly.


def _resolve_file_key(file_url: str | None) -> str:
    if file_url:
        parsed = urls.parse(file_url)
        if parsed.file_key:
            return parsed.file_key
        output.die(f"--file URL did not contain a file key: {file_url}")
    state_path = _state_path()
    if state_path.exists():
        try:
            data: dict[str, Any] = _json.loads(state_path.read_text(encoding="utf-8"))
            fk = data.get("last_file_key")
            if fk:
                return str(fk)
        except (OSError, _json.JSONDecodeError):
            pass
    output.die(
        "file_key required. Either pass --file <file-url>, or run `figma comments list <file-url>` first.",
    )
