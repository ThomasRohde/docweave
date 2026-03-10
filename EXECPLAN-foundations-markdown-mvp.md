# Docweave: Foundations & Markdown MVP

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This document must be maintained in accordance with EXEC-PLAN.md at the repository root.


## Purpose / Big Picture

After completing this plan, a user (human or AI agent) will be able to install a Python CLI called `docweave` and use it to inspect Markdown and plain-text documents, resolve structural and contextual anchors within those documents, plan targeted edits using a YAML patch file, apply those edits with atomic writes and automatic backups, and verify the results through semantic diffs and evidence bundles. Every command will return a stable JSON envelope on stdout so that AI agents can parse one schema regardless of success or failure. The CLI will follow the agent-first principles described in CLI-MANIFEST.md: structured envelopes, machine-readable error codes, distinct exit codes per error category, a built-in `guide` command, dry-run on every mutation, fingerprint-based conflict detection, and terse output by default.

To see it working after the final milestone, run:

    pip install -e .
    docweave inspect tests/fixtures/sample.md --format json
    docweave plan tests/fixtures/sample.md -p tests/fixtures/patch_insert_after.yaml --format json
    docweave apply tests/fixtures/sample.md -p tests/fixtures/patch_insert_after.yaml --backup --format json

The inspect command will return JSON metadata about the document. The plan command will show exactly which anchors resolved and what edits would happen. The apply command will modify the file, create a timestamped backup, write a journal entry, and return a structured result with before/after diff.

This plan covers PRD.md Phase 0 (Foundations) and Phase 1 (Markdown Native MVP), plus a minimal text backend to prove that the backend-pluggable architecture works.


## Progress

- [ ] Milestone 1: Project foundation and CLI shell.
- [ ] Milestone 2: Markdown backend — parse, inspect, view.
- [ ] Milestone 3: Anchor resolution, find, and anchors commands.
- [ ] Milestone 4: Plan and apply pipeline with patch schema.
- [ ] Milestone 5: Diff, validation, evidence bundle, and journal.
- [ ] Milestone 6: Text backend to prove backend pluggability.


## Surprises & Discoveries

No entries yet. This section will be updated as implementation proceeds.


## Decision Log

- Decision: CLI name is `docweave`, not `docpatch`. The PRD recommends `docpatch` but the repository is named `docweave` and the user has chosen that name.
  Rationale: Consistency with repository name. "Docweave" also captures the idea of weaving edits into documents.
  Date: 2026-03-10.

- Decision: Python 3.12+ with Typer, Pydantic, and markdown-it-py.
  Rationale: The PRD's suggested repo skeleton is Python. Python-docx (needed for the future DOCX backend) is Python-only. Typer provides a clean subcommand CLI model. Pydantic gives us validated data models and JSON serialization for the envelope. markdown-it-py is a faithful Python port of markdown-it that preserves source line mappings on every token, which we need for mapping blocks back to source lines. We use markdown-it-py instead of unified/remark (JavaScript) to avoid a Node.js runtime dependency. The PRD's key insight is "syntax-tree editing rather than regex-heavy text surgery" — we achieve this through markdown-it-py's token stream with source maps, not by adopting the specific JS libraries.
  Date: 2026-03-10.

- Decision: Edits are applied via source-line manipulation guided by the parsed token structure, not via AST-roundtrip serialization.
  Rationale: Python Markdown libraries (markdown-it-py, mistune, marko) are designed for Markdown-to-HTML conversion, not Markdown-to-Markdown roundtripping. Attempting to serialize a modified AST back to Markdown risks reformatting the user's original text (changing indentation, list markers, heading styles, etc.). Instead, we parse the Markdown to understand its structure (block boundaries, heading hierarchy, table locations), map each block to source line ranges using markdown-it-py's `map` attribute, and then apply edits directly to the source text using those line ranges. Operations that insert new content take Markdown text from the patch and splice it into the source at the correct line. Operations that replace or delete blocks remove the corresponding source lines. This approach preserves the user's original formatting everywhere except at the edit site, which is exactly what the PRD means by "surgical edits."
  Date: 2026-03-10.

- Decision: Use `uv` as the Python package manager and `hatchling` as the build backend.
  Rationale: `uv` is fast and widely adopted. `hatchling` is a modern PEP 517 build backend that works well with `pyproject.toml` and supports editable installs cleanly.
  Date: 2026-03-10.

- Decision: The envelope follows CLI-MANIFEST.md strictly: every command returns JSON with `schema_version`, `request_id`, `ok`, `command`, `result`, `errors`, `warnings`, and `metrics` on stdout. Progress and debug output goes to stderr.
  Rationale: CLI-MANIFEST.md principle 1 (structured envelope) and principle 7 (TOON — Terse Output or None) require this. Agents parse one schema.
  Date: 2026-03-10.

- Decision: Exit codes follow the CLI-MANIFEST.md contract: 0 success, 10 validation error, 20 permission denied, 40 conflict, 50 I/O error, 90 internal error.
  Rationale: CLI-MANIFEST.md principle 3.
  Date: 2026-03-10.


## Outcomes & Retrospective

No entries yet. This section will be updated at the completion of each milestone and at the end of the plan.


## Context and Orientation

The repository at this moment contains four Markdown files and nothing else:

    C:\Users\thoma\Projects\docweave\
      PRD.md            — Product requirements document for docweave
      EXEC-PLAN.md      — Template and rules for writing ExecPlans
      CLI-MANIFEST.md   — Principles for building agent-first CLIs
      SCAFFOLD.md       — Prompt template for scaffolding projects

There is no git repository, no source code, no configuration files, no tests, and no dependencies. The project is entirely in the planning phase.

The PRD describes a backend-pluggable CLI that gives AI agents one stable way to inspect, plan, patch, validate, and persist edits across block-oriented documents. The MVP targets Markdown, plain text, HTML, and DOCX. This ExecPlan covers Markdown and plain text only (the first two backends to prove the architecture).

Three documents govern the implementation. PRD.md defines what to build (the "what" and "why"). CLI-MANIFEST.md defines how the CLI should behave as an agent-facing tool (the output contract, error model, safety rails). EXEC-PLAN.md defines how this plan itself should be written and maintained.

Key terms used throughout this plan:

An "envelope" is the top-level JSON object that every command returns on stdout. It always has the same shape regardless of success or failure. CLI-MANIFEST.md principle 1 defines it.

A "backend" is a module that knows how to parse, inspect, edit, and write one family of document formats. The Markdown backend handles `.md` files. The text backend handles `.txt` files. Each backend implements a common interface (the "adapter protocol") so the CLI commands do not need format-specific logic.

