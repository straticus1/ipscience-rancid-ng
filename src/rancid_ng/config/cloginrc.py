"""
cloginrc Parser for RANCID-NG.

Parses the .cloginrc authentication configuration file.

File format:
    add directive hostname_glob value [value2 ...]

Directives:
    - password: VTY password and optional enable password
    - user: Username
    - userpassword: User password (if different from VTY)
    - userprompt: Username prompt regex
    - passprompt: Password prompt regex
    - method: Connection methods (ssh, telnet, rsh)
    - noenable: Disable enable mode
    - enauser: Enable username
    - enableprompt: Enable password prompt
    - autoenable: Auto-enable after login
    - cyphertype: SSH cipher type
    - identity: SSH identity file
    - timeout: Connection timeout

Values in braces {} are literal strings.
$env(VAR) expands environment variables.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AuthConfig:
    """Authentication configuration for a host."""

    hostname: str
    user: str | None = None
    password: str | None = None
    enable_password: str | None = None
    user_password: str | None = None
    user_prompt: str | None = None
    pass_prompt: str | None = None
    enable_prompt: str | None = None
    methods: list[str] = field(default_factory=lambda: ["ssh", "telnet"])
    noenable: bool = False
    autoenable: bool = False
    enauser: str | None = None
    cyphertype: str | None = None
    identity: str | None = None
    timeout: int | None = None

    def get_password(self) -> str | None:
        """Get the appropriate password (user_password or password)."""
        return self.user_password or self.password

    def get_enable_password(self) -> str | None:
        """Get the enable password."""
        return self.enable_password


class CloginrcParser:
    """
    Parser for .cloginrc authentication configuration files.

    The parser reads directives and stores them with hostname glob patterns.
    When querying for a host, the first matching pattern wins.
    """

    # Default prompt patterns
    DEFAULT_USER_PROMPT = r"(Username|login|user name):"
    DEFAULT_PASS_PROMPT = r"[Pp]assword:"
    DEFAULT_ENABLE_PROMPT = r"[Pp]assword:"

    def __init__(self):
        """Initialize the parser."""
        # Store directives as list of (glob_pattern, directive, values)
        self._directives: list[tuple[str, str, list[str]]] = []
        self._loaded_files: set[str] = set()

    def load_file(self, path: str | Path) -> bool:
        """
        Load a .cloginrc file.

        Args:
            path: Path to the cloginrc file

        Returns:
            True if file was loaded successfully
        """
        path = Path(path).expanduser()
        if not path.exists():
            return False

        # Prevent circular includes
        path_str = str(path.resolve())
        if path_str in self._loaded_files:
            return True
        self._loaded_files.add(path_str)

        with open(path) as f:
            for line in f:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Handle include directive
                if line.startswith("include "):
                    include_path = self._expand_value(line[8:].strip())
                    self.load_file(include_path)
                    continue

                # Parse add directive
                if line.startswith("add "):
                    self._parse_add_directive(line[4:])

        return True

    def _parse_add_directive(self, line: str) -> None:
        """
        Parse an 'add' directive line.

        Args:
            line: Line content after 'add '
        """
        # Tokenize the line, handling {} quoted values
        tokens = self._tokenize(line)
        if len(tokens) < 3:
            return

        directive = tokens[0].lower()
        hostname_glob = tokens[1]
        values = [self._expand_value(v) for v in tokens[2:]]

        self._directives.append((hostname_glob, directive, values))

    def _tokenize(self, line: str) -> list[str]:
        """
        Tokenize a line, handling {} quoted values.

        Args:
            line: Line to tokenize

        Returns:
            List of tokens
        """
        tokens = []
        current = ""
        in_braces = False

        i = 0
        while i < len(line):
            char = line[i]

            if char == "{" and not in_braces:
                in_braces = True
                i += 1
                continue
            elif char == "}" and in_braces:
                in_braces = False
                tokens.append(current)
                current = ""
                i += 1
                continue
            elif char.isspace() and not in_braces:
                if current:
                    tokens.append(current)
                    current = ""
                i += 1
                continue

            current += char
            i += 1

        if current:
            tokens.append(current)

        return tokens

    def _expand_value(self, value: str) -> str:
        """
        Expand environment variables in a value.

        Handles $env(VAR) syntax.

        Args:
            value: Value to expand

        Returns:
            Expanded value
        """
        # Handle $env(VAR) syntax
        pattern = r'\$env\(([^)]+)\)'

        def replace_env(match):
            var_name = match.group(1)
            return os.environ.get(var_name, "")

        return re.sub(pattern, replace_env, value)

    def get_auth(self, hostname: str) -> AuthConfig:
        """
        Get authentication configuration for a host.

        The first matching glob pattern for each directive wins.

        Args:
            hostname: Hostname to get auth for

        Returns:
            AuthConfig with matched settings
        """
        config = AuthConfig(hostname=hostname)

        # Track which directives we've already matched
        matched: set[str] = set()

        for glob_pattern, directive, values in self._directives:
            # Skip if we already have this directive
            if directive in matched:
                continue

            # Check if hostname matches glob
            if not fnmatch.fnmatch(hostname, glob_pattern):
                continue

            matched.add(directive)

            # Apply the directive
            if directive == "user":
                config.user = values[0] if values else None
            elif directive == "password":
                config.password = values[0] if values else None
                if len(values) > 1:
                    config.enable_password = values[1]
            elif directive == "userpassword":
                config.user_password = values[0] if values else None
            elif directive == "userprompt":
                config.user_prompt = values[0] if values else None
            elif directive == "passprompt":
                config.pass_prompt = values[0] if values else None
            elif directive == "enableprompt":
                config.enable_prompt = values[0] if values else None
            elif directive == "method":
                config.methods = values if values else ["ssh", "telnet"]
            elif directive == "noenable":
                config.noenable = values[0] == "1" if values else False
            elif directive == "autoenable":
                config.autoenable = values[0] == "1" if values else False
            elif directive == "enauser":
                config.enauser = values[0] if values else None
            elif directive == "cyphertype":
                config.cyphertype = values[0] if values else None
            elif directive == "identity":
                config.identity = values[0] if values else None
            elif directive == "timeout":
                try:
                    config.timeout = int(values[0]) if values else None
                except ValueError:
                    pass

        # Set defaults for prompts
        if config.user_prompt is None:
            config.user_prompt = self.DEFAULT_USER_PROMPT
        if config.pass_prompt is None:
            config.pass_prompt = self.DEFAULT_PASS_PROMPT
        if config.enable_prompt is None:
            config.enable_prompt = self.DEFAULT_ENABLE_PROMPT

        # Default user to current user
        if config.user is None:
            config.user = os.environ.get("USER", os.environ.get("LOGNAME", ""))

        return config

    def load_default(self) -> bool:
        """
        Load from default locations.

        Searches:
        1. $HOME/.cloginrc
        2. /etc/rancid/.cloginrc

        Returns:
            True if any file was loaded
        """
        loaded = False

        # Try home directory first
        home_cloginrc = Path.home() / ".cloginrc"
        if home_cloginrc.exists():
            loaded = self.load_file(home_cloginrc) or loaded

        # Try system location
        system_cloginrc = Path("/etc/rancid/.cloginrc")
        if system_cloginrc.exists():
            loaded = self.load_file(system_cloginrc) or loaded

        return loaded


def load_cloginrc() -> CloginrcParser:
    """
    Load .cloginrc from default locations.

    Returns:
        Configured CloginrcParser
    """
    parser = CloginrcParser()
    parser.load_default()
    return parser
