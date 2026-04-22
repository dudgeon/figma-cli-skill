# Troubleshooting

## `FIGMA_TOKEN is not set`

Generate one at **Figma → Settings → Security → Personal access tokens**, then:

```bash
export FIGMA_TOKEN=figd_...
# Persist to your shell profile (.zshrc / .bashrc) so Claude Code sees it
# across sessions.
```

Required scopes on the token (when prompted):

- **File content**: read (everything in Tier 1–4 needs this)
- **Comments**: read and write
- **Variables**: read (Enterprise only; enables richer Tier 3 annotations)
- **Library content**: read (helps with external component resolution)

## 401 Unauthorized

The token is expired or malformed. Regenerate in Figma settings, then
re-export. Tokens are prefixed `figd_`; anything else is wrong.

## 403 Forbidden

Several causes:

1. **File is not shared with the token owner.** PAT requests run as the
   user who created the token. Make sure that user has (at minimum) view
   access to the file. For team/org-wide files, check that the user is
   a member of the team.

2. **Endpoint requires Enterprise.** `/v1/files/:key/variables/local`
   and some library endpoints are Enterprise-only. The CLI degrades
   gracefully: Tier 3 still produces `tree.json`, just without variable
   name annotations (the manifest reports
   `variables_source: "unavailable"`).

3. **Token lacks a required scope.** Regenerate the token and ensure the
   relevant scopes are granted.

## 404 Not Found

- **Wrong file_key.** The key is the path segment after `/design/` or
  `/file/` in a Figma URL. Case-sensitive.
- **Wrong node_id.** URLs use `12-34`, the API uses `12:34`. The CLI
  handles this conversion automatically, but copy the full URL from
  Figma's "Copy link" menu rather than hand-editing it.
- **File/node was deleted.** Figma doesn't distinguish from "not found"
  at the API level.

## 429 Rate limited

The CLI retries automatically with exponential backoff (2s/4s/8s/16s),
honoring any `Retry-After` header. If you're consistently hitting this
on a single file, you're probably fetching nodes in a tight loop — prefer
Tier 1 (`file summary`) or Tier 2 (`file page`) before falling back on
many Tier 3 calls.

## Comments resolve returns 404/405

The resolve endpoint (`POST /v1/files/:key/comments/:id/resolve`) isn't
documented on every Figma plan. If the CLI gets 404/405 here, resolving
a thread via the REST API isn't available for that file; use Figma's UI
to resolve manually. `list`, `reply`, and `create` still work in all
cases.

## Variables annotations are missing in `tree.json`

Check the manifest:

```
"variables_source": "unavailable"
```

That means `/v1/files/:key/variables/local` returned 403 (typically
non-Enterprise) or 404. The `tree.json` is otherwise complete and usable;
concrete colors, sizes, and other resolved values are all present in
the native fields.

## `image_refs` in the manifest but no `fills/` directory

`figma node read` *detects* image-fill references but doesn't download
the bytes by default. Run:

```bash
figma node assets <node-url>
```

to download them into `.figma-cache/<file>/<node>/fills/`.

## Render fails with `err` set

Figma's render API can fail for very large or nested selections.
Workarounds:

- Drop scale: `--scale 1`
- Skip SVG: `--no-svg`
- Render a smaller subtree by picking a specific child node

## `.figma-cache/` grows huge

It's project-local and gitignored by default (the skill's `.gitignore`
covers it). If you need to reclaim space:

```bash
rm -rf .figma-cache/
```

Nothing in `refs.json` depends on the cache; the next `node read` call
rebuilds what it needs.

## `refs.json` got corrupted

The CLI handles corrupted JSON by reseting to an empty ref file on the
next load. If you want to nuke it manually:

```bash
rm ~/.claude/skills/figma/refs.json
```

Nothing downstream breaks; the ref file is a cache, not a source of truth.

## Network errors

After 4 retries with exponential backoff, the CLI emits:

```json
{ "error": "Network error after retries: <reason>", "url": "…" }
```

If this persists:

- Check that `api.figma.com` is reachable from your machine.
- Corporate VPN / proxy can block outbound HTTPS. Try
  `curl -I https://api.figma.com/v1/me -H "X-Figma-Token: $FIGMA_TOKEN"`
  to confirm.

## Python errors

The skill requires Python 3.11+. Check with `python3 --version`. If
you're on macOS and `python3` points at an older version, use
`python3.11` explicitly or upgrade via Homebrew.
