"""Offline tests for the comments grouping + shaping logic."""
from __future__ import annotations

from figma_pat.commands import comments as c


def test_group_threads_simple():
    raw = [
        {"id": "1", "parent_id": "", "message": "hi", "user": {"handle": "alice"}, "created_at": "2026-04-01T10:00:00Z",
         "client_meta": {"node_id": "10:20", "node_offset": {"x": 0, "y": 0}}},
        {"id": "2", "parent_id": "1", "message": "reply", "user": {"handle": "bob"}, "created_at": "2026-04-01T10:05:00Z",
         "client_meta": {}},
    ]
    threads = c._group_into_threads(raw, "FILE1", slug="Checkout")
    assert len(threads) == 1
    t = threads[0]
    assert t["id"] == "1"
    assert t["author"]["handle"] == "alice"
    assert t["anchor"]["node_id"] == "10:20"
    assert t["anchor"]["_url"].endswith("node-id=10-20")
    assert len(t["replies"]) == 1
    assert t["replies"][0]["id"] == "2"
    assert t["replies"][0]["author"]["handle"] == "bob"


def test_resolved_flag_reflects_resolved_at():
    raw = [
        {"id": "1", "parent_id": "", "message": "done", "user": {"handle": "alice"},
         "created_at": "2026-04-01T10:00:00Z", "resolved_at": "2026-04-02T10:00:00Z", "client_meta": {}},
    ]
    t = c._group_into_threads(raw, "FILE1", slug="")[0]
    assert t["resolved"] is True
    assert t["resolved_at"] == "2026-04-02T10:00:00Z"


def test_anchor_canvas_comments():
    c_data = {"client_meta": {"x": 10, "y": 20}}
    anchor = c._anchor(c_data, "FILE1", slug="")
    assert anchor == {"canvas": {"x": 10, "y": 20}}


def test_anchor_no_client_meta():
    assert c._anchor({}, "FILE1", slug="") == {}


def test_reply_preserves_ordering():
    raw = [
        {"id": "1", "parent_id": "", "message": "root", "user": {"handle": "alice"},
         "created_at": "2026-04-01T10:00:00Z", "client_meta": {}},
        {"id": "3", "parent_id": "1", "message": "later", "user": {"handle": "bob"},
         "created_at": "2026-04-01T11:00:00Z", "client_meta": {}},
        {"id": "2", "parent_id": "1", "message": "earlier", "user": {"handle": "carol"},
         "created_at": "2026-04-01T10:30:00Z", "client_meta": {}},
    ]
    t = c._group_into_threads(raw, "FILE1", slug="")[0]
    assert [r["id"] for r in t["replies"]] == ["2", "3"]
