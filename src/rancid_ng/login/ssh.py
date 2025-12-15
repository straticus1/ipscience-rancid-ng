"""
SSH Connection Handler for RANCID-NG.

Provides SSH connectivity using paramiko with expect-like functionality.
"""

from __future__ import annotations

import re
import socket
import sys
import time
from typing import TYPE_CHECKING

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


class SSHConnection:
    """
    SSH connection handler with expect-like capabilities.

    Uses paramiko for SSH connectivity and provides methods for
    sending commands and waiting for patterns in output.
    """

    def __init__(
        self,
        hostname: str,
        username: str = "",
        password: str = "",
        port: int = 22,
        timeout: int = 30,
        debug: bool = False,
        identity_file: str | None = None,
        ciphers: list[str] | None = None,
    ):
        """
        Initialize SSH connection parameters.

        Args:
            hostname: Target hostname or IP
            username: SSH username
            password: SSH password
            port: SSH port
            timeout: Connection timeout
            debug: Enable debug output
            identity_file: Path to SSH private key
            ciphers: List of allowed ciphers
        """
        if not HAS_PARAMIKO:
            raise ImportError("paramiko is required for SSH connections")

        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.debug = debug
        self.identity_file = identity_file
        self.ciphers = ciphers

        self._client: paramiko.SSHClient | None = None
        self._channel: paramiko.Channel | None = None
        self._buffer: str = ""

    def connect(self) -> bool:
        """
        Establish SSH connection.

        Returns:
            True if connection successful
        """
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Prepare connection kwargs
        connect_kwargs = {
            "hostname": self.hostname,
            "port": self.port,
            "username": self.username,
            "timeout": self.timeout,
            "allow_agent": True,
            "look_for_keys": True,
        }

        # Add password if provided
        if self.password:
            connect_kwargs["password"] = self.password

        # Add identity file if provided
        if self.identity_file:
            connect_kwargs["key_filename"] = self.identity_file

        try:
            if self.debug:
                print(f"SSH connecting to {self.hostname}:{self.port}",
                      file=sys.stderr)

            self._client.connect(**connect_kwargs)

            # Get interactive shell
            self._channel = self._client.invoke_shell(
                width=512,
                height=24,
            )
            self._channel.settimeout(self.timeout)

            if self.debug:
                print(f"SSH connected to {self.hostname}", file=sys.stderr)

            return True

        except paramiko.AuthenticationException as e:
            if self.debug:
                print(f"SSH authentication failed: {e}", file=sys.stderr)
            raise
        except paramiko.SSHException as e:
            if self.debug:
                print(f"SSH error: {e}", file=sys.stderr)
            raise
        except socket.timeout:
            if self.debug:
                print(f"SSH connection timeout", file=sys.stderr)
            raise
        except Exception as e:
            if self.debug:
                print(f"SSH connection error: {e}", file=sys.stderr)
            raise

    def send(self, data: str) -> None:
        """
        Send data to the SSH channel.

        Args:
            data: Data to send
        """
        if not self._channel:
            raise RuntimeError("Not connected")

        self._channel.send(data.encode('utf-8'))

        if self.debug and data.strip():
            print(f"SEND: {data.strip()}", file=sys.stderr)

    def recv(self, timeout: float = 0.1) -> str:
        """
        Receive available data from the channel.

        Args:
            timeout: Read timeout in seconds

        Returns:
            Received data
        """
        if not self._channel:
            return ""

        data = ""
        self._channel.settimeout(timeout)

        try:
            while self._channel.recv_ready():
                chunk = self._channel.recv(4096).decode('utf-8', errors='replace')
                data += chunk
        except socket.timeout:
            pass

        if data:
            self._buffer += data
            if self.debug and data.strip():
                # Only show first 200 chars in debug
                preview = data[:200] + "..." if len(data) > 200 else data
                print(f"RECV: {preview.strip()}", file=sys.stderr)

        return data

    def expect(
        self,
        patterns: list[str],
        timeout: int = 30,
    ) -> tuple[int, str] | None:
        """
        Wait for one of the patterns to match in the output.

        Args:
            patterns: List of regex patterns to match
            timeout: Maximum time to wait

        Returns:
            Tuple of (pattern_index, output_before_match) or None on timeout
        """
        if not self._channel:
            return None

        # Compile patterns
        compiled = [re.compile(p, re.MULTILINE) for p in patterns]

        start_time = time.time()
        output = ""

        while time.time() - start_time < timeout:
            # Check for data
            self.recv(timeout=0.1)

            # Check patterns against buffer
            for i, pattern in enumerate(compiled):
                match = pattern.search(self._buffer)
                if match:
                    # Found match - return output up to match
                    output = self._buffer[:match.start()]
                    self._buffer = self._buffer[match.end():]

                    if self.debug:
                        print(f"MATCH pattern {i}: {patterns[i]}", file=sys.stderr)

                    return (i, output)

            # Small delay to avoid busy loop
            time.sleep(0.05)

        if self.debug:
            print(f"EXPECT timeout after {timeout}s", file=sys.stderr)

        return None

    def read_until(
        self,
        pattern: str,
        timeout: int = 30,
    ) -> str | None:
        """
        Read until a pattern matches.

        Args:
            pattern: Regex pattern
            timeout: Maximum time to wait

        Returns:
            Output including the match, or None on timeout
        """
        result = self.expect([pattern], timeout)
        if result:
            return result[1]
        return None

    def close(self) -> None:
        """Close the SSH connection."""
        if self._channel:
            self._channel.close()
            self._channel = None

        if self._client:
            self._client.close()
            self._client = None

        if self.debug:
            print(f"SSH connection closed", file=sys.stderr)

    @property
    def connected(self) -> bool:
        """Check if connected."""
        return (
            self._client is not None and
            self._client.get_transport() is not None and
            self._client.get_transport().is_active()
        )
