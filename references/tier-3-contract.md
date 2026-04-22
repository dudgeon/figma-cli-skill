# Tier 3 — the `tree.json` contract

`figma node read <url>` writes a lossless node payload to
`$CLAUDE_PROJECT_DIR/.figma-cache/<file_key>/<node_id>/` and prints a
manifest JSON to stdout. This document is the contract for that
payload: what's guaranteed, what's best-effort, and how Claude should
consume it to build UI code.

## Manifest (stdout)

```json
{
  "file_key": "AbCdEf123",
  "node_id": "10:20",
  "name": "Checkout / Payment",
  "type": "FRAME",
  "url": "https://www.figma.com/design/AbCdEf123/Slug?node-id=10-20",
  "outputs": {
    "tree": ".figma-cache/AbCdEf123/10-20/tree.json",
    "png": ".figma-cache/AbCdEf123/10-20/render@2x.png",
    "svg": ".figma-cache/AbCdEf123/10-20/render.svg",
    "variables_used": ".figma-cache/AbCdEf123/10-20/variables.json",
    "components_inlined": ".figma-cache/AbCdEf123/10-20/components.json",
    "fills": null
  },
  "stats": { "nodes": 342, "text_nodes": 48, "instances": 17, "components": 0, "frames": 12 },
  "image_refs": ["2f1e...", "94ab..."],
  "variables_source": "enterprise_api"
}
```

`outputs.*` values are null when the corresponding artifact wasn't
produced (e.g. `svg: null` if `--no-svg` was passed; `fills: null`
unless `figma node assets` was run to materialize them).

## `tree.json` structure

The root is the requested node's `document`, returned directly from
`GET /v1/files/:key/nodes?ids=<id>&geometry=paths`. All native Figma
fields are preserved unchanged (`name`, `type`, `absoluteBoundingBox`,
`layoutMode`, `primaryAxisSizingMode`, `counterAxisSizingMode`,
`paddingLeft/Right/Top/Bottom`, `itemSpacing`, `constraints`, `fills`,
`strokes`, `effects`, `characters`, `style`, `layoutGrids`, …).

On top of that, every node gets these **additive** fields — their
names are prefixed with `_` so they never collide with native Figma
fields:

### `_url` — always present

Deep link back to Figma for the node. Paste into a browser to jump
directly to the frame/instance/text in Figma's UI.

```json
{ "id": "10:21", "type": "INSTANCE", "_url": "https://www.figma.com/design/AbCdEf123/Slug?node-id=10-21", … }
```

### `boundVariables.*._name` / `._collection` / `._resolvedType`

Native `boundVariables` entries pointing at a `VARIABLE_ALIAS` are
annotated in place with human-readable metadata looked up from
`/v1/files/:key/variables/local`.

```json
{
  "boundVariables": {
    "fills": [
      {
        "type": "VARIABLE_ALIAS",
        "id": "VariableID:1/2",
        "_name": "color/brand/primary",
        "_collection": "Brand",
        "_resolvedType": "COLOR"
      }
    ]
  },
  "fills": [{ "type": "SOLID", "color": { "r": 0.231, "g": 0.510, "b": 0.965, "a": 1 } }]
}
```

The concrete `color` on `fills[0]` is Figma's resolved value. Use that
for implementation; use `_name` to name your design-token variable.

If variables aren't available (non-Enterprise plan), `boundVariables`
stays intact but without the `_name` / `_collection` / `_resolvedType`
annotations, and the manifest reports `variables_source: "unavailable"`.

### `_styles`

When a node references shared fill/stroke/text/effect styles via the
native `styles` field, the CLI looks each style id up in the file's
`styles` metadata and emits a parallel `_styles` map.

```json
{
  "styles": { "fill": "S:1", "text": "S:2" },
  "_styles": {
    "fill": { "id": "S:1", "name": "bg/card", "styleType": "FILL" },
    "text": { "id": "S:2", "name": "body/md", "styleType": "TEXT" }
  }
}
```

### `_componentMain` — on every `INSTANCE`

Every `INSTANCE` gets `_componentMain` with metadata about the main
component it was copied from. When the main component lives in the same
file (typical), its full subtree is inlined under `body`.

```json
{
  "type": "INSTANCE",
  "componentId": "C:1",
  "componentProperties": { … },
  "overrides": [ … ],
  "_componentMain": {
    "id": "C:1",
    "name": "Primary Button",
    "description": "CTA",
    "key": "comp-key-1",
    "componentSetId": "CS:5",
    "set_name": "Button",
    "inlined": true,
    "body": { "id": "C:1", "type": "COMPONENT", "name": "Primary Button", "children": [ … ] }
  }
}
```

For external/library components whose main node isn't in the current
file, `inlined` is `false` and `body` is absent. The CLI still emits the
instance's `componentProperties` and `overrides`, which typically carry
enough information to implement the instance without the main body.

## Side files in the cache directory

### `variables.json`

Only the variables and collections actually referenced by this subtree,
in Figma's native variable shape. Keyed by variable id.

```json
{
  "_available": true,
  "variables": {
    "VariableID:1/2": {
      "id": "VariableID:1/2",
      "name": "color/brand/primary",
      "resolvedType": "COLOR",
      "variableCollectionId": "VC:1",
      "valuesByMode": { "…": { "r": 0.231, "g": 0.510, "b": 0.965, "a": 1 } }
    }
  },
  "collections": {
    "VC:1": { "id": "VC:1", "name": "Brand", "modes": [ … ] }
  }
}
```

### `components.json`

```json
{
  "metadata": { "C:1": { "name": "Primary Button", "description": "CTA", "key": "…" } },
  "component_sets": { "CS:5": { "name": "Button", "description": "…" } },
  "inlined_main": { "C:1": { "id": "C:1", "type": "COMPONENT", "children": [ … ] } }
}
```

### `render@2x.png` and `render.svg`

PNG rendered at the requested scale (default 2x), and an SVG render
(unless `--no-svg`). Use the PNG for vision-model review and visual
verification; use the SVG for icon-like elements where resolution
independence matters.

### `fills/<ref>.<ext>` (only when `figma node assets` is run)

Raw bytes behind `IMAGE` paints (fills, strokes, background) discovered
inside the subtree. Filenames are keyed by Figma's `imageRef`.

## Text fidelity

Text nodes include the native `characters` string and `style` block
(fontFamily, fontWeight, fontSize, lineHeight, letterSpacing,
textAlignHorizontal/Vertical, textCase, textDecoration, paragraphSpacing,
paragraphIndent). Per-range overrides (mixed styling within a text node)
come through via `characterStyleOverrides` and `styleOverrideTable`, both
preserved.

## Tree size expectations

Rough rules of thumb:

| Scope | Node count | tree.json size |
|---|---|---|
| A single icon component | 5–30 | 5–30 KB |
| One simple screen | 50–200 | 50–200 KB |
| A dense design-system screen | 300–1,000 | 300 KB – 2 MB |
| A full flow with many instances | 1,000–5,000 | 1–10 MB |

These are on-disk files, not prompt tokens. Claude should read
strategically: start with the root node, then descend by `id` into the
parts that matter. Don't blindly load the full file into a single LLM
call.

## Determinism

`figma node read` is idempotent. Running it again for the same node
overwrites the cache files but never deletes other nodes' caches.
Variables.json and components.json vary only with the source-of-truth
file in Figma; re-running is safe.
