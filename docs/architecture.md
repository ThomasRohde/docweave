# Architecture

Docweave is organized into focused modules. Every command flows through the
same pipeline: CLI → Backend → Anchors → Plan → Applier.

## Module Structure

```
src/docweave/
├── cli.py               # Typer app, all 10 commands
├── __init__.py          # Package version
├── envelope.py          # JSON envelope model and emit()
├── config.py            # ExitCode constants, RuntimeConfig
├── models.py            # Block, NormalizedDocument, SourceSpan
├── anchors.py           # Anchor parsing and resolution
├── validation.py        # Structural validation rules
├── journal.py           # Append-only transaction log (JSONL)
├── backends/
│   ├── base.py          # BackendAdapter ABC
│   ├── registry.py      # Auto-detection and registry
│   └── markdown_native.py  # Markdown parser (markdown-it-py)
├── plan/
│   ├── schema.py        # PatchFile and OperationSpec models
│   ├── planner.py       # Anchor resolution to ExecutionPlan
│   └── applier.py       # Atomic writes with fingerprinting
├── diff/
│   ├── raw.py           # Line-level unified diff
│   └── semantic.py      # Block-level semantic diff
└── evidence/
    └── bundle.py        # Before/after snapshot bundles
```

## Data Flow

```
File ──► Backend.parse() ──► NormalizedDocument (list of Blocks)
                                       │
                                Anchor.resolve()
                                ExecutionPlan (resolved ops)
                                       │
                               Applier.apply() ──► Modified File
                                       │
                               Journal.record()
                               Evidence.bundle()
```

## Key Concepts

**Block** — The atomic unit. Every heading, paragraph, list, code block, and
table is a `Block` with:

- `block_id`: Sequential ID (`blk_001`, `blk_002`, ...)
- `kind`: `heading`, `paragraph`, `code_block`, `list`, etc.
- `section_path`: Hierarchical location (e.g., `["API", "Methods"]`)
- `text`: Normalized plain text
- `stable_hash`: SHA-256[:16] for fingerprinting
- `source_span`: `(start_line, end_line)` in the original file

**Envelope** — Every command response. Fields: `ok`, `request_id`, `command`,
`target`, `result`, `errors`, `warnings`, `metrics`, `version`.

**Anchor** — A location reference that does not use fragile line numbers.
Resolved at plan time against the current block list.

**Fingerprint** — SHA-256 hash of the file at plan time. If the file changes
before `apply`, the fingerprint check fails with exit code `40` (ERR_CONFLICT).

**Journal** — Append-only JSONL file at `.docweave-journal/journal.jsonl` beside
each edited document. Records transaction ID, timestamp, operations, and
before/after hashes.

## Backend Architecture

Backends implement the `BackendAdapter` ABC:

- `parse(path)` → `NormalizedDocument`
- `write(path, content)`
- `detect(path)` → `bool`

The `registry.detect()` function auto-selects the appropriate backend based on
file extension. Currently supported: Markdown (`.md`), plain text (`.txt`).
