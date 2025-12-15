"""
RANCID-NG Version Control System Module

Provides Git, SVN, and CVS backend support for configuration storage.
"""

from rancid_ng.vcs.git import GitBackend
from rancid_ng.vcs.base import VCSBackend

__all__ = ["VCSBackend", "GitBackend"]
