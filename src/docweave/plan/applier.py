"""Apply an execution plan with atomic writes and fingerprint safety."""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from docweave.plan.planner import ExecutionPlan


class FingerprintConflictError(Exception):
    """Raised when the file has changed since the plan was generated."""

    def __init__(self, expected: str, actual: str) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Fingerprint conflict: expected {expected[:12]}…, got {actual[:12]}…"
        )


class ApplyResult(BaseModel):
    file: str
    operations_applied: int
    fingerprint_before: str
    fingerprint_after: str
    backup_path: str | None
    warnings: list[str]


def _file_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_content(value: str) -> str:
    """Ensure content ends with a newline."""
    if not value.endswith("\n"):
        return value + "\n"
    return value


def _render_content(
    kind: str, value: str, *,
    level: int | None = None, language: str | None = None,
) -> str:
    """Wrap a content value in the appropriate markdown syntax for its kind."""
    if kind in ("paragraph", "markdown", "table"):
        return value
    if kind == "heading":
        lvl = level if level and level >= 1 else 2
        stripped = value.lstrip("# ")
        return "#" * lvl + " " + stripped
    if kind == "code_block":
        lang = language or ""
        fence = "```"
        # Ensure the value doesn't already have fences
        if value.startswith("```"):
            return value
        return f"{fence}{lang}\n{value.rstrip(chr(10))}\n{fence}"
    if kind == "blockquote":
        # Prefix each line with "> "
        if value.startswith("> "):
            return value
        lines = value.split("\n")
        quoted = []
        for line in lines:
            if line.strip():
                quoted.append("> " + line)
            else:
                quoted.append(">")
        return "\n".join(quoted)
    if kind == "list_item":
        if value.startswith("- ") or value.startswith("* "):
            return value
        return "- " + value
    # Unknown kind — return as-is
    return value


def apply_plan(
    path: Path, plan: ExecutionPlan, *, backup: bool = False,
) -> ApplyResult:
    """Apply an execution plan to a file with atomic write."""
    fingerprint_before = _file_fingerprint(path)

    if fingerprint_before != plan.fingerprint:
        raise FingerprintConflictError(
            expected=plan.fingerprint, actual=fingerprint_before,
        )

    backup_path: str | None = None
    if backup:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        bak = path.with_suffix(f".{stamp}.bak")
        shutil.copy2(path, bak)
        backup_path = str(bak)

    lines = path.read_text("utf-8").splitlines(keepends=True)
    warnings: list[str] = []

    # Sort operations by affected_lines.end_line descending (bottom-up)
    sorted_ops = sorted(
        plan.resolved_operations,
        key=lambda r: r.affected_lines.end_line,
        reverse=True,
    )

    for resolved in sorted_ops:
        op = resolved.operation
        start = resolved.affected_lines.start_line  # 1-based
        end = resolved.affected_lines.end_line  # 1-based inclusive
        op_type = op["op"]

        # Convert to 0-based indices
        start_idx = start - 1
        end_idx = end  # end is inclusive in 1-based, so end_idx is exclusive in 0-based

        if op_type == "insert_after":
            raw_value = op["content"]["value"]
            kind = op["content"].get("kind", "paragraph")
            rendered = _render_content(
                kind, raw_value,
                level=op["content"].get("level"),
                language=op["content"].get("language"),
            )
            content = _normalize_content(rendered)
            insert_lines = ("\n" + content).splitlines(keepends=True)
            lines[end_idx:end_idx] = insert_lines

        elif op_type == "insert_before":
            raw_value = op["content"]["value"]
            kind = op["content"].get("kind", "paragraph")
            rendered = _render_content(
                kind, raw_value,
                level=op["content"].get("level"),
                language=op["content"].get("language"),
            )
            content = _normalize_content(rendered)
            insert_lines = (content + "\n").splitlines(keepends=True)
            lines[start_idx:start_idx] = insert_lines

        elif op_type == "replace_block":
            raw_value = op["content"]["value"]
            kind = op["content"].get("kind", "paragraph")
            rendered = _render_content(
                kind, raw_value,
                level=op["content"].get("level"),
                language=op["content"].get("language"),
            )
            content = _normalize_content(rendered)
            replacement_lines = content.splitlines(keepends=True)
            lines[start_idx:end_idx] = replacement_lines

        elif op_type == "replace_text":
            block_text = "".join(lines[start_idx:end_idx])
            search = op["anchor"]["value"]
            replacement = op.get("replacement", "")
            new_text = block_text.replace(search, replacement)
            lines[start_idx:end_idx] = new_text.splitlines(keepends=True)

        elif op_type == "delete_block":
            lines[start_idx:end_idx] = []

        elif op_type == "set_heading":
            raw_value = op["content"]["value"]
            # Detect the heading level from the existing line
            existing_line = lines[start_idx] if start_idx < len(lines) else ""
            level = 0
            for ch in existing_line:
                if ch == "#":
                    level += 1
                else:
                    break
            if level == 0:
                # Fallback: try from anchor_match block_kind or default to 1
                level = 1
            # Strip any leading '#' prefix the user may have included
            stripped = raw_value.lstrip("# ")
            content = _normalize_content("#" * level + " " + stripped)
            replacement_lines = content.splitlines(keepends=True)
            lines[start_idx:end_idx] = replacement_lines

        elif op_type == "normalize_whitespace":
            block_lines = lines[start_idx:end_idx]
            normalized: list[str] = []
            prev_blank = False
            for line in block_lines:
                is_blank = line.strip() == ""
                if is_blank and prev_blank:
                    continue
                normalized.append(line)
                prev_blank = is_blank
            lines[start_idx:end_idx] = normalized

        else:
            warnings.append(f"Unknown operation type: {op_type}")

    # Atomic write: write to temp file, then replace
    new_content = "".join(lines)
    tmp_name = f".docweave_tmp_{secrets.token_hex(4)}"
    tmp_path = path.parent / tmp_name
    try:
        tmp_path.write_text(new_content, "utf-8")
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file if replace fails
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    fingerprint_after = _file_fingerprint(path)

    return ApplyResult(
        file=str(path),
        operations_applied=len(sorted_ops),
        fingerprint_before=fingerprint_before,
        fingerprint_after=fingerprint_after,
        backup_path=backup_path,
        warnings=warnings,
    )
