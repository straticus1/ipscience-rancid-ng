"""
Expect-like Session Handler for RANCID-NG.

Provides an alternative expect implementation using pexpect
for cases where more advanced spawn/expect functionality is needed.
"""

from __future__ import annotations

import re
import sys
import time
from typing import TYPE_CHECKING

try:
    import pexpect
    HAS_PEXPECT = True
except ImportError:
    HAS_PEXPECT = False


class ExpectSession:
    """
    Expect-like session using pexpect.

    This provides functionality similar to the Expect/Tcl scripts
    used in the original RANCID login handlers.

    Example:
        >>> session = ExpectSession()
        >>> session.spawn("ssh router1")
        >>> session.expect("Password:")
        >>> session.send("secret\\n")
        >>> session.expect("#")
        >>> output = session.before
    """

    # Timeout exception for compatibility
    TIMEOUT = pexpect.TIMEOUT if HAS_PEXPECT else Exception
    EOF = pexpect.EOF if HAS_PEXPECT else Exception

    def __init__(
        self,
        timeout: int = 30,
        debug: bool = False,
        encoding: str = "utf-8",
    ):
        """
        Initialize expect session.

        Args:
            timeout: Default timeout for expect operations
            debug: Enable debug output
            encoding: Character encoding
        """
        if not HAS_PEXPECT:
            raise ImportError("pexpect is required for ExpectSession")

        self.timeout = timeout
        self.debug = debug
        self.encoding = encoding

        self._child: pexpect.spawn | None = None
        self.before: str = ""
        self.after: str = ""
        self.match: re.Match | None = None

    def spawn(
        self,
        command: str,
        args: list[str] | None = None,
        timeout: int | None = None,
        env: dict | None = None,
    ) -> bool:
        """
        Spawn a new process.

        Args:
            command: Command to execute
            args: Command arguments
            timeout: Optional timeout override
            env: Optional environment variables

        Returns:
            True if spawn successful
        """
        try:
            if args:
                self._child = pexpect.spawn(
                    command,
                    args,
                    timeout=timeout or self.timeout,
                    encoding=self.encoding,
                    env=env,
                )
            else:
                self._child = pexpect.spawn(
                    command,
                    timeout=timeout or self.timeout,
                    encoding=self.encoding,
                    env=env,
                )

            if self.debug:
                self._child.logfile = sys.stderr

            return True

        except Exception as e:
            if self.debug:
                print(f"Spawn failed: {e}", file=sys.stderr)
            return False

    def ssh(
        self,
        hostname: str,
        username: str = "",
        port: int = 22,
        identity: str | None = None,
        options: list[str] | None = None,
    ) -> bool:
        """
        Start an SSH connection.

        Args:
            hostname: Target hostname
            username: SSH username
            port: SSH port
            identity: SSH identity file
            options: Additional SSH options

        Returns:
            True if spawn successful
        """
        args = []

        if username:
            args.extend(["-l", username])

        if port != 22:
            args.extend(["-p", str(port)])

        if identity:
            args.extend(["-i", identity])

        # Add common options
        args.extend([
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
        ])

        if options:
            args.extend(options)

        args.append(hostname)

        return self.spawn("ssh", args)

    def telnet(
        self,
        hostname: str,
        port: int = 23,
    ) -> bool:
        """
        Start a Telnet connection.

        Args:
            hostname: Target hostname
            port: Telnet port

        Returns:
            True if spawn successful
        """
        args = [hostname]
        if port != 23:
            args.append(str(port))

        return self.spawn("telnet", args)

    def send(self, data: str) -> None:
        """
        Send data to the spawned process.

        Args:
            data: Data to send
        """
        if not self._child:
            raise RuntimeError("No process spawned")

        self._child.send(data)

        if self.debug:
            preview = data.strip()[:50]
            print(f"SEND: {preview}", file=sys.stderr)

    def sendline(self, line: str = "") -> None:
        """
        Send a line (with newline) to the process.

        Args:
            line: Line to send (newline is added)
        """
        if not self._child:
            raise RuntimeError("No process spawned")

        self._child.sendline(line)

    def expect(
        self,
        patterns: str | list[str],
        timeout: int | None = None,
    ) -> int:
        """
        Wait for patterns to match in output.

        Args:
            patterns: Pattern(s) to match
            timeout: Optional timeout override

        Returns:
            Index of matched pattern

        Raises:
            pexpect.TIMEOUT: On timeout
            pexpect.EOF: On end of file
        """
        if not self._child:
            raise RuntimeError("No process spawned")

        if isinstance(patterns, str):
            patterns = [patterns]

        try:
            index = self._child.expect(
                patterns,
                timeout=timeout or self.timeout
            )

            self.before = self._child.before or ""
            self.after = self._child.after or ""
            self.match = self._child.match

            if self.debug:
                print(f"MATCH[{index}]: {patterns[index]}", file=sys.stderr)

            return index

        except pexpect.TIMEOUT:
            self.before = self._child.before or ""
            raise
        except pexpect.EOF:
            self.before = self._child.before or ""
            raise

    def expect_exact(
        self,
        patterns: str | list[str],
        timeout: int | None = None,
    ) -> int:
        """
        Wait for exact string match (not regex).

        Args:
            patterns: String(s) to match exactly
            timeout: Optional timeout override

        Returns:
            Index of matched pattern
        """
        if not self._child:
            raise RuntimeError("No process spawned")

        if isinstance(patterns, str):
            patterns = [patterns]

        index = self._child.expect_exact(
            patterns,
            timeout=timeout or self.timeout
        )

        self.before = self._child.before or ""
        self.after = self._child.after or ""

        return index

    def read_nonblocking(self, size: int = 1000, timeout: float = 0.1) -> str:
        """
        Read available data without blocking.

        Args:
            size: Maximum bytes to read
            timeout: Read timeout

        Returns:
            Available data
        """
        if not self._child:
            return ""

        try:
            return self._child.read_nonblocking(size, timeout)
        except pexpect.TIMEOUT:
            return ""
        except pexpect.EOF:
            return ""

    def interact(self) -> None:
        """
        Give control of the child to the user.

        This is useful for debugging or manual intervention.
        """
        if self._child:
            self._child.interact()

    def close(self) -> None:
        """Close the spawned process."""
        if self._child:
            self._child.close()
            self._child = None

    @property
    def isalive(self) -> bool:
        """Check if the process is still running."""
        return self._child is not None and self._child.isalive()

    @property
    def exitstatus(self) -> int | None:
        """Get exit status of the process."""
        if self._child:
            return self._child.exitstatus
        return None


