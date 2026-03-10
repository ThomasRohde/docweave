"""Tests for the CLI module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from docweave.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_version_flag(run_cli):
    result = run_cli("--version")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "version"
    assert env["result"]["version"] == "0.1.0"


def test_guide_returns_valid_envelope(run_cli):
    result = run_cli("guide")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "guide"
    assert "commands" in env["result"]
    assert "error_codes" in env["result"]
    assert "exit_codes" in env["result"]
    assert env["result"]["version"] == "0.1.0"
    assert env["result"]["cli"] == "docweave"
    assert "duration_ms" in env["metrics"]
    assert env["version"] == "0.1.0"


def test_no_args_returns_json_error(run_cli):
    result = run_cli()
    assert result.exit_code == 10
    env = result.json
    assert env["ok"] is False
    assert "No command specified" in env["errors"][0]["message"]


def test_main_wraps_unhandled_exception():
    """Mocking app to raise RuntimeError should produce an error envelope."""
    import io

    with patch("docweave.cli.app") as mock_app:
        mock_app.side_effect = RuntimeError("boom")
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            try:
                main()
            except SystemExit as e:
                assert e.code == 90

        output = captured.getvalue().strip()
        env = json.loads(output)
        assert env["ok"] is False
        assert env["errors"][0]["code"] == "ERR_INTERNAL_UNHANDLED"
        assert "boom" in env["errors"][0]["message"]


def test_main_file_not_found_exit_code():
    """main() should propagate exit code 50 for file-not-found errors."""
    import io

    captured = io.StringIO()
    with patch("sys.stdout", captured):
        try:
            import sys
            sys.argv = ["docweave", "inspect", "nonexistent_file_xyz.md"]
            main()
        except SystemExit as e:
            assert e.code == 50


def test_main_validation_error_exit_code():
    """main() should propagate exit code 10 for validation errors."""
    import io

    captured = io.StringIO()
    with patch("sys.stdout", captured):
        try:
            import sys
            sys.argv = ["docweave", "--format", "yaml", "guide"]
            main()
        except SystemExit as e:
            assert e.code == 10


def test_directory_as_file_error(run_cli, tmp_path):
    """Passing a directory as a file should return ERR_IO_IS_DIRECTORY."""
    result = run_cli("inspect", str(tmp_path))
    assert result.exit_code == 50
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_IO_IS_DIRECTORY"


def test_directory_with_md_extension_error(run_cli, tmp_path):
    """A directory with .md extension should still be ERR_IO_IS_DIRECTORY."""
    fake_md = tmp_path / "fake.md"
    fake_md.mkdir()
    result = run_cli("inspect", str(fake_md))
    assert result.exit_code == 50
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_IO_IS_DIRECTORY"


def test_empty_query_find_error(run_cli):
    """Empty query in find should be rejected as a validation error."""
    sample = FIXTURES / "sample.md"
    result = run_cli("find", str(sample), "  ")
    assert result.exit_code != 0
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_VALIDATION"


def test_format_rejects_invalid(run_cli):
    """--format with unsupported value should fail."""
    result = run_cli("--format", "yaml", "guide")
    assert result.exit_code != 0
    env = result.json
    assert env["ok"] is False
    assert "Unsupported format" in env["errors"][0]["message"]


def test_no_args_emits_clean_json_error():
    """No-args invocation should produce clean JSON only, no help text mixed in."""
    import io

    captured = io.StringIO()
    with patch("sys.stdout", captured):
        try:
            import sys
            sys.argv = ["docweave"]
            main()
        except SystemExit:
            pass

    output = captured.getvalue().strip()
    env = json.loads(output)
    assert env["ok"] is False
    assert env["errors"][0]["message"] != ""
    assert "No command specified" in env["errors"][0]["message"]


def test_h_shorthand(run_cli):
    """'-h' should show help (same as --help)."""
    result = run_cli("-h", expect_json=False)
    assert result.exit_code == 0
    assert "docweave" in result.output.lower() or "usage" in result.output.lower()


def test_apply_missing_plan_file(run_cli, tmp_path):
    """apply --plan with nonexistent file should return exit 50."""
    sample = tmp_path / "doc.md"
    sample.write_text("# Title\n")
    result = run_cli("apply", str(sample), "--plan", str(tmp_path / "nope.json"))
    assert result.exit_code == 50
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_IO_FILE_NOT_FOUND"


def test_anchor_occurrence_zero(run_cli):
    """'-n 0' should be rejected as a validation error."""
    sample = FIXTURES / "sample.md"
    result = run_cli("anchor", str(sample), "heading:Purpose", "-n", "0")
    assert result.exit_code == 10
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_VALIDATION"


def test_anchor_occurrence_negative(run_cli):
    """'-n -1' should be rejected as a validation error."""
    sample = FIXTURES / "sample.md"
    result = run_cli("anchor", str(sample), "heading:Purpose", "-n", "-1")
    assert result.exit_code == 10
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_VALIDATION"


# --- GROUP 2: __main__.py ---


def test_python_m_docweave():
    """python -m docweave should work."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "docweave", "--version"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    env = json.loads(result.stdout.strip())
    assert env["ok"] is True
    assert env["command"] == "version"


