"""Line-level diff using difflib."""

from __future__ import annotations

import re

from pydantic import BaseModel


class DiffHunk(BaseModel):
    start_line_before: int
    count_before: int
    start_line_after: int
    count_after: int
    lines: list[str]  # prefixed with +/-/space


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def raw_diff(before_text: str, after_text: str) -> list[DiffHunk]:
    """Compute line-level diff hunks between two texts."""
    import difflib

    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        before_lines, after_lines, lineterm="",
    ))

    hunks: list[DiffHunk] = []
    current_lines: list[str] = []
    current_header: re.Match | None = None

    for line in diff_lines:
        m = _HUNK_RE.match(line)
        if m:
            # Flush previous hunk
            if current_header is not None:
                hunks.append(_make_hunk(current_header, current_lines))
            current_header = m
            current_lines = []
        elif current_header is not None and (
            line.startswith("+") or line.startswith("-") or line.startswith(" ")
        ):
            current_lines.append(line)

    # Flush last hunk
    if current_header is not None:
        hunks.append(_make_hunk(current_header, current_lines))

    return hunks


def _make_hunk(header: re.Match, lines: list[str]) -> DiffHunk:
    return DiffHunk(
        start_line_before=int(header.group(1)),
        count_before=int(header.group(2)) if header.group(2) else 1,
        start_line_after=int(header.group(3)),
        count_after=int(header.group(4)) if header.group(4) else 1,
        lines=lines,
    )


def format_raw_diff(hunks: list[DiffHunk]) -> str:
    """Render hunks as unified diff text."""
    if not hunks:
        return ""

    parts: list[str] = []
    for hunk in hunks:
        parts.append(
            f"@@ -{hunk.start_line_before},{hunk.count_before} "
            f"+{hunk.start_line_after},{hunk.count_after} @@"
        )
        for line in hunk.lines:
            parts.append(line)

    return "\n".join(parts) + "\n"
