"""Parse and construct Figma URLs.

Figma URL shapes supported:
  - figma.com/file/<key>/<slug>[?node-id=12-34]
  - figma.com/design/<key>/<slug>[?node-id=12-34]
  - figma.com/proto/<key>/<slug>[?node-id=12-34]
  - figma.com/board/<key>/<slug>[?node-id=12-34]            (FigJam)
  - figma.com/files/team/<team_id>[/<slug>]
  - figma.com/files/project/<project_id>[/<slug>]

URL node-ids use `-` as a separator (e.g. 12-34). The REST API uses `:`
(e.g. 12:34). Everywhere inside this codebase we use the API form.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlparse

UrlKind = Literal["file", "node", "team", "project", "unknown"]


@dataclass(frozen=True)
class ParsedFigmaUrl:
    kind: UrlKind
    raw: str
    file_key: str | None = None
    node_id: str | None = None  # API form, e.g. "12:34"
    team_id: str | None = None
    project_id: str | None = None
    slug: str | None = None

    def to_dict(self) -> dict:
        d = {
            "kind": self.kind,
            "url": self.raw,
        }
        for k in ("file_key", "node_id", "team_id", "project_id", "slug"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


_FILE_PATH_RE = re.compile(r"^/(file|design|proto|board)/([A-Za-z0-9]+)(?:/([^/?#]+))?/?$")
_TEAM_PATH_RE = re.compile(r"^/files/team/(\d+)(?:/([^/?#]+))?/?$")
_PROJECT_PATH_RE = re.compile(r"^/files/project/(\d+)(?:/([^/?#]+))?/?$")


def _node_id_from_query(query: str) -> str | None:
    if not query:
        return None
    qs = parse_qs(query)
    raw = qs.get("node-id", [None])[0] or qs.get("node_id", [None])[0]
    if not raw:
        return None
    # URL form 12-34 -> API form 12:34
    return raw.replace("-", ":")


def parse(url: str) -> ParsedFigmaUrl:
    """Parse a Figma URL. Returns ParsedFigmaUrl; kind='unknown' if unrecognized."""
    raw = url.strip()
    if not raw:
        return ParsedFigmaUrl(kind="unknown", raw=raw)

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower()
    if not (host == "figma.com" or host.endswith(".figma.com")):
        return ParsedFigmaUrl(kind="unknown", raw=raw)

    path = parsed.path or "/"

    m = _FILE_PATH_RE.match(path)
    if m:
        _, key, slug = m.groups()
        node_id = _node_id_from_query(parsed.query)
        return ParsedFigmaUrl(
            kind="node" if node_id else "file",
            raw=raw,
            file_key=key,
            node_id=node_id,
            slug=slug,
        )

    m = _TEAM_PATH_RE.match(path)
    if m:
        team_id, slug = m.groups()
        return ParsedFigmaUrl(kind="team", raw=raw, team_id=team_id, slug=slug)

    m = _PROJECT_PATH_RE.match(path)
    if m:
        project_id, slug = m.groups()
        return ParsedFigmaUrl(kind="project", raw=raw, project_id=project_id, slug=slug)

    return ParsedFigmaUrl(kind="unknown", raw=raw)


def deeplink(file_key: str, node_id: str | None = None, slug: str = "") -> str:
    """Build a figma.com deep link. Node IDs are emitted in URL form (12-34)."""
    base = f"https://www.figma.com/design/{file_key}"
    if slug:
        base = f"{base}/{slug}"
    if node_id:
        base = f"{base}?node-id={node_id.replace(':', '-')}"
    return base


def node_id_to_url_form(node_id: str) -> str:
    """Convert API node id '12:34' to URL form '12-34'."""
    return node_id.replace(":", "-")


def node_id_to_api_form(node_id: str) -> str:
    """Convert URL node id '12-34' to API form '12:34'. Idempotent."""
    return node_id.replace("-", ":")


def node_id_filesystem_safe(node_id: str) -> str:
    """Filesystem-safe form for cache paths: '12:34' -> '12-34'."""
    return node_id.replace(":", "-")
