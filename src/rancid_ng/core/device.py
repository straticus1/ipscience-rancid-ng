"""
Device Module Base Class for RANCID-NG.

This module defines the abstract base class that all device-specific
modules must implement. It provides the common interface and utilities
for device configuration collection.

The design mirrors the original Perl device module structure:
- init() - Initialize state for a collection run
- inloop() - Main parsing loop for device output
- Command handlers - Device-specific command output parsers
"""

from __future__ import annotations

import re
import sys
from abc import ABC, abstractmethod
from io import StringIO
from typing import TYPE_CHECKING, Any, Callable, TextIO

from rancid_ng.core.processor import ProcessHistory
from rancid_ng.core.filters import OutputFilter, FilterMode

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


class DeviceModule(ABC):
    """
    Abstract base class for device-specific configuration collectors.

    Each supported device type should subclass this and implement
    the required methods. The class handles:
    - Command table management
    - Output processing via ProcessHistory
    - Common parsing utilities
    - Clean run detection

    Example:
        class CiscoIOS(DeviceModule):
            name = "ios"
            aliases = ["cisco"]

            def init(self):
                self.found_version = False
                self.process_history.add("", "", "",
                    f"!RANCID-CONTENT-TYPE: {self.devtype}\\n!\\n")

            def inloop(self, session):
                # Parse device output
                pass

            def show_version(self, session, cmd):
                # Parse 'show version' output
                pass
    """

    # Class attributes to be overridden by subclasses
    name: str = ""  # Device type name (e.g., "ios", "junos")
    aliases: list[str] = []  # Alternative names
    login_script: str = "clogin"  # Default login script
    default_timeout: int = 90  # Default command timeout in seconds

    def __init__(
        self,
        hostname: str,
        devtype: str | None = None,
        output: TextIO | None = None,
        debug: bool = False,
    ):
        """
        Initialize the device module.

        Args:
            hostname: Target device hostname
            devtype: Device type name (defaults to class name)
            output: Output stream for configuration (defaults to stdout)
            debug: Enable debug output
        """
        self.hostname = hostname
        self.devtype = devtype or self.name
        self.output = output or sys.stdout
        self.debug = debug

        # State tracking
        self.clean_run = False
        self.found_end = False
        self.prompt: str | None = None

        # Command handling
        self.commands: dict[str, str] = {}  # cmd -> handler name
        self.command_table: list[tuple[str, str]] = []  # (cmd, handler)

        # Output processing
        self.process_history = ProcessHistory(self.output)
        self.output_filter = OutputFilter.from_env()

        # Internal state
        self._commands_run: set[str] = set()

    @abstractmethod
    def init(self) -> int:
        """
        Initialize state for a new collection run.

        This method is called before collection begins and should:
        - Reset any state variables
        - Output the RANCID-CONTENT-TYPE header
        - Initialize section separators

        Returns:
            0 on success, non-zero on error
        """
        pass

    @abstractmethod
    def inloop(self, session: "LoginSession") -> int:
        """
        Main parsing loop for device output.

        This method reads output from the device session and dispatches
        to the appropriate command handlers based on prompt matching.

        Args:
            session: Active login session to the device

        Returns:
            0 on success, non-zero on error
        """
        pass

    def register_command(
        self,
        command: str,
        handler: str | Callable,
    ) -> None:
        """
        Register a command and its handler.

        Args:
            command: Device command (e.g., "show version")
            handler: Handler method name or callable
        """
        if callable(handler):
            handler_name = handler.__name__
        else:
            handler_name = handler

        self.commands[command] = handler_name
        self.command_table.append((command, handler_name))

    def get_handler(self, command: str) -> Callable | None:
        """
        Get the handler method for a command.

        Args:
            command: Device command

        Returns:
            Handler method or None
        """
        handler_name = self.commands.get(command)
        if handler_name:
            return getattr(self, handler_name, None)
        return None

    def run_command(
        self,
        session: "LoginSession",
        command: str,
    ) -> int:
        """
        Execute a command and process its output.

        This is a generic handler that simply outputs the command
        response without special processing.

        Args:
            session: Active login session
            command: Command to execute

        Returns:
            0 on success, non-zero on error
        """
        output = session.run_command(command)
        if output is None:
            return -1

        for line in output.splitlines(keepends=True):
            line = self._filter_line(line)
            self.process_history.add("", "", "", line)

        return 0

    def _filter_line(self, line: str) -> str:
        """
        Apply output filters to a line.

        Args:
            line: Raw output line

        Returns:
            Filtered line
        """
        # Strip carriage returns
        line = line.replace("\r", "")

        # Apply configured filters
        return self.output_filter.filter(line)

    def _detect_prompt(self, line: str) -> bool:
        """
        Detect and capture the device prompt.

        Args:
            line: Output line to check

        Returns:
            True if prompt was detected
        """
        # Look for common prompt patterns
        match = re.match(r'^([^#>]+[#>])\s*$', line)
        if match and not self.prompt:
            self.prompt = match.group(1)
            # Escape regex special characters
            self.prompt = re.escape(self.prompt)
            if self.debug:
                print(f"PROMPT MATCH: {self.prompt}", file=sys.stderr)
            return True
        return False

    def _is_prompt(self, line: str) -> bool:
        """
        Check if a line matches the device prompt.

        Args:
            line: Output line to check

        Returns:
            True if line matches the prompt
        """
        if not self.prompt:
            return False
        return bool(re.match(f'^{self.prompt}', line))

    def _match_command(self, line: str) -> str | None:
        """
        Check if a line contains a command from the command table.

        Args:
            line: Output line to check

        Returns:
            Matched command or None
        """
        # Build regex from commands
        cmds_pattern = "|".join(re.escape(cmd) for cmd in self.commands.keys())
        if not cmds_pattern:
            return None

        match = re.search(f'[>#]\\s*({cmds_pattern})\\s*$', line)
        if match:
            return match.group(1)
        return None

    def debug_print(self, message: str) -> None:
        """
        Print a debug message if debugging is enabled.

        Args:
            message: Debug message
        """
        if self.debug:
            print(message, file=sys.stderr)

    def finalize(self) -> int:
        """
        Finalize collection and flush output.

        Returns:
            0 on success
        """
        self.process_history.flush()
        return 0


class GenericDevice(DeviceModule):
    """
    Generic device module for basic configuration collection.

    This can be used as a fallback for devices without specific
    module implementations, or as a template for new modules.
    """

    name = "generic"
    aliases = []

    def init(self) -> int:
        """Initialize for generic device collection."""
        self.process_history.add(
            "", "", "",
            f"!RANCID-CONTENT-TYPE: {self.devtype}\n!\n"
        )
        return 0

    def inloop(self, session: "LoginSession") -> int:
        """
        Generic parsing loop.

        Simply executes all registered commands and outputs their results.
        """
        for cmd, handler_name in self.command_table:
            if cmd in self._commands_run:
                continue

            handler = self.get_handler(cmd)
            if handler:
                result = handler(session, cmd)
                if result < 0:
                    return result
            else:
                result = self.run_command(session, cmd)
                if result < 0:
                    return result

            self._commands_run.add(cmd)

        self.clean_run = True
        return 0
