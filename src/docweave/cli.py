"""Docweave CLI entry point."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click.exceptions
import typer

from docweave import __version__
from docweave.backends.base import BackendAdapter
from docweave.backends.registry import detect as detect_backend
from docweave.backends.registry import init_backends
from docweave.config import ExitCode, RuntimeConfig, detect_config
from docweave.envelope import (
    ErrorDetail,
    Warning,
    emit,
    error_envelope,
    make_envelope,
    success_envelope,
)
from docweave.models import NormalizedDocument

app = typer.Typer(
    name="docweave",
    no_args_is_help=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

_runtime_config: RuntimeConfig | None = None


def _version_callback(value: bool) -> None:
    if value:
        envelope = success_envelope("version", {"version": __version__})
        emit(envelope)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _callback(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format (currently only 'json').",
    ),
) -> None:
    """Docweave: agent-first structured document editing."""
    if format != "json":
        _known_commands = {
            "guide", "inspect", "view", "find", "anchor",
            "plan", "apply", "diff", "validate", "journal",
        }
        if format in _known_commands:
            msg = (
                f"It looks like you meant to run the '{format}' command. "
                f"Use: docweave {format} (--format must come before the subcommand with a value)."
            )
        else:
            msg = f"Unsupported format: {format!r}. Only 'json' is supported."
        envelope = error_envelope(
            "unknown",
            [ErrorDetail(code="ERR_VALIDATION", message=msg)],
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)
    global _runtime_config  # noqa: PLW0603
    _runtime_config = detect_config(format_override=format)

    if ctx.invoked_subcommand is None:
        envelope = error_envelope(
            "unknown",
            [ErrorDetail(
                code="ERR_VALIDATION",
                message="No command specified. Run with --help for usage.",
            )],
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)


def _load_document(
    command_name: str, file: Path,
) -> tuple[BackendAdapter, NormalizedDocument]:
    """Shared file-exists + init_backends + detect_backend + load_view helper."""
    if not file.exists():
        envelope = error_envelope(
            command_name,
            [ErrorDetail(code="ERR_IO_FILE_NOT_FOUND", message=f"File not found: {file}")],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.IO)

    if file.is_dir():
        envelope = error_envelope(
            command_name,
            [ErrorDetail(
                code="ERR_IO_IS_DIRECTORY",
                message=f"Path is a directory, not a file: {file}",
            )],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.IO)

    init_backends()
    try:
        backend = detect_backend(file)
    except ValueError:
        envelope = error_envelope(
            command_name,
            [ErrorDetail(
                code="ERR_VALIDATION_NO_BACKEND",
                message=f"No backend can handle: {file}",
            )],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    try:
        doc = backend.load_view(file)
    except IsADirectoryError:
        envelope = error_envelope(
            command_name,
            [ErrorDetail(
                code="ERR_IO_IS_DIRECTORY",
                message=f"Path is a directory, not a file: {file}",
            )],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.IO)
    except PermissionError:
        envelope = error_envelope(
            command_name,
            [ErrorDetail(code="ERR_PERMISSION", message=f"Permission denied: {file}")],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.PERMISSION)
    except (UnicodeDecodeError, ValueError) as exc:
        envelope = error_envelope(
            command_name,
            [ErrorDetail(
                code="ERR_VALIDATION_DECODE",
                message=f"Cannot decode file: {file} ({exc})",
            )],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    return backend, doc


@app.command()
def guide() -> None:
    """Show command catalog, error codes, and exit codes."""
    t0 = time.monotonic()
    result = {
        "cli": "docweave",
        "version": __version__,
        "commands": {
            "guide": {
                "description": "Show command catalog, error codes, and exit codes.",
                "status": "available",
                "result_schema": {
                    "cli": "string",
                    "version": "string",
                    "commands": (
                        "object — per-command descriptor with"
                        " description, status, result_schema"
                    ),
                    "error_codes": "object",
                    "exit_codes": "object",
                    "patch_schema": "object",
                },
            },
            "inspect": {
                "description": "Return structural metadata about a document.",
                "status": "available",
                "options": {
                    "--tag": "Filter headings to those whose annotations contain this tag "
                        "(case-insensitive match against annotations.tags list).",
                },
                "result_schema": {
                    "file": "string",
                    "backend": "string",
                    "tier": "string",
                    "editable": "boolean",
                    "block_count": "integer",
                    "headings": (
                        "array[HeadingInfo] — {text, level, block_id,"
                        " section_path, annotations}"
                    ),
                    "supports": "object — {comments, tables, styles, track_changes}",
                    "fidelity": "object — {write_mode, roundtrip_risk}",
                },
            },
            "view": {
                "description": "Return the full normalized block list for a document.",
                "status": "available",
                "options": {
                    "--section": "Filter by section name (matches any hierarchy level).",
                    "--tag": "Filter to sections whose headings have this annotation tag "
                        "(case-insensitive match against annotations.tags list).",
                },
                "result_schema": {
                    "blocks": (
                        "array[Block] — {block_id, kind, section_path,"
                        " text, raw_text, level, source_span, stable_hash,"
                        " annotations}"
                    ),
                    "block_count": "integer",
                },
            },
            "find": {
                "description": "Search blocks for a text query.",
                "status": "available",
                "result_schema": {
                    "query": "string",
                    "results": "array[Block]",
                    "count": "integer",
                },
            },
            "anchor": {
                "description": "Resolve an anchor spec to a specific block.",
                "status": "available",
                "result_schema": {
                    "spec": "string",
                    "matches": "array[AnchorMatch] — {block, confidence, match_reason}",
                    "count": "integer",
                },
            },
            "plan": {
                "description": "Preview an execution plan from a YAML patch file.",
                "status": "available",
                "result_schema": {
                    "file": "string",
                    "backend": "string",
                    "fingerprint": "string — SHA-256 of file at plan time",
                    "valid": "boolean",
                    "resolved_operations": (
                        "array[ResolvedOp] —"
                        " {operation, anchor_match, affected_lines}"
                    ),
                    "warnings": "array[string]",
                },
            },
            "apply": {
                "description": "Apply a patch or execution plan to a document.",
                "status": "available",
                "result_schema": {
                    "file": "string",
                    "operations_applied": "integer",
                    "fingerprint_before": "string",
                    "fingerprint_after": "string",
                    "backup_path": "string | null",
                    "journal_txn_id": "string | null",
                    "semantic_summary": "object — {added, removed, changed, unchanged}",
                    "evidence_dir": "string | null — only present when --evidence-dir was set",
                },
            },
            "fleet": {
                "description": (
                    "Apply multiple self-describing patch files"
                    " to their respective target documents."
                ),
                "status": "available",
                "result_schema": {
                    "total": "integer",
                    "succeeded": "integer",
                    "failed": "integer",
                    "dry_run": "boolean",
                    "parallel": "boolean",
                    "results": (
                        "array[FleetResult] — {patch, file, ok,"
                        " ops_applied, dry_run, error?,"
                        " fingerprint_before?, fingerprint_after?}"
                    ),
                },
            },
            "diff": {
                "description": "Compute raw and semantic diff between two documents.",
                "status": "available",
                "result_schema": {
                    "raw_diff": (
                        "array[RawHunk] —"
                        " {old_start, old_count, new_start, new_count, lines}"
                    ),
                    "semantic_diff": "object — {summary, changes: array[BlockChange]}",
                },
            },
            "validate": {
                "description": "Validate structural integrity of a document.",
                "status": "available",
                "result_schema": {
                    "valid": "boolean",
                    "issues": "array[ValidationIssue] — {code, message, block_id?}",
                    "block_count": "integer",
                },
            },
            "journal": {
                "description": "List or retrieve transaction journal entries.",
                "status": "available",
                "result_schema": {
                    "entries": (
                        "array[JournalEntry] — {txn_id, timestamp, file,"
                        " backend, operations, fingerprint_before,"
                        " fingerprint_after, operations_applied,"
                        " warnings, validation_result}"
                    ),
                    "count": "integer",
                    "note": (
                        "When called with a transaction ID,"
                        " returns {entry: JournalEntry} instead."
                    ),
                },
            },
        },
        "error_codes": {
            "ERR_VALIDATION": "Input failed validation (bad args, missing file, schema error).",
            "ERR_PERMISSION": "Insufficient permissions to read or write target.",
            "ERR_CONFLICT": "Fingerprint mismatch — file changed since last read.",
            "ERR_IO": "File-system I/O failure.",
            "ERR_INTERNAL_UNHANDLED": "Unexpected internal error.",
        },
        "exit_codes": {
            "0": "Success",
            "10": "Validation error",
            "20": "Permission error",
            "40": "Conflict error",
            "50": "I/O error",
            "90": "Internal error",
        },
        "concurrency": "All read commands are safe to run concurrently. "
        "Mutation commands (apply) use atomic writes with fingerprint checks.",
        "patch_schema": {
            "description": "YAML patch file format for plan and apply commands.",
            "note": "--format must come BEFORE the subcommand "
                "(e.g. docweave --format json apply).",
            "fields": {
                "version": "Integer, must be 1.",
                "target": "Dict with format metadata (e.g. {format: markdown}).",
                "operations": "List of operation specs.",
            },
            "operation_types": [
                "insert_after", "insert_before", "replace_block",
                "replace_text", "delete_block", "set_heading",
                "normalize_whitespace", "set_context",
            ],
            "anchor_types": {
                "heading": "heading:<text> — match heading by exact/fuzzy text",
                "quote": "quote:<text> — match any block containing the text",
                "block_id": "block_id:<id> — match by sequential block ID (e.g. blk_001)",
                "hash": "hash:<prefix> — match by stable content hash prefix",
                "ordinal": "ordinal:<kind>:<N> — match the Nth block of a kind"
                    " (e.g. ordinal:paragraph:3)",
            },
            "operation_fields": {
                "id": "Unique string identifier for the operation.",
                "op": "One of the operation_types above.",
                "anchor": "Dict with 'by' and 'value' keys "
                    "(and optional occurrence, section, context_before, context_after).",
                "content": "Required for insert_after, insert_before, "
                    "replace_block, set_heading. Dict with 'kind' and 'value'.",
                "replacement": "Required for replace_text. The replacement string.",
                "context": "Required for set_context. Dict of annotation key-value pairs "
                    "(merged into existing annotations on the target heading).",
            },
        },
        "backends": {
            "description": "Supported document formats, auto-detected by file extension.",
            "markdown": {
                "extensions": [".md", ".markdown"],
                "tier": "full",
                "annotations_format": (
                    "HTML comments: <!-- docweave: {\"key\": \"value\"} --> "
                    "placed immediately before headings. Invisible when rendered."
                ),
            },
            "word-docx": {
                "extensions": [".docx"],
                "tier": "full",
                "extra": "Requires python-docx: pip install docweave[docx]",
                "annotations_format": (
                    "Custom XML part inside the .docx archive. "
                    "Invisible to Word users, survives normal editing."
                ),
            },
        },
        "annotations": {
            "description": (
                "Hidden context metadata on headings, surfaced by 'inspect' "
                "for progressive discovery by AI agents. Use the set_context "
                "patch operation to add or update annotations, and --tag on "
                "inspect/view to filter by tag."
            ),
            "common_keys": {
                "summary": "string — brief description of the section's content",
                "tags": "string[] — categorical labels for filtering (used by --tag)",
                "status": "string — authoring status (e.g. draft, review, complete)",
                "audience": "string — intended reader",
                "dependencies": "string[] — sections that should be read first",
            },
            "best_practices": [
                "Always annotate headings when authoring or reviewing documents "
                "so docweave inspect can provide useful structural overviews.",
                "Use tags consistently to enable --tag filtering across commands.",
                "set_context merges into existing annotations (additive, not destructive).",
                "Annotations survive content edits — they are preserved across apply operations.",
            ],
        },
    }
    elapsed = int((time.monotonic() - t0) * 1000)
    envelope = success_envelope("guide", result, duration_ms=elapsed)
    emit(envelope)


@app.command()
def inspect(
    file: Path = typer.Argument(..., help="Path to the document to inspect."),
    tag: str | None = typer.Option(
        None, "--tag",
        help="Filter headings to those whose annotations contain this tag.",
    ),
) -> None:
    """Return structural metadata about a document."""
    t0 = time.monotonic()
    backend, _doc = _load_document("inspect", file)
    result = backend.inspect(file)
    if tag:
        tag_lower = tag.lower()
        result.headings = [
            h for h in result.headings
            if tag_lower in [t.lower() for t in h.annotations.get("tags", [])]
        ]
    elapsed = int((time.monotonic() - t0) * 1000)
    envelope = success_envelope(
        "inspect", result.model_dump(), target=str(file), duration_ms=elapsed,
    )
    emit(envelope)


@app.command()
def view(
    file: Path = typer.Argument(..., help="Path to the document to view."),
    section: str | None = typer.Option(
        None, "--section",
        help="Filter by section name (matches any level in the hierarchy,"
            " not paths like 'Parent/Child').",
    ),
    tag: str | None = typer.Option(
        None, "--tag",
        help="Filter to sections whose headings have this annotation tag.",
    ),
) -> None:
    """Return the full normalized block list for a document."""
    t0 = time.monotonic()
    _backend, doc = _load_document("view", file)
    warnings: list[Warning] = []

    if tag and not section:
        # Find heading texts whose annotations contain the tag
        tag_lower = tag.lower()
        tagged_sections = {
            b.text for b in doc.blocks
            if b.kind == "heading"
            and tag_lower in [t.lower() for t in b.annotations.get("tags", [])]
        }
        if tagged_sections:
            doc.blocks = [
                b for b in doc.blocks
                if any(s in tagged_sections for s in b.section_path)
            ]
        else:
            doc.blocks = []
            warnings.append(Warning(
                code="WARN_TAG_NOT_FOUND",
                message=f"No sections found with tag {tag!r}.",
            ))

    if section:
        section_lower = section.lower()
        all_blocks = doc.blocks
        doc.blocks = [
            b for b in doc.blocks
            if any(s.lower() == section_lower for s in b.section_path)
        ]
        if not doc.blocks:
            available = sorted({s for b in all_blocks for s in b.section_path})
            warnings.append(Warning(
                code="WARN_SECTION_NOT_FOUND",
                message=f"Section {section!r} not found. Available sections: {available}",
            ))

    elapsed = int((time.monotonic() - t0) * 1000)
    envelope = success_envelope(
        "view", doc.model_dump(), target=str(file), warnings=warnings, duration_ms=elapsed,
    )
    emit(envelope)


@app.command()
def find(
    file: Path = typer.Argument(..., help="Path to the document to search."),
    query: str = typer.Argument(..., help="Text to search for."),
    section: str | None = typer.Option(
        None, "--section",
        help="Filter by section name (matches any level in the hierarchy,"
            " not paths like 'Parent/Child').",
    ),
) -> None:
    """Search blocks for a text query (searches normalized text, not raw Markdown syntax)."""
    from docweave.anchors import search_blocks

    t0 = time.monotonic()

    if not query.strip():
        envelope = error_envelope(
            "find",
            [ErrorDetail(code="ERR_VALIDATION", message="Query must not be empty.")],
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    _backend, doc = _load_document("find", file)
    warnings: list[Warning] = []
    if section:
        section_lower = section.lower()
        all_blocks = doc.blocks
        doc.blocks = [
            b for b in doc.blocks
            if any(s.lower() == section_lower for s in b.section_path)
        ]
        if not doc.blocks:
            available = sorted({s for b in all_blocks for s in b.section_path})
            warnings.append(Warning(
                code="WARN_SECTION_NOT_FOUND",
                message=f"Section {section!r} not found. Available sections: {available}",
            ))

    matches = search_blocks(doc, query)
    result = {
        "matches": [m.model_dump() for m in matches],
        "total": len(matches),
    }
    elapsed = int((time.monotonic() - t0) * 1000)
    envelope = success_envelope(
        "find", result, target=str(file),
        warnings=warnings, duration_ms=elapsed,
    )
    emit(envelope)


@app.command()
def anchor(
    file: Path = typer.Argument(..., help="Path to the document."),
    anchor_spec: str = typer.Argument(
        ..., help="Anchor spec, e.g. 'heading:Purpose' or 'ordinal:paragraph:3'.",
    ),
    section: str | None = typer.Option(
        None, "--section",
        help="Filter by section name (matches any level in the hierarchy,"
            " not paths like 'Parent/Child').",
    ),
    context_before: str | None = typer.Option(
        None, "--context-before", help="Expected text in preceding block.",
    ),
    context_after: str | None = typer.Option(
        None, "--context-after", help="Expected text in following block.",
    ),
    occurrence: int = typer.Option(1, "--occurrence", "-n", help="Which occurrence to select."),
    limit: int = typer.Option(20, "--limit", help="Max fuzzy matches to return."),
) -> None:
    """Resolve an anchor spec to a specific block."""
    from docweave.anchors import (
        OccurrenceOutOfRangeError,
        _truncate,
        parse_anchor_spec,
        resolve_anchor,
    )

    t0 = time.monotonic()

    if occurrence < 1:
        envelope = error_envelope(
            "anchor",
            [ErrorDetail(
                code="ERR_VALIDATION",
                message=f"--occurrence must be >= 1, got {occurrence}",
            )],
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    try:
        parsed = parse_anchor_spec(anchor_spec)
    except ValueError as exc:
        envelope = error_envelope(
            "anchor",
            [ErrorDetail(code="ERR_VALIDATION_INVALID_ANCHOR", message=str(exc))],
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    # Override anchor fields from CLI options
    overrides: dict = {}
    if section is not None:
        overrides["section"] = section
    if context_before is not None:
        overrides["context_before"] = context_before
    if context_after is not None:
        overrides["context_after"] = context_after
    if occurrence != 1:
        overrides["occurrence"] = occurrence
    if overrides:
        parsed = parsed.model_copy(update=overrides)

    _backend, doc = _load_document("anchor", file)
    try:
        matches = resolve_anchor(doc, parsed)
    except OccurrenceOutOfRangeError as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        envelope = error_envelope(
            "anchor",
            [ErrorDetail(
                code="ERR_VALIDATION_ANCHOR_NOT_FOUND",
                message=(
                    f"Occurrence {exc.requested} requested but only {exc.available} "
                    f"blocks match anchor: {_truncate(anchor_spec)!r}"
                ),
            )],
            target=str(file),
            duration_ms=elapsed,
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    if not matches:
        elapsed = int((time.monotonic() - t0) * 1000)
        envelope = error_envelope(
            "anchor",
            [ErrorDetail(
                code="ERR_VALIDATION_ANCHOR_NOT_FOUND",
                message=f"No blocks match anchor: {_truncate(anchor_spec)!r}",
            )],
            target=str(file),
            duration_ms=elapsed,
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    warnings: list[Warning] = []
    top_confidence = matches[0].confidence
    top_matches = [m for m in matches if m.confidence == top_confidence]
    if len(top_matches) > 1:
        warnings.append(Warning(
            code="WARN_ANCHOR_AMBIGUOUS",
            message=f"{len(top_matches)} blocks match at confidence {top_confidence}",
        ))

    selected = matches[0]
    total_matches = len(matches)
    if limit == 0:
        selected = None
        matches = []
        warnings.append(Warning(
            code="WARN_MATCHES_TRUNCATED",
            message=f"Showing 0 of {total_matches} matches. Use --limit to see more.",
        ))
    elif total_matches > limit:
        matches = matches[:limit]
        warnings.append(Warning(
            code="WARN_MATCHES_TRUNCATED",
            message=f"Showing {limit} of {total_matches} matches. Use --limit to see more.",
        ))

    result = {
        "matches": [m.model_dump() for m in matches],
        "total": total_matches,
        "selected": selected.model_dump() if selected else None,
    }
    elapsed = int((time.monotonic() - t0) * 1000)
    envelope = success_envelope(
        "anchor", result, target=str(file), warnings=warnings, duration_ms=elapsed,
    )
    emit(envelope)


@app.command(name="plan")
def plan_cmd(
    file: Path = typer.Argument(..., help="Path to the document."),
    patch: Path = typer.Option(..., "--patch", "-p", help="Path to the YAML patch file."),
    strict: bool = typer.Option(False, "--strict", help="Fail on ambiguous anchors."),
    out: Path | None = typer.Option(None, "--out", help="Write plan JSON to file."),
) -> None:
    """Preview an execution plan from a YAML patch file."""
    from docweave.plan.planner import generate_plan
    from docweave.plan.schema import load_patch

    t0 = time.monotonic()

    if not file.exists():
        envelope = error_envelope(
            "plan",
            [ErrorDetail(code="ERR_IO_FILE_NOT_FOUND", message=f"File not found: {file}")],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.IO)

    if not patch.exists():
        envelope = error_envelope(
            "plan",
            [ErrorDetail(code="ERR_IO_FILE_NOT_FOUND", message=f"Patch file not found: {patch}")],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.IO)

    try:
        patch_data = load_patch(patch)
    except ValueError as exc:
        envelope = error_envelope(
            "plan",
            [ErrorDetail(code="ERR_VALIDATION_PATCH_SCHEMA", message=str(exc))],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    exec_plan = generate_plan(file, patch_data, strict=strict)
    elapsed = int((time.monotonic() - t0) * 1000)

    if not exec_plan.valid:
        envelope = error_envelope(
            "plan",
            [ErrorDetail(
                code="ERR_VALIDATION_PLAN_INVALID",
                message="Plan is invalid: " + "; ".join(exec_plan.warnings),
            )],
            target=str(file),
            duration_ms=elapsed,
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    result = exec_plan.model_dump()
    if out:
        import orjson

        if not out.parent.exists():
            envelope = error_envelope(
                "plan",
                [ErrorDetail(
                    code="ERR_IO",
                    message=f"Parent directory does not exist: {out.parent}",
                )],
                target=str(file),
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.IO)
        out.write_bytes(orjson.dumps(result))

    envelope = success_envelope("plan", result, target=str(file), duration_ms=elapsed)
    emit(envelope)


@app.command(name="apply")
def apply_cmd(
    file: Path = typer.Argument(..., help="Path to the document."),
    patch: Path | None = typer.Option(None, "--patch", "-p", help="Path to the YAML patch file."),
    plan_file: Path | None = typer.Option(
        None, "--plan", help="Path to a saved execution plan JSON.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without modifying file.",
    ),
    backup_opt: bool = typer.Option(False, "--backup", help="Create a backup before applying."),
    strict: bool = typer.Option(False, "--strict", help="Fail on ambiguous anchors."),
    evidence_dir: Path | None = typer.Option(
        None, "--evidence-dir", help="Write evidence bundle to this directory.",
    ),
) -> None:
    """Apply a patch or execution plan to a document."""
    import uuid

    import orjson

    from docweave.diff.raw import raw_diff
    from docweave.diff.semantic import semantic_diff
    from docweave.journal import JournalEntry, record_transaction
    from docweave.plan.applier import FingerprintConflictError, apply_plan
    from docweave.plan.planner import ExecutionPlan, generate_plan
    from docweave.plan.schema import load_patch
    from docweave.validation import validate_document

    t0 = time.monotonic()

    if not file.exists():
        envelope = error_envelope(
            "apply",
            [ErrorDetail(code="ERR_IO_FILE_NOT_FOUND", message=f"File not found: {file}")],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.IO)

    has_patch = patch is not None
    has_plan = plan_file is not None
    if has_patch and has_plan:
        envelope = error_envelope(
            "apply",
            [ErrorDetail(
                code="ERR_VALIDATION",
                message="Cannot specify both --patch and --plan.",
            )],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)
    if not has_patch and not has_plan:
        envelope = error_envelope(
            "apply",
            [ErrorDetail(
                code="ERR_VALIDATION",
                message="Exactly one of --patch or --plan is required.",
            )],
            target=str(file),
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    exec_plan: ExecutionPlan
    if patch is not None:
        if not patch.exists():
            envelope = error_envelope(
                "apply",
                [ErrorDetail(
                    code="ERR_IO_FILE_NOT_FOUND",
                    message=f"Patch file not found: {patch}",
                )],
                target=str(file),
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.IO)

        try:
            patch_data = load_patch(patch)
        except ValueError as exc:
            envelope = error_envelope(
                "apply",
                [ErrorDetail(code="ERR_VALIDATION_PATCH_SCHEMA", message=str(exc))],
                target=str(file),
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.VALIDATION)

        exec_plan = generate_plan(file, patch_data, strict=strict)
    else:
        assert plan_file is not None
        if not plan_file.exists():
            envelope = error_envelope(
                "apply",
                [ErrorDetail(
                    code="ERR_IO_FILE_NOT_FOUND",
                    message=f"Plan file not found: {plan_file}",
                )],
                target=str(file),
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.IO)
        try:
            raw = orjson.loads(plan_file.read_bytes())
            exec_plan = ExecutionPlan(**raw)
        except Exception as exc:
            envelope = error_envelope(
                "apply",
                [ErrorDetail(
                    code="ERR_VALIDATION_PATCH_SCHEMA",
                    message=f"Invalid plan file: {exc}",
                )],
                target=str(file),
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.VALIDATION)

    if not exec_plan.valid:
        elapsed = int((time.monotonic() - t0) * 1000)
        envelope = error_envelope(
            "apply",
            [ErrorDetail(
                code="ERR_VALIDATION_PLAN_INVALID",
                message="Plan is invalid: " + "; ".join(exec_plan.warnings),
            )],
            target=str(file),
            duration_ms=elapsed,
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.VALIDATION)

    if dry_run:
        dry_warnings: list[Warning] = []
        if backup_opt:
            dry_warnings.append(Warning(
                code="WARN_DRY_RUN_BACKUP_IGNORED",
                message="--backup is ignored in --dry-run mode (no file modifications).",
            ))
        elapsed = int((time.monotonic() - t0) * 1000)
        envelope = success_envelope(
            "apply", exec_plan.model_dump(), target=str(file),
            warnings=dry_warnings, duration_ms=elapsed,
        )
        emit(envelope)
        return

    # Capture before state
    init_backends()
    before_backend = detect_backend(file)
    try:
        before_text = before_backend.extract_text(file)
    except (PermissionError, UnicodeDecodeError) as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        is_perm = isinstance(exc, PermissionError)
        code = "ERR_PERMISSION" if is_perm else "ERR_VALIDATION_DECODE"
        exit_code = ExitCode.PERMISSION if is_perm else ExitCode.VALIDATION
        envelope = error_envelope(
            "apply",
            [ErrorDetail(code=code, message=f"Cannot read file: {file} ({exc})")],
            target=str(file),
            duration_ms=elapsed,
        )
        emit(envelope)
        raise typer.Exit(code=exit_code)

    before_doc = before_backend.load_view(file)

    try:
        if exec_plan.backend == "word-docx":
            from docweave.plan.applier_docx import apply_plan_docx

            apply_result = apply_plan_docx(file, exec_plan, backup=backup_opt)
        else:
            apply_result = apply_plan(file, exec_plan, backup=backup_opt)
    except PermissionError:
        elapsed = int((time.monotonic() - t0) * 1000)
        envelope = error_envelope(
            "apply",
            [ErrorDetail(code="ERR_PERMISSION", message=f"Permission denied writing to: {file}")],
            target=str(file),
            duration_ms=elapsed,
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.PERMISSION)
    except FingerprintConflictError as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        envelope = error_envelope(
            "apply",
            [ErrorDetail(
                code="ERR_CONFLICT_FINGERPRINT",
                message=str(exc),
            )],
            target=str(file),
            duration_ms=elapsed,
        )
        emit(envelope)
        raise typer.Exit(code=ExitCode.CONFLICT)

    # Capture after state
    init_backends()
    after_backend = detect_backend(file)
    after_text = after_backend.extract_text(file)
    after_doc = after_backend.load_view(file)

    # Compute diffs
    raw_hunks = raw_diff(before_text, after_text)
    sem_diff = semantic_diff(before_doc, after_doc)

    # Evidence bundle
    if evidence_dir is not None:
        from docweave.evidence.bundle import write_evidence_bundle

        if not evidence_dir.parent.exists():
            elapsed = int((time.monotonic() - t0) * 1000)
            envelope = error_envelope(
                "apply",
                [ErrorDetail(
                    code="ERR_IO",
                    message=f"Parent directory does not exist: {evidence_dir.parent}",
                )],
                target=str(file),
                duration_ms=elapsed,
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.IO)

        try:
            write_evidence_bundle(
                evidence_dir,
                before_view=before_doc.model_dump(mode="json"),
                after_view=after_doc.model_dump(mode="json"),
                plan=exec_plan.model_dump(mode="json"),
                sem_diff=sem_diff,
                raw_hunks=raw_hunks,
            )
        except PermissionError:
            elapsed = int((time.monotonic() - t0) * 1000)
            envelope = error_envelope(
                "apply",
                [ErrorDetail(
                    code="ERR_PERMISSION",
                    message=f"Permission denied writing evidence to: {evidence_dir}",
                )],
                target=str(file),
                duration_ms=elapsed,
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.PERMISSION)
        except OSError as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            envelope = error_envelope(
                "apply",
                [ErrorDetail(
                    code="ERR_IO",
                    message=f"Failed to write evidence bundle: {exc}",
                )],
                target=str(file),
                duration_ms=elapsed,
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.IO)

    # Validation
    val_report = validate_document(after_doc)

    # Journal (skip for zero-operation patches)
    txn_id: str | None = None
    if apply_result.operations_applied > 0:
        op_ids = [r.operation.get("id", "") for r in exec_plan.resolved_operations]
        from datetime import UTC, datetime

        txn_id = str(uuid.uuid4())
        entry = JournalEntry(
            txn_id=txn_id,
            timestamp=datetime.now(UTC).isoformat(),
            file=str(file.resolve()),
            backend=exec_plan.backend,
            operations=op_ids,
            fingerprint_before=apply_result.fingerprint_before,
            fingerprint_after=apply_result.fingerprint_after,
            operations_applied=apply_result.operations_applied,
            warnings=apply_result.warnings,
            validation_result=val_report.model_dump(mode="json"),
        )
        record_transaction(entry)

    # Enrich result
    result_dict = apply_result.model_dump()
    result_dict["journal_txn_id"] = txn_id
    result_dict["semantic_summary"] = sem_diff.summary
    if evidence_dir is not None:
        result_dict["evidence_dir"] = str(evidence_dir)

    elapsed = int((time.monotonic() - t0) * 1000)
    envelope = success_envelope(
        "apply", result_dict, target=str(file), duration_ms=elapsed,
    )
    emit(envelope)


@app.command(name="fleet")
def fleet_cmd(
    patches: list[Path] = typer.Option(
        ..., "--patch", "-p",
        help="YAML patch files to apply. Each must have target.file set.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying files."),
    backup_opt: bool = typer.Option(False, "--backup", help="Create backups before applying."),
    strict: bool = typer.Option(False, "--strict", help="Fail on ambiguous anchors."),
    parallel: bool = typer.Option(
        False, "--parallel", help="Apply patches concurrently via threads.",
    ),
    evidence_dir: Path | None = typer.Option(
        None, "--evidence-dir",
        help="Write evidence bundles here (one subdirectory per file).",
    ),
) -> None:
    """Apply multiple self-describing patch files to their respective target documents."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from docweave.plan.applier import FingerprintConflictError, apply_plan
    from docweave.plan.planner import generate_plan
    from docweave.plan.schema import load_patch

    t0 = time.monotonic()
    init_backends()

    # Phase 1: Validate all patches upfront before touching any file.
    patch_jobs: list[tuple[Path, Path, object]] = []
    for p in patches:
        if not p.exists():
            envelope = error_envelope(
                "fleet",
                [ErrorDetail(code="ERR_IO_FILE_NOT_FOUND", message=f"Patch file not found: {p}")],
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.IO)

        try:
            patch_data = load_patch(p)
        except ValueError as exc:
            envelope = error_envelope(
                "fleet",
                [ErrorDetail(code="ERR_VALIDATION_PATCH_SCHEMA", message=str(exc))],
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.VALIDATION)

        target_file_str = patch_data.target.get("file")
        if not target_file_str:
            envelope = error_envelope(
                "fleet",
                [ErrorDetail(
                    code="ERR_VALIDATION",
                    message=f"Patch '{p}' must have target.file set for fleet apply.",
                )],
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.VALIDATION)

        file_path = Path(target_file_str)
        if not file_path.exists():
            envelope = error_envelope(
                "fleet",
                [ErrorDetail(
                    code="ERR_IO_FILE_NOT_FOUND",
                    message=f"Target file not found: {file_path} (referenced by patch {p})",
                )],
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.IO)

        patch_jobs.append((p, file_path, patch_data))

    # Phase 2: Run applies — serial or parallel.
    def _run_one(job: tuple) -> dict:
        p_path, file_path, patch_data = job
        try:
            exec_plan = generate_plan(file_path, patch_data, strict=strict)
            if not exec_plan.valid:
                return {
                    "patch": str(p_path),
                    "file": str(file_path),
                    "ok": False,
                    "ops_applied": 0,
                    "dry_run": dry_run,
                    "error": "Plan invalid: " + "; ".join(exec_plan.warnings),
                }

            if dry_run:
                return {
                    "patch": str(p_path),
                    "file": str(file_path),
                    "ok": True,
                    "ops_applied": len(exec_plan.resolved_operations),
                    "dry_run": True,
                }

            ev_dir: Path | None = None
            if evidence_dir is not None:
                import hashlib
                tag = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
                ev_dir = Path(evidence_dir) / tag
                ev_dir.mkdir(parents=True, exist_ok=True)

            if exec_plan.backend == "word-docx":
                from docweave.plan.applier_docx import apply_plan_docx

                apply_result = apply_plan_docx(file_path, exec_plan, backup=backup_opt)
            else:
                apply_result = apply_plan(file_path, exec_plan, backup=backup_opt)

            return {
                "patch": str(p_path),
                "file": str(file_path),
                "ok": True,
                "ops_applied": apply_result.operations_applied,
                "fingerprint_before": apply_result.fingerprint_before,
                "fingerprint_after": apply_result.fingerprint_after,
                "dry_run": False,
            }
        except FingerprintConflictError as exc:
            return {
                "patch": str(p_path),
                "file": str(file_path),
                "ok": False,
                "ops_applied": 0,
                "dry_run": dry_run,
                "error": f"ERR_CONFLICT_FINGERPRINT: {exc}",
            }
        except PermissionError:
            return {
                "patch": str(p_path),
                "file": str(file_path),
                "ok": False,
                "ops_applied": 0,
                "dry_run": dry_run,
                "error": f"ERR_PERMISSION: Permission denied writing to {file_path}",
            }
        except Exception as exc:
            return {
                "patch": str(p_path),
                "file": str(file_path),
                "ok": False,
                "ops_applied": 0,
                "dry_run": dry_run,
                "error": str(exc),
            }

    results: list[dict] = []
    if parallel:
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(_run_one, job): job for job in patch_jobs}
            for future in as_completed(futures):
                results.append(future.result())
        # Re-sort to match input order (as_completed is non-deterministic).
        patch_index = {str(p): i for i, (p, _, _) in enumerate(patch_jobs)}
        results.sort(key=lambda r: patch_index.get(r["patch"], 999))
    else:
        for job in patch_jobs:
            results.append(_run_one(job))

    succeeded = sum(1 for r in results if r["ok"])
    failed = len(results) - succeeded
    elapsed = int((time.monotonic() - t0) * 1000)

    fleet_result = {
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "dry_run": dry_run,
        "parallel": parallel,
        "results": results,
    }

    errors: list[ErrorDetail] = []
    if failed:
        errors = [ErrorDetail(
            code="ERR_FLEET_PARTIAL",
            message=f"{failed} of {len(results)} patches failed.",
        )]

    envelope = make_envelope(
        "fleet", ok=(failed == 0), result=fleet_result, errors=errors, duration_ms=elapsed,
    )
    emit(envelope)


