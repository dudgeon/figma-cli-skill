"""Offline tests for the Tier 3 (node read) annotation logic.

All tests are pure (no network): we call the in-module helpers with
hand-built subtrees and variable maps, and for the end-to-end test we
monkeypatch http.request and the image downloader.
"""
from __future__ import annotations

import json

import pytest
from figma_pat.render import image_fills
from figma_pat.tiers import node_full

# ---------------- pure helpers ----------------


def test_build_variable_lookup():
    meta = {
        "_available": True,
        "variables": {
            "VariableID:1/2": {
                "id": "VariableID:1/2",
                "name": "color/brand/primary",
                "resolvedType": "COLOR",
                "variableCollectionId": "VariableCollectionId:9/9",
            }
        },
        "collections": {
            "VariableCollectionId:9/9": {"id": "VariableCollectionId:9/9", "name": "Brand"},
        },
    }
    lookup = node_full._build_variable_lookup(meta)
    assert lookup["VariableID:1/2"]["name"] == "color/brand/primary"
    assert lookup["VariableID:1/2"]["collection_name"] == "Brand"
    assert lookup["VariableID:1/2"]["resolvedType"] == "COLOR"


def test_annotate_bound_variables_attaches_names():
    bv = {
        "fills": [{"type": "VARIABLE_ALIAS", "id": "VariableID:1/2"}],
        "nested": {
            "type": "VARIABLE_ALIAS",
            "id": "VariableID:1/2",
        },
    }
    lookup = {
        "VariableID:1/2": {
            "name": "color/brand/primary",
            "collection_name": "Brand",
            "resolvedType": "COLOR",
        }
    }
    node_full._annotate_bound_variables(bv, lookup)
    assert bv["fills"][0]["_name"] == "color/brand/primary"
    assert bv["fills"][0]["_collection"] == "Brand"
    assert bv["fills"][0]["_resolvedType"] == "COLOR"
    assert bv["nested"]["_name"] == "color/brand/primary"


def test_collect_instance_component_ids():
    tree = {
        "id": "0:1",
        "type": "FRAME",
        "children": [
            {"id": "1:1", "type": "INSTANCE", "componentId": "C:1"},
            {"id": "1:2", "type": "TEXT"},
            {
                "id": "1:3",
                "type": "FRAME",
                "children": [
                    {"id": "1:4", "type": "INSTANCE", "componentId": "C:2"},
                    {"id": "1:5", "type": "INSTANCE", "componentId": "C:1"},  # dup
                ],
            },
        ],
    }
    assert node_full._collect_instance_component_ids(tree) == {"C:1", "C:2"}


def test_compute_stats():
    tree = {
        "id": "0:1",
        "type": "FRAME",
        "children": [
            {"id": "1:1", "type": "TEXT"},
            {"id": "1:2", "type": "INSTANCE"},
            {"id": "1:3", "type": "COMPONENT", "children": [{"id": "1:4", "type": "TEXT"}]},
        ],
    }
    stats = node_full._compute_stats(tree)
    assert stats == {"nodes": 5, "text_nodes": 2, "instances": 1, "components": 1, "frames": 1}


def test_used_variables_only_returns_referenced():
    tree = {
        "id": "0:1",
        "type": "FRAME",
        "boundVariables": {
            "fills": [{"type": "VARIABLE_ALIAS", "id": "VariableID:1/2"}],
        },
        "children": [],
    }
    meta = {
        "_available": True,
        "variables": {
            "VariableID:1/2": {"id": "VariableID:1/2", "name": "brand/primary", "variableCollectionId": "C:1"},
            "VariableID:9/9": {"id": "VariableID:9/9", "name": "unused", "variableCollectionId": "C:1"},
        },
        "collections": {
            "C:1": {"id": "C:1", "name": "Brand"},
            "C:2": {"id": "C:2", "name": "Unused"},
        },
    }
    used = node_full._used_variables(meta, tree)
    assert set(used["variables"].keys()) == {"VariableID:1/2"}
    assert set(used["collections"].keys()) == {"C:1"}


def test_used_variables_unavailable_returns_empty():
    meta = {"_available": False, "variables": {}, "collections": {}}
    used = node_full._used_variables(meta, {"children": []})
    assert used["_available"] is False
    assert used["variables"] == {}


def test_image_fills_collect_refs():
    tree = {
        "id": "0:1",
        "fills": [
            {"type": "SOLID", "color": {"r": 1, "g": 0, "b": 0}},
            {"type": "IMAGE", "imageRef": "ref1"},
        ],
        "children": [
            {
                "id": "1:1",
                "strokes": [{"type": "IMAGE", "imageRef": "ref2"}],
                "fills": [{"type": "IMAGE", "imageRef": "ref1"}],  # dup
            }
        ],
    }
    assert image_fills.collect_refs(tree) == {"ref1", "ref2"}


# ---------------- end-to-end with mocks ----------------


