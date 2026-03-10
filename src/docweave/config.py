"""Runtime configuration and exit-code constants."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


class ExitCode:
    SUCCESS = 0
    VALIDATION = 10
    PERMISSION = 20
    CONFLICT = 40
    IO = 50
    INTERNAL = 90


@dataclass(frozen=True)
class RuntimeConfig:
    format: str
    llm_mode: bool
    is_tty: bool


def detect_config(format_override: str | None = None) -> RuntimeConfig:
    """Build a RuntimeConfig from environment and terminal state."""
    llm_mode = os.environ.get("LLM", "").lower() in ("1", "true", "yes")
    is_tty = sys.stdout.isatty()
    fmt = format_override or ("json" if llm_mode else "json")
    return RuntimeConfig(format=fmt, llm_mode=llm_mode, is_tty=is_tty)
