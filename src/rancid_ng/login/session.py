"""
Login Session Management for RANCID-NG.

Provides the main LoginSession class that handles:
- Connection establishment (SSH, Telnet)
- Authentication (username, password, enable)
- Prompt detection and matching
- Command execution
- Pager handling
"""

from __future__ import annotations

import re
import sys
import time
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rancid_ng.config.cloginrc import AuthConfig


class ConnectionMethod(Enum):
    """Available connection methods."""
    SSH = "ssh"
    TELNET = "telnet"
    RSH = "rsh"


class LoginSession:
    """
    Manages a login session to a network device.

    This class provides a high-level interface for connecting to
    network devices, handling authentication, and executing commands.
    It abstracts the underlying connection method (SSH, Telnet).

    Example:
        >>> session = LoginSession("router1", debug=True)
        >>> session.configure_auth(auth_config)
        >>> if session.connect():
        ...     output = session.run_command("show version")
        ...     session.close()
    """

    # Default prompt patterns
    DEFAULT_PROMPTS = [
        r'[\r\n][\w\.\-]+[>#]\s*$',  # Cisco style
        r'[\r\n][\w\.\-]+%\s*$',      # Unix style
        r'[\r\n][\w\.\-]+\$\s*$',     # Unix user
        r'[\r\n]>>\s*$',              # Some devices
        r'\[[\w\.\-]+\]\s*$',         # Juniper style
    ]

    # Pager prompts to handle
    PAGER_PROMPTS = [
        r'--More--',
        r'--\(more\)--',
        r'--More-- or \(q\)uit',
        r'<--- More --->',
        r'\[yes/no\]:?\s*$',
        r'\[confirm\]',
        r'Press any key to continue',
        r'lines \d+-\d+',
    ]

    # Error patterns
    ERROR_PATTERNS = [
        r'% Invalid input',
        r'% Incomplete command',
        r'% Ambiguous command',
        r'% Authorization failed',
        r'% Access denied',
        r'Error:',
        r'error:',
        r'command not found',
        r'syntax error',
    ]

    def __init__(
        self,
        hostname: str,
        login_script: str = "clogin",
        timeout: int = 90,
        debug: bool = False,
    ):
        """
        Initialize a login session.

        Args:
            hostname: Target device hostname or IP
            login_script: Login script type (clogin, jlogin, etc.)
            timeout: Command timeout in seconds
            debug: Enable debug output
        """
        self.hostname = hostname
        self.login_script = login_script
        self.timeout = timeout
        self.debug = debug

        # Authentication configuration
        self.user: str = ""
        self.password: str = ""
        self.enable_password: str = ""
        self.methods: list[ConnectionMethod] = [
            ConnectionMethod.SSH,
            ConnectionMethod.TELNET,
        ]
        self.noenable: bool = False
        self.autoenable: bool = False

        # Prompt patterns
        self.user_prompt = r'(Username|login|user name):\s*$'
        self.pass_prompt = r'[Pp]assword:\s*$'
        self.enable_prompt = r'[Pp]assword:\s*$'

        # Connection state
        self._connection = None
        self._prompt: str | None = None
        self._enabled: bool = False
        self._connected: bool = False

    def configure_auth(self, auth: "AuthConfig") -> None:
        """
        Configure authentication from an AuthConfig object.

        Args:
            auth: Authentication configuration
        """
        if auth.user:
            self.user = auth.user
        if auth.password:
            self.password = auth.password
        if auth.enable_password:
            self.enable_password = auth.enable_password
        if auth.user_password:
            self.password = auth.user_password
        if auth.methods:
            self.methods = [ConnectionMethod(m) for m in auth.methods]
        if auth.user_prompt:
            self.user_prompt = auth.user_prompt
        if auth.pass_prompt:
            self.pass_prompt = auth.pass_prompt
        if auth.enable_prompt:
            self.enable_prompt = auth.enable_prompt
        if auth.noenable:
            self.noenable = auth.noenable
        if auth.autoenable:
            self.autoenable = auth.autoenable
        if auth.timeout:
            self.timeout = auth.timeout

    def connect(self) -> bool:
        """
        Establish connection to the device.

        Tries each configured connection method in order until one succeeds.

        Returns:
            True if connected successfully
        """
        for method in self.methods:
            try:
                if self.debug:
                    print(f"Trying {method.value} to {self.hostname}...",
                          file=sys.stderr)

                if method == ConnectionMethod.SSH:
                    self._connect_ssh()
                elif method == ConnectionMethod.TELNET:
                    self._connect_telnet()
                else:
                    continue

                # If we get here, connection succeeded
                self._connected = True

                # Handle initial authentication
                if self._authenticate():
                    # Enter enable mode if needed
                    if not self.noenable and not self.autoenable:
                        self._enable()

                    if self.debug:
                        print(f"Connected to {self.hostname} via {method.value}",
                              file=sys.stderr)
                    return True

            except Exception as e:
                if self.debug:
                    print(f"Connection via {method.value} failed: {e}",
                          file=sys.stderr)
                self._connection = None
                continue

        return False

    def _connect_ssh(self) -> None:
        """Establish SSH connection."""
        from rancid_ng.login.ssh import SSHConnection

        self._connection = SSHConnection(
            hostname=self.hostname,
            username=self.user,
            password=self.password,
            timeout=self.timeout,
            debug=self.debug,
        )
        self._connection.connect()

    def _connect_telnet(self) -> None:
        """Establish Telnet connection."""
        from rancid_ng.login.telnet import TelnetConnection

        self._connection = TelnetConnection(
            hostname=self.hostname,
            timeout=self.timeout,
            debug=self.debug,
        )
        self._connection.connect()

    def _authenticate(self) -> bool:
        """
        Handle initial authentication prompts.

        Returns:
            True if authentication successful
        """
        if not self._connection:
            return False

        # For SSH, authentication is handled during connection
        # For Telnet, we need to handle it here
        if isinstance(self._connection, type) and \
           self._connection.__class__.__name__ == "TelnetConnection":
            return self._telnet_authenticate()

        return True

    def _telnet_authenticate(self) -> bool:
        """Handle Telnet authentication."""
        # Wait for login prompt
        output = self._connection.expect(
            [self.user_prompt, self.pass_prompt] + self.DEFAULT_PROMPTS,
            timeout=self.timeout
        )

        if not output:
            return False

        match_index = output[0]

        # Send username if prompted
        if match_index == 0:  # User prompt
            self._connection.send(self.user + "\n")
            output = self._connection.expect(
                [self.pass_prompt] + self.DEFAULT_PROMPTS,
                timeout=self.timeout
            )
            if not output:
                return False
            match_index = output[0]

        # Send password if prompted
        if match_index == 0:  # Password prompt
            self._connection.send(self.password + "\n")
            output = self._connection.expect(
                self.DEFAULT_PROMPTS,
                timeout=self.timeout
            )
            if not output:
                return False

        return True

    def _enable(self) -> bool:
        """
        Enter privileged (enable) mode.

        Returns:
            True if enable succeeded
        """
        if not self._connection or self._enabled:
            return self._enabled

        # Check if already in enable mode
        if self._prompt and self._prompt.endswith("#"):
            self._enabled = True
            return True

        # Send enable command
        self._connection.send("enable\n")

        # Wait for password prompt or command prompt
        output = self._connection.expect(
            [self.enable_prompt] + self.DEFAULT_PROMPTS,
            timeout=self.timeout
        )

        if not output:
            return False

        if output[0] == 0:  # Password prompt
            self._connection.send((self.enable_password or self.password) + "\n")
            output = self._connection.expect(
                self.DEFAULT_PROMPTS,
                timeout=self.timeout
            )
            if not output:
                return False

        self._enabled = True
        return True

    def run_command(
        self,
        command: str,
        timeout: int | None = None,
    ) -> str | None:
        """
        Execute a command and return the output.

        Handles pager prompts automatically.

        Args:
            command: Command to execute
            timeout: Optional command-specific timeout

        Returns:
            Command output, or None on error
        """
        if not self._connection:
            return None

        timeout = timeout or self.timeout

        # Send command
        self._connection.send(command + "\n")

        # Collect output, handling pager prompts
        output_lines = []

        while True:
            # Wait for prompt or pager
            result = self._connection.expect(
                self.PAGER_PROMPTS + self.DEFAULT_PROMPTS,
                timeout=timeout
            )

            if not result:
                # Timeout - return what we have
                break

            match_index, output = result

            # Add output to collection
            if output:
                output_lines.append(output)

            # Check if we hit a pager prompt
            if match_index < len(self.PAGER_PROMPTS):
                # Send space to continue
                self._connection.send(" ")
                continue
            else:
                # Hit command prompt - done
                break

        return "".join(output_lines)

    def send(self, data: str) -> None:
        """
        Send raw data to the device.

        Args:
            data: Data to send
        """
        if self._connection:
            self._connection.send(data)

    def expect(
        self,
        patterns: list[str],
        timeout: int | None = None,
    ) -> tuple[int, str] | None:
        """
        Wait for one of the patterns to match.

        Args:
            patterns: List of regex patterns
            timeout: Optional timeout

        Returns:
            Tuple of (match_index, output) or None on timeout
        """
        if not self._connection:
            return None

        return self._connection.expect(patterns, timeout or self.timeout)

    def close(self) -> None:
        """Close the connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
        self._connected = False
        self._enabled = False

    @property
    def connected(self) -> bool:
        """Check if connected."""
        return self._connected and self._connection is not None

    def disable_pager(self) -> bool:
        """
        Disable terminal paging on the device.

        Tries common commands to disable paging.

        Returns:
            True if pager was disabled
        """
        # Common pager disable commands
        pager_commands = [
            "terminal length 0",
            "terminal pager 0",
            "set cli screen-length 0",
            "screen-length 0 temporary",
            "no paging",
            "paging off",
        ]

        for cmd in pager_commands:
            output = self.run_command(cmd, timeout=5)
            if output and not any(
                re.search(pattern, output)
                for pattern in self.ERROR_PATTERNS
            ):
                if self.debug:
                    print(f"Disabled pager with: {cmd}", file=sys.stderr)
                return True

        return False
