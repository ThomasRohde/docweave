<!-- docweave: {"summary": "Project overview — agent-first CLI for structured document editing", "tags": ["overview", "getting-started"], "status": "complete"} -->
# docweave

**The document editing CLI that makes AI agents 16x cheaper and 27x faster.**

Docweave gives AI agents structured, surgical access to Markdown and Word documents. Instead of dumping an entire file into context, agents call `inspect` to see a document's structure with hidden metadata, then drill into exactly the sections they need. The result: fewer tokens, fewer tool calls, better edits.

```
Without docweave:  "Here's the entire 40KB document. Find the security section and update it."
With docweave:     inspect --tag security → view --section "Token Management" → apply --patch edit.yaml
```

<!-- docweave: {"summary": "Benchmark evidence for token savings, speed, and accuracy", "tags": ["overview", "benchmark", "agents"], "status": "complete"} -->
## Why Annotations Matter: The Numbers

We benchmarked six realistic agent tasks against a 55-heading architecture document &mdash; with and without docweave annotations:

| Metric | Without Annotations | With Annotations | Improvement |
|--------|--------------------:|------------------:|:-----------:|
| **Tokens consumed** | 323,152 | 20,282 | **93.7% fewer** |
| **Tool calls** | 189 | 7 | **96.3% fewer** |
| **Cost per run** | $0.97 | $0.06 | **16x cheaper** |

### Task-by-task breakdown

| Task | Plain (tokens) | Annotated (tokens) | Saved | Calls: Plain &rarr; Annotated |
|------|---------------:|-------------------:|------:|:-----------------------------:|
| Find performance sections | 99,613 | 1,119 | **98.9%** | 56 &rarr; 1 |
| Find draft sections | 99,613 | 4,442 | **95.5%** | 56 &rarr; 1 |
| Edit token management | 7,154 | 1,502 | **79.0%** | 4 &rarr; 2 |
| Find ops-audience sections | 99,613 | 4,442 | **95.5%** | 56 &rarr; 1 |
| Dependency analysis | 9,524 | 4,442 | **53.4%** | 11 &rarr; 1 |
| View compliance content | 7,635 | 4,335 | **43.2%** | 6 &rarr; 1 |

### It's not just speed &mdash; it's accuracy

Without annotations, agents must guess. With annotations, they know.

- **Status detection**: A plain agent guessed 19 draft sections using a content-length heuristic. The annotated agent found exactly 20 &mdash; the correct answer. You can't infer status from content.
- **Audience filtering**: Keyword matching flagged 46 of 55 sections as "ops-relevant" (84% false positive rate). Annotations identified exactly 20.
- **Dependency analysis**: Text search found 8 sections mentioning "auth." Annotations captured exactly 6 with explicit dependency declarations &mdash; no noise, no false positives.

### What this means at scale

At **$3/MTok** (Claude Sonnet input pricing):

| Scale | Savings |
|-------|--------:|
| 100 agent runs/day | **$91/day** |
| 1,000 agent runs/day | **$909/day** |
| 10,000 agent runs/day | **$9,086/day** |

> The benchmark code is in [`benchmarks/`](benchmarks/). Run it yourself: `python benchmarks/generate_agentic_doc.py && python benchmarks/agentic_benchmark.py`

<!-- docweave: {"summary": "Key features and value propositions", "tags": ["overview", "features"], "status": "complete"} -->
## How It Works

Docweave parses documents into a normalized block model, resolves structural anchors, and applies targeted edits through a declarative YAML patch format. Every command returns a stable JSON envelope on `stdout`.

### The agent workflow

```
1. inspect doc.md              → headings + annotations (tags, status, audience, summaries)
2. inspect doc.md --tag X      → filter to sections you care about
3. view doc.md --tag X         → read only the content of those sections
4. apply ... --patch ...       → make targeted edits
5. apply ... --patch ...       → set_context to update annotations after edits
```

One `inspect` call on a 55-heading document costs ~4,400 tokens. That single call gives the agent the summary, status, audience, tags, and dependencies for every section &mdash; enough to decide exactly where to look next without reading any content.

