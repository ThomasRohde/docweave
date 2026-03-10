"""Tests for the envelope module."""

from __future__ import annotations

import io
import json
import re

from docweave.envelope import (
    ErrorDetail,
    _generate_request_id,
    emit,
    error_envelope,
    success_envelope,
)


def test_success_envelope_has_all_fields():
    env = success_envelope("test", {"key": "value"})
    data = env.model_dump(mode="json")
    required = {
        "ok", "request_id", "command", "target", "result",
        "errors", "warnings", "metrics", "version",
    }
    assert required == set(data.keys())


def test_success_envelope_ok_is_true():
    env = success_envelope("test", {"key": "value"})
    assert env.ok is True
    assert env.result == {"key": "value"}


def test_error_envelope_ok_is_false_and_result_is_none():
    env = error_envelope("test", [ErrorDetail(code="ERR_TEST", message="oops")])
    assert env.ok is False
    assert env.result is None
    assert len(env.errors) == 1
    assert env.errors[0].code == "ERR_TEST"


def test_request_id_unique_and_formatted():
    ids = {_generate_request_id() for _ in range(50)}
    assert len(ids) == 50
    for rid in ids:
        assert re.match(r"^req_\d{8}_\d{6}_[0-9a-f]{4}$", rid)


def test_warnings_and_errors_always_lists():
    env = success_envelope("test", None)
    assert isinstance(env.warnings, list)
    assert isinstance(env.errors, list)

    env2 = error_envelope("test", [])
    assert isinstance(env2.warnings, list)
    assert isinstance(env2.errors, list)


def test_emit_writes_valid_json():
    env = success_envelope("test", {"a": 1})
    buf = io.StringIO()
    emit(env, file=buf)
    raw = buf.getvalue().strip()
    parsed = json.loads(raw)
    assert parsed["ok"] is True
    assert parsed["result"] == {"a": 1}
