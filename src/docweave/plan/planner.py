"""Resolve patch anchors into an execution plan."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel

from docweave.anchors import Anchor, AnchorMatch, OccurrenceOutOfRangeError, resolve_anchor
from docweave.backends.registry import detect as detect_backend
from docweave.backends.registry import init_backends
from docweave.models import SourceSpan
from docweave.plan.schema import PatchFile


class ResolvedOperation(BaseModel):
    operation: dict  # OperationSpec as dict for serialization
    anchor_match: AnchorMatch
    action_description: str
    affected_lines: SourceSpan


class ExecutionPlan(BaseModel):
    file: str
    fingerprint: str
    backend: str
    resolved_operations: list[ResolvedOperation]
    warnings: list[str]
    valid: bool


def _file_fingerprint(path: Path) -> str:
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def _describe_action(op_type: str, match: AnchorMatch) -> str:
    start = match.source_span.start_line
    end = match.source_span.end_line
    block_desc = f"{match.block_kind} at lines {start}-{end}"
    descriptions = {
        "insert_after": f"Insert content after {block_desc}",
        "insert_before": f"Insert content before {block_desc}",
        "replace_block": f"Replace {block_desc}",
        "replace_text": f"Replace text within {block_desc}",
        "delete_block": f"Delete {block_desc}",
        "set_heading": f"Set heading at {block_desc}",
        "normalize_whitespace": f"Normalize whitespace in {block_desc}",
    }
    return descriptions.get(op_type, f"{op_type} on {block_desc}")


def generate_plan(
    path: Path, patch: PatchFile, *, strict: bool = False,
) -> ExecutionPlan:
    """Generate an execution plan from a patch file against a document."""
    fingerprint = _file_fingerprint(path)

    init_backends()
    backend = detect_backend(path)
    doc = backend.load_view(path)

    resolved: list[ResolvedOperation] = []
    warnings: list[str] = []
    valid = True

    for op in patch.operations:
        anchor = Anchor(**op.anchor)
        try:
            matches = resolve_anchor(doc, anchor)
        except OccurrenceOutOfRangeError as exc:
            valid = False
            warnings.append(
                f"Operation {op.id}: occurrence {exc.requested} requested "
                f"but only {exc.available} blocks match anchor {op.anchor}"
            )
            continue

        if not matches:
            valid = False
            warnings.append(
                f"Operation {op.id}: no blocks match anchor {op.anchor}"
            )
            continue

        top_confidence = matches[0].confidence
        top_matches = [m for m in matches if m.confidence == top_confidence]

        if len(top_matches) > 1:
            if strict:
                valid = False
                warnings.append(
                    f"Operation {op.id}: ambiguous anchor — "
                    f"{len(top_matches)} blocks match at confidence {top_confidence}"
                )
                continue
            else:
                warnings.append(
                    f"Operation {op.id}: ambiguous anchor — "
                    f"{len(top_matches)} blocks match at confidence {top_confidence}, "
                    f"using first match"
                )

        best = matches[0]
        resolved.append(ResolvedOperation(
            operation=op.model_dump(),
            anchor_match=best,
            action_description=_describe_action(op.op, best),
            affected_lines=best.source_span,
        ))

    return ExecutionPlan(
        file=str(path),
        fingerprint=fingerprint,
        backend=backend.name,
        resolved_operations=resolved,
        warnings=warnings,
        valid=valid,
    )