### Annotations: the key innovation

Add a single HTML comment before any heading:

```markdown
<!-- docweave: {"summary": "OAuth2 flow with PKCE", "tags": ["security", "api"], "status": "draft"} -->
## Authentication
```

This comment is invisible when rendered but surfaced by `inspect`. The agent sees:

```json
{
  "text": "Authentication",
  "level": 2,
  "block_id": "blk_003",
  "annotations": {
    "summary": "OAuth2 flow with PKCE",
    "tags": ["security", "api"],
    "status": "draft"
  }
}
```

Now it can filter by tag (`--tag security`), check status without reading content, and understand section relationships through `dependencies` &mdash; all in a single tool call.

<!-- docweave: {"summary": "All features listed", "tags": ["overview", "features"], "status": "complete"} -->
## Features

- **Structured JSON output** &mdash; Every response is a Pydantic-validated `Envelope` with `ok`, `errors`, `warnings`, and `metrics` fields. Parse one schema regardless of success or failure.
- **Multi-format support** &mdash; Native backends for Markdown and Word (.docx) with automatic detection.
- **Anchor-based editing** &mdash; Target blocks by heading, content search, or contextual clues instead of fragile line numbers.
- **Progressive discovery** &mdash; Embed hidden annotations (summaries, tags, status) in documents. Agents call `inspect` to see structure + context, then drill into sections with `--tag` or `--section`.
- **Atomic writes** &mdash; Fingerprint-based conflict detection prevents lost updates. Optional backups on every mutation.
- **Semantic diffs** &mdash; Compare documents at the block level, not just line-by-line.
- **Evidence bundles** &mdash; Generate before/after snapshots, diffs, and validation reports for audit trails.
- **Transaction journal** &mdash; Every `apply` is recorded with full provenance for rollback and review.

<!-- docweave: {"summary": "Install via uv, pip, or from source", "tags": ["getting-started", "installation"], "status": "complete"} -->
## Installation

Requires **Python 3.12+**.

<!-- docweave: {"summary": "Install as a uv tool from PyPI", "tags": ["installation"], "status": "complete"} -->
### With `uv` (after the PyPI release)

```bash
uv tool install docweave
```

<!-- docweave: {"summary": "Install directly from GitHub", "tags": ["installation"], "status": "complete"} -->
### From the repository

```bash
uv tool install git+https://github.com/ThomasRohde/docweave.git
```

<!-- docweave: {"summary": "Editable install with dev dependencies for contributors", "tags": ["installation", "development"], "status": "complete"} -->
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

<!-- docweave: {"summary": "Common CLI invocations covering inspect, view, find, apply, diff, validate, and journal", "tags": ["getting-started", "examples"], "status": "complete"} -->
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

<!-- docweave: {"summary": "Complete command reference table", "tags": ["reference", "commands"], "status": "complete"} -->
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

<!-- docweave: {"summary": "Envelope schema — the JSON wrapper around every CLI response", "tags": ["reference", "api"], "status": "complete"} -->
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

<!-- docweave: {"summary": "YAML patch file format with operations, anchors, and content kinds", "tags": ["reference", "patching"], "status": "complete"} -->
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

<!-- docweave: {"summary": "All patch operation types: insert, replace, delete, set_heading, set_context", "tags": ["reference", "patching"], "status": "complete"} -->
### Supported Operations

| Operation      | Description                               |
| -------------- | ----------------------------------------- |
| `insert_after` | Insert content after the anchored block   |
| `insert_before`| Insert content before the anchored block  |
| `replace`      | Replace the anchored block's content      |
| `delete`       | Remove the anchored block                 |
| `set_heading`  | Change a heading's text                   |
| `set_context`  | Set hidden annotations on a heading       |

<!-- docweave: {"summary": "Anchor types for targeting blocks: heading, content, index, hash", "tags": ["reference", "patching"], "status": "complete"} -->
### Anchor Types