# --- GROUP 3: case-insensitive --section, unmatched section warning ---


def test_view_section_case_insensitive(run_cli):
    """--section should match case-insensitively."""
    sample = FIXTURES / "sample.md"
    result = run_cli("view", str(sample), "--section", "purpose")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert len(env["result"]["blocks"]) > 0


def test_view_unmatched_section_warns(run_cli):
    """--section with no match should produce WARN_SECTION_NOT_FOUND."""
    sample = FIXTURES / "sample.md"
    result = run_cli("view", str(sample), "--section", "NonexistentSection")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert len(env["result"]["blocks"]) == 0
    assert any(w["code"] == "WARN_SECTION_NOT_FOUND" for w in env["warnings"])
    # Warning should list available sections
    warn_msg = next(w["message"] for w in env["warnings"] if w["code"] == "WARN_SECTION_NOT_FOUND")
    assert "Available sections" in warn_msg


def test_find_section_case_insensitive(run_cli):
    """find --section should match case-insensitively."""
    sample = FIXTURES / "sample.md"
    result = run_cli("find", str(sample), "demonstrate", "--section", "purpose")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["result"]["total"] >= 1


# --- GROUP 5: --format hints, -V flag ---


def test_version_short_flag_v_upper(run_cli):
    """-V should work as shorthand for --version."""
    result = run_cli("-V")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "version"


def test_format_consumes_command_name_hint(run_cli):
    """docweave --format guide should hint about the mix-up."""
    result = run_cli("--format", "guide")
    env = result.json
    assert env["ok"] is False
    assert "meant to run" in env["errors"][0]["message"]


def test_apply_both_patch_and_plan(run_cli, tmp_path):
    """apply with both --patch and --plan should say 'Cannot specify both'."""
    sample = tmp_path / "doc.md"
    sample.write_text("# Title\n")
    patch = tmp_path / "p.yaml"
    patch.write_text("version: 1\ntarget: {format: markdown}\noperations: []\n")
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    result = run_cli(
        "apply", str(sample), "--patch", str(patch), "--plan", str(plan),
    )
    assert result.exit_code == 10
    env = result.json
    assert env["ok"] is False
    assert "Cannot specify both" in env["errors"][0]["message"]


def test_version_short_flag_v_lower(run_cli):
    """-v should work as shorthand for --version."""
    result = run_cli("-v")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "version"


def test_format_after_subcommand_hint():
    """--format after subcommand should hint it's a global option."""
    import io

    captured = io.StringIO()
    with patch("sys.stdout", captured):
        try:
            import sys
            sys.argv = ["docweave", "inspect", "--format", "json", str(FIXTURES / "sample.md")]
            main()
        except SystemExit:
            pass

    output = captured.getvalue().strip()
    env = json.loads(output)
    assert env["ok"] is False
    assert "--format" in env["errors"][0]["message"]
    assert "global option" in env["errors"][0]["message"]
