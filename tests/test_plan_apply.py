"""Tests for the plan & apply pipeline."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from docweave.plan.applier import FingerprintConflictError, apply_plan
from docweave.plan.planner import generate_plan
from docweave.plan.schema import load_patch

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.md"


def _copy_sample(tmp_path: Path) -> Path:
    dest = tmp_path / "sample.md"
    shutil.copy2(SAMPLE, dest)
    return dest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Schema tests ---


def test_plan_valid_with_fingerprint(tmp_path: Path) -> None:
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_insert_after.yaml")
    plan = generate_plan(doc, patch)

    assert plan.valid is True
    assert plan.fingerprint == _sha256(doc)
    assert len(plan.resolved_operations) == 1
    assert plan.resolved_operations[0].operation["op"] == "insert_after"


def test_plan_nonexistent_anchor_invalid(tmp_path: Path) -> None:
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_insert_after.yaml")
    # Modify the anchor to reference a nonexistent heading
    patch.operations[0].anchor["value"] = "Nonexistent"
    plan = generate_plan(doc, patch)

    assert plan.valid is False
    assert len(plan.warnings) > 0
    assert "no blocks match" in plan.warnings[0].lower()


# --- Apply tests ---


def test_apply_insert_after(tmp_path: Path) -> None:
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_insert_after.yaml")
    plan = generate_plan(doc, patch)

    result = apply_plan(doc, plan)
    assert result.operations_applied == 1

    content = doc.read_text("utf-8")
    assert "This is a new paragraph inserted after the Purpose heading." in content
    # Should appear after the Purpose heading line
    lines = content.splitlines()
    purpose_idx = next(i for i, ln in enumerate(lines) if ln.strip() == "## Purpose")
    insert_idx = next(
        i for i, ln in enumerate(lines)
        if "new paragraph inserted" in ln
    )
    assert insert_idx > purpose_idx


def test_apply_replace_text(tmp_path: Path) -> None:
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_replace_text.yaml")
    plan = generate_plan(doc, patch)

    result = apply_plan(doc, plan)
    assert result.operations_applied == 1

    content = doc.read_text("utf-8")
    assert "showcase the docweave CLI" in content
    assert "demonstrate docweave" not in content


def test_apply_delete_block(tmp_path: Path) -> None:
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_delete_block.yaml")
    plan = generate_plan(doc, patch)

    result = apply_plan(doc, plan)
    assert result.operations_applied == 1

    content = doc.read_text("utf-8")
    assert "## Non-Functional" not in content


def test_backup_creates_bak_file(tmp_path: Path) -> None:
    doc = _copy_sample(tmp_path)
    original_content = doc.read_text("utf-8")
    patch = load_patch(FIXTURES / "patch_insert_after.yaml")
    plan = generate_plan(doc, patch)

    result = apply_plan(doc, plan, backup=True)
    assert result.backup_path is not None

    bak = Path(result.backup_path)
    assert bak.exists()
    assert bak.read_text("utf-8") == original_content


def test_dry_run_no_modification(tmp_path: Path, run_cli) -> None:
    doc = _copy_sample(tmp_path)
    original_content = doc.read_text("utf-8")
    patch_path = FIXTURES / "patch_insert_after.yaml"

    result = run_cli("apply", str(doc), "--patch", str(patch_path), "--dry-run")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True

    # File should be unchanged
    assert doc.read_text("utf-8") == original_content


def test_fingerprint_conflict(tmp_path: Path) -> None:
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_insert_after.yaml")
    plan = generate_plan(doc, patch)

    # Modify the file after plan generation
    doc.write_text(doc.read_text("utf-8") + "\n# Extra section\n")

    with pytest.raises(FingerprintConflictError):
        apply_plan(doc, plan)


def test_multiple_operations(tmp_path: Path) -> None:
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_insert_after.yaml")
    # Add a second operation
    from docweave.plan.schema import OperationSpec

    patch.operations.append(OperationSpec(
        id="op_002",
        op="replace_text",
        anchor={"by": "quote", "value": "demonstrate docweave"},
        replacement="showcase the docweave CLI",
    ))

    plan = generate_plan(doc, patch)
    assert plan.valid is True
    assert len(plan.resolved_operations) == 2

    result = apply_plan(doc, plan)
    assert result.operations_applied == 2

    content = doc.read_text("utf-8")
    assert "new paragraph inserted" in content
    assert "showcase the docweave CLI" in content


def test_plan_cli_envelope(tmp_path: Path, run_cli) -> None:
    doc = _copy_sample(tmp_path)
    patch_path = FIXTURES / "patch_insert_after.yaml"

    result = run_cli("plan", str(doc), "--patch", str(patch_path))
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "plan"
    assert "resolved_operations" in env["result"]
    assert len(env["result"]["resolved_operations"]) == 1


def test_apply_cli_envelope(tmp_path: Path, run_cli) -> None:
    doc = _copy_sample(tmp_path)
    patch_path = FIXTURES / "patch_insert_after.yaml"

    result = run_cli("apply", str(doc), "--patch", str(patch_path))
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "apply"
    assert env["result"]["operations_applied"] == 1


def test_set_heading_preserves_level(tmp_path: Path) -> None:
    """set_heading should preserve the heading level prefix (e.g. '## ')."""
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_set_heading.yaml")
    plan = generate_plan(doc, patch)
    assert plan.valid is True

    result = apply_plan(doc, plan)
    assert result.operations_applied == 1

    content = doc.read_text("utf-8")
    # "Purpose" was a level-2 heading; the new title should retain "## "
    assert "## New Purpose Title" in content
    # Should NOT have bare "New Purpose Title" without the ## prefix
    lines = [ln.strip() for ln in content.splitlines()]
    heading_line = [ln for ln in lines if "New Purpose Title" in ln]
    assert len(heading_line) == 1
    assert heading_line[0].startswith("## ")


def test_guide_shows_plan_apply(run_cli) -> None:
    result = run_cli("guide")
    assert result.exit_code == 0
    env = result.json
    commands = env["result"]["commands"]
    assert "plan" in commands
    assert commands["plan"]["status"] == "available"
    assert "apply" in commands
    assert commands["apply"]["status"] == "available"


# --- Validation: missing required fields ---


def test_replace_block_missing_content_rejected(tmp_path: Path) -> None:
    """replace_block without content should fail at load_patch time."""
    patch_yaml = tmp_path / "bad_patch.yaml"
    patch_yaml.write_text(
        "version: 1\n"
        "target: {format: markdown}\n"
        "operations:\n"
        "  - id: op_001\n"
        "    op: replace_block\n"
        "    anchor: {by: heading, value: Purpose}\n"
    )
    with pytest.raises(ValueError, match="requires a 'content' field"):
        load_patch(patch_yaml)


def test_replace_text_missing_replacement_rejected(tmp_path: Path) -> None:
    """replace_text without replacement should fail at load_patch time."""
    patch_yaml = tmp_path / "bad_patch.yaml"
    patch_yaml.write_text(
        "version: 1\n"
        "target: {format: markdown}\n"
        "operations:\n"
        "  - id: op_001\n"
        "    op: replace_text\n"
        "    anchor: {by: quote, value: demonstrate docweave}\n"
    )
    with pytest.raises(ValueError, match="requires a 'replacement' field"):
        load_patch(patch_yaml)


def test_invalid_anchor_type_rejected(tmp_path: Path) -> None:
    """Invalid anchor type should be caught at load_patch time."""
    patch_yaml = tmp_path / "bad_patch.yaml"
    patch_yaml.write_text(
        "version: 1\n"
        "target: {format: markdown}\n"
        "operations:\n"
        "  - id: op_001\n"
        "    op: delete_block\n"
        "    anchor: {by: xpath, value: '//div'}\n"
    )
    with pytest.raises(ValueError, match="Invalid anchor type"):
        load_patch(patch_yaml)


def test_duplicate_operation_ids_rejected(tmp_path: Path) -> None:
    """Patch with duplicate operation IDs should fail at load_patch time."""
    patch_yaml = tmp_path / "dup_ids.yaml"
    patch_yaml.write_text(
        "version: 1\n"
        "target: {format: markdown}\n"
        "operations:\n"
        "  - id: op_001\n"
        "    op: delete_block\n"
        "    anchor: {by: heading, value: Purpose}\n"
        "  - id: op_001\n"
        "    op: delete_block\n"
        "    anchor: {by: heading, value: Features}\n"
    )
    with pytest.raises(ValueError, match="Duplicate operation IDs"):
        load_patch(patch_yaml)


def test_plan_out_nonexistent_parent(tmp_path: Path, run_cli) -> None:
    """plan --out to a path with nonexistent parent should return ERR_IO."""
    doc = _copy_sample(tmp_path)
    patch_path = FIXTURES / "patch_insert_after.yaml"
    bad_out = tmp_path / "nonexistent_dir" / "plan.json"

    result = run_cli(
        "plan", str(doc), "--patch", str(patch_path), "--out", str(bad_out),
    )
    assert result.exit_code != 0
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_IO"


# --- GROUP 1: Content kind rendering ---


def test_apply_insert_heading_renders_prefix(tmp_path: Path) -> None:
    """insert_after with kind=heading should produce ## prefix."""
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_insert_heading.yaml")
    plan = generate_plan(doc, patch)
    assert plan.valid is True

    result = apply_plan(doc, plan)
    assert result.operations_applied == 1

    content = doc.read_text("utf-8")
    assert "### New Subsection" in content