| Anchor (`by`)  | Description                                         |
| -------------- | --------------------------------------------------- |
| `heading`      | Match by heading text                               |
| `content`      | Match by block content substring                    |
| `index`        | Match by block index                                |
| `hash`         | Match by stable content hash                        |

Anchors can be refined with `--section`, `--context-before`, `--context-after`, and `--occurrence` for precise targeting.

<!-- docweave: {"summary": "Hidden metadata on headings for agent-driven progressive discovery", "tags": ["annotations", "agents", "features"], "status": "complete"} -->
## Annotations Reference

<!-- docweave: {"summary": "HTML comment syntax for Markdown, custom XML for Word", "tags": ["annotations", "reference"], "status": "complete"} -->
### Format by backend

**Markdown** &mdash; HTML comments placed before a heading:

```markdown
<!-- docweave: {"summary": "Authentication flow overview", "tags": ["security", "api"], "status": "draft"} -->
## Authentication
```

**Word (.docx)** &mdash; Custom XML part inside the archive, invisible to Word users.

<!-- docweave: {"summary": "Standard annotation keys: summary, tags, status, audience, dependencies", "tags": ["annotations", "reference"], "status": "complete"} -->
### Common annotation keys

| Key            | Type       | Purpose                              |
| -------------- | ---------- | ------------------------------------ |
| `summary`      | `string`   | One-line description of the section  |
| `tags`         | `string[]` | Categorical labels for filtering     |
| `status`       | `string`   | Editing status (draft, review, final)|
| `audience`     | `string`   | Target reader                        |
| `dependencies` | `string[]` | Sections this one depends on         |

<!-- docweave: {"summary": "set_context operation with merge semantics", "tags": ["annotations", "patching"], "status": "complete"} -->
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

<!-- docweave: {"summary": "Filter inspect and view output with --tag", "tags": ["annotations", "commands"], "status": "complete"} -->
### Querying by tag

```bash
# Show only headings tagged "security"
docweave inspect doc.md --tag security

# View blocks from all sections tagged "api"
docweave view doc.md --tag api
```

<!-- docweave: {"summary": "Process exit codes 0/10/20/40/50/90", "tags": ["reference"], "status": "complete"} -->
## Exit Codes

| Code | Meaning              |
| ---- | -------------------- |
| `0`  | Success              |
| `10` | Validation error     |
| `20` | Permission error     |
| `40` | Conflict error       |
| `50` | I/O error            |
| `90` | Internal error       |

<!-- docweave: {"summary": "Structured error codes: ERR_VALIDATION, ERR_PERMISSION, ERR_CONFLICT, ERR_IO, ERR_INTERNAL", "tags": ["reference"], "status": "complete"} -->
## Error Codes

| Code                    | Description                                            |
| ----------------------- | ------------------------------------------------------ |
| `ERR_VALIDATION`        | Input failed validation (bad args, schema error)       |
| `ERR_PERMISSION`        | Insufficient permissions to read or write target       |
| `ERR_CONFLICT`          | Fingerprint mismatch &mdash; file changed since read   |
| `ERR_IO`                | File-system I/O failure                                |
| `ERR_INTERNAL_UNHANDLED`| Unexpected internal error                              |

<!-- docweave: {"summary": "Source tree layout: cli, envelope, config, backends, plan, diff, evidence", "tags": ["architecture", "development"], "status": "complete"} -->
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

<!-- docweave: {"summary": "Dev setup, test, and lint commands", "tags": ["development"], "status": "complete"} -->
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

<!-- docweave: {"summary": "Dependencies: Typer, Pydantic, orjson, markdown-it-py, python-docx, PyYAML, Rich, Hatchling", "tags": ["architecture", "reference"], "status": "complete"} -->
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

<!-- docweave: {"summary": "Contribution workflow: fork, branch, test, PR", "tags": ["development", "contributing"], "status": "complete"} -->
## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Write tests for your changes
4. Ensure `pytest tests/ -v` and `ruff check src/ tests/` pass
5. Submit a pull request

<!-- docweave: {"summary": "License reference", "tags": ["legal"], "status": "complete"} -->
## License

See [LICENSE](LICENSE) for details.
