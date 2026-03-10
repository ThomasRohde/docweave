"""Backend registry: register, detect, and retrieve format adapters."""

from __future__ import annotations

from pathlib import Path

from docweave.backends.base import BackendAdapter

_registry: list[BackendAdapter] = []


def register(backend: BackendAdapter) -> None:
    """Add a backend adapter to the registry."""
    _registry.append(backend)


def detect(path: Path) -> BackendAdapter:
    """Return the best-matching backend for the given file path.

    Raises ValueError if no backend matches.
    """
    scored = [(b, b.detect(path)) for b in _registry]
    scored.sort(key=lambda pair: (-pair[1], pair[0].tier))
    if not scored or scored[0][1] <= 0:
        raise ValueError(f"No backend can handle: {path}")
    return scored[0][0]


def get(name: str) -> BackendAdapter:
    """Return a registered backend by name.

    Raises KeyError if not found.
    """
    for b in _registry:
        if b.name == name:
            return b
    raise KeyError(f"Unknown backend: {name}")


def list_backends() -> list[BackendAdapter]:
    """Return all registered backends."""
    return list(_registry)


def init_backends() -> None:
    """Initialize and register all built-in backends."""
    _registry.clear()
    from docweave.backends.docx_backend import WordBackend
    from docweave.backends.markdown_native import MarkdownBackend

    register(MarkdownBackend())
    register(WordBackend())
