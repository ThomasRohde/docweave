"""Patch file models and YAML loader."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator, model_validator


class PatchContent(BaseModel):
    kind: str
    value: str
    level: int | None = None
    language: str | None = None


OperationType = Literal[
    "insert_after",
    "insert_before",
    "replace_block",
    "replace_text",
    "delete_block",
    "set_heading",
    "normalize_whitespace",
]

VALID_ANCHOR_TYPES = {"heading", "quote", "block_id", "hash", "ordinal"}

_NEEDS_CONTENT = {"insert_after", "insert_before", "replace_block", "set_heading"}


class OperationSpec(BaseModel):
    id: str
    op: OperationType
    anchor: dict
    content: PatchContent | None = None
    replacement: str | None = None

    @field_validator("anchor")
    @classmethod
    def _anchor_must_have_by_and_value(cls, v: dict) -> dict:
        if "by" not in v:
            msg = "anchor must have a 'by' key"
            raise ValueError(msg)
        if v["by"] not in VALID_ANCHOR_TYPES:
            valid = ", ".join(sorted(VALID_ANCHOR_TYPES))
            msg = f"Invalid anchor type: {v['by']!r}. Valid types: {valid}"
            raise ValueError(msg)
        if "value" not in v:
            msg = "anchor must have a 'value' key"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _check_required_fields(self) -> OperationSpec:
        if self.op in _NEEDS_CONTENT and self.content is None:
            msg = f"Operation '{self.op}' requires a 'content' field"
            raise ValueError(msg)
        if self.op == "replace_text" and self.replacement is None:
            msg = "Operation 'replace_text' requires a 'replacement' field"
            raise ValueError(msg)
        return self


class PatchFile(BaseModel):
    version: int
    target: dict
    operations: list[OperationSpec]

    @field_validator("version")
    @classmethod
    def _version_must_be_1(cls, v: int) -> int:
        if v != 1:
            msg = f"Unsupported patch version: {v}. Only version 1 is supported."
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _no_duplicate_ids(self) -> PatchFile:
        ids = [op.id for op in self.operations]
        if len(set(ids)) != len(ids):
            seen: set[str] = set()
            dupes: list[str] = []
            for oid in ids:
                if oid in seen:
                    dupes.append(oid)
                seen.add(oid)
            msg = f"Duplicate operation IDs: {dupes}"
            raise ValueError(msg)
        return self


def load_patch(path: Path) -> PatchFile:
    """Load and validate a YAML patch file."""
    try:
        raw = yaml.safe_load(path.read_text("utf-8"))
    except Exception as exc:
        msg = f"Failed to read patch file {path}: {exc}"
        raise ValueError(msg) from exc

    if not isinstance(raw, dict):
        msg = f"Patch file must be a YAML mapping, got {type(raw).__name__}"
        raise ValueError(msg)

    try:
        return PatchFile(**raw)
    except Exception as exc:
        msg = f"Invalid patch file: {exc}"
        raise ValueError(msg) from exc
