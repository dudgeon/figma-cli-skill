---
name: figma
description: Read Figma mocks with full fidelity and manage Figma comments via the REST API. Use when a user pastes a figma.com/file, figma.com/design, figma.com/proto, or figma.com/board URL and asks to build, pull, read, or implement a mock; also for listing, replying to, creating, or resolving Figma comments.
when_to_use: User pastes a figma.com URL and says "build this", "pull this mock", "implement this design", "read this Figma", "check the comments", "reply to the Figma comment", "resolve this comment".
allowed-tools: Bash
---

# figma

Use the bundled CLI at `${CLAUDE_SKILL_DIR}/scripts/figma` for every Figma operation. Never hand-craft Figma API URLs — the CLI owns auth, URL parsing, the ref file, retries, and the cache layout.

## Environment check
Token status: !`[ -n "$FIGMA_TOKEN" ] && echo present || echo MISSING`

If MISSING, tell the user to `export FIGMA_TOKEN=figd_...` and stop. Don't try to run any command without the token.

## Routing by intent

### "Pull / build / read this mock" (URL points at a file or node)

Progressive disclosure — always start at the lowest tier that answers the question. Don't jump straight to Tier 3 for an unfamiliar file.

1. `${CLAUDE_SKILL_DIR}/scripts/figma resolve <url>` — classify the URL (team / project / file / node)
2. `${CLAUDE_SKILL_DIR}/scripts/figma file summary <url>` — pages + top-level frames (~1–5 KB)
3. `${CLAUDE_SKILL_DIR}/scripts/figma file page <url>` — frame list for one page (~10–50 KB); pass `--page-id` to pick a page other than the first
4. `${CLAUDE_SKILL_DIR}/scripts/figma node read <node-url>` — lossless payload written to `.figma-cache/`; manifest JSON on stdout lists the tree, PNG@2x, SVG, variables, components
5. `${CLAUDE_SKILL_DIR}/scripts/figma node assets <node-url>` — only when image-fill bytes or export-ready assets are actually needed

After `node read`, open `tree.json` and `render@2x.png` from the manifest. Every node in the tree carries `_url` — use it to cross-reference nodes in generated code.

### Comments

- `${CLAUDE_SKILL_DIR}/scripts/figma comments list <file-url> [--unresolved] [--node <node-id>] [--author <handle>]`
- `${CLAUDE_SKILL_DIR}/scripts/figma comments reply <comment-id> "<text>"`
- `${CLAUDE_SKILL_DIR}/scripts/figma comments create <node-url> "<text>"` — anchors the comment to the node in the URL
- `${CLAUDE_SKILL_DIR}/scripts/figma comments resolve <comment-id>`

When summarizing a thread, always include the anchor node's name and `_url` so the user can jump straight to it in Figma.

### Ref file

The CLI persists every team / project / file / node it touches to `${CLAUDE_SKILL_DIR}/refs.json`. Use `${CLAUDE_SKILL_DIR}/scripts/figma refs list` and `refs show <url-or-id>` to browse what's been seen before — useful when the user says "that mock I showed you last week."

## References (load on demand)

- `${CLAUDE_SKILL_DIR}/references/figma-api.md` — endpoint map with Figma REST docs links
- `${CLAUDE_SKILL_DIR}/references/tier-3-contract.md` — exact `tree.json` shape: variable annotation format, component inlining rules, text handling
- `${CLAUDE_SKILL_DIR}/references/comments-workflow.md` — formatting conventions, reply etiquette, node attribution
- `${CLAUDE_SKILL_DIR}/references/troubleshooting.md` — 403/404 hints, rate-limit behavior, token issues

## Output conventions

- CLI emits JSON on stdout, human hints on stderr. Parse stdout.
- Errors: `{"error": "...", "hint": "...", "url": "..."}` on stderr, non-zero exit.
- All commands accept `--json` (default) and `--quiet` (suppress stderr hints).
