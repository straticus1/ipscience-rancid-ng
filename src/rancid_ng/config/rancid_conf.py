"""
rancid.conf Parser for RANCID-NG.

Parses the main RANCID configuration file (rancid.conf).

This file sets environment variables and configuration options
for RANCID operations. Format is shell-like:
    VARIABLE=value; export VARIABLE
or simply:
    VARIABLE=value
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RancidConfig:
    """Main RANCID configuration."""

    # Base directories
    basedir: str = "/var/rancid"
    tmpdir: str = "/tmp"
    logdir: str = ""  # Default: $BASEDIR/logs
    cvsroot: str = ""  # Default: $BASEDIR/CVS

    # Version control system
    rcssys: str = "git"  # cvs, svn, or git

    # Email settings
    sendmail: str = "/usr/sbin/sendmail"
    maildomain: str = ""
    mailheaders: str = "Precedence: bulk\nAuto-submitted: auto-generated"
    mailopts: str = ""
    mailsplit: int = 0

    # Groups
    list_of_groups: list[str] = field(default_factory=list)

    # Filtering options
    filter_pwds: str = "YES"  # NO, YES, ALL
    nocommstr: bool = False
    filter_osc: str = "YES"  # NO, YES, ALL
    aclsort: str = "YES"
    aclfilterseq: str = "YES"
    aclfilterregex: str = ""

    # Timing options
    max_rounds: int = 4
    oldtime: int = 24
    locktime: int = 4
    par_count: int = 5

    # Diff options
    diffscript: str = ""

    @classmethod
    def from_file(cls, path: str | Path) -> "RancidConfig":
        """
        Load configuration from a file.

        Args:
            path: Path to rancid.conf

        Returns:
            RancidConfig instance
        """
        config = cls()
        path = Path(path)

        if not path.exists():
            return config

        with open(path) as f:
            for line in f:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Parse variable assignment
                # Handles: VAR=value, VAR="value", VAR=value; export VAR
                match = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)$', line, re.I)
                if not match:
                    continue

                var_name = match.group(1).upper()
                value = match.group(2)

                # Clean up value
                # Remove trailing "; export VAR"
                value = re.sub(r';\s*export\s+\w+\s*$', '', value)
                # Remove quotes
                value = value.strip('"\'')
                # Expand $BASEDIR references
                if "$BASEDIR" in value:
                    value = value.replace("$BASEDIR", config.basedir)

                # Apply configuration
                config._set_value(var_name, value)

        # Set derived defaults
        if not config.logdir:
            config.logdir = os.path.join(config.basedir, "logs")
        if not config.cvsroot:
            config.cvsroot = os.path.join(config.basedir, "CVS")

        return config

    def _set_value(self, name: str, value: str) -> None:
        """
        Set a configuration value by name.

        Args:
            name: Variable name
            value: Variable value
        """
        name_lower = name.lower()

        if name_lower == "basedir":
            self.basedir = value
        elif name_lower == "tmpdir":
            self.tmpdir = value
        elif name_lower == "logdir":
            self.logdir = value
        elif name_lower == "cvsroot":
            self.cvsroot = value
        elif name_lower == "rcssys":
            self.rcssys = value.lower()
        elif name_lower == "sendmail":
            self.sendmail = value
        elif name_lower == "maildomain":
            self.maildomain = value
        elif name_lower == "mailheaders":
            self.mailheaders = value.replace("\\n", "\n")
        elif name_lower == "mailopts":
            self.mailopts = value
        elif name_lower == "mailsplit":
            try:
                self.mailsplit = int(value)
            except ValueError:
                pass
        elif name_lower == "list_of_groups":
            # Handle space or comma separated groups
            groups = re.split(r'[\s,]+', value)
            # Handle "$LIST_OF_GROUPS additional_groups" syntax
            if "$LIST_OF_GROUPS" in value:
                groups = [g for g in groups if g != "$LIST_OF_GROUPS"]
                self.list_of_groups.extend(groups)
            else:
                self.list_of_groups = [g for g in groups if g]
        elif name_lower == "filter_pwds":
            self.filter_pwds = value.upper()
        elif name_lower == "nocommstr":
            self.nocommstr = value.upper() == "YES"
        elif name_lower == "filter_osc":
            self.filter_osc = value.upper()
        elif name_lower == "aclsort":
            self.aclsort = value.upper()
        elif name_lower == "aclfilterseq":
            self.aclfilterseq = value.upper()
        elif name_lower == "aclfilterregex":
            self.aclfilterregex = value
        elif name_lower == "max_rounds":
            try:
                self.max_rounds = int(value)
            except ValueError:
                pass
        elif name_lower == "oldtime":
            try:
                self.oldtime = int(value)
            except ValueError:
                pass
        elif name_lower == "locktime":
            try:
                self.locktime = int(value)
            except ValueError:
                pass
        elif name_lower == "par_count":
            try:
                self.par_count = int(value)
            except ValueError:
                pass
        elif name_lower == "diffscript":
            self.diffscript = value

    def to_env(self) -> dict[str, str]:
        """
        Export configuration as environment variables.

        Returns:
            Dictionary of environment variables
        """
        env = {
            "BASEDIR": self.basedir,
            "TMPDIR": self.tmpdir,
            "LOGDIR": self.logdir,
            "CVSROOT": self.cvsroot,
            "RCSSYS": self.rcssys,
            "SENDMAIL": self.sendmail,
            "FILTER_PWDS": self.filter_pwds,
            "FILTER_OSC": self.filter_osc,
            "ACLSORT": self.aclsort,
            "ACLFILTERSEQ": self.aclfilterseq,
            "MAX_ROUNDS": str(self.max_rounds),
            "OLDTIME": str(self.oldtime),
            "LOCKTIME": str(self.locktime),
            "PAR_COUNT": str(self.par_count),
        }

        if self.nocommstr:
            env["NOCOMMSTR"] = "YES"
        if self.maildomain:
            env["MAILDOMAIN"] = self.maildomain
        if self.mailheaders:
            env["MAILHEADERS"] = self.mailheaders
        if self.mailopts:
            env["MAILOPTS"] = self.mailopts
        if self.mailsplit:
            env["MAILSPLIT"] = str(self.mailsplit)
        if self.aclfilterregex:
            env["ACLFILTERREGEX"] = self.aclfilterregex
        if self.diffscript:
            env["DIFFSCRIPT"] = self.diffscript
        if self.list_of_groups:
            env["LIST_OF_GROUPS"] = " ".join(self.list_of_groups)

        return env

    def apply_to_env(self) -> None:
        """Apply configuration to the current environment."""
        for key, value in self.to_env().items():
            os.environ[key] = value


def load_rancid_conf() -> RancidConfig:
    """
    Load rancid.conf from default locations.

    Searches:
    1. RANCID_CONF environment variable
    2. /etc/rancid/rancid.conf
    3. /usr/local/etc/rancid/rancid.conf

    Returns:
        RancidConfig instance
    """
    # Check environment variable
    env_path = os.environ.get("RANCID_CONF")
    if env_path and Path(env_path).exists():
        return RancidConfig.from_file(env_path)

    # Try default locations
    locations = [
        "/etc/rancid/rancid.conf",
        "/usr/local/etc/rancid/rancid.conf",
    ]

    for location in locations:
        if Path(location).exists():
            return RancidConfig.from_file(location)

    # Return defaults
    return RancidConfig()
