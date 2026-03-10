"""Tests for the transaction journal."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from docweave.journal import (
    JournalEntry,
    get_transaction,
    get_transaction_global,
    list_all_transactions,
    list_transactions,
    record_transaction,
)


def _make_entry(file_path: str, txn_id: str | None = None) -> JournalEntry:
    return JournalEntry(
        txn_id=txn_id or str(uuid.uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        file=file_path,
        backend="markdown-native",
        operations=["op_001"],
        fingerprint_before="aaa",
        fingerprint_after="bbb",
        operations_applied=1,
        warnings=[],
        validation_result=None,
    )


def test_record_creates_journal_dir(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Test\n")
    entry = _make_entry(str(doc))
    record_transaction(entry)
    journal_dir = tmp_path / ".docweave-journal"
    assert journal_dir.is_dir()


def test_record_creates_jsonl(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Test\n")
    entry = _make_entry(str(doc))
    record_transaction(entry)
    journal_file = tmp_path / ".docweave-journal" / "journal.jsonl"
    assert journal_file.exists()
    lines = journal_file.read_bytes().splitlines()
    assert len(lines) == 1


def test_get_transaction_by_id(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Test\n")
    txn_id = str(uuid.uuid4())
    entry = _make_entry(str(doc), txn_id=txn_id)
    record_transaction(entry)

    found = get_transaction(doc, txn_id)
    assert found is not None
    assert found.txn_id == txn_id


def test_get_not_found(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Test\n")
    entry = _make_entry(str(doc))
    record_transaction(entry)

    found = get_transaction(doc, "nonexistent-id")
    assert found is None


def test_list_transactions(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Test\n")
    for _ in range(3):
        record_transaction(_make_entry(str(doc)))

    entries = list_transactions(doc)
    assert len(entries) == 3


def test_list_filter_by_file(tmp_path: Path):
    doc1 = tmp_path / "a.md"
    doc2 = tmp_path / "b.md"
    doc1.write_text("# A\n")
    doc2.write_text("# B\n")

    # Both journal entries go to the same journal dir (based on doc1 parent)
    record_transaction(_make_entry(str(doc1)))
    record_transaction(_make_entry(str(doc2)))

    # Filter by doc1
    entries = list_transactions(doc1, filter_file=str(doc1))
    assert len(entries) == 1
    assert Path(entries[0].file).name == "a.md"


def test_get_transaction_global_finds_entry(tmp_path: Path):
    """get_transaction_global should find an entry without knowing the file."""
    subdir = tmp_path / "subproject"
    subdir.mkdir()
    doc = subdir / "doc.md"
    doc.write_text("# Test\n")

    txn_id = str(uuid.uuid4())
    record_transaction(_make_entry(str(doc), txn_id=txn_id))

    found = get_transaction_global(txn_id, root=tmp_path)
    assert found is not None
    assert found.txn_id == txn_id


def test_get_transaction_global_not_found(tmp_path: Path):
    """get_transaction_global returns None when no match exists."""
    found = get_transaction_global("nonexistent-id", root=tmp_path)
    assert found is None


def test_list_all_transactions_multiple_journals(tmp_path: Path):
    """list_all_transactions returns entries from multiple journal files."""
    dir1 = tmp_path / "project1"
    dir2 = tmp_path / "project2"
    dir1.mkdir()
    dir2.mkdir()

    doc1 = dir1 / "a.md"
    doc2 = dir2 / "b.md"
    doc1.write_text("# A\n")
    doc2.write_text("# B\n")

    record_transaction(_make_entry(str(doc1)))
    record_transaction(_make_entry(str(doc2)))

    entries = list_all_transactions(root=tmp_path)
    assert len(entries) == 2