def test_apply_insert_code_block_renders_fences(tmp_path: Path) -> None:
    """insert_after with kind=code_block should produce triple-backtick fences."""
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_insert_code.yaml")
    plan = generate_plan(doc, patch)
    assert plan.valid is True

    result = apply_plan(doc, plan)
    assert result.operations_applied == 1

    content = doc.read_text("utf-8")
    assert "```python" in content
    assert "def example():" in content
    assert content.count("```") >= 4  # original fence + new fence (open + close each)


def test_apply_insert_blockquote_renders_prefix(tmp_path: Path) -> None:
    """insert_after with kind=blockquote should produce > prefix."""
    doc = _copy_sample(tmp_path)
    patch = load_patch(FIXTURES / "patch_insert_blockquote.yaml")
    plan = generate_plan(doc, patch)
    assert plan.valid is True

    result = apply_plan(doc, plan)
    assert result.operations_applied == 1

    content = doc.read_text("utf-8")
    assert "> This is an important note." in content


def test_render_content_unit() -> None:
    """Unit test for _render_content helper."""
    from docweave.plan.applier import _render_content

    # paragraph passes through
    assert _render_content("paragraph", "hello") == "hello"
    assert _render_content("markdown", "hello") == "hello"

    # heading with level
    assert _render_content("heading", "Title", level=2) == "## Title"
    assert _render_content("heading", "Title", level=3) == "### Title"

    # heading default level
    assert _render_content("heading", "Title") == "## Title"

    # heading strips existing prefix
    assert _render_content("heading", "## Already", level=2) == "## Already"

    # code block
    rendered = _render_content("code_block", "x = 1", language="python")
    assert rendered.startswith("```python\n")
    assert "x = 1" in rendered
    assert rendered.endswith("```")

    # blockquote
    rendered = _render_content("blockquote", "A quote")
    assert rendered == "> A quote"

    # multiline blockquote
    rendered = _render_content("blockquote", "line1\nline2")
    assert "> line1" in rendered
    assert "> line2" in rendered

    # list item
    assert _render_content("list_item", "an item") == "- an item"

    # unknown kind passes through
    assert _render_content("unknown_kind", "raw") == "raw"


