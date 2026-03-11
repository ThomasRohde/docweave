# docweave

Agent-first CLI for structured document editing.

Docweave parses Markdown and Word (.docx) documents into a normalized block model, resolves structural anchors, and applies targeted edits through a declarative YAML patch format. Every command returns a stable JSON envelope on `stdout`, making it ideal for AI agents, CI pipelines, and scriptable workflows.

The PyPI package name is `docweave`, and it installs the `docweave` command.

## Highlights

- **Structured JSON output** &mdash; Every response is a Pydantic-validated `Envelope` with `ok`, `errors`, `warnings`, and `metrics` fields. Parse one schema regardless of success or failure.
- **Multi-format support** &mdash; Native backends for Markdown and Word (.docx) with automatic detection.
- **Anchor-based editing** &mdash; Target blocks by heading, content search, or contextual clues instead of fragile line numbers.
- **Progressive discovery** &mdash; Embed hidden annotations (summaries, tags, status) in documents. Agents call `inspect` to see structure + context, then drill into sections with `--tag` or `--section`.
- **Atomic writes** &mdash; Fingerprint-based conflict detection prevents lost updates. Optional backups on every mutation.
- **Semantic diffs** &mdash; Compare documents at the block level, not just line-by-line.
- **Evidence bundles** &mdash; Generate before/after snapshots, diffs, and validation reports for audit trails.
- **Transaction journal** &mdash; Every `apply` is recorded with full provenance for rollback and review.

## Installation

Requires **Python 3.12+**.

### With `uv` (after the PyPI release)

```bash
uv tool install docweave
```

### From the repository

```bash
uv tool install git+https://github.com/ThomasRohde/docweave.git
```

### Development install

```bash
git clone https://github.com/ThomasRohde/docweave.git
cd docweave
pip install -e ".[dev]"
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv sync --extra dev
```

Verify the installation:

```bash
docweave --version
docweave guide
```

## Quick Start

```bash
# Inspect a document's structure
docweave inspect README.md

# Inspect only sections tagged "security"
docweave inspect doc.md --tag security

# View all blocks as normalized JSON
docweave view README.md

# View blocks from tagged sections
docweave view doc.md --tag api

# Search for blocks containing text
docweave find README.md "installation"

# Resolve a specific anchor
docweave anchor README.md "heading:Quick Start"

# Preview a patch plan (no changes written)
docweave plan doc.md --patch edits.yaml

# Apply a patch with backup and evidence
docweave apply doc.md --patch edits.yaml --backup --evidence-dir ./evidence

# Dry-run an apply (shows plan, writes nothing)
docweave apply doc.md --patch edits.yaml --dry-run

# Compare two document versions
docweave diff before.md after.md

# Validate document structure
docweave validate doc.md

# Review transaction history
docweave journal --file doc.md
```

## Commands

| Command      | Description                                              |
| ------------ | -------------------------------------------------------- |
| `guide`      | Show command catalog, error codes, and exit codes        |
| `inspect`    | Return structural metadata, headings with annotations    |
| `view`       | Return the full normalized block list                    |
| `find`       | Search blocks for a text query                           |
| `anchor`     | Resolve an anchor spec to a specific block               |
| `plan`       | Preview an execution plan from a YAML patch file         |
| `apply`      | Apply a patch to a document with conflict detection      |
| `diff`       | Compute raw and semantic diff between two documents      |
| `validate`   | Validate structural integrity of a document              |
| `journal`    | List or retrieve transaction journal entries              |

> Run `docweave guide` for the full machine-readable command reference.

## JSON Envelope

Every command emits a JSON envelope to `stdout`:

```jsonc
{
  "ok": true,
  "request_id": "req_20260310_143022_a1b2",
  "command": "inspect",
  "target": "doc.md",
  "result": { /* command-specific payload */ },
  "errors": [],
  "warnings": [],
  "metrics": { "duration_ms": 12 },
  "version": "x.y.z"
}
```

On failure, `ok` is `false` and `errors` contains structured error details:

```jsonc
{
  "ok": false,
  "command": "inspect",
  "errors": [
    {
      "code": "ERR_IO_FILE_NOT_FOUND",
      "message": "File not found: missing.md"
    }
  ]
  // ...
}
```

## Patch Format

Edits are described in YAML patch files:

```yaml
version: 1
target:
  file: doc.md
  backend: auto
operations:
  - id: op_001
    op: insert_after
    anchor:
      by: heading
      value: Purpose
    content:
      kind: markdown
      value: |
        New paragraph inserted after the Purpose heading.

  - id: op_002
    op: replace
    anchor:
      by: heading
      value: Scope
    content:
      kind: markdown
      value: |
        Updated scope section content.
```

### Supported Operations

| Operation      | Description                               |
| -------------- | ----------------------------------------- |
| `insert_after` | Insert content after the anchored block   |
| `insert_before`| Insert content before the anchored block  |
| `replace`      | Replace the anchored block's content      |
| `delete`       | Remove the anchored block                 |
| `set_heading`  | Change a heading's text                   |
| `set_context`  | Set hidden annotations on a heading       |

### Anchor Types