class CloginExpect(ExpectSession):
    """
    Specialized expect session for Cisco-style login.

    Handles common Cisco IOS authentication and enable sequences.
    """

    # Common prompts
    USER_PROMPT = r"(Username|login|user name):\s*$"
    PASS_PROMPT = r"[Pp]assword:\s*$"
    ENABLE_PROMPT = r"[Pp]assword:\s*$"
    CMD_PROMPT = r"[\w\.\-]+[>#]\s*$"

    def __init__(self, *args, **kwargs):
        """Initialize Cisco login session."""
        super().__init__(*args, **kwargs)

        self.user_prompt = self.USER_PROMPT
        self.pass_prompt = self.PASS_PROMPT
        self.enable_prompt = self.ENABLE_PROMPT
        self.cmd_prompt = self.CMD_PROMPT

    def login(
        self,
        hostname: str,
        username: str,
        password: str,
        enable_password: str | None = None,
        method: str = "ssh",
    ) -> bool:
        """
        Perform full login sequence.

        Args:
            hostname: Target device
            username: Login username
            password: Login password
            enable_password: Enable mode password
            method: Connection method (ssh/telnet)

        Returns:
            True if login successful
        """
        # Start connection
        if method == "ssh":
            if not self.ssh(hostname, username):
                return False
        else:
            if not self.telnet(hostname):
                return False

        # Handle authentication
        try:
            patterns = [
                self.user_prompt,
                self.pass_prompt,
                self.cmd_prompt,
                pexpect.TIMEOUT,
                pexpect.EOF,
            ]

            index = self.expect(patterns)

            # Username prompt
            if index == 0:
                self.sendline(username)
                index = self.expect(patterns)

            # Password prompt
            if index == 1:
                self.sendline(password)
                index = self.expect(patterns)

            # Command prompt - success
            if index == 2:
                # Check if we're in enable mode
                if ">" in self.after:
                    # Need to enable
                    if enable_password:
                        return self.enable(enable_password)
                return True

            # Timeout or EOF - failure
            return False

        except (pexpect.TIMEOUT, pexpect.EOF):
            return False

    def enable(self, password: str) -> bool:
        """
        Enter enable mode.

        Args:
            password: Enable password

        Returns:
            True if enable successful
        """
        try:
            self.sendline("enable")

            index = self.expect([
                self.enable_prompt,
                self.cmd_prompt,
            ])

            if index == 0:
                self.sendline(password)
                self.expect(self.cmd_prompt)

            return True

        except (pexpect.TIMEOUT, pexpect.EOF):
            return False

    def run_command(self, command: str) -> str:
        """
        Execute a command and return output.

        Args:
            command: Command to execute

        Returns:
            Command output
        """
        self.sendline(command)
        self.expect(self.cmd_prompt)
        return self.before
