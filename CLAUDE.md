# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Dev Commands

```bash
# Setup (Python 3.12+ required)
uv sync --extra dev          # preferred
pip install -e ".[dev]"      # alternative

# Run all tests
pytest tests/ -v

# Run a single test file or test
pytest tests/test_cli.py -v
pytest tests/test_cli.py::test_function_name -v

# Lint
ruff check src/ tests/

# Run CLI locally
docweave --version
docweave guide
```

Build system is hatchling. Version is read from `src/docweave/__init__.py`.

## Architecture

Docweave is an agent-first CLI for structured document editing. Every command emits a JSON envelope to stdout — no plain text output. This makes it machine-parseable for AI agents and CI pipelines.

### Data flow

```
CLI command → init_backends() → detect backend → backend.load_view() → NormalizedDocument
                                                                           ↓
Patch YAML → PatchFile (Pydantic) → planner.generate_plan() → ExecutionPlan
                                                                    ↓
                                              applier.apply_plan() → writes file + journal entry
```

### Key design decisions

- **JSON envelope everywhere**: All output goes through `envelope.py`. Use `success_envelope()` / `error_envelope()` / `make_envelope()` → `emit()`. Never print raw text to stdout from commands.
- **Entry point is `main()`, not `app`**: `pyproject.toml` points to `docweave.cli:main`. The `main()` function wraps `app(standalone_mode=False)` with structured error handling that catches exceptions and emits proper error envelopes.
- **Backend plugin system**: `BackendAdapter` ABC in `backends/base.py`. Registry in `backends/registry.py` handles auto-detection by file extension and confidence scoring. Currently only `MarkdownBackend` (using markdown-it-py).
- **Anchor resolution**: Blocks are targeted by heading text, content substring, index, or stable hash — never by line number. See `anchors.py`.
- **Fingerprint conflict detection**: `applier.py` uses content hashing to prevent concurrent edit conflicts.
- **ExitCode constants** (in `config.py`): 0=success, 10=validation, 20=permission, 40=conflict, 50=IO, 90=internal. Commands must use these, not arbitrary codes.

### CLI quirks

- `--format` is on the Typer callback (parent), so it must come BEFORE the subcommand: `docweave --format json guide`
- `--version` / `-V` / `-v` is an eager callback that emits a JSON envelope and raises `typer.Exit()`
- No-args invocation emits a JSON error envelope (exit 10), not Typer's default help

### Testing

Tests use `typer.testing.CliRunner`. The shared `run_cli` fixture (in `tests/conftest.py`) invokes the app and auto-parses the JSON envelope into `result.json`. Most tests create temp markdown files via `tmp_path` and assert against envelope fields.

### Ruff config

Line length 99, target Python 3.12. Lint rules: E, F, I, N, W, UP.

## Custom Commands

### `/project:author <subject>`

Produces a large, structured Markdown document on the given subject using docweave's patch-based editing and **Claude Code agent teams**.

The lead (Editor-in-Chief) creates the outline and skeleton, then spawns a team:
- **Research Agent** — investigates the topic, sends notes to authors
- **Section Authors** (2-4) — draft content as patch YAML files in parallel
- **Continuity Agent** — reviews the assembled document for coherence

Only the lead applies patches to the document file (prevents fingerprint conflicts from concurrent edits). Teammates draft YAML patches and message the lead when ready.

Phases: outline → team spawn → parallel section development → cohesion pass → expansion → final polish.

The patch YAML reference is at `.claude/references/patch-format.md`.

Agent teams require the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` env var (enabled in `.claude/settings.json`).