A "normalized document view" is a list of blocks (headings, paragraphs, lists, tables, code blocks, etc.) that a backend extracts from a file. Each block has an ID, a kind, source line numbers, text content, and a hash. This is the intermediate representation that anchors and patches operate on.

An "anchor" is a way to reference a location in a document without using fragile byte offsets. For example, "the heading called 'Purpose'" is a structural anchor. "The text containing 'must immediately' with context 'The system' before it" is a quote anchor. Anchors are how patch operations say where to apply.

A "patch" is a YAML file containing a list of operations (insert, replace, delete, etc.) that reference document locations via anchors. The `plan` command resolves anchors and previews what would happen. The `apply` command executes the patch.

A "fingerprint" is a SHA-256 hash of the file contents at the time of planning. If the file changes between `plan` and `apply`, the fingerprint will not match and the apply will be rejected. This prevents stale overwrites (CLI-MANIFEST.md principle 18).

An "evidence bundle" is a directory containing the normalized document view before and after the edit, the execution plan, the semantic diff, the raw diff, and the fidelity report. It is used for auditing and debugging.

A "transaction journal" is a log of every apply operation, including timestamps, input/output hashes, operations applied, and validation results. It enables rollback and audit.


## Milestone 1: Project Foundation & CLI Shell

After this milestone, you will be able to run `pip install -e .` to install the `docweave` CLI, run `docweave guide` to get a machine-readable JSON description of all commands, run `docweave --version` to see the version, and run `pytest` to see the foundation tests pass. The CLI will not yet do anything useful with documents, but the entire output contract (envelope, errors, exit codes) will be established and tested.

Begin by initializing a git repository in the project root. Create a `.gitignore` that excludes `__pycache__`, `.pytest_cache`, `*.egg-info`, `dist/`, `build/`, `.venv/`, and `.docweave-journal/`.

Create `pyproject.toml` at the repository root. Use `hatchling` as the build backend. Set the project name to `docweave`, version `0.1.0`, and require Python 3.12 or higher. Declare the following runtime dependencies: `typer[all]>=0.15`, `pydantic>=2.0`, `orjson>=3.9`, `markdown-it-py>=3.0`, `pyyaml>=6.0`, and `rich>=13.0`. Declare the following development dependencies under a `[project.optional-dependencies] dev` section: `pytest>=8.0`, `pytest-cov>=5.0`, and `ruff>=0.8`. Define a console script entry point mapping `docweave` to `docweave.cli:app`. Configure ruff with a line length of 99 and target Python 3.12.

Create the source directory `src/docweave/` with an `__init__.py` that defines `__version__ = "0.1.0"`.

Create `src/docweave/config.py`. This module defines a `RuntimeConfig` dataclass that holds the output format (json, yaml, or text, defaulting to json), a boolean `llm_mode` that is true when the `LLM` environment variable equals `"true"`, and a boolean `is_tty` that reflects whether stdout is a terminal. It also defines an `ExitCode` class with integer constants: `SUCCESS = 0`, `VALIDATION = 10`, `PERMISSION = 20`, `CONFLICT = 40`, `IO = 50`, `INTERNAL = 90`. Provide a factory function `detect_config()` that reads the environment and returns a `RuntimeConfig`. This follows CLI-MANIFEST.md principles 3 and 8 (exit codes and LLM=true).

Create `src/docweave/envelope.py`. This module defines Pydantic models for the response envelope. The `ErrorDetail` model has fields: `code` (str), `message` (str), `retryable` (bool, default False), `retry_after_ms` (int or None, default None), `suggested_action` (str or None, default None, one of "retry", "fix_input", "reauth", "escalate"), and `details` (dict, default empty). The `Warning` model has fields: `code` (str) and `message` (str). The `Metrics` model has fields: `duration_ms` (int) and optionally `operations_executed` (int or None) and `bytes_written` (int or None). The `Envelope` model has fields: `schema_version` (str, default "1.0"), `request_id` (str), `ok` (bool), `command` (str), `target` (dict or None, default None), `result` (Any, default None), `warnings` (list of Warning, default empty list), `errors` (list of ErrorDetail, default empty list), and `metrics` (Metrics). Provide a helper function `success_envelope(command, result, target=None, warnings=None, metrics=None)` that constructs a successful envelope with a generated `request_id` (use a timestamp plus random suffix, like `req_20260310_143000_a7f3`). Provide a helper function `error_envelope(command, errors, target=None, warnings=None, metrics=None)` that constructs a failed envelope. Provide a function `emit(envelope, format="json")` that serializes the envelope to stdout using `orjson` for JSON. The emit function must write exactly one JSON object to stdout with a trailing newline, nothing else. This follows CLI-MANIFEST.md principle 1 and 7.

Create `src/docweave/backends/__init__.py` (empty).

Create `src/docweave/backends/base.py`. This module defines the backend adapter interface as a Python abstract base class (ABC) called `BackendAdapter`. It has the following abstract properties: `name` (str), `tier` (str, one of "native-safe", "semantic-roundtrip", "extract-and-rewrite"), and `extensions` (list of str, the file extensions this backend handles, e.g. `[".md"]`). It has the following abstract methods, each documented with a one-line docstring:

    def detect(self, path: Path) -> float:
        """Return a confidence score 0.0-1.0 that this backend can handle the file."""

    def inspect(self, path: Path) -> dict:
        """Return structured metadata about the file's capabilities and structure."""

    def load_view(self, path: Path) -> "NormalizedDocument":
        """Parse the file and return a normalized document view."""

    def resolve_anchor(self, view: "NormalizedDocument", anchor: "Anchor") -> list["AnchorMatch"]:
        """Resolve an anchor against the document view and return matching locations."""

    def plan(self, view: "NormalizedDocument", operations: list["Operation"]) -> "ExecutionPlan":
        """Generate an execution plan for the given operations without writing."""

    def apply(self, path: Path, plan: "ExecutionPlan") -> "ApplyResult":
        """Execute a plan and return the result."""

    def validate(self, path: Path) -> "ValidationReport":
        """Validate the file's structural integrity."""

    def diff(self, before: "NormalizedDocument", after: "NormalizedDocument") -> "DiffReport":
        """Compute a diff between two document views."""

The type names in quotes (NormalizedDocument, Anchor, etc.) will be defined in Milestone 2. For now, use string forward references.

