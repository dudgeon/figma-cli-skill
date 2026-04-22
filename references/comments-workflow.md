# Comments workflow

How the CLI models Figma comments, and conventions for Claude to follow
when summarizing threads or replying.

## Thread shape from `figma comments list`

```json
{
  "file_key": "AbCdEf123",
  "count": 2,
  "threads": [
    {
      "id": "1234567890",
      "file_key": "AbCdEf123",
      "message": "Can we bump the padding here to 24?",
      "author": { "handle": "alice", "id": "…" },
      "created_at": "2026-04-01T10:00:00Z",
      "resolved": false,
      "resolved_at": null,
      "parent_id": null,
      "anchor": {
        "node_id": "10:20",
        "node_offset": { "x": 0, "y": 0 },
        "node_name": "Checkout / Payment",
        "_url": "https://www.figma.com/design/AbCdEf123/Slug?node-id=10-20"
      },
      "replies": [
        {
          "id": "1234567891",
          "message": "+1, the current 16 feels tight",
          "author": { "handle": "bob", "id": "…" },
          "created_at": "2026-04-01T11:00:00Z",
          "resolved": false,
          "parent_id": "1234567890"
        }
      ]
    }
  ]
}
```

- Top-level entries are threads (a root comment + its replies).
- Replies sit under `replies`, sorted oldest-first by `created_at`.
- `anchor.node_name` is pulled from `refs.json`; if the anchor node
  hasn't been read yet, it will be null but `_url` is always present.
- Canvas-level comments have `anchor: { "canvas": { "x": ..., "y": ... } }`.
- File-level comments (rare) have `anchor: {}`.

## Filters

```bash
figma comments list <file-url> --unresolved
figma comments list <file-url> --node 10:20
figma comments list <file-url> --author alice
```

Filters compose; `--unresolved --node 10:20` returns only unresolved
threads anchored on that node.

## Attribution format for user-facing summaries

When summarizing a thread to the user, always include:

1. The **anchor node name** if known, else the `_url`.
2. The **author handle** for each comment.
3. A short **relative timestamp** ("2 days ago") or the ISO time.
4. The **resolved state** if resolved.

Example:

> **alice on "Checkout / Payment"** (2 days ago)
> — Can we bump the padding here to 24?
> ↳ **bob**: +1, the current 16 feels tight.

Link: `https://www.figma.com/design/AbCdEf123/Slug?node-id=10-20`

Keep markdown terse — these summaries land in chat, not documentation.

## Replying

```bash
figma comments reply <comment-id> "Got it, pushing a fix"
```

No `--file` needed if the most recent `comments list` call was for the
same file (the CLI stashes that in
`~/.claude/skills/figma/comments-state.json`). For an older thread or a
different file:

```bash
figma comments reply <comment-id> "…" --file <file-url>
```

## Creating anchored comments

```bash
figma comments create <node-url> "This icon looks off at 12px"
```

The `<node-url>` must include `?node-id=...`. The CLI anchors the new
comment at offset (0, 0) of that node.

## Resolving

```bash
figma comments resolve <comment-id>
```

Hits `POST /v1/files/:key/comments/:id/resolve`. This endpoint is not
documented on every Figma plan; if it returns 404/405 the CLI prints a
clear hint suggesting manual resolution in the Figma UI.

## Reply etiquette

When Claude replies on behalf of the user, default to:

- **One issue per reply.** Don't batch unrelated follow-ups into a single comment.
- **Terse, direct.** Designers scan, they don't read.
- **Cross-reference code.** When the reply addresses a specific implementation change, mention the file/function: "Fixed in `src/pages/checkout/payment.tsx:checkoutForm`".
- **Don't resolve the comment in the reply.** Let the designer do that — they may have follow-ups.
