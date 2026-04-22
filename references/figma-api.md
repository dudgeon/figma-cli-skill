# Figma REST API endpoints

Docs root: https://www.figma.com/developers/api

Every endpoint the CLI calls, and which module hits it.

## Users

| Endpoint | Used by | Figma docs |
|---|---|---|
| `GET /v1/me` | `figma whoami` (`commands/whoami.py`) | https://www.figma.com/developers/api#get-me-endpoint |

## Files

| Endpoint | Used by | Figma docs |
|---|---|---|
| `GET /v1/files/:file_key` | `tiers/summary.py` (`depth=2`), `tiers/page_index.py` (`depth=1` to find first page) | https://www.figma.com/developers/api#get-files-endpoint |
| `GET /v1/files/:file_key/nodes` | `tiers/page_index.py` (`depth=3`), `tiers/node_full.py` (`geometry=paths`), `tiers/node_full.py` again for batched component inlining | https://www.figma.com/developers/api#get-file-nodes-endpoint |
| `GET /v1/files/:file_key/images` | `render/image_fills.py` | https://www.figma.com/developers/api#get-image-fills-endpoint |

## Variables (Enterprise)

| Endpoint | Used by | Figma docs |
|---|---|---|
| `GET /v1/files/:file_key/variables/local` | `tiers/node_full.py` (annotation) | https://www.figma.com/developers/api#get-local-variables-endpoint |

The CLI tolerates 403/404 here — variables annotation is a nice-to-have, not a hard requirement. When unavailable, Tier 3 sets `variables_source: "unavailable"` in the manifest.

## Images (rendering)

| Endpoint | Used by | Figma docs |
|---|---|---|
| `GET /v1/images/:file_key` | `render/images.py` (PNG/SVG/PDF/JPG render URLs) | https://www.figma.com/developers/api#get-images-endpoint |

Returns `{"images": {"<node_id>": "https://s3.../pre-signed"}}`. The CLI downloads each URL directly (no auth header on the CDN URL).

## Comments

| Endpoint | Used by | Figma docs |
|---|---|---|
| `GET /v1/files/:file_key/comments` | `commands/comments.py run_list` | https://www.figma.com/developers/api#get-comments-endpoint |
| `POST /v1/files/:file_key/comments` | `commands/comments.py run_reply`, `run_create` | https://www.figma.com/developers/api#post-comments-endpoint |
| `POST /v1/files/:file_key/comments/:id/resolve` | `commands/comments.py run_resolve` | (extended; undocumented on some plans — CLI degrades to a hint) |
| `DELETE /v1/files/:file_key/comments/:id` | (reserved) | https://www.figma.com/developers/api#delete-comments-endpoint |

## Rate limits

Figma's REST API returns 429 with a `Retry-After` header. `http.py` honors that header when present, and otherwise applies exponential backoff at 2s / 4s / 8s / 16s. 5xx errors and network errors use the same schedule. After 4 retries the CLI emits a structured error and exits non-zero.

## Authentication

All requests send `X-Figma-Token: $FIGMA_TOKEN`. No OAuth. Token scope requirements on Enterprise vary by endpoint; see [troubleshooting.md](troubleshooting.md#403-permissions).