Create `src/docweave/backends/registry.py`. This module maintains a list of registered backend instances. It provides `register(backend: BackendAdapter)` to add a backend, `detect(path: Path) -> BackendAdapter` to find the best backend for a file by calling each registered backend's `detect` method and returning the one with the highest score (raising an error if none scores above 0.0), and `get(name: str) -> BackendAdapter` to retrieve a backend by name. Keep the registry as a module-level list. Provide an `init_backends()` function that imports and registers the built-in backends (initially empty; Milestone 2 will add the Markdown backend).

Create `src/docweave/cli.py`. This module defines the Typer application. Create a `typer.Typer` instance named `app`. Add a `--version` callback and a `--format` option (choices: json, yaml, text; default: json) stored via a Typer callback. Add a `guide` command that returns a JSON envelope containing, in the `result` field, a dictionary with: the CLI name, version, a list of all commands with their group (read or write), arguments, flags, and descriptions, the error code taxonomy, the exit code mapping, and concurrency rules. For now the command list will be partially populated — just `guide` and `inspect` — and will grow as milestones add commands. The guide command follows CLI-MANIFEST.md principle 4 (progressive discovery). Wrap the entire CLI in a try/except that catches all exceptions and emits a proper error envelope with code `ERR_INTERNAL_UNHANDLED` and exit code 90, so no command ever produces unstructured output.

Create `tests/__init__.py` (empty), `tests/conftest.py` with common fixtures (a `tmp_path` fixture is provided by pytest, add a helper that invokes the CLI as a subprocess and parses the JSON envelope from stdout), and `tests/fixtures/` directory.

Create `tests/test_envelope.py` with tests that verify: a success envelope has all required fields, an error envelope has `ok=false` and `result=null`, the `request_id` is always present and unique across calls, and `errors` and `warnings` are always lists (never None or missing).

Create `tests/test_cli.py` with tests that verify: `docweave --version` prints the version, `docweave guide --format json` returns valid JSON with an `ok=true` envelope, and an unknown command returns a proper error envelope (not a Typer traceback).

To validate this milestone, run the following from the repository root:

    uv venv .venv
    source .venv/bin/activate   # or .venv\Scripts\activate on Windows
    uv pip install -e ".[dev]"
    pytest tests/test_envelope.py tests/test_cli.py -v

All tests should pass. Running `docweave guide --format json` should print a single JSON object to stdout with `ok: true` and a `result` containing the command catalog. Running `docweave --version` should print `0.1.0`.


## Milestone 2: Markdown Backend — Parse, Inspect, View

After this milestone, you will be able to run `docweave inspect sample.md` and get back JSON describing the document's structure (number of blocks, headings, tables, etc., plus the backend name, tier, and capabilities), and run `docweave view sample.md` to get the full normalized block list.

Create `src/docweave/models.py`. This module defines the core data models used across the entire system. All models are Pydantic BaseModels.

`SourceSpan` has fields `start_line` (int, 1-based) and `end_line` (int, 1-based inclusive). It represents the line range in the original file that a block occupies.

`Block` has fields: `block_id` (str, a stable identifier like `"blk_001"`), `kind` (str, one of: `"heading"`, `"paragraph"`, `"ordered_list"`, `"unordered_list"`, `"table"`, `"code_block"`, `"blockquote"`, `"thematic_break"`, `"html_block"`, `"front_matter"`), `section_path` (list of str, the heading hierarchy leading to this block, e.g. `["Introduction", "Purpose"]`), `text` (str, the plain text content of the block with inline markup stripped), `raw_text` (str, the original source text of the block including markup), `level` (int or None, the heading level 1-6 for headings, None for other block types), `source_span` (SourceSpan), and `stable_hash` (str, the SHA-256 hex digest of the `raw_text`).

`NormalizedDocument` has fields: `file` (str, the file path), `backend` (str, the backend name), `blocks` (list of Block), and `metadata` (dict, optional additional metadata). It also has computed properties: `headings` returns only blocks where kind is "heading"; `block_count` returns len(blocks); `heading_count` returns len(headings).

`InspectResult` has fields: `file` (str), `backend` (str), `tier` (str), `editable` (bool), `supports` (dict mapping capability names to booleans or strings like "limited" or "read"), `fidelity` (dict with keys `write_mode` and `roundtrip_risk`), and `document_summary` (dict with keys `blocks`, `headings`, `tables`, `code_blocks`). This matches the inspect output example in PRD.md section 17.

Create `src/docweave/backends/markdown_native.py`. This module implements the `BackendAdapter` for Markdown files. The class is called `MarkdownBackend`.

The `detect` method checks the file extension against `.md` and `.markdown` and returns 1.0 for a match, 0.0 otherwise.

The `inspect` method calls `load_view` and then constructs an `InspectResult` from the view.

The `load_view` method is the core of this milestone. It works as follows:

First, read the file content as a UTF-8 string. Split it into lines (preserving the original line endings for reconstruction later).

Second, parse the content using `markdown-it-py`. Create a `MarkdownIt` instance with the default preset ("commonmark" is fine, or "default" for GFM-like features — use "commonmark" for strict behavior). Call `md.parse(content)` to get a list of Token objects.

Third, walk the token list and build Block objects. The tokens from markdown-it-py are a flat sequence of opening, content, and closing tokens. Block-level tokens have a `map` attribute that is a two-element list `[start_line, end_line)` where start_line is 0-based inclusive and end_line is 0-based exclusive. The algorithm is:

Iterate through the tokens. When you encounter a block-opening token (nesting == 1, and the type ends with `_open`), note its type and map. The corresponding close token (nesting == -1) will follow later. The text content of the block is found in inline tokens between open and close, or in the `content` attribute of certain tokens. Specifically:

For `heading_open` tokens: the map gives the line range. The next token is typically an `inline` token whose `content` attribute has the heading text. The `tag` attribute of the heading_open token is `"h1"` through `"h6"`, from which you extract the level as an integer.

For `paragraph_open` tokens: the map gives the line range. The next `inline` token's `content` has the paragraph text.

For `bullet_list_open` and `ordered_list_open` tokens: the map covers the entire list. Collect all the text from `list_item_open` children.

For `fence` (code fence) tokens: these are self-closing (nesting == 0) with a `map` attribute and a `content` attribute containing the code.

For `code_block` tokens: similar to fence.

For `table_open` tokens (if using the tables plugin): the map covers the whole table.

For `hr` tokens: thematic break, self-closing.

For `html_block` tokens: self-closing with content.

For `blockquote_open` tokens: the map covers the quoted content.

