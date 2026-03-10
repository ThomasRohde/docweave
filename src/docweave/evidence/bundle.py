"""Evidence bundle writer for apply audit trail."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson

from docweave.diff.raw import DiffHunk, format_raw_diff
from docweave.diff.semantic import SemanticDiffReport


def write_evidence_bundle(
    evidence_dir: Path,
    before_view: dict[str, Any],
    after_view: dict[str, Any],
    plan: dict[str, Any],
    sem_diff: SemanticDiffReport,
    raw_hunks: list[DiffHunk],
) -> dict[str, str]:
    """Write a full evidence bundle and return artifact name → path mapping."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    opts = orjson.OPT_INDENT_2

    artifacts: dict[str, str] = {}

    # before_view.json
    p = evidence_dir / "before_view.json"
    p.write_bytes(orjson.dumps(before_view, option=opts))
    artifacts["before_view.json"] = str(p)

    # after_view.json
    p = evidence_dir / "after_view.json"
    p.write_bytes(orjson.dumps(after_view, option=opts))
    artifacts["after_view.json"] = str(p)

    # plan.json
    p = evidence_dir / "plan.json"
    p.write_bytes(orjson.dumps(plan, option=opts))
    artifacts["plan.json"] = str(p)

    # semantic_diff.json
    p = evidence_dir / "semantic_diff.json"
    p.write_bytes(orjson.dumps(sem_diff.model_dump(mode="json"), option=opts))
    artifacts["semantic_diff.json"] = str(p)

    # raw_diff.txt
    p = evidence_dir / "raw_diff.txt"
    p.write_text(format_raw_diff(raw_hunks), encoding="utf-8")
    artifacts["raw_diff.txt"] = str(p)

    # summary.json
    summary = {
        "file": plan.get("file", ""),
        "operations_count": len(plan.get("resolved_operations", [])),
        "before_block_count": len(before_view.get("blocks", [])),
        "after_block_count": len(after_view.get("blocks", [])),
        "diff_summary": sem_diff.summary,
    }
    p = evidence_dir / "summary.json"
    p.write_bytes(orjson.dumps(summary, option=opts))
    artifacts["summary.json"] = str(p)

    return artifacts
