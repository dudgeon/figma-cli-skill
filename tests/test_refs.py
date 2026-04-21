from __future__ import annotations

import json

import pytest
from figma_pat import refs


@pytest.fixture
def skill_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGMA_SKILL_DIR", str(tmp_path))
    yield tmp_path


def test_empty_when_missing(skill_dir):
    data = refs.load()
    assert data["version"] == refs.SCHEMA_VERSION
    for k in ("teams", "projects", "files", "nodes"):
        assert data[k] == {}


def test_add_and_save_roundtrip(skill_dir):
    data = refs.load()
    refs.add_team(data, "team1", name="ACME", source_url="https://figma.com/files/team/team1")
    refs.add_project(data, "proj1", team_id="team1", name="Web")
    refs.add_file(data, "fileA", name="Checkout", project_id="proj1")
    refs.add_node(data, "fileA", "12:34", name="Pay", type="FRAME", page_id="0:1",
                  url="https://figma.com/design/fileA?node-id=12-34")
    refs.save(data)

    # Reload and check
    reloaded = refs.load()
    assert reloaded["teams"]["team1"]["name"] == "ACME"
    assert reloaded["projects"]["proj1"]["team_id"] == "team1"
    assert reloaded["files"]["fileA"]["name"] == "Checkout"
    assert reloaded["nodes"]["fileA:12:34"]["name"] == "Pay"


def test_add_is_idempotent(skill_dir):
    data = refs.load()
    refs.add_file(data, "fileA", name="One")
    first_seen = data["files"]["fileA"]["first_seen_at"]
    refs.add_file(data, "fileA", name="Two")
    assert data["files"]["fileA"]["name"] == "Two"
    assert data["files"]["fileA"]["first_seen_at"] == first_seen  # preserved


def test_find_filters(skill_dir):
    data = refs.load()
    refs.add_file(data, "fileA", name="Checkout Mocks")
    refs.add_file(data, "fileB", name="Admin Dashboard")
    refs.add_node(data, "fileA", "1:2", name="Payment Step")

    all_items = refs.find(data)
    assert len(all_items) == 3

    files = refs.find(data, kind="file")
    assert len(files) == 2
    assert {f["id"] for f in files} == {"fileA", "fileB"}

    grep = refs.find(data, grep="checkout")
    assert len(grep) == 1
    assert grep[0]["id"] == "fileA"


def test_forget(skill_dir):
    data = refs.load()
    refs.add_file(data, "fileA", name="One")
    assert refs.forget(data, "fileA")
    assert "fileA" not in data["files"]
    assert not refs.forget(data, "nonexistent")


def test_save_atomic_write(skill_dir):
    data = refs.load()
    refs.add_team(data, "team1")
    refs.save(data)
    assert (skill_dir / "refs.json").exists()
    with (skill_dir / "refs.json").open() as fp:
        json.load(fp)  # must be valid JSON
    # No leftover .tmp files
    tmp_files = [p for p in skill_dir.iterdir() if p.suffix == ".tmp"]
    assert tmp_files == []


def test_corrupted_file_recovers(skill_dir):
    (skill_dir / "refs.json").write_text("{not valid json", encoding="utf-8")
    data = refs.load()
    assert data["version"] == refs.SCHEMA_VERSION
    assert data["teams"] == {}