For each block, extract the `raw_text` by joining the original source lines from `start_line` to `end_line` (using the line range from the `map` attribute, remembering that `map` values are 0-based and `end_line` is exclusive). Compute `stable_hash` as `hashlib.sha256(raw_text.encode()).hexdigest()[:16]`. Generate `block_id` as `blk_` followed by a zero-padded three-digit sequence number.

Fourth, build the `section_path` for each block. Maintain a stack of current headings. When a heading of level N is encountered, pop the stack down to level N-1 and push this heading's text. For non-heading blocks, the section_path is the current stack contents.

Fifth, construct and return a `NormalizedDocument` with the file path, backend name `"markdown-native"`, and the block list.

Update `src/docweave/backends/registry.py` to import `MarkdownBackend` in `init_backends()` and register an instance.

Add two new commands to `src/docweave/cli.py`:

The `inspect` command takes a file path argument. It calls `init_backends()`, detects the backend, calls `inspect`, and returns the result in a success envelope. If the file does not exist, return an error envelope with code `ERR_IO_FILE_NOT_FOUND` and exit code 50. If no backend matches, return an error with code `ERR_VALIDATION_NO_BACKEND` and exit code 10.

The `view` command takes a file path argument. It calls `load_view` and returns the full NormalizedDocument (serialized via Pydantic's `model_dump()`) in a success envelope. Accept an optional `--section` flag that filters blocks to only those within a given section path.

Create `tests/fixtures/sample.md` with the following content:

    # Introduction

    This document describes the project.

    ## Purpose

    The purpose is to demonstrate docweave.

    ## Scope

    This section defines the scope.

    - Item one
    - Item two
    - Item three

    # Requirements

    ## Functional

    The system must do the following:

    1. Parse documents
    2. Resolve anchors
    3. Apply patches

    ## Non-Functional

    Performance must be acceptable.

    ---

    # Appendix

    Additional notes go here.

    ```python
    def example():
        return True
    ```

Create `tests/test_markdown_backend.py` with tests that verify:

The `detect` method returns 1.0 for a `.md` file and 0.0 for a `.txt` file.

The `load_view` method on `sample.md` produces a NormalizedDocument with the correct number of blocks. Specifically, it should find headings for "Introduction", "Purpose", "Scope", "Requirements", "Functional", "Non-Functional", and "Appendix" (7 headings). It should find paragraphs, a bullet list, an ordered list, a thematic break, and a code block.

Each block's `source_span` correctly maps back to the original lines: extracting `raw_text` from the source using the span should produce content that matches the block's `raw_text` field.

The `section_path` for the paragraph "The purpose is to demonstrate docweave." should be `["Introduction", "Purpose"]`.

The `section_path` for the paragraph "Performance must be acceptable." should be `["Requirements", "Non-Functional"]`.

Heading levels are correctly assigned: "Introduction" is level 1, "Purpose" is level 2.

The `stable_hash` for a block is deterministic: parsing the same file twice produces the same hashes.

The `inspect` method returns an InspectResult with `backend="markdown-native"`, `tier="native-safe"`, `editable=True`.

Create `tests/test_cli_inspect.py` with tests that invoke `docweave inspect tests/fixtures/sample.md --format json` as a subprocess and verify the envelope has `ok=true`, the result contains the expected heading count, and the backend is "markdown-native".

To validate this milestone:

    pytest tests/test_markdown_backend.py tests/test_cli_inspect.py -v

All tests should pass. Running `docweave inspect tests/fixtures/sample.md --format json` should produce output like:

    {
      "schema_version": "1.0",
      "request_id": "req_...",
      "ok": true,
      "command": "document.inspect",
      "result": {
        "file": "tests/fixtures/sample.md",
        "backend": "markdown-native",
        "tier": "native-safe",
        "editable": true,
        "supports": {"comments": false, "tables": true, "styles": false, "track_changes": false},
        "fidelity": {"write_mode": "native", "roundtrip_risk": "low"},
        "document_summary": {"blocks": 16, "headings": 7, "tables": 0, "code_blocks": 1}
      },
      "warnings": [],
      "errors": [],
      "metrics": {"duration_ms": 12}
    }


## Milestone 3: Anchor Resolution, Find, and Anchors Commands

After this milestone, you will be able to query a document for specific locations using structural, quote, and ordinal anchors. The `find` command will search for text across the document. The `anchors` command will resolve a specific anchor and return the matching locations with confidence information. These are the building blocks that the plan/apply pipeline in Milestone 4 depends on.

Create `src/docweave/anchors/__init__.py` (empty).

Create `src/docweave/anchors/models.py`. Define the following Pydantic models:

`Anchor` has fields: `by` (str, one of "heading", "quote", "ordinal", "table", "block_id"), `value` (str, the search value — a heading name for "heading", a text excerpt for "quote", a block_id for "block_id"), `occurrence` (int, default 1, which match to select when multiple exist), `context_before` (str or None, for quote anchors), `context_after` (str or None, for quote anchors), `section` (str or None, for ordinal anchors — limit search to this section), and `index` (int or None, for ordinal anchors — the nth block of a given kind within a section).

`AnchorMatch` has fields: `block_id` (str), `block_kind` (str), `source_span` (SourceSpan), `confidence` (float, 0.0-1.0), `match_type` (str, which anchor strategy was used), and `context` (str, a short text excerpt around the match for display).

Create `src/docweave/anchors/resolver.py`. This module provides the `resolve_anchor(view: NormalizedDocument, anchor: Anchor) -> list[AnchorMatch]` function. It dispatches to strategy-specific functions based on `anchor.by`:

For `by="heading"`: iterate the blocks in the view. For each block with `kind=="heading"`, compare its text to `anchor.value`. Use case-insensitive exact match first; if no exact match, try substring match; if no substring match, try fuzzy matching (simple: check if the anchor value words all appear in the heading text). Return matches sorted by confidence (exact=1.0, substring=0.8, fuzzy=0.5). If `anchor.occurrence` is specified, return only that numbered match (1-based). If `anchor.section` is specified, only search within that section's descendants.

For `by="quote"`: iterate all blocks. For each block, check if `anchor.value` appears as a substring of the block's text. If `context_before` is given, verify it also appears in the block's text before the matched substring. If `context_after` is given, verify it appears after. Score exact substring match with correct context as 1.0, substring without context as 0.7.

For `by="ordinal"`: if `anchor.section` is given, find the blocks under that section. Then filter by kind (if `anchor.value` is a kind like "paragraph") and return the `anchor.index`-th match (1-based).

For `by="block_id"`: direct lookup by block_id. Return confidence 1.0 if found.

For `by="table"`: iterate blocks with `kind=="table"`. Match by table caption or the text of the first row. This is a basic implementation for MVP; the DOCX backend will need richer table semantics later.

The function returns a list of `AnchorMatch` objects. An empty list means the anchor did not resolve. Multiple matches mean the anchor is ambiguous.

Add the `resolve_anchor` method to `MarkdownBackend` in `markdown_native.py` by delegating to the resolver function.

Add two new commands to `src/docweave/cli.py`:

The `find` command takes a file path and a query string. It calls `load_view`, then searches all blocks for the query (case-insensitive substring match). It returns in the envelope's result a list of matching blocks with their block_id, kind, section_path, source_span, and a snippet of the matching text (truncated to 200 characters). This is a simple search, not anchor resolution.

The `anchors` command takes a file path and an anchor specification. The anchor spec is provided as a string in the format `"type:value"` (e.g., `"heading:Purpose"` or `"quote:must immediately"`). The command parses this into an Anchor object, calls `resolve_anchor`, and returns the list of AnchorMatch objects in the envelope. If the anchor is ambiguous (multiple matches), include a warning with code `WARN_ANCHOR_AMBIGUOUS`. If the anchor does not resolve, return an error with code `ERR_VALIDATION_ANCHOR_NOT_FOUND` and exit code 10.

Create `tests/test_anchors.py` with tests that verify:

A heading anchor `"heading:Purpose"` resolves to the "Purpose" heading in `sample.md` with confidence 1.0.

A heading anchor `"heading:purpose"` (lowercase) also resolves with high confidence due to case-insensitive matching.

A heading anchor `"heading:Nonexistent"` returns an empty match list.

A quote anchor `"quote:demonstrate docweave"` resolves to the paragraph "The purpose is to demonstrate docweave." with the correct block_id and source_span.

A quote anchor with `context_before="purpose is"` and value `"demonstrate"` and `context_after="docweave"` resolves with confidence 1.0.

An ordinal anchor `by="ordinal", value="paragraph", section="Scope", index=1` resolves to the paragraph "This section defines the scope."

A block_id anchor resolves to the block with that exact ID.

When multiple headings match (e.g., if the document had two "Purpose" headings), the `occurrence` field selects which one.

Create `tests/test_cli_find.py` with a test that invokes `docweave find tests/fixtures/sample.md "demonstrate" --format json` and verifies the envelope contains one match with the correct block info.

To validate this milestone:

    pytest tests/test_anchors.py tests/test_cli_find.py -v

All tests should pass. Running `docweave anchors tests/fixtures/sample.md "heading:Purpose" --format json` should return a successful envelope with one match at the correct line range.


## Milestone 4: Plan & Apply Pipeline with Patch Schema

After this milestone, you will be able to write a YAML patch file describing operations like `insert_after`, `replace_text`, and `delete_block`, run `docweave plan` to preview what would happen, and run `docweave apply` to execute the edits with atomic writes and automatic backups. This is the core of the product: anchor-based patching of Markdown documents.

Create `src/docweave/plan/__init__.py` (empty).

Create `src/docweave/plan/schema.py`. Define Pydantic models for the patch file format:

`PatchContent` has fields: `kind` (str, the format of the content, e.g. "markdown" or "text") and `value` (str, the actual content to insert).

`OperationSpec` has fields: `id` (str, a unique ID for this operation like "op1"), `op` (str, one of: "insert_before", "insert_after", "replace_block", "replace_text", "delete_block", "set_heading", "normalize_whitespace"), `anchor` (Anchor, the location target), `content` (PatchContent or None, for insert and replace operations), and `replacement` (str or None, for replace_text — the string to substitute).

`PatchFile` has fields: `version` (int, must be 1), `target` (dict with keys `file` (str) and `backend` (str, default "auto")), and `operations` (list of OperationSpec).

Provide a function `load_patch(path: Path) -> PatchFile` that reads a YAML file and parses it into a PatchFile model. If the YAML is invalid, raise a validation error with code `ERR_VALIDATION_PATCH_SCHEMA`.

Create `src/docweave/plan/planner.py`. This module contains the planning logic:

`ResolvedOperation` has fields: `operation` (OperationSpec), `anchor_match` (AnchorMatch), `action_description` (str, a human-readable summary like "Insert 3 lines after heading 'Purpose' at line 5"), and `affected_lines` (SourceSpan, the lines that will be modified or displaced).

`ExecutionPlan` has fields: `file` (str), `fingerprint` (str, SHA-256 of the file content at planning time), `backend` (str), `resolved_operations` (list of ResolvedOperation), `warnings` (list of str), and `valid` (bool, whether all operations resolved successfully).

The `generate_plan(path: Path, patch: PatchFile, backend: BackendAdapter) -> ExecutionPlan` function works as follows:

Read the file and compute its SHA-256 fingerprint. Call `load_view` to get the normalized document. For each operation in the patch, call `resolve_anchor` to find the target location. If the anchor does not resolve, mark the plan as invalid and add an error description. If the anchor is ambiguous and `--strict` mode is on (passed as a parameter), mark as invalid. Otherwise, pick the highest-confidence match and add a warning. Build a `ResolvedOperation` for each successful resolution, including a human-readable description of what will happen.

Return the `ExecutionPlan`. If all operations resolved, `valid` is True.

Create `src/docweave/plan/applier.py`. This module applies an execution plan to a file:

The `apply_plan(path: Path, plan: ExecutionPlan, backup: bool = False) -> ApplyResult` function works as follows:

First, read the current file and compute its fingerprint. Compare to `plan.fingerprint`. If they differ, raise a conflict error with code `ERR_CONFLICT_FINGERPRINT` and exit code 40. This is CLI-MANIFEST.md principle 18.

If `backup` is True, copy the file to `<filename>.<ISO-timestamp>.bak` in the same directory.

Split the file content into lines. Sort the resolved operations by their affected line numbers in descending order (bottom to top). This is critical: applying edits from the bottom of the file upward means that line-number references for earlier operations remain valid even after later operations insert or delete lines.

For each resolved operation, apply it:

`insert_after`: the anchor match gives the block's source span. Take the end_line of that span. Insert the new content lines immediately after that line.

`insert_before`: take the start_line of the anchor's source span. Insert the new content lines immediately before that line.

`replace_block`: remove all lines from start_line to end_line of the anchor's source span, then insert the new content lines at that position.

`replace_text`: within the lines of the anchor's source span, find the old text (the operation's `anchor.value` for quote anchors, or the `replacement` source) and replace it with `operation.replacement`. This operates on the raw text of the affected lines.

