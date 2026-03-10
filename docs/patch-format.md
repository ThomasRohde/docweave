# Patch Format

Docweave edits are described in YAML patch files. Pass them to `plan` or `apply`
with `--patch FILE.yaml`.

## File Structure

```yaml
version: 1
target:
  backend: auto       # or: markdown, text
operations:
  - id: op_001        # unique identifier
    op: insert_after  # operation type
    anchor:
      by: heading
      value: Introduction
    content:
      kind: markdown
      value: |
        New paragraph to insert.
```

**Top-level fields:**

| Field | Required | Description |
| ----- | -------- | ----------- |
| `version` | Yes | Must be `1` |
| `target` | No | Metadata (backend hint) |
| `operations` | Yes | List of edit operations |

## Operations

### insert_after / insert_before

Insert new content after or before the anchored block.

```yaml
- id: op_001
  op: insert_after
  anchor:
    by: heading
    value: Overview
  content:
    kind: markdown
    value: |
      New content here.
```

### replace_block

Replace the entire anchored block with new content.

```yaml
- id: op_002
  op: replace_block
  anchor:
    by: heading
    value: Old Section
  content:
    kind: markdown
    value: |
      ## New Section

      Updated content.
```

### replace_text

Replace a specific substring within the anchored block.

```yaml
- id: op_003
  op: replace_text
  anchor:
    by: quote
    value: old phrase
  replacement: new phrase
```

### delete_block

Remove the anchored block entirely.

```yaml
- id: op_004
  op: delete_block
  anchor:
    by: heading
    value: Deprecated Section
```

### set_heading

Change a heading's text.

```yaml
- id: op_005
  op: set_heading
  anchor:
    by: heading
    value: Old Title
  content:
    kind: markdown
    value: New Title
```

### normalize_whitespace

Normalize whitespace in the anchored block.

```yaml
- id: op_006
  op: normalize_whitespace
  anchor:
    by: block_id
    value: blk_007
```

## Anchor Specification

```yaml
anchor:
  by: heading          # anchor type
  value: Introduction  # match value
  section: Overview    # optional: restrict to section
  occurrence: 2        # optional: match Nth occurrence (default: 1)
  context_before: text # optional: require preceding text
  context_after: text  # optional: require following text
```

| `by` value | Matches |
| ---------- | ------- |
| `heading` | Heading block with matching text |
| `quote` | Any block containing the text |
| `block_id` | Block with ID like `blk_001` |
| `hash` | Block whose hash starts with the given prefix |
| `ordinal` | Nth block of a kind (e.g., `paragraph:3`) |
