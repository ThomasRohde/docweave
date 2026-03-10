"""Tests for evidence bundle and integration with apply."""

from __future__ import annotations

import shutil
from pathlib import Path

import orjson

from docweave.backends.markdown_native import MarkdownBackend
from docweave.diff.raw import raw_diff
from docweave.diff.semantic import semantic_diff
from docweave.evidence.bundle import write_evidence_bundle

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.md"


def _copy_sample(tmp_path: Path) -> Path:
    dest = tmp_path / "sample.md"
    shutil.copy2(SAMPLE, dest)
    return dest


def _make_bundle(tmp_path: Path) -> Path:
    """Create a sample evidence bundle and return the evidence dir."""
    backend = MarkdownBackend()
    before_text = "# Title\n\nOld paragraph.\n"
    after_text = "# Title\n\nNew paragraph.\n"
    before_doc = backend._parse_source(before_text, "before.md")
    after_doc = backend._parse_source(after_text, "after.md")

    plan = {
        "file": "test.md",
        "fingerprint": "abc123",
        "backend": "markdown-native",
        "resolved_operations": [{"operation": {"id": "op_001", "op": "replace_block"}}],
        "warnings": [],
        "valid": True,
    }

    sem = semantic_diff(before_doc, after_doc)
    raw_hunks = raw_diff(before_text, after_text)

    evidence_dir = tmp_path / "evidence"
    write_evidence_bundle(
        evidence_dir,
        before_view=before_doc.model_dump(mode="json"),
        after_view=after_doc.model_dump(mode="json"),
        plan=plan,
        sem_diff=sem,
        raw_hunks=raw_hunks,
    )
    return evidence_dir


def test_evidence_creates_all_files(tmp_path: Path):
    evidence_dir = _make_bundle(tmp_path)
    expected = {
        "before_view.json", "after_view.json", "plan.json",
        "semantic_diff.json", "raw_diff.txt", "summary.json",
    }
    actual = {f.name for f in evidence_dir.iterdir()}
    assert expected == actual


def test_evidence_json_valid(tmp_path: Path):
    evidence_dir = _make_bundle(tmp_path)
    json_files = [
        "before_view.json", "after_view.json", "plan.json",
        "semantic_diff.json", "summary.json",
    ]
    for name in json_files:
        data = orjson.loads((evidence_dir / name).read_bytes())
        assert isinstance(data, dict)


def test_apply_cli_with_evidence(tmp_path: Path, run_cli):
    doc = _copy_sample(tmp_path)
    patch_path = FIXTURES / "patch_insert_after.yaml"
    evidence = tmp_path / "evidence"

    result = run_cli(
        "apply", str(doc), "--patch", str(patch_path),
        "--evidence-dir", str(evidence),
    )
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert evidence.is_dir()
    assert (evidence / "summary.json").exists()


def test_apply_records_journal(tmp_path: Path, run_cli):
    doc = _copy_sample(tmp_path)
    patch_path = FIXTURES / "patch_insert_after.yaml"

    result = run_cli("apply", str(doc), "--patch", str(patch_path))
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert "journal_txn_id" in env["result"]
    assert "semantic_summary" in env["result"]

    # Verify journal file was created
    journal_file = tmp_path / ".docweave-journal" / "journal.jsonl"
    assert journal_file.exists()
