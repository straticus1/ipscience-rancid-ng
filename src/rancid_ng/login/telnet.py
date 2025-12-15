"""
Telnet Connection Handler for RANCID-NG.

Provides Telnet connectivity with expect-like functionality.
"""

from __future__ import annotations

import re
import socket
import sys
import telnetlib
import time
from typing import TYPE_CHECKING


class TelnetConnection:
    """
    Telnet connection handler with expect-like capabilities.

    Uses the standard library telnetlib for connectivity and provides
    methods for sending commands and waiting for patterns in output.
    """

    def __init__(
        self,
        hostname: str,
        port: int = 23,
        timeout: int = 30,
        debug: bool = False,
    ):
        """
        Initialize Telnet connection parameters.

        Args:
            hostname: Target hostname or IP
            port: Telnet port
            timeout: Connection timeout
            debug: Enable debug output
        """
        self.hostname = hostname
        self.port = port
        self.timeout = timeout
        self.debug = debug

        self._tn: telnetlib.Telnet | None = None
        self._buffer: str = ""

    def connect(self) -> bool:
        """
        Establish Telnet connection.

        Returns:
            True if connection successful
        """
        try:
            if self.debug:
                print(f"Telnet connecting to {self.hostname}:{self.port}",
                      file=sys.stderr)

            self._tn = telnetlib.Telnet(
                self.hostname,
                self.port,
                timeout=self.timeout
            )

            if self.debug:
                print(f"Telnet connected to {self.hostname}", file=sys.stderr)

            return True

        except socket.timeout:
            if self.debug:
                print(f"Telnet connection timeout", file=sys.stderr)
            raise
        except ConnectionRefusedError:
            if self.debug:
                print(f"Telnet connection refused", file=sys.stderr)
            raise
        except Exception as e:
            if self.debug:
                print(f"Telnet connection error: {e}", file=sys.stderr)
            raise

    def send(self, data: str) -> None:
        """
        Send data to the Telnet connection.

        Args:
            data: Data to send
        """
        if not self._tn:
            raise RuntimeError("Not connected")

        self._tn.write(data.encode('utf-8'))

        if self.debug and data.strip():
            print(f"SEND: {data.strip()}", file=sys.stderr)

    def recv(self, timeout: float = 0.1) -> str:
        """
        Receive available data from the connection.

        Args:
            timeout: Read timeout in seconds

        Returns:
            Received data
        """
        if not self._tn:
            return ""

        data = ""

        try:
            # Read any available data
            chunk = self._tn.read_very_eager().decode('utf-8', errors='replace')
            if chunk:
                data = chunk
                self._buffer += data

                if self.debug and data.strip():
                    preview = data[:200] + "..." if len(data) > 200 else data
                    print(f"RECV: {preview.strip()}", file=sys.stderr)

        except EOFError:
            pass

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
        if not self._tn:
            return None

        # Compile patterns for telnetlib
        compiled = [re.compile(p.encode('utf-8'), re.MULTILINE) for p in patterns]

        try:
            index, match, data = self._tn.expect(compiled, timeout)

            if index >= 0 and match:
                output = data.decode('utf-8', errors='replace')

                if self.debug:
                    print(f"MATCH pattern {index}: {patterns[index]}", file=sys.stderr)

                return (index, output[:match.start()])

        except EOFError:
            if self.debug:
                print("EXPECT: Connection closed", file=sys.stderr)

        return None

    def read_until(
        self,
        pattern: str,
        timeout: int = 30,
    ) -> str | None:
        """
        Read until a pattern matches.

        Args:
            pattern: String to match
            timeout: Maximum time to wait

        Returns:
            Output including the match, or None on timeout
        """
        if not self._tn:
            return None

        try:
            data = self._tn.read_until(
                pattern.encode('utf-8'),
                timeout=timeout
            )
            return data.decode('utf-8', errors='replace')
        except EOFError:
            return None

    def close(self) -> None:
        """Close the Telnet connection."""
        if self._tn:
            self._tn.close()
            self._tn = None

        if self.debug:
            print(f"Telnet connection closed", file=sys.stderr)

    @property
    def connected(self) -> bool:
        """Check if connected."""
        if not self._tn:
            return False

        try:
            # Try to check connection state
            return self._tn.sock is not None
        except Exception:
            return False
