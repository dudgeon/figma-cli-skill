"""Project-local cache for Tier 3/4 artifacts.

Layout:
    $CLAUDE_PROJECT_DIR/.figma-cache/<file_key>/<node_id_fs_safe>/
        tree.json
        render@2x.png
        render.svg
        variables.json
        components.json
        fills/<fill_id>.<ext>

If CLAUDE_PROJECT_DIR isn't set, we fall back to the current working
directory. Tests can override via FIGMA_CACHE_ROOT.
"""
from __future__ import annotations

import os
import pathlib

from .urls import node_id_filesystem_safe


def cache_root() -> pathlib.Path:
    env = os.environ.get("FIGMA_CACHE_ROOT")
    if env:
        return pathlib.Path(env).resolve()
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return pathlib.Path(project).resolve() / ".figma-cache"


def node_dir(file_key: str, node_id: str) -> pathlib.Path:
    return cache_root() / file_key / node_id_filesystem_safe(node_id)


def ensure_node_dir(file_key: str, node_id: str) -> pathlib.Path:
    d = node_dir(file_key, node_id)
    d.mkdir(parents=True, exist_ok=True)
    return d
