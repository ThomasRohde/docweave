"""Abstract base class for backend adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BackendAdapter(ABC):
    """Base class all format backends must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this backend (e.g. 'markdown')."""

    @property
    @abstractmethod
    def tier(self) -> int:
        """Priority tier: lower = tried first."""

    @property
    @abstractmethod
    def extensions(self) -> set[str]:
        """File extensions this backend handles (e.g. {'.md', '.markdown'})."""

    @abstractmethod
    def detect(self, path: Path) -> float:
        """Return a confidence score 0.0–1.0 that this backend can handle the file."""

    @abstractmethod
    def inspect(self, path: Path) -> dict[str, Any]:
        """Return structural metadata about the document."""

    @abstractmethod
    def load_view(self, path: Path) -> Any:
        """Load a parsed view of the document for editing."""

    @abstractmethod
    def resolve_anchor(self, view: Any, anchor: dict[str, Any]) -> Any:
        """Resolve an anchor spec to a location in the document view."""

    @abstractmethod
    def plan(self, view: Any, patches: list[dict[str, Any]]) -> dict[str, Any]:
        """Produce an edit plan from a list of patch operations."""

    @abstractmethod
    def apply(self, view: Any, plan: dict[str, Any]) -> str:
        """Apply an edit plan and return the new document content."""

    @abstractmethod
    def validate(self, original: str, modified: str) -> list[dict[str, Any]]:
        """Validate the modified document against the original."""

    @abstractmethod
    def diff(self, original: str, modified: str) -> dict[str, Any]:
        """Produce a structured diff between original and modified content."""