@app.command(name="diff")
def diff_cmd(
    before: Path = typer.Argument(..., help="Path to the before document."),
    after: Path = typer.Argument(..., help="Path to the after document."),
) -> None:
    """Compute raw and semantic diff between two documents."""
    from docweave.diff.raw import raw_diff
    from docweave.diff.semantic import semantic_diff

    t0 = time.monotonic()

    for label, fpath in [("before", before), ("after", after)]:
        if not fpath.exists():
            envelope = error_envelope(
                "diff",
                [ErrorDetail(
                    code="ERR_IO_FILE_NOT_FOUND",
                    message=f"{label.capitalize()} file not found: {fpath}",
                )],
                target=str(fpath),
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.IO)

    backend_b, before_doc = _load_document("diff", before)
    backend_a, after_doc = _load_document("diff", after)

    before_text = backend_b.extract_text(before)
    after_text = backend_a.extract_text(after)

    raw_hunks = raw_diff(before_text, after_text)
    sem_report = semantic_diff(before_doc, after_doc)

    result = {
        "raw_diff": [h.model_dump() for h in raw_hunks],
        "semantic_diff": sem_report.model_dump(mode="json"),
    }
    elapsed = int((time.monotonic() - t0) * 1000)
    envelope = success_envelope("diff", result, target=str(before), duration_ms=elapsed)
    emit(envelope)