`delete_block`: remove all lines from start_line to end_line.

`set_heading`: replace the heading line(s) with a new heading using the appropriate Markdown syntax (e.g., `## New Heading`).

`normalize_whitespace`: collapse multiple blank lines into single blank lines within the affected range.

After all operations, join the lines back into a string. Write the result using atomic write: write to a temporary file in the same directory (name it `.docweave_tmp_<random>`), flush and sync, then rename it over the original file. On Windows, use `os.replace()` which is atomic. On failure, delete the temp file.

`ApplyResult` has fields: `file` (str), `operations_applied` (int), `fingerprint_before` (str), `fingerprint_after` (str), `backup_path` (str or None), and `warnings` (list of str).

Add the `plan` and `apply` methods to `MarkdownBackend` in `markdown_native.py` by delegating to the planner and applier modules.

Add two new commands to `src/docweave/cli.py`:

The `plan` command takes a file path and a `-p` / `--patch` option pointing to a YAML patch file. It loads the patch, generates the plan, and returns the plan in the envelope's result. If the plan is invalid (unresolved anchors), set `ok=false` and include the errors. The plan is always a read-only operation. Accept an optional `--out` flag to write the plan to a JSON file for later use with `apply`.

The `apply` command takes a file path and either `-p` / `--patch` (patch YAML) or `--plan` (a previously generated plan JSON file). If given a patch, it generates the plan internally first. It supports `--dry-run` (acts like `plan` — does everything except write), `--backup` (creates a timestamped backup), and `--strict` (rejects ambiguous anchors). On success, the envelope's result contains the ApplyResult.