# --- GROUP 6: empty-ops journal, dry-run backup warning ---


def test_empty_ops_no_journal_entry(tmp_path: Path, run_cli) -> None:
    """Applying a patch with zero operations should not create a journal entry."""
    doc = _copy_sample(tmp_path)
    patch_yaml = tmp_path / "empty_patch.yaml"
    patch_yaml.write_text(
        "version: 1\n"
        "target: {format: markdown}\n"
        "operations: []\n"
    )
    result = run_cli("apply", str(doc), "--patch", str(patch_yaml))
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["result"]["journal_txn_id"] is None


def test_apply_evidence_dir_nonexistent_parent(tmp_path: Path, run_cli) -> None:
    """--evidence-dir with nonexistent parent should return ERR_IO."""
    doc = _copy_sample(tmp_path)
    patch_path = FIXTURES / "patch_insert_after.yaml"
    bad_evidence = tmp_path / "nonexistent_parent" / "subdir" / "evidence"

    result = run_cli(
        "apply", str(doc), "--patch", str(patch_path),
        "--evidence-dir", str(bad_evidence),
    )
    assert result.exit_code == 50
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_IO"
    assert "Parent directory" in env["errors"][0]["message"]


def test_dry_run_backup_warns(tmp_path: Path, run_cli) -> None:
    """--dry-run --backup should warn that backup is ignored."""
    doc = _copy_sample(tmp_path)
    patch_path = FIXTURES / "patch_insert_after.yaml"

    result = run_cli(
        "apply", str(doc), "--patch", str(patch_path), "--dry-run", "--backup",
    )
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert any(w["code"] == "WARN_DRY_RUN_BACKUP_IGNORED" for w in env["warnings"])
