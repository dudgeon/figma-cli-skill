"""Tier 3 — lossless node payload.

Pulls a node subtree, resolves variables and styles, inlines local
components with overrides, renders PNG@<scale>x + SVG, and downloads
image-fill bytes referenced inside the subtree.

Endpoints used:
  GET /v1/files/:key/nodes?ids=<id>&geometry=paths
      https://www.figma.com/developers/api#get-file-nodes-endpoint
  GET /v1/files/:key/variables/local       (Enterprise; optional)
      https://www.figma.com/developers/api#get-local-variables-endpoint
  GET /v1/images/:key                      (rendering URLs)
  GET /v1/files/:key/images                (image-fill bytes)
"""
from __future__ import annotations

import json
from typing import Any

from .. import cache, http, output, refs, urls
from ..render import image_fills, images


def generate(
    file_key: str,
    node_id: str,
    *,
    slug: str | None = None,
    scale: int = 2,
    include_svg: bool = True,
    depth: int | None = None,
    download_image_fills: bool = False,
) -> dict[str, Any]:
    # 1) Subtree
    params: dict[str, Any] = {"ids": node_id, "geometry": "paths"}
    if depth is not None:
        params["depth"] = depth
    node_resp = http.get(f"/v1/files/{file_key}/nodes", params=params)
    envelope = (node_resp.get("nodes") or {}).get(node_id)
    if not envelope or not envelope.get("document"):
        output.die(
            f"Node {node_id} not found in file {file_key}",
            hint_text="The node id may have been deleted, moved, or typoed. Double-check the URL.",
        )
    subtree = envelope["document"]
    file_components_meta: dict[str, Any] = envelope.get("components") or {}
    file_component_sets_meta: dict[str, Any] = envelope.get("componentSets") or {}
    file_styles_meta: dict[str, Any] = envelope.get("styles") or {}

    # 2) Variables (optional; 403 on non-Enterprise)
    variables_meta = _fetch_variables(file_key)

    # 3) Components: inline main bodies for every INSTANCE in the subtree.
    instance_component_ids = _collect_instance_component_ids(subtree)
    main_components = _fetch_components(file_key, instance_component_ids)

    # 4) Render PNG + SVG URLs
    png_map = images.render_urls(file_key, [node_id], fmt="png", scale=scale)
    svg_map = images.render_urls(file_key, [node_id], fmt="svg") if include_svg else {}

    # 5) Annotate the tree in place: _url, _boundVariables, _componentMain, _style
    _annotate_tree(
        subtree,
        file_key=file_key,
        slug=slug or "",
        variables_meta=variables_meta,
        components_meta=file_components_meta,
        component_sets_meta=file_component_sets_meta,
        styles_meta=file_styles_meta,
        main_components=main_components,
    )

    # 6) Write artifacts to cache
    cache_dir = cache.ensure_node_dir(file_key, node_id)
    tree_path = cache_dir / "tree.json"
    tree_path.write_text(json.dumps(subtree, indent=2, ensure_ascii=False), encoding="utf-8")

    png_path = cache_dir / f"render@{scale}x.png"
    if node_id in png_map:
        images.download(png_map[node_id], png_path)

    svg_path = cache_dir / "render.svg"
    if include_svg and node_id in svg_map:
        images.download(svg_map[node_id], svg_path)

    variables_path = cache_dir / "variables.json"
    used_vars = _used_variables(variables_meta, subtree)
    variables_path.write_text(json.dumps(used_vars, indent=2, ensure_ascii=False), encoding="utf-8")

    components_path = cache_dir / "components.json"
    components_path.write_text(
        json.dumps(
            {
                "metadata": file_components_meta,
                "component_sets": file_component_sets_meta,
                "inlined_main": main_components,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 7) Image fills — only download on demand to keep Tier 3 fast.
    fills_dir = cache_dir / "fills"
    fills_downloaded: dict[str, str] = {}
    image_refs = image_fills.collect_refs(subtree)
    if download_image_fills and image_refs:
        fills_downloaded = image_fills.download_all(file_key, image_refs, fills_dir)

    # 8) Update refs
    _update_refs(file_key, node_id, subtree, source_url=urls.deeplink(file_key, node_id, slug=slug or ""))

    # 9) Manifest
    stats = _compute_stats(subtree)
    return {
        "file_key": file_key,
        "node_id": node_id,
        "name": subtree.get("name"),
        "type": subtree.get("type"),
        "url": urls.deeplink(file_key, node_id, slug=slug or ""),
        "outputs": {
            "tree": str(tree_path),
            "png": str(png_path) if png_path.exists() else None,
            "svg": str(svg_path) if include_svg and svg_path.exists() else None,
            "variables_used": str(variables_path),
            "components_inlined": str(components_path),
            "fills": str(fills_dir) if fills_downloaded else None,
        },
        "stats": stats,
        "image_refs": sorted(image_refs),
        "variables_source": (
            "enterprise_api" if variables_meta.get("_available") else "unavailable"
        ),
    }


# ---------------- helpers ----------------


def _fetch_variables(file_key: str) -> dict[str, Any]:
    """Best-effort fetch of local variables. On 403/404 returns an empty map."""
    try:
        data = http.get(f"/v1/files/{file_key}/variables/local")
    except http.FigmaHttpError as e:
        if e.status in (403, 404):
            output.hint(
                f"variables/local returned {e.status}; skipping variable name annotation "
                "(Enterprise plan + Variables scope is required for rich annotations)."
            )
            return {"_available": False, "variables": {}, "collections": {}}
        raise
    meta = data.get("meta") or {}
    return {
        "_available": True,
        "variables": meta.get("variables") or {},
        "collections": meta.get("variableCollections") or {},
    }


def _collect_instance_component_ids(node: dict) -> set[str]:
    out: set[str] = set()

    def visit(n: dict) -> None:
        if n.get("type") == "INSTANCE":
            cid = n.get("componentId")
            if cid:
                out.add(cid)
        for child in n.get("children") or []:
            visit(child)

    visit(node)
    return out


def _fetch_components(file_key: str, component_ids: set[str]) -> dict[str, dict]:
    """Batch-fetch component subtrees by node id. External/library components
    whose node is outside this file will be missing from the result."""
    if not component_ids:
        return {}
    ids = sorted(component_ids)
    try:
        data = http.get(f"/v1/files/{file_key}/nodes", params={"ids": ids, "geometry": "paths"})
    except http.FigmaHttpError as e:
        if e.status == 404:
            output.hint(f"components fetch 404 for {len(ids)} id(s); they may be external.")
            return {}
        raise
    out: dict[str, dict] = {}
    for cid, envelope in (data.get("nodes") or {}).items():
        doc = envelope.get("document") if isinstance(envelope, dict) else None
        if doc:
            out[cid] = doc
    return out


def _annotate_tree(
    node: dict,
    *,
    file_key: str,
    slug: str,
    variables_meta: dict,
    components_meta: dict,
    component_sets_meta: dict,
    styles_meta: dict,
    main_components: dict,
) -> None:
    var_lookup = _build_variable_lookup(variables_meta)

    def visit(n: dict) -> None:
        n["_url"] = urls.deeplink(file_key, n["id"], slug=slug)

        # Annotate boundVariables with human-readable names.
        bv = n.get("boundVariables")
        if isinstance(bv, dict) and var_lookup:
            _annotate_bound_variables(bv, var_lookup)

        # Annotate styles references (fill/stroke/text/effect/grid) with names.
        styles = n.get("styles")
        if isinstance(styles, dict) and styles_meta:
            n["_styles"] = {
                prop: _style_entry(styles_meta.get(style_id), style_id)
                for prop, style_id in styles.items()
            }

        # Inline the main component body and metadata for INSTANCE nodes.
        if n.get("type") == "INSTANCE":
            cid = n.get("componentId")
            if cid:
                meta = components_meta.get(cid) or {}
                main = main_components.get(cid)
                n["_componentMain"] = {
                    "id": cid,
                    "name": meta.get("name"),
                    "description": meta.get("description"),
                    "key": meta.get("key"),
                    "componentSetId": meta.get("componentSetId"),
                    "inlined": main is not None,
                }
                if main is not None:
                    n["_componentMain"]["body"] = main
                # componentSet metadata
                set_id = meta.get("componentSetId")
                if set_id:
                    set_meta = component_sets_meta.get(set_id) or {}
                    n["_componentMain"]["set_name"] = set_meta.get("name")

        for child in n.get("children") or []:
            visit(child)

    visit(node)


def _build_variable_lookup(variables_meta: dict) -> dict[str, dict]:
    variables = variables_meta.get("variables") or {}
    collections = variables_meta.get("collections") or {}
    out: dict[str, dict] = {}
    for var_id, var in variables.items():
        coll_id = var.get("variableCollectionId")
        coll = collections.get(coll_id) or {}
        out[var_id] = {
            "id": var_id,
            "name": var.get("name"),
            "resolvedType": var.get("resolvedType"),
            "collection_id": coll_id,
            "collection_name": coll.get("name"),
        }
    return out


def _annotate_bound_variables(bv: dict, lookup: dict[str, dict]) -> None:
    """Walk boundVariables tree and attach _name / _collection to each alias."""
    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if obj.get("type") == "VARIABLE_ALIAS" and "id" in obj:
                meta = lookup.get(obj["id"])
                if meta:
                    obj["_name"] = meta["name"]
                    obj["_collection"] = meta["collection_name"]
                    obj["_resolvedType"] = meta["resolvedType"]
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(bv)


def _style_entry(style_meta: dict | None, style_id: str) -> dict:
    if not style_meta:
        return {"id": style_id}
    return {
        "id": style_id,
        "name": style_meta.get("name"),
        "styleType": style_meta.get("styleType"),
        "description": style_meta.get("description"),
        "key": style_meta.get("key"),
    }


def _used_variables(variables_meta: dict, tree: dict) -> dict:
    """Return variables referenced anywhere inside `tree`, plus their collections."""
    if not variables_meta.get("_available"):
        return {"_available": False, "variables": {}, "collections": {}}

    used_ids: set[str] = set()

    def visit(n: Any) -> None:
        if isinstance(n, dict):
            if n.get("type") == "VARIABLE_ALIAS" and "id" in n:
                used_ids.add(n["id"])
            for v in n.values():
                visit(v)
        elif isinstance(n, list):
            for item in n:
                visit(item)

    visit(tree.get("boundVariables"))
    for child in tree.get("children") or []:
        visit(child)

    all_vars = variables_meta.get("variables") or {}
    all_colls = variables_meta.get("collections") or {}
    used_vars = {vid: all_vars[vid] for vid in used_ids if vid in all_vars}
    used_coll_ids = {v.get("variableCollectionId") for v in used_vars.values() if v.get("variableCollectionId")}
    used_colls = {cid: all_colls[cid] for cid in used_coll_ids if cid in all_colls}
    return {
        "_available": True,
        "variables": used_vars,
        "collections": used_colls,
    }


def _compute_stats(tree: dict) -> dict:
    counts = {"nodes": 0, "text_nodes": 0, "instances": 0, "components": 0, "frames": 0}

    def visit(n: dict) -> None:
        counts["nodes"] += 1
        t = n.get("type")
        if t == "TEXT":
            counts["text_nodes"] += 1
        elif t == "INSTANCE":
            counts["instances"] += 1
        elif t in ("COMPONENT", "COMPONENT_SET"):
            counts["components"] += 1
        elif t == "FRAME":
            counts["frames"] += 1
        for child in n.get("children") or []:
            visit(child)

    visit(tree)
    return counts


def _update_refs(file_key: str, node_id: str, subtree: dict, *, source_url: str) -> None:
    store = refs.load()
    refs.add_node(
        store,
        file_key,
        node_id,
        name=subtree.get("name"),
        type=subtree.get("type"),
        url=source_url,
    )
    refs.save(store)
