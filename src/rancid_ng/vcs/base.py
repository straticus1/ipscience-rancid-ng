"""
Base VCS Backend for RANCID-NG.

Abstract base class for version control system backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class VCSBackend(ABC):
    """Abstract base class for VCS backends."""

    def __init__(self, path: str | Path):
        """Initialize VCS backend with repository path."""
        self.path = Path(path)

    @abstractmethod
    def init(self) -> bool:
        """Initialize a new repository."""
        pass

    @abstractmethod
    def add(self, files: list[str]) -> bool:
        """Stage files for commit."""
        pass

    @abstractmethod
    def commit(self, message: str) -> bool:
        """Commit staged changes."""
        pass

    @abstractmethod
    def diff(self, file: str | None = None) -> str:
        """Get diff of changes."""
        pass

    @abstractmethod
    def status(self) -> str:
        """Get repository status."""
        pass

    @property
    @abstractmethod
    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        pass