| Anchor (`by`)  | Description                                         |
| -------------- | --------------------------------------------------- |
| `heading`      | Match by heading text                               |
| `content`      | Match by block content substring                    |
| `index`        | Match by block index                                |
| `hash`         | Match by stable content hash                        |

Anchors can be refined with `--section`, `--context-before`, `--context-after`, and `--occurrence` for precise targeting.

## Annotations & Progressive Discovery

Docweave supports hidden annotations on heading blocks — structured metadata that is invisible when the document is rendered but surfaced by `inspect`. This enables **progressive discovery**: an agent calls `inspect` to see the document structure with context, then drills into specific sections.

### Annotation format

In Markdown, annotations are HTML comments placed before a heading:

```markdown
<!-- docweave: {"summary": "Authentication flow overview", "tags": ["security", "api"], "status": "draft"} -->
## Authentication
```

In Word (.docx), annotations are stored in a custom XML part inside the archive, invisible to Word users.

### Common annotation keys

| Key            | Type       | Purpose                              |
| -------------- | ---------- | ------------------------------------ |
| `summary`      | `string`   | One-line description of the section  |
| `tags`         | `string[]` | Categorical labels for filtering     |
| `status`       | `string`   | Editing status (draft, review, final)|
| `audience`     | `string`   | Target reader                        |
| `dependencies` | `string[]` | Sections this one depends on         |

### Setting annotations via patches

Use the `set_context` operation to add or merge annotations:

```yaml
operations:
  - id: op_annotate
    op: set_context
    anchor:
      by: heading
      value: Authentication
    context:
      summary: "OAuth2 flow with PKCE"
      tags: ["security", "api"]
      status: "draft"
```

Merge semantics: new keys are added, existing keys are overwritten.

### Querying by tag

```bash
# Show only headings tagged "security"
docweave inspect doc.md --tag security

# View blocks from all sections tagged "api"
docweave view doc.md --tag api
```

The `inspect` output includes `block_id`, `section_path`, and `annotations` for each heading, giving agents everything they need to target a section directly.

## Exit Codes

| Code | Meaning              |
| ---- | -------------------- |
| `0`  | Success              |
| `10` | Validation error     |
| `20` | Permission error     |
| `40` | Conflict error       |
| `50` | I/O error            |
| `90` | Internal error       |

## Error Codes

| Code                    | Description                                            |
| ----------------------- | ------------------------------------------------------ |
| `ERR_VALIDATION`        | Input failed validation (bad args, schema error)       |
| `ERR_PERMISSION`        | Insufficient permissions to read or write target       |
| `ERR_CONFLICT`          | Fingerprint mismatch &mdash; file changed since read   |
| `ERR_IO`                | File-system I/O failure                                |
| `ERR_INTERNAL_UNHANDLED`| Unexpected internal error                              |

## Architecture

```
src/docweave/
├── cli.py              # Typer app, all commands, entry point
├── envelope.py         # JSON envelope model & emit()
├── config.py           # ExitCode constants, RuntimeConfig
├── models.py           # Block, NormalizedDocument, SourceSpan
├── anchors.py          # Anchor parsing & resolution
├── validation.py       # Structural validation rules
├── journal.py          # Transaction journal (append-only log)
├── backends/
│   ├── base.py         # BackendAdapter ABC
│   ├── registry.py     # Backend auto-detection & registry
│   ├── markdown_native.py  # Markdown parser (markdown-it-py)
│   ├── docx_backend.py     # Word (.docx) backend (python-docx)
│   └── docx_annotations.py # Custom XML annotation storage
├── plan/
│   ├── schema.py       # PatchFile, OperationSpec (YAML → Pydantic)
│   ├── planner.py      # Anchor resolution → ExecutionPlan
│   ├── applier.py      # Atomic file writes with fingerprinting
│   └── applier_docx.py # Word-specific plan applier
├── diff/
│   ├── raw.py          # Line-level unified diff
│   └── semantic.py     # Block-level semantic diff
└── evidence/
    └── bundle.py       # Before/after snapshot bundles
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Or with uv
uv sync --extra dev

# Run tests
pytest tests/ -v

# Run linter
ruff check src/ tests/

# Run tests with coverage
pytest tests/ --cov=docweave --cov-report=term-missing
```

## Tech Stack

| Component      | Library                                                         |
| -------------- | --------------------------------------------------------------- |
| CLI framework  | [Typer](https://typer.tiangolo.com/)                            |
| Data models    | [Pydantic v2](https://docs.pydantic.dev/)                      |
| JSON output    | [orjson](https://github.com/ijl/orjson)                        |
| Markdown parse | [markdown-it-py](https://github.com/executablebooks/markdown-it-py) |
| Word docs      | [python-docx](https://python-docx.readthedocs.io/)             |
| Patch files    | [PyYAML](https://pyyaml.org/)                                  |
| Terminal UI    | [Rich](https://github.com/Textualize/rich)                     |
| Build system   | [Hatchling](https://hatch.pypa.io/)                            |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Write tests for your changes
4. Ensure `pytest tests/ -v` and `ruff check src/ tests/` pass
5. Submit a pull request

## License

See [LICENSE](LICENSE) for details.