@pytest.fixture
def mocked_http(monkeypatch):
    """Monkeypatch http.request to return canned responses."""
    responses: dict[str, object] = {}

    def fake_request(method, path, *, params=None, body=None, **kw):
        from figma_pat import http

        key = f"{method.upper()} {path} {sorted((params or {}).items())}"
        if key not in responses:
            # Also try without params for flexibility.
            generic = f"{method.upper()} {path}"
            if generic in responses:
                return http.Response(status=200, data=responses[generic], headers={}, url=path)
            raise AssertionError(f"unexpected request: {key}")
        return http.Response(status=200, data=responses[key], headers={}, url=path)

    monkeypatch.setattr("figma_pat.http.request", fake_request)
    return responses


@pytest.fixture
def no_download(monkeypatch, tmp_path):
    def fake_download(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)  # just enough to "exist"
        return 40

    monkeypatch.setattr("figma_pat.render.images.download", fake_download)
    return fake_download


def test_generate_end_to_end(tmp_path, monkeypatch, mocked_http, no_download):
    monkeypatch.setenv("FIGMA_TOKEN", "figd_test")
    monkeypatch.setenv("FIGMA_SKILL_DIR", str(tmp_path / "skill"))
    monkeypatch.setenv("FIGMA_CACHE_ROOT", str(tmp_path / "cache"))

    file_key = "FILE1"
    node_id = "10:20"

    # Primary subtree fetch
    subtree = {
        "id": node_id,
        "name": "Checkout / Payment",
        "type": "FRAME",
        "boundVariables": {
            "fills": [{"type": "VARIABLE_ALIAS", "id": "VariableID:1/2"}],
        },
        "styles": {"fill": "S:1"},
        "fills": [{"type": "IMAGE", "imageRef": "ref1"}],
        "children": [
            {
                "id": "10:21",
                "type": "INSTANCE",
                "componentId": "C:1",
                "name": "Button",
                "children": [],
            },
            {"id": "10:22", "type": "TEXT", "characters": "Pay $12.99", "children": []},
        ],
    }

    mocked_http["GET /v1/files/FILE1/nodes [('geometry', 'paths'), ('ids', '10:20')]"] = {
        "nodes": {
            node_id: {
                "document": subtree,
                "components": {
                    "C:1": {"name": "Primary Button", "description": "CTA", "key": "comp-key-1"},
                },
                "componentSets": {},
                "styles": {"S:1": {"name": "bg/card", "styleType": "FILL"}},
            }
        }
    }

    # Variables fetch
    mocked_http["GET /v1/files/FILE1/variables/local []"] = {
        "meta": {
            "variables": {
                "VariableID:1/2": {
                    "id": "VariableID:1/2",
                    "name": "color/brand/primary",
                    "resolvedType": "COLOR",
                    "variableCollectionId": "VC:1",
                }
            },
            "variableCollections": {"VC:1": {"id": "VC:1", "name": "Brand"}},
        }
    }

    # Components fetch (batched by id)
    mocked_http["GET /v1/files/FILE1/nodes [('geometry', 'paths'), ('ids', ['C:1'])]"] = {
        "nodes": {
            "C:1": {
                "document": {"id": "C:1", "name": "Primary Button", "type": "COMPONENT", "children": []},
            }
        }
    }

    # Render URLs
    mocked_http["GET /v1/images/FILE1 [('format', 'png'), ('ids', ['10:20']), ('scale', 2)]"] = {
        "err": None, "images": {node_id: "https://s3/png"}
    }
    mocked_http["GET /v1/images/FILE1 [('format', 'svg'), ('ids', ['10:20']), ('svg_outline_text', 'true')]"] = {
        "err": None, "images": {node_id: "https://s3/svg"}
    }

    manifest = node_full.generate(file_key, node_id, slug="Checkout")

    # Manifest shape
    assert manifest["file_key"] == file_key
    assert manifest["node_id"] == node_id
    assert manifest["name"] == "Checkout / Payment"
    assert manifest["type"] == "FRAME"
    assert manifest["url"].endswith("node-id=10-20")
    assert manifest["variables_source"] == "enterprise_api"
    assert manifest["outputs"]["tree"].endswith("tree.json")
    assert manifest["outputs"]["png"].endswith("render@2x.png")
    assert manifest["outputs"]["svg"].endswith("render.svg")
    assert manifest["outputs"]["variables_used"].endswith("variables.json")
    assert manifest["outputs"]["components_inlined"].endswith("components.json")
    assert manifest["stats"]["instances"] == 1
    assert manifest["stats"]["text_nodes"] == 1
    assert "ref1" in manifest["image_refs"]

    # Written tree has annotations
    tree_data = json.loads((tmp_path / "cache" / file_key / "10-20" / "tree.json").read_text())
    assert tree_data["_url"].endswith("node-id=10-20")
    assert tree_data["boundVariables"]["fills"][0]["_name"] == "color/brand/primary"
    assert tree_data["boundVariables"]["fills"][0]["_collection"] == "Brand"
    assert tree_data["_styles"]["fill"]["name"] == "bg/card"

    # INSTANCE inlining
    instance = tree_data["children"][0]
    assert instance["_componentMain"]["inlined"] is True
    assert instance["_componentMain"]["name"] == "Primary Button"
    assert instance["_componentMain"]["body"]["type"] == "COMPONENT"

    # Variables file only includes referenced vars
    used = json.loads((tmp_path / "cache" / file_key / "10-20" / "variables.json").read_text())
    assert set(used["variables"].keys()) == {"VariableID:1/2"}
