"""CLI integration tests for find and anchor commands."""

from __future__ import annotations

from pathlib import Path

SAMPLE = Path(__file__).parent / "fixtures" / "sample.md"


# --- find command ---


def test_find_returns_matches(run_cli):
    result = run_cli("find", str(SAMPLE), "demonstrate")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "find"
    assert len(env["result"]["matches"]) >= 1
    assert env["result"]["total"] >= 1


def test_find_no_results(run_cli):
    result = run_cli("find", str(SAMPLE), "zzzzz")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["result"]["matches"] == []
    assert env["result"]["total"] == 0


def test_find_file_not_found(run_cli):
    result = run_cli("find", "nonexistent.md", "hello")
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_IO_FILE_NOT_FOUND"


# --- anchor command ---


def test_anchor_heading(run_cli):
    result = run_cli("anchor", str(SAMPLE), "heading:Purpose")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "anchor"
    assert env["result"]["selected"]["confidence"] == 1.0


def test_anchor_block_id(run_cli):
    result = run_cli("anchor", str(SAMPLE), "block_id:blk_001")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["result"]["selected"]["confidence"] == 1.0
    assert env["result"]["selected"]["block_id"] == "blk_001"


def test_anchor_not_found(run_cli):
    result = run_cli("anchor", str(SAMPLE), "heading:Nonexistent")
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_VALIDATION_ANCHOR_NOT_FOUND"


def test_anchor_ambiguous_warning(run_cli):
    # "must" appears in two paragraphs: "The tool must parse Markdown correctly."
    # and "Performance must be acceptable."
    result = run_cli("anchor", str(SAMPLE), "quote:must")
    env = result.json
    assert env["ok"] is True
    assert len(env["warnings"]) >= 1
    assert env["warnings"][0]["code"] == "WARN_ANCHOR_AMBIGUOUS"


# --- guide updated ---


def test_anchor_limit_truncates_matches(run_cli, tmp_path):
    """--limit should cap the number of fuzzy matches returned."""
    # Create a file with many similarly-named headings
    lines = ["# Document\n\n"]
    for i in range(50):
        lines.append(f"## Section {i}\n\nContent for section {i}.\n\n")
    doc = tmp_path / "many_sections.md"
    doc.write_text("".join(lines))

    result = run_cli("anchor", str(doc), "heading:Section 25", "--limit", "5")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert len(env["result"]["matches"]) <= 5
    # total should reflect the actual number found before truncation
    assert env["result"]["total"] >= 5
    if env["result"]["total"] > 5:
        assert any(w["code"] == "WARN_MATCHES_TRUNCATED" for w in env["warnings"])


def test_anchor_limit_zero_no_selected(run_cli):
    """--limit 0 should return selected=None and matches=[]."""
    result = run_cli("anchor", str(SAMPLE), "heading:Purpose", "--limit", "0")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["result"]["selected"] is None
    assert env["result"]["matches"] == []
    assert env["result"]["total"] >= 1
    assert any(w["code"] == "WARN_MATCHES_TRUNCATED" for w in env["warnings"])


def test_anchor_occurrence_out_of_range(run_cli):
    """Requesting occurrence beyond available matches gives informative error."""
    result = run_cli("anchor", str(SAMPLE), "heading:Purpose", "-n", "5")
    assert result.exit_code == 10
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_VALIDATION_ANCHOR_NOT_FOUND"
    assert "Occurrence 5" in env["errors"][0]["message"]
    assert "blocks match" in env["errors"][0]["message"]


def test_guide_shows_new_commands(run_cli):
    result = run_cli("guide")
    assert result.exit_code == 0
    env = result.json
    commands = env["result"]["commands"]
    assert "find" in commands
    assert commands["find"]["status"] == "available"
    assert "anchor" in commands
    assert commands["anchor"]["status"] == "available"
