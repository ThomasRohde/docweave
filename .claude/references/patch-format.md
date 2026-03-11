# Docweave Patch YAML Reference

## Patch Structure

```yaml
version: 1
target:
  file: path/to/document.md
  backend: auto
operations:
  - id: unique_op_id      # Must be unique within the patch
    op: <operation_type>
    anchor:
      by: <anchor_type>
      value: <match_text>
    content:               # Required for insert/replace ops
      kind: <content_kind>
      value: <text>
```

## Operation Types

| Operation | Description | Requires `content` | Requires `replacement` |
|-----------|-------------|---------------------|------------------------|
| `insert_after` | Insert content after the anchored block | Yes | No |
| `insert_before` | Insert content before the anchored block | Yes | No |
| `replace_block` | Replace the entire anchored block | Yes | No |
| `delete_block` | Delete the anchored block | No | No |
| `replace_text` | Replace a substring within the anchored block | No | Yes |
| `set_heading` | Change heading text or level | Yes | No |
| `normalize_whitespace` | Normalize whitespace in block | No | No |
| `set_context` | Set hidden context annotations on a heading | No | No |

## Anchor Types

### `heading` — Match by heading text (fuzzy, case-insensitive)
```yaml
anchor:
  by: heading
  value: "Section Title"
```

### `quote` — Match by substring in block text
```yaml
anchor:
  by: quote
  value: "some text in the block"
```

### `ordinal` — Match by block kind and position
```yaml
anchor:
  by: ordinal
  value: paragraph    # block kind
  index: 3            # 1-based occurrence
```

### `block_id` — Match by exact block ID
```yaml
anchor:
  by: block_id
  value: "blk_005"
```

### `hash` — Match by stable hash prefix
```yaml
anchor:
  by: hash
  value: "a1b2c3"    # First 6+ chars of hash
```

### Anchor Modifiers (optional on any anchor)
```yaml
anchor:
  by: heading
  value: "Purpose"
  occurrence: 2           # Which match if multiple (1-based)
  section: "Introduction" # Filter to blocks under this section
  context_before: "text"  # Expected text in preceding block
  context_after: "text"   # Expected text in following block
```

## Content Kinds

### `markdown` — Raw markdown text (most flexible)
```yaml
content:
  kind: markdown
  value: |
    This is a paragraph with **bold** and *italic*.

    Another paragraph follows.
```

### `heading` — A heading block
```yaml
content:
  kind: heading
  level: 2
  value: "New Section Title"
```

### `code_block` — Fenced code block
```yaml
content:
  kind: code_block
  language: python
  value: |
    def example():
        return 42
```

### `blockquote`
```yaml
content:
  kind: blockquote
  value: "An important note or callout."
```

### `table`
```yaml
content:
  kind: table
  value: |
    | Column A | Column B |
    |----------|----------|
    | Data 1   | Data 2   |
```

### `list_item`
```yaml
content:
  kind: list_item
  value: "A list entry"
```

## Multi-Operation Patch Example

```yaml
version: 1
target:
  file: output.md
operations:
  - id: add_intro_paragraph
    op: insert_after
    anchor:
      by: heading
      value: "Introduction"
    content:
      kind: markdown
      value: |
        This chapter introduces the core concepts that underpin
        the entire framework. By the end, you will understand
        why these foundations matter.

  - id: add_subsection
    op: insert_after
    anchor:
      by: quote
      value: "foundations matter"
    content:
      kind: heading
      level: 2
      value: "Historical Context"

  - id: add_subsection_body
    op: insert_after
    anchor:
      by: heading
      value: "Historical Context"
    content:
      kind: markdown
      value: |
        The field emerged in the late 1990s when researchers
        first observed the phenomenon in controlled settings.
```

## Context Annotations

The `set_context` operation embeds hidden metadata on a heading as an HTML comment.
These annotations are invisible when the document is rendered but are surfaced by
`docweave inspect` for progressive discovery by AI agents.

```yaml
operations:
  - id: ctx_intro
    op: set_context
    anchor:
      by: heading
      value: "Introduction"
    context:
      summary: "Covers the project's origin, goals, and target audience"
      tags: ["overview", "getting-started"]
      status: "complete"
```

This inserts (or updates) a comment immediately before the heading:

```markdown
<!-- docweave: {"summary": "Covers the project's origin, goals, and target audience", "tags": ["overview", "getting-started"], "status": "complete"} -->
# Introduction
```

The `context` field accepts any JSON-serialisable dictionary. Common keys:

| Key | Description |
|-----|-------------|
| `summary` | Brief description of the section's content |
| `tags` | List of topic tags for filtering/search |
| `status` | Authoring status (e.g. "draft", "review", "complete") |
| `audience` | Intended audience for the section |
| `dependencies` | Sections that should be read first |

When `set_context` targets a heading that already has annotations, the new
context is **merged** (new keys are added, existing keys are overwritten).

## Tips for Reliable Patches

1. **Prefer `heading` anchors** — they are the most stable and readable
2. **Use `quote` anchors** for targeting specific paragraphs — pick a unique substring
3. **Add `context_before`/`context_after`** when a heading appears multiple times
4. **Keep operations small** — one logical change per operation
5. **Use `insert_after` for new content** — it's the most common and predictable op
6. **Test anchors first** with `docweave anchor <file> "heading:Title"` before writing patches
7. **Use `--dry-run`** on apply to preview before committing changes
