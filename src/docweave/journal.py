"""Transaction journal for apply operations (JSONL-based)."""

from __future__ import annotations

from pathlib import Path

import orjson
from pydantic import BaseModel


class JournalEntry(BaseModel):
    txn_id: str  # UUID4
    timestamp: str  # ISO 8601
    file: str
    backend: str
    operations: list[str]  # op IDs
    fingerprint_before: str
    fingerprint_after: str
    operations_applied: int
    warnings: list[str]
    validation_result: dict | None = None


def _journal_path(file_path: Path) -> Path:
    return file_path.parent / ".docweave-journal" / "journal.jsonl"


def record_transaction(entry: JournalEntry) -> None:
    """Append a journal entry to the JSONL file."""
    path = _journal_path(Path(entry.file))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        f.write(orjson.dumps(entry.model_dump(mode="json")))
        f.write(b"\n")


def get_transaction(file_path: Path, txn_id: str) -> JournalEntry | None:
    """Look up a single transaction by ID."""
    jpath = _journal_path(file_path)
    if not jpath.exists():
        return None
    for line in jpath.read_bytes().splitlines():
        if not line.strip():
            continue
        data = orjson.loads(line)
        if data.get("txn_id") == txn_id:
            return JournalEntry(**data)
    return None


def list_transactions(
    file_path: Path, *, filter_file: str | None = None,
) -> list[JournalEntry]:
    """Read all journal entries, optionally filtered by file path."""
    jpath = _journal_path(file_path)
    if not jpath.exists():
        return []
    entries: list[JournalEntry] = []
    for line in jpath.read_bytes().splitlines():
        if not line.strip():
            continue
        data = orjson.loads(line)
        entry = JournalEntry(**data)
        if filter_file is not None:
            if Path(entry.file).resolve() != Path(filter_file).resolve():
                continue
        entries.append(entry)
    return entries


def find_all_journals(root: Path | None = None) -> list[Path]:
    """Find all .docweave-journal directories under root (defaults to cwd)."""
    root = root or Path.cwd()
    return sorted(root.rglob(".docweave-journal/journal.jsonl"))


def get_transaction_global(txn_id: str, root: Path | None = None) -> JournalEntry | None:
    """Search all journal files for a transaction ID."""
    for jpath in find_all_journals(root):
        for line in jpath.read_bytes().splitlines():
            if not line.strip():
                continue
            data = orjson.loads(line)
            if data.get("txn_id") == txn_id:
                return JournalEntry(**data)
    return None


def list_all_transactions(root: Path | None = None) -> list[JournalEntry]:
    """List all journal entries across all discovered journal files."""
    entries: list[JournalEntry] = []
    for jpath in find_all_journals(root):
        for line in jpath.read_bytes().splitlines():
            if not line.strip():
                continue
            entries.append(JournalEntry(**orjson.loads(line)))
    return entries