Create `tests/fixtures/patch_insert_after.yaml`:

    version: 1
    target:
      file: sample.md
      backend: auto
    operations:
      - id: op1
        op: insert_after
        anchor:
          by: heading
          value: Purpose
          occurrence: 1
        content:
          kind: markdown
          value: |
            This is a new paragraph inserted after the Purpose heading section.

Create `tests/fixtures/patch_replace_text.yaml`:

    version: 1
    target:
      file: sample.md
      backend: auto
    operations:
      - id: op1
        op: replace_text
        anchor:
          by: quote
          value: "demonstrate docweave"
          context_before: "purpose is to"
        replacement: "showcase the docweave CLI"

Create `tests/fixtures/patch_delete_block.yaml`:

    version: 1
    target:
      file: sample.md
      backend: auto
    operations:
      - id: op1
        op: delete_block
        anchor:
          by: heading
          value: Appendix
          occurrence: 1

Create `tests/test_plan_apply.py` with tests that verify:

Planning with `patch_insert_after.yaml` against `sample.md` produces a valid plan with one resolved operation targeting the "Purpose" heading, and the plan's fingerprint matches the SHA-256 of the file.

Planning with an anchor that does not exist produces an invalid plan with `ok=false`.

Applying `patch_insert_after.yaml` to a copy of `sample.md` (use `tmp_path` to avoid modifying the fixture) inserts the new paragraph after the "Purpose" section. After applying, re-parsing the file with `load_view` should find a new paragraph block with text containing "new paragraph inserted."

Applying `patch_replace_text.yaml` replaces "demonstrate docweave" with "showcase the docweave CLI" in the output file. The rest of the file is unchanged.

Applying `patch_delete_block.yaml` removes the "Appendix" heading and the content below it (the paragraph and code block). The resulting file should have fewer blocks.

The `--backup` flag creates a `.bak` file alongside the modified file.

