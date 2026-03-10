"""Shared test fixtures."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from docweave.cli import app


@pytest.fixture()
def run_cli():
    """Return a helper that invokes the CLI and parses the JSON envelope."""
    runner = CliRunner()

    def _run(*args: str, expect_json: bool = True):
        result = runner.invoke(app, list(args))
        result.json = None
        if expect_json and result.output.strip():
            result.json = json.loads(result.output.strip())
        return result

    return _run
