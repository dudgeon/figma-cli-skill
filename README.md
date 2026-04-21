# figma-cli-skill

A [Claude Code Skill](https://code.claude.com/docs/en/skills) that lets Claude read Figma mocks with full fidelity and manage Figma comments, using a Figma Personal Access Token.

Python 3.11+, stdlib only, MIT licensed.

## Install

```bash
git clone https://github.com/dudgeon/figma-cli-skill ~/.claude/skills/figma
export FIGMA_TOKEN=figd_your_token_here
```

That's it. `/figma` is now a slash command in Claude Code, and Claude will auto-invoke the skill when you paste a Figma URL.

### Get a Personal Access Token

1. In Figma, go to **Settings → Security → Personal access tokens**.
2. Generate a token. The skill needs at minimum: File content (read), Comments (read/write), Variables (read), Library content (read).
3. `export FIGMA_TOKEN=figd_...` (add to your shell profile to persist).

### Narrow permissions (optional)

By default the skill's frontmatter declares `allowed-tools: Bash`, which pre-approves bash invocations while the skill is active. If you prefer a narrower rule, add this to your Claude Code settings instead and remove `allowed-tools` from `SKILL.md`:

```json
{
  "permissions": {
    "allow": ["Bash(~/.claude/skills/figma/scripts/figma:*)"]
  }
}
```

## Quickstart

Paste a Figma URL into Claude:

> Pull this mock from figma and build it: https://figma.com/design/AbCdEf123/Checkout?node-id=12-56

Claude will progressively load fidelity:

1. `figma resolve` — parse the URL
2. `figma file summary` — orient itself in the file
3. `figma node read` — pull the lossless payload (tree JSON + PNG@2x + SVG + resolved variables + inlined components)
4. Implement against `.figma-cache/<file-key>/<node-id>/tree.json` and `render@2x.png`

## Commands

All commands emit JSON on stdout. Errors go to stderr as `{"error", "hint", "url"}` with a non-zero exit code.

```
figma whoami                                     # sanity-check the token
figma resolve <url>                              # classify any Figma URL
figma refs list [--kind team|project|file|node] [--grep PATTERN]
figma refs show <url-or-id>
figma refs forget <url-or-id>

figma file summary <file-url>                    # Tier 1
figma file page <file-url> [--page-id ID]        # Tier 2

figma node read <node-url>                       # Tier 3 — the "build this" payload
    [--scale 2] [--no-svg] [--depth N]
figma node assets <node-url>                     # Tier 4 — binary assets on demand
    [--format png|svg|pdf] [--scale 1|2|3|4]

figma comments list <file-url> [--unresolved] [--node NODE_ID] [--author HANDLE]
figma comments reply <comment-id> "<text>"
figma comments create <node-url> "<text>"
figma comments resolve <comment-id>
```

## How fidelity works

`figma node read` is the core command. It writes artifacts to `$CLAUDE_PROJECT_DIR/.figma-cache/<file-key>/<node-id>/`:

| File                 | Contents                                                                                       |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| `tree.json`          | Full node subtree with every Figma-native property. Variables resolved with `boundVariable` metadata. Local components inlined with `_componentMain`. Every node has `_url`. |
| `render@2x.png`      | PNG render at 2x scale from the Figma images API.                                              |
| `render.svg`         | SVG render (unless `--no-svg`).                                                                |
| `variables.json`     | Every variable referenced by the subtree: id, name, collection, resolved values per mode.      |
| `components.json`    | Inlined main components and their overrides per instance.                                      |
| `fills/`             | Image-fill bytes if you ran `figma node assets`.                                               |

See [`references/tier-3-contract.md`](references/tier-3-contract.md) for the exact shape.

## How discovery works

Figma's REST API has no "list my teams" endpoint for PATs, so the skill is URL-driven. You paste a URL, and the skill:

1. Parses it to extract team / project / file / node IDs.
2. Fetches what's needed.
3. Appends whatever it learned (team names, project names, file names, page IDs, node names) to `refs.json` inside the skill directory.

Over time, `refs.json` becomes a searchable index of every Figma asset you've touched. `figma refs list --grep checkout` finds them again. Nothing is auto-discovered beyond what you've pointed at.

## Layout

```
figma-cli-skill/          # this repo; cloned to ~/.claude/skills/figma
├── SKILL.md              # Claude-facing entry point
├── scripts/
│   ├── figma             # CLI executable
│   └── figma_pat/        # stdlib-only Python package
├── references/           # supporting docs, loaded on demand
└── tests/
```

## Contributing

PRs welcome. The CLI is intentionally stdlib-only so it runs wherever Python 3.11+ is available, with no `pip install` step. Every module that hits the Figma REST API carries a comment linking to the Figma docs for that endpoint.

## License

MIT. See [LICENSE](LICENSE).
