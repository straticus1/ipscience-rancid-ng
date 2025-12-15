"""
Git Backend for RANCID-NG.

Provides Git-based version control for configuration storage.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rancid_ng.vcs.base import VCSBackend


class GitBackend(VCSBackend):
    """Git version control backend."""

    def init(self) -> bool:
        """Initialize a new Git repository."""
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "init"],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def add(self, files: list[str]) -> bool:
        """Stage files for commit."""
        try:
            result = subprocess.run(
                ["git", "add"] + files,
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def commit(self, message: str) -> bool:
        """Commit staged changes."""
        try:
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def diff(self, file: str | None = None) -> str:
        """Get diff of changes."""
        try:
            cmd = ["git", "diff"]
            if file:
                cmd.append(file)
            result = subprocess.run(
                cmd,
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            return result.stdout
        except Exception:
            return ""

    def status(self) -> str:
        """Get repository status."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            return result.stdout
        except Exception:
            return ""

    @property
    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        return bool(self.status().strip())

    def log(self, count: int = 10) -> str:
        """Get recent commit log."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{count}", "--oneline"],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            return result.stdout
        except Exception:
            return ""
