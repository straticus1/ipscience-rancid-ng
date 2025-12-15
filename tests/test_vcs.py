"""Tests for RANCID-NG VCS backends."""

import subprocess
from pathlib import Path

import pytest

from rancid_ng.vcs.git import GitBackend
from rancid_ng.vcs.base import VCSBackend


class TestGitBackend:
    """Tests for Git VCS backend."""

    def test_init_creates_repo(self, temp_dir):
        """Test initializing a Git repository."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)

        result = backend.init()
        assert result is True
        assert (repo_path / ".git").exists()

    def test_init_existing_dir(self, temp_dir):
        """Test initializing in existing directory."""
        repo_path = temp_dir / "existing"
        repo_path.mkdir()

        backend = GitBackend(repo_path)
        result = backend.init()

        assert result is True
        assert (repo_path / ".git").exists()

    def test_add_files(self, temp_dir):
        """Test staging files."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)
        backend.init()

        # Create a file
        test_file = repo_path / "test.txt"
        test_file.write_text("test content")

        result = backend.add(["test.txt"])
        assert result is True

    def test_commit(self, temp_dir):
        """Test committing changes."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)
        backend.init()

        # Configure git user for the test repo
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
        )

        # Create and stage a file
        test_file = repo_path / "test.txt"
        test_file.write_text("test content")
        backend.add(["test.txt"])

        result = backend.commit("Test commit")
        assert result is True

    def test_status_empty_repo(self, temp_dir):
        """Test status on empty repo."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)
        backend.init()

        status = backend.status()
        assert status == ""

    def test_status_with_changes(self, temp_dir):
        """Test status with uncommitted changes."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)
        backend.init()

        # Create an untracked file
        test_file = repo_path / "test.txt"
        test_file.write_text("test content")

        status = backend.status()
        assert "test.txt" in status

    def test_has_changes(self, temp_dir):
        """Test has_changes property."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)
        backend.init()

        # No changes initially
        assert backend.has_changes is False

        # Create a file
        test_file = repo_path / "test.txt"
        test_file.write_text("test content")

        # Now has changes
        assert backend.has_changes is True

    def test_diff(self, temp_dir):
        """Test diff output."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)
        backend.init()

        # Configure git user
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
        )

        # Create, add, and commit a file
        test_file = repo_path / "test.txt"
        test_file.write_text("original content")
        backend.add(["test.txt"])
        backend.commit("Initial commit")

        # Modify the file
        test_file.write_text("modified content")

        diff = backend.diff("test.txt")
        assert "modified content" in diff or "original" in diff

    def test_log(self, temp_dir):
        """Test log output."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)
        backend.init()

        # Configure git user
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
        )

        # Create and commit a file
        test_file = repo_path / "test.txt"
        test_file.write_text("content")
        backend.add(["test.txt"])
        backend.commit("My commit message")

        log = backend.log()
        assert "My commit message" in log

    def test_path_property(self, temp_dir):
        """Test that path is stored correctly."""
        repo_path = temp_dir / "test_repo"
        backend = GitBackend(repo_path)

        assert backend.path == repo_path


class TestVCSBackendAbstract:
    """Tests for VCSBackend abstract base class."""

    def test_cannot_instantiate_directly(self):
        """Test that VCSBackend cannot be instantiated."""
        with pytest.raises(TypeError):
            VCSBackend("/some/path")

    def test_subclass_must_implement_methods(self):
        """Test that subclasses must implement abstract methods."""

        class IncompleteBackend(VCSBackend):
            pass

        with pytest.raises(TypeError):
            IncompleteBackend("/some/path")
