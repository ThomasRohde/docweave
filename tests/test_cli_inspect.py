"""CLI integration tests for inspect and view commands."""

from __future__ import annotations

from pathlib import Path

from docweave.backends.markdown_native import MarkdownBackend

SAMPLE = Path(__file__).parent / "fixtures" / "sample.md"


def test_inspect_envelope(run_cli):
    result = run_cli("inspect", str(SAMPLE))
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "inspect"
    assert env["result"]["backend"] == "markdown-native"
    assert len(env["result"]["headings"]) == 7
    assert env["result"]["block_count"] == 18


def test_inspect_file_not_found(run_cli):
    result = run_cli("inspect", "nonexistent.md")
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_IO_FILE_NOT_FOUND"


def test_inspect_unsupported_file(run_cli, tmp_path):
    unsupported = tmp_path / "data.xyz"
    unsupported.write_text("hello")
    result = run_cli("inspect", str(unsupported))
    env = result.json
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "ERR_VALIDATION_NO_BACKEND"


def test_view_envelope(run_cli):
    result = run_cli("view", str(SAMPLE))
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "view"
    assert isinstance(env["result"]["blocks"], list)
    assert env["result"]["block_count"] == 18


def test_view_section_filter(run_cli):
    result = run_cli("view", str(SAMPLE), "--section", "Purpose")
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    blocks = env["result"]["blocks"]
    # Should include the "Purpose" heading and its paragraph
    assert len(blocks) == 2
    for b in blocks:
        assert "Purpose" in b["section_path"]


def test_table_parsed_as_table(tmp_path):
    """Tables should be parsed as kind='table', not 'paragraph'."""
    md_content = (
        "# Doc\n\n"
        "| Name | Value |\n"
        "| ---- | ----- |\n"
        "| A    | 1     |\n"
        "| B    | 2     |\n"
    )
    doc_file = tmp_path / "table.md"
    doc_file.write_text(md_content)

    backend = MarkdownBackend()
    doc = backend.load_view(doc_file)
    table_blocks = [b for b in doc.blocks if b.kind == "table"]
    assert len(table_blocks) == 1
    assert "Name" in table_blocks[0].text
    assert "Value" in table_blocks[0].text


def test_inspect_tables_true(tmp_path):
    """inspect should report tables=True in supports."""
    md_content = "# Doc\n\nSome content.\n"
    doc_file = tmp_path / "doc.md"
    doc_file.write_text(md_content)

    backend = MarkdownBackend()
    result = backend.inspect(doc_file)
    assert result.supports["tables"] is True