The `--dry-run` flag on apply returns the plan but does not modify the file (verify by checking the file's content is unchanged after the command).

Fingerprint conflict detection works: modify the file after planning, then attempt to apply the saved plan. The command should fail with `ERR_CONFLICT_FINGERPRINT` and exit code 40.

Multiple operations in one patch are applied correctly. Create a test with a patch that inserts after "Purpose" and replaces text in "Scope". Both should succeed, and the file should reflect both changes.

To validate this milestone:

    pytest tests/test_plan_apply.py -v

All tests should pass. Run the following end-to-end sequence manually to see the full workflow:

    cp tests/fixtures/sample.md /tmp/test_doc.md
    docweave inspect /tmp/test_doc.md --format json
    docweave plan /tmp/test_doc.md -p tests/fixtures/patch_insert_after.yaml --format json
    docweave apply /tmp/test_doc.md -p tests/fixtures/patch_insert_after.yaml --backup --format json
    cat /tmp/test_doc.md   # should show the inserted paragraph

On Windows, substitute appropriate paths like `$env:TEMP/test_doc.md` and use `copy` instead of `cp`.


## Milestone 5: Diff, Validation, Evidence Bundle, and Journal

After this milestone, you will be able to run `docweave diff before.md after.md` to see structural differences between two documents, `docweave validate file.md` to check structural integrity, and every apply operation will produce a transaction journal entry and optionally an evidence bundle. This completes the verification and auditability story from the PRD.

Create `src/docweave/diff/__init__.py` (empty).

Create `src/docweave/diff/raw.py`. This module provides a `raw_diff(before_text: str, after_text: str) -> list[DiffHunk]` function using Python's built-in `difflib.unified_diff`. A `DiffHunk` model has fields: `start_line_before` (int), `count_before` (int), `start_line_after` (int), `count_after` (int), and `lines` (list of str, the unified diff lines with +/- prefixes).

Create `src/docweave/diff/semantic.py`. This module provides a `semantic_diff(before: NormalizedDocument, after: NormalizedDocument) -> SemanticDiffReport` function. It compares the two documents block by block. The `SemanticDiffReport` model has fields: `sections_added` (list of str), `sections_removed` (list of str), `blocks_added` (int), `blocks_removed` (int), `blocks_modified` (int), `headings_changed` (list of dict with before/after), `summary` (str, a one-sentence human-readable description like "1 section inserted, 2 paragraphs rewritten, 1 heading renamed"). The comparison algorithm matches blocks by their `stable_hash` and `block_id`. Blocks present in `after` but not in `before` (by hash) are counted as added. Blocks in `before` but not in `after` are removed. Blocks where the block_id matches but the hash changed are modified.

Create `src/docweave/diff/models.py` for the DiffHunk and SemanticDiffReport models if they are not already defined inline.

Add the `diff` method to `MarkdownBackend` by delegating to the semantic diff module.

Add the `diff` command to `src/docweave/cli.py`. It takes two file paths (before and after). It loads both files via the backend's `load_view`, computes both the raw diff and the semantic diff, and returns both in the envelope's result.

Add the `validate` command to `src/docweave/cli.py`. It takes a file path. It calls the backend's `load_view` and performs structural checks: are all headings properly nested (no skipping levels, e.g., jumping from h1 to h3)? Are all block source spans non-overlapping and covering the whole file? Are there any zero-length blocks? Return a `ValidationReport` with a `valid` boolean, a list of `issues` (each with a severity, message, and location), and the block count.

Create `src/docweave/journal.py`. This module manages the transaction journal. The journal is stored as a JSON Lines file (one JSON object per line) at `.docweave-journal/journal.jsonl` relative to the file being edited (i.e., in the same directory as the target file). Each entry has fields: `txn_id` (str, a UUID), `timestamp` (str, ISO 8601), `file` (str), `backend` (str), `operations` (list of operation IDs), `fingerprint_before` (str), `fingerprint_after` (str), `operations_applied` (int), `warnings` (list of str), and `validation_result` (str, "pass" or "fail" or "skipped"). Provide `record_transaction(entry: JournalEntry)` to append to the journal and `get_transaction(txn_id: str) -> JournalEntry` to look up a specific entry. Provide `list_transactions(file: str) -> list[JournalEntry]` to list all entries for a file.

Add the `journal` command to `src/docweave/cli.py`. It takes an optional transaction ID. If given, return that specific journal entry. If not given, list recent entries. Accept a `--file` flag to filter by file path.

Create `src/docweave/evidence/__init__.py` (empty).

Create `src/docweave/evidence/bundle.py`. This module writes an evidence bundle to a directory. The `write_evidence_bundle(dir: Path, before_view: NormalizedDocument, after_view: NormalizedDocument, plan: ExecutionPlan, semantic_diff: SemanticDiffReport, raw_diff: list[DiffHunk])` function creates the directory if needed and writes: `before_view.json`, `after_view.json`, `plan.json`, `semantic_diff.json`, `raw_diff.txt` (the unified diff as plain text), and `summary.json` (a combined summary with timestamp, file, operations count, and diff summary).

Update the `apply` command to optionally accept `--evidence-dir <path>`. When provided, after a successful apply, compute the after-view by re-parsing the file, compute both diffs, and write the evidence bundle. Also record a journal entry for every apply (evidence or not).

Create `tests/test_diff.py` with tests that verify: the raw diff between two strings produces the correct hunks; the semantic diff between two NormalizedDocuments correctly counts added, removed, and modified blocks; the summary string is formatted correctly.

Create `tests/test_journal.py` with tests that verify: recording a transaction creates the journal file; the entry can be retrieved by txn_id; listing transactions for a file returns the correct entries.

Create `tests/test_evidence.py` with a test that applies a patch with `--evidence-dir` and verifies that the evidence directory contains the expected files with valid JSON content.

To validate this milestone:

    pytest tests/test_diff.py tests/test_journal.py tests/test_evidence.py -v

All tests should pass. Run an end-to-end evidence bundle test:

    cp tests/fixtures/sample.md /tmp/test_doc.md
    docweave apply /tmp/test_doc.md -p tests/fixtures/patch_insert_after.yaml --evidence-dir /tmp/evidence --format json
    ls /tmp/evidence/   # should contain before_view.json, after_view.json, plan.json, etc.

Inspect the journal:

    docweave journal --file /tmp/test_doc.md --format json


## Milestone 6: Text Backend to Prove Pluggability

After this milestone, you will be able to use all the same commands (inspect, view, find, anchors, plan, apply, diff, validate) on plain `.txt` files. This proves that the backend-pluggable architecture works: the CLI surface is stable, only the backend changes.

Create `src/docweave/backends/text_native.py`. The `TextBackend` class implements `BackendAdapter`.

The `detect` method returns 1.0 for `.txt` files and 0.0 otherwise.

The `load_view` method is simpler than the Markdown backend. Read the file and split into lines. Group consecutive non-blank lines into paragraph blocks. Blank lines are block separators. Lines that start with `#` are not treated as headings in plain text (there is no heading syntax). Every block's kind is `"paragraph"`. Section paths are empty since there is no heading structure. Compute source spans and stable hashes as before.

The `inspect` method returns an InspectResult with `backend="text-native"`, `tier="native-safe"`, `editable=True`, and `supports` showing no comments, no tables, no styles.

For anchor resolution, `by="heading"` always returns empty (plain text has no headings). `by="quote"` works the same as the Markdown backend — search for text substrings. `by="ordinal"` works by counting paragraph blocks. `by="block_id"` works as before.

The `plan` and `apply` methods reuse the same planner and applier logic from the plan module, since those operate on source lines and are backend-agnostic.

The `diff` and `validate` methods work analogously to the Markdown backend.

Register `TextBackend` in `init_backends()`.

Create `tests/fixtures/sample.txt`:

    This is the first paragraph of the
    plain text document. It spans two lines.

    This is the second paragraph.

    This is the third paragraph with some
    specific text we can search for.

Create `tests/fixtures/patch_txt_replace.yaml`:

    version: 1
    target:
      file: sample.txt
      backend: auto
    operations:
      - id: op1
        op: replace_text
        anchor:
          by: quote
          value: "specific text"
        replacement: "particular content"

Create `tests/test_text_backend.py` with tests that verify:

The `detect` method returns 1.0 for `.txt` and 0.0 for `.md`.

The `load_view` on `sample.txt` produces three paragraph blocks.

Each block's source_span maps to the correct lines.

The `inspect` method returns the correct backend name and tier.

A quote anchor resolves correctly in the text backend.

Applying `patch_txt_replace.yaml` replaces "specific text" with "particular content" in the output file.

The same CLI commands work: `docweave inspect sample.txt`, `docweave view sample.txt`, `docweave find sample.txt "specific"`, all produce valid envelopes.

To validate this milestone:

    pytest tests/test_text_backend.py -v

Run the full test suite to confirm nothing is broken:

    pytest -v

All tests across all milestones should pass. Run the key demonstration:

    docweave inspect tests/fixtures/sample.txt --format json
    docweave inspect tests/fixtures/sample.md --format json

Both should return valid envelopes with different backend names ("text-native" vs "markdown-native") but the same envelope structure. This proves the one-protocol-many-backends architecture from the PRD.


## Validation and Acceptance

The plan is complete when all of the following hold:

Running `pytest -v` from the repository root executes all tests and they pass. There should be tests covering: envelope construction, CLI entry points (guide, version, inspect, view, find, anchors, plan, apply, diff, validate, journal), Markdown backend parsing, text backend parsing, anchor resolution (structural, quote, ordinal, block_id), plan generation, plan application (insert, replace, delete), dry-run mode, backup creation, fingerprint conflict detection, raw and semantic diff, journal recording and retrieval, and evidence bundle writing.

Running `docweave guide --format json` returns a complete command catalog that an agent can use to discover all available commands, their arguments, and error codes without reading external documentation.

Running the following end-to-end sequence on a fresh copy of `sample.md` succeeds:

    docweave inspect <file> --format json
    docweave view <file> --format json
    docweave find <file> "demonstrate" --format json
    docweave anchors <file> "heading:Purpose" --format json
    docweave plan <file> -p patch_insert_after.yaml --format json
    docweave apply <file> -p patch_insert_after.yaml --backup --evidence-dir ./evidence --format json
    docweave diff <original> <modified> --format json
    docweave validate <modified> --format json
    docweave journal --file <file> --format json

Every command in that sequence returns a JSON envelope with `schema_version`, `request_id`, `ok`, `command`, `result`, `errors`, `warnings`, and `metrics`. No command produces unstructured output on stdout. Errors are always structured with a `code` field. Exit codes follow the 0/10/20/40/50/90 contract.

The same sequence works for `.txt` files using the text backend, proving backend pluggability.


## Idempotence and Recovery

Every milestone is safe to run multiple times. The `uv pip install -e ".[dev]"` command is idempotent. Tests use `tmp_path` fixtures to avoid modifying source fixtures. The `apply` command with `--backup` creates a timestamped backup before writing, so the original can always be restored. If a milestone partially fails, you can re-run the tests to see which parts pass and which need attention. The git repository provides rollback to any prior commit.

If the `apply` command fails mid-write (e.g., due to a crash), the atomic write strategy ensures the original file is intact: the temp file will be left behind (named `.docweave_tmp_*`) and can be deleted. The original file is never written to directly.

If you need to restart a milestone, delete any generated files (the source code you wrote for that milestone) and start fresh from the milestone's description.


## Interfaces and Dependencies

Runtime dependencies, all installed via `pyproject.toml`:

`typer[all]>=0.15` provides the CLI framework. Typer is built on Click and adds type-hint-based parameter declaration. The `[all]` extra includes `rich` and `shellingham` for terminal detection. Import as `import typer`.

`pydantic>=2.0` provides data validation and JSON serialization for all models (envelope, blocks, anchors, patches, plans). Import as `from pydantic import BaseModel`. Use `model.model_dump()` for dict conversion and `model.model_dump_json()` for JSON strings.

`orjson>=3.9` provides fast JSON serialization. Used in the envelope's `emit` function for writing JSON to stdout. Import as `import orjson`. Use `orjson.dumps(data, option=orjson.OPT_INDENT_2)` for pretty-printed JSON.

`markdown-it-py>=3.0` provides Markdown parsing. Import as `from markdown_it import MarkdownIt`. Use `md = MarkdownIt("commonmark")` and `tokens = md.parse(content)`. Each token has attributes: `type` (str), `tag` (str), `nesting` (int: 1=open, 0=self-close, -1=close), `map` (list of two ints: [start_line, end_line) 0-based), `content` (str), `children` (list of Token or None), `markup` (str), and `info` (str, for fence language). Block tokens with `map` not None are the ones we use for building the normalized view.

`pyyaml>=6.0` provides YAML parsing for patch files. Import as `import yaml`. Use `yaml.safe_load(f)` to parse.

`rich>=13.0` is included via `typer[all]` and used for stderr progress output when the terminal is interactive. Never write Rich output to stdout; stdout is exclusively for the JSON envelope.

Development dependencies:

`pytest>=8.0` for testing. Run as `pytest -v` from the repo root.

`pytest-cov>=5.0` for coverage reporting. Run as `pytest --cov=docweave --cov-report=term-missing`.

`ruff>=0.8` for linting and formatting. Run as `ruff check src/ tests/` and `ruff format src/ tests/`.

Key interfaces defined in this plan:

In `src/docweave/backends/base.py`, the `BackendAdapter` abstract base class with methods: `detect`, `inspect`, `load_view`, `resolve_anchor`, `plan`, `apply`, `validate`, `diff`.

In `src/docweave/envelope.py`, the `Envelope` Pydantic model and the `emit(envelope, format)` function.

In `src/docweave/models.py`, the `Block`, `SourceSpan`, `NormalizedDocument`, and `InspectResult` Pydantic models.

In `src/docweave/anchors/models.py`, the `Anchor` and `AnchorMatch` Pydantic models.

In `src/docweave/plan/schema.py`, the `PatchFile`, `OperationSpec`, and `PatchContent` Pydantic models.

In `src/docweave/plan/planner.py`, the `ExecutionPlan` and `ResolvedOperation` models and the `generate_plan` function.

In `src/docweave/plan/applier.py`, the `ApplyResult` model and the `apply_plan` function.


## Artifacts and Notes

The final file tree after all milestones will be:

    docweave/
      .gitignore
      pyproject.toml
      PRD.md
      EXEC-PLAN.md
      CLI-MANIFEST.md
      SCAFFOLD.md
      EXECPLAN-foundations-markdown-mvp.md
      src/docweave/
        __init__.py
        cli.py
        config.py
        envelope.py
        models.py
        journal.py
        backends/
          __init__.py
          base.py
          registry.py
          markdown_native.py
          text_native.py
        anchors/
          __init__.py
          models.py
          resolver.py
        plan/
          __init__.py
          schema.py
          planner.py
          applier.py
        diff/
          __init__.py
          raw.py
          semantic.py
        evidence/
          __init__.py
          bundle.py
      tests/
        __init__.py
        conftest.py
        fixtures/
          sample.md
          sample.txt
          patch_insert_after.yaml
          patch_replace_text.yaml
          patch_delete_block.yaml
          patch_txt_replace.yaml
        test_envelope.py
        test_cli.py
        test_cli_inspect.py
        test_cli_find.py
        test_markdown_backend.py
        test_text_backend.py
        test_anchors.py
        test_plan_apply.py
        test_diff.py
        test_journal.py
        test_evidence.py

This plan does not cover the HTML backend, DOCX backend, review mode, reference-driven rewrite mode, or policy engine. Those are future ExecPlans corresponding to PRD.md Phases 2-5.
