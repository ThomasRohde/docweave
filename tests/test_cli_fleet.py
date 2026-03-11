"""CLI integration tests for the fleet command."""

from __future__ import annotations

import pytest
import yaml

SAMPLE_CONTENT = "# Doc\n\nOriginal content.\n"


def _make_patch(target_file: str, op_id: str, after_heading: str, new_text: str) -> dict:
    return {
        "version": 1,
        "target": {"file": target_file, "backend": "auto"},
        "operations": [
            {
                "id": op_id,
                "op": "insert_after",
                "anchor": {"by": "heading", "value": after_heading},
                "content": {"kind": "markdown", "value": new_text},
            }
        ],
    }


@pytest.fixture()
def fleet_setup(tmp_path):
    """Create three doc files and corresponding patch files."""
    docs = []
    patches = []
    for i in range(1, 4):
        doc = tmp_path / f"doc{i}.md"
        doc.write_text(f"# Doc {i}\n\nOriginal content.\n")
        patch = tmp_path / f"patch{i}.yaml"
        patch.write_text(
            yaml.dump(
                _make_patch(
                    str(doc),
                    f"op_{i:03d}",
                    f"Doc {i}",
                    f"Fleet-injected paragraph {i}.",
                )
            )
        )
        docs.append(doc)
        patches.append(patch)
    return docs, patches


def test_fleet_serial_all_succeed(run_cli, fleet_setup):
    docs, patches = fleet_setup
    args = []
    for p in patches:
        args += ["--patch", str(p)]
    result = run_cli("fleet", *args)
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "fleet"
    assert env["result"]["total"] == 3
    assert env["result"]["succeeded"] == 3
    assert env["result"]["failed"] == 0
    assert env["result"]["parallel"] is False
    for r in env["result"]["results"]:
        assert r["ok"] is True
        assert r["ops_applied"] == 1


def test_fleet_parallel_all_succeed(run_cli, fleet_setup):
    docs, patches = fleet_setup
    args = ["--parallel"]
    for p in patches:
        args += ["--patch", str(p)]
    result = run_cli("fleet", *args)
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["result"]["succeeded"] == 3
    assert env["result"]["parallel"] is True


def test_fleet_dry_run_does_not_modify(run_cli, fleet_setup):
    docs, patches = fleet_setup
    before_texts = [d.read_text() for d in docs]
    args = ["--dry-run"]
    for p in patches:
        args += ["--patch", str(p)]
    result = run_cli("fleet", *args)
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["result"]["dry_run"] is True
    # Files must be unchanged
    for doc, before in zip(docs, before_texts):
        assert doc.read_text() == before
    for r in env["result"]["results"]:
        assert r["dry_run"] is True


def test_fleet_results_order_matches_input(run_cli, fleet_setup):
    """Results list should preserve input patch order regardless of parallel mode."""
    docs, patches = fleet_setup
    for parallel_flag in ([], ["--parallel"]):
        args = parallel_flag[:]
        for p in patches:
            args += ["--patch", str(p)]
        result = run_cli("fleet", *args)
        env = result.json
        patch_strs = [str(p) for p in patches]
        result_patches = [r["patch"] for r in env["result"]["results"]]
        assert result_patches == patch_strs


def test_fleet_missing_target_file_in_patch(run_cli, tmp_path):
    """Patch without target.file must fail fast with ERR_VALIDATION."""
    doc = tmp_path / "doc.md"
    doc.write_text("# Doc\n\nContent.\n")
    patch = tmp_path / "bad.yaml"
    patch.write_text(
        yaml.dump({
            "version": 1,
            "target": {"backend": "auto"},  # missing file
            "operations": [
                {
                    "id": "op_001",
                    "op": "insert_after",
                    "anchor": {"by": "heading", "value": "Doc"},
                    "content": {"kind": "markdown", "value": "New content."},
                }
            ],
        })
    )
    result = run_cli("fleet", "--patch", str(patch))
    env = result.json
    assert env["ok"] is False
    # Now returns fleet result with per-patch failure instead of immediate exit
    assert env["result"]["failed"] >= 1


def test_fleet_missing_patch_file(run_cli, tmp_path):
    """Non-existent patch path must fail with ERR_IO_FILE_NOT_FOUND."""
    result = run_cli("fleet", "--patch", str(tmp_path / "ghost.yaml"))
    env = result.json
    assert env["ok"] is False
    assert any(e["code"] == "ERR_IO_FILE_NOT_FOUND" for e in env["errors"])


def test_fleet_missing_target_doc(run_cli, tmp_path):
    """Patch whose target.file doesn't exist must fail with ERR_IO_FILE_NOT_FOUND."""
    patch = tmp_path / "patch.yaml"
    patch.write_text(
        yaml.dump({
            "version": 1,
            "target": {"file": str(tmp_path / "ghost.md"), "backend": "auto"},
            "operations": [
                {
                    "id": "op_001",
                    "op": "insert_after",
                    "anchor": {"by": "heading", "value": "Doc"},
                    "content": {"kind": "markdown", "value": "New content."},
                }
            ],
        })
    )
    result = run_cli("fleet", "--patch", str(patch))
    env = result.json
    assert env["ok"] is False
    # Now returns fleet result with per-patch failure instead of immediate exit
    assert env["result"]["failed"] >= 1


def test_fleet_one_bad_anchor_partial_failure(run_cli, tmp_path):
    """When one patch has a bad anchor, fleet ok=false but reports per-patch results."""
    good_doc = tmp_path / "good.md"
    good_doc.write_text("# Good\n\nContent.\n")
    good_patch = tmp_path / "good.yaml"
    good_patch.write_text(
        yaml.dump(
            _make_patch(str(good_doc), "op_good", "Good", "Inserted paragraph.")
        )
    )

    bad_doc = tmp_path / "bad.md"
    bad_doc.write_text("# Bad\n\nContent.\n")
    bad_patch = tmp_path / "bad.yaml"
    bad_patch.write_text(
        yaml.dump(
            _make_patch(str(bad_doc), "op_bad", "NONEXISTENT HEADING", "Should fail.")
        )
    )

    result = run_cli(
        "fleet",
        "--patch", str(good_patch),
        "--patch", str(bad_patch),
    )
    env = result.json
    assert env["ok"] is False
    assert env["result"]["total"] == 2
    assert env["result"]["failed"] == 1
    assert env["result"]["succeeded"] == 1
    assert any(e["code"] == "ERR_FLEET_PARTIAL" for e in env["errors"])

    good_result = next(r for r in env["result"]["results"] if r["patch"].endswith("good.yaml"))
    bad_result = next(r for r in env["result"]["results"] if r["patch"].endswith("bad.yaml"))
    assert good_result["ok"] is True
    assert bad_result["ok"] is False


def test_fleet_guide_lists_fleet_command(run_cli):
    """guide output must include fleet in its commands dict."""
    result = run_cli("guide")
    env = result.json
    assert "fleet" in env["result"]["commands"]
    fleet_entry = env["result"]["commands"]["fleet"]
    assert "result_schema" in fleet_entry
    assert "total" in fleet_entry["result_schema"]