@app.command(name="validate")
def validate_cmd(
    file: Path = typer.Argument(..., help="Path to the document to validate."),
) -> None:
    """Validate structural integrity of a document."""
    from docweave.validation import validate_document

    t0 = time.monotonic()
    _backend, doc = _load_document("validate", file)
    report = validate_document(doc)

    elapsed = int((time.monotonic() - t0) * 1000)
    envelope = success_envelope(
        "validate", report.model_dump(mode="json"), target=str(file), duration_ms=elapsed,
    )
    emit(envelope)


@app.command(name="journal")
def journal_cmd(
    txn_id: str | None = typer.Argument(None, help="Transaction ID to look up."),
    file: Path | None = typer.Option(None, "--file", help="Filter by file path."),
) -> None:
    """List or retrieve transaction journal entries."""
    from docweave.journal import (
        get_transaction,
        get_transaction_global,
        list_all_transactions,
        list_transactions,
    )

    t0 = time.monotonic()

    if txn_id is not None:
        if file is not None:
            entry = get_transaction(file, txn_id)
        else:
            entry = get_transaction_global(txn_id)
        if entry is None:
            elapsed = int((time.monotonic() - t0) * 1000)
            envelope = error_envelope(
                "journal",
                [ErrorDetail(
                    code="ERR_VALIDATION",
                    message=f"Transaction not found: {txn_id}",
                )],
                duration_ms=elapsed,
            )
            emit(envelope)
            raise typer.Exit(code=ExitCode.VALIDATION)

        elapsed = int((time.monotonic() - t0) * 1000)
        envelope = success_envelope(
            "journal", entry.model_dump(mode="json"), duration_ms=elapsed,
        )
        emit(envelope)
    else:
        if file is not None:
            entries = list_transactions(file, filter_file=str(file.resolve()))
        else:
            entries = list_all_transactions()
        result = {
            "entries": [e.model_dump(mode="json") for e in entries],
            "count": len(entries),
        }
        elapsed = int((time.monotonic() - t0) * 1000)
        envelope = success_envelope("journal", result, duration_ms=elapsed)
        emit(envelope)


def main() -> None:
    """Entry point with structured error handling."""
    try:
        result = app(standalone_mode=False)
        if isinstance(result, int) and result != 0:
            sys.exit(result)
    except SystemExit as exc:
        sys.exit(exc.code)
    except click.exceptions.ClickException as exc:
        message = str(exc.format_message())
        if not message:
            message = "No command specified. Run with --help for usage."
        if "--format" in message:
            message += (
                " (Note: --format is a global option"
                " and must appear before the subcommand.)"
            )
        envelope = error_envelope(
            "unknown",
            [ErrorDetail(code="ERR_VALIDATION", message=message)],
        )
        emit(envelope)
        sys.exit(ExitCode.VALIDATION)
    except Exception as exc:
        envelope = error_envelope(
            "unknown",
            [ErrorDetail(code="ERR_INTERNAL_UNHANDLED", message=str(exc))],
        )
        emit(envelope)
        sys.exit(ExitCode.INTERNAL)
