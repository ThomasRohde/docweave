"""Structured JSON envelope for all CLI output."""

from __future__ import annotations

import secrets
import sys
from datetime import UTC, datetime
from typing import Any

import orjson
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None
    hint: str | None = None


class Warning(BaseModel):
    code: str
    message: str


class Metrics(BaseModel):
    duration_ms: int = 0


class Envelope(BaseModel):
    ok: bool
    request_id: str
    command: str
    target: str | None = None
    result: Any = None
    errors: list[ErrorDetail] = Field(default_factory=list)
    warnings: list[Warning] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    version: str = ""


def _generate_request_id() -> str:
    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"req_{stamp}_{suffix}"


def success_envelope(
    command: str,
    result: Any,
    *,
    target: str | None = None,
    warnings: list[Warning] | None = None,
    duration_ms: int = 0,
) -> Envelope:
    from docweave import __version__

    return Envelope(
        ok=True,
        request_id=_generate_request_id(),
        command=command,
        target=target,
        result=result,
        warnings=warnings or [],
        metrics=Metrics(duration_ms=duration_ms),
        version=__version__,
    )


def error_envelope(
    command: str,
    errors: list[ErrorDetail],
    *,
    target: str | None = None,
    warnings: list[Warning] | None = None,
    duration_ms: int = 0,
) -> Envelope:
    from docweave import __version__

    return Envelope(
        ok=False,
        request_id=_generate_request_id(),
        command=command,
        target=target,
        result=None,
        errors=errors,
        warnings=warnings or [],
        metrics=Metrics(duration_ms=duration_ms),
        version=__version__,
    )


def emit(envelope: Envelope, *, file: Any = None) -> None:
    """Serialize envelope as JSON and write to stdout (or given file)."""
    data = orjson.dumps(envelope.model_dump(mode="json"))
    out = file or sys.stdout
    if hasattr(out, "buffer"):
        out.buffer.write(data)
        out.buffer.write(b"\n")
        out.buffer.flush()
    else:
        out.write(data.decode("utf-8"))
        out.write("\n")
        if hasattr(out, "flush"):
            out.flush()
