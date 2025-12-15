"""Pytest configuration and fixtures for RANCID-NG tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_cloginrc(temp_dir: Path) -> Path:
    """Create a sample .cloginrc file for testing."""
    cloginrc_path = temp_dir / ".cloginrc"
    cloginrc_content = """
# Sample cloginrc for testing
add user router* admin
add password router* {secret123} {enable456}
add method router1.example.com ssh
add method router2.example.com telnet ssh
add method *.legacy.example.com telnet
add noenable switch* 1
add autoenable firewall* 1
add timeout slow* 120
add cyphertype secure* aes256-ctr
add identity router-secure* /home/admin/.ssh/id_rsa
add enauser router-enable* enableuser
"""
    cloginrc_path.write_text(cloginrc_content)
    return cloginrc_path


@pytest.fixture
def sample_router_db(temp_dir: Path) -> Path:
    """Create a sample router.db file for testing."""
    router_db_path = temp_dir / "router.db"
    router_db_content = """
# Sample router.db
router1.example.com:cisco:up
router2.example.com:juniper:up
switch1.example.com:arista:up
firewall1.example.com:paloalto:up
# down device
router3.example.com:cisco:down
"""
    router_db_path.write_text(router_db_content)
    return router_db_path


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Clean environment variables for testing."""
    env_vars = [
        "FILTER_PWDS",
        "NOCOMMSTR",
        "FILTER_OSC",
        "ACLFILTERSEQ",
        "ACLFILTERREGEX",
    ]
    original_values = {var: os.environ.get(var) for var in env_vars}

    # Clear the variables
    for var in env_vars:
        if var in os.environ:
            del os.environ[var]

    yield

    # Restore original values
    for var, value in original_values.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]
